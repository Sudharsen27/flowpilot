from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.provider import TokenUsage


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
    response: str | None = None
    error: str | None = None
    failure_category: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    duration_ms: int | None = None


class LeadResponseDraftSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    created_at: datetime
