"""ASGI middleware that applies a limiter to every request.

Use this when you want a blanket limit across an app. For per-route limits,
prefer :class:`ratelimiter.dependency.RateLimit`.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ratelimiter.keys import KeyFunc, default_key_func
from ratelimiter.limiter import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce a :class:`RateLimiter` on all requests.

    On success, ``X-RateLimit-*`` headers are attached to the response. On
    exceed, a 429 JSON response is returned with ``Retry-After`` set.
    """

    def __init__(
        self,
        app,
        limiter: RateLimiter,
        key_func: KeyFunc = default_key_func,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._key_func = key_func

    async def dispatch(self, request: Request, call_next) -> Response:
        key = self._key_func(request)
        result = self._limiter.check(key)

        if not result.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers=result.headers(),
            )

        response = await call_next(request)
        for header, value in result.headers().items():
            response.headers[header] = value
        return response
