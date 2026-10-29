from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.deal import DealStage
from app.schemas.money import CurrencyCode, Money, MoneyOut

DealHistoryChange = Literal["CREATED", "STAGE", "AMOUNT", "EXPECTED_CLOSE_DATE"]
ProbabilitySource = Literal["STAGE_DEFAULT", "OVERRIDE"]


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Deal name is required")
    return value


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class DealCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    amount: Money
    currency: CurrencyCode | None = None
    stage: DealStage = DealStage.QUALIFICATION
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    lead_id: str | None = Field(default=None, min_length=1, max_length=36)
    lost_reason: str | None = Field(default=None, max_length=1000)

    _name = field_validator("name")(_strip_required)
    _description = field_validator("description")(_strip_optional)
    _lost_reason = field_validator("lost_reason")(_strip_optional)


class DealUpdate(BaseModel):
    """Partial update. Stage changes go through POST /deals/{id}/stage; currency and
    lead links are fixed at creation. An explicit null clears probability or owner."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    amount: Money | None = None
    expected_close_date: date | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    lost_reason: str | None = Field(default=None, max_length=1000)
    change_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)

    _description = field_validator("description")(_strip_optional)
    _lost_reason = field_validator("lost_reason")(_strip_optional)
    _change_reason = field_validator("change_reason")(_strip_optional)


class DealStageChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: DealStage
    expected_revision: int = Field(ge=1)
    probability: int | None = Field(default=None, ge=0, le=100)
    lost_reason: str | None = Field(default=None, max_length=1000)
    change_reason: str | None = Field(default=None, max_length=1000)

    _lost_reason = field_validator("lost_reason")(_strip_optional)
    _change_reason = field_validator("change_reason")(_strip_optional)


class DealPublic(BaseModel):
    id: str
    name: str
    description: str | None
    amount: MoneyOut
    currency: str
    stage: DealStage
    probability: int | None
    effective_probability: int
    probability_source: ProbabilitySource
    expected_close_date: date
    closed_at: datetime | None
    owner_user_id: str | None
    owner_name: str | None
    lead_id: str | None
    lead_name: str | None
    lost_reason: str | None
    revision: int
    stage_entered_at: datetime
    created_at: datetime
    updated_at: datetime


class DealListResponse(BaseModel):
    items: list[DealPublic]
    limit: int
    offset: int
    total: int


class DealHistoryEvent(BaseModel):
    id: str
    deal_id: str
    changes: list[DealHistoryChange]
    previous_stage: DealStage | None
    new_stage: DealStage
    previous_amount: MoneyOut | None
    new_amount: MoneyOut
    previous_expected_close_date: date | None
    new_expected_close_date: date
    changed_by_user_id: str | None
    changed_by_name: str | None
    change_reason: str | None
    created_at: datetime


class DealHistoryResponse(BaseModel):
    items: list[DealHistoryEvent]
    limit: int
    offset: int
    total: int
