"""Pluggable state backends.

A backend stores per-key algorithm state (:class:`TokenBucketState` or
:class:`SlidingWindowState`). The default :class:`InMemoryBackend` is fine for
a single process; :class:`RedisBackend` documents the interface a distributed,
multi-process deployment would implement.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """Storage contract for rate-limiter state.

    Implementations map an opaque string ``key`` (e.g. a client IP or API
    key) to the algorithm's state object. ``get`` returns ``None`` for an
    unseen key so the caller can seed a fresh state.
    """

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, state: Any) -> None: ...


class InMemoryBackend:
    """Process-local, thread-safe backend backed by a plain dict.

    Suitable for a single-instance app or for tests. State is lost on restart
    and is not shared across processes/hosts.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            return self._store.get(key)

    def set(self, key: str, state: Any) -> None:
        with self._lock:
            self._store[key] = state

    def clear(self) -> None:
        """Drop all stored state (handy in tests)."""
        with self._lock:
            self._store.clear()


class RedisBackend:
    """Reference interface for a distributed Redis-backed store.

    This is a *documented interface*, not a battle-tested implementation, and
    is intentionally left unwired to keep the toolkit fully offline. It shows
    the shape a real deployment would take.

    Design notes for a production implementation:

    * **Serialization.** State objects (dataclasses) serialize cleanly to JSON.
      Store under a namespaced key such as ``ratelimit:{key}`` with a TTL a bit
      longer than the window so idle keys self-evict.
    * **Atomicity.** The naive get -> compute -> set cycle races under
      concurrency across processes. A correct implementation performs the
      read-modify-write atomically inside a single **Lua script** (or, for the
      sliding window, a ``ZADD`` / ``ZREMRANGEBYSCORE`` / ``ZCARD`` pipeline in
      a ``MULTI``/``EXEC`` transaction) so the token math cannot interleave.
    * **Clock.** Prefer Redis server ``TIME`` as the single source of truth so
      every app instance agrees on "now" regardless of host clock skew.

    Example (illustrative — requires ``redis`` and a running server)::

        import json
        from redis import Redis

        class RedisBackend:
            def __init__(self, client: Redis, ttl_seconds: int, prefix="ratelimit"):
                self._client = client
                self._ttl = ttl_seconds
                self._prefix = prefix

            def get(self, key):
                raw = self._client.get(f"{self._prefix}:{key}")
                return json.loads(raw) if raw else None

            def set(self, key, state):
                self._client.set(
                    f"{self._prefix}:{key}",
                    json.dumps(state.__dict__),
                    ex=self._ttl,
                )
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            "RedisBackend is a documented reference interface only. Implement "
            "get/set against your Redis client using atomic Lua scripts; see "
            "the class docstring for the recommended approach."
        )

    def get(self, key: str) -> Any | None:  # pragma: no cover - interface only
        raise NotImplementedError

    def set(self, key: str, state: Any) -> None:  # pragma: no cover - interface only
        raise NotImplementedError
