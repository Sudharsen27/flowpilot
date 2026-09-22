"""Read-only agent tools that delegate to existing FlowPilot services.

Tenant identity always comes from ToolContext.organization_id — never from
tool arguments. These tools do not create ActivityEvents; read paths already
use org-scoped repositories, and Phase 6D.3+ will decide invocation auditing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models.lead import LeadSource, LeadStatus
from app.models.lead_follow_up import LeadFollowUpStatus
from app.repositories.lead_follow_up_repository import (
    FOLLOW_UP_LIST_DEFAULT_LIMIT,
    FOLLOW_UP_LIST_MAX_LIMIT,
)
from app.repositories.lead_repository import LEAD_LIST_DEFAULT_LIMIT, LEAD_LIST_MAX_LIMIT
from app.services.inbox_service import InboxService
from app.services.lead_follow_up_service import LeadFollowUpService
from app.services.lead_service import LeadService
from app.tools.base import Tool
from app.tools.schema import ToolContext, ToolRiskLevel, ToolSideEffectLevel


class SearchLeadsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, max_length=200)
    status: LeadStatus | None = None
    source: LeadSource | None = None
    limit: int = Field(default=LEAD_LIST_DEFAULT_LIMIT, ge=1, le=LEAD_LIST_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class SearchLeadsOutput(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class GetLeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(min_length=1, max_length=36)


class GetLeadOutput(BaseModel):
    lead: dict[str, Any]


class GetCustomerContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(min_length=1, max_length=36)


class GetCustomerContextOutput(BaseModel):
    lead: dict[str, Any]
    timeline_item_count: int
    timeline_preview: list[dict[str, Any]]


class GetFollowUpsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(min_length=1, max_length=36)
    status: LeadFollowUpStatus | None = None
    overdue: bool | None = None
    limit: int = Field(
        default=FOLLOW_UP_LIST_DEFAULT_LIMIT, ge=1, le=FOLLOW_UP_LIST_MAX_LIMIT
    )
    offset: int = Field(default=0, ge=0)


class GetFollowUpsOutput(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class SearchLeadsTool(Tool):
    name = "search_leads"
    description = (
        "Search leads in the current organization by text, status, or source. "
        "Read-only. Does not create or modify leads."
    )
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.READ
    requires_human_approval = False
    input_model = SearchLeadsInput
    output_model = SearchLeadsOutput

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = SearchLeadsInput.model_validate(arguments)
        result = LeadService(self._session).list(
            context.organization_id,
            status=payload.status,
            source=payload.source,
            search=payload.query,
            limit=payload.limit,
            offset=payload.offset,
        )
        return SearchLeadsOutput(
            items=[item.model_dump(mode="json") for item in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )


class GetLeadTool(Tool):
    name = "get_lead"
    description = (
        "Get one lead by id in the current organization, including latest "
        "qualification, draft, and sales-run summaries when available. Read-only."
    )
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.READ
    requires_human_approval = False
    input_model = GetLeadInput
    output_model = GetLeadOutput

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = GetLeadInput.model_validate(arguments)
        lead = LeadService(self._session).get_public(
            context.organization_id, payload.lead_id
        )
        return GetLeadOutput(lead=lead.model_dump(mode="json"))


class GetCustomerContextTool(Tool):
    name = "get_customer_context"
    description = (
        "Get Customer 360 / inbox conversation context for a lead in the current "
        "organization: profile, enquiry, approval needs, and a timeline preview. "
        "Read-only."
    )
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.READ
    requires_human_approval = False
    input_model = GetCustomerContextInput
    output_model = GetCustomerContextOutput

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = GetCustomerContextInput.model_validate(arguments)
        conversation = InboxService(self._session).get_conversation(
            context.organization_id, payload.lead_id
        )
        preview = [
            item.model_dump(mode="json") for item in conversation.items[:10]
        ]
        return GetCustomerContextOutput(
            lead=conversation.lead.model_dump(mode="json"),
            timeline_item_count=conversation.total_items,
            timeline_preview=preview,
        )


class GetFollowUpsTool(Tool):
    name = "get_followups"
    description = (
        "List follow-ups for a lead in the current organization. Read-only. "
        "Does not schedule, cancel, or send follow-ups."
    )
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.READ
    requires_human_approval = False
    input_model = GetFollowUpsInput
    output_model = GetFollowUpsOutput

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = GetFollowUpsInput.model_validate(arguments)
        result = LeadFollowUpService(self._session).list(
            context.organization_id,
            payload.lead_id,
            status=payload.status,
            overdue=payload.overdue,
            limit=payload.limit,
            offset=payload.offset,
        )
        return GetFollowUpsOutput(
            items=[item.model_dump(mode="json") for item in result.items],
            total=result.total,
            limit=result.limit,
            offset=result.offset,
        )
