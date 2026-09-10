from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_follow_up_execution import (
    LeadFollowUpExecution,
    LeadFollowUpExecutionStatus,
)
from app.repositories.lead_follow_up_execution_repository import (
    LeadFollowUpExecutionRepository,
)
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead_follow_up_execution import (
    LeadFollowUpExecutionListResponse,
    LeadFollowUpExecutionPublic,
    LeadFollowUpExecutionSnapshot,
)
from app.services.observability import duration_ms

DUE_CLAIM_DEFAULT_LIMIT = 20
DUE_CLAIM_MAX_LIMIT = 50
STALE_RUNNING_ERROR = "Follow-up execution timed out"
FOLLOW_UP_EMAIL_SUBJECT = "Re: Your enquiry"


def provider_idempotency_key(follow_up_id: str, attempt: int) -> str:
    return f"follow-up:{follow_up_id}:attempt:{attempt}"


class LeadFollowUpExecutionService:
    def __init__(
        self,
        session: Session,
        *,
        stale_timeout_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.follow_ups = LeadFollowUpRepository(session)
        self.executions = LeadFollowUpExecutionRepository(session)
        self._stale_timeout_seconds = stale_timeout_seconds

    def create_attempt(
        self,
        *,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        snapshot: LeadFollowUpExecutionSnapshot,
        status: LeadFollowUpExecutionStatus = LeadFollowUpExecutionStatus.PENDING,
    ) -> LeadFollowUpExecution:
        follow_up = self._require_follow_up(organization_id, lead_id, follow_up_id)
        if self.executions.inflight_for_follow_up(organization_id, follow_up.id) is not None:
            raise ConflictError("This follow-up already has an in-flight execution")
        attempt = self.executions.next_attempt(organization_id, follow_up.id)
        now = datetime.now(UTC)
        row = LeadFollowUpExecution(
            organization_id=follow_up.organization_id,
            lead_id=follow_up.lead_id,
            follow_up_id=follow_up.id,
            status=status,
            attempt=attempt,
            recipient_email=snapshot.recipient_email,
            sender_email=snapshot.sender_email,
            subject=snapshot.subject,
            body_text=snapshot.body_text,
            started_at=now if status == LeadFollowUpExecutionStatus.RUNNING else None,
            created_at=now,
            updated_at=now,
        )
        self.executions.add(row)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("This follow-up already has an in-flight execution") from exc
        self.session.refresh(row)
        return row

    def get(
        self, organization_id: str, execution_id: str
    ) -> LeadFollowUpExecution:
        row = self.executions.get_by_id(organization_id, execution_id)
        if row is None:
            raise NotFoundError("Lead not found")
        return row

    def list_for_follow_up(
        self,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        *,
        limit: int = DUE_CLAIM_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> LeadFollowUpExecutionListResponse:
        follow_up = self._require_follow_up(organization_id, lead_id, follow_up_id)
        capped = min(max(limit, 1), DUE_CLAIM_MAX_LIMIT)
        items, total = self.executions.list_for_follow_up(
            organization_id,
            follow_up.id,
            limit=capped,
            offset=max(offset, 0),
        )
        return LeadFollowUpExecutionListResponse(
            items=[to_execution_public(row) for row in items],
            limit=capped,
            offset=max(offset, 0),
            total=total,
        )

    def list_due_email_follow_ups(
        self,
        *,
        as_of: datetime | None = None,
        limit: int = DUE_CLAIM_DEFAULT_LIMIT,
    ) -> list[LeadFollowUp]:
        capped = min(max(limit, 1), DUE_CLAIM_MAX_LIMIT)
        return self.follow_ups.list_due_email_follow_ups(
            as_of=as_of or datetime.now(UTC),
            limit=capped,
            for_update_skip_locked=False,
        )

    def claim_due_email_follow_up(
        self,
        *,
        as_of: datetime | None = None,
        limit: int = DUE_CLAIM_DEFAULT_LIMIT,
    ) -> LeadFollowUpExecution | None:
        """Lock a due EMAIL follow-up and persist a RUNNING execution, then commit.

        Does not call an email provider. The caller must commit is already done
        here so a future worker can send outside this transaction.
        """
        now = as_of or datetime.now(UTC)
        capped = min(max(limit, 1), DUE_CLAIM_MAX_LIMIT)
        candidates = self.follow_ups.list_due_email_follow_ups(
            as_of=now,
            limit=capped,
            for_update_skip_locked=True,
        )
        for follow_up in candidates:
            if not self.follow_up_still_sendable(follow_up):
                continue
            if self.executions.inflight_for_follow_up(
                follow_up.organization_id, follow_up.id
            ) is not None:
                continue
            snapshot = self._snapshot_for_follow_up(follow_up)
            if snapshot is None:
                continue
            try:
                row = self._new_running_row(follow_up, snapshot, now)
                self.executions.add(row)
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                continue
            self.session.refresh(row)
            return row
        self.session.commit()
        return None

    def follow_up_still_sendable(self, follow_up: LeadFollowUp) -> bool:
        self.session.refresh(follow_up)
        return (
            follow_up.status == LeadFollowUpStatus.PENDING
            and follow_up.type == LeadFollowUpType.EMAIL_FOLLOW_UP
            and bool(follow_up.body_text and follow_up.body_text.strip())
        )

    def reload_follow_up_for_send(
        self, organization_id: str, lead_id: str, follow_up_id: str
    ) -> LeadFollowUp | None:
        """Re-load the follow-up after claim commit, before any provider call."""
        row = self.follow_ups.get_by_id(organization_id, lead_id, follow_up_id)
        if row is None or not self.follow_up_still_sendable(row):
            return None
        return row

    def mark_running(self, organization_id: str, execution_id: str) -> LeadFollowUpExecution:
        now = datetime.now(UTC)
        updated = self.executions.mark_running(organization_id, execution_id, started_at=now)
        if updated != 1:
            raise ConflictError("This follow-up execution cannot be marked running")
        return self.get(organization_id, execution_id)

    def mark_sent(
        self,
        organization_id: str,
        execution_id: str,
        *,
        provider: str | None,
        provider_message_id: str | None,
    ) -> LeadFollowUpExecution:
        now = datetime.now(UTC)
        updated = self.executions.mark_sent(
            organization_id,
            execution_id,
            values={
                "status": LeadFollowUpExecutionStatus.SENT,
                "provider": provider,
                "provider_message_id": provider_message_id,
                "completed_at": now,
                "updated_at": now,
                "error": None,
                "failure_category": None,
            },
        )
        if updated != 1:
            raise ConflictError("This follow-up execution cannot be marked sent")
        return self.get(organization_id, execution_id)

    def mark_failed(
        self,
        organization_id: str,
        execution_id: str,
        *,
        error: str,
        category: ExecutionFailureCategory,
        provider: str | None = None,
    ) -> LeadFollowUpExecution:
        now = datetime.now(UTC)
        updated = self.executions.mark_failed(
            organization_id,
            execution_id,
            values={
                "status": LeadFollowUpExecutionStatus.FAILED,
                "error": sanitize_provider_error(error),
                "failure_category": category,
                "provider": provider,
                "completed_at": now,
                "updated_at": now,
            },
        )
        if updated != 1:
            raise ConflictError("This follow-up execution cannot be marked failed")
        return self.get(organization_id, execution_id)

    def recover_stale_running_executions(
        self,
        *,
        now: datetime | None = None,
        organization_id: str | None = None,
        execution_id: str | None = None,
    ) -> int:
        current = now or datetime.now(UTC)
        cutoff = current - timedelta(seconds=self._effective_stale_timeout_seconds())
        return self.executions.recover_stale_running(
            cutoff=cutoff,
            organization_id=organization_id,
            execution_id=execution_id,
            values={
                "status": LeadFollowUpExecutionStatus.FAILED,
                "error": sanitize_provider_error(STALE_RUNNING_ERROR),
                "failure_category": ExecutionFailureCategory.EXECUTION_ERROR,
                "completed_at": current,
                "updated_at": current,
            },
        )

    def _effective_stale_timeout_seconds(self) -> float:
        if self._stale_timeout_seconds is not None:
            return self._stale_timeout_seconds
        return settings.lead_follow_up_execution_stale_timeout_effective_seconds()

    def _require_follow_up(
        self, organization_id: str, lead_id: str, follow_up_id: str
    ) -> LeadFollowUp:
        if self.leads.get_by_id(organization_id, lead_id) is None:
            raise NotFoundError("Lead not found")
        row = self.follow_ups.get_by_id(organization_id, lead_id, follow_up_id)
        if row is None:
            raise NotFoundError("Lead not found")
        return row

    def _snapshot_for_follow_up(
        self, follow_up: LeadFollowUp
    ) -> LeadFollowUpExecutionSnapshot | None:
        lead = self.leads.get_by_id(follow_up.organization_id, follow_up.lead_id)
        if lead is None or not lead.email or not follow_up.body_text:
            return None
        sender = settings.email_from_address
        if not sender:
            return None
        return LeadFollowUpExecutionSnapshot(
            recipient_email=lead.email,
            sender_email=sender,
            subject=FOLLOW_UP_EMAIL_SUBJECT,
            body_text=follow_up.body_text,
        )

    def _new_running_row(
        self,
        follow_up: LeadFollowUp,
        snapshot: LeadFollowUpExecutionSnapshot,
        now: datetime,
    ) -> LeadFollowUpExecution:
        attempt = self.executions.next_attempt(follow_up.organization_id, follow_up.id)
        return LeadFollowUpExecution(
            organization_id=follow_up.organization_id,
            lead_id=follow_up.lead_id,
            follow_up_id=follow_up.id,
            status=LeadFollowUpExecutionStatus.RUNNING,
            attempt=attempt,
            recipient_email=snapshot.recipient_email,
            sender_email=snapshot.sender_email,
            subject=snapshot.subject,
            body_text=snapshot.body_text,
            started_at=now,
            created_at=now,
            updated_at=now,
        )


def to_execution_public(row: LeadFollowUpExecution) -> LeadFollowUpExecutionPublic:
    category = None
    if row.failure_category:
        category = ExecutionFailureCategory(row.failure_category)
    return LeadFollowUpExecutionPublic(
        id=row.id,
        lead_id=row.lead_id,
        follow_up_id=row.follow_up_id,
        status=LeadFollowUpExecutionStatus(row.status),
        attempt=row.attempt,
        recipient_email=row.recipient_email,
        sender_email=row.sender_email,
        subject=row.subject,
        body_text=row.body_text,
        provider=row.provider,
        provider_message_id=row.provider_message_id,
        failure_category=category,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        duration_ms=duration_ms(row.started_at, row.completed_at),
        provider_idempotency_key=provider_idempotency_key(row.follow_up_id, row.attempt),
    )
