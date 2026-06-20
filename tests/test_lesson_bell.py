"""Tests for LessonBell — local bell scheduler (task X2).

Coverage:
- planned() returns events in correct order: LessonStarting -> Bell(begin) ->
  Bell(end) -> LessonEnded for a single lesson slot.
- planned() sorts multiple slots chronologically.
- Injected fixed `now` and injected fake `sleep` — zero network, zero real waiting.
- No Client / no network calls made in any test.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pskovedu.models.schedule import LessonTime, ScheduleDay, SchoolShift
from pskovedu.reactive.bell import LessonBell
from pskovedu.reactive.events import Bell, LessonEnded, LessonStarting, ReactiveEvent

_DATE_STR = "20.06.2026"  # "DD.MM.YYYY" — a Saturday, irrelevant for bell logic


def _make_slot(
    sys_guid: str,
    number: int,
    time_begin: str,
    time_end: str,
) -> LessonTime:
    """Construct a LessonTime using wire-format aliases (populate_by_name=True)."""
    return LessonTime.model_validate(
        {
            "SYS_GUID": sys_guid,
            "NUMBER": number,
            "TIME_BEGIN": time_begin,
            "TIME_END": time_end,
            "LESSONS": [],
        }
    )


def _make_shift(slots: list[LessonTime], sys_guid: str = "SHIFT001") -> SchoolShift:
    return SchoolShift.model_validate(
        {
            "SYS_GUID": sys_guid,
            "NAME": "1-я смена",
            "LESSON_TIMES": [s.model_dump(by_alias=True) for s in slots],
        }
    )


def _make_schedule(slots: list[LessonTime]) -> ScheduleDay:
    """Build a ScheduleDay with one shift containing the given slots."""
    shift = _make_shift(slots)
    return ScheduleDay.model_validate(
        {
            "grade_guid": "ABCD1234EFAB1234EFAB1234EFAB1234",
            "date_str": _DATE_STR,
            "shifts": [shift.model_dump(by_alias=True)],
        }
    )


class _FakeSleep:
    """Records sleep durations; returns immediately (no real waiting)."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _fixed_now(hour: int, minute: int) -> datetime:
    """Return a naive local datetime on _DATE_STR at HH:MM."""
    # date_str = "DD.MM.YYYY" → "20.06.2026"
    return datetime(2026, 6, 20, hour, minute, 0)


def test_planned_single_slot_event_order() -> None:
    """planned() returns 4 events per slot in the canonical order.

    LessonStarting -> Bell(begin) -> Bell(end) -> LessonEnded
    """
    slot = _make_slot("SLOT001", 1, "08:00", "08:45")
    schedule = _make_schedule([slot])

    def now_fn() -> datetime:
        return _fixed_now(7, 0)  # well before lesson start

    bell = LessonBell(schedule, now=now_fn, sleep=_FakeSleep())

    plan = bell.planned()
    assert len(plan) == 4

    whens = [when for when, _ in plan]
    events = [ev for _, ev in plan]

    # Timestamps must be non-decreasing.
    assert whens == sorted(whens), "Events must be sorted by time"

    assert isinstance(events[0], LessonStarting), f"Expected LessonStarting, got {type(events[0])}"
    assert isinstance(events[1], Bell), f"Expected Bell(begin), got {type(events[1])}"
    assert isinstance(events[2], Bell), f"Expected Bell(end), got {type(events[2])}"
    assert isinstance(events[3], LessonEnded), f"Expected LessonEnded, got {type(events[3])}"

    assert events[1].phase == "begin"
    assert events[2].phase == "end"


def test_planned_lesson_starting_fires_lead_before_begin() -> None:
    """LessonStarting fires exactly `lead` minutes before lesson begin."""
    lead = timedelta(minutes=5)
    slot = _make_slot("SLOT002", 1, "09:00", "09:45")
    schedule = _make_schedule([slot])

    bell = LessonBell(schedule, lead=lead, now=lambda: _fixed_now(8, 0), sleep=_FakeSleep())
    plan = bell.planned()

    # First event is LessonStarting at 08:55
    starting_when, starting_ev = plan[0]
    assert isinstance(starting_ev, LessonStarting)
    assert starting_when == datetime(2026, 6, 20, 8, 55, 0)
    assert starting_ev.lead == lead


def test_planned_bell_begin_fires_at_lesson_start() -> None:
    """Bell(begin) fires at the exact lesson start time."""
    slot = _make_slot("SLOT003", 1, "10:00", "10:45")
    schedule = _make_schedule([slot])

    bell = LessonBell(schedule, now=lambda: _fixed_now(9, 0), sleep=_FakeSleep())
    plan = bell.planned()

    _, begin_bell = plan[1]
    begin_when, _ = plan[1]
    assert isinstance(begin_bell, Bell)
    assert begin_bell.phase == "begin"
    assert begin_when == datetime(2026, 6, 20, 10, 0, 0)


