"""Ties an algorithm to a backend.

:class:`RateLimiter` is the seam the FastAPI integrations depend on: it loads
per-key state from the backend, runs the (pure) algorithm, persists the new
state, and hands back a :class:`RateLimitResult`.
"""

from __future__ import annotations

from typing import Protocol

from ratelimiter.backend import Backend, InMemoryBackend
from ratelimiter.models import RateLimitResult


class Algorithm(Protocol):
    """The subset of the algorithm surface :class:`RateLimiter` relies on."""

    def initial_state(self): ...

    def check(self, state, cost: int = 1): ...


class RateLimiter:
    """Coordinates an algorithm and a backend for a set of keys."""

    def __init__(self, algorithm: Algorithm, backend: Backend | None = None) -> None:
        self.algorithm = algorithm
        self.backend: Backend = backend or InMemoryBackend()

    def check(self, key: str, cost: int = 1) -> RateLimitResult:
        """Evaluate one request for ``key`` and record the resulting state."""
        state = self.backend.get(key)
        if state is None:
            state = self.algorithm.initial_state()
        new_state, result = self.algorithm.check(state, cost)
        self.backend.set(key, new_state)
        return result
