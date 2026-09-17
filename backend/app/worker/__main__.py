"""Worker entrypoint: `python -m app.worker`.

Runs as a separate process from the API. Follow-up sending and Sales Agent
auto-start each have their own enable flag. Both can share this process.
Disabled by default so a local checkout never emails customers or calls the
model for website enquiries unexpectedly.
"""

import logging
import signal
import sys
import threading
from types import FrameType

from app.core.config import settings
from app.worker.follow_up_worker import FollowUpWorker
from app.worker.sales_agent_auto_start_worker import SalesAgentAutoStartWorker

logger = logging.getLogger("app.worker")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    follow_up_enabled = settings.follow_up_worker_enabled
    auto_start_enabled = settings.sales_agent_auto_start_worker_enabled
    if not follow_up_enabled and not auto_start_enabled:
        logger.info(
            "no worker is enabled; set FOLLOW_UP_WORKER_ENABLED or "
            "SALES_AGENT_AUTO_START_WORKER_ENABLED to run"
        )
        return 0

    follow_up = FollowUpWorker() if follow_up_enabled else None
    auto_start = SalesAgentAutoStartWorker() if auto_start_enabled else None
    if follow_up is not None and auto_start is None:
        follow_up.install_signal_handlers()
        follow_up.run_forever()
        return 0
    if auto_start is not None and follow_up is None:
        auto_start.install_signal_handlers()
        auto_start.run_forever()
        return 0
    assert follow_up is not None and auto_start is not None
    run_combined_forever(follow_up, auto_start)
    return 0


def run_combined_forever(
    follow_up: FollowUpWorker,
    auto_start: SalesAgentAutoStartWorker,
) -> None:
    """Poll both workers in one process with a shared interruptible sleep."""
    stop = threading.Event()

    def handle(signum: int, _frame: FrameType | None) -> None:
        logger.info(
            "worker received signal, finishing current item signal=%s",
            signal.Signals(signum).name,
        )
        follow_up.request_stop()
        auto_start.request_stop()
        stop.set()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    interval = min(follow_up.poll_interval_seconds, auto_start.poll_interval_seconds)
    logger.info(
        "combined worker started follow_up_poll_interval_seconds=%s "
        "auto_start_poll_interval_seconds=%s shared_sleep_seconds=%s",
        follow_up.poll_interval_seconds,
        auto_start.poll_interval_seconds,
        interval,
    )
    try:
        while not stop.is_set() and not follow_up.is_stopping and not auto_start.is_stopping:
            try:
                follow_up.run_once()
            except Exception:
                logger.exception("follow-up worker batch raised")
            if stop.is_set() or follow_up.is_stopping or auto_start.is_stopping:
                break
            try:
                auto_start.run_once()
            except Exception:
                logger.exception("sales-agent auto-start worker batch raised")
            if stop.is_set() or follow_up.is_stopping or auto_start.is_stopping:
                break
            stop.wait(interval)
    finally:
        logger.info("combined worker stopped")


if __name__ == "__main__":
    sys.exit(main())
