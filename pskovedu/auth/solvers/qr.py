"""QrSolver — drive the SSE QR subscribe stream to obtain an ``X1_SSO`` cookie.

The portal provides a QR-code-based login flow via a Server-Sent Events (SSE)
endpoint::

    GET /qr-delegate/qr/subscribe/{uuid}    (text/event-stream)

The stream emits :class:`~pskovedu.models.esia.QrEvent` frames via
:meth:`~pskovedu.sessions.base.BaseSession.open_stream`.  Each raw SSE frame
arrives as an :class:`~pskovedu.transport.sse.SseEvent` wrapper; the typed
payload is in ``SseEvent.parsed`` (a :class:`~pskovedu.models.esia.QrEvent`
when ``__event_model__`` is wired, or ``None`` if the frame could not be
parsed).

When a ``qr-auth-confirmed`` event arrives its one-time code is passed to
:class:`~pskovedu.methods.qr.ConfirmQr` which returns a
:class:`~pskovedu.models.esia.QrConfirm` model whose ``x1_sso`` field is the
``X1_SSO`` session token.

:class:`QrSolver` wires this flow as a :class:`ChallengeSolver` implementation
so :meth:`~pskovedu.auth.manager.AuthManager.login_with_qr` can use it::

    solver = QrSolver(uuid=uuid, display_cb=lambda url: print(url))
    await manager.login_with_qr(client, solver=solver)

**Note on imports:** this module imports from ``pskovedu.methods.qr`` which is
written by a concurrent agent.  Import errors surface as ``ImportError`` at
runtime if the sibling module is absent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ...exceptions import AuthError
from ...logging import get_logger
from ...models.esia import QrEvent, QrEventKind
from .base import ChallengeSolver

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

# Maximum time to wait for QR confirmation
_DEFAULT_TIMEOUT_S = 120.0
# Maximum number of error events before giving up
_MAX_ERRORS = 3

DisplayCallback = Callable[[str], None | Coroutine[Any, Any, None]]
"""Callable invoked with the QR URL / code for display (sync or async)."""


class QrSolver(ChallengeSolver):
    """Drive the SSE QR authentication stream to obtain an ``X1_SSO`` cookie.

    Opens the QR subscribe SSE stream (``GET /qr-delegate/qr/subscribe/{uuid}``),
    calls *display_cb* with the QR URL so the caller can render it, then waits
    for a ``qr-auth-confirmed`` event.  The one-time code from that event is
    passed to the QR confirm endpoint to exchange for ``X1_SSO``.

    Args:
        uuid: the QR session UUID (obtained from a preceding ``POST /qr/start``
            call, issued by ``pskovedu.methods.qr.StartQr``).
        display_cb: optional callable invoked with the QR URL string so the
            caller can display it (e.g. print to terminal or render as image).
            May be sync or async.
        timeout_s: maximum seconds to wait for QR confirmation.
    """

    def __init__(
        self,
        uuid: UUID | str,
        display_cb: DisplayCallback | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._uuid: str = str(uuid) if isinstance(uuid, UUID) else str(UUID(uuid))
        self._display_cb = display_cb
        self._timeout_s = timeout_s

    async def solve(self, client: Any) -> str:
        """Drive the QR SSE stream and return the resulting ``X1_SSO`` cookie.

        Args:
            client: the ``Client`` instance — used to call the QR subscribe
                and confirm methods from ``pskovedu.methods.qr``.

        Raises:
            AuthError: when the stream times out, exceeds the error limit,
                or the confirm call does not return a cookie.
            ChallengeRequired: when the server signals a CAPTCHA requirement.
            ImportError: when ``pskovedu.methods.qr`` or
                ``pskovedu.protocol.sse`` are not yet available.
        """
        # Late import — pskovedu.methods.qr is written by a concurrent agent
        try:
            from ...methods import qr as qr_methods
        except ImportError as exc:
            raise ImportError(
                "pskovedu.methods.qr is not available — ensure the methods agent has written qr.py"
            ) from exc

        log.info("qr_solver.start", uuid=str(self._uuid))

        # Invoke display callback with QR URL if provided
        qr_url = self._build_qr_url(client)
        if self._display_cb is not None:
            result = self._display_cb(qr_url)
            if asyncio.iscoroutine(result):
                await result

        # Subscribe to the SSE stream with a timeout
        try:
            x1_sso = await asyncio.wait_for(
                self._stream_until_confirmed(client, qr_methods),
                timeout=self._timeout_s,
            )
        except TimeoutError as exc:
            raise AuthError(f"QR authentication timed out after {self._timeout_s}s") from exc

        log.info("qr_solver.confirmed", uuid=str(self._uuid))
        return x1_sso

    def _build_qr_url(self, client: Any) -> str:
        """Build the QR display URL from client config and the UUID."""
        config = getattr(client, "config", None)
        hosts: dict[Any, str] = getattr(config, "hosts", {})
        # Try to resolve the portal host
        try:
            from ...constants import Host

            portal_base = hosts.get(Host.PORTAL, "https://one.pskovedu.ru")
        except ImportError:
            portal_base = "https://one.pskovedu.ru"
        return f"{portal_base}/qr-delegate/qr/{self._uuid}"

    async def _stream_until_confirmed(self, client: Any, qr_methods: Any) -> str:
        """Consume SSE events until ``qr-auth-confirmed`` or fatal error.

        Opens the QR subscribe SSE stream via
        ``client.session.open_stream(client, SubscribeQr(uuid=...))``.  Each
        iteration yields an :class:`~pskovedu.transport.sse.SseEvent` wrapper;
        the typed payload is in ``event.parsed`` (a
        :class:`~pskovedu.models.esia.QrEvent` or ``None`` when the frame
        cannot be parsed — those are silently skipped).

        On ``qr-auth-confirmed`` the one-time code is sent to
        :class:`~pskovedu.methods.qr.ConfirmQr`; the returned
        :class:`~pskovedu.models.esia.QrConfirm` model's ``x1_sso`` field is
        returned as the ``X1_SSO`` cookie value.

        Args:
            client: the ``Client`` instance.
            qr_methods: the imported ``pskovedu.methods.qr`` module.

        Raises:
            AuthError: on ``qr-error`` events (after ``_MAX_ERRORS``
                threshold), on unexpected stream end, or when ``ConfirmQr``
                returns an empty ``x1_sso``.
            ImportError: when ``pskovedu.methods.qr.SubscribeQr`` is absent.
        """
        error_count = 0

        subscribe_cls = getattr(qr_methods, "SubscribeQr", None)
        confirm_cls = getattr(qr_methods, "ConfirmQr", None)

        if subscribe_cls is None:
            raise ImportError("pskovedu.methods.qr.SubscribeQr not found")
        if confirm_cls is None:
            raise ImportError("pskovedu.methods.qr.ConfirmQr not found")

        # Open the SSE stream via the session layer (not via client.__call__)
        stream = await client.session.open_stream(client, subscribe_cls(uuid=self._uuid))
        async for sse_event in stream:
            # Each sse_event is an SseEvent wrapper; .parsed is QrEvent or None
            qr_event: QrEvent | None = sse_event.parsed if isinstance(sse_event.parsed, QrEvent) else None
            if qr_event is None:
                log.debug("qr_solver.unparsed_event", raw=repr(sse_event))
                continue

            if qr_event.kind in (QrEventKind.PING, QrEventKind.WAITING):
                log.debug("qr_solver.keepalive", kind=qr_event.kind)
                continue

            if qr_event.kind == QrEventKind.QR_ERROR:
                error_count += 1
                log.warning("qr_solver.error_event", count=error_count, data=qr_event.data)
                if error_count >= _MAX_ERRORS:
                    raise AuthError(f"QR stream emitted {error_count} error events — giving up")
                continue

            if qr_event.kind == QrEventKind.QR_AUTH_CONFIRMED:
                code = qr_event.code or qr_event.data
                if not code:
                    raise AuthError("qr-auth-confirmed event has no code")

                # Exchange the one-time code for X1_SSO via ConfirmQr endpoint
                confirm_result = await client(confirm_cls(code=code))
                x1_sso: str | None = confirm_result.x1_sso
                if not x1_sso:
                    raise AuthError("QR confirm returned empty X1_SSO")
                return x1_sso

        raise AuthError("QR SSE stream ended without a confirmed event")
