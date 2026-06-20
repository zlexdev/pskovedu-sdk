"""ESIA / Gosuslugi OAuth2 DTOs.

These models carry the parsed fields from the ESIA OAuth2 redirect flow
(F001 — ``client_secret`` in ``302 Location``) and the QR authentication
stream event.

Source: ``security/auth.md`` §Step 1–2 (EsiaRedirect), §Step 3 (EsiaCookies),
``security/findings.md`` §F011 (QrEvent / SSE stream).
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from ._base import EduObject
from .enums import QrEventKind as QrEventKind


class EsiaRedirect(EduObject):
    """Parsed fields from the ESIA OAuth2 ``302 Location`` redirect URL.

    The portal endpoint ``GET /auth/esia/redirect`` returns a ``302`` whose
    ``Location`` header carries the full ESIA authorization URL.  The query
    string of that URL contains ``client_id``, ``client_secret`` (a DER/CMS
    blob), ``state``, and ``redirect_uri`` (finding F001).

    **Security note:** ``client_secret`` must never be logged, committed, or
    hardcoded.  It is present on the wire and is extracted here solely to drive
    the headless ESIA replay.

    Args:
        client_id: ESIA client identifier (``client_id`` query param).
        client_secret: DER/CMS blob from ``client_secret`` query param.
            Structlog redaction applies automatically.
        state: CSRF state nonce (``state`` query param).
        redirect_uri: callback URI (``redirect_uri`` query param).
        raw_location: the full ``Location`` header value for debugging.
    """

    client_id: str = Field(..., alias="client_id")
    client_secret: str = Field(..., alias="client_secret")
    state: str = Field(..., alias="state")
    redirect_uri: str = Field(..., alias="redirect_uri")
    raw_location: str = Field(default="", alias="raw_location")

    @field_validator("client_secret", mode="before")
    @classmethod
    def _validate_non_empty(cls, v: Any) -> Any:
        """Reject an empty client_secret — indicates the redirect was not the
        expected ESIA authorization URL."""
        if not v:
            raise ValueError("client_secret must not be empty")
        return v


class EsiaCookies(EduObject):
    """Cookies obtained after following the ESIA authorization redirect chain.

    After step 3 of the ESIA replay (``GET esia.gosuslugi.ru/aas/oauth2/ac``),
    the response sets cookies needed for subsequent ESIA form POST calls.

    Args:
        cookies: flat name→value mapping of all ESIA cookies collected from the
            authorization redirect chain.
    """

    cookies: dict[str, str] = Field(default_factory=dict)

    def get(self, name: str) -> str | None:
        """Return a cookie value by name, or ``None``."""
        return self.cookies.get(name)


class QrGenerate(EduObject):
    """Response from ``POST /qr-delegate/qr/generate``.

    Args:
        qr_id: opaque QR session identifier returned by the generate endpoint.
            Pass this as ``uuid`` to :class:`~pskovedu.methods.qr.QrAuthEvent`
            (``SubscribeQr``) and :class:`~pskovedu.methods.qr.ConfirmQr`.
    """

    qr_id: str = Field(..., alias="qrId")


class QrConfirm(EduObject):
    """Response from ``POST /qr-delegate/qr/confirm``.

    Args:
        x1_sso: X1 SSO token injected as a cookie after successful QR
            confirmation; ``None`` when the response carries no token.
    """

    x1_sso: str | None = None


class QrEvent(EduObject):
    """A single event from the QR authentication SSE stream.

    The stream endpoint is ``GET /qr-delegate/qr/subscribe/{uuid}``
    (``text/event-stream``).  Each SSE frame is decoded into a :class:`QrEvent`.

    Args:
        kind: event type from the ``event:`` SSE field.
        data: raw data payload from the ``data:`` SSE field (may be JSON or
            plain text depending on ``kind``).
        code: one-time authentication code extracted from a
            ``qr-auth-confirmed`` event; ``None`` for all other event types.
    """

    kind: QrEventKind = Field(..., alias="kind")
    data: str = Field(default="", alias="data")
    code: str | None = Field(default=None, alias="code")

    @property
    def is_confirmed(self) -> bool:
        """``True`` when this event carries a successful QR authentication."""
        return self.kind == QrEventKind.QR_AUTH_CONFIRMED

    @property
    def is_error(self) -> bool:
        """``True`` when this event signals a QR authentication failure."""
        return self.kind == QrEventKind.QR_ERROR
