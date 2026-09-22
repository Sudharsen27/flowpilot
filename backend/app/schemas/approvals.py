from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.lead import LeadSource, LeadStatus
from app.models.lead_response_draft import LeadResponseReviewStatus
from app.models.sales_run import SalesRunStage, SalesRunStatus


class ApprovalQueueStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ApprovalLeadPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    email: str | None
    company: str | None
    status: LeadStatus
    source: LeadSource


class ApprovalDraftPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: str | None
    review_status: LeadResponseReviewStatus | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ApprovalSalesRunPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: SalesRunStatus
    stage: SalesRunStage
    agent_id: str
    agent_name: str | None


class ApprovalEmailPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    sent_at: datetime | None


class ApprovalQueueItemPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    lead_id: str
    lead: ApprovalLeadPublic
    enquiry: str
    draft: ApprovalDraftPublic
    sales_run: ApprovalSalesRunPublic | None
    email: ApprovalEmailPublic | None
    needs_approval: bool
    can_approve: bool
    can_reject: bool
    can_edit: bool
    can_send: bool
    created_at: datetime
    updated_at: datetime


class ApprovalListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ApprovalQueueItemPublic]
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
