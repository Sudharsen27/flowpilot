import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.ai.provider import AIProvider
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    UnprocessableError,
    ValidationError,
)
from app.email.provider import EmailProvider
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.agent import EXECUTABLE_AGENT_STATUSES, Agent, AgentStatus, AgentType
from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpType
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.sales_run import (
    CANCELLABLE_SALES_RUN_STATUSES,
    SalesRun,
    SalesRunStage,
    SalesRunStatus,
)
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.lead_response_draft_repository import LeadResponseDraftRepository
from app.repositories.sales_run_repository import (
    SALES_RUN_LIST_DEFAULT_LIMIT,
    SALES_RUN_LIST_MAX_LIMIT,
    SalesRunRepository,
)
from app.schemas.sales_run import (
    SalesRunDraftSummary,
    SalesRunEmailSendSummary,
    SalesRunFollowUpSummary,
    SalesRunLeadSummary,
    SalesRunListResponse,
    SalesRunPublic,
    SalesRunQualificationSummary,
)
from app.services.activity_service import ActivityService
from app.services.agent_service import AgentService
from app.services.lead_email_send_service import LeadEmailSendService
from app.services.lead_follow_up_service import LeadFollowUpService, to_follow_up_public
from app.services.lead_qualification_service import LeadQualificationService
from app.services.lead_response_draft_service import LeadResponseDraftService
from app.services.lead_service import LeadService

logger = logging.getLogger(__name__)

STALE_SALES_RUN_MESSAGE = "This sales run did not finish and was marked failed."
OPEN_RUN_DETAIL = (
    "This lead already has an open sales run. Cancel it or wait for review "
    "before starting another."
)


