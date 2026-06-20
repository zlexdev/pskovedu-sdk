"""Monitoring domain models (Ext.Direct ``monitoring`` action).

The monitoring system tracks student absences per lesson.
Wire fields use a mix of UPPER_CASE X1-style names and camelCase.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from ._base import EduObject
from .enums import AbsenceKind


class AbsenceRow(EduObject):
    """A single student absence record in the monitoring system.

    Attributes:
        student_guid: GUID of the student.
        student_name: student full name.
        lesson_date: date string ``"DD.MM.YYYY"``.
        lesson_number: lesson slot number.
        absence_kind: type of absence (:class:`~pskovedu.models.enums.AbsenceKind`).
        subject: subject name, or ``None``.
        teacher: teacher name, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    student_guid: str = Field(..., alias="studentGuid")
    student_name: str = Field(..., alias="studentName")
    lesson_date: str = Field(..., alias="lessonDate")
    lesson_number: int | None = Field(None, alias="lessonNumber")
    absence_kind: AbsenceKind | None = Field(None, alias="absenceKind")
    subject: str | None = Field(None, alias="subject")
    teacher: str | None = Field(None, alias="teacher")


class MonitoringResult(EduObject):
    """Aggregated monitoring result for a grade.

    Contains the list of absence rows returned by ``monitoring.read`` or
    ``monitoring.readskip``.

    Attributes:
        rows: list of :class:`AbsenceRow` entries.
        grade_guid: GUID of the queried grade, or ``None``.
        total: total absence count, or ``None`` when not provided.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    rows: list[AbsenceRow] = Field(default_factory=list)
    grade_guid: str | None = None
    total: int | None = None
