from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from app.models.deal import DealStage, ForecastCategory
from app.schemas.deals import ProbabilitySource
from app.schemas.money import MoneyOut

# Each deal's weighted value is rounded half-up to the cent once; every total is a sum
# of those cents, so stage, period and bucket figures always add up to their totals.
PipelineRounding = Literal["PER_DEAL_HALF_UP_CENTS"]


class PipelineTotals(BaseModel):
    count: int
    total_amount: MoneyOut


class PipelineWeightedTotals(PipelineTotals):
    """Open deals: total value and value weighted by each deal's effective probability."""

    weighted_amount: MoneyOut


class PipelineStageSummary(BaseModel):
    stage: DealStage
    count: int
    total_amount: MoneyOut
    weighted_amount: MoneyOut
    default_probability: int


class PipelineMonth(BaseModel):
    month: date
    count: int
    total_amount: MoneyOut


class PipelineSummary(BaseModel):
    """Deterministic pipeline figures computed from stored deals. Not a forecast."""

    currency: str
    generated_at: datetime
    rounding: PipelineRounding = "PER_DEAL_HALF_UP_CENTS"
    open: PipelineWeightedTotals
    won: PipelineTotals
    lost: PipelineTotals
    overdue_open: PipelineTotals
    by_stage: list[PipelineStageSummary]
    won_by_month: list[PipelineMonth]
    excluded_other_currency_count: int


