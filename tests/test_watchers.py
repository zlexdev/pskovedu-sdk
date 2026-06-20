"""Tests for reactive Watcher subclasses (task X2).

Coverage:
- MarkWatcher yields NewMark for an unseen mark.
- MarkWatcher yields nothing when the mark list is unchanged on the next poll.
- Drive via fake_client with enqueued get_marks_report responses.
- Bounded iteration (break after N events, no real network, no real sleep).
"""

from __future__ import annotations

import asyncio

from pskovedu.models.diary import SubjectMark
from pskovedu.reactive.events import NewMark
from pskovedu.reactive.watchers import MarkWatcher
from pskovedu.storage.memory import MemoryStorage

from .conftest import json_response

_PARTICIPANT_GUID = "ABCD1234EFAB1234EFAB1234EFAB1234"


def _mark_payload(subject: str = "Математика", mark: str = "5") -> dict:
    """Return a wire-format dict that MarksReport.model_validate can parse."""
    return {
        "participant_guid": _PARTICIPANT_GUID,
        "marks": [
            {
                "subject": subject,
                "mark": mark,
                "weight": "1",
                "period_name": "1 четверть",
                "mark_date": "01.09.2025",
            }
        ],
        "period_name": "1 четверть",
    }


def _empty_marks_payload() -> dict:
    return {
        "participant_guid": _PARTICIPANT_GUID,
        "marks": [],
        "period_name": None,
    }


async def test_mark_watcher_to_events_new_mark() -> None:
    """to_events maps a delta with an added SubjectMark to a NewMark event."""
    from pskovedu.reactive.diff import Delta

    # Build a minimal SubjectMark (strict=False on the model allows this)
    mark = SubjectMark.model_validate(
        {
            "subject": "Физика",
            "mark": "4",
            "weight": "1",
            "period_name": "1 четверть",
            "mark_date": "15.09.2025",
        }
    )

    # We can construct a MarkWatcher without real client for unit-testing to_events.
    import types

    fake_client = types.SimpleNamespace(_storage=MemoryStorage(), _cookies={})
    watcher = MarkWatcher(
        fake_client,  # type: ignore[arg-type]
        _PARTICIPANT_GUID,
        storage=MemoryStorage(),
    )

    delta: Delta[SubjectMark] = Delta(added=[mark], changed=[], removed=[])
    events = list(watcher.to_events(delta))

    assert len(events) == 1
    assert isinstance(events[0], NewMark)
    assert events[0].mark is mark
    assert events[0].participant_guid == _PARTICIPANT_GUID


async def test_mark_watcher_to_events_empty_delta_no_events() -> None:
    """to_events on an empty delta yields nothing."""
    import types

    from pskovedu.reactive.diff import Delta

    fake_client = types.SimpleNamespace(_storage=MemoryStorage(), _cookies={})
    watcher = MarkWatcher(
        fake_client,  # type: ignore[arg-type]
        _PARTICIPANT_GUID,
        storage=MemoryStorage(),
    )
    delta: Delta[SubjectMark] = Delta(added=[], changed=[], removed=[])
    events = list(watcher.to_events(delta))
    assert events == []


async def test_mark_watcher_yields_new_mark_via_fake_client(
    fake_client, enqueue_response
) -> None:
    """MarkWatcher emits NewMark for a mark not seen before.

    Enqueue one marks-report response and consume one event from
    watcher.events() with a short timeout to avoid hanging the test suite.
    """
    enqueue_response(json_response(_mark_payload("Химия", "5")))

    watcher = MarkWatcher(
        fake_client,
        _PARTICIPANT_GUID,
        interval=0.0,  # no real wait between polls
        storage=MemoryStorage(),
    )

    collected: list[NewMark] = []

    async def _drain() -> None:
        async for event in watcher.events():
            collected.append(event)  # type: ignore[arg-type]
            break  # stop after first event

    await asyncio.wait_for(_drain(), timeout=5.0)

    assert len(collected) == 1
    ev = collected[0]
    assert isinstance(ev, NewMark)
    assert ev.mark.subject == "Химия"
    assert ev.mark.mark == "5"
    assert ev.participant_guid == _PARTICIPANT_GUID


async def test_mark_watcher_no_event_for_unchanged_marks(
    fake_client, enqueue_response
) -> None:
    """Second poll with identical marks produces no events.

    We enqueue two identical responses, poll twice through deltas(),
    and assert zero deltas are yielded for the second poll.
    """
    payload = _mark_payload("Биология", "4")
    enqueue_response(json_response(payload))
    enqueue_response(json_response(payload))

    storage = MemoryStorage()
    watcher = MarkWatcher(
        fake_client,
        _PARTICIPANT_GUID,
        interval=0.0,
        storage=storage,
    )

    # Poll 1: seeds snapshot, yields delta with the new mark.
    items1 = await watcher.poll()
    delta1 = await watcher._differ.compute(items1)

    # Poll 2: same marks → empty delta, no events.
    items2 = await watcher.poll()
    delta2 = await watcher._differ.compute(items2)

    assert not delta1.is_empty, "First poll should detect the new mark"
    assert delta2.is_empty, "Second poll with unchanged marks must produce empty delta"


async def test_mark_watcher_detects_added_mark_between_polls(
    fake_client, enqueue_response
) -> None:
    """A mark appearing in the second poll is classified as added."""
    # First poll: one mark
    enqueue_response(json_response(_mark_payload("История", "3")))
    # Second poll: two marks (one new)
    second_payload = {
        "participant_guid": _PARTICIPANT_GUID,
        "marks": [
            {
                "subject": "История",
                "mark": "3",
                "weight": "1",
                "period_name": "1 четверть",
                "mark_date": "01.09.2025",
            },
            {
                "subject": "Химия",
                "mark": "5",
                "weight": "1",
                "period_name": "1 четверть",
                "mark_date": "05.09.2025",
            },
        ],
        "period_name": "1 четверть",
    }
    enqueue_response(json_response(second_payload))

    storage = MemoryStorage()
    watcher = MarkWatcher(
        fake_client,
        _PARTICIPANT_GUID,
        interval=0.0,
        storage=storage,
    )

    items1 = await watcher.poll()
    await watcher._differ.compute(items1)

    items2 = await watcher.poll()
    delta2 = await watcher._differ.compute(items2)

    assert not delta2.is_empty
    added_subjects = [m.subject for m in delta2.added]
    assert "Химия" in added_subjects


async def test_mark_watcher_events_bounded_n(fake_client, enqueue_response) -> None:
    """Collect up to N events from watcher.events() and verify they are NewMark."""
    # Enqueue 3 separate mark payloads with distinct marks
    subjects = ["Физика", "Химия", "Биология"]
    marks_payload = {
        "participant_guid": _PARTICIPANT_GUID,
        "marks": [
            {
                "subject": s,
                "mark": "5",
                "weight": "1",
                "period_name": "1 четверть",
                "mark_date": f"0{i + 1}.09.2025",
            }
            for i, s in enumerate(subjects)
        ],
        "period_name": "1 четверть",
    }
    # First poll: all three marks appear as new
    enqueue_response(json_response(marks_payload))

    watcher = MarkWatcher(
        fake_client,
        _PARTICIPANT_GUID,
        interval=0.0,
        storage=MemoryStorage(),
    )

    collected: list = []
    MAX_EVENTS = 3

    async def _drain() -> None:
        async for event in watcher.events():
            collected.append(event)
            if len(collected) >= MAX_EVENTS:
                break

    await asyncio.wait_for(_drain(), timeout=5.0)

    assert len(collected) == MAX_EVENTS
    assert all(isinstance(e, NewMark) for e in collected)
