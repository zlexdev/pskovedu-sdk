"""pskovedu — Python SDK for the pskovedu.ru educational portal.

Minimal re-exports for the primary public surface.  Import everything else
from the relevant sub-module.

Quick start::

    from pskovedu import Client, ClientConfig, EduError

    client = Client.from_cookie(x1_sso="<your-X1_SSO-cookie>")
    session = await client.get_session()
    print(session.session_id, session.expired)
"""

from .cache.reference import ReferenceCache
from .client import Client
from .config import ClientConfig
from .exceptions import EduError, ErrorCode
from .models.enums import ReportFmt
from .polling import watch_notifications
from .reactive._base import Watcher
from .reactive.bell import LessonBell
from .reactive.diff import Delta, StateDiffer
from .reactive.dispatcher import Dispatcher
from .reactive.events import (
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
from .sync import SyncClient

__all__ = [
    "Bell",
    "Client",
    "ClientConfig",
    "Delta",
    "Dispatcher",
    "EduError",
    "ErrorCode",
    "LessonBell",
    "LessonEnded",
    "LessonStarting",
    "MarkChanged",
    "NewHomework",
    "NewMark",
    "NewNotification",
    "NewReception",
    "ReactiveEvent",
    "ReferenceCache",
    "ReportFmt",
    "ScheduleChanged",
    "StateDiffer",
    "SyncClient",
    "Watcher",
    "watch_notifications",
]
