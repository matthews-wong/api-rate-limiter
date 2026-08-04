"""FastAPI dependency for per-route rate limiting.

``RateLimit`` is a callable dependency: attach it to a route and it will set
rate-limit headers on the outgoing response and raise a 429 (with
``Retry-After``) when the caller exceeds the limit.
"""

# NOTE: deliberately no ``from __future__ import annotations`` here. FastAPI
# resolves a dependency's type hints via the callable's ``__globals__``; a
# class *instance* has none, so stringized annotations for ``Request`` /
# ``Response`` get misread as query params (HTTP 422). Concrete annotations
# keep the injection working.

from fastapi import HTTPException, Request, Response

from ratelimiter.keys import KeyFunc, default_key_func
from ratelimiter.limiter import RateLimiter


class RateLimit:
    """A dependency that enforces a limiter on the routes it guards.

    Example::

        limiter = RateLimiter(TokenBucket(capacity=5, refill_rate=1))
        guard = RateLimit(limiter)

        @app.get("/ping", dependencies=[Depends(guard)])
        def ping():
            return {"pong": True}
    """

    def __init__(
        self,
        limiter: RateLimiter,
        key_func: KeyFunc = default_key_func,
    ) -> None:
        self._limiter = limiter
        self._key_func = key_func

    async def __call__(self, request: Request, response: Response) -> None:
        key = self._key_func(request)
        result = self._limiter.check(key)

        # Set headers for both the allowed and denied paths.
        headers = result.headers()
        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers=headers,
            )
        for header, value in headers.items():
            response.headers[header] = value
