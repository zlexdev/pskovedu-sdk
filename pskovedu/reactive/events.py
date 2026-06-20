"""Reactive event hierarchy for the pskovedu SDK.

All events are immutable value objects (frozen dataclasses with __slots__).
The ``at`` timestamp on the base class records when the event was detected,
not when the underlying change happened on the portal.

DTO-typed fields (``mark``, ``lesson``, ``slot``, etc.) are declared ``Any``
here to avoid a circular import with the models package.  The concrete watcher
that constructs each event always passes the actual SDK model, so callers can
safely cast/annotate at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Literal


class ScheduleChangeKind(StrEnum):
    """Detected kind of change in a polled schedule diff."""

    CANCELLED = "cancelled"
    """Lesson was cancelled."""

    MOVED = "moved"
    """Lesson was moved to a different time."""

    TEACHER = "teacher"
    """Assigned teacher changed."""

    ROOM = "room"
    """Classroom changed."""

    ADDED = "added"
    """New lesson appeared that was not previously in the schedule."""


@dataclass(frozen=True, slots=True)
class ReactiveEvent:
    """Immutable base for all SDK reactive events.

    Attributes:
        at: UTC datetime when the SDK detected this event (wall-clock of the
            poll cycle that produced it).
    """

    at: datetime


@dataclass(frozen=True, slots=True)
class NewMark(ReactiveEvent):
    """A previously unseen grade/mark was found for ``participant_guid``.

    Attributes:
        mark: The raw SDK mark DTO.  # loose: real model bound by watcher
        participant_guid: GUID of the participant this mark belongs to.
    """

    mark: Any  # loose: real model bound by watcher
    participant_guid: str


@dataclass(frozen=True, slots=True)
class MarkChanged(ReactiveEvent):
    """An existing mark changed its value or metadata.

    Attributes:
        before: Previous mark DTO snapshot.  # loose: real model bound by watcher
        after: Current mark DTO snapshot.    # loose: real model bound by watcher
    """

    before: Any  # loose: real model bound by watcher
    after: Any  # loose: real model bound by watcher


@dataclass(frozen=True, slots=True)
class NewHomework(ReactiveEvent):
    """A new homework entry appeared in the diary.

    Attributes:
        entry: The raw SDK homework/diary entry DTO.  # loose: real model bound by watcher
    """

    entry: Any  # loose: real model bound by watcher


@dataclass(frozen=True, slots=True)
class ScheduleChanged(ReactiveEvent):
    """A lesson in the polled schedule changed in some detectable way.

    Attributes:
        kind: Nature of the detected change.
        lesson: The affected lesson DTO (post-change state where applicable).
                # loose: real model bound by watcher
    """

    kind: ScheduleChangeKind
    lesson: Any  # loose: real model bound by watcher


@dataclass(frozen=True, slots=True)
class NewReception(ReactiveEvent):
    """A new reception slot became available.

    Attributes:
        slot: The raw SDK reception slot DTO.  # loose: real model bound by watcher
    """

    slot: Any  # loose: real model bound by watcher


@dataclass(frozen=True, slots=True)
class NewNotification(ReactiveEvent):
    """A new portal notification/announcement was detected.

    Attributes:
        notification: The raw SDK notification DTO.  # loose: real model bound by watcher
    """

    notification: Any  # loose: real model bound by watcher


@dataclass(frozen=True, slots=True)
class LessonStarting(ReactiveEvent):
    """Fired ``lead`` time before a lesson begins.

    Attributes:
        lesson: The upcoming lesson DTO.  # loose: real model bound by watcher
        lead: How far ahead of the lesson start this event is emitted.
    """

    lesson: Any  # loose: real model bound by watcher
    lead: timedelta


@dataclass(frozen=True, slots=True)
class Bell(ReactiveEvent):
    """Fires at the exact start or end of a lesson.

    Attributes:
        lesson: The lesson DTO.  # loose: real model bound by watcher
        phase: ``"begin"`` at lesson start, ``"end"`` at lesson end.
    """

    lesson: Any  # loose: real model bound by watcher
    phase: Literal["begin", "end"]


@dataclass(frozen=True, slots=True)
class LessonEnded(ReactiveEvent):
    """Fires when a lesson has concluded (coincides with the end Bell).

    Kept as a separate event type so callers can subscribe exclusively to
    lesson-end semantics without filtering on ``Bell.phase``.

    Attributes:
        lesson: The finished lesson DTO.  # loose: real model bound by watcher
    """

    lesson: Any  # loose: real model bound by watcher
