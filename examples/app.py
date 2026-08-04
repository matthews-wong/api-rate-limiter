"""A tiny FastAPI app that applies the rate limiter two ways.

Run it with::

    uvicorn examples.app:app --reload

* ``GET /ping`` is guarded by a per-route dependency (token bucket).
* ``GET /search`` is guarded by a separate sliding-window limiter.

Hit either endpoint faster than its limit to see a 429 with ``Retry-After``.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from ratelimiter import (
    InMemoryBackend,
    RateLimit,
    RateLimiter,
    SlidingWindow,
    TokenBucket,
)

app = FastAPI(title="api-rate-limiter demo")

# 5 requests of burst, refilling at 1 request/second.
ping_limiter = RateLimiter(
    TokenBucket(capacity=5, refill_rate=1.0),
    backend=InMemoryBackend(),
)

# At most 3 requests in any rolling 10-second window.
search_limiter = RateLimiter(
    SlidingWindow(limit=3, window_seconds=10.0),
    backend=InMemoryBackend(),
)


@app.get("/ping", dependencies=[Depends(RateLimit(ping_limiter))])
def ping() -> dict[str, bool]:
    return {"pong": True}


@app.get("/search", dependencies=[Depends(RateLimit(search_limiter))])
def search(q: str = "") -> dict[str, str]:
    return {"query": q, "result": "ok"}
