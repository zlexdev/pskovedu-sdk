"""JWT decode utilities — base64url header + payload decode, NO signature verify.

The portal uses HS256 (symmetric) JWTs; we don't have the server secret and
don't need to verify — we only need to read ``exp``, ``iat``, ``jti``, and
``sessionId`` from the payload.
"""

from __future__ import annotations

import base64
import json
from typing import Any


def _b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, adding padding as needed."""
    # base64url uses '-' and '_'; standard base64 uses '+' and '/'
    segment = segment.replace("-", "+").replace("_", "/")
    # Pad to a multiple of 4
    padding = 4 - len(segment) % 4
    if padding != 4:
        segment += "=" * padding
    return base64.b64decode(segment)


def decode_header(token: str) -> dict[str, Any]:
    """Decode the JOSE header of a JWT without verifying the signature.

    Args:
        token: raw JWT string in ``header.payload[.signature]`` format.

    Raises:
        ValueError: when the token is malformed or the header is not valid JSON.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError(f"Malformed JWT: expected at least 2 parts, got {len(parts)}")
    try:
        raw = _b64url_decode(parts[0])
        return dict(json.loads(raw))
    except Exception as exc:
        raise ValueError(f"Failed to decode JWT header: {exc}") from exc


def decode_payload(token: str) -> dict[str, Any]:
    """Decode the payload claims of a JWT without verifying the signature.

    Args:
        token: raw JWT string in ``header.payload[.signature]`` format.

    Raises:
        ValueError: when the token is malformed or the payload is not valid JSON.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError(f"Malformed JWT: expected at least 2 parts, got {len(parts)}")
    try:
        raw = _b64url_decode(parts[1])
        return dict(json.loads(raw))
    except Exception as exc:
        raise ValueError(f"Failed to decode JWT payload: {exc}") from exc
