"""Historical forecast accuracy: each month's forecast as stored in a daily snapshot,
compared with the revenue actually won in that month.

Forecast figures come only from forecast_snapshot_periods and are never recomputed.
Actual revenue comes from PipelineService.won_revenue_by_month(), the same query the
forecast uses for won revenue. All money is integer cents; percentages are integer
tenths, rounded half away from zero (Decimal ROUND_HALF_UP).

Snapshot selection, for target month M and lead L days:
  cutoff_at       = 00:00 UTC on M's first day - L days
  window_start_at = cutoff_at - 7 days
  eligible        = window_start_at <= captured_at < cutoff_at   (L == 0)
                    window_start_at <= captured_at <= cutoff_at  (L > 0)
and the snapshot must hold a period for M. The latest eligible captured_at wins (ties by
id). Lead 0 never uses a snapshot captured on M's first day, which could already contain
M's wins; with daily captures shortly after midnight it selects the snapshot captured
early on the previous month's last day.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import UnprocessableError
from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.schemas.forecast_accuracy import (
    ForecastAccuracy,
    ForecastAccuracyAssumption,
    ForecastAccuracyAssumptionCode,
    ForecastAccuracyBasis,
    ForecastAccuracyComparison,
    ForecastAccuracyLead,
    ForecastAccuracyMonth,
    ForecastAccuracyMonthStatus,
    ForecastAccuracyStatus,
    ForecastAccuracySummary,
    ForecastAccuracySummaryStatus,
    ForecastCutoffRule,
    ForecastSnapshotStatus,
)
from app.schemas.pipeline import ForecastGranularity, PipelineTotals
from app.services.pipeline_service import FORECAST_MAX_PERIODS, PipelineService

ACCURACY_LEAD_DAYS = (0, 30, 60, 90)
DEFAULT_LEAD_DAYS = (0,)
SNAPSHOT_TOLERANCE = timedelta(days=7)
ACCURACY_DEFAULT_MONTHS = 6
ACCURACY_MAX_MONTHS = FORECAST_MAX_PERIODS[ForecastGranularity.MONTH]
# Earliest month the API accepts. Checked before any month shift or cutoff subtraction,
# so the longest lead and the tolerance (97 days back) can never underflow a date.
EARLIEST_MONTH = date(1971, 1, 1)
_EARLIEST_DETAIL = f"Months before {EARLIEST_MONTH.isoformat()} are not supported"

_GRANULARITY = ForecastGranularity.MONTH
_BASES = tuple(ForecastAccuracyBasis)


def _shift_months(month: date, delta: int) -> date:
    index = month.year * 12 + (month.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


def _utc_midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes (stored as UTC); PostgreSQL returns them in the
    # connection's time zone.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _money(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def round_tenths(numerator: int, denominator: int) -> int:
    """numerator / denominator rounded to an integer, half away from zero."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    magnitude = (2 * abs(numerator) + denominator) // (2 * denominator)
    return magnitude if numerator >= 0 else -magnitude


def format_tenths(tenths: int) -> str:
    """Integer tenths as a one-decimal string: -63 -> "-6.3"; 0 -> "0.0"."""
    sign = "-" if tenths < 0 else ""
    magnitude = abs(tenths)
    return f"{sign}{magnitude // 10}.{magnitude % 10}"


def variance_percent(actual_cents: int, forecast_cents: int) -> str | None:
    """(actual - forecast) / forecast * 100; None when the forecast is zero."""
    if forecast_cents == 0:
        return None
    return format_tenths(round_tenths(1000 * (actual_cents - forecast_cents), forecast_cents))


def accuracy_percent(actual_cents: int, absolute_error_cents: int) -> str | None:
    """(1 - |actual - forecast| / actual) * 100, not floored; None when actual is zero."""
    if actual_cents == 0:
        return None
    return format_tenths(round_tenths(1000 * (actual_cents - absolute_error_cents), actual_cents))


def cutoff_rule(lead_days: int) -> ForecastCutoffRule:
    return ForecastCutoffRule.BEFORE if lead_days == 0 else ForecastCutoffRule.ON_OR_BEFORE


def is_before_cutoff(captured_at: datetime, cutoff_at: datetime, rule: ForecastCutoffRule) -> bool:
    if rule == ForecastCutoffRule.BEFORE:
        return captured_at < cutoff_at
    return captured_at <= cutoff_at


