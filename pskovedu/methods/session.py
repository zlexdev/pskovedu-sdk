"""Shell bootstrap method: GetShell.

GetShell fetches ``GET /`` and passes the HTML to ``parsers/shell.py`` for
``REMOTING_API`` + ``X1_CONFIG`` extraction.  The authenticated user's identity
lives in ``X1_CONFIG.meta.au`` (the ``X1.user`` global the portal injects into
the shell) — there is **no** portal ``/session`` profile endpoint.
"""

from __future__ import annotations

from typing import ClassVar

from ..constants import PATH_SHELL, Host
from ..models._base import HtmlParsed
from ._bases import RestMethod


class _ShellHtml(HtmlParsed):
    """Internal marker model: the app-shell HTML response.

    ``RestProtocol`` detects ``HtmlParsed`` and returns the raw HTML text.
    ``GetShell`` (called by ``client.get_shell()``) then hands it to
    ``parsers/shell.py``.
    """


class GetShell(RestMethod[_ShellHtml]):
    """Fetch the app-shell HTML (``GET /``) for bootstrap parsing.

    The response is the full ``GET /`` HTML page that contains
    ``window.REMOTING_API`` and ``window.X1_CONFIG`` as inline JS globals.
    ``RestProtocol`` detects the ``HtmlParsed`` return type and passes the
    raw HTML text back instead of attempting JSON parsing.

    The caller (``client.get_shell()``) passes the ``.raw_html`` field to
    ``parsers/shell.py`` to extract ``ShellConfig`` — including the current
    user's role identity from ``X1_CONFIG.meta.au``.

    Raises:
        ProtocolError: on HTTP-level errors.
    """

    __http_method__: ClassVar[str] = "GET"
    __url__: ClassVar[str] = PATH_SHELL
    __host__: ClassVar[str] = Host.PORTAL
    __returning__: ClassVar[type] = _ShellHtml
