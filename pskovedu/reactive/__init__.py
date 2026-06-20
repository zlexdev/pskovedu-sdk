"""reactive — snapshot-diff engine and event-driven watcher layer.

Public surface (added incrementally by tasks B0–B8):

- :class:`Delta` / :class:`StateDiffer` — diff backbone (B0)
- Event hierarchy, Watcher base, concrete watchers, LessonBell,
  Dispatcher — added by B1–B6.

Import example::

    from pskovedu.reactive import Delta, StateDiffer, MarkWatcher, Dispatcher
"""

from __future__ import annotations

from ._base import Watcher
from .bell import LessonBell
from .diff import Delta, StateDiffer
from .dispatcher import Dispatcher
from .events import (
    Bell,
    LessonEnded,
    LessonStarting,
    MarkChanged,
    NewHomework,
    NewMark,
    NewNotification,
    NewReception,
    ReactiveEvent,
    ScheduleChanged,
)
from .watchers import (
    HomeworkWatcher,
    MarkWatcher,
    NotificationWatcher,
    ReceptionWatcher,
    ScheduleWatcher,
)

__all__ = [
    "Bell",
    "Delta",
    "Dispatcher",
    "HomeworkWatcher",
    "LessonBell",
    "LessonEnded",
    "LessonStarting",
    "MarkChanged",
    "MarkWatcher",
    "NewHomework",
    "NewMark",
    "NewNotification",
    "NewReception",
    "NotificationWatcher",
    "ReactiveEvent",
    "ReceptionWatcher",
    "ScheduleChanged",
    "ScheduleWatcher",
    "StateDiffer",
    "Watcher",
]
