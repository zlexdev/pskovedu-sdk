"""Concrete Watcher subclasses for the pskovedu reactive layer.

Each watcher polls a single client endpoint, identifies items by a stable key,
and maps :class:`~pskovedu.reactive.diff.Delta` entries to typed
:class:`~pskovedu.reactive.events.ReactiveEvent` instances.

Watcher     | client method             | item type       | key
------------|---------------------------|-----------------|-----------------------------
MarkWatcher | get_marks_report          | SubjectMark     | subject:period:date:mark
HomeworkWatcher | get_diary             | DiaryEntry      | entry_date:subject
ScheduleWatcher | get_schedule          | Lesson          | sys_guid
ReceptionWatcher | get_reception        | ReceptionSlot   | guid
NotificationWatcher | get_user_notifications | UserNotification | guid
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..models.diary import DiaryEntry, SubjectMark
from ..models.enums import ReceptionAudience
from ..models.notifications import UserNotification
from ..models.reception import ReceptionSlot
from ..models.schedule import Lesson
from ._base import Watcher
from .diff import Delta
from .events import (
    MarkChanged,
    NewHomework,
    NewMark,
    NewNotification,
    NewReception,
    ReactiveEvent,
    ScheduleChanged,
    ScheduleChangeKind,
)

if TYPE_CHECKING:
    from ..client import Client


def _now() -> datetime:
    return datetime.now(UTC)


class MarkWatcher(Watcher[SubjectMark]):
    """Poll the marks report for *participant_guid* and emit mark events.

    Args:
        client: authenticated :class:`~pskovedu.client.Client`.
        participant_guid: GUID of the diary participant.
        **kw: forwarded to :class:`~pskovedu.reactive._base.Watcher`.

    Events emitted:
        :class:`~pskovedu.reactive.events.NewMark` — mark appeared for the
        first time.
        :class:`~pskovedu.reactive.events.MarkChanged` — existing mark changed
        (e.g. grade corrected).
    """

    def __init__(
        self,
        client: Client,
        participant_guid: str,
        **kw: Any,
    ) -> None:
        super().__init__(client, **kw)
        self._participant_guid = participant_guid
        # Cache items by key so we can reconstruct the "before" snapshot for
        # MarkChanged events (StateDiffer only returns the new state).
        self._cache: dict[str, SubjectMark] = {}

    async def poll(self) -> list[SubjectMark]:
        report = await self._client.get_marks_report(self._participant_guid)
        items = report.marks
        # Refresh the local cache so to_events can read old values.
        new_cache: dict[str, SubjectMark] = {self.key_fn(m): m for m in items}
        self._cache = new_cache
        return items

    def key_fn(self, item: SubjectMark) -> str:
        # SubjectMark has no guid; use a composite of all stable identity fields.
        period = item.period_name or ""
        date = item.mark_date or ""
        return f"{item.subject}:{period}:{date}:{item.mark}"

    def to_events(self, delta: Delta[SubjectMark]) -> Iterable[ReactiveEvent]:
        at = _now()
        for mark in delta.added:
            yield NewMark(at=at, mark=mark, participant_guid=self._participant_guid)
        for mark in delta.changed:
            before = self._cache.get(self.key_fn(mark))
            if before is not None:
                yield MarkChanged(at=at, before=before, after=mark)
            else:
                # No cached predecessor — treat as new.
                yield NewMark(at=at, mark=mark, participant_guid=self._participant_guid)
        # Removed marks are not signalled (they silently disappear from the report).


class HomeworkWatcher(Watcher[DiaryEntry]):
    """Poll the diary for *participant_guid* and emit new-homework events.

    Args:
        client: authenticated :class:`~pskovedu.client.Client`.
        participant_guid: GUID of the diary participant.
        **kw: forwarded to :class:`~pskovedu.reactive._base.Watcher`.

    Events emitted:
        :class:`~pskovedu.reactive.events.NewHomework` — a diary entry with
        homework text appeared that was not seen before.
    """

    def __init__(
        self,
        client: Client,
        participant_guid: str,
        **kw: Any,
    ) -> None:
        super().__init__(client, **kw)
        self._participant_guid = participant_guid

    async def poll(self) -> list[DiaryEntry]:
        diary_week = await self._client.get_diary(self._participant_guid)
        # Emit only entries that actually have homework text.
        return [e for e in diary_week.entries if e.homework]

    def key_fn(self, item: DiaryEntry) -> str:
        # DiaryEntry has no guid; date + subject is the natural unique key.
        date = item.entry_date or ""
        subject = item.subject or ""
        return f"{date}:{subject}"

    def to_events(self, delta: Delta[DiaryEntry]) -> Iterable[ReactiveEvent]:
        at = _now()
        for entry in delta.added:
            yield NewHomework(at=at, entry=entry)
        # Changed homework (text edited) also counts as something new to surface.
        for entry in delta.changed:
            yield NewHomework(at=at, entry=entry)


class ScheduleWatcher(Watcher[Lesson]):
    """Poll the schedule for *grade_guid* and emit change events per lesson.

    Lessons are diffed by their ``sys_guid``; the ``to_events`` method
    classifies each change as :attr:`~.ScheduleChangeKind.CANCELLED`,
    :attr:`~.ScheduleChangeKind.MOVED`, :attr:`~.ScheduleChangeKind.TEACHER`,
    :attr:`~.ScheduleChangeKind.ROOM`, or :attr:`~.ScheduleChangeKind.ADDED`.

    Args:
        client: authenticated :class:`~pskovedu.client.Client`.
        grade_guid: GUID of the grade whose schedule to watch.
        **kw: forwarded to :class:`~pskovedu.reactive._base.Watcher`.

    Events emitted:
        :class:`~pskovedu.reactive.events.ScheduleChanged`
    """

    def __init__(
        self,
        client: Client,
        grade_guid: str,
        **kw: Any,
    ) -> None:
        super().__init__(client, **kw)
        self._grade_guid = grade_guid
        # Map sys_guid -> Lesson so we can reconstruct the before-state.
        self._cache: dict[str, Lesson] = {}

    async def poll(self) -> list[Lesson]:
        schedule_day = await self._client.get_schedule(self._grade_guid)
        lessons: list[Lesson] = []
        for shift in schedule_day.shifts:
            for slot in shift.lesson_times:
                lessons.extend(slot.lessons)
        # Update cache BEFORE returning so to_events sees the previous values.
        # We keep the old cache until after the diff has been produced; the
        # _base.Watcher calls poll() → StateDiffer.compute() → to_events(),
        # so we need the OLD cache in to_events and can refresh here.
        # Strategy: build new_cache but don't replace self._cache here;
        # instead refresh it at the end of to_events.  But to_events is a
        # generator — we solve this by building a new_cache first and updating
        # self._cache at the END of to_events.
        #
        # Simpler: keep a "pending" cache that poll sets, and to_events commits.
        self._pending_cache: dict[str, Lesson] = {self.key_fn(lesson): lesson for lesson in lessons}
        return lessons

    def key_fn(self, item: Lesson) -> str:
        return item.sys_guid

    def _classify(self, before: Lesson, after: Lesson) -> ScheduleChangeKind:
        """Best-effort classification of what changed between two lesson snapshots."""
        if after.subject is None and before.subject is not None:
            return ScheduleChangeKind.CANCELLED
        if after.teacher != before.teacher and before.teacher is not None:
            return ScheduleChangeKind.TEACHER
        if after.classroom != before.classroom and before.classroom is not None:
            return ScheduleChangeKind.ROOM
        # Fallback: something structural changed — treat as MOVED.
        return ScheduleChangeKind.MOVED

    def to_events(self, delta: Delta[Lesson]) -> Iterable[ReactiveEvent]:
        at = _now()
        for lesson in delta.added:
            yield ScheduleChanged(at=at, kind=ScheduleChangeKind.ADDED, lesson=lesson)
        for lesson in delta.changed:
            before = self._cache.get(self.key_fn(lesson))
            if before is not None:
                kind = self._classify(before, lesson)
            else:
                kind = ScheduleChangeKind.MOVED
            yield ScheduleChanged(at=at, kind=kind, lesson=lesson)
        # Commit the pending cache after we've used the old one.
        if hasattr(self, "_pending_cache"):
            self._cache = self._pending_cache

    # Note: removed lessons are not explicitly emitted here; a lesson that
    # disappears will simply stop appearing.  Callers can filter
    # ScheduleChangeKind.CANCELLED for "gone" semantics.


class ReceptionWatcher(Watcher[ReceptionSlot]):
    """Poll reception slots and emit :class:`~.NewReception` for new ones.

    Args:
        client: authenticated :class:`~pskovedu.client.Client`.
        start: date range start (``"DD.MM.YYYY"`` format).
        end: date range end (``"DD.MM.YYYY"`` format).
        audience: optional audience filter (:class:`~pskovedu.models.enums.ReceptionAudience`).
        **kw: forwarded to :class:`~pskovedu.reactive._base.Watcher`.

    Events emitted:
        :class:`~pskovedu.reactive.events.NewReception`
    """

    def __init__(
        self,
        client: Client,
        start: str,
        end: str,
        audience: ReceptionAudience | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(client, **kw)
        self._start = start
        self._end = end
        self._audience = audience

    async def poll(self) -> list[ReceptionSlot]:
        page = await self._client.get_reception(
            self._start,
            self._end,
            audience=self._audience,
        )
        return page.items

    def key_fn(self, item: ReceptionSlot) -> str:
        return item.guid

    def to_events(self, delta: Delta[ReceptionSlot]) -> Iterable[ReactiveEvent]:
        at = _now()
        for slot in delta.added:
            yield NewReception(at=at, slot=slot)
        # Changed slots (status/booked_by changed) are not re-emitted to avoid
        # noise from booking state transitions the caller did not initiate.


class NotificationWatcher(Watcher[UserNotification]):
    """Poll user notifications and emit :class:`~.NewNotification` for new ones.

    Args:
        client: authenticated :class:`~pskovedu.client.Client`.
        **kw: forwarded to :class:`~pskovedu.reactive._base.Watcher`.

    Events emitted:
        :class:`~pskovedu.reactive.events.NewNotification`
    """

    def __init__(
        self,
        client: Client,
        **kw: Any,
    ) -> None:
        super().__init__(client, **kw)

    async def poll(self) -> list[UserNotification]:
        page = await self._client.get_user_notifications()
        return page.items

    def key_fn(self, item: UserNotification) -> str:
        return item.guid

    def to_events(self, delta: Delta[UserNotification]) -> Iterable[ReactiveEvent]:
        at = _now()
        for notification in delta.added:
            yield NewNotification(at=at, notification=notification)
        # Changed notifications (e.g. title/message edited) are not re-emitted.