def test_planned_bell_end_and_lesson_ended_coincide() -> None:
    """Bell(end) and LessonEnded share the same timestamp."""
    slot = _make_slot("SLOT004", 1, "11:00", "11:45")
    schedule = _make_schedule([slot])

    bell = LessonBell(schedule, now=lambda: _fixed_now(10, 0), sleep=_FakeSleep())
    plan = bell.planned()

    end_when, end_bell = plan[2]
    ended_when, lesson_ended = plan[3]
    assert isinstance(end_bell, Bell) and end_bell.phase == "end"
    assert isinstance(lesson_ended, LessonEnded)
    assert end_when == ended_when == datetime(2026, 6, 20, 11, 45, 0)


def test_planned_two_slots_ordered() -> None:
    """Two lesson slots produce 8 events sorted by time."""
    slot1 = _make_slot("SLOT-A", 1, "08:00", "08:45")
    slot2 = _make_slot("SLOT-B", 2, "09:00", "09:45")
    schedule = _make_schedule([slot1, slot2])

    bell = LessonBell(schedule, now=lambda: _fixed_now(7, 0), sleep=_FakeSleep())
    plan = bell.planned()

    assert len(plan) == 8
    whens = [w for w, _ in plan]
    assert whens == sorted(whens), "Multi-slot events must be globally sorted"

    # Slot 1 LessonStarting must come before Slot 2 LessonStarting
    starting_events = [(w, e) for w, e in plan if isinstance(e, LessonStarting)]
    assert len(starting_events) == 2
    assert starting_events[0][0] < starting_events[1][0]


def test_planned_empty_schedule_returns_empty_list() -> None:
    """ScheduleDay with no lesson_times → planned() returns []."""
    schedule = ScheduleDay.model_validate(
        {
            "grade_guid": "ABCD1234EFAB1234EFAB1234EFAB1234",
            "date_str": _DATE_STR,
            "shifts": [],
        }
    )
    bell = LessonBell(schedule, now=lambda: _fixed_now(8, 0), sleep=_FakeSleep())
    assert bell.planned() == []


async def test_events_calls_fake_sleep_not_real() -> None:
    """events() drives planned() with injected sleep; no real delay occurs."""
    slot = _make_slot("SLOT-S", 1, "08:00", "08:45")
    schedule = _make_schedule([slot])

    fake_sleep = _FakeSleep()
    # Set now to well after lesson end so all events fire immediately (delay=0)
    bell = LessonBell(
        schedule,
        now=lambda: _fixed_now(12, 0),
        sleep=fake_sleep,
    )

    collected: list[ReactiveEvent] = []
    async for event in bell.events():
        collected.append(event)

    # All 4 events collected with zero-delay sleeps
    assert len(collected) == 4
    assert all(d == 0.0 for d in fake_sleep.calls), (
        f"Expected all zero delays for past events, got: {fake_sleep.calls}"
    )


async def test_events_sleep_called_for_future_events() -> None:
    """events() calls sleep with positive delay for events in the future."""
    # Set now to just before lead time so LessonStarting is in the future
    slot = _make_slot("SLOT-F", 1, "09:00", "09:45")
    schedule = _make_schedule([slot])

    fake_sleep = _FakeSleep()
    # now = 08:50, lead = 5 min → LessonStarting at 08:55 → delay = 5 min = 300s
    bell = LessonBell(
        schedule,
        lead=timedelta(minutes=5),
        now=lambda: _fixed_now(8, 50),
        sleep=fake_sleep,
    )

    plan = bell.planned()
    # Verify the first delay is positive (5 min = 300s)
    first_when, _ = plan[0]
    expected_delay = (first_when - _fixed_now(8, 50)).total_seconds()
    assert expected_delay > 0, "LessonStarting should be in the future"

    # Drive one event through events()
    count = 0
    async for _ in bell.events():
        count += 1
        break  # only consume first event

    assert fake_sleep.calls[0] == pytest.approx(expected_delay, abs=1.0)


def test_no_client_needed_for_lesson_bell() -> None:
    """LessonBell is constructed and planned() runs without any Client."""
    slot = _make_slot("SLOT-NC", 1, "10:00", "10:45")
    schedule = _make_schedule([slot])
    bell = LessonBell(schedule, now=lambda: _fixed_now(9, 0), sleep=_FakeSleep())
    plan = bell.planned()
    # If we got here without importing or instantiating Client, the test passes.
    assert len(plan) == 4
