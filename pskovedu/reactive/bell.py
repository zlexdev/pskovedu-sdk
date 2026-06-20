"""Local lesson-bell scheduler — zero network, zero client imports.

:class:`LessonBell` takes a :class:`~pskovedu.models.schedule.ScheduleDay`
(already fetched by the caller) and turns its nested shift/lesson-time structure
into a stream of :class:`~pskovedu.reactive.events.ReactiveEvent` objects that
fire at the right wall-clock moments.

Clock / timezone contract (R6)
-------------------------------
Portal lesson times are stored as **local-naive** ``"HH:MM"`` strings — there is
no timezone information in the wire format.  The ``now`` callable **must** return
a datetime in the same reference frame as those strings:

* **Recommended (local-naive):** ``datetime.now`` (the default) — wall-clock
  local time with no tzinfo, matching the portal directly.
* **Allowed (tz-aware):** pass a callable returning a tz-aware datetime in the
  school's local timezone (e.g. ``lambda: datetime.now(ZoneInfo("Europe/Moscow"))``).
  The parsed lesson datetimes will be made tz-aware in the same zone so that
  arithmetic is consistent.

Never mix naive and aware: if ``now()`` returns an aware datetime, the parsed
``date_str + HH:MM`` datetimes produced by :meth:`LessonBell.planned` are also
made aware (using the same tzinfo); if ``now()`` returns naive, they stay naive.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from pskovedu.models.schedule import LessonTime, ScheduleDay
from pskovedu.reactive.events import Bell, LessonEnded, LessonStarting, ReactiveEvent


def _local_now() -> datetime:
    """Return the current local wall-clock time (naive, no tzinfo)."""
    return datetime.now()  # noqa: DTZ005 — intentionally local-naive to match portal


def _parse_date_str(date_str: str) -> tuple[int, int, int]:
    """Parse ``"DD.MM.YYYY"`` into ``(year, month, day)``."""
    day_s, month_s, year_s = date_str.split(".")
    return int(year_s), int(month_s), int(day_s)


def _build_dt(year: int, month: int, day: int, hhmm: str, tzinfo: Any) -> datetime:
    """Combine a calendar date with an ``"HH:MM"`` string into a datetime.

    If ``tzinfo`` is not ``None`` the result is tz-aware in that zone,
    otherwise it is local-naive.
    """
    h, m = hhmm.split(":")
    naive = datetime(year, month, day, int(h), int(m))
    if tzinfo is not None:
        return naive.replace(tzinfo=tzinfo)
    return naive


class LessonBell:
    """Local bell scheduler built from a single :class:`ScheduleDay`.

    Converts the nested ``shifts → lesson_times`` structure into a flat,
    chronologically sorted sequence of :class:`~pskovedu.reactive.events.ReactiveEvent`
    instances and either returns them synchronously (via :meth:`planned`) or
    yields them in real time (via :meth:`events`).

    Per lesson slot the following events are emitted in order:

    1. :class:`~pskovedu.reactive.events.LessonStarting` at ``begin - lead``
    2. :class:`~pskovedu.reactive.events.Bell` (``phase="begin"``) at ``begin``
    3. :class:`~pskovedu.reactive.events.Bell` (``phase="end"``) at ``end``
    4. :class:`~pskovedu.reactive.events.LessonEnded` at ``end`` (same moment as #3)

    Args:
        schedule: A :class:`~pskovedu.models.schedule.ScheduleDay` instance
            (caller is responsible for fetching it).
        lead: How far before lesson start to emit the
            :class:`~pskovedu.reactive.events.LessonStarting` warning event.
            Defaults to 5 minutes.
        now: Zero-argument callable returning the current datetime.
            **Must match the portal wall clock** — see module docstring (R6).
            Defaults to ``datetime.now`` (local-naive).
        sleep: Async callable accepting seconds as a float; used by
            :meth:`events` to wait between firings.  Injectable for testing
            (pass an async no-op to fast-forward without real delays).
    """

    def __init__(
        self,
        schedule: ScheduleDay,
        *,
        lead: timedelta = timedelta(minutes=5),
        now: Callable[[], datetime] = _local_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._schedule = schedule
        self._lead = lead
        self._now = now
        self._sleep = sleep


    def _all_lesson_times(self) -> list[LessonTime]:
        """Flatten all shifts' lesson_times into a single list (input order)."""
        result: list[LessonTime] = []
        for shift in self._schedule.shifts:
            result.extend(shift.lesson_times)
        return result

    def _tzinfo(self) -> Any:
        """Return the tzinfo from ``now()`` (or ``None`` for naive clocks)."""
        return self._now().tzinfo

    def _slot_datetimes(
        self,
        slot: LessonTime,
        year: int,
        month: int,
        day: int,
        tzinfo: Any,
    ) -> tuple[datetime, datetime]:
        """Return ``(begin_dt, end_dt)`` for *slot* on the schedule date."""
        begin = _build_dt(year, month, day, slot.time_begin, tzinfo)
        end = _build_dt(year, month, day, slot.time_end, tzinfo)
        return begin, end


    def planned(self) -> list[tuple[datetime, ReactiveEvent]]:
        """Return the full event schedule as a sorted list — **pure, no I/O**.

        Flattens all shifts' ``lesson_times``, parses ``"HH:MM"`` strings
        against :attr:`~pskovedu.models.schedule.ScheduleDay.date_str`, and
        expands each slot into up to four events:

        * ``LessonStarting`` at ``begin - lead``
        * ``Bell(phase="begin")`` at ``begin``
        * ``Bell(phase="end")`` at ``end``
        * ``LessonEnded`` at ``end``

        The returned list is sorted by ``when`` ascending.  Events that share
        the same ``when`` (``Bell("end")`` and ``LessonEnded``) preserve the
        order listed above via Python's stable sort.

        Returns:
            A list of ``(when: datetime, event: ReactiveEvent)`` tuples,
            sorted chronologically.  Empty when the schedule has no lesson
            time slots.
        """
        year, month, day = _parse_date_str(self._schedule.date_str)
        tzinfo = self._tzinfo()
        entries: list[tuple[datetime, int, ReactiveEvent]] = []

        for slot in self._all_lesson_times():
            begin, end = self._slot_datetimes(slot, year, month, day, tzinfo)
            warn_at = begin - self._lead

            # Stable ordering within the same timestamp: use a priority index.
            # LessonStarting=0, Bell(begin)=1, Bell(end)=2, LessonEnded=3
            entries.append((
                warn_at,
                0,
                LessonStarting(at=warn_at, lesson=slot, lead=self._lead),
            ))
            entries.append((
                begin,
                1,
                Bell(at=begin, lesson=slot, phase="begin"),
            ))
            entries.append((
                end,
                2,
                Bell(at=end, lesson=slot, phase="end"),
            ))
            entries.append((
                end,
                3,
                LessonEnded(at=end, lesson=slot),
            ))

        entries.sort(key=lambda t: (t[0], t[1]))
        return [(when, ev) for when, _pri, ev in entries]

    async def events(self) -> AsyncIterator[ReactiveEvent]:
        """Drive :meth:`planned` in real time, yielding events as they become due.

        For each ``(when, event)`` pair returned by :meth:`planned`:

        1. Compute ``delay = max(0, (when - now()).total_seconds())``.
        2. Await ``sleep(delay)`` (injectable — tests can pass a no-op coroutine).
        3. Yield the event.

        Past events (``when < now()`` at iteration start) are yielded
        immediately with ``delay=0``; they are **not** skipped.

        Yields:
            :class:`~pskovedu.reactive.events.ReactiveEvent` instances in
            chronological order.
        """
        for when, event in self.planned():
            delay = max(0.0, (when - self._now()).total_seconds())
            await self._sleep(delay)
            yield event


    def current_lesson(self) -> LessonTime | None:
        """Return the :class:`~pskovedu.models.schedule.LessonTime` slot
        currently in progress according to ``now()``, or ``None``.

        A slot is considered *in progress* when ``begin <= now() <= end``.
        If multiple shifts overlap (unusual), the first match wins.
        """
        current = self._now()
        year, month, day = _parse_date_str(self._schedule.date_str)
        tzinfo = self._tzinfo()
        for slot in self._all_lesson_times():
            begin, end = self._slot_datetimes(slot, year, month, day, tzinfo)
            if begin <= current <= end:
                return slot
        return None

    def next_lesson(self) -> LessonTime | None:
        """Return the next :class:`~pskovedu.models.schedule.LessonTime` slot
        that has not yet begun according to ``now()``, or ``None`` when no
        future lesson exists on this schedule day.

        Slots are evaluated in begin-time order across all shifts.
        """
        current = self._now()
        year, month, day = _parse_date_str(self._schedule.date_str)
        tzinfo = self._tzinfo()

        upcoming: list[tuple[datetime, LessonTime]] = []
        for slot in self._all_lesson_times():
            begin, _end = self._slot_datetimes(slot, year, month, day, tzinfo)
            if begin > current:
                upcoming.append((begin, slot))

        if not upcoming:
            return None
        upcoming.sort(key=lambda t: t[0])
        return upcoming[0][1]

    def time_to_bell(self) -> timedelta | None:
        """Return the time remaining until the next bell event, or ``None``.

        The "next bell" is the earliest future moment in :meth:`planned` that
        is strictly after ``now()``.  Both ``Bell(begin)`` and ``Bell(end)``
        fire points count; the ``LessonStarting`` warning and ``LessonEnded``
        duplicate are excluded (only ``Bell`` instances are considered).

        Returns:
            A positive :class:`~datetime.timedelta`, or ``None`` when no future
            ``Bell`` events remain on this schedule day.
        """
        current = self._now()
        for when, event in self.planned():
            if isinstance(event, Bell) and when > current:
                return when - current
        return None
