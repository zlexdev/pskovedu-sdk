"""Long-poll helpers for the pskovedu SDK.

Provides async generators that continuously fetch portal data and yield only
new items, backing off exponentially on transient errors.

.. note::
    :func:`watch_notifications` is now a thin shim over
    :class:`~pskovedu.reactive.watchers.NotificationWatcher`.  Its public
    signature and observable behaviour (dedup by ``guid``, exponential
    back-off, ``AsyncIterator[UserNotification]`` return type) are unchanged.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .models.notifications import UserNotification
from .reactive.watchers import NotificationWatcher

if TYPE_CHECKING:
    from .client import Client

__all__ = ["watch_notifications"]


async def watch_notifications(
    client: Client,
    *,
    poll_interval: float = 30.0,
    backoff_max: float = 300.0,
    limit: int = 50,  # noqa: ARG001  # kept for public-API compat; watcher owns its fetch size
) -> AsyncIterator[UserNotification]:
    """Yield new portal notifications as they arrive.

    Polls the portal every *poll_interval* seconds via
    :class:`~pskovedu.reactive.watchers.NotificationWatcher` and yields each
    :class:`~pskovedu.models.notifications.UserNotification` whose ``guid``
    has not been seen before.

    On any non-cancellation exception the generator sleeps with exponential
    back-off (starting at 5 s, capped at *backoff_max*) rather than
    propagating, so callers stay alive through transient network errors.

    Args:
        client: authenticated :class:`~pskovedu.client.Client` instance.
        poll_interval: seconds between successful polls (default ``30.0``).
        backoff_max: maximum back-off ceiling in seconds (default ``300.0``).
        limit: kept for backwards compatibility; the underlying watcher
            controls its own fetch size via
            :meth:`~pskovedu.reactive.watchers.NotificationWatcher.poll`.
    """
    watcher = NotificationWatcher(
        client,
        interval=poll_interval,
        backoff_max=backoff_max,
    )
    async for delta in watcher.deltas():
        for item in delta.added:
            yield item
