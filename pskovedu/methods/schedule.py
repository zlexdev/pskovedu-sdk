"""Schedule method-classes.

REST endpoints:
- ``GET /schedule/index/schedule/grade/{grade_guid}/{date}`` — get schedule for a grade on a date.
- ``GET /schedule/index/current`` — get schedule for the current user's grade (today).

Both use arbitrary GUIDs from the SSR bootstrap (no auth-scoped GUID required).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import Field

from ..models.schedule import ScheduleDay
from ._base import PaginatedMethod
from ._bases import RestMethod


def _today_str() -> str:
    return date.today().strftime("%d.%m.%Y")


class GetSchedule(RestMethod[ScheduleDay]):
    """Fetch the schedule for a specific grade on a given date.

    REST: ``GET /schedule/index/schedule/grade/{grade_guid}/{date}?single=1``

    The ``date`` path parameter uses ``DD.MM.YYYY`` format.
    ``single=1`` is always sent to receive a single-day view.

    Args:
        grade_guid: GUID of the grade (class), e.g. from ``window.schedule_subject_guid``.
        schedule_date: date to fetch (defaults to today).
    """

    __http_method__ = "GET"
    __url__ = "/schedule/index/schedule/grade/{grade_guid}/{date_str}"
    __path_fields__ = frozenset({"grade_guid", "date_str"})
    __query_fields__ = frozenset({"single"})

    grade_guid: str
    date_str: str = Field(default_factory=_today_str)
    single: str = Field(default="1")

    @classmethod
    def for_date(cls, grade_guid: str, schedule_date: date) -> GetSchedule:
        """Construct a :class:`GetSchedule` for a specific :class:`~datetime.date`.

        Args:
            grade_guid: grade GUID string.
            schedule_date: the date to fetch.
        """
        return cls(
            grade_guid=grade_guid,
            date_str=schedule_date.strftime("%d.%m.%Y"),
        )


class GetCurrentSchedule(RestMethod[ScheduleDay]):
    """Fetch today's schedule for the current user's grade.

    REST: ``GET /schedule/index/current``

    Does not require a GUID — the portal derives the grade from the active
    session cookie.  Returns the same ``ScheduleDay`` shape as
    :class:`GetSchedule`.
    """

    __http_method__ = "GET"
    __url__ = "/schedule/index/current"


class SchedulePages(PaginatedMethod[ScheduleDay]):
    """Paginated schedule: yields one ``ScheduleDay`` per day across ``[start, end]``."""

    grade_guid: str
    start: date
    end: date

    def _first(self) -> GetSchedule:
        return GetSchedule(
            grade_guid=self.grade_guid,
            date_str=self.start.strftime("%d.%m.%Y"),
        )

    def _extract(self, page: Any) -> list[ScheduleDay]:
        day: ScheduleDay = page
        return [day]

    def _advance(self, page: Any) -> GetSchedule | None:
        day: ScheduleDay = page
        cur = datetime.strptime(day.date_str, "%d.%m.%Y").date()
        nxt = cur + timedelta(days=1)
        if nxt > self.end:
            return None
        return GetSchedule(
            grade_guid=self.grade_guid,
            date_str=nxt.strftime("%d.%m.%Y"),
        )
