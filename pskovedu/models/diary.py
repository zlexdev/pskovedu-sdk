"""Diary domain models.

Wire shapes from:
- ``GET /edv/index/diary/{student_guid}?date=DD.MM.YYYY``
- ``GET /edv/index/diary/{student_guid}/marks-report``   (marks report)
- ``GET /edv/index/diary/{student_guid}/xls``             (XLS export)

``DiaryWeek`` is the main EduObject with bound methods for pagination,
export, and convenience helpers.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field

from ._base import EduObject
from .common import DateWindow, Guid, MarkWeight

if TYPE_CHECKING:
    from ..methods.diary import GetDiary, GetDiaryXls, GetMarksReport


def _parse_ru_date(value: str) -> date:
    """Parse ``DD.MM.YYYY`` portal date string into a :class:`datetime.date`."""
    return datetime.strptime(value, "%d.%m.%Y").date()


class EduPeriod(EduObject):
    """An academic period (year / quarter / trimester / semester).

    Wire fields use camelCase aliases.  Hierarchy: top-level year periods have
    ``parent_edu_period_guid == ""``, sub-periods have it set to the year GUID.

    Attributes:
        school_edu_period_guid: school-specific period GUID.
        edu_period_guid: system-wide period GUID.
        parent_edu_period_guid: parent period GUID, or ``""`` for year periods.
        name: Russian display name, e.g. ``"Первый квартал"``.
        date_begin: first day of the period.
        date_end: last day of the period.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    school_edu_period_guid: str = Field(..., alias="schoolEduPeriodGuid")
    edu_period_guid: str = Field(..., alias="eduPeriodGuid")
    parent_edu_period_guid: str = Field("", alias="parentEduPeriodGuid")
    name: str
    date_begin: str = Field(..., alias="dateBegin")
    date_end: str = Field(..., alias="dateEnd")

    @property
    def is_year_period(self) -> bool:
        """``True`` when this is a top-level year period (no parent)."""
        return not self.parent_edu_period_guid

    @property
    def start(self) -> date:
        """Parse ``dateBegin`` into a :class:`datetime.date`."""
        return _parse_ru_date(self.date_begin)

    @property
    def end(self) -> date:
        """Parse ``dateEnd`` into a :class:`datetime.date`."""
        return _parse_ru_date(self.date_end)


class DiaryEntry(EduObject):
    """A single lesson/day entry in the diary.

    Fields were empty in the HAR capture; shape inferred from the portal JS
    rendering.  All fields are optional to handle partial responses.

    Attributes:
        entry_date: entry date as ``"DD.MM.YYYY"``.
        subject: subject name.
        grade: mark string (e.g. ``"5"``, ``"н"``, ``"пт"``).
        homework: homework assignment text.
        topic: lesson topic.
        remark: teacher remark.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    entry_date: str | None = Field(None, alias="date")
    subject: str | None = None
    grade: str | None = None
    homework: str | None = None
    topic: str | None = None
    remark: str | None = None

    @property
    def parsed_date(self) -> date | None:
        """Parse ``date`` into a :class:`datetime.date`, or ``None`` if absent."""
        if not self.entry_date:
            return None
        return _parse_ru_date(self.entry_date)


class DiaryWeek(EduObject):
    """A week's worth of diary data with bound navigation and export methods.

    Bound via ``.as_(client)`` by the session funnel.  Provides:
    - :meth:`next_week` / :meth:`prev_week` — navigate to adjacent weeks.
    - :meth:`export_xls` — download the week as XLS.
    - :meth:`missing_homework` — filter entries without homework.
    - :meth:`marks_by_subject` — group grades by subject name.

    Attributes:
        participant_guid: GUID of the diary participant.
        date_window: the :class:`~pskovedu.models.common.DateWindow` this week covers.
        entries: diary entries for the week.
        edu_periods: list of academic periods available for this student.
        dop_diary_url: URL to supplementary diary portal.
        edu_program_url: URL to education programme, may be empty.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    participant_guid: Guid
    date_window: DateWindow
    entries: list[DiaryEntry] = Field(default_factory=list)
    edu_periods: list[EduPeriod] = Field(default_factory=list, alias="edu_periods")
    dop_diary_url: str = ""
    edu_program_url: str = ""

    def next_week(self) -> GetDiary:
        """Return a :class:`~pskovedu.methods.diary.GetDiary` for the following week.

        The new window starts the day after this week's end.
        """
        from datetime import timedelta

        from ..methods.diary import GetDiary

        new_start = self.date_window.end + timedelta(days=1)
        return GetDiary(
            participant_guid=self.participant_guid,
            date=new_start.strftime("%d.%m.%Y"),
        ).as_(self._require_client())

    def prev_week(self) -> GetDiary:
        """Return a :class:`~pskovedu.methods.diary.GetDiary` for the previous week.

        The new window ends the day before this week's start.
        """
        from datetime import timedelta

        from ..methods.diary import GetDiary

        new_end = self.date_window.start - timedelta(days=1)
        return GetDiary(
            participant_guid=self.participant_guid,
            date=new_end.strftime("%d.%m.%Y"),
        ).as_(self._require_client())

    def export_xls(self) -> GetDiaryXls:
        """Return a :class:`~pskovedu.methods.diary.GetDiaryXls` for this week."""
        from ..methods.diary import GetDiaryXls

        return GetDiaryXls(
            participant_guid=self.participant_guid,
            date=self.date_window.start.strftime("%d.%m.%Y"),
        ).as_(self._require_client())

    def missing_homework(self) -> list[DiaryEntry]:
        """Return entries where ``homework`` is ``None`` or empty.

        Useful for identifying lessons with no assignment recorded.
        """
        return [e for e in self.entries if not e.homework]

    def marks_by_subject(self) -> dict[str, list[str]]:
        """Group non-empty grade strings by subject name."""
        result: dict[str, list[str]] = {}
        for entry in self.entries:
            if entry.subject and entry.grade:
                result.setdefault(entry.subject, []).append(entry.grade)
        return result


