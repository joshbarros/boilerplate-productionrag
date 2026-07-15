"""Simple sliding-window rate limiter (per-process, per-key)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitExceededError(Exception):
    """Raised when a client exceeds the per-minute budget."""

    def __init__(self, key: str, limit: int) -> None:
        self.key = key
        self.limit = limit
        super().__init__(f"rate limit exceeded for {key!r}: {limit}/min")


# Back-compat alias
RateLimitExceeded = RateLimitExceededError


class RateLimiter:
    """Thread-safe fixed-window counter over the last 60 seconds."""

    def __init__(self, per_minute: int = 30) -> None:
        self._limit = per_minute
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str = "default") -> None:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            q = self._hits[key]
            while q and q[0] < window_start:
                q.popleft()
            if len(q) >= self._limit:
                raise RateLimitExceededError(key, self._limit)
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
