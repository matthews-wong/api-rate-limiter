"""Shared test fixtures.

The ``FakeClock`` lets tests advance time explicitly so the time-based
algorithms are deterministic and instant — no real ``sleep`` anywhere.
"""

from __future__ import annotations

import pytest


class FakeClock:
    """A manually-advanced monotonic clock."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