class ForecastGranularity(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"


class ForecastAssumptionCode(StrEnum):
    STAGE_PROBABILITY_WEIGHTING = "STAGE_PROBABILITY_WEIGHTING"
    PROBABILITY_OVERRIDES = "PROBABILITY_OVERRIDES"
    NO_HISTORICAL_WIN_RATES = "NO_HISTORICAL_WIN_RATES"
    EXPECTED_CLOSE_DATE_PERIODS = "EXPECTED_CLOSE_DATE_PERIODS"
    PAST_DUE_SEPARATED = "PAST_DUE_SEPARATED"
    UTC_PERIODS = "UTC_PERIODS"
    SINGLE_CURRENCY = "SINGLE_CURRENCY"
    OTHER_CURRENCY_EXCLUDED = "OTHER_CURRENCY_EXCLUDED"
    WON_AMOUNT_CURRENT_VALUE = "WON_AMOUNT_CURRENT_VALUE"
    ORGANIZATION_TARGETS_ONLY = "ORGANIZATION_TARGETS_ONLY"
    TARGETS_INCOMPLETE = "TARGETS_INCOMPLETE"


class ForecastAssumption(BaseModel):
    code: ForecastAssumptionCode
    detail: str


class ForecastCategoryTotals(PipelineWeightedTotals):
    """Open deals of one forecast category within a bucket."""

    category: ForecastCategory


class ForecastOpenTotals(PipelineWeightedTotals):
    """Open deals in a bucket: unweighted pipeline value and probability-weighted value.
    override_count is how many of them use a manual probability override.
    category_totals has one entry per forecast category, in a fixed order and including
    empty ones; its counts and amounts add up exactly to the bucket's."""

    override_count: int
    category_totals: list[ForecastCategoryTotals]


class ForecastPastDue(ForecastOpenTotals):
    oldest_expected_close_date: date | None


class ForecastTargetStatus(StrEnum):
    # Every month in the range has an organization target.
    FULL = "FULL"
    # Some months have one, some do not.
    PARTIAL = "PARTIAL"
    # No month in the range has one.
    NONE = "NONE"


class ForecastTargetBasis(StrEnum):
    WON = "WON"
    COMMIT_SCENARIO = "COMMIT_SCENARIO"
    BEST_CASE_SCENARIO = "BEST_CASE_SCENARIO"
    PROJECTED = "PROJECTED"


class ForecastTargetComparison(BaseModel):
    """One forecast figure against a FULL target. Exactly one of remaining_amount and
    above_target_amount is non-zero, or both are zero when the figure equals the target."""

    basis: ForecastTargetBasis
    amount: MoneyOut
    # amount / target as a percentage, half-up to one decimal ("84.3"); not capped at
    # 100. None when the target is zero.
    attainment_percent: str | None
    # max(target - amount, 0)
    remaining_amount: MoneyOut
    # max(amount - target, 0)
    above_target_amount: MoneyOut


class ForecastTarget(BaseModel):
    """Organization-wide monthly sales targets summed over a period or the horizon.
    Owner targets are never added in. comparisons is filled only when status is FULL:
    comparing a whole range against a partial target would overstate attainment."""

    status: ForecastTargetStatus
    # Sum of the monthly organization targets that are set; None when status is NONE.
    amount: MoneyOut | None
    months_in_range: int
    months_with_target: int
    # First day of each month in the range without an organization target.
    missing_months: list[date]
    # Whether any owner-level target exists for a month in the range.
    has_owner_targets: bool
    # WON, COMMIT_SCENARIO, BEST_CASE_SCENARIO, PROJECTED, in that order; empty unless FULL.
    comparisons: list[ForecastTargetComparison]


class ForecastPeriod(BaseModel):
    label: str
    period_start: date
    period_end: date
    # Actual revenue: deals won (closed_at) inside the period.
    won: PipelineTotals
    # Pipeline value: open deals expected to close in the period (from as_of onwards).
    open: ForecastOpenTotals
    # won.total_amount + open.weighted_amount. An estimate, not committed revenue.
    projected_amount: MoneyOut
    # Per-period scenarios, same rules as the horizon ones: won.total_amount + COMMIT
    # total_amount, then + BEST_CASE total_amount. Across periods they add up to
    # commit_scenario_amount and best_case_scenario_amount.
    commit_scenario_amount: MoneyOut
    best_case_scenario_amount: MoneyOut
    target: ForecastTarget


class ForecastStageProbability(BaseModel):
    stage: DealStage
    default_probability: int


class PipelineForecast(BaseModel):
    """Stage-probability-weighted forecast from stored deals. Every figure is calculated;
    nothing is estimated from history or generated by AI."""

    currency: str
    as_of: datetime
    granularity: ForecastGranularity
    method: Literal["STAGE_PROBABILITY_WEIGHTED"] = "STAGE_PROBABILITY_WEIGHTED"
    rounding: PipelineRounding = "PER_DEAL_HALF_UP_CENTS"
    horizon_start: date
    horizon_end: date
    periods: list[ForecastPeriod]
    # Open deals whose expected close date is before as_of: not forecast into any period.
    past_due: ForecastPastDue
    # Open deals expected to close after horizon_end.
    beyond_horizon: ForecastOpenTotals
    # All open deals = past_due + every period's open + beyond_horizon.
    open_pipeline: ForecastOpenTotals
    won_in_horizon: PipelineTotals
    projected_in_horizon_amount: MoneyOut
    # Open deals expected to close inside the horizon = every period's open combined.
    in_horizon_open: ForecastOpenTotals
    # Scenarios use full, unweighted amounts of in-horizon open deals; they are
    # cumulative (best case includes commit) and estimates, not committed revenue.
    # won_in_horizon.total_amount + COMMIT total_amount.
    commit_scenario_amount: MoneyOut
    # commit_scenario_amount + BEST_CASE total_amount. PIPELINE deals are in neither.
    best_case_scenario_amount: MoneyOut
    # Organization targets for every month from horizon_start to horizon_end, compared
    # with won_in_horizon, the two scenarios and projected_in_horizon_amount.
    target_in_horizon: ForecastTarget
    stage_probabilities: list[ForecastStageProbability]
    assumptions: list[ForecastAssumption]
    excluded_other_currency_count: int


class ForecastCategoryDeal(BaseModel):
    """One open deal counted in a forecast category; weighted_amount is the same per-deal
    half-up cents the forecast sums."""

    id: str
    name: str
    amount: MoneyOut
    currency: str
    stage: DealStage
    probability: int | None
    effective_probability: int
    probability_source: ProbabilitySource
    forecast_category: ForecastCategory
    weighted_amount: MoneyOut
    expected_close_date: date
    # Start of the forecast period the deal is counted in.
    period_start: date
    owner_user_id: str | None
    owner_name: str | None


class ForecastCategoryDeals(BaseModel):
    """The open deals behind one forecast category, for one period or the whole horizon.
    Selected exactly as the forecast buckets them (open, organization currency, expected
    to close from as_of up to range_end), so totals equal the matching category_totals
    entry: a period's open.category_totals, or in_horizon_open's when no period is given."""

    currency: str
    as_of: datetime
    granularity: ForecastGranularity
    rounding: PipelineRounding = "PER_DEAL_HALF_UP_CENTS"
    category: ForecastCategory
    horizon_start: date
    horizon_end: date
    # The selected period, or the whole horizon.
    range_start: date
    range_end: date
    # Every matching deal, not only this page.
    totals: PipelineWeightedTotals
    items: list[ForecastCategoryDeal]
    limit: int
    offset: int
    total: int