@dataclass(frozen=True)
class _Window:
    month: date
    lead_days: int
    cutoff_at: datetime
    window_start_at: datetime
    rule: ForecastCutoffRule

    @classmethod
    def build(cls, month: date, lead_days: int) -> "_Window":
        cutoff_at = _utc_midnight(month) - timedelta(days=lead_days)
        return cls(
            month=month,
            lead_days=lead_days,
            cutoff_at=cutoff_at,
            window_start_at=cutoff_at - SNAPSHOT_TOLERANCE,
            rule=cutoff_rule(lead_days),
        )

    def contains(self, captured_at: datetime) -> bool:
        return self.window_start_at <= captured_at and is_before_cutoff(
            captured_at, self.cutoff_at, self.rule
        )


@dataclass(frozen=True)
class _Candidate:
    snapshot_id: str
    snapshot_date: date
    captured_at: datetime
    currency: str
    figures: dict[ForecastAccuracyBasis, int]


@dataclass
class _Sums:
    months: int = 0
    forecast: int = 0
    actual: int = 0
    variance: int = 0
    absolute_error: int = 0


class ForecastAccuracyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def accuracy(
        self,
        organization_id: str,
        *,
        from_month: date | None = None,
        to_month: date | None = None,
        lead_days: Sequence[int] | None = None,
        now: datetime | None = None,
    ) -> ForecastAccuracy:
        as_of = (now or datetime.now(UTC)).astimezone(UTC)
        current_month = as_of.date().replace(day=1)
        first, last = _month_range(from_month, to_month, current_month)
        leads = _lead_days(lead_days)
        month_count = (last.year - first.year) * 12 + last.month - first.month + 1
        months = [_shift_months(first, offset) for offset in range(month_count)]

        won = PipelineService(self.session).won_revenue_by_month(
            organization_id, first_month=first, month_count=month_count
        )
        currency = won.currency
        first_captured_at = self._first_captured_at(organization_id)
        windows = {(month, lead): _Window.build(month, lead) for month in months for lead in leads}
        candidates = self._candidates(organization_id, list(windows.values()))

        sums = {(lead, basis): _Sums() for lead in leads for basis in _BASES}
        missing = dict.fromkeys(leads, 0)
        result_months: list[ForecastAccuracyMonth] = []
        for month, actual in zip(months, won.months, strict=True):
            in_progress = month == current_month
            forecasts: list[ForecastAccuracyLead] = []
            for lead in leads:
                window = windows[(month, lead)]
                selected = _select(candidates.get(month, []), window)
                status = _snapshot_status(selected, window, first_captured_at, currency)
                comparisons: list[ForecastAccuracyComparison] = []
                if status == ForecastSnapshotStatus.AVAILABLE and selected is not None:
                    for basis in _BASES:
                        forecast = selected.figures[basis]
                        comparisons.append(_compare(basis, actual.cents, forecast, in_progress))
                        if not in_progress:
                            _add(sums[(lead, basis)], actual.cents, forecast)
                elif not in_progress:
                    missing[lead] += 1
                forecasts.append(
                    ForecastAccuracyLead(
                        lead_days=lead,
                        cutoff_at=window.cutoff_at,
                        cutoff_rule=window.rule,
                        window_start_at=window.window_start_at,
                        snapshot_status=status,
                        snapshot_date=selected.snapshot_date if selected else None,
                        captured_at=selected.captured_at if selected else None,
                        comparisons=comparisons,
                    )
                )
            result_months.append(
                ForecastAccuracyMonth(
                    label=f"{month.year}-{month.month:02d}",
                    period_start=month,
                    period_end=_shift_months(month, 1) - timedelta(days=1),
                    status=(
                        ForecastAccuracyMonthStatus.IN_PROGRESS
                        if in_progress
                        else ForecastAccuracyMonthStatus.CLOSED
                    ),
                    actual=PipelineTotals(count=actual.count, total_amount=_money(actual.cents)),
                    forecasts=forecasts,
                )
            )

        return ForecastAccuracy(
            currency=currency,
            as_of=as_of,
            granularity=_GRANULARITY,
            from_month=first,
            to_month=last,
            lead_days=list(leads),
            snapshot_tolerance_days=SNAPSHOT_TOLERANCE.days,
            first_captured_at=first_captured_at,
            months=result_months,
            summary=[
                _summary(lead, basis, sums[(lead, basis)], missing[lead])
                for lead in leads
                for basis in _BASES
            ],
            assumptions=_assumptions(currency, include_in_progress=last == current_month),
        )

    def _first_captured_at(self, organization_id: str) -> datetime | None:
        first = self.session.scalar(
            select(func.min(ForecastSnapshot.captured_at)).where(
                ForecastSnapshot.organization_id == organization_id,
                ForecastSnapshot.granularity == _GRANULARITY.value,
            )
        )
        return None if first is None else _as_utc(first)

    def _candidates(
        self, organization_id: str, windows: Sequence[_Window]
    ) -> dict[date, list[_Candidate]]:
        """Periods of the organization's monthly snapshots whose snapshot_date can fall in
        one of the windows, in one query. Exact captured_at bounds are applied in Python
        after normalizing to UTC, so SQLite and PostgreSQL select identically."""
        ranges = {
            (window.month, window.window_start_at.date(), window.cutoff_at.date())
            for window in windows
        }
        terms = [
            and_(
                ForecastSnapshotPeriod.period_start == month,
                ForecastSnapshot.snapshot_date >= low,
                ForecastSnapshot.snapshot_date <= high,
            )
            for month, low, high in sorted(ranges)
        ]
        rows = self.session.execute(
            select(
                ForecastSnapshotPeriod.period_start,
                ForecastSnapshot.id,
                ForecastSnapshot.snapshot_date,
                ForecastSnapshot.captured_at,
                ForecastSnapshot.currency,
                ForecastSnapshotPeriod.projected_cents,
                ForecastSnapshotPeriod.commit_scenario_cents,
                ForecastSnapshotPeriod.best_case_scenario_cents,
            )
            .join(
                ForecastSnapshot,
                and_(
                    ForecastSnapshot.organization_id == ForecastSnapshotPeriod.organization_id,
                    ForecastSnapshot.id == ForecastSnapshotPeriod.snapshot_id,
                ),
            )
            .where(
                ForecastSnapshot.organization_id == organization_id,
                ForecastSnapshotPeriod.organization_id == organization_id,
                ForecastSnapshot.granularity == _GRANULARITY.value,
                or_(*terms),
            )
        ).all()
        by_month: dict[date, list[_Candidate]] = defaultdict(list)
        for period_start, snapshot_id, snapshot_date, captured_at, currency, *figures in rows:
            projected, commit, best_case = (int(value) for value in figures)
            by_month[period_start].append(
                _Candidate(
                    snapshot_id=snapshot_id,
                    snapshot_date=snapshot_date,
                    captured_at=_as_utc(captured_at),
                    currency=currency,
                    figures={
                        ForecastAccuracyBasis.PROJECTED: projected,
                        ForecastAccuracyBasis.COMMIT_SCENARIO: commit,
                        ForecastAccuracyBasis.BEST_CASE_SCENARIO: best_case,
                    },
                )
            )
        return by_month


