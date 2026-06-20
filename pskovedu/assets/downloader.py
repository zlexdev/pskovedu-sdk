"""AssetDownloader — session-aware binary asset fetcher with FileCache.

Downloads binary assets (avatars, XLS exports) using the authenticated
httpx session and caches responses by URL hash.

The downloader is DI-injected into the client; it does not hold credentials
itself but receives a callable that returns the active httpx session.

Usage::

    dl = AssetDownloader(session_getter=lambda: client.session, cache=file_cache)
    avatar_bytes = await dl.download(url)
    xls = await dl.download_xls(url, filename="diary.xls")
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..logging import get_logger
from .cache import FileCache
from .xls import XlsExport

log = get_logger(__name__)


class AssetDownloader:
    """Downloads binary assets via the authenticated session with optional caching.

    Args:
        session_getter: zero-arg callable that returns the current ``httpx.AsyncClient``
            or session object.  Called lazily on each download so it always reflects
            the active (possibly refreshed) session.
        cache: :class:`~pskovedu.assets.cache.FileCache` instance, or ``None`` to
            disable caching.
        timeout_s: per-download timeout in seconds (default 60 s).
    """

    def __init__(
        self,
        session_getter: Callable[[], Any],
        cache: FileCache | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self._session_getter = session_getter
        self._cache = cache
        self._timeout_s = timeout_s

    async def download(self, url: str, *, bypass_cache: bool = False) -> bytes:
        """Download *url* and return raw bytes.

        Checks :attr:`cache` before making a network call.  Stores the result
        in the cache on success (when caching is enabled).

        Args:
            url: absolute URL to download.
            bypass_cache: when ``True``, skip cache read (but still write on success).

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
        """
        if self._cache is not None and not bypass_cache:
            cached = self._cache.get(url)
            if cached is not None:
                log.debug("assets.downloader.cache_hit", url=url, size=len(cached))
                return cached

        log.debug("assets.downloader.fetch", url=url)
        session = self._session_getter()
        response = await session.get(url, timeout=self._timeout_s)
        response.raise_for_status()
        data: bytes = response.content

        if self._cache is not None:
            self._cache.put(url, data)

        log.info("assets.downloader.fetched", url=url, size=len(data))
        return data

    async def download_xls(
        self,
        url: str,
        filename: str = "export.xls",
        *,
        bypass_cache: bool = False,
    ) -> XlsExport:
        """Download *url* and wrap the result in an :class:`~pskovedu.assets.xls.XlsExport`.

        Args:
            url: absolute URL of the XLS export endpoint.
            filename: suggested filename for the export.
            bypass_cache: skip cache read when ``True``.
        """
        data = await self.download(url, bypass_cache=bypass_cache)
        return XlsExport(data=data, filename=filename)
