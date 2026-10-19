"""In-process sliding-window rate limiter (noisy-neighbour protection).

One budget per tenant (falling back to client IP for unauthenticated
traffic). Kept dependency-free on purpose: this is a single-instance
limiter. When you scale the backend horizontally, swap the storage for
Redis — the interface (``allow``) is deliberately tiny so the upgrade is
mechanical. See docs/MULTI-TENANCY.md → "Noisy neighbours".
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 50_000):
        self.limit = max(1, limit)
        self.window = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window

        bucket = self._hits.get(key)
        if bucket is None:
            if len(self._hits) >= self.max_keys:
                self._prune(now)
            bucket = deque()
            self._hits[key] = bucket

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(1, int(bucket[0] + self.window - now) + 1)
            return False, 0, retry_after

        bucket.append(now)
        return True, self.limit - len(bucket), 0

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        stale = [key for key, bucket in self._hits.items() if not bucket or bucket[-1] <= cutoff]
        for key in stale:
            self._hits.pop(key, None)
