"""A rate-limiting toolkit for FastAPI.

Provides token-bucket and sliding-window algorithms behind a pluggable
backend, plus FastAPI middleware and dependency integrations that emit
standard ``X-RateLimit-*`` / ``Retry-After`` headers and a 429 on exceed.
"""

from ratelimiter.algorithms import SlidingWindow, TokenBucket
from ratelimiter.backend import Backend, InMemoryBackend, RedisBackend
from ratelimiter.dependency import RateLimit
from ratelimiter.limiter import RateLimiter
from ratelimiter.middleware import RateLimitMiddleware
from ratelimiter.models import (
    RateLimitResult,
    SlidingWindowState,
    TokenBucketState,
)

__all__ = [
    "SlidingWindow",
    "TokenBucket",
    "Backend",
    "InMemoryBackend",
    "RedisBackend",
    "RateLimit",
    "RateLimiter",
    "RateLimitMiddleware",
    "RateLimitResult",
    "SlidingWindowState",
    "TokenBucketState",
]

__version__ = "0.1.0"
