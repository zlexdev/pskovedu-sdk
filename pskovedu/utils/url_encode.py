"""URL / GUID / UUID validation and query-string encoding utilities."""

from __future__ import annotations

import re
import urllib.parse
from uuid import UUID

# pskovedu GUIDs are uppercase hex strings, 30–40 chars, optionally wrapped in {}.
# Source: html_pages.md — X1_CONFIG meta.models SYS_GUID is 32 hex chars;
#         05-risks.md R13 — "some are 30, some 32, some braced {…} in X1_CONFIG".
_GUID_BARE_RE = re.compile(r"^[0-9A-Fa-f]{30,40}$")
_GUID_BRACED_RE = re.compile(r"^\{[0-9A-Fa-f]{30,40}\}$")


def validate_guid(value: str) -> str:
    """Validate and normalise a pskovedu GUID.

    Accepts:
    - Bare uppercase or lowercase hex, 30–40 chars.
    - Braced ``{hex}`` variants (as found in ``X1_CONFIG``).

    Returns the value unchanged (normalisation is left to caller — the portal
    accepts mixed-case GUIDs and normalising could break opaque keys).

    Raises:
        ValueError: when the value does not match the expected pattern.
    """
    if _GUID_BARE_RE.match(value) or _GUID_BRACED_RE.match(value):
        return value
    raise ValueError(f"Invalid GUID {value!r}: expected 30–40 hex chars, optionally braced.")


def validate_uuid(value: str) -> str:
    """Validate a standard RFC 4122 UUID string (case-insensitive, with hyphens).

    Args:
        value: UUID string to validate.

    Raises:
        ValueError: when the value is not a valid UUID.
    """
    try:
        UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid UUID {value!r}: {exc}") from exc
    return value


def encode_query(params: dict[str, str | int | float | bool | None]) -> str:
    """Encode a flat dict into a URL query string, omitting ``None`` values.

    Args:
        params: key-value pairs to encode.  ``None`` values are skipped.
    """
    filtered = {k: str(v) for k, v in params.items() if v is not None}
    return urllib.parse.urlencode(filtered)
