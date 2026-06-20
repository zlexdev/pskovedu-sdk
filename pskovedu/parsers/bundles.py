"""Extract versioned ``<script>`` and ``<link>`` build URLs from the portal shell HTML.

The portal serves versioned assets using MD5-hash suffixes in filenames::

    /app/eservicediaryview/build/es_diary_view_participant_v{HASH}.css
    /app/eservicediaryview/build/es_diary_view_participant_v{HASH}.js
    /app/eservicescheduleview/build/es_schedule_one_day_v{HASH}.js

Usage::

    urls = parse_bundle_urls(html)
    # urls.scripts  -> ["/app/.../build/name_vABC.js", ...]
    # urls.styles   -> ["/app/.../build/name_vABC.css", ...]
    # urls.all      -> combined list, scripts first
"""

from __future__ import annotations

from dataclasses import dataclass, field

from selectolax.parser import HTMLParser

from ..logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class BundleUrls:
    """Versioned build asset URLs extracted from the portal shell HTML.

    Attributes:
        scripts: list of JavaScript bundle URLs (``*.js``), in document order.
        styles: list of CSS bundle URLs (``*.css``), in document order.
    """

    scripts: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[str]:
        """All bundle URLs — scripts first, then styles."""
        return list(self.scripts) + list(self.styles)


def parse_bundle_urls(html: str) -> BundleUrls:
    """Extract versioned build asset URLs from the portal shell HTML.

    Collects all ``<script src="...">`` and ``<link href="...">`` URLs that
    contain ``/build/`` in their path.  No hardcoded paths or hash patterns are
    used — any versioned build asset is included.

    Deduplicates while preserving document order.

    Args:
        html: raw HTML text of the portal shell page.
    """
    tree = HTMLParser(html)
    scripts: list[str] = []
    styles: list[str] = []
    seen: set[str] = set()

    for node in tree.css("script[src]"):
        url = node.attributes.get("src") or ""
        if "/build/" in url.lower() and url not in seen:
            seen.add(url)
            scripts.append(url)

    for node in tree.css("link[href]"):
        rel = node.attributes.get("rel") or ""
        href = node.attributes.get("href") or ""
        if (
            "stylesheet" in rel
            and "/build/" in href.lower()
            and href.endswith(".css")
            and href not in seen
        ):
            seen.add(href)
            styles.append(href)

    log.debug(
        "bundles.parsed",
        script_count=len(scripts),
        style_count=len(styles),
    )
    return BundleUrls(scripts=scripts, styles=styles)
