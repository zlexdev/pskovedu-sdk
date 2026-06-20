"""Parse ``window.REMOTING_API`` and ``window.X1_CONFIG`` from the GET / shell HTML.

The portal injects both globals as inline ``<script>`` blocks:

.. code-block:: html

    <script type="text/javascript">
        window.REMOTING_API = { ... };
        window.X1_CONFIG    = { ... };
    </script>

Both are standard JSON objects (not JS expressions with function calls), so
a regex to locate the assignment + ``json.loads`` on the captured group is
sufficient and avoids a full JS runtime dependency.

Usage::

    cfg = parse_shell(html, url="https://one.pskovedu.ru/")
    print(cfg.remoting_api_url)   # "/extjs/direct"
    print(cfg.model_guid("JOURNAL"))
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..exceptions import HtmlParseError
from ..logging import get_logger
from ..models.session import RoleMeta, ShellConfig, X1ModelRef

log = get_logger(__name__)

# Matches:  window.REMOTING_API = { ... };
# The value must start with { or [; we capture everything up to the matching
# closing brace/bracket via a "scan for balanced braces" approach, but since
# these are always flat JSON objects we use a greedy-then-validate strategy:
# capture everything from the first { to the last } on the same logical block.
_REMOTING_RE = re.compile(
    r"window\.REMOTING_API\s*=\s*(\{[\s\S]*?\})\s*;",
    re.MULTILINE,
)
_X1CONFIG_RE = re.compile(
    r"window\.X1_CONFIG\s*=\s*(\{[\s\S]*?\})\s*;",
    re.MULTILINE,
)

# Fallback: wider capture up to the next window. assignment or </script>
_REMOTING_WIDE_RE = re.compile(
    r"window\.REMOTING_API\s*=\s*(\{[\s\S]+?\})\s*(?:;|\n\s*window\.|\n\s*</script>)",
    re.MULTILINE,
)
_X1CONFIG_WIDE_RE = re.compile(
    r"window\.X1_CONFIG\s*=\s*(\{[\s\S]+?\})\s*(?:;|\n\s*window\.|\n\s*</script>)",
    re.MULTILINE,
)


def _extract_json(
    html: str, pattern: re.Pattern[str], wide: re.Pattern[str], label: str, url: str
) -> dict[str, Any]:
    """Extract a JSON object assigned to a JS global variable.

    Tries the tight pattern first, then the wide fallback.  Validates that the
    extracted text is valid JSON before returning.

    Args:
        html: raw HTML text of the page.
        pattern: tight regex (greedy-non-greedy ``{...}``).
        wide: wider fallback regex.
        label: human-readable name of the global (for error messages).
        url: page URL (included in :exc:`HtmlParseError`).

    Raises:
        HtmlParseError: when neither pattern finds a valid JSON block.
    """
    for pat in (pattern, wide):
        m = pat.search(html)
        if not m:
            continue
        candidate = m.group(1)
        # Attempt to find the correctly balanced JSON by scanning from the first {
        parsed = _try_parse_json_block(candidate)
        if parsed is not None:
            return parsed

    raise HtmlParseError(label, url)


def _try_parse_json_block(text: str) -> dict[str, Any] | None:
    """Try to parse *text* as a JSON object; return ``None`` on failure.

    Uses a bracket-depth scan to find the end of the first top-level JSON
    object, then validates with ``json.loads``.
    """
    text = text.strip()
    if not text.startswith("{"):
        return None
    depth = 0
    in_string = False
    escape = False
    end = -1
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        return dict(json.loads(text[: end + 1]))
    except json.JSONDecodeError:
        return None


def _parse_remoting(data: dict[str, Any]) -> tuple[str, dict[str, list[dict[str, Any]]]]:
    """Extract ``url`` and ``actions`` from the parsed ``REMOTING_API`` dict.

    Args:
        data: parsed JSON of ``window.REMOTING_API``.
    """
    url: str = data.get("url") or "/extjs/direct"
    actions: dict[str, list[dict[str, Any]]] = data.get("actions") or {}
    return url, actions


def _parse_x1config(data: dict[str, Any]) -> tuple[RoleMeta | None, list[X1ModelRef]]:
    """Extract ``role_meta`` and ``models`` from ``X1_CONFIG``.

    Args:
        data: parsed JSON of ``window.X1_CONFIG``.
    """
    meta: dict[str, Any] = data.get("meta") or {}

    # Role metadata lives under meta.au
    au_raw: dict[str, Any] | None = meta.get("au")
    role_meta: RoleMeta | None = None
    if au_raw and isinstance(au_raw, dict):
        try:
            role_meta = RoleMeta.model_validate(au_raw)
        except Exception:
            log.warning("shell.role_meta.parse_failed", au_keys=list(au_raw.keys()))

    # Model catalog lives under meta.models (list of {SYS_GUID, NAME, ALIAS})
    models_raw: list[Any] = meta.get("models") or []
    models: list[X1ModelRef] = []
    for entry in models_raw:
        if not isinstance(entry, dict):
            continue
        try:
            models.append(X1ModelRef.model_validate(entry))
        except Exception:
            log.debug("shell.model_ref.skip", entry=entry)

    return role_meta, models


def parse_shell(html: str, url: str = "https://one.pskovedu.ru/") -> ShellConfig:
    """Parse the portal shell HTML and return a :class:`~pskovedu.models.session.ShellConfig`.

    Extracts ``window.REMOTING_API`` and ``window.X1_CONFIG`` from inline
    ``<script>`` blocks.  Both globals are standard JSON objects assigned with
    ``window.X = {...};`` so no JS evaluation is needed.

    Args:
        html: raw HTML text of ``GET /`` response.
        url: canonical URL of the page (used in error messages).

    Raises:
        HtmlParseError: when either ``REMOTING_API`` or ``X1_CONFIG`` cannot be
            found or is not valid JSON.
    """
    remoting_data = _extract_json(html, _REMOTING_RE, _REMOTING_WIDE_RE, "REMOTING_API", url)
    x1config_data = _extract_json(html, _X1CONFIG_RE, _X1CONFIG_WIDE_RE, "X1_CONFIG", url)

    remoting_url, actions = _parse_remoting(remoting_data)
    role_meta, models = _parse_x1config(x1config_data)

    log.debug(
        "shell.parsed",
        remoting_url=remoting_url,
        action_count=len(actions),
        model_count=len(models),
    )
    return ShellConfig(
        remoting_api_url=remoting_url,
        remoting_actions=actions,
        role_meta=role_meta,
        models=models,
    )
