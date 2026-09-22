from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from app.repositories.agent_repository import AgentRepository
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_response_draft_repository import (
    APPROVAL_LIST_DEFAULT_LIMIT,
    APPROVAL_LIST_MAX_LIMIT,
    LeadResponseDraftRepository,
)
from app.repositories.sales_run_repository import SalesRunRepository
from app.schemas.approvals import (
    ApprovalDraftPublic,
    ApprovalEmailPublic,
    ApprovalLeadPublic,
    ApprovalListResponse,
    ApprovalQueueItemPublic,
    ApprovalQueueStatus,
    ApprovalSalesRunPublic,
)


class ApprovalService:
    """Draft-centric Approval Center queue over existing review entities."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.drafts = LeadResponseDraftRepository(session)
        self.sales_runs = SalesRunRepository(session)
        self.sends = LeadEmailSendRepository(session)
        self.agents = AgentRepository(session)

    def list(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        status: ApprovalQueueStatus = ApprovalQueueStatus.pending,
        limit: int = APPROVAL_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ApprovalListResponse:
        capped = min(max(limit, 1), APPROVAL_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        cleaned = _sanitize_search(search)
        review_statuses = _review_statuses_for_queue(status)

        pairs, total = self.drafts.list_for_approval_queue(
            organization_id,
            review_statuses=review_statuses,
            search=cleaned,
            limit=capped,
            offset=safe_offset,
        )
        if not pairs:
            return ApprovalListResponse(
                items=[],
                limit=capped,
                offset=safe_offset,
                total=total,
            )

        draft_ids = [draft.id for draft, _lead in pairs]
        runs_by_draft = self.sales_runs.latest_for_drafts(organization_id, draft_ids)
        sends_by_draft = self.sends.latest_for_drafts(organization_id, draft_ids)
        agent_ids = list({run.agent_id for run in runs_by_draft.values()})
        agents = self.agents.get_by_ids(organization_id, agent_ids)

        items: list[ApprovalQueueItemPublic] = []
        for draft, lead in pairs:
            run = runs_by_draft.get(draft.id)
            send = sends_by_draft.get(draft.id)
            agent_name = None
            if run is not None:
                agent = agents.get(run.agent_id)
                agent_name = agent.name if agent is not None else None
            items.append(
                _to_queue_item(
                    draft=draft,
                    lead=lead,
                    sales_run=run,
                    agent_name=agent_name,
                    email_send=send,
                )
            )

        return ApprovalListResponse(
            items=items,
            limit=capped,
            offset=safe_offset,
            total=total,
        )


def _review_statuses_for_queue(status: ApprovalQueueStatus) -> tuple[str, ...]:
    if status == ApprovalQueueStatus.pending:
        return (
            LeadResponseReviewStatus.GENERATED.value,
            LeadResponseReviewStatus.EDITED.value,
        )
    if status == ApprovalQueueStatus.approved:
        return (LeadResponseReviewStatus.APPROVED.value,)
    return (LeadResponseReviewStatus.REJECTED.value,)


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_"})
    return cleaned or None


def _review_value(review: str | LeadResponseReviewStatus | None) -> str | None:
    if review is None:
        return None
    if isinstance(review, LeadResponseReviewStatus):
        return review.value
    return str(review)


def _needs_approval(draft: LeadResponseDraft, sales_run: SalesRun | None) -> bool:
    if sales_run is not None and sales_run.status == SalesRunStatus.WAITING_APPROVAL:
        return True
    if draft.status != LeadResponseDraftStatus.COMPLETED:
        return False
    return _review_value(draft.review_status) in {
        LeadResponseReviewStatus.GENERATED.value,
        LeadResponseReviewStatus.EDITED.value,
    }


def _action_flags(
    draft: LeadResponseDraft,
    lead: Lead,
    email_send: LeadEmailSend | None,
) -> tuple[bool, bool, bool, bool]:
    completed = draft.status == LeadResponseDraftStatus.COMPLETED
    review = _review_value(draft.review_status)
    has_response = bool(draft.current_response)
    pending_review = review in {
        LeadResponseReviewStatus.GENERATED.value,
        LeadResponseReviewStatus.EDITED.value,
    }
    approved = review == LeadResponseReviewStatus.APPROVED.value
    rejected = review == LeadResponseReviewStatus.REJECTED.value

    can_approve = completed and has_response and pending_review
    can_reject = completed and review in {
        LeadResponseReviewStatus.GENERATED.value,
        LeadResponseReviewStatus.EDITED.value,
        LeadResponseReviewStatus.APPROVED.value,
    }
    can_edit = completed and not rejected and draft.original_response is not None

    active_send = (
        email_send is not None
        and email_send.draft_revision == draft.revision
        and email_send.status
        in {LeadEmailSendStatus.PENDING.value, LeadEmailSendStatus.SENT.value}
    )
    can_send = (
        completed
        and approved
        and has_response
        and bool(lead.email)
        and not active_send
    )
    return can_approve, can_reject, can_edit, can_send


def _to_queue_item(
    *,
    draft: LeadResponseDraft,
    lead: Lead,
    sales_run: SalesRun | None,
    agent_name: str | None,
    email_send: LeadEmailSend | None,
) -> ApprovalQueueItemPublic:
    review_status = None
    if draft.review_status:
        review_status = LeadResponseReviewStatus(draft.review_status)

    sales_run_public = None
    if sales_run is not None:
        sales_run_public = ApprovalSalesRunPublic(
            id=sales_run.id,
            status=SalesRunStatus(sales_run.status),
            stage=SalesRunStage(sales_run.stage),
            agent_id=sales_run.agent_id,
            agent_name=agent_name,
        )

    email_public = None
    if email_send is not None:
        sent_at = None
        if email_send.status == LeadEmailSendStatus.SENT:
            sent_at = email_send.completed_at
        email_public = ApprovalEmailPublic(
            status=str(email_send.status),
            sent_at=sent_at,
        )

    can_approve, can_reject, can_edit, can_send = _action_flags(
        draft, lead, email_send
    )

    return ApprovalQueueItemPublic(
        draft_id=draft.id,
        lead_id=lead.id,
        lead=ApprovalLeadPublic(
            name=lead.name,
            email=lead.email,
            company=lead.company,
            status=LeadStatus(lead.status),
            source=LeadSource(lead.source),
        ),
        enquiry=draft.enquiry,
        draft=ApprovalDraftPublic(
            response=draft.current_response,
            review_status=review_status,
            revision=draft.revision,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        ),
        sales_run=sales_run_public,
        email=email_public,
        needs_approval=_needs_approval(draft, sales_run),
        can_approve=can_approve,
        can_reject=can_reject,
        can_edit=can_edit,
        can_send=can_send,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )
