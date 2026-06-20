"""XLS export handles — wrapper for diary/marks-report XLS downloads.

:class:`XlsExport` wraps raw XLS bytes and provides save/open helpers.
The SDK returns ``bytes`` directly from REST calls; this class adds
a convenience layer for callers who need to persist or process the file.

Usage::

    raw = await client(GetDiaryXls(participant_guid=guid))
    xls = XlsExport(raw, filename="diary_week.xls")
    xls.save(Path("~/Downloads"))
"""

from __future__ import annotations

from pathlib import Path

from ..logging import get_logger

log = get_logger(__name__)


class XlsExport:
    """Wrapper for raw XLS bytes downloaded from the portal.

    Args:
        data: raw XLS bytes from a portal export endpoint.
        filename: suggested filename (with extension).  Default ``"export.xls"``.
    """

    def __init__(self, data: bytes, filename: str = "export.xls") -> None:
        if not data:
            raise ValueError("XlsExport: cannot wrap empty bytes — the export response was empty.")
        self._data = data
        self.filename = filename

    @property
    def data(self) -> bytes:
        """Raw XLS bytes."""
        return self._data

    def __len__(self) -> int:
        return len(self._data)

    def save(self, directory: Path, filename: str | None = None) -> Path:
        """Write the XLS bytes to *directory* / *filename*.

        Creates *directory* if it does not exist.

        Args:
            directory: target directory.
            filename: override filename (defaults to ``self.filename``).
        """
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (filename or self.filename)
        target.write_bytes(self._data)
        log.info("assets.xls.saved", path=str(target), size=len(self._data))
        return target

    def __repr__(self) -> str:
        return f"XlsExport(filename={self.filename!r}, size={len(self._data)})"
