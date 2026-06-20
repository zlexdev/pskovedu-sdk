"""Session bootstrap methods: GetSession and GetShell.

GetSession decodes the portal JWT into a typed ``Session`` DTO.
GetShell fetches ``GET /`` and passes the HTML to ``parsers/shell.py``
for REMOTING_API + X1_CONFIG extraction.
"""

from __future__ import annotations

from typing import ClassVar

from ..constants import PATH_SESSION, PATH_SHELL, Host
from ..models._base import HtmlParsed
from ..models.session import Session
from ._bases import RestMethod


class GetSession(RestMethod[Session]):
    """Fetch the current session JWT and decode it into a ``Session`` DTO.

    Sends ``GET /session`` with the ``X1_SSO`` cookie (injected by the auth
    layer).  The raw HS256 JWT response body is decoded by
    ``RestProtocol.decode_response`` into :class:`~pskovedu.models.session.Session`.

    Raises:
        AuthExpiredError: when the server returns 401 (handled by the funnel).
        ProtocolError: when the response is not a valid JWT or cannot be parsed.
    """

    __http_method__: ClassVar[str] = "GET"
    __url__: ClassVar[str] = PATH_SESSION
    __host__: ClassVar[str] = Host.PORTAL
    __returning__: ClassVar[type] = Session


class _ShellHtml(HtmlParsed):
    """Internal marker model: the app-shell HTML response.

    ``RestProtocol`` detects ``HtmlParsed`` and returns the raw HTML text.
    ``GetShell.decode`` (called by client.bootstrap()) then hands it to
    ``parsers/shell.py``.
    """


class GetShell(RestMethod[_ShellHtml]):
    """Fetch the app-shell HTML (``GET /``) for bootstrap parsing.

    The response is the full ``GET /`` HTML page that contains
    ``window.REMOTING_API`` and ``window.X1_CONFIG`` as inline JS globals.
    ``RestProtocol`` detects the ``HtmlParsed`` return type and passes the
    raw HTML text back instead of attempting JSON parsing.

    The caller (``client.bootstrap()``) passes the ``.raw_html`` field to
    ``parsers/shell.py`` to extract ``ShellConfig``.

    Raises:
        ProtocolError: on HTTP-level errors.
    """

    __http_method__: ClassVar[str] = "GET"
    __url__: ClassVar[str] = PATH_SHELL
    __host__: ClassVar[str] = Host.PORTAL
    __returning__: ClassVar[type] = _ShellHtml
