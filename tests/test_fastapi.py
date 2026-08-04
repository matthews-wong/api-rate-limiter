"""Integration tests: the FastAPI dependency and middleware over TestClient."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from ratelimiter import (
    RateLimit,
    RateLimiter,
    RateLimitMiddleware,
    TokenBucket,
)


def make_dependency_app(clock) -> FastAPI:
    app = FastAPI()
    limiter = RateLimiter(TokenBucket(capacity=3, refill_rate=1.0, clock=clock))

    @app.get("/ping", dependencies=[Depends(RateLimit(limiter))])
    def ping():
        return {"pong": True}

    return app


def test_dependency_allows_then_429s(clock):
    client = TestClient(make_dependency_app(clock))

    for _ in range(3):
        ok = client.get("/ping")
        assert ok.status_code == 200
        assert ok.headers["X-RateLimit-Limit"] == "3"

    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "1"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.json()["detail"] == "Rate limit exceeded"


def test_dependency_recovers_after_refill(clock):
    client = TestClient(make_dependency_app(clock))
    for _ in range(3):
        client.get("/ping")
    assert client.get("/ping").status_code == 429

    clock.advance(1.0)  # one token refills
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429


def test_middleware_applies_globally(clock):
    app = FastAPI()
    limiter = RateLimiter(TokenBucket(capacity=2, refill_rate=1.0, clock=clock))
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/")
    def root():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    blocked = client.get("/")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_api_key_and_ip_are_separate_buckets(clock):
    client = TestClient(make_dependency_app(clock))

    # Exhaust the IP-keyed bucket.
    for _ in range(3):
        client.get("/ping")
    assert client.get("/ping").status_code == 429

    # A caller presenting an API key gets its own fresh bucket.
    assert client.get("/ping", headers={"X-API-Key": "abc"}).status_code == 200
