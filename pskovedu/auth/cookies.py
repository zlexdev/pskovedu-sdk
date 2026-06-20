"""CrossHostCookieJar — a single cookie jar spanning portal + ESIA hosts.

The pskovedu authentication flow requires cookies to be shared across:
- ``*.pskovedu.ru`` — portal, passport SSO
- ``*.gosuslugi.ru`` — ESIA authorization, SFD JWT endpoint

Standard ``httpx`` cookie jars scope by domain and refuse to send cookies
across unrelated second-level domains.  This wrapper relaxes that restriction
so the ESIA replay and the portal session can share a single jar, and
``SameSite=None`` cookies received from the portal are forwarded correctly.

Usage::

    jar = CrossHostCookieJar()
    jar.set("X1_SSO", value, domain="one.pskovedu.ru")
    # or from a flat dict (bootstrapping from HAR):
    jar = CrossHostCookieJar.from_dict({"X1_SSO": "...", "EsiaAuth": "..."})
    jar.inject(prepared_request_headers)
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlparse

import httpx

from ..logging import get_logger

log = get_logger(__name__)

# Domains whose cookies we accept and forward without strict SameSite checks
_TRUSTED_DOMAINS = frozenset(
    {
        "pskovedu.ru",
        "gosuslugi.ru",
    }
)


def _is_trusted(domain: str) -> bool:
    """Return ``True`` when *domain* is a subdomain of a trusted root."""
    domain = domain.lstrip(".")
    return any(domain == root or domain.endswith(f".{root}") for root in _TRUSTED_DOMAINS)


class _Cookie:
    """Minimal cookie record stored in the jar."""

    __slots__ = ("name", "value", "domain", "path", "secure", "same_site")

    def __init__(
        self,
        name: str,
        value: str,
        domain: str = "",
        path: str = "/",
        secure: bool = False,
        same_site: str = "None",
    ) -> None:
        self.name = name
        self.value = value
        self.domain = domain
        self.path = path
        self.secure = secure
        self.same_site = same_site


class CrossHostCookieJar:
    """A cookie jar that spans ``*.pskovedu.ru`` and ``*.gosuslugi.ru``.

    Cookies from both domain families are stored together and injected into
    outbound requests by matching the request URL's host against the stored
    domain.  ``SameSite=None`` cookies are forwarded across origins.

    The jar also wraps an ``httpx.Cookies`` instance so it can be passed
    directly to ``httpx.AsyncClient(cookies=...)``.

    Args:
        initial: optional flat name→value dict for bootstrapping (no domain
            scoping — cookies are sent to all trusted hosts).
    """

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._store: list[_Cookie] = []
        if initial:
            for name, value in initial.items():
                self.set(name, value)

    @classmethod
    def from_dict(cls, cookies: dict[str, str]) -> CrossHostCookieJar:
        """Construct a jar pre-loaded with *cookies* (no domain scoping).

        Args:
            cookies: flat name→value mapping (e.g. from HAR bootstrap or
                ``Client.from_cookie``).
        """
        return cls(initial=cookies)

    def set(
        self,
        name: str,
        value: str,
        domain: str = "",
        path: str = "/",
        secure: bool = False,
        same_site: str = "None",
    ) -> None:
        """Set (or overwrite) a cookie in the jar.

        Args:
            name: cookie name.
            value: cookie value.
            domain: cookie domain (empty = send to all trusted hosts).
            path: cookie path scope.
            secure: whether this is a ``Secure`` cookie.
            same_site: ``SameSite`` attribute value.
        """
        self._store = [c for c in self._store if not (c.name == name and c.domain == domain)]
        self._store.append(_Cookie(name, value, domain, path, secure, same_site))

    def delete(self, name: str, domain: str = "") -> None:
        """Remove all cookies matching *name* and (optionally) *domain*.

        Args:
            name: cookie name to remove.
            domain: if provided, only remove cookies for this domain.
        """
        self._store = [
            c for c in self._store if not (c.name == name and (not domain or c.domain == domain))
        ]

    def update_from_httpx(self, response: httpx.Response) -> None:
        """Import ``Set-Cookie`` headers from an httpx response.

        Only cookies from trusted domains are accepted.

        Args:
            response: an ``httpx.Response`` object.
        """
        url_host = response.url.host
        if not _is_trusted(url_host):
            log.debug("cookies.untrusted_host_skipped", host=url_host)
            return
        for name, value in response.cookies.items():
            self.set(name, value, domain=url_host)
            log.debug("cookies.set_from_response", name=name, domain=url_host)

    def for_url(self, url: str) -> dict[str, str]:
        """Return cookies applicable to *url* as a flat name→value dict.

        Matching rules:
        - Cookie ``domain`` is empty → send to all trusted hosts.
        - Cookie ``domain`` matches the request host (subdomain-aware) → send.
        - Request host is not trusted → return empty dict.

        Args:
            url: target URL string.
        """
        host = urlparse(url).hostname or ""
        if not _is_trusted(host):
            return {}
        result: dict[str, str] = {}
        for c in self._store:
            if (
                not c.domain
                or _is_trusted(c.domain)
                and (
                    host == c.domain.lstrip(".")
                    or host.endswith("." + c.domain.lstrip("."))
                    or not c.domain
                )
            ):
                result[c.name] = c.value
        return result

    def as_httpx_cookies(self, url: str = "") -> httpx.Cookies:
        """Return an ``httpx.Cookies`` instance for the given URL.

        Args:
            url: if provided, only cookies applicable to this URL are included.
        """
        cookies = httpx.Cookies()
        items = self.for_url(url) if url else {c.name: c.value for c in self._store}
        for name, value in items.items():
            cookies.set(name, value)
        return cookies

    def to_dict(self) -> dict[str, str]:
        """Export all cookies as a flat name→value dict (last write wins)."""
        return {c.name: c.value for c in self._store}

    def __iter__(self) -> Iterator[_Cookie]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        names = [c.name for c in self._store]
        return f"CrossHostCookieJar({names})"