def _month_range(
    from_month: date | None, to_month: date | None, current_month: date
) -> tuple[date, date]:
    for name, value in (("from_month", from_month), ("to_month", to_month)):
        if value is not None and value.day != 1:
            raise UnprocessableError(f"{name} must be the first day of a month")
        if value is not None and value < EARLIEST_MONTH:
            raise UnprocessableError(_EARLIEST_DETAIL)
    last = _shift_months(current_month, -1) if to_month is None else to_month
    first = from_month or _shift_months(last, -(ACCURACY_DEFAULT_MONTHS - 1))
    if first < EARLIEST_MONTH:
        # Only a defaulted from_month can land here (to_month in the first months of 1971).
        raise UnprocessableError(_EARLIEST_DETAIL)
    if last > current_month:
        raise UnprocessableError("to_month cannot be after the current month")
    if first > last:
        raise UnprocessableError("from_month must not be after to_month")
    months = (last.year - first.year) * 12 + last.month - first.month + 1
    if months > ACCURACY_MAX_MONTHS:
        raise UnprocessableError(f"The range can cover at most {ACCURACY_MAX_MONTHS} months")
    return first, last


def _lead_days(values: Sequence[int] | None) -> tuple[int, ...]:
    if not values:
        return DEFAULT_LEAD_DAYS
    allowed = ", ".join(str(value) for value in ACCURACY_LEAD_DAYS)
    if any(value not in ACCURACY_LEAD_DAYS for value in values):
        raise UnprocessableError(f"lead_days must be one of {allowed}")
    if len(set(values)) != len(values):
        raise UnprocessableError("lead_days must not repeat a value")
    return tuple(sorted(values))


def _select(candidates: Sequence[_Candidate], window: _Window) -> _Candidate | None:
    eligible = [c for c in candidates if window.contains(c.captured_at)]
    if not eligible:
        return None
    return max(eligible, key=lambda c: (c.captured_at, c.snapshot_id))


def _snapshot_status(
    selected: _Candidate | None,
    window: _Window,
    first_captured_at: datetime | None,
    currency: str,
) -> ForecastSnapshotStatus:
    if selected is not None:
        if selected.currency != currency:
            return ForecastSnapshotStatus.CURRENCY_MISMATCH
        return ForecastSnapshotStatus.AVAILABLE
    if first_captured_at is None or not is_before_cutoff(
        first_captured_at, window.cutoff_at, window.rule
    ):
        return ForecastSnapshotStatus.BEFORE_FIRST_SNAPSHOT
    return ForecastSnapshotStatus.MISSING


