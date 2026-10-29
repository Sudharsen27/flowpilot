from datetime import date, datetime

from pydantic import BaseModel

from app.models.deal import DealStage
from app.schemas.money import MoneyOut


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
    open: PipelineWeightedTotals
    won: PipelineTotals
    lost: PipelineTotals
    overdue_open: PipelineTotals
    by_stage: list[PipelineStageSummary]
    won_by_month: list[PipelineMonth]
    excluded_other_currency_count: int
