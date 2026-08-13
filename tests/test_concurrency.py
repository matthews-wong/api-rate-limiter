"""Concurrency tests for :class:`RateLimiter`.

A rate limiter's core promise is that it never admits more than the configured
limit. That promise must hold when many threads hit the *same* key at once --
the exact situation a threaded ASGI server (or FastAPI running sync routes in a
threadpool) creates. These tests widen the read-modify-write window with a slow
backend so the race is exercised deterministically rather than by luck.
"""

from __future__ import annotations

import threading
import time

from ratelimiter import InMemoryBackend, RateLimiter, TokenBucket


class SlowBackend(InMemoryBackend):
    """In-memory backend whose ``get`` is deliberately slow.

    Widening the gap between ``get`` and ``set`` makes any non-atomic
    read-modify-write in the limiter over-admit reliably, instead of only
    under rare scheduling.
    """

    def get(self, key):  # type: ignore[override]
        value = super().get(key)
        time.sleep(0.01)
        return value


def _hammer(limiter: RateLimiter, key: str, threads: int) -> int:
    """Fire ``threads`` concurrent checks at ``key``; return how many were allowed."""
    results: list[bool] = []
    results_lock = threading.Lock()
    start = threading.Barrier(threads)

    def worker() -> None:
        start.wait()  # release all threads together to maximize contention
        allowed = limiter.check(key).allowed
        with results_lock:
            results.append(allowed)

    workers = [threading.Thread(target=worker) for _ in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    return sum(results)


def test_concurrent_requests_never_exceed_capacity(clock):
    # No refill during the test (huge window) so capacity is a hard ceiling.
    bucket = TokenBucket(capacity=1, refill_rate=1e-9, clock=clock)
    limiter = RateLimiter(bucket, backend=SlowBackend())

    allowed = _hammer(limiter, "shared", threads=25)

    assert allowed == 1, f"admitted {allowed} requests for a capacity-1 bucket"


def test_concurrent_requests_respect_larger_capacity(clock):
    bucket = TokenBucket(capacity=5, refill_rate=1e-9, clock=clock)
    limiter = RateLimiter(bucket, backend=SlowBackend())

    allowed = _hammer(limiter, "shared", threads=25)

    assert allowed == 5, f"admitted {allowed} requests for a capacity-5 bucket"


def test_concurrent_distinct_keys_are_isolated(clock):
    # Each key has capacity 1; concurrent hits across distinct keys must each
    # get their single allowance -- isolation must not be broken by locking.
    bucket = TokenBucket(capacity=1, refill_rate=1e-9, clock=clock)
    limiter = RateLimiter(bucket, backend=SlowBackend())

    allowed_per_key: dict[str, int] = {}
    lock = threading.Lock()

    def worker(key: str) -> None:
        allowed = limiter.check(key).allowed
        with lock:
            allowed_per_key[key] = allowed_per_key.get(key, 0) + int(allowed)

    keys = [f"k{i}" for i in range(20)]
    threads = [threading.Thread(target=worker, args=(k,)) for k in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(count == 1 for count in allowed_per_key.values())
    assert len(allowed_per_key) == len(keys)
