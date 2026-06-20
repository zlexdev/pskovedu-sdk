"""Diary method-classes.

REST endpoints:
- ``GET /edv/index/diary/{participant_guid}`` — fetch weekly diary.
- ``GET /edv/index/diary/{participant_guid}?format=xls`` — XLS export.
- ``GET /edv/index/diary/{participant_guid}/marks-report`` — marks report.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import Field

from ..models.diary import DiaryEntry, DiaryWeek, MarksReport
from ._base import PaginatedMethod
from ._bases import RestMethod


def _today_str() -> str:
    return datetime.date.today().strftime("%d.%m.%Y")


class GetDiary(RestMethod[DiaryWeek]):
    """Fetch the weekly diary for a participant.

    REST: ``GET /edv/index/diary/{participant_guid}?date=DD.MM.YYYY``

    The portal returns the week that contains ``date``.

    Args:
        participant_guid: GUID from ``#participant[data-guid]`` SSR attr.
        date_str: any date within the desired week in ``DD.MM.YYYY`` format.
    """

    __http_method__ = "GET"
    __url__ = "/edv/index/diary/{participant_guid}"
    __path_fields__ = frozenset({"participant_guid"})
    __query_fields__ = frozenset({"date"})

    participant_guid: str
    date: str = Field(default_factory=_today_str)

    @classmethod
    def for_week(cls, participant_guid: str, week_date: datetime.date) -> GetDiary:
        """Construct for a specific week containing ``week_date``.

        Args:
            participant_guid: participant GUID.
            week_date: any date within the desired week.
        """
        return cls(
            participant_guid=participant_guid,
            date=week_date.strftime("%d.%m.%Y"),
        )


class GetMarksReport(RestMethod[MarksReport]):
    """Fetch the marks report (выписка оценок) for a participant.

    REST: ``GET /edv/index/diary/{participant_guid}/marks-report``

    Optional query param ``withDates=1`` includes date columns in the export.

    Args:
        participant_guid: GUID of the participant.
        with_dates: include date columns when ``True``.
    """

    __http_method__ = "GET"
    __url__ = "/edv/index/diary/{participant_guid}/marks-report"
    __path_fields__ = frozenset({"participant_guid"})
    __query_fields__ = frozenset({"withDates"})

    participant_guid: str
    with_dates: bool = Field(False, alias="withDates")


class GetDiaryXls(RestMethod[bytes]):
    """Download the weekly diary as an XLS file.

    REST: ``GET /edv/index/diary/{participant_guid}?date=DD.MM.YYYY&format=xls``

    Returns raw XLS bytes; caller is responsible for saving/parsing.

    Args:
        participant_guid: GUID of the participant.
        date_str: any date within the desired week.
        format: always ``"xls"`` — passed as query parameter.
    """

    __http_method__ = "GET"
    __url__ = "/edv/index/diary/{participant_guid}"
    __path_fields__ = frozenset({"participant_guid"})
    __query_fields__ = frozenset({"date", "format"})

    participant_guid: str
    date: str = Field(default_factory=_today_str)
    format: str = Field(default="xls")


class DiaryPages(PaginatedMethod[DiaryEntry]):
    """Paginated diary: yields entries week by week across ``[start, end]``."""

    participant_guid: str
    start: datetime.date | None = None
    end: datetime.date | None = None

    def _first(self) -> GetDiary:
        if self.start is None:
            return GetDiary(participant_guid=self.participant_guid)
        return GetDiary(
            participant_guid=self.participant_guid,
            date=self.start.strftime("%d.%m.%Y"),
        )

    def _extract(self, page: Any) -> list[DiaryEntry]:
        week: DiaryWeek = page
        return week.entries

    def _advance(self, page: Any) -> GetDiary | None:
        week: DiaryWeek = page
        nxt = week.date_window.end + datetime.timedelta(days=1)
        if self.end is not None and nxt > self.end:
            return None
        if self.end is None and not week.entries:
            return None
        return GetDiary(
            participant_guid=self.participant_guid,
            date=nxt.strftime("%d.%m.%Y"),
        )
