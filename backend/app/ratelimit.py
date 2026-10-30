"""In-memory sliding-window rate limits.

Scope and limits: counters live in this one Uvicorn process. They reset when
the backend restarts and are not shared between workers or replicas. That is
enough for the single-process Docker Compose demo; a multi-process deployment
needs a shared store (PostgreSQL or Redis) instead.
"""

import math
import time
from collections import deque
from collections.abc import Callable

# Bound memory if many distinct keys appear (e.g. random usernames).
MAX_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def _events(self, key: str) -> deque[float]:
        now = self._clock()
        events = self._hits.get(key)
        if events is None:
            if len(self._hits) >= MAX_KEYS:
                self._prune(now)
            events = self._hits.setdefault(key, deque())
        while events and events[0] <= now - self.window:
            events.popleft()
        return events

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
            del self._hits[key]
        if len(self._hits) >= MAX_KEYS:
            self._hits.clear()

    def retry_after(self, key: str) -> int | None:
        """Seconds until one more event is allowed, or None if allowed now."""
        events = self._events(key)
        if len(events) < self.limit:
            return None
        return max(1, math.ceil(events[0] + self.window - self._clock()))

    def record(self, key: str) -> None:
        self._events(key).append(self._clock())

    def hit(self, key: str) -> int | None:
        """Record an event if allowed; otherwise return the retry delay."""
        wait = self.retry_after(key)
        if wait is None:
            self.record(key)
        return wait

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
