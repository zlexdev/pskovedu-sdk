"""Notification method-classes.

User notifications are fetched via the X1 ORM ``USER_NOTIFICATION`` model
using :class:`~pskovedu.methods._bases.X1Method`.

The X1Protocol resolves ``X1Model.USER_NOTIFICATION`` → ``SYS_GUID`` at
request time via the client's registry (populated during bootstrap).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from ..models.common import EduPage
from ..models.notifications import UserNotification
from ..x1db.constants import X1Model
from ._bases import X1Method


class GetUserNotifications(X1Method[EduPage[UserNotification]]):
    """Fetch portal notifications for the current user.

    X1 ORM: ``USER_NOTIFICATION`` model, ``query.select`` method.

    Resolves ``X1Model.USER_NOTIFICATION`` → ``SYS_GUID`` via the runtime
    registry.  Optionally filter by state to show only active notifications.

    Args:
        where: optional X1 filter dict (e.g. ``{"SYS_STATE": "2"}`` for active only).
        limit: max records (``None`` = server default, typically 50).
    """

    __x1_service__: ClassVar[str] = "query"
    __x1_method__: ClassVar[str] = "select"
    __x1_model__: ClassVar[str] = X1Model.USER_NOTIFICATION

    where: dict[str, Any] = Field(default_factory=dict)
    limit: int | None = None
