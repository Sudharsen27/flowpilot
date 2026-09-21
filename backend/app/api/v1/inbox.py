from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.lead import LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUpStatus
from app.models.organization import Organization
from app.models.sales_run import SalesRunStatus
from app.schemas.inbox import (
    InboxConversationResponse,
    InboxConversationState,
    InboxListResponse,
)
from app.services.inbox_service import (
    INBOX_LIST_DEFAULT_LIMIT,
    INBOX_LIST_MAX_LIMIT,
    InboxService,
)

router = APIRouter(prefix="/api/v1/inbox", tags=["inbox"])


@router.get("", response_model=InboxListResponse)
def list_inbox(
    q: str | None = Query(default=None, max_length=200),
    lead_status: LeadStatus | None = None,
    needs_approval: bool | None = None,
    conversation_state: InboxConversationState | None = None,
    email_status: LeadEmailSendStatus | None = None,
    sales_run_status: SalesRunStatus | None = None,
    follow_up_status: LeadFollowUpStatus | None = None,
    source: LeadSource | None = None,
    limit: int = Query(default=INBOX_LIST_DEFAULT_LIMIT, ge=1, le=INBOX_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> InboxListResponse:
    return InboxService(db).list(
        organization.id,
        search=q,
        lead_status=lead_status,
        needs_approval=needs_approval,
        conversation_state=conversation_state,
        email_status=email_status,
        sales_run_status=sales_run_status,
        follow_up_status=follow_up_status,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}", response_model=InboxConversationResponse)
def get_inbox_conversation(
    lead_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> InboxConversationResponse:
    return InboxService(db).get_conversation(organization.id, lead_id)
