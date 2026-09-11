"""Follow-up worker entrypoint: `python -m app.worker`.

Runs as a separate process from the API. Set FOLLOW_UP_WORKER_ENABLED=true to
allow it to send; it is disabled by default so a local checkout never emails
customers unexpectedly.
"""

import logging
import sys

from app.core.config import settings
from app.worker.follow_up_worker import FollowUpWorker

logger = logging.getLogger("app.worker")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not settings.follow_up_worker_enabled:
        logger.info(
            "follow-up worker is disabled; set FOLLOW_UP_WORKER_ENABLED=true to run it"
        )
        return 0
    worker = FollowUpWorker()
    worker.install_signal_handlers()
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
