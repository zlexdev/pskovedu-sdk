"""AuthManager — authentication state machine and request injection point.

The ``AuthManager`` is the single component that knows about auth state.
``BaseSession.make_request`` calls ``auth_manager.ensure(client)`` before
every SDK request.  That call is the only place where cookies and JWT headers
are injected into outbound requests.

## State machine

    UNAUTH  ──login_with_*──►  COOKIE_ONLY  ──GET /session──►  SESSIONED
                                                                    │
                                                         (JWT refresh on exp-skew)
                                                                    │
                                                              SESSIONED (refreshed)

- **UNAUTH**: no credentials; ``ensure()`` is a no-op (raises nothing — the
  subsequent request will fail with ``AuthExpiredError`` if auth is required).
- **COOKIE_ONLY**: ``X1_SSO`` cookie injected; no JWT yet.
- **SESSIONED**: ``X1_SSO`` + ``Authorization: Bearer <jwt>`` injected;
  JWT refresh triggered when ``token.needs_refresh(skew_s)`` is ``True``.

Usage::

    manager = AuthManager(store=TokenStore(MemoryStorage()))
    await manager.login_with_cookies(client, x1_sso="...")
    # Then BaseSession calls:
    await manager.ensure(client)
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx

from ..exceptions import AuthError, AuthExpiredError
from ..logging import get_logger
from .cookies import CrossHostCookieJar
from .session_token import SessionToken
from .store import TokenStore

if TYPE_CHECKING:
    from ..auth.solvers.qr import DisplayCallback

log = get_logger(__name__)

# Portal session endpoint
_SESSION_PATH = "/session"


class AuthState(StrEnum):
    """Authentication state of the :class:`AuthManager`."""

    UNAUTH = "unauth"
    """No credentials; requests proceed without authentication."""

    COOKIE_ONLY = "cookie_only"
    """X1_SSO cookie injected; JWT not yet obtained."""

    SESSIONED = "sessioned"
    """X1_SSO cookie + JWT injected; proactive refresh on exp-skew."""


class AuthManager:
    """Authentication state machine for the pskovedu SDK.

    Owns the ``CrossHostCookieJar`` and (optionally) the ``SessionToken``,
    and injects both into every outbound request via :meth:`ensure`.

    Multiple login paths are supported:
    - :meth:`login_with_cookies` — bootstrap from a pre-obtained ``X1_SSO``.
    - :meth:`login_with_qr` — drive the SSE QR flow via a
      :class:`~pskovedu.auth.solvers.base.ChallengeSolver`.
    - :meth:`login_with_esia` — headless ESIA OAuth2 replay (experimental).

    Args:
        store: :class:`TokenStore` for persisting token + jar across restarts.
        account_key: storage key for this account (e.g. login or a UUID).
            When ``None``, persistence is disabled (in-memory only).
        portal_host: base URL of the portal for ``GET /session`` calls.
        passport_host: base URL of the passport service for ESIA redirects.
        esia_host: base URL of the ESIA authorization server.
    """

    def __init__(
        self,
        store: TokenStore | None = None,
        account_key: str | None = None,
        portal_host: str = "https://one.pskovedu.ru",
        passport_host: str = "https://passport.pskovedu.ru",
        esia_host: str = "https://esia.gosuslugi.ru",
    ) -> None:
        self._store = store
        self._account_key = account_key
        self._portal_host = portal_host
        self._passport_host = passport_host
        self._esia_host = esia_host

        self._state: AuthState = AuthState.UNAUTH
        self._jar: CrossHostCookieJar = CrossHostCookieJar()
        self._token: SessionToken | None = None

    @property
    def state(self) -> AuthState:
        """Current authentication state."""
        return self._state

    @property
    def jar(self) -> CrossHostCookieJar:
        """The cross-host cookie jar (shared by all requests)."""
        return self._jar

    @property
    def token(self) -> SessionToken | None:
        """Current session token, or ``None`` when not yet obtained."""
        return self._token

    async def ensure(self, client: Any) -> None:
        """Inject auth state into *client* and refresh stale credentials.

        Called by ``BaseSession.make_request`` before every SDK request.
        The method is idempotent: if credentials are fresh, it returns
        immediately without any network call.

        Steps:
        1. If ``UNAUTH``: try to restore state from ``TokenStore``.
        2. If ``COOKIE_ONLY``: inject ``X1_SSO`` cookie; attempt JWT obtain.
        3. If ``SESSIONED``: inject cookie + JWT; refresh token if stale.

        Args:
            client: the ``Client`` instance (provides ``config``, ``_session``).

        Raises:
            AuthExpiredError: when the session has expired and cannot be
                refreshed (no credentials available).
        """
        # Attempt restore from storage on first call
        if self._state == AuthState.UNAUTH and self._store and self._account_key:
            await self._try_restore()

        if self._state == AuthState.UNAUTH:
            # No credentials — let the request proceed (will fail with 401 if needed)
            return

        skew_s: int = getattr(getattr(client, "config", None), "jwt_refresh_skew_s", 300)

        self._inject_jar(client)

        if self._state == AuthState.COOKIE_ONLY:
            # Try to upgrade to SESSIONED by obtaining a JWT
            await self._obtain_jwt(client)
            return

        # SESSIONED: check token freshness
        if self._token is not None and self._token.needs_refresh(skew_s):
            log.info("auth.token_refresh.triggered", skew_s=skew_s)
            try:
                await self._obtain_jwt(client)
            except Exception as exc:
                log.warning("auth.token_refresh.failed", exc=str(exc))
                # If refresh failed and token is fully expired, surface the error
                if self._token.expired:
                    raise AuthExpiredError("JWT has expired and could not be refreshed") from exc

        if self._token is not None:
            self._inject_jwt(client, self._token.raw)

    async def login_with_cookies(self, client: Any, x1_sso: str) -> None:
        """Bootstrap authentication from a pre-obtained ``X1_SSO`` cookie.

        Transitions to ``COOKIE_ONLY`` immediately; :meth:`ensure` will
        upgrade to ``SESSIONED`` on the next request by calling ``GET /session``.

        Args:
            client: the ``Client`` instance.
            x1_sso: the ``X1_SSO`` cookie value.
        """
        self._jar.set("X1_SSO", x1_sso, domain="one.pskovedu.ru", secure=True, same_site="None")
        self._state = AuthState.COOKIE_ONLY
        log.info("auth.login_with_cookies.ok")
        # Eagerly obtain JWT if possible
        try:
            await self._obtain_jwt(client)
        except Exception as exc:
            log.warning("auth.jwt_obtain_on_login_failed", exc=str(exc))

    async def login_with_qr(
        self,
        client: Any,
        *,
        display_cb: DisplayCallback | None = None,
    ) -> None:
        """Authenticate via the QR SSE stream.

        Generates a QR session via :class:`~pskovedu.methods.qr.GenerateQr`,
        constructs a :class:`~pskovedu.auth.solvers.qr.QrSolver` with the
        returned UUID and optional *display_cb*, drives the SSE stream to
        obtain an ``X1_SSO`` cookie, then calls :meth:`login_with_cookies`
        to bootstrap the session.

        Args:
            client: the ``Client`` instance.
            display_cb: optional callable invoked with the QR URL string so
                the caller can display it (e.g. print to terminal or render
                as an image).  May be sync or async.

        Raises:
            AuthError: when the solver fails to produce a valid token.
        """
        from ..methods.qr import GenerateQr
        from .solvers.qr import QrSolver

        log.info("auth.login_with_qr.start")
        gen = await client(GenerateQr())
        solver = QrSolver(uuid=gen.qr_id, display_cb=display_cb)
        x1_sso = await solver.solve(client)
        await self.login_with_cookies(client, x1_sso=x1_sso)
        log.info("auth.login_with_qr.ok")

    async def login_with_esia(
        self,
        client: Any,
        login: str,
        password: str,
    ) -> None:
        """Authenticate via headless ESIA OAuth2 replay (experimental).

        Drives the 8-step ESIA authorization code flow using the F001
        ``client_secret`` leak.  For own-account use only.

        Args:
            client: the ``Client`` instance.
            login: ESIA login (SNILS, email, or phone number).
            password: ESIA account password.

        Raises:
            EsiaReplayError: when any step of the ESIA replay fails.
            ChallengeRequired: when a CAPTCHA is detected.
        """
        from .esia import replay_oauth  # local import — avoids circular at module level

        log.info("auth.login_with_esia.start")
        async with httpx.AsyncClient(follow_redirects=False) as transport:
            x1_sso = await replay_oauth(
                transport,
                login,
                password,
                portal_host=self._passport_host,
                esia_host=self._esia_host,
            )

        await self.login_with_cookies(client, x1_sso=x1_sso)
        log.info("auth.login_with_esia.ok")

    async def _obtain_jwt(self, client: Any) -> None:
        """Call ``GET /session`` and store the resulting JWT.

        Transitions ``COOKIE_ONLY`` → ``SESSIONED`` on success.

        Args:
            client: the ``Client`` instance (used only for its config + session).
        """
        session_url = f"{self._portal_host}{_SESSION_PATH}"
        cookies_for_req = self._jar.for_url(session_url)

        try:
            async with httpx.AsyncClient(cookies=cookies_for_req) as http:
                resp = await http.get(session_url)
        except httpx.TransportError as exc:
            raise AuthError(f"GET /session network error: {exc}") from exc

        if resp.status_code == 401:
            raise AuthExpiredError("GET /session returned 401 — X1_SSO is expired")
        if resp.status_code != 200:
            raise AuthError(f"GET /session returned unexpected status {resp.status_code}")

        raw_jwt = resp.text.strip()
        if not raw_jwt:
            raise AuthError("GET /session returned empty body")

        self._token = SessionToken.from_jwt(raw_jwt)
        self._state = AuthState.SESSIONED

        for name, value in resp.cookies.items():
            self._jar.set(name, value, domain="one.pskovedu.ru")

        # Persist to storage if configured
        if self._store and self._account_key:
            try:
                await self._store.save(self._account_key, self._token, self._jar)
            except Exception as exc:
                log.warning("auth.store_save_failed", exc=str(exc))

        log.info(
            "auth.jwt_obtained",
            session_id=self._token.session_id,
            exp=self._token.exp.isoformat(),
        )

    async def _try_restore(self) -> None:
        """Try to restore token + jar from storage.

        Transitions ``UNAUTH`` → ``SESSIONED`` on success;
        ``UNAUTH`` → ``UNAUTH`` on failure (silent).
        """
        assert self._store is not None and self._account_key is not None
        result = await self._store.load(self._account_key)
        if result is None:
            return
        token, jar = result
        if token.expired:
            log.info("auth.restore.token_expired")
            return
        self._token = token
        self._jar = jar
        self._state = AuthState.SESSIONED
        log.info(
            "auth.restore.ok",
            session_id=token.session_id,
            exp=token.exp.isoformat(),
        )

    def _inject_jar(self, client: Any) -> None:
        """Write the cookie jar into *client*'s ``_cookies`` dict."""
        existing: dict[str, str] = getattr(client, "_cookies", {})
        existing.update(self._jar.to_dict())
        import contextlib

        with contextlib.suppress(AttributeError):
            client._cookies = existing

    def _inject_jwt(self, client: Any, raw_jwt: str) -> None:
        """Write the JWT Authorization header into *client*'s default headers."""
        import contextlib

        with contextlib.suppress(AttributeError):
            headers: dict[str, str] = getattr(client, "_headers", {})
            headers["Authorization"] = f"Bearer {raw_jwt}"
            client._headers = headers
