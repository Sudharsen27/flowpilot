from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from app.repositories.lead_qualification_repository import LeadQualificationRepository
from app.repositories.lead_repository import (
    LEAD_LIST_DEFAULT_LIMIT,
    LEAD_LIST_MAX_LIMIT,
    LeadRepository,
)
from app.repositories.lead_response_draft_repository import LeadResponseDraftRepository
from app.repositories.sales_run_repository import SalesRunRepository
from app.schemas.lead_qualification import (
    LeadQualificationAnalysis,
    LeadQualificationPublic,
    LeadQualificationSummary,
)
from app.schemas.lead_response_draft import LeadResponseDraftSummary
from app.schemas.leads import LeadListResponse, LeadPublic, LeadUpdate
from app.schemas.sales_run import (
    LeadLatestSalesRunEmailSummary,
    LeadLatestSalesRunFollowUpSummary,
    LeadLatestSalesRunSummary,
)
from app.services.activity_service import ActivityService
from app.services.lead_follow_up_service import to_follow_up_public
from app.services.lead_qualification_service import usage_from_result
from app.services.observability import duration_ms


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_"})
    return cleaned or None


class LeadService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.qualifications = LeadQualificationRepository(session)
        self.response_drafts = LeadResponseDraftRepository(session)
        self.sales_runs = SalesRunRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        source: LeadSource = LeadSource.MANUAL,
        status: LeadStatus = LeadStatus.NEW,
        notes: str | None = None,
        enquiry: str | None = None,
        initiated_by_user_id: str | None = None,
        website_enquiry: bool = False,
    ) -> Lead:
        lead = Lead(
            organization_id=organization_id,
            name=name.strip(),
            email=email,
            phone=phone,
            company=company,
            source=source,
            status=status,
            notes=notes,
            enquiry=enquiry,
        )
        self.leads.add(lead)
        self.session.flush()
        if website_enquiry:
            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.SYSTEM_EVENT,
                actor_type=ActivityActorType.PUBLIC_VISITOR,
                title="Website enquiry received",
                summary="A website visitor submitted an enquiry and a lead was created.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead.id,
                lead_id=lead.id,
                status=lead.status,
                dedupe_key=f"lead:{lead.id}:WEBSITE_ENQUIRY",
            )
        else:
            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.HUMAN_ACTION,
                actor_type=(
                    ActivityActorType.USER if initiated_by_user_id else ActivityActorType.SYSTEM
                ),
                title="Lead created",
                summary="A lead record was created in this organization.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead.id,
                lead_id=lead.id,
                actor_user_id=initiated_by_user_id,
                status=lead.status,
                dedupe_key=f"lead:{lead.id}:CREATED",
            )
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def get(self, organization_id: str, lead_id: str) -> Lead | None:
        return self.leads.get_by_id(organization_id, lead_id)

    def get_or_raise(self, organization_id: str, lead_id: str) -> Lead:
        lead = self.get(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    def get_public(self, organization_id: str, lead_id: str) -> LeadPublic:
        return self._to_public(self.get_or_raise(organization_id, lead_id))

    def list(
        self,
        organization_id: str,
        *,
        status: LeadStatus | None = None,
        source: LeadSource | None = None,
        search: str | None = None,
        limit: int = LEAD_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> LeadListResponse:
        safe_limit = min(max(limit, 1), LEAD_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.leads.list_for_organization(
            organization_id,
            status=status,
            source=source,
            search=_sanitize_search(search),
            limit=safe_limit,
            offset=safe_offset,
        )
        raw_counts = self.leads.status_counts(organization_id)
        lead_ids = [item.id for item in items]
        latest = self.qualifications.latest_for_leads(organization_id, lead_ids)
        drafts = self.response_drafts.latest_completed_for_leads(organization_id, lead_ids)
        latest_runs = self.sales_runs.latest_for_leads(organization_id, lead_ids)
        sends, follow_ups = self._related_for_runs(
            organization_id, list(latest_runs.values())
        )
        return LeadListResponse(
            items=[
                self._to_public(
                    item,
                    latest.get(item.id),
                    drafts.get(item.id),
                    sales_run=latest_runs.get(item.id),
                    email_send=_send_for_run(latest_runs.get(item.id), sends),
                    follow_up=_follow_up_for_run(latest_runs.get(item.id), follow_ups),
                    hydrate=False,
                )
                for item in items
            ],
            limit=safe_limit,
            offset=safe_offset,
            total=total,
            status_counts={LeadStatus(key): value for key, value in raw_counts.items()},
        )

    def update(
        self,
        *,
        organization_id: str,
        lead_id: str,
        payload: LeadUpdate,
        initiated_by_user_id: str | None = None,
    ) -> Lead:
        lead = self.get_or_raise(organization_id, lead_id)
        previous_status = lead.status
        fields = payload.model_fields_set
        if "name" in fields and payload.name is not None:
            lead.name = payload.name.strip()
        if "email" in fields:
            lead.email = payload.email
        if "phone" in fields:
            lead.phone = payload.phone
        if "company" in fields:
            lead.company = payload.company
        if "source" in fields and payload.source is not None:
            lead.source = payload.source
        if "status" in fields and payload.status is not None:
            lead.status = payload.status
        if "notes" in fields:
            lead.notes = payload.notes
        if "enquiry" in fields:
            lead.enquiry = payload.enquiry
        lead.updated_at = datetime.now(UTC)
        if "status" in fields and payload.status is not None and payload.status != previous_status:
            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.HUMAN_ACTION,
                actor_type=(
                    ActivityActorType.USER if initiated_by_user_id else ActivityActorType.SYSTEM
                ),
                title="Lead status changed",
                summary="A lead CRM status was updated.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead.id,
                lead_id=lead.id,
                actor_user_id=initiated_by_user_id,
                status=payload.status,
                dedupe_key=f"lead:{lead.id}:STATUS:{payload.status}",
            )
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def _related_for_runs(
        self, organization_id: str, runs: Sequence[SalesRun]
    ) -> tuple[dict[str, LeadEmailSend], dict[str, LeadFollowUp]]:
        send_ids = [row.email_send_id for row in runs if row.email_send_id]
        follow_up_ids = [row.follow_up_id for row in runs if row.follow_up_id]
        sends: dict[str, LeadEmailSend] = {}
        if send_ids:
            for send_row in self.session.scalars(
                select(LeadEmailSend).where(
                    LeadEmailSend.organization_id == organization_id,
                    LeadEmailSend.id.in_(send_ids),
                )
            ):
                sends[send_row.id] = send_row
        follow_ups: dict[str, LeadFollowUp] = {}
        if follow_up_ids:
            for follow_up_row in self.session.scalars(
                select(LeadFollowUp).where(
                    LeadFollowUp.organization_id == organization_id,
                    LeadFollowUp.id.in_(follow_up_ids),
                )
            ):
                follow_ups[follow_up_row.id] = follow_up_row
        return sends, follow_ups

    def _to_public(
        self,
        lead: Lead,
        qualification: LeadQualification | None = None,
        draft: LeadResponseDraft | None = None,
        *,
        sales_run: SalesRun | None = None,
        email_send: LeadEmailSend | None = None,
        follow_up: LeadFollowUp | None = None,
        hydrate: bool = True,
    ) -> LeadPublic:
        if hydrate:
            if qualification is None:
                latest = self.qualifications.latest_for_leads(
                    lead.organization_id, [lead.id]
                )
                qualification = latest.get(lead.id)
            if draft is None:
                drafts = self.response_drafts.latest_completed_for_leads(
                    lead.organization_id, [lead.id]
                )
                draft = drafts.get(lead.id)
            if sales_run is None:
                latest_runs = self.sales_runs.latest_for_leads(
                    lead.organization_id, [lead.id]
                )
                sales_run = latest_runs.get(lead.id)
            if sales_run is not None and (email_send is None or follow_up is None):
                sends, follow_ups = self._related_for_runs(
                    lead.organization_id, [sales_run]
                )
                if email_send is None:
                    email_send = _send_for_run(sales_run, sends)
                if follow_up is None:
                    follow_up = _follow_up_for_run(sales_run, follow_ups)
        public = LeadPublic.model_validate(lead)
        return public.model_copy(
            update={
                "latest_qualification": _qualification_summary(qualification),
                "latest_response_draft": _draft_summary(draft),
                "latest_sales_run": _sales_run_summary(sales_run, email_send, follow_up),
            }
        )


def _qualification_summary(
    row: LeadQualification | None,
) -> LeadQualificationSummary | None:
    if row is None:
        return None
    analysis = None
    if (
        row.status == LeadQualificationRecordStatus.COMPLETED
        and isinstance(row.result, dict)
    ):
        payload = {key: value for key, value in row.result.items() if key != "usage"}
        try:
            analysis = LeadQualificationAnalysis.model_validate(payload)
        except ValueError:
            analysis = None
    return LeadQualificationSummary(
        id=row.id,
        status=row.status,
        qualification=analysis.qualification if analysis else None,
        confidence=analysis.confidence if analysis else None,
        created_at=row.created_at,
        error=row.error,
    )


def _send_for_run(
    run: SalesRun | None, sends: dict[str, LeadEmailSend]
) -> LeadEmailSend | None:
    if run is None or not run.email_send_id:
        return None
    return sends.get(run.email_send_id)


def _follow_up_for_run(
    run: SalesRun | None, follow_ups: dict[str, LeadFollowUp]
) -> LeadFollowUp | None:
    if run is None or not run.follow_up_id:
        return None
    return follow_ups.get(run.follow_up_id)


def _sales_run_summary(
    row: SalesRun | None,
    email_send: LeadEmailSend | None,
    follow_up: LeadFollowUp | None,
) -> LeadLatestSalesRunSummary | None:
    if row is None:
        return None
    follow_up_summary = None
    if follow_up is not None:
        public = to_follow_up_public(follow_up)
        follow_up_summary = LeadLatestSalesRunFollowUpSummary(
            status=public.status,
            due_at=public.due_at,
            is_overdue=public.is_overdue,
        )
    email_summary = None
    if email_send is not None:
        email_summary = LeadLatestSalesRunEmailSummary(
            status=email_send.status,
            completed_at=email_send.completed_at,
        )
    return LeadLatestSalesRunSummary(
        id=row.id,
        agent_id=row.agent_id,
        status=SalesRunStatus(row.status),
        stage=SalesRunStage(row.stage),
        email_send=email_summary,
        follow_up=follow_up_summary,
    )


def _draft_summary(row: LeadResponseDraft | None) -> LeadResponseDraftSummary | None:
    if row is None or row.status != LeadResponseDraftStatus.COMPLETED:
        return None
    return LeadResponseDraftSummary(
        id=row.id,
        status=row.status,
        review_status=(
            LeadResponseReviewStatus(row.review_status) if row.review_status else None
        ),
        created_at=row.created_at,
    )


def to_qualification_public(row: LeadQualification) -> LeadQualificationPublic:
    analysis = None
    usage = usage_from_result(row.result)
    if (
        row.status == LeadQualificationRecordStatus.COMPLETED
        and isinstance(row.result, dict)
    ):
        payload = {key: value for key, value in row.result.items() if key != "usage"}
        try:
            analysis = LeadQualificationAnalysis.model_validate(payload)
        except ValueError:
            analysis = None
    return LeadQualificationPublic(
        id=row.id,
        lead_id=row.lead_id,
        status=row.status,
        enquiry=row.enquiry,
        analysis=analysis,
        error=row.error,
        failure_category=row.failure_category,
        provider=row.provider,
        model=row.model,
        usage=usage,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        duration_ms=duration_ms(row.started_at, row.completed_at),
    )
