"""Polling worker that stores each organization's forecast snapshot once per UTC day.

Runs inside ``python -m app.worker`` only. There is no wall-clock trigger: every check
asks the database which organizations have no snapshot for today (UTC) and captures
them through ``ForecastSnapshotService``, so it catches up after downtime or a restart.

One UTC timestamp is taken at the start of each batch and used for the day, the lookup
and every capture in it, so a batch that runs past midnight still files every snapshot
under the day it started. Capture is idempotent per organization and day (unique
constraint plus the service's race handling), so overlapping workers never store a
second snapshot; they can only repeat a forecast calculation.

A failed organization is retried after 5, 10, 20 and 40 minutes, then every 60 minutes.
The retry schedule lives in memory and is cleared when the UTC day changes. The day is
complete only when no organization is missing today's snapshot and none awaits a retry.
"""

import logging
import signal
import threading
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import FrameType

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.models.forecast_snapshot import ForecastSnapshot
from app.models.organization import Organization
from app.services.forecast_snapshot_service import SNAPSHOT_GRANULARITY, ForecastSnapshotService

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session] | sessionmaker[Session]
Clock = Callable[[], datetime]
RETRY_DELAYS = (
    timedelta(minutes=5),
    timedelta(minutes=10),
    timedelta(minutes=20),
    timedelta(minutes=40),
    timedelta(minutes=60),
)


def retry_delay(failures: int) -> timedelta:
    """Wait after the n-th consecutive failure (n >= 1); 60 minutes from the fifth on."""
    return RETRY_DELAYS[min(failures, len(RETRY_DELAYS)) - 1]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _missing(snapshot_date: date) -> Select[str]:
    """Ids of organizations with no monthly snapshot for the date."""
    return (
        select(Organization.id)
        .outerjoin(
            ForecastSnapshot,
            and_(
                ForecastSnapshot.organization_id == Organization.id,
                ForecastSnapshot.snapshot_date == snapshot_date,
                ForecastSnapshot.granularity == SNAPSHOT_GRANULARITY.value,
            ),
        )
        .where(ForecastSnapshot.id.is_(None))
    )


@dataclass
class _Retry:
    failures: int
    retry_at: datetime


@dataclass(frozen=True)
class ForecastSnapshotBatchResult:
    capture_at: datetime
    # False when the next check was not due yet and the database was not queried.
    checked: bool = False
    candidates: int = 0
    captured: int = 0
    # Already captured today by another worker or an earlier batch.
    already_captured: int = 0
    # Deleted after the lookup.
    skipped: int = 0
    failed: int = 0
    # Organizations still without today's snapshot, waiting for their retry time.
    pending_retries: int = 0
    day_complete: bool = False


