"""Historical forecast accuracy: stored monthly forecast snapshots compared with the
revenue later won in each month."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from app.schemas.money import MoneyOut
from app.schemas.pipeline import ForecastGranularity, PipelineRounding, PipelineTotals


class ForecastAccuracyBasis(StrEnum):
    PROJECTED = "PROJECTED"
    COMMIT_SCENARIO = "COMMIT_SCENARIO"
    BEST_CASE_SCENARIO = "BEST_CASE_SCENARIO"


class ForecastAccuracyMonthStatus(StrEnum):
    # The month ended before as_of: actual revenue is final and the month is scored.
    CLOSED = "CLOSED"
    # The month containing as_of: actual revenue so far, not scored.
    IN_PROGRESS = "IN_PROGRESS"


class ForecastCutoffRule(StrEnum):
    # captured_at < cutoff_at (lead 0: nothing captured on or after the month's start).
    BEFORE = "BEFORE"
    # captured_at <= cutoff_at (leads 30, 60 and 90).
    ON_OR_BEFORE = "ON_OR_BEFORE"


class ForecastSnapshotStatus(StrEnum):
    # A snapshot was captured inside [window_start_at, cutoff_at] under the cutoff rule.
    AVAILABLE = "AVAILABLE"
    # The organization has snapshots before the cutoff, but none inside the window.
    MISSING = "MISSING"
    # The organization's first snapshot is not before the cutoff: tracking had not started.
    BEFORE_FIRST_SNAPSHOT = "BEFORE_FIRST_SNAPSHOT"
    # The selected snapshot is in another currency than the organization's; not compared.
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"


class ForecastAccuracyStatus(StrEnum):
    COMPUTED = "COMPUTED"
    # Actual revenue is zero: accuracy is undefined; variance is still reported.
    NO_ACTUAL_REVENUE = "NO_ACTUAL_REVENUE"
    # The month has not ended: variance and accuracy are not reported.
    MONTH_IN_PROGRESS = "MONTH_IN_PROGRESS"


class ForecastAccuracySummaryStatus(StrEnum):
    COMPUTED = "COMPUTED"
    NO_ACTUAL_REVENUE = "NO_ACTUAL_REVENUE"
    # No closed month in the range has an AVAILABLE snapshot for this lead.
    NO_COMPARABLE_MONTHS = "NO_COMPARABLE_MONTHS"


class ForecastAccuracyAssumptionCode(StrEnum):
    SNAPSHOT_FIGURES = "SNAPSHOT_FIGURES"
    LEAD_CUTOFFS = "LEAD_CUTOFFS"
    SNAPSHOT_TOLERANCE = "SNAPSHOT_TOLERANCE"
    ACTUAL_WON_CURRENT_VALUE = "ACTUAL_WON_CURRENT_VALUE"
    UTC_MONTHS = "UTC_MONTHS"
    SINGLE_CURRENCY = "SINGLE_CURRENCY"
    IN_PROGRESS_NOT_SCORED = "IN_PROGRESS_NOT_SCORED"


class ForecastAccuracyAssumption(BaseModel):
    code: ForecastAccuracyAssumptionCode
    detail: str


class ForecastAccuracyComparison(BaseModel):
    """One stored forecast figure against the month's actual won revenue.
    Percentages are strings to one decimal, rounded half away from zero; accuracy is not
    floored and can be negative."""

    basis: ForecastAccuracyBasis
    forecast_amount: MoneyOut
    # actual - forecast; None while the month is in progress.
    variance_amount: MoneyOut | None
    # (actual - forecast) / forecast * 100; None when forecast is zero or in progress.
    variance_percent: str | None
    # (1 - |actual - forecast| / actual) * 100; None when actual is zero or in progress.
    accuracy_percent: str | None
    accuracy_status: ForecastAccuracyStatus


class ForecastAccuracyLead(BaseModel):
    """The snapshot selected for one lead time: the latest captured inside
    [window_start_at, cutoff_at] under cutoff_rule."""

    lead_days: int
    # Month start (00:00 UTC) minus lead_days.
    cutoff_at: datetime
    cutoff_rule: ForecastCutoffRule
    # cutoff_at minus the tolerance; inclusive.
    window_start_at: datetime
    snapshot_status: ForecastSnapshotStatus
    # The selected snapshot; None unless AVAILABLE or CURRENCY_MISMATCH.
    snapshot_date: date | None
    captured_at: datetime | None
    # PROJECTED, COMMIT_SCENARIO, BEST_CASE_SCENARIO; empty unless AVAILABLE.
    comparisons: list[ForecastAccuracyComparison]


class ForecastAccuracyMonth(BaseModel):
    label: str
    period_start: date
    period_end: date
    status: ForecastAccuracyMonthStatus
    # Deals won in the month by closed_at (so far, when in progress).
    actual: PipelineTotals
    # One entry per requested lead, in ascending lead order.
    forecasts: list[ForecastAccuracyLead]


class ForecastAccuracySummary(BaseModel):
    """Closed months with an AVAILABLE snapshot for this lead, combined by sums (never an
    average of monthly percentages). Totals are None when no month is comparable."""

    lead_days: int
    basis: ForecastAccuracyBasis
    months_compared: int
    # Closed months in the range without an AVAILABLE snapshot for this lead.
    months_missing: int
    forecast_total: MoneyOut | None
    actual_total: MoneyOut | None
    # sum(actual - forecast)
    variance_amount: MoneyOut | None
    # sum(actual - forecast) / sum(forecast) * 100; None when sum(forecast) is zero.
    variance_percent: str | None
    # (1 - sum|actual - forecast| / sum(actual)) * 100; None when sum(actual) is zero.
    weighted_accuracy_percent: str | None
    status: ForecastAccuracySummaryStatus


class ForecastAccuracy(BaseModel):
    """Monthly forecasts as stored in daily snapshots, compared with actual won revenue.
    Forecast figures are read from snapshots only; nothing is recomputed."""

    currency: str
    as_of: datetime
    granularity: ForecastGranularity
    method: Literal["SNAPSHOT_VS_ACTUAL_WON"] = "SNAPSHOT_VS_ACTUAL_WON"
    rounding: PipelineRounding = "PER_DEAL_HALF_UP_CENTS"
    accuracy_formula: Literal["ONE_MINUS_ABS_ERROR_OVER_ACTUAL"] = "ONE_MINUS_ABS_ERROR_OVER_ACTUAL"
    percent_rounding: Literal["HALF_AWAY_FROM_ZERO_TENTHS"] = "HALF_AWAY_FROM_ZERO_TENTHS"
    variance_sign: Literal["ACTUAL_MINUS_FORECAST"] = "ACTUAL_MINUS_FORECAST"
    from_month: date
    to_month: date
    lead_days: list[int]
    snapshot_tolerance_days: int
    # Earliest monthly snapshot of the organization; None when it has none.
    first_captured_at: datetime | None
    months: list[ForecastAccuracyMonth]
    # One entry per (lead, basis), leads ascending, bases in ForecastAccuracyBasis order.
    summary: list[ForecastAccuracySummary]
    assumptions: list[ForecastAccuracyAssumption]
