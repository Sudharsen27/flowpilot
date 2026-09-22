"""Read and controlled-write agent tools that delegate to existing FlowPilot services.

Tenant identity always comes from ToolContext.organization_id — never from
tool arguments. ActivityEvents for draft creation are owned by
LeadResponseDraftService (not duplicated here).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.core.exceptions import (
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
)
from app.models.lead import LeadSource, LeadStatus
from app.models.lead_follow_up import LeadFollowUpStatus
from app.repositories.lead_follow_up_repository import (
    FOLLOW_UP_LIST_DEFAULT_LIMIT,
    FOLLOW_UP_LIST_MAX_LIMIT,
)
from app.repositories.lead_repository import LEAD_LIST_DEFAULT_LIMIT, LEAD_LIST_MAX_LIMIT
from app.services.inbox_service import InboxService
from app.services.lead_follow_up_service import LeadFollowUpService
from app.services.lead_response_draft_service import LeadResponseDraftService
from app.services.lead_service import LeadService
from app.services.tool_execution_service import ToolExecutionError
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


class CreateResponseDraftInput(BaseModel):
    """Matches LeadResponseDraftService.generate / LeadRespondRequest contract."""

    model_config = ConfigDict(extra="forbid")

    lead_id: str = Field(min_length=1, max_length=36)
    enquiry: str = Field(min_length=1, max_length=8000)

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped


class CreateResponseDraftOutput(BaseModel):
    draft_id: str
    lead_id: str
    status: str
    review_status: str | None = None
    revision: int
    created_at: datetime


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


class CreateResponseDraftTool(Tool):
    """Controlled WRITE: create a LeadResponseDraft via existing draft service.

    Does not approve, reject, or send. Human review remains in Approval Center.
    DefaultToolPolicy ALLOWs WRITE + LOW risk for org members; it does not
    REQUIRE_APPROVAL for this classification (send/approve remain separate).
    """

    name = "create_response_draft"
    description = (
        "Create a customer response draft for a lead in the current organization "
        "using the existing draft generator. Persists a LeadResponseDraft for "
        "human review in Approvals. Does not approve, reject, or send email."
    )
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.WRITE
    requires_human_approval = False
    input_model = CreateResponseDraftInput
    output_model = CreateResponseDraftOutput

    def __init__(
        self, session: Session, provider: AIProvider | None = None
    ) -> None:
        self._session = session
        self._provider = provider

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        payload = CreateResponseDraftInput.model_validate(arguments)
        service = LeadResponseDraftService(self._session, self._provider)
        try:
            row = service.generate(
                organization_id=context.organization_id,
                lead_id=payload.lead_id,
                enquiry=payload.enquiry,
                initiated_by_user_id=context.user_id,
            )
        except NotFoundError:
            raise
        except (ProviderError, ProviderNotConfiguredError) as exc:
            raise ToolExecutionError(exc.detail) from exc

        review = row.review_status
        return CreateResponseDraftOutput(
            draft_id=row.id,
            lead_id=row.lead_id,
            status=str(row.status),
            review_status=str(review) if review is not None else None,
            revision=row.revision,
            created_at=row.created_at,
        )
