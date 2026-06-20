"""Schedule domain models.

Wire shapes from:
``GET /schedule/index/schedule/grade/{grade_guid}/{date}?single=1``

Response envelope: ``{success, message, data: [SchoolShift, ...]}``.
``LESSON_TIMES`` contains ordered lesson slots; ``LESSONS`` per slot may be
empty (no lessons on that day) or populated with subject/teacher/classroom.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

from pydantic import ConfigDict, Field

from ._base import EduObject
from .common import Guid


class LessonTime(EduObject):
    """A single timetable slot (bell time) within a school shift.

    Wire fields use ``UPPER_CASE`` aliases; access via snake_case.

    Attributes:
        sys_guid: opaque record GUID.
        number: slot ordinal (0-indexed).
        time_begin: lesson start time as ``"HH:MM"`` string.
        time_end: lesson end time as ``"HH:MM"`` string.
        lessons: list of lessons scheduled in this slot (may be empty).
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    sys_guid: str = Field(..., alias="SYS_GUID")
    number: int = Field(..., alias="NUMBER")
    time_begin: str = Field(..., alias="TIME_BEGIN")
    time_end: str = Field(..., alias="TIME_END")
    lessons: list[Lesson] = Field(default_factory=list, alias="LESSONS")

    @property
    def start_time(self) -> time:
        """Parse ``TIME_BEGIN`` into a :class:`datetime.time` object."""
        h, m = self.time_begin.split(":")
        return time(int(h), int(m))

    @property
    def end_time(self) -> time:
        """Parse ``TIME_END`` into a :class:`datetime.time` object."""
        h, m = self.time_end.split(":")
        return time(int(h), int(m))

    def is_active(self, now: datetime | None = None) -> bool:
        """Return ``True`` when the current time falls within this lesson slot.

        Args:
            now: UTC-aware datetime to compare against (defaults to ``datetime.now(UTC)``).
        """
        current = (now or datetime.now(UTC)).time()
        return self.start_time <= current <= self.end_time


class Lesson(EduObject):
    """A single lesson entry within a :class:`LessonTime` slot.

    Fields were empty in the HAR capture (no lessons scheduled on that date);
    shape inferred from the portal's JS rendering logic.

    Attributes:
        sys_guid: opaque record GUID.
        subject: subject name, or ``None`` when absent.
        teacher: teacher display name, or ``None``.
        classroom: classroom identifier, or ``None``.
        homework: homework text, or ``None``.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    sys_guid: str = Field(..., alias="SYS_GUID")
    subject: str | None = Field(None, alias="SUBJECT")
    teacher: str | None = Field(None, alias="TEACHER")
    classroom: str | None = Field(None, alias="CLASSROOM")
    homework: str | None = Field(None, alias="HOMEWORK")


class SchoolShift(EduObject):
    """A school shift (смена) containing ordered lesson time slots.

    Typical names: ``"1-я смена. 1, 5, 7-11 кл."``

    Attributes:
        sys_guid: opaque shift GUID.
        name: Russian shift name string.
        lesson_times: ordered list of :class:`LessonTime` slots.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    sys_guid: str = Field(..., alias="SYS_GUID")
    name: str = Field(..., alias="NAME")
    lesson_times: list[LessonTime] = Field(default_factory=list, alias="LESSON_TIMES")


class ScheduleDay(EduObject):
    """A full schedule day: multiple shifts each with ordered lesson slots.

    This is the SDK-level aggregate returned by
    :class:`~pskovedu.methods.schedule.GetSchedule`.  The raw ``data`` array
    (list of shifts) is wrapped here to provide helper methods.

    Attributes:
        grade_guid: GUID of the grade this schedule belongs to.
        date_str: date of this schedule in ``"DD.MM.YYYY"`` format.
        shifts: list of :class:`SchoolShift` entries.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    grade_guid: Guid
    date_str: str
    shifts: list[SchoolShift] = Field(default_factory=list)

    def current_lesson(self, now: datetime | None = None) -> LessonTime | None:
        """Return the :class:`LessonTime` slot that is currently active.

        Iterates all shifts' lesson times and returns the first slot whose
        ``[TIME_BEGIN, TIME_END]`` window contains ``now``.

        Args:
            now: UTC-aware datetime (defaults to ``datetime.now(UTC)``).
        """
        reference = now or datetime.now(UTC)
        for shift in self.shifts:
            for slot in shift.lesson_times:
                if slot.is_active(reference):
                    return slot
        return None

    def all_lesson_times(self) -> list[LessonTime]:
        """Return all lesson time slots across all shifts, in order."""
        result: list[LessonTime] = []
        for shift in self.shifts:
            result.extend(shift.lesson_times)
        return result


# Rebuild forward refs
LessonTime.model_rebuild()
