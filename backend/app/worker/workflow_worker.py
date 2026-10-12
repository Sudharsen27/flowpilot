"""Polling worker that executes queued workflow runs.

Runs inside ``python -m app.worker`` only. The API process never executes a
workflow step: triggers just insert PENDING ``workflow_runs`` rows in the
same transaction as the event. Each run is claimed with a PENDING → RUNNING
compare-and-set, so two workers never execute the same run. A run left
RUNNING by a crashed worker is marked FAILED rather than retried, because
repeating an AI call or follow-up is worse than reporting the interruption.
"""

import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import FrameType

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.factory import create_ai_provider
from app.ai.provider import AIProvider
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.workflow import WorkflowRun, WorkflowRunStatus
from app.services.workflow_service import WorkflowRunner, fail_interrupted_runs

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session] | sessionmaker[Session]
ProviderFactory = Callable[[], AIProvider]
INTERRUPTED_AFTER = timedelta(minutes=15)


@dataclass(frozen=True)
class WorkflowBatchResult:
    """Aggregate outcome of one poll. Contains no customer data."""

    candidates: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    interrupted: int = 0


class WorkflowWorker:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        provider_factory: ProviderFactory = create_ai_provider,
        poll_interval_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._provider_factory = provider_factory
        self.poll_interval_seconds = (
            settings.workflow_worker_poll_interval_seconds
            if poll_interval_seconds is None
            else poll_interval_seconds
        )
        self.batch_size = (
            settings.workflow_worker_batch_size if batch_size is None else batch_size
        )
        self._stop = threading.Event()

    @property
    def is_stopping(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self) -> None:
        def handle(signum: int, _frame: FrameType | None) -> None:
            logger.info(
                "workflow worker received signal, finishing current item signal=%s",
                signal.Signals(signum).name,
            )
            self.request_stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)

    def run_forever(self) -> None:
        logger.info(
            "workflow worker started poll_interval_seconds=%s batch_size=%s",
            self.poll_interval_seconds,
            self.batch_size,
        )
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception:
                    logger.exception("workflow worker batch raised")
                if self._stop.is_set():
                    break
                self._stop.wait(self.poll_interval_seconds)
        finally:
            logger.info("workflow worker stopped")

    def run_once(self, *, now: datetime | None = None) -> WorkflowBatchResult:
        interrupted = self.fail_interrupted(now=now)
        candidates = self.discover_pending(self.batch_size)
        succeeded = skipped = failed = 0
        for organization_id, run_id in candidates:
            if self._stop.is_set():
                break
            status = self.execute_one(organization_id, run_id)
            if status is WorkflowRunStatus.SUCCEEDED:
                succeeded += 1
            elif status is WorkflowRunStatus.FAILED:
                failed += 1
            else:
                skipped += 1
        result = WorkflowBatchResult(
            candidates=len(candidates),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
            interrupted=interrupted,
        )
        if candidates or interrupted:
            logger.info(
                "workflow worker batch finished candidates=%s succeeded=%s skipped=%s "
                "failed=%s interrupted=%s",
                result.candidates,
                result.succeeded,
                result.skipped,
                result.failed,
                result.interrupted,
            )
        return result

    def fail_interrupted(self, *, now: datetime | None = None) -> int:
        session = self._session_factory()
        try:
            return fail_interrupted_runs(
                session, started_before=(now or datetime.now(UTC)) - INTERRUPTED_AFTER
            )
        finally:
            session.close()

    def discover_pending(self, limit: int) -> list[tuple[str, str]]:
        session = self._session_factory()
        try:
            rows = session.execute(
                select(WorkflowRun.organization_id, WorkflowRun.id)
                .where(WorkflowRun.status == WorkflowRunStatus.PENDING)
                .order_by(WorkflowRun.created_at, WorkflowRun.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            return [(organization_id, run_id) for organization_id, run_id in rows]
        finally:
            session.close()

    def execute_one(self, organization_id: str, run_id: str) -> WorkflowRunStatus | None:
        """Execute one run in its own session. Never raises."""
        session = self._session_factory()
        try:
            return WorkflowRunner(session, self._provider_factory()).execute(
                organization_id, run_id
            )
        except Exception:
            logger.exception(
                "workflow worker execution raised organization_id=%s run_id=%s",
                organization_id,
                run_id,
            )
            return WorkflowRunStatus.FAILED
        finally:
            session.close()
