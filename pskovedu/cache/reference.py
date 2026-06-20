from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

__all__ = ["ReferenceCache"]


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class ReferenceCache:
    """Per-account TTL cache for reference data.

    Caches rarely-changing API responses (grades, teachers, periods, X1 model
    map) so repeated calls within the TTL window skip the network round-trip.
    """

    def __init__(self, ttl_s: float = 300.0) -> None:
        self._ttl = ttl_s
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        """Return cached value if not expired, else None."""
        entry = self._store.get(key)
        if entry is None or time.monotonic() > entry.expires_at:
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* with TTL expiry."""
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.monotonic() + self._ttl,
        )

    def invalidate(self, key: str) -> None:
        """Remove a single key (no-op if absent)."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Evict all cached entries."""
        self._store.clear()