class SubjectMark(EduObject):
    """A mark/grade entry in the marks report.

    Attributes:
        subject: subject name.
        mark: mark string (e.g. ``"5"``, ``"4"``).
        weight: decimal weight for weighted average calculation.
        period_name: academic period name this mark belongs to.
        mark_date: date string the mark was given.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    subject: str
    mark: str
    weight: MarkWeight = Field(default=Decimal("1"))
    period_name: str | None = None
    mark_date: str | None = None


class MarksReport(EduObject):
    """Marks report for a student covering one or more academic periods.

    Bound via ``.as_(client)`` — provides :meth:`weighted_average` and
    :meth:`export_xls`.

    Attributes:
        participant_guid: GUID of the participant.
        marks: list of :class:`SubjectMark` entries.
        period_name: name of the period this report covers.
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    participant_guid: Guid
    marks: list[SubjectMark] = Field(default_factory=list)
    period_name: str | None = None

    def weighted_average(self, subject: str | None = None) -> Decimal:
        """Compute the weighted average mark across all (or a single) subject.

        Uses ``Decimal`` arithmetic to avoid floating-point imprecision.

        Args:
            subject: when given, restrict calculation to that subject only.
        """
        entries = [m for m in self.marks if (subject is None or m.subject == subject)]

        total_weight = Decimal("0")
        weighted_sum = Decimal("0")

        for entry in entries:
            try:
                numeric = Decimal(entry.mark)
            except Exception:
                continue  # skip non-numeric marks (н, пт, etc.)
            total_weight += entry.weight
            weighted_sum += numeric * entry.weight

        if total_weight == Decimal("0"):
            return Decimal("0")
        return weighted_sum / total_weight

    def export_xls(self, with_dates: bool = False) -> GetMarksReport:
        """Return a :class:`~pskovedu.methods.diary.GetMarksReport` for XLS export.

        Args:
            with_dates: when ``True``, include date columns in the export.
        """
        from ..methods.diary import GetMarksReport

        return GetMarksReport(
            participant_guid=self.participant_guid,
            with_dates=with_dates,
        ).as_(self._require_client())


class Participant(EduObject):
    """A diary participant (student) with bound diary and marks-report methods.

    Obtained from ``GET /edv/index/participant`` SSR parsing.

    Attributes:
        guid: GUID from ``#participant[data-guid]``.
        full_name: student full name (ФИО), e.g. ``"Иванов Александр Романович"``.
        grade_label: class label, e.g. ``"11У"``.
        school: school display name.
        role: participant role (``"participant"`` / ``"teacher"`` / ``"admin"``).
    """

    model_config = ConfigDict(populate_by_name=True, strict=False)

    guid: Guid
    full_name: str = ""
    grade_label: str = ""
    school: str = ""
    role: str = "participant"

    def diary(self, diary_date: date | None = None) -> GetDiary:
        """Return a :class:`~pskovedu.methods.diary.GetDiary` for this participant.

        Args:
            diary_date: date to fetch (defaults to today).
        """
        from ..methods.diary import GetDiary

        date_str = (diary_date or date.today()).strftime("%d.%m.%Y")
        return GetDiary(
            participant_guid=self.guid,
            date=date_str,
        ).as_(self._require_client())

    def marks_report(self, with_dates: bool = False) -> GetMarksReport:
        """Return a :class:`~pskovedu.methods.diary.GetMarksReport` for this participant.

        Args:
            with_dates: when ``True``, include date columns in the report.
        """
        from ..methods.diary import GetMarksReport

        return GetMarksReport(
            participant_guid=self.guid,
            with_dates=with_dates,
        ).as_(self._require_client())
