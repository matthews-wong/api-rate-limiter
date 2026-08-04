"""Pure rate-limiting algorithms.

Both algorithms are framework-agnostic and take an injectable ``clock`` so
tests can advance time deterministically without ever sleeping. Each exposes
the same shape:

    initial_state() -> State
    check(state, cost=1) -> (new_state, RateLimitResult)

``check`` is a pure function of ``(state, clock())``: given the same inputs it
always returns the same outputs, which is what makes them trivially testable.
"""

from __future__ import annotations

import time
from typing import Callable

from ratelimiter.models import (
    RateLimitResult,
    SlidingWindowState,
    TokenBucketState,
)

# A clock returns monotonically increasing seconds as a float.
Clock = Callable[[], float]


class TokenBucket:
    """Token-bucket limiter.

    A bucket holds up to ``capacity`` tokens and refills at ``refill_rate``
    tokens per second. Each request costs one (or ``cost``) tokens. Bursts up
    to ``capacity`` are allowed; sustained throughput is bounded by the rate.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        clock: Clock = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock

    def initial_state(self) -> TokenBucketState:
        """A fresh, full bucket as of now."""
        return TokenBucketState(tokens=float(self.capacity), last_refill=self._clock())

    def check(
        self, state: TokenBucketState, cost: int = 1
    ) -> tuple[TokenBucketState, RateLimitResult]:
        now = self._clock()
        # Accrue tokens for the elapsed interval, capped at capacity.
        elapsed = max(0.0, now - state.last_refill)
        tokens = min(self.capacity, state.tokens + elapsed * self.refill_rate)

        allowed = tokens >= cost
        if allowed:
            tokens -= cost

        new_state = TokenBucketState(tokens=tokens, last_refill=now)

        # Seconds until the bucket is completely full again.
        reset_after = max(0.0, (self.capacity - tokens) / self.refill_rate)
        # Seconds until enough tokens exist to serve this request.
        retry_after = 0.0 if allowed else (cost - tokens) / self.refill_rate

        result = RateLimitResult(
            allowed=allowed,
            limit=self.capacity,
            remaining=int(tokens),
            reset_after=reset_after,
            retry_after=retry_after,
        )
        return new_state, result


class SlidingWindow:
    """Sliding-window (log) limiter.

    Allows at most ``limit`` requests in any rolling ``window_seconds``
    interval. Unlike a fixed window, it has no boundary-burst problem: the
    window slides continuously with each request.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Clock = time.monotonic,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock

    def initial_state(self) -> SlidingWindowState:
        return SlidingWindowState(timestamps=[])

    def check(
        self, state: SlidingWindowState, cost: int = 1
    ) -> tuple[SlidingWindowState, RateLimitResult]:
        now = self._clock()
        cutoff = now - self.window_seconds
        # Drop entries that have aged out of the window.
        timestamps = [t for t in state.timestamps if t > cutoff]

        allowed = len(timestamps) + cost <= self.limit
        if allowed:
            timestamps.extend([now] * cost)

        new_state = SlidingWindowState(timestamps=timestamps)
        remaining = max(0, self.limit - len(timestamps))

        # The oldest in-window request dictates when a slot frees up.
        if timestamps:
            oldest = timestamps[0]
            reset_after = max(0.0, (oldest + self.window_seconds) - now)
        else:
            reset_after = 0.0
        retry_after = 0.0 if allowed else reset_after

        result = RateLimitResult(
            allowed=allowed,
            limit=self.limit,
            remaining=remaining,
            reset_after=reset_after,
            retry_after=retry_after,
        )
        return new_state, result
