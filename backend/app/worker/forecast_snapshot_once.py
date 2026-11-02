"""One-off daily forecast snapshot capture: ``python -m app.worker.forecast_snapshot_once``.

For a scheduler that starts one process per run (such as a GitHub Actions cron job)
instead of the polling ``python -m app.worker``. It captures every organization that has
no snapshot for today (UTC) with ``ForecastSnapshotWorker.run_once()`` and the existing
capture logic, prints one line of aggregate counts and exits: 0 when the lookup and every
capture succeeded, 1 otherwise. A failed organization is normally left for the next run,
though a run still going after its five-minute retry delay may try it again; capture is
idempotent per organization and UTC day, so overlapping or repeated runs are safe. If the
lookup, or the retry check after a batch, fails, the run exits 1 and the summary may omit
that batch's counts.

The output may be public, so it holds counts only: no organization ids, figures, SQL
parameters, connection details, exception messages or tracebacks. An error inside
``main()`` is reported by class name only. Invalid settings can fail earlier, while
``python -m`` imports the ``app.worker`` package: that prints a short Pydantic traceback
whose message is redacted (``hide_input_in_errors``), never the supplied values.
It does not read ``FORECAST_SNAPSHOT_WORKER_ENABLED``, never calls ``run_forever()`` and
installs no signal handlers.
"""

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

WORKER_LOGGER = "app.worker.forecast_snapshot_worker"


@dataclass(frozen=True)
class SnapshotRunSummary:
    snapshot_date: date
    batches: int = 0
    candidates: int = 0
    captured: int = 0
    already_captured: int = 0
    skipped: int = 0
    failed: int = 0
    lookup_failed: bool = False

    @property
    def exit_code(self) -> int:
        return 1 if self.lookup_failed or self.failed else 0

    def line(self) -> str:
        status = "failed" if self.exit_code else "complete"
        return (
            f"forecast snapshot run status={status} date={self.snapshot_date.isoformat()} "
            f"batches={self.batches} candidates={self.candidates} captured={self.captured} "
            f"already_captured={self.already_captured} skipped={self.skipped} "
            f"failed={self.failed} lookup_failed={str(self.lookup_failed).lower()}"
        )


def create_session_factory(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    """A dedicated engine whose errors never include SQL parameter values."""
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args=connect_args,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine, factory


def run(
    session_factory: Callable[[], Session],
    *,
    batch_size: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SnapshotRunSummary:
    """Run batches until one holds fewer organizations than the batch size, or fails."""
    from app.worker.forecast_snapshot_worker import ForecastSnapshotWorker

    now = clock or (lambda: datetime.now(UTC))
    worker = ForecastSnapshotWorker(
        session_factory=session_factory, clock=now, batch_size=batch_size
    )
    totals = {"candidates": 0, "captured": 0, "already_captured": 0, "skipped": 0, "failed": 0}
    snapshot_date: date | None = None
    batches = 0
    lookup_failed = False
    # The worker logs organization ids and tracebacks; they must not reach this output.
    worker_logger = logging.getLogger(WORKER_LOGGER)
    was_disabled = worker_logger.disabled
    worker_logger.disabled = True
    try:
        while True:
            try:
                result = worker.run_once()
            except Exception:
                lookup_failed = True
                break
            batches += 1
            snapshot_date = snapshot_date or result.capture_at.date()
            for key in totals:
                totals[key] += getattr(result, key)
            if result.candidates < worker.batch_size:
                break
    finally:
        worker_logger.disabled = was_disabled
    return SnapshotRunSummary(
        snapshot_date=snapshot_date or now().astimezone(UTC).date(),
        batches=batches,
        lookup_failed=lookup_failed,
        **totals,
    )


def main() -> int:
    try:
        from app.core.config import settings

        engine, session_factory = create_session_factory(settings.database_url)
        try:
            summary = run(session_factory)
        finally:
            engine.dispose()
    except Exception as exc:
        print(f"forecast snapshot run status=error error={type(exc).__name__}", flush=True)
        return 1
    print(summary.line(), flush=True)
    return summary.exit_code


if __name__ == "__main__":
    sys.exit(main())