def _compare(
    basis: ForecastAccuracyBasis, actual_cents: int, forecast_cents: int, in_progress: bool
) -> ForecastAccuracyComparison:
    if in_progress:
        return ForecastAccuracyComparison(
            basis=basis,
            forecast_amount=_money(forecast_cents),
            variance_amount=None,
            variance_percent=None,
            accuracy_percent=None,
            accuracy_status=ForecastAccuracyStatus.MONTH_IN_PROGRESS,
        )
    return ForecastAccuracyComparison(
        basis=basis,
        forecast_amount=_money(forecast_cents),
        variance_amount=_money(actual_cents - forecast_cents),
        variance_percent=variance_percent(actual_cents, forecast_cents),
        accuracy_percent=accuracy_percent(actual_cents, abs(actual_cents - forecast_cents)),
        accuracy_status=(
            ForecastAccuracyStatus.NO_ACTUAL_REVENUE
            if actual_cents == 0
            else ForecastAccuracyStatus.COMPUTED
        ),
    )


def _add(sums: _Sums, actual_cents: int, forecast_cents: int) -> None:
    sums.months += 1
    sums.forecast += forecast_cents
    sums.actual += actual_cents
    sums.variance += actual_cents - forecast_cents
    sums.absolute_error += abs(actual_cents - forecast_cents)


def _summary(
    lead: int, basis: ForecastAccuracyBasis, sums: _Sums, months_missing: int
) -> ForecastAccuracySummary:
    if sums.months == 0:
        return ForecastAccuracySummary(
            lead_days=lead,
            basis=basis,
            months_compared=0,
            months_missing=months_missing,
            forecast_total=None,
            actual_total=None,
            variance_amount=None,
            variance_percent=None,
            weighted_accuracy_percent=None,
            status=ForecastAccuracySummaryStatus.NO_COMPARABLE_MONTHS,
        )
    return ForecastAccuracySummary(
        lead_days=lead,
        basis=basis,
        months_compared=sums.months,
        months_missing=months_missing,
        forecast_total=_money(sums.forecast),
        actual_total=_money(sums.actual),
        variance_amount=_money(sums.variance),
        variance_percent=variance_percent(sums.actual, sums.forecast),
        weighted_accuracy_percent=accuracy_percent(sums.actual, sums.absolute_error),
        status=(
            ForecastAccuracySummaryStatus.NO_ACTUAL_REVENUE
            if sums.actual == 0
            else ForecastAccuracySummaryStatus.COMPUTED
        ),
    )


def _assumptions(currency: str, *, include_in_progress: bool) -> list[ForecastAccuracyAssumption]:
    code = ForecastAccuracyAssumptionCode
    tolerance = SNAPSHOT_TOLERANCE.days
    items = [
        ForecastAccuracyAssumption(
            code=code.SNAPSHOT_FIGURES,
            detail="Forecast figures are read from the daily snapshot as it was stored; "
            "later deal changes never alter them.",
        ),
        ForecastAccuracyAssumption(
            code=code.LEAD_CUTOFFS,
            detail="Each lead's cutoff is 00:00 UTC on the month's first day minus the lead "
            "in days. Lead 0 uses only snapshots captured before the month started, usually "
            "the one captured early on the previous month's last day; other leads use "
            "snapshots captured at or before the cutoff.",
        ),
        ForecastAccuracyAssumption(
            code=code.SNAPSHOT_TOLERANCE,
            detail=f"The latest snapshot captured within {tolerance} days before the cutoff "
            "is used; if there is none the lead is reported as missing, never as zero.",
        ),
        ForecastAccuracyAssumption(
            code=code.ACTUAL_WON_CURRENT_VALUE,
            detail="Actual revenue is deals won in the month by close date, at each deal's "
            "current amount including any recorded manager correction.",
        ),
        ForecastAccuracyAssumption(
            code=code.UTC_MONTHS,
            detail="Months are calendar months in UTC.",
        ),
        ForecastAccuracyAssumption(
            code=code.SINGLE_CURRENCY,
            detail=f"All amounts are in {currency}; no currency conversion is applied.",
        ),
    ]
    if include_in_progress:
        items.append(
            ForecastAccuracyAssumption(
                code=code.IN_PROGRESS_NOT_SCORED,
                detail="The current month is shown with revenue won so far; it has no "
                "variance or accuracy and is not in the summary.",
            )
        )
    return items
