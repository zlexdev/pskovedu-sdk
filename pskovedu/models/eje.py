"""EJE (electronic journal) response DTOs.

All shapes are **unverified** — response bodies for these endpoints have not
been captured in HAR.  ``EjeResult.data`` is kept permissive until a capture
is available to tighten the contract (see decision D7 in 00-decisions.md).
"""

from __future__ import annotations

from typing import Any

from ._base import EduObject


# unverified shape
class EjeResult(EduObject):
    """Envelope returned by every ``/eje/*`` read endpoint.

    Attributes:
        success: server-side success flag (defaults to ``True``).
        message: optional human-readable message (error detail or ``None``).
        data: payload — list of records or a single object map; ``None`` when
            the endpoint returns no data.  Shape is unverified; tighten once
            HAR captures are available.
    """

    success: bool = True
    message: str | None = None
    data: list[dict[str, Any]] | dict[str, Any] | None = None  # unverified shape
