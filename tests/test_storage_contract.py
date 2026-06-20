"""BaseStorageContract — abstract pytest suite for all BaseStorage implementations.

Every concrete backend (MemoryStorage, FileStorage, …) must subclass this and
supply a ``storage`` fixture.  Running the suite proves identical behaviour.

Usage::

    class TestMemoryStorage(BaseStorageContract):
        @pytest.fixture
        def storage(self) -> BaseStorage[str]:
            return MemoryStorage()
"""

from __future__ import annotations

import pytest

from pskovedu.storage.base import BaseStorage
from pskovedu.storage.memory import MemoryStorage


class BaseStorageContract:
    """Abstract contract test suite — subclass and implement the ``storage`` fixture."""

    @pytest.fixture
    def storage(self) -> BaseStorage[str]:
        raise NotImplementedError("Subclass must supply a storage fixture.")

    async def test_get_missing_returns_none(self, storage: BaseStorage[str]) -> None:
        assert await storage.get("nonexistent") is None

    async def test_set_and_get_roundtrip(self, storage: BaseStorage[str]) -> None:
        await storage.set("key", "value")
        assert await storage.get("key") == "value"

    async def test_set_overwrites_existing(self, storage: BaseStorage[str]) -> None:
        await storage.set("key", "v1")
        await storage.set("key", "v2")
        assert await storage.get("key") == "v2"

    async def test_delete_removes_key(self, storage: BaseStorage[str]) -> None:
        await storage.set("key", "value")
        await storage.delete("key")
        assert await storage.get("key") is None

    async def test_delete_missing_is_noop(self, storage: BaseStorage[str]) -> None:
        await storage.delete("nonexistent")  # must not raise

    async def test_independent_keys(self, storage: BaseStorage[str]) -> None:
        await storage.set("a", "1")
        await storage.set("b", "2")
        assert await storage.get("a") == "1"
        assert await storage.get("b") == "2"
        await storage.delete("a")
        assert await storage.get("a") is None
        assert await storage.get("b") == "2"


class TestMemoryStorage(BaseStorageContract):
    """MemoryStorage must satisfy the full contract."""

    @pytest.fixture
    def storage(self) -> BaseStorage[str]:
        return MemoryStorage()
