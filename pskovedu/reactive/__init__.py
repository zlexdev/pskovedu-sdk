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
from .diff import Delta, StateDiffer
from .dispatcher import Dispatcher
from .watchers import (
    HomeworkWatcher,
    MarkWatcher,
    NotificationWatcher,
    ReceptionWatcher,
    ScheduleWatcher,
)

__all__ = [
    "Delta",
    "Dispatcher",
    "HomeworkWatcher",
    "MarkWatcher",
    "NotificationWatcher",
    "ReceptionWatcher",
    "ScheduleWatcher",
    "StateDiffer",
    "Watcher",
]
