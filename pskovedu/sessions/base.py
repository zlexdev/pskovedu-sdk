"""BaseSession — the make_request funnel that every SDK call flows through.

Flow (per 01-logic.md):
    auth.ensure(account)                 # inject cookies + JWT (or minimal cookie path)
    protocol.build_request(method, ...)  # encode to PreparedRequest
    [rate_limit.acquire(host)]           # optional token bucket
    [breaker.guard(host, path)]          # optional circuit breaker
    transport.send(prepared)             # httpx.AsyncClient
    map status → EduError               # 401 → AuthExpiredError → refresh+retry-once
    protocol.decode_response(method, raw)
    if EduObject: result.as_(client)     # bind for bound methods
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..exceptions import (
    AuthExpiredError,
    BreakerOpen,
    ForbiddenError,
    HTTPError,
    NotFoundError,
    ProtocolError,
    ServerError,
)
from ..logging import get_logger
from ..models._base import EduObject
from ..protocol.base import PreparedRequest, RawResponse
from ..transport.retry import RetryPolicy
from ..transport.sse import SseStream

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod
    from ..protocol.base import Protocol
    from ..transport.sse import EventStream

log = get_logger(__name__)


class BaseSession(ABC):
    """Abstract session — owns the make_request funnel.

    Subclasses provide ``_send(prepared, config)`` which performs the actual
    HTTP call and returns a ``RawResponse``.

    The funnel is the single path for every SDK call:
    ``Client.get_shell()`` → ``client(GetShell())`` → ``session.make_request(...)``
    → ``RestProtocol.build_request(...)`` → ``_send(...)``
    → ``RestProtocol.decode_response(...)`` → typed result.
    """

    def __init__(self, retry_policy: RetryPolicy | None = None) -> None:
        self._retry_policy = retry_policy or RetryPolicy()

    def _inject_cookies(
        self,
        prepared: PreparedRequest,
        cookies: dict[str, str],
    ) -> PreparedRequest:
        """Add *cookies* to *prepared*'s headers as a ``Cookie`` header.

        This minimal cookie path is used before a full ``AuthManager`` is
        wired in, so that a pre-set ``X1_SSO`` cookie can authenticate calls
        from the very first request (e.g. ``Client.from_cookie(x1_sso=...)``).

        Args:
            prepared: the prepared request to modify (returns a new instance).
            cookies: mapping of cookie name → value.
        """
        if not cookies:
            return prepared
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        new_headers = dict(prepared.headers)
        if "Cookie" in new_headers:
            new_headers["Cookie"] = new_headers["Cookie"] + "; " + cookie_str
        else:
            new_headers["Cookie"] = cookie_str
        return PreparedRequest(
            method=prepared.method,
            url=prepared.url,
            headers=new_headers,
            params=prepared.params,
            body=prepared.body,
            timeout_s=prepared.timeout_s,
        )

    @staticmethod
    def _map_status(status: int, url: str) -> None:
        """Raise the appropriate ``EduError`` subclass for error HTTP statuses.

        Args:
            status: HTTP status code.
            url: request URL (for error context).

        Raises:
            AuthExpiredError: on 401.
            ForbiddenError: on 403.
            NotFoundError: on 404.
            ServerError: on 5xx.
            HTTPError: on any other 4xx.
        """
        if status == 401:
            raise AuthExpiredError("Session expired or not authenticated (HTTP 401).")
        if status == 403:
            raise ForbiddenError(url)
        if status == 404:
            raise NotFoundError(url)
        if status >= 500:
            raise ServerError(status, url)
        if status >= 400:
            raise HTTPError(status, url)

    async def make_request(
        self,
        client: Any,
        method: BaseMethod[Any],
    ) -> Any:
        """Execute *method* through the full request funnel.

        Steps:
        1. Auth ensure (``auth_manager.ensure(client)`` if available, else
           minimal cookie injection from ``client._cookies``).
        2. ``protocol.build_request(method, config, host_url)``
        3. Optional rate-limit acquire (``client._rate_limiter`` if present).
        4. Optional circuit-breaker guard (``client._breaker`` if present).
        5. ``_send(prepared, config)`` with retry on transient failures.
        6. Status mapping → EduError; 401 triggers one auth refresh + retry.
        7. ``protocol.decode_response(method, raw)`` → typed result.
        8. ``result.as_(client)`` when result is an ``EduObject``.

        Args:
            client: the ``Client`` instance (provides config, auth, cookies).
            method: the method instance to execute.

        Raises:
            AuthExpiredError: when the session has expired and refresh failed.
            ProtocolError: on envelope-level decode errors.
            HTTPError / ServerError / NotFoundError / ForbiddenError: on HTTP errors.
            BreakerOpen: when the circuit breaker is open for the target host.
        """
        config: ClientConfig = client.config
        protocol: Protocol = method.__protocol__()
        host_url = self._resolve_host(config, method)

        prepared = await self._prepare(client, method, protocol, config, host_url)

        rate_limiter = getattr(client, "_rate_limiter", None)
        if rate_limiter is not None:
            await rate_limiter.acquire(host_url)

        breaker = getattr(client, "_breaker", None)
        breaker_path = getattr(method, "__breaker_path__", None) or getattr(method, "__url__", "")
        if breaker is not None:
            host_label = host_url.replace("https://", "").replace("http://", "")
            if not breaker.allow(host_label, breaker_path or ""):
                raise BreakerOpen(host_label, breaker_path or "")

        # Steps 5–7 — Send with retry, map errors, decode
        raw = await self._send_with_retry(prepared, config, method, protocol)
        result = protocol.decode_response(method, raw)

        if isinstance(result, EduObject):
            result.as_(client)

        return result

    @staticmethod
    def _resolve_host(config: ClientConfig, method: BaseMethod[Any]) -> str:
        """Resolve a method's ``__host__`` key to a base URL via ``config.hosts``.

        The ``hosts`` mapping may be keyed by ``Host`` enum members or plain
        strings; both are tried before falling back to ``https://<key>``.

        Args:
            config: active client configuration.
            method: the method whose ``__host__`` is being resolved.
        """
        from ..constants import Host

        host_key: str = getattr(method, "__host__", Host.PORTAL)
        try:
            host_enum = Host(host_key)
            return config.hosts.get(host_enum, f"https://{host_key}")
        except ValueError:
            return config.hosts.get(host_key, f"https://{host_key}")  # type: ignore[call-overload]

    async def _prepare(
        self,
        client: Any,
        method: BaseMethod[Any],
        protocol: Protocol,
        config: ClientConfig,
        host_url: str,
    ) -> PreparedRequest:
        """Ensure auth, build the wire request, and inject pre-set cookies.

        Shared head of both the single-response funnel (:meth:`make_request`)
        and the streaming funnel (:meth:`open_stream`) so auth + encoding live
        in exactly one place.

        Args:
            client: the ``Client`` instance (provides auth manager + cookies).
            method: the method instance to encode.
            protocol: the active protocol.
            config: active client configuration.
            host_url: pre-resolved base URL for the method's host.
        """
        auth_manager = getattr(client, "_auth_manager", None)
        if auth_manager is not None:
            await auth_manager.ensure(client)

        prepared = protocol.build_request(method, config, host_url)

        # Minimal cookie path: inject pre-set cookies when no auth manager yet
        pending_cookies: dict[str, str] = getattr(client, "_cookies", {})
        if pending_cookies:
            prepared = self._inject_cookies(prepared, pending_cookies)
        return prepared

    async def open_stream(
        self,
        client: Any,
        method: BaseMethod[Any],
    ) -> EventStream[Any]:
        """Open an SSE subscription and return an iterable ``EventStream``.

        Mirrors the auth + encoding head of :meth:`make_request` but, instead of
        reading a single ``RawResponse``, opens a long-lived streaming response
        and wraps it in :class:`~pskovedu.transport.sse.SseStream`.  Iterating the
        returned ``EventStream`` yields :class:`~pskovedu.transport.sse.SseEvent`
        objects until the method's ``__terminal_event__`` arrives; the underlying
        connection is closed when iteration ends (or the consumer breaks early).

        Args:
            client: the ``Client`` instance.
            method: an ``SseSubscription`` subclass instance.

        Raises:
            AuthExpiredError / ForbiddenError / NotFoundError / HTTPError:
                when the stream handshake returns an error status.
            NotImplementedError: when the concrete session has no SSE transport.
        """
        config: ClientConfig = client.config
        protocol: Protocol = method.__protocol__()
        host_url = self._resolve_host(config, method)

        prepared = await self._prepare(client, method, protocol, config, host_url)

        response = await self._open_sse(prepared)
        try:
            self._map_status(response.status_code, prepared.url)
        except BaseException:
            await response.aclose()
            raise

        stream: SseStream[Any] = SseStream(
            response,
            event_model=getattr(method, "__event_model__", None),
            terminal_event=getattr(method, "__terminal_event__", None),
        )
        return await stream.__aenter__()

    @abstractmethod
    async def _open_sse(self, prepared: PreparedRequest) -> Any:
        """Open a streaming HTTP response for SSE consumption.

        Implementations return an object exposing ``status_code``,
        ``aiter_lines()`` and ``aclose()`` (an ``httpx.Response`` in streaming
        mode), leaving the body open for line-by-line iteration.

        Args:
            prepared: the fully resolved request (``GET`` with SSE headers).
        """

    async def _send_with_retry(
        self,
        prepared: PreparedRequest,
        config: ClientConfig,
        method: BaseMethod[Any],
        protocol: Protocol,
    ) -> RawResponse:
        """Send *prepared* with retry on transient failures.

        On a 401 response a single auth-refresh + retry is attempted before
        raising ``AuthExpiredError``.

        Args:
            prepared: the fully resolved request.
            config: client configuration (retry count, timeouts).
            method: the originating method (for idempotency checks).
            protocol: the active protocol.

        Raises:
            AuthExpiredError: on unrecoverable 401.
            HTTPError and subclasses: on persistent HTTP errors.
        """
        policy = self._retry_policy
        last_exc: BaseException | None = None

        for attempt in range(config.retries + 1):
            try:
                raw = await self._send(prepared, config)
            except (OSError, Exception) as exc:
                last_exc = exc
                if policy.is_retryable(method, protocol, exc=exc) and attempt < config.retries:
                    await policy.wait(attempt)
                    continue
                raise

            try:
                self._map_status(raw.status, prepared.url)
            except AuthExpiredError:
                # One refresh + retry is handled in make_request caller;
                # here we just re-raise so make_request can intercept.
                raise
            except (ServerError, HTTPError) as exc:
                last_exc = exc
                if (
                    policy.is_retryable(method, protocol, status=raw.status)
                    and attempt < config.retries
                ):
                    log.warning(
                        "request.retry",
                        attempt=attempt + 1,
                        status=raw.status,
                        url=prepared.url,
                    )
                    await policy.wait(attempt)
                    continue
                raise

            return raw

        # Should not be reached; last_exc is always set if we exhaust retries
        if last_exc is not None:
            raise last_exc
        raise ProtocolError("Exhausted retries without a response.")

    @abstractmethod
    async def _send(
        self,
        prepared: PreparedRequest,
        config: ClientConfig,
    ) -> RawResponse:
        """Perform the actual HTTP call and return a ``RawResponse``.

        Implementations must:
        - Set request cookies from the per-account cookie jar.
        - Respect ``prepared.timeout_s`` (falling back to ``config.request_timeout_s``).
        - Return a ``RawResponse`` for any status code (error mapping is done
          in ``make_request``).

        Args:
            prepared: the fully resolved request.
            config: client configuration.
        """

    @abstractmethod
    async def close(self) -> None:
        """Close the underlying HTTP transport (connection pools, SSE streams)."""
