"""EduError hierarchy for the pskovedu SDK.

All exceptions carry structured args (never pre-formatted text) and are
chained with ``raise XxxError(...) from e`` at boundaries.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import ClassVar


class ErrorCode(StrEnum):
    """Stable machine-readable codes for programmatic error classification.

    Use these in logs, monitoring, and error-mapping layers instead of
    catching by class name alone.
    """

    CONFIG_INVALID = "EDU_CONFIG_INVALID"
    METHOD_DECLARATION = "EDU_METHOD_DECLARATION"
    METHOD_NOT_BOUND = "EDU_METHOD_NOT_BOUND"
    MODEL_NOT_BOUND = "EDU_MODEL_NOT_BOUND"
    PROTOCOL_ERROR = "EDU_PROTOCOL_ERROR"
    EXT_DIRECT_ERROR = "EDU_EXT_DIRECT"
    X1_ERROR = "EDU_X1_ERROR"
    HTML_PARSE_ERROR = "EDU_HTML_PARSE"
    HTTP_ERROR = "EDU_HTTP_ERROR"
    SERVER_ERROR = "EDU_HTTP_5XX"
    NOT_FOUND = "EDU_HTTP_404"
    FORBIDDEN = "EDU_HTTP_403"
    BREAKER_OPEN = "EDU_BREAKER_OPEN"
    AUTH_EXPIRED = "EDU_AUTH_EXPIRED"
    CHALLENGE_REQUIRED = "EDU_CHALLENGE_REQUIRED"
    ESIA_REPLAY = "EDU_ESIA_REPLAY"
    INVALID_STATE_TRANSITION = "EDU_STATE_TRANSITION"
    MUTATIONS_DISABLED = "EDU_MUTATIONS_DISABLED"
    REPORT_FORMAT = "EDU_REPORT_FORMAT"


class EduError(Exception):
    """Root exception for every pskovedu SDK error."""


class EduConfigError(EduError):
    """Raised when ``ClientConfig`` contains invalid or incompatible values."""


class MethodDeclarationError(EduError):
    """Raised at import time when a ``BaseMethod`` subclass is declared incorrectly.

    Example: ``__returning__`` contradicts the Generic[T] parameter, or a required
    class-var for the chosen protocol is missing.

    Args:
        message: human-readable description of the declaration problem.
    """

    code: ClassVar[ErrorCode] = ErrorCode.METHOD_DECLARATION

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class MethodNotBoundError(EduError):
    """Raised when a ``BaseMethod`` is awaited without a client bound.

    Args:
        method_name: class name of the unbound method.
    """

    code: ClassVar[ErrorCode] = ErrorCode.METHOD_NOT_BOUND

    def __init__(self, method_name: str) -> None:
        self.method_name = method_name
        super().__init__(method_name)

    def __str__(self) -> str:
        return (
            f"{self.method_name} awaited without a bound client. "
            "Use `await client(method)` or `method.as_(client)` first."
        )


class ModelNotBoundError(EduError):
    """Raised when a bound method is called on an ``EduObject`` with no client.

    Args:
        model_name: class name of the unbound model.
    """

    code: ClassVar[ErrorCode] = ErrorCode.MODEL_NOT_BOUND

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(model_name)

    def __str__(self) -> str:
        return (
            f"{self.model_name} has no client bound. "
            "Obtain it via a Client call, or call `.as_(client)` explicitly."
        )


class ProtocolError(EduError):
    """Raised when the wire protocol returns an unexpected or error envelope."""


class ExtDirectError(ProtocolError):
    """Ext.Direct RPC returned ``{"type": "exception", ...}``.

    Args:
        action: Ext.Direct action name (e.g. ``"Reports"``).
        method: Ext.Direct method name (e.g. ``"getGrades"``).
        tid: transaction id echoed from the request.
        server_msg: raw server-provided message string.
    """

    def __init__(self, action: str, method: str, tid: int, server_msg: str) -> None:
        self.action = action
        self.method = method
        self.tid = tid
        self.server_msg = server_msg
        super().__init__(action, method, tid, server_msg)


class X1Error(ProtocolError):
    """X1 ORM call returned an error envelope.

    Args:
        model: X1 model name (e.g. ``"JOURNAL"``).
        server_msg: raw server-provided message string.
    """

    def __init__(self, model: str, server_msg: str) -> None:
        self.model = model
        self.server_msg = server_msg
        super().__init__(model, server_msg)


class HtmlParseError(ProtocolError):
    """HTML parser failed to extract a required element.

    Args:
        what: description of what was being extracted (e.g. ``"REMOTING_API"``).
        url: the URL of the page that was parsed.
    """

    def __init__(self, what: str, url: str) -> None:
        self.what = what
        self.url = url
        super().__init__(what, url)


class TransportError(EduError):
    """Base for network / HTTP-level errors."""


class HTTPError(TransportError):
    """An HTTP response with an error status code was received.

    Args:
        status: HTTP status code.
        url: request URL that triggered the error.
    """

    def __init__(self, status: int, url: str) -> None:
        self.status = status
        self.url = url
        super().__init__(status, url)


class ServerError(HTTPError):
    """5xx response from the server."""


class NotFoundError(HTTPError):
    """404 response — resource not found."""

    def __init__(self, url: str) -> None:
        super().__init__(404, url)


class ForbiddenError(HTTPError):
    """403 response — access denied."""

    def __init__(self, url: str) -> None:
        super().__init__(403, url)


class BreakerOpen(TransportError):
    """Circuit breaker is open for this host+path and the request was rejected.

    Args:
        host: target host that is currently open.
        path: request path that was blocked.
    """

    def __init__(self, host: str, path: str) -> None:
        self.host = host
        self.path = path
        super().__init__(host, path)


class AuthError(EduError):
    """Base for authentication / session errors."""


class AuthExpiredError(AuthError):
    """Session has expired (HTTP 401) and could not be automatically refreshed.

    Triggers the auth refresh cycle inside ``BaseSession.make_request``.
    """


class ChallengeRequired(AuthError):
    """Server requires an interactive challenge that cannot be solved headlessly.

    Args:
        kind: challenge type, e.g. ``"captcha"`` or ``"qr"``.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(kind)


class EsiaReplayError(AuthError):
    """ESIA OAuth2 headless replay failed at a specific step.

    Args:
        step: step number (1–8) in the 8-step ESIA replay sequence.
        detail: human-readable description of what failed.
    """

    def __init__(self, step: int, detail: str) -> None:
        self.step = step
        self.detail = detail
        super().__init__(step, detail)


class InvalidStateTransition(EduError):
    """A state-machine transition was attempted that is not allowed.

    Args:
        current: current state value.
        target: attempted target state value.
        allowed: frozenset of valid target states from the current state.
    """

    def __init__(
        self,
        current: str,
        target: str,
        allowed: frozenset[str],
    ) -> None:
        self.current = current
        self.target = target
        self.allowed = allowed
        super().__init__(current, target, allowed)


class MutationsDisabled(EduError):
    """A write method was called but ``ClientConfig.allow_mutations`` is ``False``.

    Args:
        method: name of the method that attempted the mutation.
    """

    def __init__(self, method: str) -> None:
        self.method = method
        super().__init__(method)


class ReportFormatError(ValueError):
    """Raised when XLS export is requested for a form that does not support it.

    Caught before any network request is issued — purely a client-side guard.

    Args:
        form: the :class:`~pskovedu.models.enums.ReportForm` that was requested.
    """

    def __init__(self, form: object) -> None:
        self.form = form
        super().__init__(form)
