"""HttpxSession — concrete BaseSession backed by httpx.AsyncClient.

Shares one ``httpx.AsyncClient`` (connection pool) across all accounts while
maintaining a per-account cookie jar via httpx's ``Cookies`` object.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

from ..protocol.base import PreparedRequest, RawResponse
from ..transport.retry import RetryPolicy
from .base import BaseSession

if TYPE_CHECKING:
    from ..config import ClientConfig


class HttpxSession(BaseSession):
    """Concrete session implementation using ``httpx.AsyncClient``.

    A single ``httpx.AsyncClient`` is shared for connection-pool reuse.
    Cookie jars are managed externally by the auth layer and injected via
    the ``BaseSession._inject_cookies`` path.

    Args:
        retry_policy: optional ``RetryPolicy``; defaults to ``RetryPolicy()``.
        client: optional pre-built ``httpx.AsyncClient``; one is created if
            ``None`` (useful for test injection).
    """

    def __init__(
        self,
        retry_policy: RetryPolicy | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(retry_policy=retry_policy)
        self._owns_client = client is None
        self._http: httpx.AsyncClient = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        )

    async def _send(
        self,
        prepared: PreparedRequest,
        config: ClientConfig,
    ) -> RawResponse:
        """Perform the HTTP call via httpx and return a ``RawResponse``.

        Args:
            prepared: fully resolved request.
            config: client configuration (timeout fallback).
        """
        timeout = prepared.timeout_s if prepared.timeout_s is not None else config.request_timeout_s

        content: bytes | None = None
        if prepared.body is not None:
            content = json.dumps(prepared.body, ensure_ascii=False).encode("utf-8")

        response = await self._http.request(
            method=prepared.method,
            url=prepared.url,
            headers=prepared.headers,
            params=prepared.params or None,
            content=content,
            timeout=timeout,
        )

        # Attempt JSON parse; don't fail hard if not JSON
        json_body = None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or "text/json" in content_type:
            try:
                json_body = response.json()
            except Exception:
                json_body = None

        return RawResponse(
            status=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            text=response.text,
            json_body=json_body,
        )

    async def _open_sse(self, prepared: PreparedRequest) -> httpx.Response:
        """Open a streaming ``httpx.Response`` for SSE consumption.

        Uses ``send(..., stream=True)`` so the response body is left open for
        line-by-line iteration; :class:`~pskovedu.transport.sse.SseStream` owns
        closing it via ``aclose()``.

        Args:
            prepared: fully resolved request (``GET`` with SSE headers).
        """
        request = self._http.build_request(
            method=prepared.method,
            url=prepared.url,
            headers=prepared.headers,
            params=prepared.params or None,
        )
        return await self._http.send(request, stream=True)

    async def close(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` if we own it."""
        if self._owns_client:
            await self._http.aclose()
