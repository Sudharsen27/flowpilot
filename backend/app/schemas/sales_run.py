from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead import LeadStatus
from app.models.lead_follow_up import LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_response_draft import LeadResponseReviewStatus
from app.models.sales_run import SalesRunStage, SalesRunStatus

_MAX_HORIZON = timedelta(days=3650)


class SalesRunStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enquiry: str = Field(min_length=1, max_length=8000)
    lead_id: str | None = Field(default=None, min_length=1, max_length=36)
    name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped

    @field_validator("lead_id", "name", mode="before")
    @classmethod
    def empty_optional_str(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class LeadSalesRunStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enquiry: str = Field(min_length=1, max_length=8000)
    agent_id: str = Field(min_length=1, max_length=36)

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped

    @field_validator("agent_id")
    @classmethod
    def strip_agent_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Agent is required")
        return stripped


class SalesRunCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class SalesRunSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("due_at must include a timezone offset")
    return value.astimezone(UTC)


def _within_horizon(value: datetime) -> datetime:
    now = datetime.now(UTC)
    if value < now - _MAX_HORIZON or value > now + _MAX_HORIZON:
        raise ValueError("due_at is outside the allowed range")
    return value


class SalesRunScheduleFollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    due_at: datetime
    type: LeadFollowUpType = LeadFollowUpType.EMAIL_FOLLOW_UP
    notes: str | None = Field(default=None, max_length=4000)
    body_text: str | None = Field(default=None, max_length=8000)

    @field_validator("due_at")
    @classmethod
    def aware_due_at(cls, value: datetime) -> datetime:
        return _within_horizon(_require_aware(value))

    @field_validator("notes", "body_text", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def email_requires_body(self) -> Self:
        if self.type == LeadFollowUpType.EMAIL_FOLLOW_UP and not self.body_text:
            raise ValueError("body_text is required for EMAIL_FOLLOW_UP")
        return self


class SalesRunLeadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: str | None = None
    status: LeadStatus


class SalesRunQualificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str


class SalesRunDraftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    review_status: LeadResponseReviewStatus | None = None


class SalesRunEmailSendSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    recipient_email: str
    provider: str | None = None
    provider_message_id: str | None = None
    draft_revision: int
    failure_category: ExecutionFailureCategory | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


class SalesRunFollowUpSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: LeadFollowUpType
    status: LeadFollowUpStatus
    due_at: datetime
    is_overdue: bool


class LeadLatestSalesRunEmailSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    completed_at: datetime | None = None


class LeadLatestSalesRunFollowUpSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LeadFollowUpStatus
    due_at: datetime
    is_overdue: bool


class LeadLatestSalesRunSummary(BaseModel):
    """Safe directory summary. No enquiry, bodies, or provider payloads."""

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    status: SalesRunStatus
    stage: SalesRunStage
    email_send: LeadLatestSalesRunEmailSummary | None = None
    follow_up: LeadLatestSalesRunFollowUpSummary | None = None


class SalesRunPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    lead_id: str
    status: SalesRunStatus
    stage: SalesRunStage
    qualification_id: str | None = None
    response_draft_id: str | None = None
    email_send_id: str | None = None
    follow_up_id: str | None = None
    failure_category: ExecutionFailureCategory | None = None
    error: str | None = None
    initiated_by_user_id: str | None = None
    revision: int
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    enquiry: str | None = None
    lead: SalesRunLeadSummary | None = None
    qualification: SalesRunQualificationSummary | None = None
    response_draft: SalesRunDraftSummary | None = None
    email_send: SalesRunEmailSendSummary | None = None
    follow_up: SalesRunFollowUpSummary | None = None


class SalesRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SalesRunPublic]
    limit: int
    offset: int
    total: int
    status_counts: dict[str, int] | None = None
