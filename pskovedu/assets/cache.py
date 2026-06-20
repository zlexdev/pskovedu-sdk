"""FileCache — URL-keyed binary file cache backed by the local filesystem.

Cache keys are URL-derived SHA-256 hashes so paths are always filesystem-safe.
TTL is applied at read time; stale entries are evicted lazily.

Usage::

    cache = FileCache(cache_dir=Path(".pskovedu_cache"), ttl_s=3600)
    data = cache.get(url)
    if data is None:
        data = await fetch(url)
        cache.put(url, data)
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from ..logging import get_logger

log = get_logger(__name__)


class FileCache:
    """Persistent URL → bytes cache backed by a local directory.

    Cache keys are SHA-256 hashes of the URL so no escaping is needed.
    Each entry is stored as two files:

    - ``<hash>.bin`` — raw content bytes.
    - ``<hash>.ts``  — unix timestamp (float) of when the entry was stored.

    Entries older than ``ttl_s`` seconds are considered stale on read.
    No background eviction — stale files are removed on access.

    Args:
        cache_dir: directory to store cache files in.  Created if absent.
        ttl_s: time-to-live in seconds (``0`` = entries never expire).
    """

    def __init__(self, cache_dir: Path, ttl_s: int = 3600) -> None:
        self._dir = cache_dir
        self._ttl = ttl_s
        self._dir.mkdir(parents=True, exist_ok=True)
        log.debug("assets.cache.init", dir=str(self._dir), ttl_s=ttl_s)

    def _key(self, url: str) -> str:
        """Compute a filesystem-safe cache key from ``url``."""
        return hashlib.sha256(url.encode()).hexdigest()

    def get(self, url: str) -> bytes | None:
        """Return cached bytes for ``url``, or ``None`` when absent / stale.

        Deletes stale entries lazily on access.

        Args:
            url: the full URL whose response to look up.
        """
        key = self._key(url)
        data_path = self._dir / f"{key}.bin"
        ts_path = self._dir / f"{key}.ts"

        if not data_path.exists():
            return None

        if self._ttl > 0 and ts_path.exists():
            try:
                stored_at = float(ts_path.read_text())
                age = time.time() - stored_at
                if age > self._ttl:
                    log.debug("assets.cache.stale", url=url, age_s=int(age))
                    self._evict(key)
                    return None
            except (ValueError, OSError):
                self._evict(key)
                return None

        try:
            return data_path.read_bytes()
        except OSError:
            return None

    def put(self, url: str, data: bytes) -> None:
        """Store *data* bytes under *url*.

        Writes atomically: data file first, then timestamp file.  A crash
        between the two writes leaves an entry with no timestamp, which is
        evicted on next read.

        Args:
            url: the URL whose response is being cached.
            data: raw response bytes.
        """
        key = self._key(url)
        data_path = self._dir / f"{key}.bin"
        ts_path = self._dir / f"{key}.ts"

        data_path.write_bytes(data)
        ts_path.write_text(str(time.time()))
        log.debug("assets.cache.put", url=url, size=len(data))

    def invalidate(self, url: str) -> None:
        """Remove the cached entry for *url* (no-op when absent).

        Args:
            url: the URL whose entry to remove.
        """
        self._evict(self._key(url))

    def clear(self) -> int:
        """Remove all cache entries."""
        count = 0
        for p in self._dir.glob("*.bin"):
            ts = self._dir / f"{p.stem}.ts"
            try:
                p.unlink(missing_ok=True)
                ts.unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
        log.info("assets.cache.cleared", count=count)
        return count

    def _evict(self, key: str) -> None:
        (self._dir / f"{key}.bin").unlink(missing_ok=True)
        (self._dir / f"{key}.ts").unlink(missing_ok=True)
