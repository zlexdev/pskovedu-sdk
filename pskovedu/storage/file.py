"""FileStorage — JSON-on-disk persistence for token + cookie jars.

Writes a single JSON file per storage namespace.  Thread-safe for single-process
use (no cross-process locking); use a Redis backend for multi-process deployments.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .base import BaseStorage


class FileStorage(BaseStorage[Any]):
    """Async JSON-file storage.

    All keys share one JSON file at *path*.  Reads and writes are wrapped in
    ``asyncio.to_thread`` to avoid blocking the event loop on disk I/O.

    Token + cookie jars serialised here must be JSON-compatible dicts.  The
    ``auth/`` layer is responsible for converting its internal state to/from dict
    before calling ``set``/``get``.

    Args:
        path: path to the JSON file (created on first write if it does not exist).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()

    def _read_sync(self) -> dict[str, Any]:
        """Synchronously read and parse the JSON file.  Returns ``{}`` if missing."""
        if not self._path.exists():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
            return dict(json.loads(text))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_sync(self, data: dict[str, Any]) -> None:
        """Synchronously write *data* to the JSON file, creating parent dirs."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def get(self, key: str) -> Any | None:
        """Read the stored value for *key* from disk.

        Args:
            key: storage key.
        """
        async with self._lock:
            data = await asyncio.to_thread(self._read_sync)
        return data.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Persist *value* under *key* to disk.

        Args:
            key: storage key.
            value: JSON-serialisable value to persist.
        """
        async with self._lock:
            data = await asyncio.to_thread(self._read_sync)
            data[key] = value
            await asyncio.to_thread(self._write_sync, data)

    async def delete(self, key: str) -> None:
        """Remove *key* from the JSON file (no-op when absent).

        Args:
            key: storage key to remove.
        """
        async with self._lock:
            data = await asyncio.to_thread(self._read_sync)
            if key in data:
                del data[key]
                await asyncio.to_thread(self._write_sync, data)
