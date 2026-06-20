"""Reception domain models (Ext.Direct ``Reception`` action).

Appointment slots for parent/student reception sessions.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from ._base import EduObject
from .enums import ReceptionAudience, ReceptionStatus


class ReceptionSlot(EduObject):
    """A single reception appointment slot.

    Attributes:
        guid: slot GUID (``SYS_GUID``).
        teacher_name: teacher offering this slot.
        date_str: date string ``"DD.MM.YYYY"``.
        time_begin: slot start time ``"HH:MM"``.
        time_end: slot end time ``"HH:MM"``.
        status: booking status (:class:`~pskovedu.models.enums.ReceptionStatus`).
        audience: target audience (:class:`~pskovedu.models.enums.ReceptionAudience`).
        location: reception location/room, or ``None``.
        booked_by: GUID of user who booked the slot, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: str = Field(..., alias="SYS_GUID")
    teacher_name: str = Field(..., alias="teacherName")
    date_str: str = Field(..., alias="date")
    time_begin: str = Field(..., alias="timeBegin")
    time_end: str = Field(..., alias="timeEnd")
    status: ReceptionStatus | None = Field(None, alias="status")
    audience: ReceptionAudience | None = Field(None, alias="type")
    location: str | None = Field(None, alias="location")
    booked_by: str | None = Field(None, alias="bookedBy")

    @property
    def is_available(self) -> bool:
        """``True`` when the slot has :attr:`ReceptionStatus.OPEN` status."""
        return self.status == ReceptionStatus.OPEN
