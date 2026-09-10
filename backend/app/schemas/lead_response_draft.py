from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.provider import TokenUsage
from app.models.lead_response_draft import LeadResponseReviewStatus
from app.schemas.lead_email_send import LeadEmailSendPublic


class LeadResponseDraftOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    response: str = Field(min_length=1, max_length=8000)

    @field_validator("response")
    @classmethod
    def strip_response(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Response is required")
        return stripped


LEAD_RESPONSE_DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["response"],
    "properties": {"response": {"type": "string"}},
}


class LeadRespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enquiry: str = Field(min_length=1, max_length=8000)

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped


class LeadResponseDraftPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lead_id: str
    status: str
    enquiry: str
    original_response: str | None = None
    response: str | None = None
    human_edited: bool = False
    review_status: LeadResponseReviewStatus | None = None
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    revision: int
    error: str | None = None
    failure_category: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    duration_ms: int | None = None
    latest_email_send: LeadEmailSendPublic | None = None


class LeadResponseDraftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    review_status: LeadResponseReviewStatus | None = None
    created_at: datetime


class LeadResponseDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=8000)
    expected_revision: int = Field(ge=1)

    @field_validator("response")
    @classmethod
    def strip_response(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Response is required")
        return stripped


class LeadResponseDraftApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class LeadResponseDraftSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LeadResponseDraftRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value
