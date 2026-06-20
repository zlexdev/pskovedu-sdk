"""SessionToken — decoded JWT cache with refresh-needed check.

Wraps the raw JWT string returned by ``GET /session`` and caches the decoded
claims (``sessionId``, ``exp``, ``iat``, ``jti``) so subsequent calls do not
re-parse the token on every request.

The portal uses HS256 (symmetric) JWTs.  We do not have the server secret and
do not verify the signature — we only need the expiry and session ID.

Usage::

    token = SessionToken.from_jwt(raw_jwt)
    if token.needs_refresh(skew_s=300):
        # refresh before exp
        ...
    headers["Authorization"] = f"Bearer {token.raw}"
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from ..exceptions import AuthError
from ..logging import get_logger
from ..models.session import Session
from ..utils.jwt import decode_payload

log = get_logger(__name__)


class SessionToken:
    """Decoded and cached portal JWT session token.

    Decodes the raw JWT string once on construction, caches the ``Session``
    model, and exposes :meth:`needs_refresh` for proactive token renewal.

    Args:
        raw: raw JWT string (``header.payload.signature``).
        session: decoded :class:`~pskovedu.models.session.Session` model.
    """

    __slots__ = ("_raw", "_session")

    def __init__(self, raw: str, session: Session) -> None:
        self._raw = raw
        self._session = session

    @classmethod
    def from_jwt(cls, raw: str) -> SessionToken:
        """Decode *raw* JWT and construct a :class:`SessionToken`.

        Args:
            raw: raw JWT string from the ``GET /session`` response body.

        Raises:
            AuthError: when the JWT is malformed or missing required claims
                (``sessionId``, ``exp``, ``iat``, ``jti``).
        """
        try:
            payload = decode_payload(raw)
        except ValueError as exc:
            raise AuthError(f"Malformed JWT: {exc}") from exc

        try:
            session = Session.model_validate(payload)
        except Exception as exc:
            raise AuthError(f"JWT payload missing required claims: {exc}") from exc

        log.debug(
            "session_token.decoded",
            session_id=session.session_id,
            jti=str(session.jti),
        )
        return cls(raw=raw, session=session)

    @property
    def raw(self) -> str:
        """The original raw JWT string."""
        return self._raw

    @property
    def session(self) -> Session:
        """The decoded :class:`~pskovedu.models.session.Session` model."""
        return self._session

    @property
    def session_id(self) -> str:
        """64-hex session identifier from ``payload.sessionId``."""
        return self._session.session_id

    @property
    def exp(self) -> datetime:
        """Token expiry — UTC tz-aware :class:`datetime`."""
        return self._session.exp

    @property
    def iat(self) -> datetime:
        """Token issue time — UTC tz-aware :class:`datetime`."""
        return self._session.iat

    @property
    def jti(self) -> UUID:
        """JWT ID — RFC 4122 :class:`~uuid.UUID`."""
        return self._session.jti

    @property
    def expired(self) -> bool:
        """``True`` when the token's expiry has passed relative to UTC now."""
        return self._session.expired

    def needs_refresh(self, skew_s: int = 300) -> bool:
        """Return ``True`` when the token should be refreshed proactively.

        The token is considered stale when ``now + skew_s >= exp``, i.e. when
        fewer than *skew_s* seconds remain before expiry.

        Args:
            skew_s: seconds before ``exp`` at which to declare refresh needed.
                Defaults to 300 (5 minutes), matching ``ClientConfig.jwt_refresh_skew_s``.
        """
        now = datetime.now(tz=UTC)
        remaining = (self._session.exp - now).total_seconds()
        return remaining <= skew_s

    def __repr__(self) -> str:
        return (
            f"SessionToken(session_id={self.session_id!r}, "
            f"exp={self.exp.isoformat()}, expired={self.expired})"
        )
