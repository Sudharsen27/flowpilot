"""Polling worker that sends due EMAIL_FOLLOW_UP records.

Process model
-------------
This runs as its own OS process (`python -m app.worker`). The FastAPI
application never starts it: no startup hook, no background task, no scheduler
and no in-process loop. That keeps request latency and email delivery
independent of each other.

Responsibilities
----------------
The worker only discovers due work, hands each row to the execution service,
records the outcome and decides whether to continue. It deliberately contains
no email logic: recipient/sender/subject/body selection, provider invocation,
idempotency keys, SENT/FAILED persistence and follow-up completion all remain
owned by ``LeadFollowUpExecutionService``.

Claiming
--------
Discovery is a read-only query. The atomic claim happens inside the execution
service, which locks the follow-up row with PostgreSQL ``SELECT ... FOR UPDATE
SKIP LOCKED``, inserts the RUNNING execution and commits before any provider
call. Two workers therefore cannot claim the same follow-up: the second either
skips the locked row or is rejected by the partial unique index on in-flight
executions. The worker passes ``resume_inflight=False`` so it never re-delivers
an attempt another process is still sending.

Delivery guarantee
------------------
At-least-once. If the provider accepts an email and this process dies before
the SENT transaction commits, a later attempt may send again. The provider
idempotency key is the protection against duplicate acceptance. There are no
automatic retries in this phase: a FAILED execution leaves the follow-up
PENDING for a human or a future retry policy.
"""

import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.session import SessionLocal
from app.email.provider import EmailProvider
from app.email.resend_provider import ResendEmailProvider
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from app.services.observability import duration_ms

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session] | sessionmaker[Session]
ProviderFactory = Callable[[], EmailProvider]


@dataclass(frozen=True)
class FollowUpBatchResult:
    """Safe, aggregate outcome of one poll. Contains no customer data."""

    candidates: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def processed(self) -> int:
        return self.sent + self.failed + self.skipped + self.errors


class FollowUpWorker:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        provider_factory: ProviderFactory = ResendEmailProvider,
        poll_interval_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider_factory = provider_factory
        self.poll_interval_seconds = (
            settings.follow_up_worker_poll_interval_seconds
            if poll_interval_seconds is None
            else poll_interval_seconds
        )
        self.batch_size = (
            settings.follow_up_worker_batch_size if batch_size is None else batch_size
        )
        self._stop = threading.Event()

    @property
    def is_stopping(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        """Stop accepting new work. The in-flight item is allowed to finish."""
        self._stop.set()

    def install_signal_handlers(self) -> None:
        """Handle SIGINT/SIGTERM. Must be called from the main thread."""

        def handle(signum: int, _frame: FrameType | None) -> None:
            logger.info(
                "follow-up worker received signal, finishing current item signal=%s",
                signal.Signals(signum).name,
            )
            self.request_stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)

    def run_forever(self) -> None:
        logger.info(
            "follow-up worker started poll_interval_seconds=%s batch_size=%s",
            self.poll_interval_seconds,
            self.batch_size,
        )
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception:
                    # An infrastructure failure (for example the database being
                    # unreachable) must not kill the worker.
                    logger.exception("follow-up worker batch raised")
                if self._stop.is_set():
                    break
                # Interruptible sleep so shutdown does not wait a full interval.
                self._stop.wait(self.poll_interval_seconds)
        finally:
            logger.info("follow-up worker stopped")

    def run_once(self) -> FollowUpBatchResult:
        """Run one poll: discover due follow-ups and execute them one by one."""
        candidates = self._discover_due()
        logger.info("follow-up worker polled candidates=%s", len(candidates))
        if not candidates:
            return FollowUpBatchResult()

        sent = failed = skipped = errors = 0
        for organization_id, follow_up_id in candidates:
            if self._stop.is_set():
                logger.info(
                    "follow-up worker stopping before remaining items remaining=%s",
                    len(candidates) - (sent + failed + skipped + errors),
                )
                break
            outcome = self._execute_one(organization_id, follow_up_id)
            if outcome == "sent":
                sent += 1
            elif outcome == "failed":
                failed += 1
            elif outcome == "error":
                errors += 1
            else:
                skipped += 1
        result = FollowUpBatchResult(
            candidates=len(candidates),
            sent=sent,
            failed=failed,
            skipped=skipped,
            errors=errors,
        )
        logger.info(
            "follow-up worker batch finished candidates=%s sent=%s failed=%s "
            "skipped=%s errors=%s",
            result.candidates,
            result.sent,
            result.failed,
            result.skipped,
            result.errors,
        )
        return result

    def _discover_due(self) -> list[tuple[str, str]]:
        session = self._session_factory()
        try:
            service = LeadFollowUpExecutionService(session)
            return service.discover_due_email_follow_ups(
                as_of=datetime.now(UTC), limit=self.batch_size
            )
        finally:
            session.close()

    def _execute_one(self, organization_id: str, follow_up_id: str) -> str:
        """Execute one follow-up in its own session. Never raises."""
        logger.info(
            "follow-up worker claiming organization_id=%s follow_up_id=%s",
            organization_id,
            follow_up_id,
        )
        session = self._session_factory()
        try:
            service = LeadFollowUpExecutionService(
                session, provider=self._provider_factory()
            )
            execution = service.execute_follow_up(
                organization_id=organization_id,
                follow_up_id=follow_up_id,
                # A concurrent worker must never deliver another worker's
                # in-flight attempt.
                resume_inflight=False,
            )
            if execution is None:
                logger.info(
                    "follow-up worker skipped organization_id=%s follow_up_id=%s",
                    organization_id,
                    follow_up_id,
                )
                return "skipped"
            if execution.status == LeadFollowUpExecutionStatus.SENT:
                logger.info(
                    "follow-up worker sent organization_id=%s follow_up_id=%s "
                    "execution_id=%s attempt=%s provider=%s duration_ms=%s",
                    organization_id,
                    follow_up_id,
                    execution.id,
                    execution.attempt,
                    execution.provider,
                    duration_ms(execution.started_at, execution.completed_at),
                )
                return "sent"
            if execution.status == LeadFollowUpExecutionStatus.FAILED:
                # failure_category and error are already sanitized by the
                # execution service. No provider payload is logged.
                logger.warning(
                    "follow-up worker execution failed organization_id=%s "
                    "follow_up_id=%s execution_id=%s attempt=%s "
                    "failure_category=%s error=%s",
                    organization_id,
                    follow_up_id,
                    execution.id,
                    execution.attempt,
                    execution.failure_category,
                    execution.error,
                )
                return "failed"
            logger.info(
                "follow-up worker left execution in progress organization_id=%s "
                "follow_up_id=%s execution_id=%s status=%s",
                organization_id,
                follow_up_id,
                execution.id,
                execution.status,
            )
            return "skipped"
        except Exception:
            # One bad follow-up must not stop the batch. The execution service
            # owns execution state, so nothing is changed here.
            logger.exception(
                "follow-up worker execution raised organization_id=%s follow_up_id=%s",
                organization_id,
                follow_up_id,
            )
            return "error"
        finally:
            session.close()
