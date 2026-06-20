"""pskovedu.auth — authentication layer.

Public API::

    from pskovedu.auth.manager import AuthManager, AuthState
    from pskovedu.auth.cookies import CrossHostCookieJar
    from pskovedu.auth.session_token import SessionToken
    from pskovedu.auth.store import TokenStore
    from pskovedu.auth.esia import extract_client_secret, replay_oauth
"""

from __future__ import annotations

from .cookies import CrossHostCookieJar
from .manager import AuthManager, AuthState
from .session_token import SessionToken
from .store import TokenStore

__all__ = [
    "AuthManager",
    "AuthState",
    "CrossHostCookieJar",
    "SessionToken",
    "TokenStore",
]
