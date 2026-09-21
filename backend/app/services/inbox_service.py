from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import NotFoundError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus
from app.models.lead_follow_up_execution import LeadFollowUpExecution
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.sales_run import SalesRun, SalesRunStatus
from app.repositories.activity_event_repository import ActivityEventRepository
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_follow_up_execution_repository import (
    LeadFollowUpExecutionRepository,
)
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.repositories.lead_qualification_repository import LeadQualificationRepository
from app.repositories.lead_repository import (
    LEAD_LIST_DEFAULT_LIMIT,
    LEAD_LIST_MAX_LIMIT,
    LeadRepository,
)
from app.repositories.lead_response_draft_repository import LeadResponseDraftRepository
from app.repositories.sales_run_repository import SalesRunRepository
from app.schemas.inbox import (
    InboxConversationResponse,
    InboxConversationState,
    InboxDirection,
    InboxItemPublic,
    InboxLeadContext,
    InboxListResponse,
    InboxTimelineItem,
    InboxTimelineKind,
)
from app.services.lead_follow_up_service import to_follow_up_public
from app.services.lead_service import _draft_summary, _sales_run_summary

INBOX_LIST_DEFAULT_LIMIT = LEAD_LIST_DEFAULT_LIMIT
INBOX_LIST_MAX_LIMIT = LEAD_LIST_MAX_LIMIT
INBOX_TIMELINE_MAX_ITEMS = 200
_PREVIEW_MAX = 160

# Module-level aliases avoid mypy resolving list[...] to InboxService.list.
_LeadRows = list[Lead]
_StrIds = list[str]
_InboxItems = list[InboxItemPublic]
_TimelineItems = list[InboxTimelineItem]
_ActivityRows = list[ActivityEvent]

_TITLE_KIND: dict[str, InboxTimelineKind] = {
    "Lead created": InboxTimelineKind.LEAD_CREATED,
    "Website enquiry received": InboxTimelineKind.WEBSITE_ENQUIRY,
    "Lead status changed": InboxTimelineKind.LEAD_STATUS_CHANGED,
    "Lead qualified": InboxTimelineKind.QUALIFICATION_COMPLETED,
    "Response draft generated": InboxTimelineKind.DRAFT_GENERATED,
    "Response draft edited": InboxTimelineKind.DRAFT_EDITED,
    "Response draft approved": InboxTimelineKind.DRAFT_APPROVED,
    "Response draft rejected": InboxTimelineKind.DRAFT_REJECTED,
    "Email sent": InboxTimelineKind.EMAIL_SENT,
    "Email send failed": InboxTimelineKind.EMAIL_FAILED,
    "Follow-up scheduled": InboxTimelineKind.FOLLOW_UP_SCHEDULED,
    "Follow-up rescheduled": InboxTimelineKind.FOLLOW_UP_RESCHEDULED,
    "Follow-up completed": InboxTimelineKind.FOLLOW_UP_COMPLETED,
    "Follow-up cancelled": InboxTimelineKind.FOLLOW_UP_CANCELLED,
    "Follow-up executed": InboxTimelineKind.FOLLOW_UP_EXECUTION_SENT,
    "Follow-up failed": InboxTimelineKind.FOLLOW_UP_EXECUTION_FAILED,
    "Sales Agent started": InboxTimelineKind.SALES_RUN_STARTED,
    "Waiting for review": InboxTimelineKind.SALES_RUN_WAITING_APPROVAL,
    "Sales Run completed": InboxTimelineKind.SALES_RUN_COMPLETED,
    "Sales Run cancelled": InboxTimelineKind.SALES_RUN_CANCELLED,
    "Sales Run failed": InboxTimelineKind.SALES_RUN_FAILED,
}

_DRAFT_KINDS = {
    InboxTimelineKind.DRAFT_GENERATED,
    InboxTimelineKind.DRAFT_EDITED,
    InboxTimelineKind.DRAFT_APPROVED,
    InboxTimelineKind.DRAFT_REJECTED,
}
_SENT_KINDS = {
    InboxTimelineKind.EMAIL_SENT,
    InboxTimelineKind.FOLLOW_UP_EXECUTION_SENT,
}
_INBOUND_KINDS = {InboxTimelineKind.WEBSITE_ENQUIRY}
_OUTBOUND_KINDS = {
    InboxTimelineKind.EMAIL_SENT,
    InboxTimelineKind.EMAIL_FAILED,
    InboxTimelineKind.FOLLOW_UP_EXECUTION_SENT,
    InboxTimelineKind.FOLLOW_UP_EXECUTION_FAILED,
}


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_"})
    return cleaned or None


