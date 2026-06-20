"""ESIA OAuth2 headless replay — extract ``client_secret`` and drive the 8-step flow.

**Security / legal note (F001 / R1):**
The ESIA ``client_secret`` is a DER/CMS blob that the portal exposes in the
plain-text ``302 Location`` query string (finding F001).  This module parses
that value at runtime — it is *never* hardcoded.  Use this only on accounts
you own; automated use at scale may violate ESIA / Gosuslugi ToS.

## 8-step ESIA replay (source: ``security/auth.md``)

1. ``GET passport.pskovedu.ru/auth/esia/redirect``
   → follow 302 → capture ``Location`` header.
2. Parse ``client_id``, ``client_secret`` (DER/CMS), ``state``, ``redirect_uri``
   from ``Location`` query string → :class:`EsiaRedirect`.
3. ``GET esia.gosuslugi.ru/aas/oauth2/ac?{params}``
   → collect ESIA cookies, follow redirects to ``/login``.
4. POST credentials (``login``, ``password``) to the ESIA login form endpoint
   (discovered from ``js/endpoints.json``).
   → may yield CAPTCHA challenge → raise :exc:`ChallengeRequired("captcha")`.
5. Follow ESIA 302 chain → ``passport.pskovedu.ru/auth/esia/return?code=&state=``
   → ``GET`` that callback URL → portal sets ``X1_SSO`` cookie.
6. Return the ``X1_SSO`` cookie value to the caller.

Steps 7–8 (``GET /session`` → JWT) are handled by
:class:`~pskovedu.auth.manager.AuthManager` after ``X1_SSO`` is obtained.

Raises :exc:`EsiaReplayError(step, detail)` on any step failure.
Raises :exc:`ChallengeRequired("captcha")` when a CAPTCHA is detected.
"""

from __future__ import annotations

import base64
import re
from urllib.parse import parse_qs, urlparse

import httpx

from ..exceptions import ChallengeRequired, EsiaReplayError
from ..logging import get_logger
from ..models.esia import EsiaRedirect

log = get_logger(__name__)

# ESIA login form POST endpoint (from js/endpoints.json)
_ESIA_LOGIN_PATH = "/aas/oauth2/api/login"

# Redirect trigger: ESIA auth URL prefix
_ESIA_AC_PATH = "/aas/oauth2/ac"

# Passport callback path pattern
_PASSPORT_RETURN_RE = re.compile(r"/auth/esia/return", re.IGNORECASE)

_X1_SSO_COOKIE = "X1_SSO"

# CAPTCHA indicators in ESIA HTML response
_CAPTCHA_INDICATORS = ("captcha", "recaptcha", "g-recaptcha", "captcha-block")

# Sanity check: DER/base64 blobs are typically > 100 chars
_MIN_SECRET_LEN = 50


def extract_client_secret(location_url: str) -> EsiaRedirect:
    """Parse ESIA OAuth2 parameters from the ``302 Location`` redirect URL.

    The portal's ``GET /auth/esia/redirect`` returns a ``302`` whose
    ``Location`` query string contains ``client_id``, ``client_secret``
    (a DER/CMS base64 blob — finding F001), ``state``, and ``redirect_uri``.

    Args:
        location_url: full ``Location`` header value from the ``302`` response.

    Raises:
        EsiaReplayError: step 2 — when required query parameters are missing or
            ``client_secret`` fails a basic DER/base64 sanity check.
    """
    try:
        parsed = urlparse(location_url)
        qs = parse_qs(parsed.query, keep_blank_values=False)
    except Exception as exc:
        raise EsiaReplayError(2, f"Failed to parse Location URL: {exc}") from exc

    def _require(param: str) -> str:
        values = qs.get(param)
        if not values:
            raise EsiaReplayError(2, f"Missing required query param: {param!r}")
        return values[0]

    client_id = _require("client_id")
    client_secret = _require("client_secret")
    state = _require("state")
    redirect_uri = _require("redirect_uri")

    # Basic DER/base64 sanity check — the secret should be a non-trivial blob
    _sanity_check_secret(client_secret)

    log.debug("esia.client_secret.extracted", client_id=client_id, state=state)
    return EsiaRedirect(
        client_id=client_id,
        client_secret=client_secret,
        state=state,
        redirect_uri=redirect_uri,
        raw_location=location_url,
    )


