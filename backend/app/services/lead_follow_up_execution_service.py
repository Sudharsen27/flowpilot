import logging
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
)
from app.email.headers import safe_header, safe_optional_name
from app.email.provider import EmailMessage, EmailProvider
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

logger = logging.getLogger(__name__)

DUE_CLAIM_DEFAULT_LIMIT = 20
DUE_CLAIM_MAX_LIMIT = 50
STALE_RUNNING_ERROR = "Follow-up execution timed out"
FOLLOW_UP_EMAIL_SUBJECT = "Re: Your enquiry"
UNCONFIGURED_SENDER = "unconfigured@localhost"


def provider_idempotency_key(follow_up_id: str, attempt: int) -> str:
    return f"follow-up:{follow_up_id}:attempt:{attempt}"


class LeadFollowUpExecutionService:
    def __init__(
        self,
        session: Session,
        *,
        provider: EmailProvider | None = None,
        stale_timeout_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
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
            claimed = self._claim_locked_follow_up(follow_up, now)
            if claimed is not None:
                return claimed
        self.session.commit()
        return None

    def claim_email_follow_up(
        self,
        *,
        organization_id: str,
        follow_up_id: str,
        as_of: datetime | None = None,
    ) -> LeadFollowUpExecution | None:
        now = as_of or datetime.now(UTC)
        follow_up = self.follow_ups.lock_due_email_follow_up(
            organization_id,
            follow_up_id,
            as_of=now,
            for_update_skip_locked=True,
        )
        if follow_up is None:
            self.session.commit()
            return None
        claimed = self._claim_locked_follow_up(follow_up, now)
        if claimed is None:
            self.session.commit()
        return claimed

    def execute_next_due_email_follow_up(
        self, *, as_of: datetime | None = None
    ) -> LeadFollowUpExecution | None:
        """Claim one due EMAIL follow-up and deliver it. Not a worker loop."""
        claimed = self.claim_due_email_follow_up(as_of=as_of)
        if claimed is None:
            return None
        return self.deliver_claimed_execution(
            organization_id=claimed.organization_id,
            execution_id=claimed.id,
        )

    def execute_follow_up(
        self,
        *,
        organization_id: str,
        follow_up_id: str,
    ) -> LeadFollowUpExecution | None:
        """Execute one tenant-scoped follow-up. MANUAL and terminal rows are skipped."""
        follow_up = self.follow_ups.get_by_organization_id(organization_id, follow_up_id)
        if follow_up is None:
            raise NotFoundError("Lead not found")
        if follow_up.organization_id != organization_id:
            raise NotFoundError("Lead not found")
        if follow_up.type != LeadFollowUpType.EMAIL_FOLLOW_UP:
            return None
        latest = self.executions.latest_for_follow_up(organization_id, follow_up.id)
        if latest is not None and latest.status == LeadFollowUpExecutionStatus.SENT:
            if follow_up.status == LeadFollowUpStatus.PENDING:
                self._complete_follow_up_after_sent(follow_up)
            return self.get(organization_id, latest.id)
        if latest is not None and latest.status == LeadFollowUpExecutionStatus.FAILED:
            return latest
        if follow_up.status in {
            LeadFollowUpStatus.COMPLETED,
            LeadFollowUpStatus.CANCELLED,
        }:
            return None
        inflight = self.executions.inflight_for_follow_up(organization_id, follow_up.id)
        if inflight is not None:
            if inflight.status == LeadFollowUpExecutionStatus.PENDING:
                inflight = self.mark_running(organization_id, inflight.id)
            if inflight.status == LeadFollowUpExecutionStatus.RUNNING:
                return self.deliver_claimed_execution(
                    organization_id=organization_id,
                    execution_id=inflight.id,
                )
            return inflight
        claimed = self.claim_email_follow_up(
            organization_id=organization_id,
            follow_up_id=follow_up.id,
        )
        if claimed is None:
            follow_up = self.follow_ups.get_by_organization_id(
                organization_id, follow_up_id
            )
            if follow_up is None:
                return None
            return self._fail_unsendable_due_follow_up(follow_up)
        return self.deliver_claimed_execution(
            organization_id=claimed.organization_id,
            execution_id=claimed.id,
        )

    def deliver_claimed_execution(
        self, *, organization_id: str, execution_id: str
    ) -> LeadFollowUpExecution:
        """Txn B/C: recheck, send from the execution snapshot, persist SENT/FAILED.

        Must only be called after the RUNNING execution is committed (txn A).
        Does not hold a DB transaction across EmailProvider.send.
        """
        self.session.expire_all()
        execution = self.get(organization_id, execution_id)
        if execution.status != LeadFollowUpExecutionStatus.RUNNING:
            return execution
        blocked = self._pre_send_block_reason(execution)
        if blocked is not None:
            error, category = blocked
            return self.mark_failed(
                organization_id,
                execution.id,
                error=error,
                category=category,
            )
        if self.provider is None or not settings.email_from_address:
            return self.mark_failed(
                organization_id,
                execution.id,
                error="Email provider is not configured",
                category=ExecutionFailureCategory.CONFIGURATION_ERROR,
            )
        provider = self.provider
        try:
            message = EmailMessage(
                to=safe_header(execution.recipient_email),
                from_email=safe_header(execution.sender_email),
                from_name=safe_optional_name(settings.email_from_name),
                subject=execution.subject,
                body_text=execution.body_text,
                idempotency_key=provider_idempotency_key(
                    execution.follow_up_id, execution.attempt
                ),
            )
        except PydanticValidationError:
            return self.mark_failed(
                organization_id,
                execution.id,
                error="Follow-up email snapshot is invalid",
                category=ExecutionFailureCategory.VALIDATION_ERROR,
            )
        try:
            result = provider.send(message)
        except ProviderNotConfiguredError as exc:
            return self.mark_failed(
                organization_id,
                execution.id,
                error=sanitize_provider_error(exc.detail),
                category=ExecutionFailureCategory.CONFIGURATION_ERROR,
            )
        except ProviderError as exc:
            return self.mark_failed(
                organization_id,
                execution.id,
                error=sanitize_provider_error(exc.detail),
                category=ExecutionFailureCategory.PROVIDER_ERROR,
            )
        except TimeoutError:
            return self.mark_failed(
                organization_id,
                execution.id,
                error="Email provider request timed out",
                category=ExecutionFailureCategory.PROVIDER_ERROR,
            )
        except Exception:
            logger.exception(
                "Unexpected follow-up email failure follow_up_id=%s",
                execution.follow_up_id,
            )
            return self.mark_failed(
                organization_id,
                execution.id,
                error="Email provider request failed",
                category=ExecutionFailureCategory.EXECUTION_ERROR,
            )

        try:
            sent = self.mark_sent(
                organization_id,
                execution.id,
                provider=result.provider,
                provider_message_id=result.message_id,
            )
        except Exception:
            logger.exception(
                "Follow-up email accepted by provider but SENT persist failed follow_up_id=%s",
                execution.follow_up_id,
            )
            raise
        follow_up = self.follow_ups.get_by_id(
            sent.organization_id, sent.lead_id, sent.follow_up_id
        )
        if follow_up is not None:
            self._complete_follow_up_after_sent(follow_up)
        return self.get(organization_id, sent.id)

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

    def _claim_locked_follow_up(
        self, follow_up: LeadFollowUp, now: datetime
    ) -> LeadFollowUpExecution | None:
        if not self.follow_up_still_sendable(follow_up):
            return None
        if self.executions.inflight_for_follow_up(
            follow_up.organization_id, follow_up.id
        ) is not None:
            return None
        latest = self.executions.latest_for_follow_up(
            follow_up.organization_id, follow_up.id
        )
        if latest is not None and latest.status in {
            LeadFollowUpExecutionStatus.SENT,
            LeadFollowUpExecutionStatus.FAILED,
        }:
            return None
        snapshot = self._snapshot_for_follow_up(follow_up)
        if snapshot is None:
            return None
        try:
            row = self._new_running_row(follow_up, snapshot, now)
            self.executions.add(row)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return None
        self.session.refresh(row)
        return row

    def _fail_unsendable_due_follow_up(
        self, follow_up: LeadFollowUp
    ) -> LeadFollowUpExecution | None:
        """Persist FAILED when a due EMAIL follow-up cannot be claimed for send."""
        now = datetime.now(UTC)
        due_at = follow_up.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        if (
            follow_up.status != LeadFollowUpStatus.PENDING
            or follow_up.type != LeadFollowUpType.EMAIL_FOLLOW_UP
            or due_at > now
        ):
            return None
        if self.executions.inflight_for_follow_up(
            follow_up.organization_id, follow_up.id
        ) is not None:
            return None
        latest = self.executions.latest_for_follow_up(
            follow_up.organization_id, follow_up.id
        )
        if latest is not None and latest.status in {
            LeadFollowUpExecutionStatus.SENT,
            LeadFollowUpExecutionStatus.FAILED,
        }:
            return latest
        lead = self.leads.get_by_id(follow_up.organization_id, follow_up.lead_id)
        error = "Follow-up could not be executed"
        category = ExecutionFailureCategory.EXECUTION_ERROR
        if lead is None or not lead.email:
            error = "This lead has no email address"
            category = ExecutionFailureCategory.VALIDATION_ERROR
        elif not follow_up.body_text or not follow_up.body_text.strip():
            error = "Follow-up body is missing"
            category = ExecutionFailureCategory.VALIDATION_ERROR
        elif not settings.email_from_address or self.provider is None:
            error = "Email provider is not configured"
            category = ExecutionFailureCategory.CONFIGURATION_ERROR
        else:
            return None
        snapshot = LeadFollowUpExecutionSnapshot(
            recipient_email=(lead.email if lead is not None and lead.email else "invalid@invalid"),
            sender_email=settings.email_from_address or "unconfigured@localhost",
            subject=FOLLOW_UP_EMAIL_SUBJECT,
            body_text=follow_up.body_text or "Follow-up body is missing",
        )
        try:
            row = self._new_running_row(follow_up, snapshot, now)
            self.executions.add(row)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return None
        return self.mark_failed(
            follow_up.organization_id,
            row.id,
            error=error,
            category=category,
        )

    def _pre_send_block_reason(
        self, execution: LeadFollowUpExecution
    ) -> tuple[str, ExecutionFailureCategory] | None:
        follow_up = self.reload_follow_up_for_send(
            execution.organization_id, execution.lead_id, execution.follow_up_id
        )
        if follow_up is None:
            return (
                "Follow-up is no longer eligible to send",
                ExecutionFailureCategory.EXECUTION_ERROR,
            )
        lead = self.leads.get_by_id(execution.organization_id, execution.lead_id)
        if lead is not None:
            self.session.refresh(lead)
        if lead is None:
            return (
                "Lead is no longer eligible to send",
                ExecutionFailureCategory.VALIDATION_ERROR,
            )
        if not lead.email:
            return (
                "This lead has no email address",
                ExecutionFailureCategory.VALIDATION_ERROR,
            )
        if lead.email.strip().lower() != execution.recipient_email.strip().lower():
            return (
                "Lead email no longer matches the execution snapshot",
                ExecutionFailureCategory.VALIDATION_ERROR,
            )
        return None

    def _complete_follow_up_after_sent(self, follow_up: LeadFollowUp) -> None:
        from app.services.lead_follow_up_service import LeadFollowUpService

        self.session.refresh(follow_up)
        if follow_up.status != LeadFollowUpStatus.PENDING:
            return
        try:
            LeadFollowUpService(self.session).complete(
                organization_id=follow_up.organization_id,
                lead_id=follow_up.lead_id,
                follow_up_id=follow_up.id,
                expected_revision=follow_up.revision,
            )
        except ConflictError:
            logger.info(
                "Follow-up %s was not completed after SENT; leaving execution SENT",
                follow_up.id,
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
        if lead is None:
            return None
        body = (follow_up.body_text or "").strip()
        if not body:
            return None
        sender = settings.email_from_address or UNCONFIGURED_SENDER
        recipient = lead.email or "unknown@invalid.local"
        return LeadFollowUpExecutionSnapshot(
            recipient_email=recipient,
            sender_email=sender,
            subject=FOLLOW_UP_EMAIL_SUBJECT,
            body_text=follow_up.body_text or body,
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
