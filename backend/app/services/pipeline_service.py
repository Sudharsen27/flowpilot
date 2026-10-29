"""Read-only pipeline figures and forecasts, aggregated in SQL from persisted deals.

Money is aggregated as integer cents: each deal's amount is converted to cents and its
weighted value is rounded half-up to the cent once (PER_DEAL_HALF_UP_CENTS). Totals are
sums of those integers, so every breakdown reconciles exactly with its total and nothing
passes through float. Integer arithmetic also keeps SQLite and PostgreSQL identical.
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
    OPEN_DEAL_STAGES,
    Deal,
    DealStage,
)
from app.models.organization import Organization
from app.schemas.pipeline import (
    ForecastAssumption,
    ForecastAssumptionCode,
    ForecastGranularity,
    ForecastOpenTotals,
    ForecastPastDue,
    ForecastPeriod,
    ForecastStageProbability,
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


def _amount_cents() -> ColumnElement[Any]:
    # round() makes SQLite's REAL storage exact again; PostgreSQL numeric is already exact.
    return cast(func.round(Deal.amount * 100), BigInteger)


def _weighted_cents() -> ColumnElement[Any]:
    # Integer floor of (cents * p + 50) / 100: half-up rounding for non-negative amounts.
    return (_amount_cents() * _effective_probability() + 50) // 100


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

    def open(self) -> ForecastOpenTotals:
        return ForecastOpenTotals(
            count=self.count,
            total_amount=_money(self.cents),
            weighted_amount=_money(self.weighted_cents),
            override_count=self.override_count,
        )


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
        count = FORECAST_DEFAULT_PERIODS[granularity] if periods is None else periods
        maximum = FORECAST_MAX_PERIODS[granularity]
        if not 1 <= count <= maximum:
            raise UnprocessableError(f"periods must be between 1 and {maximum} for {granularity}")
        currency = self._currency(organization_id)
        as_of = (now or datetime.now(UTC)).astimezone(UTC)
        today = as_of.date()

        step = _MONTHS_PER_PERIOD[granularity]
        first = _period_start(today, granularity)
        starts = [_shift_months(first, step * offset) for offset in range(count)]
        horizon_end = _shift_months(first, step * count)  # exclusive

        bucket = case(
            (Deal.expected_close_date < today, _PAST_DUE_BUCKET),
            else_=_bucket(Deal.expected_close_date, [*starts, horizon_end]),
        )
        open_deals = (
            select(
                bucket.label("bucket"),
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
                func.count(),
                func.sum(open_deals.c.cents),
                func.sum(open_deals.c.weighted_cents),
                func.sum(open_deals.c.override),
                func.min(open_deals.c.expected_close_date),
            ).group_by(open_deals.c.bucket)
        ).all()

        open_buckets = {index: _Totals() for index in range(_PAST_DUE_BUCKET, count + 1)}
        oldest_past_due: date | None = None
        for index, deal_count, cents, weighted, overrides, earliest in open_rows:
            open_buckets[int(index)] = _Totals(
                count=deal_count,
                cents=int(cents),
                weighted_cents=int(weighted),
                override_count=int(overrides),
            )
            if index == _PAST_DUE_BUCKET:
                oldest_past_due = earliest
        open_total = _Totals()
        for totals in open_buckets.values():
            open_total.add(totals)

        won = self._won_by_period(organization_id, currency, starts, horizon_end)
        won_total = _Totals()
        result_periods: list[ForecastPeriod] = []
        for index, start in enumerate(starts):
            won_total.add(won[index])
            end = starts[index + 1] if index + 1 < count else horizon_end
            result_periods.append(
                ForecastPeriod(
                    label=_period_label(start, granularity),
                    period_start=start,
                    period_end=end - timedelta(days=1),
                    won=won[index].plain(),
                    open=open_buckets[index].open(),
                    projected_amount=_money(won[index].cents + open_buckets[index].weighted_cents),
                )
            )
        horizon_weighted = sum(open_buckets[index].weighted_cents for index in range(count))
        excluded = self._other_currency_count(organization_id, currency)
        past_due = open_buckets[_PAST_DUE_BUCKET]

        return PipelineForecast(
            currency=currency,
            as_of=as_of,
            granularity=granularity,
            horizon_start=first,
            horizon_end=horizon_end - timedelta(days=1),
            periods=result_periods,
            past_due=ForecastPastDue(
                **past_due.open().model_dump(), oldest_expected_close_date=oldest_past_due
            ),
            beyond_horizon=open_buckets[count].open(),
            open_pipeline=open_total.open(),
            won_in_horizon=won_total.plain(),
            projected_in_horizon_amount=_money(won_total.cents + horizon_weighted),
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
            ),
            excluded_other_currency_count=excluded,
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
    return items