class SalesRunService:
    def __init__(
        self,
        session: Session,
        provider: AIProvider | None = None,
        email_provider: EmailProvider | None = None,
        *,
        stale_timeout_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.email_provider = email_provider
        self._stale_timeout_seconds = stale_timeout_seconds
        self.agents = AgentService(session)
        self.leads = LeadService(session)
        self.lead_rows = LeadRepository(session)
        self.drafts = LeadResponseDraftRepository(session)
        self.sends = LeadEmailSendRepository(session)
        self.sales_runs = SalesRunRepository(session)

    def start_sales_run(
        self,
        *,
        organization_id: str,
        agent_id: str,
        enquiry: str,
        initiated_by_user_id: str | None,
        lead_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
    ) -> SalesRunPublic:
        agent = self._require_executable_sales_agent(organization_id, agent_id)
        self.recover_stale_running(
            organization_id=organization_id,
            agent_id=agent.id,
        )
        lead = self._resolve_lead(
            organization_id=organization_id,
            lead_id=lead_id,
            name=name,
            email=email,
        )
        existing = self.sales_runs.find_open_for_lead(organization_id, lead.id)
        if existing is not None:
            raise ConflictError(
                OPEN_RUN_DETAIL,
                content={
                    "detail": OPEN_RUN_DETAIL,
                    "sales_run_id": existing.id,
                    "status": existing.status,
                    "lead_id": lead.id,
                },
            )

        now = datetime.now(UTC)
        row = SalesRun(
            organization_id=organization_id,
            agent_id=agent.id,
            lead_id=lead.id,
            enquiry=enquiry,
            status=SalesRunStatus.RUNNING,
            stage=SalesRunStage.MATCH_LEAD,
            initiated_by_user_id=initiated_by_user_id,
            revision=1,
            started_at=now,
        )
        self.sales_runs.add(row)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            open_run = self.sales_runs.find_open_for_lead(organization_id, lead.id)
            if open_run is not None:
                raise ConflictError(
                    OPEN_RUN_DETAIL,
                    content={
                        "detail": OPEN_RUN_DETAIL,
                        "sales_run_id": open_run.id,
                        "status": open_run.status,
                        "lead_id": lead.id,
                    },
                ) from exc
            raise
        self.session.refresh(row)
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.AI_ACTION,
            actor_type=ActivityActorType.AGENT,
            title="Sales Agent started",
            summary="A Sales Agent run started for this lead.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=row.id,
            lead_id=row.lead_id,
            agent_id=row.agent_id,
            actor_user_id=initiated_by_user_id,
            status=SalesRunStatus.RUNNING,
            dedupe_key=f"sales_run:{row.id}:STARTED",
        )
        self.session.commit()
        logger.info(
            "sales_run_started sales_run_id=%s agent_id=%s lead_id=%s",
            row.id,
            agent.id,
            lead.id,
        )
        return self._run_pipeline(row, enquiry=enquiry, initiated_by_user_id=initiated_by_user_id)

    def start_for_lead(
        self,
        *,
        organization_id: str,
        lead_id: str,
        agent_id: str,
        enquiry: str,
        initiated_by_user_id: str | None,
    ) -> SalesRunPublic:
        self.leads.get_or_raise(organization_id, lead_id)
        return self.start_sales_run(
            organization_id=organization_id,
            agent_id=agent_id,
            enquiry=enquiry,
            lead_id=lead_id,
            initiated_by_user_id=initiated_by_user_id,
        )

    def get_for_agent(
        self, organization_id: str, agent_id: str, sales_run_id: str
    ) -> SalesRunPublic:
        self._require_sales_agent(organization_id, agent_id)
        self.recover_stale_running(
            organization_id=organization_id,
            agent_id=agent_id,
            sales_run_id=sales_run_id,
        )
        row = self.sales_runs.get_for_agent(organization_id, agent_id, sales_run_id)
        if row is None:
            raise NotFoundError("Sales run not found")
        return self._to_public(row, include_enquiry=True)

    def list_for_agent(
        self,
        organization_id: str,
        agent_id: str,
        *,
        limit: int = SALES_RUN_LIST_DEFAULT_LIMIT,
        offset: int = 0,
        status: SalesRunStatus | None = None,
        stage: SalesRunStage | None = None,
    ) -> SalesRunListResponse:
        self._require_sales_agent(organization_id, agent_id)
        self.recover_stale_running(organization_id=organization_id, agent_id=agent_id)
        capped = min(max(limit, 1), SALES_RUN_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.sales_runs.list_for_agent(
            organization_id,
            agent_id,
            limit=capped,
            offset=safe_offset,
            status=status,
            stage=stage,
        )
        return SalesRunListResponse(
            items=self._to_public_many(items, include_enquiry=False),
            limit=capped,
            offset=safe_offset,
            total=total,
        )

    def list_for_lead(
        self,
        organization_id: str,
        lead_id: str,
        *,
        limit: int = SALES_RUN_LIST_DEFAULT_LIMIT,
        offset: int = 0,
        status: SalesRunStatus | None = None,
        stage: SalesRunStage | None = None,
    ) -> SalesRunListResponse:
        self.leads.get_or_raise(organization_id, lead_id)
        self.recover_stale_running(organization_id=organization_id)
        capped = min(max(limit, 1), SALES_RUN_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.sales_runs.list_for_lead(
            organization_id,
            lead_id,
            limit=capped,
            offset=safe_offset,
            status=status,
            stage=stage,
        )
        return SalesRunListResponse(
            items=self._to_public_many(items, include_enquiry=False),
            limit=capped,
            offset=safe_offset,
            total=total,
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = SALES_RUN_LIST_DEFAULT_LIMIT,
        offset: int = 0,
        status: SalesRunStatus | None = None,
        stage: SalesRunStage | None = None,
    ) -> SalesRunListResponse:
        self.recover_stale_running(organization_id=organization_id)
        capped = min(max(limit, 1), SALES_RUN_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.sales_runs.list_for_organization(
            organization_id,
            limit=capped,
            offset=safe_offset,
            status=status,
            stage=stage,
        )
        return SalesRunListResponse(
            items=self._to_public_many(items, include_enquiry=False),
            limit=capped,
            offset=safe_offset,
            total=total,
            status_counts=self.sales_runs.status_counts(organization_id),
        )

    def cancel(
        self,
        *,
        organization_id: str,
        agent_id: str,
        sales_run_id: str,
        expected_revision: int,
    ) -> SalesRunPublic:
        self._require_sales_agent(organization_id, agent_id)
        row = self.sales_runs.get_for_agent(organization_id, agent_id, sales_run_id)
        if row is None:
            raise NotFoundError("Sales run not found")
        if row.revision != expected_revision:
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        if row.status not in {status.value for status in CANCELLABLE_SALES_RUN_STATUSES}:
            raise ConflictError("This sales run cannot be cancelled in its current status")
        now = datetime.now(UTC)
        updated = self.sales_runs.update_if_status(
            organization_id,
            sales_run_id,
            from_statuses=tuple(CANCELLABLE_SALES_RUN_STATUSES),
            expected_revision=expected_revision,
            increment_revision=True,
            values={
                "status": SalesRunStatus.CANCELLED,
                "completed_at": now,
                "updated_at": now,
            },
        )
        if updated == 0:
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        cancelled = self.sales_runs.get_for_agent(organization_id, agent_id, sales_run_id)
        if cancelled is None:
            raise NotFoundError("Sales run not found")
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            title="Sales Run cancelled",
            summary="A Sales Agent run was cancelled.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=cancelled.id,
            lead_id=cancelled.lead_id,
            agent_id=cancelled.agent_id,
            status=SalesRunStatus.CANCELLED,
            dedupe_key=f"sales_run:{cancelled.id}:CANCELLED",
        )
        self.session.commit()
        logger.info(
            "sales_run_cancelled sales_run_id=%s agent_id=%s lead_id=%s",
            cancelled.id,
            cancelled.agent_id,
            cancelled.lead_id,
        )
        return self._to_public(cancelled, include_enquiry=True)

    def cancel_waiting_for_rejected_draft(
        self,
        *,
        organization_id: str,
        lead_id: str,
        draft_id: str,
    ) -> SalesRun | None:
        """Cancel a WAITING_APPROVAL SalesRun linked to a rejected draft.

        Does not commit — intended to share the reject() transaction.
        Standalone drafts (no waiting linked run) are a no-op.
        """
        now = datetime.now(UTC)
        cancelled = self.sales_runs.cancel_waiting_for_draft(
            organization_id,
            lead_id=lead_id,
            draft_id=draft_id,
            now=now,
        )
        if cancelled is None:
            return None
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            title="Sales Run cancelled",
            summary="A Sales Agent run was cancelled.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=cancelled.id,
            lead_id=cancelled.lead_id,
            agent_id=cancelled.agent_id,
            status=SalesRunStatus.CANCELLED,
            dedupe_key=f"sales_run:{cancelled.id}:CANCELLED",
        )
        logger.info(
            "sales_run_cancelled_on_draft_reject sales_run_id=%s agent_id=%s "
            "lead_id=%s draft_id=%s",
            cancelled.id,
            cancelled.agent_id,
            cancelled.lead_id,
            draft_id,
        )
        return cancelled

    def send_approved_response(
        self,
        *,
        organization_id: str,
        agent_id: str,
        sales_run_id: str,
        expected_revision: int,
        initiated_by_user_id: str | None,
    ) -> SalesRunPublic:
        self._require_sales_agent(organization_id, agent_id)
        row = self.sales_runs.get_for_agent(organization_id, agent_id, sales_run_id)
        if row is None:
            raise NotFoundError("Sales run not found")
        if row.revision != expected_revision:
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        if not _can_send(row):
            raise ConflictError("This sales run cannot send in its current status")
        if not row.response_draft_id:
            raise ConflictError("This sales run has no response draft to send.")

        draft = self.drafts.get_by_id(organization_id, row.lead_id, row.response_draft_id)
        if draft is None:
            raise ConflictError("This sales run has no response draft to send.")
        if (
            draft.status != LeadResponseDraftStatus.COMPLETED
            or draft.review_status != LeadResponseReviewStatus.APPROVED
            or not (draft.current_response or "").strip()
        ):
            raise ConflictError("This draft is not approved for sending.")

        lead = self.leads.get_or_raise(organization_id, row.lead_id)
        if not lead.email:
            raise UnprocessableError("This lead has no email address.")

        now = datetime.now(UTC)
        claimed = self.sales_runs.update_if_status(
            organization_id,
            sales_run_id,
            from_statuses=_sendable_statuses(row),
            expected_revision=expected_revision,
            increment_revision=False,
            values={"stage": SalesRunStage.SEND, "updated_at": now},
        )
        if claimed == 0:
            raise ConflictError("This sales run changed. Refresh and review the latest status.")

        try:
            send_row = LeadEmailSendService(self.session, self.email_provider).send(
                organization_id=organization_id,
                lead_id=row.lead_id,
                draft_id=row.response_draft_id,
                initiated_by_user_id=initiated_by_user_id,
            )
        except ConflictError as exc:
            if _conflict_is_already_sent(exc):
                send_id = _id_from_content(exc.content, "id")
                if send_id is None:
                    raise
                return self._complete_after_sent(
                    row,
                    email_send_id=send_id,
                    expected_revision=expected_revision,
                )
            raise
        except UnprocessableError:
            raise
        except (ProviderError, ProviderNotConfiguredError) as exc:
            return self._fail_send(
                row,
                exc,
                expected_revision=expected_revision,
            )

        return self._complete_after_sent(
            row,
            email_send_id=send_row.id,
            expected_revision=expected_revision,
        )

    def schedule_follow_up(
        self,
        *,
        organization_id: str,
        agent_id: str,
        sales_run_id: str,
        expected_revision: int,
        due_at: datetime,
        follow_up_type: LeadFollowUpType,
        notes: str | None,
        body_text: str | None,
        initiated_by_user_id: str | None,
    ) -> SalesRunPublic:
        self._require_sales_agent(organization_id, agent_id)
        row = self.sales_runs.get_for_agent(organization_id, agent_id, sales_run_id)
        if row is None:
            raise NotFoundError("Sales run not found")
        if row.follow_up_id:
            return self._to_public(row, include_enquiry=True)
        if row.revision != expected_revision:
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        if row.status != SalesRunStatus.COMPLETED or row.stage != SalesRunStage.DONE:
            raise ConflictError(
                "This sales run cannot schedule a follow-up in its current status"
            )
        if not row.email_send_id:
            raise ConflictError("This sales run has no sent email to follow up.")
        send = self.sends.get_by_id(organization_id, row.email_send_id)
        if send is None or send.lead_id != row.lead_id:
            raise ConflictError("This sales run has no sent email to follow up.")
        if send.status == LeadEmailSendStatus.PENDING:
            raise ConflictError("A send is already in progress.")
        if send.status != LeadEmailSendStatus.SENT:
            raise ConflictError("This sales run has no sent email to follow up.")

        created = LeadFollowUpService(self.session).create(
            organization_id=organization_id,
            lead_id=row.lead_id,
            due_at=due_at,
            follow_up_type=follow_up_type,
            notes=notes,
            body_text=body_text,
            email_send_id=row.email_send_id,
            initiated_by_user_id=initiated_by_user_id,
        )
        orphan_id = created.id
        orphan_lead_id = created.lead_id
        orphan_revision = created.revision
        now = datetime.now(UTC)
        try:
            linked = self.sales_runs.link_follow_up_if_unset(
                organization_id,
                sales_run_id,
                follow_up_id=created.id,
                expected_revision=expected_revision,
                updated_at=now,
            )
        except IntegrityError:
            self.session.rollback()
            linked = 0
        current = self._reload(row)
        if linked == 0:
            self._cancel_orphan_follow_up(
                organization_id=organization_id,
                lead_id=orphan_lead_id,
                follow_up_id=orphan_id,
                expected_revision=orphan_revision,
            )
            current = self._reload(row)
            if current.follow_up_id:
                return self._to_public(current, include_enquiry=True)
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        logger.info(
            "sales_run_follow_up_scheduled sales_run_id=%s follow_up_id=%s lead_id=%s",
            current.id,
            current.follow_up_id,
            current.lead_id,
        )
        return self._to_public(current, include_enquiry=True)

    def recover_stale_running(
        self,
        *,
        organization_id: str,
        agent_id: str | None = None,
        sales_run_id: str | None = None,
    ) -> int:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self._effective_stale_timeout_seconds())
        recovered = self.sales_runs.recover_stale_running(
            organization_id,
            cutoff=cutoff,
            agent_id=agent_id,
            sales_run_id=sales_run_id,
            values={
                "status": SalesRunStatus.FAILED,
                "error": STALE_SALES_RUN_MESSAGE,
                "failure_category": ExecutionFailureCategory.EXECUTION_ERROR,
                "completed_at": now,
                "updated_at": now,
            },
        )
        if recovered:
            logger.info(
                "sales_run_stale_recovered count=%s organization_id=%s agent_id=%s",
                recovered,
                organization_id,
                agent_id,
            )
        return recovered

    def _complete_after_sent(
        self,
        row: SalesRun,
        *,
        email_send_id: str,
        expected_revision: int,
    ) -> SalesRunPublic:
        now = datetime.now(UTC)
        updated = self.sales_runs.update_if_status(
            row.organization_id,
            row.id,
            from_statuses=(SalesRunStatus.WAITING_APPROVAL, SalesRunStatus.FAILED),
            expected_revision=expected_revision,
            increment_revision=True,
            values={
                "status": SalesRunStatus.COMPLETED,
                "stage": SalesRunStage.DONE,
                "email_send_id": email_send_id,
                "completed_at": now,
                "updated_at": now,
                "error": None,
                "failure_category": None,
            },
        )
        current = self._reload(row)
        if updated == 0:
            if current.status == SalesRunStatus.COMPLETED:
                return self._to_public(current, include_enquiry=True)
            raise ConflictError("This sales run changed. Refresh and review the latest status.")
        logger.info(
            "sales_run_completed sales_run_id=%s agent_id=%s lead_id=%s email_send_id=%s",
            current.id,
            current.agent_id,
            current.lead_id,
            current.email_send_id,
        )
        ActivityService(self.session).record(
            organization_id=current.organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            title="Sales Run completed",
            summary="A Sales Agent run finished after the approved response was sent.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=current.id,
            lead_id=current.lead_id,
            agent_id=current.agent_id,
            status=SalesRunStatus.COMPLETED,
            dedupe_key=f"sales_run:{current.id}:COMPLETED",
        )
        self.session.commit()
        return self._to_public(current, include_enquiry=True)

    def _fail_send(
        self,
        row: SalesRun,
        exc: ProviderError | ProviderNotConfiguredError,
        *,
        expected_revision: int,
    ) -> SalesRunPublic:
        now = datetime.now(UTC)
        email_send_id = _id_from_content(exc.content, "id")
        error = sanitize_provider_error(exc.detail)
        category = _failure_category(exc.content)
        values: dict[str, Any] = {
            "status": SalesRunStatus.FAILED,
            "stage": SalesRunStage.SEND,
            "error": error,
            "failure_category": category,
            "completed_at": now,
            "updated_at": now,
        }
        if email_send_id:
            values["email_send_id"] = email_send_id
        self.sales_runs.update_if_status(
            row.organization_id,
            row.id,
            from_statuses=(SalesRunStatus.WAITING_APPROVAL, SalesRunStatus.FAILED),
            expected_revision=expected_revision,
            increment_revision=True,
            values=values,
        )
        failed = self._reload(row)
        logger.info(
            "sales_run_send_failed sales_run_id=%s agent_id=%s lead_id=%s category=%s",
            failed.id,
            failed.agent_id,
            failed.lead_id,
            failed.failure_category,
        )
        ActivityService(self.session).record(
            organization_id=failed.organization_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title="Sales Run failed",
            summary="A Sales Agent run failed while sending email.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=failed.id,
            lead_id=failed.lead_id,
            agent_id=failed.agent_id,
            status=SalesRunStatus.FAILED,
            dedupe_key=f"sales_run:{failed.id}:FAILED",
        )
        self.session.commit()
        payload = self._to_public(failed, include_enquiry=True).model_dump(mode="json")
        payload["detail"] = error
        raise type(exc)(error, content=payload)

    def _run_pipeline(
        self,
        row: SalesRun,
        *,
        enquiry: str,
        initiated_by_user_id: str | None,
    ) -> SalesRunPublic:
        self._set_stage_if_running(row, SalesRunStage.QUALIFY)
        current = self._reload(row)
        if current.status != SalesRunStatus.RUNNING:
            return self._to_public(current, include_enquiry=True)

        try:
            qualification = LeadQualificationService(self.session, self.provider).qualify(
                organization_id=row.organization_id,
                lead_id=row.lead_id,
                enquiry=enquiry,
                initiated_by_user_id=initiated_by_user_id,
            )
        except (ProviderError, ProviderNotConfiguredError) as exc:
            return self._handle_provider_failure(
                row,
                exc,
                qualification_id=_id_from_content(exc.content, "qualification_id"),
            )

        self._persist_links(row, qualification_id=qualification.id)
        current = self._reload(row)
        if current.status != SalesRunStatus.RUNNING:
            return self._to_public(current, include_enquiry=True)

        self._set_stage_if_running(row, SalesRunStage.DRAFT)
        current = self._reload(row)
        if current.status != SalesRunStatus.RUNNING:
            return self._to_public(current, include_enquiry=True)

        try:
            draft = LeadResponseDraftService(self.session, self.provider).generate(
                organization_id=row.organization_id,
                lead_id=row.lead_id,
                enquiry=enquiry,
                initiated_by_user_id=initiated_by_user_id,
            )
        except (ProviderError, ProviderNotConfiguredError) as exc:
            return self._handle_provider_failure(
                row,
                exc,
                qualification_id=qualification.id,
                response_draft_id=_id_from_content(exc.content, "draft_id"),
            )

        now = datetime.now(UTC)
        updated = self.sales_runs.update_if_status(
            row.organization_id,
            row.id,
            from_statuses=(SalesRunStatus.RUNNING,),
            increment_revision=True,
            values={
                "status": SalesRunStatus.WAITING_APPROVAL,
                "stage": SalesRunStage.AWAIT_APPROVAL,
                "response_draft_id": draft.id,
                "qualification_id": qualification.id,
                "updated_at": now,
                "error": None,
                "failure_category": None,
            },
        )
        current = self._reload(row)
        if updated == 0:
            return self._to_public(current, include_enquiry=True)
        logger.info(
            "sales_run_waiting_approval sales_run_id=%s agent_id=%s lead_id=%s",
            current.id,
            current.agent_id,
            current.lead_id,
        )
        ActivityService(self.session).record(
            organization_id=current.organization_id,
            event_type=ActivityEventType.AI_ACTION,
            actor_type=ActivityActorType.AGENT,
            title="Waiting for review",
            summary="A Sales Agent run is waiting for a person to review the draft.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=current.id,
            lead_id=current.lead_id,
            agent_id=current.agent_id,
            status=SalesRunStatus.WAITING_APPROVAL,
            dedupe_key=f"sales_run:{current.id}:WAITING_APPROVAL",
        )
        self.session.commit()
        return self._to_public(current, include_enquiry=True)

    def _handle_provider_failure(
        self,
        row: SalesRun,
        exc: ProviderError | ProviderNotConfiguredError,
        *,
        qualification_id: str | None = None,
        response_draft_id: str | None = None,
    ) -> SalesRunPublic:
        current = self._reload(row)
        if current.status == SalesRunStatus.CANCELLED:
            self._persist_links(
                row,
                qualification_id=qualification_id,
                response_draft_id=response_draft_id,
            )
            cancelled = self._reload(row)
            return self._to_public(cancelled, include_enquiry=True)

        now = datetime.now(UTC)
        category = _failure_category(exc.content)
        error = sanitize_provider_error(exc.detail)
        values: dict[str, Any] = {
            "status": SalesRunStatus.FAILED,
            "error": error,
            "failure_category": category,
            "completed_at": now,
            "updated_at": now,
        }
        if qualification_id:
            values["qualification_id"] = qualification_id
        if response_draft_id:
            values["response_draft_id"] = response_draft_id
        self.sales_runs.update_if_status(
            row.organization_id,
            row.id,
            from_statuses=(SalesRunStatus.RUNNING,),
            increment_revision=True,
            values=values,
        )
        failed = self._reload(row)
        logger.info(
            "sales_run_failed sales_run_id=%s agent_id=%s lead_id=%s category=%s",
            failed.id,
            failed.agent_id,
            failed.lead_id,
            failed.failure_category,
        )
        ActivityService(self.session).record(
            organization_id=failed.organization_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title="Sales Run failed",
            summary="A Sales Agent run failed during qualification or drafting.",
            entity_type=ActivityEntityType.SALES_RUN,
            entity_id=failed.id,
            lead_id=failed.lead_id,
            agent_id=failed.agent_id,
            status=SalesRunStatus.FAILED,
            dedupe_key=f"sales_run:{failed.id}:FAILED",
        )
        self.session.commit()
        payload = self._to_public(failed, include_enquiry=True).model_dump(mode="json")
        payload["detail"] = error
        raise type(exc)(error, content=payload)

    def _set_stage_if_running(self, row: SalesRun, stage: SalesRunStage) -> None:
        now = datetime.now(UTC)
        self.sales_runs.update_if_status(
            row.organization_id,
            row.id,
            from_statuses=(SalesRunStatus.RUNNING,),
            increment_revision=False,
            values={"stage": stage, "updated_at": now},
        )

    def _persist_links(
        self,
        row: SalesRun,
        *,
        qualification_id: str | None = None,
        response_draft_id: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        self.sales_runs.persist_links(
            row.organization_id,
            row.id,
            qualification_id=qualification_id,
            response_draft_id=response_draft_id,
            updated_at=now,
        )

    def _reload(self, row: SalesRun) -> SalesRun:
        loaded = self.sales_runs.get_by_id(row.organization_id, row.id)
        if loaded is None:
            raise NotFoundError("Sales run not found")
        return loaded

    def _cancel_orphan_follow_up(
        self,
        *,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        expected_revision: int,
    ) -> None:
        try:
            LeadFollowUpService(self.session).cancel(
                organization_id=organization_id,
                lead_id=lead_id,
                follow_up_id=follow_up_id,
                expected_revision=expected_revision,
            )
        except ConflictError:
            logger.info(
                "sales_run_follow_up_orphan_not_cancelled follow_up_id=%s",
                follow_up_id,
            )

    def _resolve_lead(
        self,
        *,
        organization_id: str,
        lead_id: str | None,
        name: str | None,
        email: str | None,
    ) -> Lead:
        if lead_id:
            return self.leads.get_or_raise(organization_id, lead_id)
        if email:
            matches = self.lead_rows.list_by_email(organization_id, email)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                detail = "Multiple leads match this email. Provide lead_id to continue."
                raise ConflictError(
                    detail,
                    content={
                        "detail": detail,
                        "matching_lead_ids": [item.id for item in matches],
                    },
                )
        if not name:
            raise UnprocessableError("Name is required to create a lead")
        return self.leads.create(
            organization_id=organization_id,
            name=name,
            email=email,
            source=LeadSource.API,
            initiated_by_user_id=None,
        )

    def _require_sales_agent(self, organization_id: str, agent_id: str) -> Agent:
        agent = self.agents.get_or_raise(organization_id, agent_id)
        if agent.agent_type != AgentType.SALES:
            raise UnprocessableError("Sales runs can only be started for SALES agents")
        return agent

    def _require_executable_sales_agent(self, organization_id: str, agent_id: str) -> Agent:
        agent = self._require_sales_agent(organization_id, agent_id)
        if AgentStatus(agent.status) not in EXECUTABLE_AGENT_STATUSES:
            raise ValidationError(
                f"Agent cannot start a sales run while status is {agent.status}"
            )
        return agent

    def _effective_stale_timeout_seconds(self) -> float:
        if self._stale_timeout_seconds is not None:
            return self._stale_timeout_seconds
        return settings.sales_run_stale_timeout_effective_seconds()

    def _to_public(self, row: SalesRun, *, include_enquiry: bool) -> SalesRunPublic:
        return self._to_public_many([row], include_enquiry=include_enquiry)[0]

    def _to_public_many(
        self, rows: list[SalesRun], *, include_enquiry: bool
    ) -> list[SalesRunPublic]:
        if not rows:
            return []
        organization_id = rows[0].organization_id
        lead_ids = {row.lead_id for row in rows}
        leads = {
            lead.id: lead
            for lead in self.session.scalars(
                select(Lead).where(
                    Lead.organization_id == organization_id,
                    Lead.id.in_(lead_ids),
                )
            )
        }
        qualification_ids = [row.qualification_id for row in rows if row.qualification_id]
        draft_ids = [row.response_draft_id for row in rows if row.response_draft_id]
        send_ids = [row.email_send_id for row in rows if row.email_send_id]
        follow_up_ids = [row.follow_up_id for row in rows if row.follow_up_id]
        qualifications: dict[str, LeadQualification] = {}
        if qualification_ids:
            for qualification_row in self.session.scalars(
                select(LeadQualification).where(
                    LeadQualification.organization_id == organization_id,
                    LeadQualification.id.in_(qualification_ids),
                )
            ):
                qualifications[qualification_row.id] = qualification_row
        drafts: dict[str, LeadResponseDraft] = {}
        if draft_ids:
            for draft_row in self.session.scalars(
                select(LeadResponseDraft).where(
                    LeadResponseDraft.organization_id == organization_id,
                    LeadResponseDraft.id.in_(draft_ids),
                )
            ):
                drafts[draft_row.id] = draft_row
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
        return [
            _public_from_row(
                row,
                lead=leads.get(row.lead_id),
                qualification=(
                    qualifications.get(row.qualification_id) if row.qualification_id else None
                ),
                draft=drafts.get(row.response_draft_id) if row.response_draft_id else None,
                email_send=sends.get(row.email_send_id) if row.email_send_id else None,
                follow_up=follow_ups.get(row.follow_up_id) if row.follow_up_id else None,
                include_enquiry=include_enquiry,
            )
            for row in rows
        ]


def _public_from_row(
    row: SalesRun,
    *,
    lead: Lead | None,
    qualification: LeadQualification | None,
    draft: LeadResponseDraft | None,
    email_send: LeadEmailSend | None,
    follow_up: LeadFollowUp | None,
    include_enquiry: bool,
) -> SalesRunPublic:
    category = None
    if row.failure_category:
        category = ExecutionFailureCategory(row.failure_category)
    return SalesRunPublic(
        id=row.id,
        agent_id=row.agent_id,
        lead_id=row.lead_id,
        status=SalesRunStatus(row.status),
        stage=SalesRunStage(row.stage),
        qualification_id=row.qualification_id,
        response_draft_id=row.response_draft_id,
        email_send_id=row.email_send_id,
        follow_up_id=row.follow_up_id,
        failure_category=category,
        error=row.error,
        initiated_by_user_id=row.initiated_by_user_id,
        revision=row.revision,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        enquiry=row.enquiry if include_enquiry else None,
        lead=(
            SalesRunLeadSummary(
                id=lead.id,
                name=lead.name,
                email=lead.email,
                status=LeadStatus(lead.status),
            )
            if lead is not None
            else None
        ),
        qualification=(
            SalesRunQualificationSummary(id=qualification.id, status=qualification.status)
            if qualification is not None
            else None
        ),
        response_draft=(
            SalesRunDraftSummary(
                id=draft.id,
                status=draft.status,
                review_status=(
                    LeadResponseReviewStatus(draft.review_status) if draft.review_status else None
                ),
            )
            if draft is not None
            else None
        ),
        email_send=_email_send_summary(email_send),
        follow_up=_follow_up_summary(follow_up),
    )


def _follow_up_summary(row: LeadFollowUp | None) -> SalesRunFollowUpSummary | None:
    if row is None:
        return None
    public = to_follow_up_public(row)
    return SalesRunFollowUpSummary(
        id=public.id,
        type=public.type,
        status=public.status,
        due_at=public.due_at,
        is_overdue=public.is_overdue,
    )


def _email_send_summary(row: LeadEmailSend | None) -> SalesRunEmailSendSummary | None:
    if row is None:
        return None
    category = None
    if row.failure_category:
        category = ExecutionFailureCategory(row.failure_category)
    return SalesRunEmailSendSummary(
        id=row.id,
        status=row.status,
        recipient_email=row.recipient_email,
        provider=row.provider,
        provider_message_id=row.provider_message_id,
        draft_revision=row.draft_revision,
        failure_category=category,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _can_send(row: SalesRun) -> bool:
    if row.status == SalesRunStatus.WAITING_APPROVAL:
        return True
    return _is_retryable_send_failure(row)


def _sendable_statuses(row: SalesRun) -> tuple[SalesRunStatus, ...]:
    if _is_retryable_send_failure(row):
        return (SalesRunStatus.WAITING_APPROVAL, SalesRunStatus.FAILED)
    return (SalesRunStatus.WAITING_APPROVAL,)


def _is_retryable_send_failure(row: SalesRun) -> bool:
    return (
        row.status == SalesRunStatus.FAILED
        and row.stage == SalesRunStage.SEND
        and bool(row.response_draft_id)
    )


def _conflict_is_already_sent(exc: ConflictError) -> bool:
    status = exc.content.get("status") if exc.content else None
    if status == LeadEmailSendStatus.SENT:
        return True
    return "already sent" in exc.detail.lower()


def _id_from_content(content: dict[str, Any] | None, key: str) -> str | None:
    if not content:
        return None
    value = content.get(key)
    return value if isinstance(value, str) and value else None


def _failure_category(content: dict[str, Any] | None) -> ExecutionFailureCategory:
    if content:
        raw = content.get("failure_category")
        if isinstance(raw, ExecutionFailureCategory):
            return raw
        if isinstance(raw, str):
            try:
                return ExecutionFailureCategory(raw)
            except ValueError:
                pass
    return ExecutionFailureCategory.PROVIDER_ERROR
