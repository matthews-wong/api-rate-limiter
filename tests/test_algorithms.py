"""Unit tests for the pure algorithms, driven by a fake clock."""

from __future__ import annotations

from ratelimiter import RateLimiter, SlidingWindow, TokenBucket


def run(limiter: RateLimiter, key: str, n: int) -> list[bool]:
    return [limiter.check(key).allowed for _ in range(n)]


class TestTokenBucket:
    def test_allows_up_to_capacity_then_denies(self, clock):
        limiter = RateLimiter(TokenBucket(capacity=5, refill_rate=1.0, clock=clock))
        results = run(limiter, "a", 6)
        assert results == [True, True, True, True, True, False]

    def test_refills_over_time(self, clock):
        bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=clock)
        limiter = RateLimiter(bucket)

        # Drain the bucket.
        assert run(limiter, "a", 5) == [True] * 5
        assert limiter.check("a").allowed is False

        # Two seconds pass -> two tokens accrue at 1/sec.
        clock.advance(2.0)
        assert limiter.check("a").allowed is True
        assert limiter.check("a").allowed is True
        assert limiter.check("a").allowed is False

    def test_refill_is_capped_at_capacity(self, clock):
        bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=clock)
        limiter = RateLimiter(bucket)
        run(limiter, "a", 3)  # drain

        # Idle far longer than needed to refill; cannot exceed capacity.
        clock.advance(100.0)
        assert run(limiter, "a", 4) == [True, True, True, False]

    def test_retry_after_reflects_refill_rate(self, clock):
        # refill 0.5/sec -> one token every 2 seconds.
        bucket = TokenBucket(capacity=1, refill_rate=0.5, clock=clock)
        limiter = RateLimiter(bucket)
        assert limiter.check("a").allowed is True

        denied = limiter.check("a")
        assert denied.allowed is False
        # Need ~1 token at 0.5/sec => ~2s wait.
        assert denied.retry_after == 2.0
        assert denied.headers()["Retry-After"] == "2"

    def test_remaining_header_counts_down(self, clock):
        limiter = RateLimiter(TokenBucket(capacity=3, refill_rate=1.0, clock=clock))
        first = limiter.check("a")
        assert first.headers()["X-RateLimit-Limit"] == "3"
        assert first.headers()["X-RateLimit-Remaining"] == "2"
        assert limiter.check("a").headers()["X-RateLimit-Remaining"] == "1"

    def test_keys_are_isolated(self, clock):
        limiter = RateLimiter(TokenBucket(capacity=1, refill_rate=1.0, clock=clock))
        assert limiter.check("a").allowed is True
        assert limiter.check("b").allowed is True  # different key, own bucket
        assert limiter.check("a").allowed is False


class TestSlidingWindow:
    def test_counts_within_window(self, clock):
        limiter = RateLimiter(
            SlidingWindow(limit=3, window_seconds=10.0, clock=clock)
        )
        assert run(limiter, "a", 4) == [True, True, True, False]

    def test_slot_frees_as_window_slides(self, clock):
        window = SlidingWindow(limit=2, window_seconds=10.0, clock=clock)
        limiter = RateLimiter(window)

        assert limiter.check("a").allowed is True  # t=0
        clock.advance(4.0)
        assert limiter.check("a").allowed is True  # t=4
        assert limiter.check("a").allowed is False  # t=4, at limit

        # At t=11 the first request (t=0) has aged out of the 10s window.
        clock.advance(7.0)
        assert limiter.check("a").allowed is True

    def test_full_window_then_all_expire(self, clock):
        limiter = RateLimiter(
            SlidingWindow(limit=2, window_seconds=5.0, clock=clock)
        )
        assert run(limiter, "a", 2) == [True, True]
        assert limiter.check("a").allowed is False

        clock.advance(6.0)  # entire window elapsed
        assert run(limiter, "a", 2) == [True, True]

    def test_retry_after_points_at_oldest_expiry(self, clock):
        window = SlidingWindow(limit=1, window_seconds=10.0, clock=clock)
        limiter = RateLimiter(window)
        assert limiter.check("a").allowed is True  # t=0

        clock.advance(3.0)
        denied = limiter.check("a")  # t=3
        assert denied.allowed is False
        # Oldest (t=0) frees at t=10 => wait 7s.
        assert denied.retry_after == 7.0
        assert denied.headers()["Retry-After"] == "7"

    def test_headers_have_no_retry_after_when_allowed(self, clock):
        limiter = RateLimiter(
            SlidingWindow(limit=2, window_seconds=10.0, clock=clock)
        )
        headers = limiter.check("a").headers()
        assert "Retry-After" not in headers
        assert headers["X-RateLimit-Remaining"] == "1"
