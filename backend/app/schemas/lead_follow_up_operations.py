"""Organization-scoped follow-up operations view.

Read-only projections for the Follow-ups screen. The execution summary exposes
only safe fields: no provider payload, no authorization header and no secret.
The snapshot body is deliberately omitted here; the human-authored body stays
in the per-lead follow-up views that already show it.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus
from app.schemas.lead_follow_up import LeadFollowUpPublic


class FollowUpLeadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: str | None = None


class FollowUpExecutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: LeadFollowUpExecutionStatus
    attempt: int
    recipient_email: str
    provider: str | None = None
    provider_message_id: str | None = None
    failure_category: ExecutionFailureCategory | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None


class FollowUpOperationsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    follow_up: LeadFollowUpPublic
    lead: FollowUpLeadSummary
    latest_execution: FollowUpExecutionSummary | None = None


class FollowUpOperationsSummary(BaseModel):
    """Counts across the whole organization, not just the current page."""

    model_config = ConfigDict(extra="forbid")

    overdue: int
    due_today: int
    upcoming: int
    completed: int
    cancelled: int


class FollowUpOperationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FollowUpOperationsItem]
    summary: FollowUpOperationsSummary
    limit: int
    offset: int
    total: int
