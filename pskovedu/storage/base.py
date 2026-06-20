"""BaseStorage[T] — abstract key-value store for token + cookie persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

T = TypeVar("T")


class BaseStorage[T](ABC):
    """Abstract async key-value store for SDK state persistence.

    Used to persist session tokens and cookie jars across process restarts.
    The default implementation is ``MemoryStorage`` (in-process, no persistence).
    ``FileStorage`` writes JSON to disk.  Redis and other backends are external extras.

    Type parameter ``T`` is the stored value type (typically a ``dict`` or
    Pydantic model that can round-trip through JSON).
    """

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """Retrieve the value for *key*.

        Args:
            key: storage key (e.g. account identifier or ``"session"``).
        """

    @abstractmethod
    async def set(self, key: str, value: T) -> None:
        """Store *value* under *key*, overwriting any existing entry.

        Args:
            key: storage key.
            value: value to store; must be JSON-serialisable for ``FileStorage``.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the entry for *key* (no-op when the key does not exist).

        Args:
            key: storage key to remove.
        """
