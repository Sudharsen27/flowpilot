"""Read-only pipeline figures and forecasts, aggregated in SQL from persisted deals.

Money is aggregated as integer cents: each deal's amount is converted to cents and its
weighted value is rounded half-up to the cent once (PER_DEAL_HALF_UP_CENTS). Totals are
sums of those integers, so every breakdown reconciles exactly with its total and nothing
passes through float. Integer arithmetic also keeps SQLite and PostgreSQL identical.
Forecast category totals are sums of the same per-deal cents, so they add up exactly too.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ColumnElement, and_, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.deal import (
    CLOSED_DEAL_STAGES,
    DEAL_STAGE_DEFAULT_PROBABILITY,
    DEFAULT_FORECAST_CATEGORY,
    OPEN_DEAL_STAGES,
    Deal,
    DealStage,
    ForecastCategory,
    effective_probability,
)
from app.models.organization import Organization
from app.models.sales_target import SalesTarget
from app.models.user import User
from app.schemas.pipeline import (
    ForecastAssumption,
    ForecastAssumptionCode,
    ForecastCategoryDeal,
    ForecastCategoryDeals,
    ForecastCategoryTotals,
    ForecastGranularity,
    ForecastOpenTotals,
    ForecastPastDue,
    ForecastPeriod,
    ForecastStageProbability,
    ForecastTarget,
    ForecastTargetBasis,
    ForecastTargetComparison,
    ForecastTargetStatus,
    PipelineForecast,
    PipelineMonth,
    PipelineStageSummary,
    PipelineSummary,
    PipelineTotals,
    PipelineWeightedTotals,
)

FORECAST_MAX_PERIODS = {ForecastGranularity.MONTH: 24, ForecastGranularity.QUARTER: 8}
FORECAST_DEFAULT_PERIODS = {ForecastGranularity.MONTH: 6, ForecastGranularity.QUARTER: 4}
_MONTHS_PER_PERIOD = {ForecastGranularity.MONTH: 1, ForecastGranularity.QUARTER: 3}

_OPEN_STAGE_VALUES = tuple(stage.value for stage in DealStage if stage in OPEN_DEAL_STAGES)
_CLOSED_STAGE_VALUES = tuple(stage.value for stage in DealStage if stage in CLOSED_DEAL_STAGES)
_PAST_DUE_BUCKET = -1


def _money(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def _shift_months(month: date, delta: int) -> date:
    index = month.year * 12 + (month.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


def _period_start(day: date, granularity: ForecastGranularity) -> date:
    if granularity == ForecastGranularity.QUARTER:
        return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)
    return day.replace(day=1)


def _period_label(start: date, granularity: ForecastGranularity) -> str:
    if granularity == ForecastGranularity.QUARTER:
        return f"{start.year}-Q{(start.month - 1) // 3 + 1}"
    return f"{start.year}-{start.month:02d}"


def _period_count(granularity: ForecastGranularity, periods: int | None) -> int:
    count = FORECAST_DEFAULT_PERIODS[granularity] if periods is None else periods
    maximum = FORECAST_MAX_PERIODS[granularity]
    if not 1 <= count <= maximum:
        raise UnprocessableError(f"periods must be between 1 and {maximum} for {granularity}")
    return count


def _horizon(today: date, granularity: ForecastGranularity, count: int) -> tuple[list[date], date]:
    """Period starts from the period containing today, and the exclusive horizon end."""
    step = _MONTHS_PER_PERIOD[granularity]
    first = _period_start(today, granularity)
    starts = [_shift_months(first, step * offset) for offset in range(count)]
    return starts, _shift_months(first, step * count)


def _utc_midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _effective_probability() -> ColumnElement[Any]:
    """SQL mirror of effective_probability(), built from the same stage defaults."""
    stage_default = case(
        {stage.value: value for stage, value in DEAL_STAGE_DEFAULT_PROBABILITY.items()},
        value=Deal.stage,
    )
    return case(
        (Deal.stage.in_(_CLOSED_STAGE_VALUES), stage_default),
        else_=func.coalesce(Deal.probability, stage_default),
    )


def _cents(column: Any) -> ColumnElement[Any]:
    # round() makes SQLite's REAL storage exact again; PostgreSQL numeric is already exact.
    return cast(func.round(column * 100), BigInteger)


def _amount_cents() -> ColumnElement[Any]:
    return _cents(Deal.amount)


def _weighted_cents() -> ColumnElement[Any]:
    # Integer floor of (cents * p + 50) / 100: half-up rounding for non-negative amounts.
    return (_amount_cents() * _effective_probability() + 50) // 100


def _forecast_category() -> ColumnElement[Any]:
    """SQL mirror of effective_forecast_category() for open deals: NULL (rows written
    before migration 036) reads as PIPELINE."""
    return func.coalesce(Deal.forecast_category, DEFAULT_FORECAST_CATEGORY.value)


def _bucket(column: Any, boundaries: Sequence[date | datetime]) -> ColumnElement[Any]:
    """Index i when boundaries[i] <= column < boundaries[i + 1]; len - 1 past the last."""
    return case(
        *((column < boundary, index) for index, boundary in enumerate(boundaries[1:])),
        else_=len(boundaries) - 1,
    )


@dataclass
class _Totals:
    count: int = 0
    cents: int = 0
    weighted_cents: int = 0
    override_count: int = 0

    def add(self, other: "_Totals") -> None:
        self.count += other.count
        self.cents += other.cents
        self.weighted_cents += other.weighted_cents
        self.override_count += other.override_count

    def plain(self) -> PipelineTotals:
        return PipelineTotals(count=self.count, total_amount=_money(self.cents))

    def weighted(self) -> PipelineWeightedTotals:
        return PipelineWeightedTotals(
            count=self.count,
            total_amount=_money(self.cents),
            weighted_amount=_money(self.weighted_cents),
        )


_Categories = dict[ForecastCategory, _Totals]


def _no_categories() -> _Categories:
    return {category: _Totals() for category in ForecastCategory}


def _combined(groups: Sequence[_Categories]) -> _Categories:
    merged = _no_categories()
    for group in groups:
        for category, totals in group.items():
            merged[category].add(totals)
    return merged


def _total(categories: _Categories) -> _Totals:
    total = _Totals()
    for totals in categories.values():
        total.add(totals)
    return total


def _open_totals(categories: _Categories) -> ForecastOpenTotals:
    """A bucket's open totals with its category breakdown; both from the same cents."""
    total = _total(categories)
    return ForecastOpenTotals(
        count=total.count,
        total_amount=_money(total.cents),
        weighted_amount=_money(total.weighted_cents),
        override_count=total.override_count,
        category_totals=[
            ForecastCategoryTotals(
                category=category,
                count=totals.count,
                total_amount=_money(totals.cents),
                weighted_amount=_money(totals.weighted_cents),
            )
            for category, totals in categories.items()
        ],
    )


