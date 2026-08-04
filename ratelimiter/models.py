"""Value objects shared across the toolkit.

These types carry algorithm state and the outcome of a rate-limit check.
They are intentionally free of framework dependencies so the algorithms
stay pure and unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class TokenBucketState:
    """Mutable-by-copy state for a single token-bucket key.

    ``tokens`` is a float because refills accrue continuously; ``last_refill``
    is the clock timestamp (seconds) at which ``tokens`` was last computed.
    """

    tokens: float
    last_refill: float


@dataclass
class SlidingWindowState:
    """State for a single sliding-window key.

    Uses the *sliding log* variant: the exact timestamps of accepted requests
    within the current window. This is precise (no boundary bursts) at the
    cost of storing up to ``limit`` timestamps per key.
    """

    timestamps: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single rate-limit check.

    Attributes:
        allowed: Whether the request may proceed.
        limit: The configured maximum for the window/bucket.
        remaining: Requests still available right now.
        reset_after: Seconds until the limiter is fully replenished.
        retry_after: Seconds the client should wait before retrying. ``0.0``
            when the request was allowed.
    """

    allowed: bool
    limit: int
    remaining: int
    reset_after: float
    retry_after: float

    def headers(self) -> dict[str, str]:
        """Render the standard rate-limit response headers.

        ``Retry-After`` is only emitted when the request was denied, matching
        common HTTP semantics. Time values are rounded up to whole seconds so
        clients never retry a fraction too early.
        """

        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(math.ceil(self.reset_after)),
        }
        if not self.allowed:
            headers["Retry-After"] = str(math.ceil(self.retry_after))
        return headers
