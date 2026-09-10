from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.lead_follow_up import LeadFollowUpStatus, LeadFollowUpType

_MAX_HORIZON = timedelta(days=3650)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("due_at must include a timezone offset")
    return value.astimezone(UTC)


def _within_horizon(value: datetime) -> datetime:
    now = datetime.now(UTC)
    if value < now - _MAX_HORIZON or value > now + _MAX_HORIZON:
        raise ValueError("due_at is outside the allowed range")
    return value


class LeadFollowUpCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_at: datetime
    type: LeadFollowUpType = LeadFollowUpType.EMAIL_FOLLOW_UP
    notes: str | None = Field(default=None, max_length=4000)
    email_send_id: str | None = Field(default=None, max_length=36)

    @field_validator("due_at")
    @classmethod
    def aware_due_at(cls, value: datetime) -> datetime:
        return _within_horizon(_require_aware(value))

    @field_validator("notes", "email_send_id", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class LeadFollowUpUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    due_at: datetime | None = None
    type: LeadFollowUpType | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("due_at")
    @classmethod
    def aware_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _within_horizon(_require_aware(value))

    @field_validator("notes", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.due_at is None and self.type is None and "notes" not in self.model_fields_set:
            raise ValueError("At least one of due_at, type, or notes is required")
        return self


class LeadFollowUpLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class LeadFollowUpPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lead_id: str
    email_send_id: str | None = None
    type: LeadFollowUpType
    status: LeadFollowUpStatus
    due_at: datetime
    notes: str | None = None
    revision: int
    is_overdue: bool
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LeadFollowUpListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LeadFollowUpPublic]
    limit: int
    offset: int
    total: int