def _attainment_percent(cents: int, target_cents: int) -> str | None:
    """cents / target as a percentage, half-up to one decimal, in integer arithmetic."""
    if target_cents == 0:
        return None
    tenths = (cents * 2000 + target_cents) // (target_cents * 2)
    return f"{tenths // 10}.{tenths % 10}"


@dataclass
class _Targets:
    """Organization target cents by month start, and the months with an owner target."""

    organization: dict[date, int]
    owner_months: set[date]

    def for_range(
        self, months: Sequence[date], figures: Sequence[tuple[ForecastTargetBasis, int]]
    ) -> ForecastTarget:
        missing = [month for month in months if month not in self.organization]
        set_months = len(months) - len(missing)
        if set_months == 0:
            status = ForecastTargetStatus.NONE
        elif missing:
            status = ForecastTargetStatus.PARTIAL
        else:
            status = ForecastTargetStatus.FULL
        target = sum(self.organization.get(month, 0) for month in months)
        comparisons = (
            [
                ForecastTargetComparison(
                    basis=basis,
                    amount=_money(cents),
                    attainment_percent=_attainment_percent(cents, target),
                    remaining_amount=_money(max(target - cents, 0)),
                    above_target_amount=_money(max(cents - target, 0)),
                )
                for basis, cents in figures
            ]
            if status == ForecastTargetStatus.FULL
            else []
        )
        return ForecastTarget(
            status=status,
            amount=None if status == ForecastTargetStatus.NONE else _money(target),
            months_in_range=len(months),
            months_with_target=set_months,
            missing_months=missing,
            has_owner_targets=any(month in self.owner_months for month in months),
            comparisons=comparisons,
        )


