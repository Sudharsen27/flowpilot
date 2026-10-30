"""Worker entrypoint: `python -m app.worker`.

Runs as a separate process from the API. Follow-up sending, Sales Agent
auto-start, workflow runs, outgoing webhooks and daily forecast snapshots each
have their own enable flag and can share this process. All are disabled by
default so a local checkout never emails customers, calls the model, or sends
event data out unexpectedly.
"""

import logging
import signal
import sys
import threading
from types import FrameType
from typing import Protocol

from app.core.config import settings
from app.worker.follow_up_worker import FollowUpWorker
from app.worker.forecast_snapshot_worker import ForecastSnapshotWorker
from app.worker.sales_agent_auto_start_worker import SalesAgentAutoStartWorker
from app.worker.webhook_worker import WebhookWorker
from app.worker.workflow_worker import WorkflowWorker

logger = logging.getLogger("app.worker")


class PollingWorker(Protocol):
    poll_interval_seconds: float

    @property
    def is_stopping(self) -> bool: ...

    def request_stop(self) -> None: ...

    def install_signal_handlers(self) -> None: ...

    def run_forever(self) -> None: ...

    def run_once(self) -> object: ...


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    workers: list[PollingWorker] = []
    if settings.follow_up_worker_enabled:
        workers.append(FollowUpWorker())
    if settings.sales_agent_auto_start_worker_enabled:
        workers.append(SalesAgentAutoStartWorker())
    if settings.workflow_worker_enabled:
        workers.append(WorkflowWorker())
    if settings.webhook_worker_enabled:
        workers.append(WebhookWorker())
    if settings.forecast_snapshot_worker_enabled:
        workers.append(ForecastSnapshotWorker())
    if not workers:
        logger.info(
            "no worker is enabled; set FOLLOW_UP_WORKER_ENABLED, "
            "SALES_AGENT_AUTO_START_WORKER_ENABLED, WORKFLOW_WORKER_ENABLED, "
            "WEBHOOK_WORKER_ENABLED or FORECAST_SNAPSHOT_WORKER_ENABLED to run"
        )
        return 0
    if len(workers) == 1:
        workers[0].install_signal_handlers()
        workers[0].run_forever()
        return 0
    run_combined_forever(*workers)
    return 0


def run_combined_forever(*workers: PollingWorker) -> None:
    """Poll every enabled worker in one process with a shared interruptible sleep."""
    stop = threading.Event()

    def handle(signum: int, _frame: FrameType | None) -> None:
        logger.info(
            "worker received signal, finishing current item signal=%s",
            signal.Signals(signum).name,
        )
        for worker in workers:
            worker.request_stop()
        stop.set()

    def stopping() -> bool:
        return stop.is_set() or any(worker.is_stopping for worker in workers)

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    interval = min(worker.poll_interval_seconds for worker in workers)
    logger.info(
        "combined worker started workers=%s shared_sleep_seconds=%s",
        ",".join(type(worker).__name__ for worker in workers),
        interval,
    )
    try:
        while not stopping():
            for worker in workers:
                try:
                    worker.run_once()
                except Exception:
                    logger.exception("%s batch raised", type(worker).__name__)
                if stopping():
                    break
            else:
                stop.wait(interval)
    finally:
        logger.info("combined worker stopped")


if __name__ == "__main__":
    sys.exit(main())
