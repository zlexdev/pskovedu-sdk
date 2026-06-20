"""Common value types used across multiple domain models.

These primitives are imported by every domain model file; keep this module
free of domain-specific imports.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, TypeVar

from pydantic import AfterValidator

from ..utils.url_encode import validate_guid, validate_uuid
from ._base import EduObject

Guid = Annotated[str, AfterValidator(validate_guid)]
"""Uppercase hex GUID, 30–40 chars, with optional ``{}`` braces.

Used as the primary key for schedule grades, diary participants, journal
entries, and all X1 ORM records.
"""

Uuid = Annotated[str, AfterValidator(validate_uuid)]
"""Standard RFC 4122 UUID string (``xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx``).

Used for QR subscribe streams, JWT ``jti``, and ESIA avatar lookups.
"""


MarkWeight = Decimal
"""Mark weight for academic grades.  Always ``Decimal``; never ``float``.

Rule: money/weight primitives must not lose precision via floating-point
arithmetic (see code-quality rules).
"""


class DateWindow(EduObject):
    """A half-open ``[start, end]`` date interval used for diary/schedule pagination.

    Args:
        start: first day of the window (inclusive).
        end: last day of the window (inclusive).
    """

    start: date
    end: date


T = TypeVar("T")


class EduPage[T](EduObject):
    """Generic paginated result envelope returned by list endpoints.

    Args:
        items: the page of domain objects.
    """

    items: list[T]
