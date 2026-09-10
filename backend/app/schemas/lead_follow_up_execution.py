from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus


class LeadFollowUpExecutionPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lead_id: str
    follow_up_id: str
    status: LeadFollowUpExecutionStatus
    attempt: int
    recipient_email: str
    sender_email: str
    subject: str
    body_text: str
    provider: str | None = None
    provider_message_id: str | None = None
    failure_category: ExecutionFailureCategory | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    duration_ms: int | None = None
    provider_idempotency_key: str


class LeadFollowUpExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LeadFollowUpExecutionPublic]
    limit: int
    offset: int
    total: int


class LeadFollowUpExecutionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_email: str = Field(min_length=1, max_length=320)
    sender_email: str = Field(min_length=1, max_length=320)
    subject: str = Field(min_length=1, max_length=200)
    body_text: str = Field(min_length=1, max_length=8000)