class ForecastSnapshotWorker:
    def __init__(
        self,
        *,
        session_factory: SessionFactory = SessionLocal,
        clock: Clock = _utc_now,
        poll_interval_seconds: float | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self.poll_interval_seconds = (
            settings.forecast_snapshot_worker_poll_interval_seconds
            if poll_interval_seconds is None
            else poll_interval_seconds
        )
        self.batch_size = (
            settings.forecast_snapshot_worker_batch_size if batch_size is None else batch_size
        )
        self._stop = threading.Event()
        self._day: date | None = None
        self._retries: dict[str, _Retry] = {}
        self._next_check_at: datetime | None = None
        self._completed_day: date | None = None

    @property
    def is_stopping(self) -> bool:
        return self._stop.is_set()

    @property
    def next_check_at(self) -> datetime | None:
        """When the next batch queries the database; None means at once."""
        return self._next_check_at

    def request_stop(self) -> None:
        self._stop.set()

    def install_signal_handlers(self) -> None:
        def handle(signum: int, _frame: FrameType | None) -> None:
            logger.info(
                "forecast snapshot worker received signal, finishing current item signal=%s",
                signal.Signals(signum).name,
            )
            self.request_stop()

        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)

    def run_forever(self) -> None:
        logger.info(
            "forecast snapshot worker started poll_interval_seconds=%s batch_size=%s",
            self.poll_interval_seconds,
            self.batch_size,
        )
        try:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception:
                    logger.exception("forecast snapshot worker batch raised")
                if self._stop.is_set():
                    break
                self._stop.wait(self._seconds_until_next_check())
        finally:
            logger.info("forecast snapshot worker stopped")

    def run_once(self, *, now: datetime | None = None) -> ForecastSnapshotBatchResult:
        capture_at = (now or self._clock()).astimezone(UTC)
        today = capture_at.date()
        if today != self._day:
            # A new UTC day: yesterday's retries no longer apply.
            self._day = today
            self._retries.clear()
            self._next_check_at = None
        if self._next_check_at is not None and capture_at < self._next_check_at:
            return ForecastSnapshotBatchResult(capture_at=capture_at)
        # If anything below raises, the next check still waits a full interval.
        self._next_check_at = capture_at + timedelta(seconds=self.poll_interval_seconds)

        waiting = {org for org, retry in self._retries.items() if retry.retry_at > capture_at}
        candidates = self.discover_missing(today, exclude=waiting, limit=self.batch_size)
        captured = already = skipped = failed = 0
        stopped = False
        for organization_id in candidates:
            if self._stop.is_set():
                stopped = True
                break
            outcome = self.capture_one(organization_id, capture_at)
            if outcome == "captured":
                captured += 1
            elif outcome == "already_captured":
                already += 1
            elif outcome == "skipped":
                skipped += 1
            else:
                failed += 1

        pending = self._prune_retries(today)
        day_complete = False
        if stopped or len(candidates) >= self.batch_size:
            # More organizations may be missing: check again at once.
            self._next_check_at = None
        elif pending:
            earliest = min(retry.retry_at for retry in self._retries.values())
            self._next_check_at = min(earliest, self._next_check_at)
        else:
            day_complete = True

        result = ForecastSnapshotBatchResult(
            capture_at=capture_at,
            checked=True,
            candidates=len(candidates),
            captured=captured,
            already_captured=already,
            skipped=skipped,
            failed=failed,
            pending_retries=pending,
            day_complete=day_complete,
        )
        if candidates:
            logger.info(
                "forecast snapshot worker batch finished date=%s candidates=%s captured=%s "
                "already_captured=%s skipped=%s failed=%s pending_retries=%s",
                today.isoformat(),
                result.candidates,
                result.captured,
                result.already_captured,
                result.skipped,
                result.failed,
                result.pending_retries,
            )
        if day_complete and self._completed_day != today:
            self._completed_day = today
            logger.info("forecast snapshots complete date=%s", today.isoformat())
        return result

    def discover_missing(
        self, snapshot_date: date, *, exclude: Collection[str], limit: int
    ) -> list[str]:
        """Organizations without a snapshot for the date, in id order. Ids come from the
        organizations table only; no row is locked."""
        statement = _missing(snapshot_date).order_by(Organization.id).limit(limit)
        if exclude:
            statement = statement.where(Organization.id.not_in(list(exclude)))
        session = self._session_factory()
        try:
            return list(session.scalars(statement))
        finally:
            session.close()

    def capture_one(self, organization_id: str, capture_at: datetime) -> str:
        """Capture one organization in its own session. Never raises."""
        session = self._session_factory()
        try:
            capture = ForecastSnapshotService(session).capture(organization_id, now=capture_at)
        except NotFoundError:
            self._retries.pop(organization_id, None)
            logger.info(
                "forecast snapshot worker skipped deleted organization organization_id=%s",
                organization_id,
            )
            return "skipped"
        except Exception:
            previous = self._retries.get(organization_id)
            failures = 1 if previous is None else previous.failures + 1
            retry_at = capture_at + retry_delay(failures)
            self._retries[organization_id] = _Retry(failures=failures, retry_at=retry_at)
            logger.exception(
                "forecast snapshot capture raised organization_id=%s attempt=%s retry_at=%s",
                organization_id,
                failures,
                retry_at.isoformat(),
            )
            return "failed"
        finally:
            session.close()
        self._retries.pop(organization_id, None)
        return "captured" if capture.created else "already_captured"

    def _prune_retries(self, snapshot_date: date) -> int:
        """Drop retries for organizations that now have today's snapshot (another worker
        captured it) or no longer exist; return how many still wait."""
        if not self._retries:
            return 0
        statement = _missing(snapshot_date).where(Organization.id.in_(list(self._retries)))
        session = self._session_factory()
        try:
            still_missing = set(session.scalars(statement))
        finally:
            session.close()
        for organization_id in list(self._retries):
            if organization_id not in still_missing:
                del self._retries[organization_id]
        return len(self._retries)

    def _seconds_until_next_check(self) -> float:
        if self._next_check_at is None:
            return 0.0
        remaining = (self._next_check_at - self._clock()).total_seconds()
        return min(max(remaining, 0.0), self.poll_interval_seconds)
