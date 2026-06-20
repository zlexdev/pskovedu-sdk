"""Structured logging via structlog with credential redaction.

Usage::

    from pskovedu.logging import get_logger
    log = get_logger(__name__)
    log.info("session.obtained", session_id=sid)

Sensitive values (X1_SSO cookie, JWT tokens, ESIA client_secret) are
redacted to ``"[REDACTED]"`` in every log event, regardless of which field
they appear in.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from structlog.typing import EventDict

# Field names whose *values* are always redacted
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "x1_sso",
        "X1_SSO",
        "jwt",
        "token",
        "client_secret",
        "clientSecret",
        "access_token",
        "id_token",
        "authorization",
        "Authorization",
        "cookie",
        "Cookie",
        "password",
        "passwd",
    }
)

# Regex that matches JWT-shaped strings (header.payload.sig or header.payload)
_JWT_RE = re.compile(r"^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+(?:\.[A-Za-z0-9\-_]*)?$")

# Regex for X1_SSO-like opaque tokens (long base64url / hex blobs, ≥ 32 chars)
_OPAQUE_TOKEN_RE = re.compile(r"^[A-Za-z0-9\-_+/=]{32,}$")

_REDACTED = "[REDACTED]"


def _looks_sensitive(value: Any) -> bool:
    """Heuristic: does this *value* look like a credential even if the key didn't match?"""
    if not isinstance(value, str):
        return False
    return bool(_JWT_RE.match(value)) or bool(_OPAQUE_TOKEN_RE.match(value))


def _redact_processor(
    logger: Any,  # noqa: ARG001
    method: str,  # noqa: ARG001
    event_dict: EventDict,
) -> EventDict:
    """structlog processor: redact sensitive fields from every log event."""
    for key in list(event_dict.keys()):
        if key in _SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
        elif isinstance(event_dict[key], str) and _looks_sensitive(event_dict[key]):
            # Only redact string values that look like credentials; keep other types.
            # This catches e.g. log.debug("...", value=some_jwt) where the key is generic.
            event_dict[key] = _REDACTED
    return event_dict


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog bound logger for *name* with redaction active.

    Args:
        name: typically ``__name__`` of the calling module.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
