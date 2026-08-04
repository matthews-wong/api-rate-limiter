"""Key-extraction helpers.

A rate limiter needs a stable identity per caller. The default strategy keys
by API key header when present, otherwise by client IP. Both FastAPI
integrations accept a custom ``key_func`` if you need something else.
"""

from __future__ import annotations

from typing import Callable

from starlette.requests import Request

# A key function maps a request to the string a limiter buckets on.
KeyFunc = Callable[[Request], str]

API_KEY_HEADER = "X-API-Key"


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Honors the first hop in ``X-Forwarded-For`` when present (typical behind a
    proxy), else falls back to the socket peer. In production, only trust
    forwarded headers when a known proxy sets them.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def default_key_func(request: Request) -> str:
    """Key by API key if supplied, otherwise by client IP."""
    api_key = request.headers.get(API_KEY_HEADER)
    if api_key:
        return f"key:{api_key}"
    return f"ip:{client_ip(request)}"
