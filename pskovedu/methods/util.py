"""Utility / auth method-classes.

``CheckAuth``    — ``GET /common-api/check-auth?value=<token>``  (portal host)
``GetOAuthConfig`` — ``GET /aas/oauth2/config``                   (ESIA host)
"""

from __future__ import annotations

from ..constants import PATH_CHECK_AUTH, PATH_OAUTH_CONFIG, Host
from ..models.util import AuthCheck, OAuthConfig
from ._bases import RestMethod


class CheckAuth(RestMethod[AuthCheck]):
    """Validate a session token against the portal auth endpoint.

    REST: ``GET one.pskovedu.ru/common-api/check-auth?value=<token>``

    Args:
        value: the token string to validate.
    """

    __http_method__ = "GET"
    __url__ = PATH_CHECK_AUTH
    __query_fields__ = frozenset({"value"})

    value: str


class GetOAuthConfig(RestMethod[OAuthConfig]):
    """Fetch the ESIA OAuth2 / QR configuration.

    REST: ``GET esia.gosuslugi.ru/aas/oauth2/config``

    No parameters — the endpoint returns a flat JSON object with ~40
    dotted-key entries describing OAuth2 settings and QR-login parameters.
    """

    __http_method__ = "GET"
    __host__ = Host.ESIA
    __url__ = PATH_OAUTH_CONFIG