def _months(start: date, end: date) -> list[date]:
    """Month starts from start up to the exclusive end."""
    months: list[date] = []
    while start < end:
        months.append(start)
        start = _shift_months(start, 1)
    return months


def _target_figures(
    won_cents: int, categories: _Categories, weighted_cents: int
) -> list[tuple[ForecastTargetBasis, int]]:
    """The four figures compared with a target, in ForecastTarget order."""
    commit = won_cents + categories[ForecastCategory.COMMIT].cents
    best_case = commit + categories[ForecastCategory.BEST_CASE].cents
    return [
        (ForecastTargetBasis.WON, won_cents),
        (ForecastTargetBasis.COMMIT_SCENARIO, commit),
        (ForecastTargetBasis.BEST_CASE_SCENARIO, best_case),
        (ForecastTargetBasis.PROJECTED, won_cents + weighted_cents),
    ]


class PipelineService:
    """Read-only pipeline figures from persisted deals, in exact integer-cent arithmetic."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(
        self, organization_id: str, *, months: int, now: datetime | None = None
    ) -> PipelineSummary:
        currency = self._currency(organization_id)
        current = (now or datetime.now(UTC)).astimezone(UTC)
        today = current.date()

        past_due = case(
            (
                and_(Deal.stage.in_(_OPEN_STAGE_VALUES), Deal.expected_close_date < today),
                1,
            ),
            else_=0,
        )
        deals = (
            select(
                Deal.stage.label("stage"),
                Deal.currency.label("currency"),
                past_due.label("past_due"),
                _amount_cents().label("cents"),
                _weighted_cents().label("weighted_cents"),
            )
            .where(Deal.organization_id == organization_id)
            .subquery()
        )
        rows = self.session.execute(
            select(
                deals.c.stage,
                deals.c.currency,
                deals.c.past_due,
                func.count(),
                func.sum(deals.c.cents),
                func.sum(deals.c.weighted_cents),
            ).group_by(deals.c.stage, deals.c.currency, deals.c.past_due)
        ).all()

        by_stage = {stage: _Totals() for stage in DealStage}
        overdue = _Totals()
        excluded = 0
        for stage_value, deal_currency, is_past_due, count, cents, weighted in rows:
            if deal_currency != currency:
                # Never add amounts across currencies; there is no conversion.
                excluded += count
                continue
            group = _Totals(count=count, cents=int(cents), weighted_cents=int(weighted))
            by_stage[DealStage(stage_value)].add(group)
            if is_past_due:
                overdue.add(group)

        open_totals = _Totals()
        for stage in DealStage:
            if stage not in CLOSED_DEAL_STAGES:
                open_totals.add(by_stage[stage])

        first_month = _shift_months(today.replace(day=1), -(months - 1))
        month_keys = [_shift_months(first_month, offset) for offset in range(months)]
        won = self._won_by_period(organization_id, currency, month_keys, _shift_months(today, 1))

        return PipelineSummary(
            currency=currency,
            generated_at=current,
            open=open_totals.weighted(),
            won=by_stage[DealStage.CLOSED_WON].plain(),
            lost=by_stage[DealStage.CLOSED_LOST].plain(),
            overdue_open=overdue.plain(),
            by_stage=[
                PipelineStageSummary(
                    stage=stage,
                    count=by_stage[stage].count,
                    total_amount=_money(by_stage[stage].cents),
                    weighted_amount=_money(by_stage[stage].weighted_cents),
                    default_probability=DEAL_STAGE_DEFAULT_PROBABILITY[stage],
                )
                for stage in DealStage
            ],
            won_by_month=[
                PipelineMonth(month=month, count=won[i].count, total_amount=_money(won[i].cents))
                for i, month in enumerate(month_keys)
            ],
            excluded_other_currency_count=excluded,
        )

    def forecast(
        self,
        organization_id: str,
        *,
        granularity: ForecastGranularity,
        periods: int | None = None,
        now: datetime | None = None,
    ) -> PipelineForecast:
        count = _period_count(granularity, periods)
        currency = self._currency(organization_id)
        as_of = (now or datetime.now(UTC)).astimezone(UTC)
        today = as_of.date()

        starts, horizon_end = _horizon(today, granularity, count)  # end is exclusive
        first = starts[0]

        bucket = case(
            (Deal.expected_close_date < today, _PAST_DUE_BUCKET),
            else_=_bucket(Deal.expected_close_date, [*starts, horizon_end]),
        )
        open_deals = (
            select(
                bucket.label("bucket"),
                _forecast_category().label("category"),
                Deal.expected_close_date.label("expected_close_date"),
                case((Deal.probability.is_not(None), 1), else_=0).label("override"),
                _amount_cents().label("cents"),
                _weighted_cents().label("weighted_cents"),
            )
            .where(
                Deal.organization_id == organization_id,
                Deal.currency == currency,
                Deal.stage.in_(_OPEN_STAGE_VALUES),
            )
            .subquery()
        )
        open_rows = self.session.execute(
            select(
                open_deals.c.bucket,
                open_deals.c.category,
                func.count(),
                func.sum(open_deals.c.cents),
                func.sum(open_deals.c.weighted_cents),
                func.sum(open_deals.c.override),
                func.min(open_deals.c.expected_close_date),
            ).group_by(open_deals.c.bucket, open_deals.c.category)
        ).all()

        # One row per (bucket, category); bucket totals are the sum of their categories.
        open_buckets = {index: _no_categories() for index in range(_PAST_DUE_BUCKET, count + 1)}
        oldest_past_due: date | None = None
        for index, category, deal_count, cents, weighted, overrides, earliest in open_rows:
            open_buckets[int(index)][ForecastCategory(category)] = _Totals(
                count=deal_count,
                cents=int(cents),
                weighted_cents=int(weighted),
                override_count=int(overrides),
            )
            if index == _PAST_DUE_BUCKET:
                oldest_past_due = min(earliest, oldest_past_due or earliest)
        in_horizon = _combined([open_buckets[index] for index in range(count)])
        all_open = _combined(list(open_buckets.values()))
        open_total = _total(all_open)

        won = self._won_by_period(organization_id, currency, starts, horizon_end)
        targets = self._organization_targets(organization_id, currency, first, horizon_end)
        won_total = _Totals()
        result_periods: list[ForecastPeriod] = []
        for index, start in enumerate(starts):
            won_total.add(won[index])
            end = starts[index + 1] if index + 1 < count else horizon_end
            figures = _target_figures(
                won[index].cents, open_buckets[index], _total(open_buckets[index]).weighted_cents
            )
            result_periods.append(
                ForecastPeriod(
                    label=_period_label(start, granularity),
                    period_start=start,
                    period_end=end - timedelta(days=1),
                    won=won[index].plain(),
                    open=_open_totals(open_buckets[index]),
                    projected_amount=_money(figures[3][1]),
                    commit_scenario_amount=_money(figures[1][1]),
                    best_case_scenario_amount=_money(figures[2][1]),
                    target=targets.for_range(_months(start, end), figures),
                )
            )
        horizon_weighted = _total(in_horizon).weighted_cents
        horizon_figures = _target_figures(won_total.cents, in_horizon, horizon_weighted)
        commit_cents = horizon_figures[1][1]
        best_case_cents = horizon_figures[2][1]
        target_in_horizon = targets.for_range(_months(first, horizon_end), horizon_figures)
        excluded = self._other_currency_count(organization_id, currency)
        past_due = _total(open_buckets[_PAST_DUE_BUCKET])

        return PipelineForecast(
            currency=currency,
            as_of=as_of,
            granularity=granularity,
            horizon_start=first,
            horizon_end=horizon_end - timedelta(days=1),
            periods=result_periods,
            past_due=ForecastPastDue(
                **_open_totals(open_buckets[_PAST_DUE_BUCKET]).model_dump(),
                oldest_expected_close_date=oldest_past_due,
            ),
            beyond_horizon=_open_totals(open_buckets[count]),
            open_pipeline=_open_totals(all_open),
            won_in_horizon=won_total.plain(),
            projected_in_horizon_amount=_money(won_total.cents + horizon_weighted),
            in_horizon_open=_open_totals(in_horizon),
            commit_scenario_amount=_money(commit_cents),
            best_case_scenario_amount=_money(best_case_cents),
            target_in_horizon=target_in_horizon,
            stage_probabilities=[
                ForecastStageProbability(stage=stage, default_probability=probability)
                for stage, probability in DEAL_STAGE_DEFAULT_PROBABILITY.items()
            ],
            assumptions=_assumptions(
                currency,
                granularity,
                override_count=open_total.override_count,
                past_due_count=past_due.count,
                excluded=excluded,
                months_without_target=len(target_in_horizon.missing_months),
                horizon_months=target_in_horizon.months_in_range,
            ),
            excluded_other_currency_count=excluded,
        )

    def forecast_deals(
        self,
        organization_id: str,
        *,
        category: ForecastCategory,
        granularity: ForecastGranularity,
        periods: int | None = None,
        period_start: date | None = None,
        limit: int,
        offset: int,
        now: datetime | None = None,
    ) -> ForecastCategoryDeals:
        """The open deals behind one category of forecast(), for one period or the whole
        horizon, selected with the forecast's own SQL so the totals match to the cent."""
        count = _period_count(granularity, periods)
        currency = self._currency(organization_id)
        as_of = (now or datetime.now(UTC)).astimezone(UTC)
        today = as_of.date()
        starts, horizon_end = _horizon(today, granularity, count)
        if period_start is None:
            range_start, range_end = starts[0], horizon_end
        elif period_start in starts:
            index = starts.index(period_start)
            range_start = period_start
            range_end = starts[index + 1] if index + 1 < count else horizon_end
        else:
            raise UnprocessableError("period_start must be the start of a period in the horizon")

        conditions = [
            Deal.organization_id == organization_id,
            Deal.currency == currency,
            Deal.stage.in_(_OPEN_STAGE_VALUES),
            _forecast_category() == category.value,
            # Deals expected before as_of are past due, never in a period.
            Deal.expected_close_date >= max(today, range_start),
            Deal.expected_close_date < range_end,
        ]
        deal_count, cents, weighted = self.session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(_amount_cents()), 0),
                func.coalesce(func.sum(_weighted_cents()), 0),
            ).where(*conditions)
        ).one()
        # One query for the page, owner names joined in: no per-deal lookups.
        rows = self.session.execute(
            select(Deal, _amount_cents(), _weighted_cents(), User.name)
            .outerjoin(User, User.id == Deal.owner_user_id)
            .where(*conditions)
            .order_by(Deal.expected_close_date, Deal.amount.desc(), Deal.id)
            .limit(limit)
            .offset(offset)
        ).all()

        return ForecastCategoryDeals(
            currency=currency,
            as_of=as_of,
            granularity=granularity,
            category=category,
            horizon_start=starts[0],
            horizon_end=horizon_end - timedelta(days=1),
            range_start=range_start,
            range_end=range_end - timedelta(days=1),
            totals=PipelineWeightedTotals(
                count=deal_count,
                total_amount=_money(int(cents)),
                weighted_amount=_money(int(weighted)),
            ),
            items=[
                ForecastCategoryDeal(
                    id=deal.id,
                    name=deal.name,
                    amount=_money(int(deal_cents)),
                    currency=deal.currency,
                    stage=DealStage(deal.stage),
                    probability=deal.probability,
                    effective_probability=effective_probability(deal.stage, deal.probability),
                    probability_source="STAGE_DEFAULT" if deal.probability is None else "OVERRIDE",
                    forecast_category=category,
                    weighted_amount=_money(int(deal_weighted)),
                    expected_close_date=deal.expected_close_date,
                    period_start=_period_start(deal.expected_close_date, granularity),
                    owner_user_id=deal.owner_user_id,
                    owner_name=owner_name,
                )
                for deal, deal_cents, deal_weighted, owner_name in rows
            ],
            limit=limit,
            offset=offset,
            total=deal_count,
        )

    def _currency(self, organization_id: str) -> str:
        organization = self.session.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization.default_currency

    def _won_by_period(
        self, organization_id: str, currency: str, starts: Sequence[date], end: date
    ) -> list[_Totals]:
        """Won deals per period by closed_at (UTC), for periods starts[i]..next start."""
        boundaries = [_utc_midnight(day) for day in (*starts, end)]
        won = (
            select(
                _bucket(Deal.closed_at, boundaries).label("bucket"),
                _amount_cents().label("cents"),
            )
            .where(
                Deal.organization_id == organization_id,
                Deal.currency == currency,
                Deal.stage == DealStage.CLOSED_WON,
                Deal.closed_at >= boundaries[0],
                Deal.closed_at < boundaries[-1],
            )
            .subquery()
        )
        totals = [_Totals() for _ in starts]
        for index, deal_count, cents in self.session.execute(
            select(won.c.bucket, func.count(), func.sum(won.c.cents)).group_by(won.c.bucket)
        ):
            totals[int(index)] = _Totals(count=deal_count, cents=int(cents))
        return totals

    def _organization_targets(
        self, organization_id: str, currency: str, start: date, end: date
    ) -> _Targets:
        """Monthly targets starting in [start, end), in one grouped query. Organization
        targets are unique per month, so each organization group holds one row."""
        is_organization = SalesTarget.owner_user_id.is_(None)
        rows = self.session.execute(
            select(
                SalesTarget.period_start,
                is_organization.label("is_organization"),
                func.sum(_cents(SalesTarget.amount)),
            )
            .where(
                SalesTarget.organization_id == organization_id,
                SalesTarget.currency == currency,
                SalesTarget.period_start >= start,
                SalesTarget.period_start < end,
            )
            .group_by(SalesTarget.period_start, is_organization)
        ).all()
        targets = _Targets(organization={}, owner_months=set())
        for month, organization_wide, cents in rows:
            if organization_wide:
                targets.organization[month] = int(cents)
            else:
                targets.owner_months.add(month)
        return targets

    def _other_currency_count(self, organization_id: str, currency: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Deal)
                .where(Deal.organization_id == organization_id, Deal.currency != currency)
            )
            or 0
        )


