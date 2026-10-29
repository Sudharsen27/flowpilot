from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.schemas.approvals import ApprovalQueueStatus


class ActivityEventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: ActivityEventType
    title: str
    summary: str | None = None
    occurred_at: datetime
    actor_type: ActivityActorType
    actor_user_id: str | None = None
    actor_name: str | None = None
    agent_id: str | None = None
    entity_type: ActivityEntityType
    entity_id: str
    lead_id: str | None = None
    status: str | None = None
    sales_run_id: str | None = None
    execution_id: str | None = None
    email_send_id: str | None = None
    follow_up_id: str | None = None
    follow_up_execution_id: str | None = None
    draft_id: str | None = None
    # Approval queue that lists the draft now (not when the event happened); None when
    # the draft is missing, failed, or outside the organization.
    draft_approval_status: ApprovalQueueStatus | None = None
    qualification_id: str | None = None


class ActivityListResponse(BaseModel):
    items: list[ActivityEventPublic]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    type_counts: dict[ActivityEventType, int]
