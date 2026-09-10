from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeadEmailSendPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lead_id: str
    response_draft_id: str
    status: str
    recipient_email: str
    sender_email: str
    subject: str
    body_text: str
    draft_revision: int
    provider: str | None = None
    provider_message_id: str | None = None
    error: str | None = None
    failure_category: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    duration_ms: int | None = None