def _assumptions(
    currency: str,
    granularity: ForecastGranularity,
    *,
    override_count: int,
    past_due_count: int,
    excluded: int,
    months_without_target: int,
    horizon_months: int,
) -> list[ForecastAssumption]:
    code = ForecastAssumptionCode
    items = [
        ForecastAssumption(
            code=code.STAGE_PROBABILITY_WEIGHTING,
            detail="Each open deal is weighted by its stage's default probability unless "
            "the deal has a manual override.",
        ),
        ForecastAssumption(
            code=code.NO_HISTORICAL_WIN_RATES,
            detail="Probabilities are not calibrated against past outcomes; historical "
            "win rates are not used.",
        ),
        ForecastAssumption(
            code=code.EXPECTED_CLOSE_DATE_PERIODS,
            detail="Open deals are placed in the period of their expected close date; won "
            "revenue is placed in the period it was closed.",
        ),
        ForecastAssumption(
            code=code.UTC_PERIODS,
            detail=f"Periods are calendar {granularity.value}s in UTC; the organization has "
            "no timezone or fiscal-year setting.",
        ),
        ForecastAssumption(
            code=code.SINGLE_CURRENCY,
            detail=f"All amounts are in {currency}; no currency conversion is applied.",
        ),
        ForecastAssumption(
            code=code.WON_AMOUNT_CURRENT_VALUE,
            detail="Won revenue uses each deal's current amount, including any recorded "
            "manager correction.",
        ),
        ForecastAssumption(
            code=code.ORGANIZATION_TARGETS_ONLY,
            detail="Targets are the organization-wide monthly sales targets; a quarter's "
            "target is the sum of its three months. Owner targets are not added in.",
        ),
    ]
    if override_count:
        items.append(
            ForecastAssumption(
                code=code.PROBABILITY_OVERRIDES,
                detail=f"{override_count} open deal(s) use a manual probability override.",
            )
        )
    if past_due_count:
        items.append(
            ForecastAssumption(
                code=code.PAST_DUE_SEPARATED,
                detail=f"{past_due_count} open deal(s) have a past expected close date; they "
                "are reported as past due and not forecast into any period.",
            )
        )
    if excluded:
        items.append(
            ForecastAssumption(
                code=code.OTHER_CURRENCY_EXCLUDED,
                detail=f"{excluded} deal(s) in another currency are excluded, not converted.",
            )
        )
    if months_without_target:
        items.append(
            ForecastAssumption(
                code=code.TARGETS_INCOMPLETE,
                detail=f"{months_without_target} of {horizon_months} month(s) in this horizon "
                "have no organization target; attainment is shown only where every month "
                "has one.",
            )
        )
    return items
