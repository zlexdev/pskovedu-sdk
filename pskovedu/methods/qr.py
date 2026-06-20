"""QR method-classes — generate, subscribe, and confirm QR-code auth.

Wire endpoints (all on ``esia.gosuslugi.ru``):
- ``POST /qr-delegate/qr/generate``       — mint a new QR session UUID.
- ``GET  /qr-delegate/qr/subscribe/{uuid}`` — SSE stream of QR events.
- ``POST /qr-delegate/qr/confirm``        — exchange one-time code for SSO token.

Events from the subscribe stream:
- ``qr-auth-confirmed`` — terminal event: QR was scanned and auth succeeded.
- ``qr-error``          — terminal event: auth failed / expired.
- ``waiting``           — keepalive: still waiting for scan.
- ``ping``              — keepalive: connection alive.
"""

from __future__ import annotations

from ..constants import PATH_QR_CONFIRM, PATH_QR_GENERATE, PATH_QR_SUBSCRIBE, Host, SseEvent
from ..models.common import Uuid
from ..models.esia import QrConfirm, QrEvent, QrGenerate
from ._bases import RestMethod, SseSubscription


class GenerateQr(RestMethod[QrGenerate]):
    """Mint a new QR session on the ESIA endpoint.

    Sends ``POST esia.gosuslugi.ru/qr-delegate/qr/generate`` with an empty
    body.  Returns :class:`~pskovedu.models.esia.QrGenerate` carrying the
    ``qr_id`` (``qrId``) needed to open the SSE subscription and to confirm.

    Args:
        (none — this method carries no fields; body is empty)
    """

    __host__ = Host.ESIA
    __url__ = PATH_QR_GENERATE
    __http_method__ = "POST"


class QrAuthEvent(SseSubscription[None]):
    """SSE subscription for QR-code ESIA authentication.

    Opens a ``GET`` SSE stream to
    ``esia.gosuslugi.ru/qr-delegate/qr/subscribe/{uuid}`` and yields events
    until the terminal ``qr-auth-confirmed`` or ``qr-error`` event arrives.

    Use :class:`~pskovedu.transport.sse.SseStream` on the transport layer to
    iterate events.  Each SSE frame is parsed into a typed
    :class:`~pskovedu.models.esia.QrEvent` via ``event.parsed``.

    Args:
        uuid: QR session UUID from :class:`GenerateQr` (``QrGenerate.qr_id``).
    """

    __host__ = Host.ESIA
    __url__ = PATH_QR_SUBSCRIBE
    __path_fields__ = frozenset({"uuid"})
    __event_model__ = QrEvent  # SSE frames parse into a typed QrEvent
    __terminal_event__ = SseEvent.QR_AUTH_CONFIRMED

    uuid: Uuid


class ConfirmQr(RestMethod[QrConfirm]):
    """Exchange a one-time QR auth code for an X1 SSO token.

    Sends ``POST esia.gosuslugi.ru/qr-delegate/qr/confirm`` with
    ``{"code": <one-time-code>}`` in the request body.  Returns
    :class:`~pskovedu.models.esia.QrConfirm` whose ``x1_sso`` field carries
    the session token.

    Args:
        code: one-time authentication code from the ``qr-auth-confirmed`` SSE
            event (``QrEvent.code``).
    """

    __host__ = Host.ESIA
    __url__ = PATH_QR_CONFIRM
    __http_method__ = "POST"
    __body_fields__ = frozenset({"code"})

    code: str


# Keep a short alias for method-style call: client(SubscribeQr(uuid=...))
SubscribeQr = QrAuthEvent
