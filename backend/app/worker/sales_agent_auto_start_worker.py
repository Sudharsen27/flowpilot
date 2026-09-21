"""Polling worker that starts the Sales Agent for PENDING website leads.

Process model
-------------
This runs inside ``python -m app.worker``, the same OS process as the
follow-up worker. The FastAPI application never starts it: no startup hook,
no background task, no scheduler and no in-process loop.

Responsibilities
----------------
The worker only discovers PENDING website leads, opens an isolated session
per item, and hands ``organization_id`` / ``lead_id`` from the database row
to ``SalesAgentAutoStartService``. Claiming, skip/fail rules, SalesRun
orchestration and Activity remain owned by that service.

Discovery
---------
``list_pending_auto_start(..., for_update_skip_locked=True)`` is a short-lived
read. The session is closed before any provider call so row locks are not
held across OpenAI. ``PENDING → CLAIMED`` CAS inside the service is what
prevents two workers from starting the same lead.
"""

import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass
from types import FrameType

from sqlalchemy.orm import Session, sessionmaker

from app.ai.factory import create_ai_provider
from app.ai.provider import AIProvider
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.db.session import SessionLocal
from app.models.lead import LeadSalesAgentAutoStartStatus
from app.repositories.lead_repository import LeadRepository
from app.services.sales_agent_auto_start_service import SalesAgentAutoStartService

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session] | sessionmaker[Session]
ProviderFactory = Callable[[], AIProvider]


@dataclass(frozen=True)
class AutoStartBatchResult:
    """Safe, aggregate outcome of one poll. Contains no customer data."""

    candidates: int = 0
    started: int = 0
    skipped: int = 0
    failed: int = 0
    errors: int = 0

    @property
    def processed(self) -> int:
        return self.started + self.skipped + self.failed + self.errors


class SalesAgentAutoStartWorker:
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
            settings.sales_agent_auto_start_worker_poll_interval_seconds
            if poll_interval_seconds is None
            else poll_interval_seconds
        )
        self.batch_size = (
            settings.sales_agent_auto_start_worker_batch_size
            if batch_size is None
            else batch_size
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
                "sales-agent auto-start worker received signal, finishing current "
                "item signal=%s",
                signal.Signals(signum).name,
            )
            self.request_stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)

    def run_forever(self) -> None:
        logger.info(
            "sales-agent auto-start worker started poll_interval_seconds=%s batch_size=%s",
            self.poll_interval_seconds,
            self.batch_size,
        )
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception:
                    logger.exception("sales-agent auto-start worker batch raised")
                if self._stop.is_set():
                    break
                self._stop.wait(self.poll_interval_seconds)
        finally:
            logger.info("sales-agent auto-start worker stopped")

    def run_once(self) -> AutoStartBatchResult:
        candidates = self.discover_pending(self.batch_size)
        logger.info("sales-agent auto-start worker polled candidates=%s", len(candidates))
        if not candidates:
            return AutoStartBatchResult()

        started = skipped = failed = errors = 0
        for organization_id, lead_id in candidates:
            if self._stop.is_set():
                logger.info(
                    "sales-agent auto-start worker stopping before remaining items remaining=%s",
                    len(candidates) - (started + skipped + failed + errors),
                )
                break
            outcome = self.execute_one(organization_id, lead_id)
            if outcome == "started":
                started += 1
            elif outcome == "failed":
                failed += 1
            elif outcome == "error":
                errors += 1
            else:
                skipped += 1
        result = AutoStartBatchResult(
            candidates=len(candidates),
            started=started,
            skipped=skipped,
            failed=failed,
            errors=errors,
        )
        logger.info(
            "sales-agent auto-start worker batch finished candidates=%s started=%s "
            "skipped=%s failed=%s errors=%s",
            result.candidates,
            result.started,
            result.skipped,
            result.failed,
            result.errors,
        )
        return result

    def discover_pending(self, limit: int) -> list[tuple[str, str]]:
        session = self._session_factory()
        try:
            rows = LeadRepository(session).list_pending_auto_start(
                limit=limit,
                for_update_skip_locked=True,
            )
            return [(row.organization_id, row.id) for row in rows]
        finally:
            session.close()

    def execute_one(self, organization_id: str, lead_id: str) -> str:
        """Process one lead in its own session. Never raises."""
        logger.info(
            "sales-agent auto-start worker executing organization_id=%s lead_id=%s",
            organization_id,
            lead_id,
        )
        session = self._session_factory()
        try:
            result = SalesAgentAutoStartService(
                session,
                provider=self._provider_factory(),
            ).process(organization_id, lead_id)
            if not result.claimed:
                logger.info(
                    "sales-agent auto-start worker skipped organization_id=%s lead_id=%s",
                    organization_id,
                    lead_id,
                )
                return "skipped"
            if result.outcome == LeadSalesAgentAutoStartStatus.STARTED:
                logger.info(
                    "sales-agent auto-start worker started organization_id=%s lead_id=%s "
                    "sales_run_id=%s",
                    organization_id,
                    lead_id,
                    result.sales_run_id,
                )
                return "started"
            if result.outcome == LeadSalesAgentAutoStartStatus.FAILED:
                logger.warning(
                    "sales-agent auto-start worker failed organization_id=%s lead_id=%s",
                    organization_id,
                    lead_id,
                )
                return "failed"
            logger.info(
                "sales-agent auto-start worker skipped organization_id=%s lead_id=%s "
                "outcome=%s",
                organization_id,
                lead_id,
                result.outcome,
            )
            return "skipped"
        except (ProviderError, ProviderNotConfiguredError):
            logger.warning(
                "sales-agent auto-start worker provider failed organization_id=%s lead_id=%s",
                organization_id,
                lead_id,
            )
            return "failed"
        except Exception:
            logger.exception(
                "sales-agent auto-start worker execution raised organization_id=%s lead_id=%s",
                organization_id,
                lead_id,
            )
            return "error"
        finally:
            session.close()
