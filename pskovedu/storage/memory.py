"""MemoryStorage — default in-process key-value store (no persistence)."""

from __future__ import annotations

from typing import Any

from .base import BaseStorage


class MemoryStorage(BaseStorage[Any]):
    """In-process storage backed by a plain ``dict``.

    All data is lost when the process exits.  This is the SDK default —
    use ``FileStorage`` (or a redis backend) for cross-restart persistence.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        """Return the value for *key*, or ``None`` if absent."""
        return self._store.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*."""
        self._store[key] = value

    async def delete(self, key: str) -> None:
        """Remove *key* (no-op when absent)."""
        self._store.pop(key, None)
