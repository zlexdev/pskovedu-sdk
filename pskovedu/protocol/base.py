"""Protocol ABC — wire-encoding abstraction for the pskovedu SDK.

Every endpoint is encoded / decoded by a concrete ``Protocol`` implementation.
REST is the default; Ext.Direct, X1, and SSE are siblings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..exceptions import ProtocolError  # noqa: F401 — re-exported for convenience

if TYPE_CHECKING:
    from ..config import ClientConfig
    from ..methods._base import BaseMethod


@dataclass
class PreparedRequest:
    """A fully resolved HTTP request ready for the transport layer.

    Attributes:
        method: HTTP verb (``"GET"``, ``"POST"``, …).
        url: absolute URL including host and path.
        headers: request headers dict.
        params: URL query-string parameters (pre-encoded values).
        body: request body; either a JSON-serialisable object or ``None``.
        timeout_s: per-request timeout override; ``None`` uses ``ClientConfig`` default.
    """

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body: Any = None
    timeout_s: float | None = None


@dataclass
class RawResponse:
    """Raw HTTP response from the transport layer.

    Attributes:
        status: HTTP status code.
        headers: response headers dict (lowercase keys).
        content: raw response body bytes.
        text: response body decoded as UTF-8 (may be empty string for binary).
        json_body: parsed JSON object, or ``None`` if the body is not JSON.
    """

    status: int
    headers: dict[str, str]
    content: bytes
    text: str
    json_body: Any = None


class Protocol(ABC):
    """Knows how to encode a method-class into a ``PreparedRequest`` and decode the response.

    Concrete implementations: ``RestProtocol``, ``ExtDirectProtocol``,
    ``X1Protocol``, ``SseProtocol``.

    The session funnel calls::

        prepared = protocol.build_request(method, config, host_base_url)
        raw = await transport.send(prepared)
        result = protocol.decode_response(method, raw)
    """

    @classmethod  # noqa: B027
    def validate_subclass(cls, method_cls: type[BaseMethod]) -> None:  # type: ignore[type-arg]
        """Validate that *method_cls* declares all class-vars required by this protocol.

        Called by ``BaseMethod.__init_subclass__`` at import time.  Raises
        :exc:`~pskovedu.exceptions.MethodDeclarationError` on any violation so
        misconfigured method-classes are caught before the first request.

        The base implementation is a no-op; each concrete protocol overrides it
        to check its own required class-vars.

        Args:
            method_cls: the ``BaseMethod`` subclass being registered.
        """

    @abstractmethod
    def build_request(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        config: ClientConfig,
        host: str,
    ) -> PreparedRequest:
        """Translate *method* into a wire-ready ``PreparedRequest``.

        Args:
            method: the bound (or unbound) method instance.
            config: active ``ClientConfig`` (used for timeouts, user-agent, …).
            host: base URL for the target host (e.g. ``"https://one.pskovedu.ru"``).
        """

    @abstractmethod
    def decode_response(
        self,
        method: BaseMethod,  # type: ignore[type-arg]
        raw: RawResponse,
    ) -> Any:
        """Decode *raw* into the typed return value declared by *method*.

        Args:
            method: the method instance (provides ``__returning__`` and protocol hints).
            raw: raw HTTP response from the transport layer.

        Raises:
            ProtocolError: on envelope-level errors (bad shape, exception envelope, …).
        """

    @abstractmethod
    def is_idempotent(self, method: BaseMethod) -> bool:  # type: ignore[type-arg]
        """Return ``True`` when the method is safe to retry on transient failures.

        Used by ``RetryPolicy`` to decide whether to retry a failed request.
        REST: ``GET``/``HEAD`` only.  Ext.Direct: read-only actions.  X1: queries.

        Args:
            method: the method instance to check.
        """