def _sanity_check_secret(secret: str) -> None:
    """Validate that *secret* looks like a DER/base64 blob (not a placeholder).

    Raises:
        EsiaReplayError: step 2 — when the secret is too short or fails
            base64 decoding entirely.
    """
    if len(secret) < _MIN_SECRET_LEN:
        raise EsiaReplayError(
            2,
            f"client_secret too short ({len(secret)} chars) — not a valid DER/CMS blob",
        )
    # Attempt base64 decode as a sanity check (URL-safe or standard)
    try:
        # URL-safe variant first (ESIA uses URL-encoded query strings)
        padded = secret + "=" * (-len(secret) % 4)
        base64.urlsafe_b64decode(padded)
    except Exception:
        try:
            padded = secret + "=" * (-len(secret) % 4)
            base64.b64decode(padded)
        except Exception as exc:
            raise EsiaReplayError(
                2,
                f"client_secret is not valid base64/DER: {exc}",
            ) from exc


def _detect_captcha(html: str) -> bool:
    """Return ``True`` when *html* contains CAPTCHA indicators."""
    lower = html.lower()
    return any(ind in lower for ind in _CAPTCHA_INDICATORS)


async def replay_oauth(
    transport: httpx.AsyncClient,
    login: str,
    password: str,
    *,
    portal_host: str = "https://passport.pskovedu.ru",
    esia_host: str = "https://esia.gosuslugi.ru",
) -> str:
    """Drive the full 8-step ESIA OAuth2 headless flow and return ``X1_SSO``.

    Uses the provided *transport* (an ``httpx.AsyncClient`` with
    ``follow_redirects=False`` so we can intercept each step) to replay the
    ESIA authorization code flow.

    Args:
        transport: ``httpx.AsyncClient`` for all HTTP calls.  Should have
            ``follow_redirects=False`` to allow per-step redirect interception.
        login: ESIA / Gosuslugi login (SNILS, email, or phone number).
        password: ESIA account password.
        portal_host: base URL of the portal passport service.
        esia_host: base URL of the ESIA authorization server.

    Raises:
        EsiaReplayError: when any step fails (carries the step number 1–6 and
            a human-readable description).
        ChallengeRequired: when a CAPTCHA is detected at step 4.
    """
    # Step 1 — GET passport.pskovedu.ru/auth/esia/redirect
    log.info("esia.replay.step1", url=f"{portal_host}/auth/esia/redirect")
    try:
        resp1 = await transport.get(f"{portal_host}/auth/esia/redirect")
    except httpx.TransportError as exc:
        raise EsiaReplayError(1, f"Network error on redirect endpoint: {exc}") from exc

    if resp1.status_code not in (301, 302, 303, 307, 308):
        raise EsiaReplayError(
            1,
            f"Expected 302 from /auth/esia/redirect, got {resp1.status_code}",
        )

    location = resp1.headers.get("location", "")
    if not location:
        raise EsiaReplayError(1, "302 response missing Location header")

    # Step 2 — Parse client_secret + params from Location
    log.info("esia.replay.step2")
    esia_redir = extract_client_secret(location)  # raises EsiaReplayError(2) on failure

    # Step 3 — GET esia.gosuslugi.ru/aas/oauth2/ac?{params} → collect ESIA cookies
    log.info("esia.replay.step3", url=location)
    try:
        resp3 = await transport.get(location)
    except httpx.TransportError as exc:
        raise EsiaReplayError(3, f"Network error on ESIA ac endpoint: {exc}") from exc

    # Collect ESIA cookies from the redirect chain
    esia_cookies: dict[str, str] = {}
    esia_cookies.update({k: v for k, v in resp3.cookies.items()})

    # Follow redirects manually to stay in step-by-step control
    current_resp = resp3
    for _ in range(10):  # max redirect depth
        if current_resp.status_code not in (301, 302, 303, 307, 308):
            break
        next_url = current_resp.headers.get("location", "")
        if not next_url:
            break
        try:
            current_resp = await transport.get(next_url)
            esia_cookies.update({k: v for k, v in current_resp.cookies.items()})
        except httpx.TransportError as exc:
            raise EsiaReplayError(3, f"Network error following ESIA redirect: {exc}") from exc

    # After redirects, we should be at the ESIA login page
    login_html = ""
    if hasattr(current_resp, "text"):
        login_html = current_resp.text

    if _detect_captcha(login_html):
        log.warning("esia.replay.captcha_detected", step=3)
        raise ChallengeRequired("captcha")

    # Step 4 — POST credentials to ESIA login endpoint
    log.info("esia.replay.step4")
    login_url = f"{esia_host}{_ESIA_LOGIN_PATH}"
    login_payload = {
        "login": login,
        "password": password,
        "client_id": esia_redir.client_id,
        "state": esia_redir.state,
        "redirect_uri": esia_redir.redirect_uri,
        "client_secret": esia_redir.client_secret,
        "scope": "openid",
        "response_type": "code",
    }
    try:
        resp4 = await transport.post(
            login_url,
            data=login_payload,
            cookies=esia_cookies,
        )
    except httpx.TransportError as exc:
        raise EsiaReplayError(4, f"Network error on ESIA login POST: {exc}") from exc

    # Check for CAPTCHA in login response
    resp4_text = resp4.text if hasattr(resp4, "text") else ""
    if _detect_captcha(resp4_text):
        log.warning("esia.replay.captcha_on_login")
        raise ChallengeRequired("captcha")

    if resp4.status_code not in (200, 301, 302, 303, 307, 308):
        raise EsiaReplayError(
            4,
            f"ESIA login POST returned unexpected status {resp4.status_code}",
        )

    esia_cookies.update({k: v for k, v in resp4.cookies.items()})

    # Step 5 — Follow ESIA 302 chain → passport callback → X1_SSO
    log.info("esia.replay.step5")
    current_resp = resp4
    x1_sso: str | None = None

    for _ in range(15):  # max redirect depth for callback chain
        loc = current_resp.headers.get("location", "")
        if not loc:
            break
        # Check if this is the passport callback
        if _PASSPORT_RETURN_RE.search(loc):
            log.debug("esia.replay.callback_found", url=loc)
            try:
                cb_resp = await transport.get(loc, cookies=esia_cookies)
            except httpx.TransportError as exc:
                raise EsiaReplayError(5, f"Network error on passport callback: {exc}") from exc
            x1_sso = cb_resp.cookies.get(_X1_SSO_COOKIE)
            if x1_sso:
                log.info("esia.replay.x1_sso_obtained")
                break
            # Follow further if cookie not yet set
            current_resp = cb_resp
            esia_cookies.update({k: v for k, v in cb_resp.cookies.items()})
        else:
            try:
                current_resp = await transport.get(loc, cookies=esia_cookies)
                esia_cookies.update({k: v for k, v in current_resp.cookies.items()})
                # Check if X1_SSO appeared
                x1_sso = current_resp.cookies.get(_X1_SSO_COOKIE)
                if x1_sso:
                    log.info("esia.replay.x1_sso_obtained")
                    break
            except httpx.TransportError as exc:
                raise EsiaReplayError(5, f"Network error following callback chain: {exc}") from exc

    # Step 6 — Return X1_SSO
    if not x1_sso:
        raise EsiaReplayError(
            6,
            "X1_SSO cookie was not set after completing the ESIA callback chain",
        )

    return x1_sso
