from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEventType,
)
from app.models.lead import LeadSource, LeadStatus
from app.models.lead_follow_up import LeadFollowUpStatus
from app.schemas.lead_response_draft import LeadResponseDraftSummary
from app.schemas.sales_run import LeadLatestSalesRunSummary


class InboxConversationState(StrEnum):
    OPEN = "OPEN"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    CLOSED = "CLOSED"


class InboxTimelineKind(StrEnum):
    LEAD_CREATED = "LEAD_CREATED"
    WEBSITE_ENQUIRY = "WEBSITE_ENQUIRY"
    LEAD_STATUS_CHANGED = "LEAD_STATUS_CHANGED"
    QUALIFICATION_COMPLETED = "QUALIFICATION_COMPLETED"
    DRAFT_GENERATED = "DRAFT_GENERATED"
    DRAFT_EDITED = "DRAFT_EDITED"
    DRAFT_APPROVED = "DRAFT_APPROVED"
    DRAFT_REJECTED = "DRAFT_REJECTED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"
    FOLLOW_UP_SCHEDULED = "FOLLOW_UP_SCHEDULED"
    FOLLOW_UP_RESCHEDULED = "FOLLOW_UP_RESCHEDULED"
    FOLLOW_UP_COMPLETED = "FOLLOW_UP_COMPLETED"
    FOLLOW_UP_CANCELLED = "FOLLOW_UP_CANCELLED"
    FOLLOW_UP_EXECUTION_SENT = "FOLLOW_UP_EXECUTION_SENT"
    FOLLOW_UP_EXECUTION_FAILED = "FOLLOW_UP_EXECUTION_FAILED"
    SALES_RUN_STARTED = "SALES_RUN_STARTED"
    SALES_RUN_WAITING_APPROVAL = "SALES_RUN_WAITING_APPROVAL"
    SALES_RUN_COMPLETED = "SALES_RUN_COMPLETED"
    SALES_RUN_CANCELLED = "SALES_RUN_CANCELLED"
    SALES_RUN_FAILED = "SALES_RUN_FAILED"


class InboxDirection(StrEnum):
    inbound = "inbound"
    outbound = "outbound"
    internal = "internal"


class InboxItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str
    name: str
    email: str | None
    company: str | None
    source: LeadSource
    lead_status: LeadStatus
    conversation_state: InboxConversationState
    needs_approval: bool
    last_activity_at: datetime
    last_activity_type: ActivityEventType | None
    last_activity_title: str | None
    preview: str | None
    latest_draft: LeadResponseDraftSummary | None
    latest_email_status: Literal["PENDING", "SENT", "FAILED"] | None
    latest_sales_run: LeadLatestSalesRunSummary | None
    latest_follow_up_status: LeadFollowUpStatus | None
    latest_follow_up_overdue: bool | None


class InboxListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InboxItemPublic]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    state_counts: dict[InboxConversationState, int]
    needs_approval_count: int = Field(ge=0)


class InboxLeadContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str
    name: str
    email: str | None
    phone: str | None
    company: str | None
    source: LeadSource
    lead_status: LeadStatus
    enquiry: str | None
    conversation_state: InboxConversationState
    needs_approval: bool
    latest_draft: LeadResponseDraftSummary | None
    latest_sales_run: LeadLatestSalesRunSummary | None


class InboxTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: InboxTimelineKind
    direction: InboxDirection
    occurred_at: datetime
    title: str
    summary: str | None
    body: str | None
    status: str | None
    actor_type: ActivityActorType | None
    actor_user_id: str | None
    agent_id: str | None
    source_entity_type: ActivityEntityType | Literal["LEAD"]
    source_entity_id: str
    activity_id: str | None
    is_draft: bool
    is_sent_message: bool
    draft_id: str | None = None
    email_send_id: str | None = None
    follow_up_id: str | None = None
    follow_up_execution_id: str | None = None
    sales_run_id: str | None = None
    qualification_id: str | None = None


class InboxConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead: InboxLeadContext
    items: list[InboxTimelineItem]
    total_items: int = Field(ge=0)
