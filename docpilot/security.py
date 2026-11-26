"""API-key auth and a per-key token-bucket rate limiter (in-process; use Redis for >1 replica)."""
from __future__ import annotations

import hmac
import time
from typing import Callable


class ApiKeyAuth:
    def __init__(self, keys: list[str]):
        self.keys = [k.strip() for k in keys if k.strip()]

    @property
    def enabled(self) -> bool:
        return bool(self.keys)

    def check(self, presented: str | None) -> bool:
        if not self.enabled:
            return True
        if not presented:
            return False
        return any(hmac.compare_digest(presented, k) for k in self.keys)


class RateLimiter:
    def __init__(self, per_minute: int, burst: int | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.rate = per_minute / 60.0
        self.burst = float(burst if burst is not None else max(1, per_minute))
        self.clock = clock
        self.state: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = self.clock()
        tokens, last = self.state.get(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens >= cost:
            self.state[key] = (tokens - cost, now)
            return True
        self.state[key] = (tokens, now)
        return False
