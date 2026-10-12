"""Polling worker that delivers queued outgoing webhooks.

Runs inside ``python -m app.worker`` only. Events insert PENDING
``webhook_deliveries`` rows in the same transaction as the change. Each due
row is claimed with a PENDING → SENDING compare-and-set, sent once, and then
marked DELIVERED, rescheduled with backoff, or FAILED after the last attempt.
Delivery is at-least-once: receivers should dedupe on ``FlowPilot-Delivery``.
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

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.webhook_sender import WebhookSender, send_webhook
from app.models.webhook import WebhookDelivery, WebhookDeliveryStatus
from app.services.webhook_service import WebhookDeliverer, requeue_stuck_deliveries

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session] | sessionmaker[Session]
STUCK_AFTER = timedelta(minutes=10)


@dataclass(frozen=True)
class WebhookBatchResult:
    candidates: int = 0
    delivered: int = 0
    retrying: int = 0
    failed: int = 0
    requeued: int = 0


class WebhookWorker:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        sender: WebhookSender = send_webhook,
        poll_interval_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._sender = sender
        self.poll_interval_seconds = (
            settings.webhook_worker_poll_interval_seconds
            if poll_interval_seconds is None
            else poll_interval_seconds
        )
        self.batch_size = settings.webhook_worker_batch_size if batch_size is None else batch_size
        self._stop = threading.Event()

    @property
    def is_stopping(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self) -> None:
        def handle(signum: int, _frame: FrameType | None) -> None:
            logger.info(
                "webhook worker received signal, finishing current item signal=%s",
                signal.Signals(signum).name,
            )
            self.request_stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)

    def run_forever(self) -> None:
        logger.info(
            "webhook worker started poll_interval_seconds=%s batch_size=%s",
            self.poll_interval_seconds,
            self.batch_size,
        )
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception:
                    logger.exception("webhook worker batch raised")
                if self._stop.is_set():
                    break
                self._stop.wait(self.poll_interval_seconds)
        finally:
            logger.info("webhook worker stopped")

    def run_once(self, *, now: datetime | None = None) -> WebhookBatchResult:
        current = now or datetime.now(UTC)
        requeued = self._requeue_stuck(current)
        candidates = self.discover_due(self.batch_size, now=current)
        delivered = retrying = failed = 0
        for organization_id, delivery_id in candidates:
            if self._stop.is_set():
                break
            status = self.deliver_one(organization_id, delivery_id)
            if status == WebhookDeliveryStatus.DELIVERED:
                delivered += 1
            elif status == WebhookDeliveryStatus.PENDING:
                retrying += 1
            elif status == WebhookDeliveryStatus.FAILED:
                failed += 1
        result = WebhookBatchResult(
            candidates=len(candidates),
            delivered=delivered,
            retrying=retrying,
            failed=failed,
            requeued=requeued,
        )
        if candidates or requeued:
            logger.info(
                "webhook worker batch finished candidates=%s delivered=%s retrying=%s "
                "failed=%s requeued=%s",
                result.candidates,
                result.delivered,
                result.retrying,
                result.failed,
                result.requeued,
            )
        return result

    def _requeue_stuck(self, now: datetime) -> int:
        session = self._session_factory()
        try:
            return requeue_stuck_deliveries(session, started_before=now - STUCK_AFTER)
        finally:
            session.close()

    def discover_due(self, limit: int, *, now: datetime) -> list[tuple[str, str]]:
        session = self._session_factory()
        try:
            rows = session.execute(
                select(WebhookDelivery.organization_id, WebhookDelivery.id)
                .where(
                    WebhookDelivery.status == WebhookDeliveryStatus.PENDING,
                    WebhookDelivery.next_attempt_at <= now,
                )
                .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            return [(organization_id, delivery_id) for organization_id, delivery_id in rows]
        finally:
            session.close()

    def deliver_one(self, organization_id: str, delivery_id: str) -> str | None:
        """Attempt one delivery in its own session. Never raises."""
        session = self._session_factory()
        try:
            return WebhookDeliverer(session, self._sender).deliver(organization_id, delivery_id)
        except Exception:
            logger.exception(
                "webhook worker delivery raised organization_id=%s delivery_id=%s",
                organization_id,
                delivery_id,
            )
            return None
        finally:
            session.close()
