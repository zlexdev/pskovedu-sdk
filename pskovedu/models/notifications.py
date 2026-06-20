"""Notification domain models.

Portal notifications come from two surfaces:
1. Ext.Direct ``X1API.direct`` with ``service="utility", method="getusernotifications"``.
2. X1 ORM ``USER_NOTIFICATION`` model via :class:`~pskovedu.methods.notifications.GetUserNotifications`.

Both return the same wire shape (``SYS_*`` prefix fields + ``TITLE``/``MESSAGE``/``TYPE``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ConfigDict, Field

from ._base import EduObject
from .enums import NotificationKind


def _parse_portal_dt(value: str) -> datetime:
    """Parse ``"DD.MM.YYYY HH:MM:SS"`` or ``"DD.MM.YYYY HH:MM:SS.ffffff"`` into UTC datetime."""
    for fmt in ("%d.%m.%Y %H:%M:%S.%f", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse portal datetime: {value!r}")


class UserNotification(EduObject):
    """A portal notification / announcement record.

    Wire source: ``X1API.direct`` (utility/getusernotifications) or
    ``/x1db/service/call`` with ``USER_NOTIFICATION`` model.

    All datetime strings from the portal are in ``"DD.MM.YYYY HH:MM:SS"`` format
    (no timezone — treated as UTC).

    Attributes:
        guid: primary key GUID (``SYS_GUID``).
        guidfk: foreign key GUID, or ``None``.
        state: record state string (``SYS_STATE``).
        rev: revision counter string (``SYS_REV``).
        user: last-modifier user GUID (``SYS_USER``).
        creator: creator user GUID (``SYS_CREATOR``).
        created_at: UTC-aware creation datetime.
        updated_at: UTC-aware last-update datetime.
        title: HTML title string.
        message: HTML message body.
        kind: notification type (:class:`~pskovedu.models.enums.NotificationKind`).
        time_begin: notification display start (UTC-aware).
        time_end: notification display end (UTC-aware).
        duration: display duration in days (as string on wire).
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="SYS_GUID")
    guidfk: str | None = Field(None, alias="SYS_GUIDFK")
    state: str | None = Field(None, alias="SYS_STATE")
    rev: str | None = Field(None, alias="SYS_REV")
    parent_guid: str | None = Field(None, alias="SYS_PARENTGUID")
    user: str | None = Field(None, alias="SYS_USER")
    creator: str | None = Field(None, alias="SYS_CREATOR")
    created_raw: str | None = Field(None, alias="SYS_CREATED")
    updated_raw: str | None = Field(None, alias="SYS_UPDATED")
    title: str = Field("", alias="TITLE")
    message: str = Field("", alias="MESSAGE")
    kind_raw: str | None = Field(None, alias="TYPE")
    time_begin_raw: str | None = Field(None, alias="TIME_BEGIN")
    time_end_raw: str | None = Field(None, alias="TIME_END")
    duration: str | None = Field(None, alias="DURATION")

    @property
    def kind(self) -> NotificationKind | None:
        """Parse ``TYPE`` into a :class:`~pskovedu.models.enums.NotificationKind`."""
        if not self.kind_raw:
            return None
        try:
            return NotificationKind(self.kind_raw)
        except ValueError:
            return None

    @property
    def created_at(self) -> datetime | None:
        """Parse ``SYS_CREATED`` into a UTC-aware :class:`datetime.datetime`."""
        if not self.created_raw:
            return None
        return _parse_portal_dt(self.created_raw)

    @property
    def updated_at(self) -> datetime | None:
        """Parse ``SYS_UPDATED`` into a UTC-aware :class:`datetime.datetime`."""
        if not self.updated_raw:
            return None
        return _parse_portal_dt(self.updated_raw)

    @property
    def time_begin(self) -> datetime | None:
        """Parse ``TIME_BEGIN`` into a UTC-aware :class:`datetime.datetime`."""
        if not self.time_begin_raw:
            return None
        return _parse_portal_dt(self.time_begin_raw)

    @property
    def time_end(self) -> datetime | None:
        """Parse ``TIME_END`` into a UTC-aware :class:`datetime.datetime`."""
        if not self.time_end_raw:
            return None
        return _parse_portal_dt(self.time_end_raw)

    def is_active(self, now: datetime | None = None) -> bool:
        """Return ``True`` when the notification is currently active.

        Args:
            now: UTC-aware datetime (defaults to ``datetime.now(UTC)``).
        """
        reference = now or datetime.now(UTC)
        begin = self.time_begin
        end = self.time_end
        if begin is not None and reference < begin:
            return False
        return not (end is not None and reference > end)
