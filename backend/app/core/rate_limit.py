from __future__ import annotations

from collections import defaultdict, deque
from itertools import count
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
contact_form_limiter = SlidingWindowRateLimiter()


class ProspectDiscoveryUsageLimiter:
    """Organization-scoped, in-process request and result budgets."""

    def __init__(self) -> None:
        self._events: dict[str, deque[tuple[int, float, int]]] = defaultdict(deque)
        self._ids = count()
        self._lock = Lock()

    def allow_request(
        self,
        organization_id: str,
        *,
        max_requests: int,
        window_seconds: float,
    ) -> int | None:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[organization_id]
            while events and events[0][1] <= cutoff:
                events.popleft()
            if len(events) >= max_requests:
                return None
            ticket = next(self._ids)
            events.append((ticket, now, 0))
            return ticket

    def allow_results(
        self,
        organization_id: str,
        ticket: int,
        result_count: int,
        *,
        max_results: int,
        window_seconds: float,
    ) -> bool:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[organization_id]
            while events and events[0][1] <= cutoff:
                events.popleft()
            total_results = sum(results for _, _, results in events)
            for index, (event_ticket, created_at, _) in enumerate(events):
                if event_ticket == ticket:
                    if total_results + result_count > max_results:
                        return False
                    events[index] = (event_ticket, created_at, result_count)
                    return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


prospect_discovery_limiter = ProspectDiscoveryUsageLimiter()
