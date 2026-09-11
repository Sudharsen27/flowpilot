from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead import LeadStatus
from app.models.lead_response_draft import LeadResponseReviewStatus
from app.models.sales_run import SalesRunStage, SalesRunStatus


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


class SalesRunCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


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


class SalesRunPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    lead_id: str
    status: SalesRunStatus
    stage: SalesRunStage
    qualification_id: str | None = None
    response_draft_id: str | None = None
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


class SalesRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SalesRunPublic]
    limit: int
    offset: int
    total: int
    status_counts: dict[str, int] | None = None
