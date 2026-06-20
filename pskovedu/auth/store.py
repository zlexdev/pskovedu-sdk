"""TokenStore — persist session token + cookie jar per account key.

Wraps :class:`~pskovedu.storage.base.BaseStorage` to save and load the
authentication state (JWT + cookies) across process restarts.

The stored format is a plain JSON-serialisable dict so any ``BaseStorage``
backend (memory, file, Redis) works without extra adapters::

    {
        "jwt": "<raw JWT string>",
        "cookies": {"X1_SSO": "...", "EsiaAuth": "..."}
    }

Usage::

    store = TokenStore(storage=MemoryStorage())
    await store.save("user@example.com", token, jar)
    token, jar = await store.load("user@example.com") or (None, None)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging import get_logger
from ..storage.base import BaseStorage
from .cookies import CrossHostCookieJar
from .session_token import SessionToken

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

_StoredDict = dict[str, object]


class TokenStore:
    """Persist and retrieve :class:`SessionToken` + :class:`CrossHostCookieJar`.

    Uses any :class:`~pskovedu.storage.base.BaseStorage` backend.  The stored
    value is a JSON-serialisable dict with two keys: ``"jwt"`` and
    ``"cookies"``.

    Args:
        storage: a :class:`BaseStorage` instance (``MemoryStorage``,
            ``FileStorage``, or a custom backend).
    """

    def __init__(self, storage: BaseStorage[_StoredDict]) -> None:
        self._storage = storage

    async def save(
        self,
        account_key: str,
        token: SessionToken,
        jar: CrossHostCookieJar,
    ) -> None:
        """Persist *token* and *jar* for *account_key*.

        Args:
            account_key: unique identifier for the account (e.g. login e-mail
                or a UUID string).
            token: current session token to store.
            jar: current cross-host cookie jar to store.
        """
        data: _StoredDict = {
            "jwt": token.raw,
            "cookies": jar.to_dict(),
        }
        await self._storage.set(account_key, data)
        log.debug("token_store.saved", account_key=account_key)

    async def load(
        self,
        account_key: str,
    ) -> tuple[SessionToken, CrossHostCookieJar] | None:
        """Load the stored token + jar for *account_key*.

        Returns ``None`` when no entry exists or the stored data is invalid
        (e.g. the JWT is malformed).  Errors are logged but not re-raised so
        that a missing / corrupt store entry falls through to re-authentication.

        Args:
            account_key: unique identifier for the account.
        """
        data = await self._storage.get(account_key)
        if data is None:
            return None

        raw_jwt = data.get("jwt")
        raw_cookies = data.get("cookies") or {}

        if not isinstance(raw_jwt, str) or not raw_jwt:
            log.warning("token_store.missing_jwt", account_key=account_key)
            return None

        try:
            token = SessionToken.from_jwt(raw_jwt)
        except Exception as exc:
            log.warning("token_store.invalid_jwt", account_key=account_key, exc=str(exc))
            return None

        if not isinstance(raw_cookies, dict):
            raw_cookies = {}

        jar = CrossHostCookieJar.from_dict({str(k): str(v) for k, v in raw_cookies.items()})
        log.debug("token_store.loaded", account_key=account_key)
        return token, jar

    async def delete(self, account_key: str) -> None:
        """Remove stored authentication state for *account_key*.

        Args:
            account_key: unique identifier for the account.
        """
        await self._storage.delete(account_key)
        log.debug("token_store.deleted", account_key=account_key)
