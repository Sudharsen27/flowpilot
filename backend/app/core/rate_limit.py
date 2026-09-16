from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    """In-process sliding-window limiter.

    This is single-instance protection only. Separate API processes do not share
    counters. Redis is not used.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, max_requests: int, window_seconds: float) -> bool:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


website_capture_limiter = SlidingWindowRateLimiter()
