"""Shared type aliases for raw wire-format boundary values."""

from __future__ import annotations

JournalCellValue = str | int | float | bool | None
"""Value type for a single cell in a journal row (ExtDirect wire format)."""

X1Filter = dict[str, str | int | None]
"""X1 ORM filter dict — keys are X1 field names (e.g. ``"SYS_STATE"``), values are filter literals."""
