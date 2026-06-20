"""SseProtocol — Server-Sent Events wire protocol.

Opens a ``GET`` request with ``Accept: text/event-stream`` and streams
events until the terminal event is received or the connection closes.

The actual line-by-line SSE parsing is in :mod:`pskovedu.transport.sse`
(:class:`~pskovedu.transport.sse.SseStream`).  This protocol layer builds
the request and connects the event stream to the method's ``__event_model__``
and ``__terminal_event__``.

Requires the ``[sse]`` extra (``httpx-sse`` or ``httpx`` streaming mode).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import MethodDeclarationError, ProtocolError
from .base import PreparedRequest, Protocol, RawResponse

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod


class SseProtocol(Protocol):
    """Wire protocol for ``GET`` SSE subscriptions (``Accept: text/event-stream``).

    Used by :class:`~pskovedu.methods.qr.SubscribeQr` and any future SSE
    endpoints.

    The ``build_request`` call returns a ``PreparedRequest`` with
    ``Accept: text/event-stream``.  The transport layer is expected to handle
    the SSE line stream via :class:`~pskovedu.transport.sse.SseStream`.

    ``decode_response`` is a **no-op** for SSE — responses are streamed
    event-by-event via the transport context manager, not decoded from a
    single ``RawResponse``.  Calling it raises :exc:`ProtocolError`.

    Subclasses declare:
    - ``__url__``: SSE endpoint path template.
    - ``__event_model__``: Pydantic model for individual events.
    - ``__terminal_event__``: event name that signals end of stream.
    """

    @classmethod
    def validate_subclass(cls, method_cls: type[BaseMethod]) -> None:  # type: ignore[type-arg]
        """Ensure ``__url__`` and ``__event_model__`` are declared.

        Args:
            method_cls: the ``SseSubscription`` subclass.

        Raises:
            MethodDeclarationError: when required class-vars are missing.
        """
        url = getattr(method_cls, "__url__", None)
        event_model = getattr(method_cls, "__event_model__", None)

        # Abstract bases may leave both as None — skip
        if url is None and event_model is None:
            return

        if url is not None and not isinstance(url, str):
            raise MethodDeclarationError(
                f"{method_cls.__name__}: __url__ must be a str, got {type(url).__name__}."
            )

    def build_request(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        config: ClientConfig,
        host: str,
    ) -> PreparedRequest:
        """Build a ``GET`` request for SSE streaming.

        Resolves path placeholders in ``__url__`` from ``__path_fields__`` (if
        declared), sets ``Accept: text/event-stream``, and returns the prepared
        request with no body.

        Args:
            method: bound ``SseSubscription`` instance.
            config: active client configuration.
            host: base URL for the ESIA/SSE host.

        Raises:
            ProtocolError: when ``__url__`` is missing or a path field is None.
        """
        url_template: str | None = getattr(method, "__url__", None)
        if not url_template:
            raise ProtocolError(f"{type(method).__name__} is missing __url__ for SSE subscription.")

        # Resolve path placeholders (same logic as RestProtocol)
        all_fields: dict[str, Any] = method.model_dump(by_alias=False, exclude_none=False)
        path_fields: frozenset[str] = getattr(method, "__path_fields__", frozenset())
        path_values: dict[str, str] = {}
        for name in path_fields:
            value = all_fields.get(name)
            if value is None:
                raise ProtocolError(
                    f"{type(method).__name__}: path field {name!r} is None; cannot build SSE URL."
                )
            path_values[name] = str(value)

        resolved_path = url_template.format(**path_values)
        full_url = host.rstrip("/") + resolved_path

        # Remaining non-path fields → query params
        params: dict[str, str] = {}
        for k, v in all_fields.items():
            if k not in path_fields and v is not None:
                params[k] = str(v)

        headers: dict[str, str] = {
            "User-Agent": config.user_agent,
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        return PreparedRequest(
            method="GET",
            url=full_url,
            headers=headers,
            params=params,
            body=None,
            timeout_s=None,  # SSE streams have no fixed timeout
        )

    def decode_response(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        raw: RawResponse,
    ) -> Any:
        """Not applicable for SSE — raises ``ProtocolError``.

        SSE responses are consumed event-by-event via the transport context
        manager, not as a single ``RawResponse``.  This method should never
        be called in normal operation.

        Raises:
            ProtocolError: always.
        """
        raise ProtocolError(
            f"SseProtocol.decode_response called for {type(method).__name__}; "
            "SSE responses are streamed via transport.sse.SseStream, "
            "not decoded from a single RawResponse."
        )

    def is_idempotent(self, method: BaseMethod) -> bool:  # type: ignore[type-arg]
        """Return ``True`` — SSE subscriptions are ``GET`` (safe to retry).

        Args:
            method: the method instance.
        """
        return True