def _preview(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    if len(cleaned) <= _PREVIEW_MAX:
        return cleaned
    return cleaned[: _PREVIEW_MAX - 1] + "…"


def _enquiry_nonempty() -> ColumnElement[bool]:
    return and_(
        Lead.enquiry.is_not(None),
        func.length(func.trim(Lead.enquiry)) > 0,
    )


class InboxService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.events = ActivityEventRepository(session)
        self.drafts = LeadResponseDraftRepository(session)
        self.sends = LeadEmailSendRepository(session)
        self.follow_ups = LeadFollowUpRepository(session)
        self.executions = LeadFollowUpExecutionRepository(session)
        self.sales_runs = SalesRunRepository(session)
        self.qualifications = LeadQualificationRepository(session)

    def list(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        lead_status: LeadStatus | None = None,
        needs_approval: bool | None = None,
        conversation_state: InboxConversationState | None = None,
        email_status: LeadEmailSendStatus | None = None,
        sales_run_status: SalesRunStatus | None = None,
        follow_up_status: LeadFollowUpStatus | None = None,
        source: LeadSource | None = None,
        limit: int = INBOX_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> InboxListResponse:
        capped = min(max(limit, 1), INBOX_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        search = _sanitize_search(search)

        candidates = self._list_candidate_leads(
            organization_id,
            lead_status=lead_status,
            source=source,
            search=search,
        )
        if not candidates:
            empty_counts = {state: 0 for state in InboxConversationState}
            return InboxListResponse(
                items=[],
                limit=capped,
                offset=safe_offset,
                total=0,
                state_counts=empty_counts,
                needs_approval_count=0,
            )

        lead_ids = [lead.id for lead in candidates]
        hydrated = self._hydrate_leads(organization_id, candidates, lead_ids)

        items: _InboxItems = []
        for lead in candidates:
            item = hydrated[lead.id]
            if needs_approval is not None and item.needs_approval is not needs_approval:
                continue
            if (
                conversation_state is not None
                and item.conversation_state != conversation_state
            ):
                continue
            if email_status is not None and item.latest_email_status != email_status.value:
                continue
            if sales_run_status is not None:
                run = item.latest_sales_run
                if run is None or run.status != sales_run_status:
                    continue
            if follow_up_status is not None and item.latest_follow_up_status != follow_up_status:
                continue
            items.append(item)

        items.sort(key=lambda row: (row.last_activity_at, row.lead_id), reverse=True)

        state_counts = {state: 0 for state in InboxConversationState}
        needs_approval_count = 0
        for item in items:
            state_counts[item.conversation_state] += 1
            if item.needs_approval:
                needs_approval_count += 1

        page = items[safe_offset : safe_offset + capped]
        return InboxListResponse(
            items=page,
            limit=capped,
            offset=safe_offset,
            total=len(items),
            state_counts=state_counts,
            needs_approval_count=needs_approval_count,
        )

    def get_conversation(
        self, organization_id: str, lead_id: str
    ) -> InboxConversationResponse:
        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")

        drafts = self.drafts.latest_completed_for_leads(organization_id, [lead.id])
        runs = self.sales_runs.latest_for_leads(organization_id, [lead.id])
        sends = self.sends.latest_for_leads(organization_id, [lead.id])
        follow_ups = self.follow_ups.latest_for_leads(organization_id, [lead.id])
        draft = drafts.get(lead.id)
        run = runs.get(lead.id)
        send = sends.get(lead.id)
        follow_up = follow_ups.get(lead.id)
        run_send = None
        run_follow_up = None
        if run is not None:
            if run.email_send_id:
                run_send = self.sends.get_by_id(organization_id, run.email_send_id)
            if run.follow_up_id:
                run_follow_up = self.follow_ups.get_by_id(
                    organization_id, lead.id, run.follow_up_id
                )
        sales_summary = _sales_run_summary(run, run_send or send, run_follow_up or follow_up)
        needs = self._needs_approval(draft, run)
        state = self._conversation_state(
            lead=lead,
            needs_approval=needs,
            sales_run=run,
            latest_email=send,
            latest_follow_up=follow_up,
        )

        events, _total = self.events.list_for_organization(
            organization_id,
            limit=INBOX_TIMELINE_MAX_ITEMS,
            offset=0,
            lead_id=lead.id,
            oldest_first=True,
        )
        timeline = self._build_timeline(organization_id, lead, events)

        return InboxConversationResponse(
            lead=InboxLeadContext(
                lead_id=lead.id,
                name=lead.name,
                email=lead.email,
                phone=lead.phone,
                company=lead.company,
                source=LeadSource(lead.source),
                lead_status=LeadStatus(lead.status),
                enquiry=lead.enquiry,
                conversation_state=state,
                needs_approval=needs,
                latest_draft=_draft_summary(draft),
                latest_sales_run=sales_summary,
            ),
            items=timeline,
            total_items=len(timeline),
        )

    def _list_candidate_leads(
        self,
        organization_id: str,
        *,
        lead_status: LeadStatus | None,
        source: LeadSource | None,
        search: str | None,
    ) -> _LeadRows:
        inclusion = or_(
            _enquiry_nonempty(),
            Lead.source == LeadSource.WEBSITE,
            exists(
                select(LeadResponseDraft.id).where(
                    LeadResponseDraft.organization_id == organization_id,
                    LeadResponseDraft.lead_id == Lead.id,
                )
            ),
            exists(
                select(LeadEmailSend.id).where(
                    LeadEmailSend.organization_id == organization_id,
                    LeadEmailSend.lead_id == Lead.id,
                )
            ),
            exists(
                select(SalesRun.id).where(
                    SalesRun.organization_id == organization_id,
                    SalesRun.lead_id == Lead.id,
                )
            ),
            exists(
                select(LeadFollowUp.id).where(
                    LeadFollowUp.organization_id == organization_id,
                    LeadFollowUp.lead_id == Lead.id,
                )
            ),
            exists(
                select(ActivityEvent.id).where(
                    ActivityEvent.organization_id == organization_id,
                    ActivityEvent.lead_id == Lead.id,
                )
            ),
        )
        filters = [Lead.organization_id == organization_id, inclusion]
        if lead_status is not None:
            filters.append(Lead.status == lead_status)
        if source is not None:
            filters.append(Lead.source == source)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Lead.name.ilike(pattern),
                    Lead.email.ilike(pattern),
                    Lead.company.ilike(pattern),
                )
            )
        return list(self.session.scalars(select(Lead).where(*filters)))

    def _hydrate_leads(
        self,
        organization_id: str,
        leads: _LeadRows,
        lead_ids: _StrIds,
    ) -> dict[str, InboxItemPublic]:
        drafts = self.drafts.latest_completed_for_leads(organization_id, lead_ids)
        runs = self.sales_runs.latest_for_leads(organization_id, lead_ids)
        sends = self.sends.latest_for_leads(organization_id, lead_ids)
        follow_ups = self.follow_ups.latest_for_leads(organization_id, lead_ids)
        activities = self.events.latest_for_leads(organization_id, lead_ids)

        run_send_ids = [row.email_send_id for row in runs.values() if row.email_send_id]
        run_follow_ids = [row.follow_up_id for row in runs.values() if row.follow_up_id]
        run_sends = self.sends.get_by_ids(organization_id, run_send_ids)
        run_follow_ups = self.follow_ups.get_by_ids(organization_id, run_follow_ids)

        now = datetime.now(UTC)
        result: dict[str, InboxItemPublic] = {}
        for lead in leads:
            draft = drafts.get(lead.id)
            run = runs.get(lead.id)
            send = sends.get(lead.id)
            follow_up = follow_ups.get(lead.id)
            activity = activities.get(lead.id)
            run_send = run_sends.get(run.email_send_id) if run and run.email_send_id else None
            run_follow = (
                run_follow_ups.get(run.follow_up_id) if run and run.follow_up_id else None
            )
            sales_summary = _sales_run_summary(run, run_send or send, run_follow or follow_up)
            needs = self._needs_approval(draft, run)
            state = self._conversation_state(
                lead=lead,
                needs_approval=needs,
                sales_run=run,
                latest_email=send,
                latest_follow_up=follow_up,
            )
            last_at = activity.occurred_at if activity is not None else lead.updated_at
            follow_status = LeadFollowUpStatus(follow_up.status) if follow_up else None
            overdue = None
            if follow_up is not None:
                overdue = to_follow_up_public(follow_up, now=now).is_overdue
            result[lead.id] = InboxItemPublic(
                lead_id=lead.id,
                name=lead.name,
                email=lead.email,
                company=lead.company,
                source=LeadSource(lead.source),
                lead_status=LeadStatus(lead.status),
                conversation_state=state,
                needs_approval=needs,
                last_activity_at=last_at,
                last_activity_type=(
                    ActivityEventType(activity.type) if activity is not None else None
                ),
                last_activity_title=activity.title if activity is not None else None,
                preview=self._item_preview(lead, draft, send),
                latest_draft=_draft_summary(draft),
                latest_email_status=(
                    LeadEmailSendStatus(send.status).value if send is not None else None
                ),
                latest_sales_run=sales_summary,
                latest_follow_up_status=follow_status,
                latest_follow_up_overdue=overdue,
            )
        return result

    def _item_preview(
        self,
        lead: Lead,
        draft: LeadResponseDraft | None,
        send: LeadEmailSend | None,
    ) -> str | None:
        if send is not None and send.body_text:
            return _preview(send.body_text)
        if draft is not None and draft.current_response:
            return _preview(draft.current_response)
        return _preview(lead.enquiry)

    def _needs_approval(
        self, draft: LeadResponseDraft | None, sales_run: SalesRun | None
    ) -> bool:
        if sales_run is not None and sales_run.status == SalesRunStatus.WAITING_APPROVAL:
            return True
        if draft is None or draft.status != LeadResponseDraftStatus.COMPLETED:
            return False
        return draft.review_status in {
            LeadResponseReviewStatus.GENERATED,
            LeadResponseReviewStatus.EDITED,
        }

    def _conversation_state(
        self,
        *,
        lead: Lead,
        needs_approval: bool,
        sales_run: SalesRun | None,
        latest_email: LeadEmailSend | None,
        latest_follow_up: LeadFollowUp | None,
    ) -> InboxConversationState:
        if needs_approval:
            return InboxConversationState.NEEDS_APPROVAL
        if lead.status in {LeadStatus.CONVERTED, LeadStatus.UNQUALIFIED}:
            return InboxConversationState.CLOSED
        pending_follow_up = (
            latest_follow_up is not None
            and latest_follow_up.status == LeadFollowUpStatus.PENDING
        )
        if (
            sales_run is not None
            and sales_run.status == SalesRunStatus.COMPLETED
            and latest_email is not None
            and latest_email.status == LeadEmailSendStatus.SENT
            and not pending_follow_up
        ):
            return InboxConversationState.CLOSED
        return InboxConversationState.OPEN

    def _build_timeline(
        self,
        organization_id: str,
        lead: Lead,
        events: _ActivityRows,
    ) -> _TimelineItems:
        draft_ids: _StrIds = []
        send_ids: _StrIds = []
        follow_up_ids: _StrIds = []
        execution_ids: _StrIds = []
        sales_run_ids: _StrIds = []
        qualification_ids: _StrIds = []
        for event in events:
            entity_type = ActivityEntityType(event.entity_type)
            if entity_type == ActivityEntityType.LEAD_RESPONSE_DRAFT:
                draft_ids.append(event.entity_id)
            elif entity_type == ActivityEntityType.LEAD_EMAIL_SEND:
                send_ids.append(event.entity_id)
            elif entity_type == ActivityEntityType.LEAD_FOLLOW_UP:
                follow_up_ids.append(event.entity_id)
            elif entity_type == ActivityEntityType.LEAD_FOLLOW_UP_EXECUTION:
                execution_ids.append(event.entity_id)
            elif entity_type == ActivityEntityType.SALES_RUN:
                sales_run_ids.append(event.entity_id)
            elif entity_type == ActivityEntityType.LEAD_QUALIFICATION:
                qualification_ids.append(event.entity_id)

        drafts = self.drafts.get_by_ids(organization_id, draft_ids)
        sends = self.sends.get_by_ids(organization_id, send_ids)
        follow_ups = self.follow_ups.get_by_ids(organization_id, follow_up_ids)
        executions = self.executions.get_by_ids(organization_id, execution_ids)
        sales_runs = self.sales_runs.get_by_ids(organization_id, sales_run_ids)
        qualifications = (
            {
                row.id: row
                for row in self.session.scalars(
                    select(LeadQualification).where(
                        LeadQualification.organization_id == organization_id,
                        LeadQualification.id.in_(qualification_ids),
                    )
                )
            }
            if qualification_ids
            else {}
        )

        items: _TimelineItems = []
        for event in events:
            kind = _TITLE_KIND.get(event.title)
            if kind is None:
                continue
            entity_type = ActivityEntityType(event.entity_type)
            body = self._timeline_body(
                kind=kind,
                lead=lead,
                entity_id=event.entity_id,
                drafts=drafts,
                sends=sends,
                executions=executions,
            )
            draft_id = (
                event.entity_id
                if entity_type == ActivityEntityType.LEAD_RESPONSE_DRAFT
                and event.entity_id in drafts
                else None
            )
            email_send_id = (
                event.entity_id
                if entity_type == ActivityEntityType.LEAD_EMAIL_SEND
                and event.entity_id in sends
                else None
            )
            follow_up_id = (
                event.entity_id
                if entity_type == ActivityEntityType.LEAD_FOLLOW_UP
                and event.entity_id in follow_ups
                else None
            )
            follow_up_execution_id = (
                event.entity_id
                if entity_type == ActivityEntityType.LEAD_FOLLOW_UP_EXECUTION
                and event.entity_id in executions
                else None
            )
            sales_run_id = (
                event.entity_id
                if entity_type == ActivityEntityType.SALES_RUN
                and event.entity_id in sales_runs
                else None
            )
            qualification_id = (
                event.entity_id
                if entity_type == ActivityEntityType.LEAD_QUALIFICATION
                and event.entity_id in qualifications
                else None
            )
            items.append(
                InboxTimelineItem(
                    id=event.id,
                    kind=kind,
                    direction=self._direction(kind),
                    occurred_at=event.occurred_at,
                    title=event.title,
                    summary=event.summary,
                    body=body,
                    status=event.status,
                    actor_type=ActivityActorType(event.actor_type),
                    actor_user_id=event.actor_user_id,
                    agent_id=event.agent_id,
                    source_entity_type=entity_type,
                    source_entity_id=event.entity_id,
                    activity_id=event.id,
                    is_draft=kind in _DRAFT_KINDS,
                    is_sent_message=kind in _SENT_KINDS,
                    draft_id=draft_id,
                    email_send_id=email_send_id,
                    follow_up_id=follow_up_id,
                    follow_up_execution_id=follow_up_execution_id,
                    sales_run_id=sales_run_id,
                    qualification_id=qualification_id,
                )
            )
        items.sort(key=lambda row: (row.occurred_at, row.id))
        return items

    def _timeline_body(
        self,
        *,
        kind: InboxTimelineKind,
        lead: Lead,
        entity_id: str,
        drafts: dict[str, LeadResponseDraft],
        sends: dict[str, LeadEmailSend],
        executions: dict[str, LeadFollowUpExecution],
    ) -> str | None:
        if kind == InboxTimelineKind.WEBSITE_ENQUIRY:
            return lead.enquiry
        if kind in _DRAFT_KINDS:
            draft = drafts.get(entity_id)
            return draft.current_response if draft is not None else None
        if kind in {
            InboxTimelineKind.EMAIL_SENT,
            InboxTimelineKind.EMAIL_FAILED,
        }:
            send = sends.get(entity_id)
            return send.body_text if send is not None else None
        if kind in {
            InboxTimelineKind.FOLLOW_UP_EXECUTION_SENT,
            InboxTimelineKind.FOLLOW_UP_EXECUTION_FAILED,
        }:
            execution = executions.get(entity_id)
            return execution.body_text if execution is not None else None
        return None

    def _direction(self, kind: InboxTimelineKind) -> InboxDirection:
        if kind in _INBOUND_KINDS:
            return InboxDirection.inbound
        if kind in _OUTBOUND_KINDS:
            return InboxDirection.outbound
        return InboxDirection.internal
