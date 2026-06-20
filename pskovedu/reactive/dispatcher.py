"""Dispatcher — merges N :class:`~pskovedu.reactive._base.Watcher` streams into one.

Each watcher's :meth:`~pskovedu.reactive._base.Watcher.events` generator runs
concurrently in its own :class:`asyncio.Task`.  Events are pushed into a shared
:class:`asyncio.Queue` and the consumer yields them in arrival order.

A failing watcher (any exception other than :exc:`asyncio.CancelledError`) is
logged and silently dropped — the remaining watchers keep running.  When the
caller stops iterating (``break``, ``return``, or cancellation) all pump tasks
are cancelled in the ``finally`` block.

Example::

    dispatcher = Dispatcher(mark_watcher, homework_watcher, notification_watcher)
    async for event in dispatcher.events():
        print(event)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ._base import Watcher
from .events import ReactiveEvent

log = logging.getLogger(__name__)

# Sentinel object placed in the queue when a pump task finishes (either
# normally or after its exception is swallowed).
_DONE = object()


class Dispatcher:
    """Merges the event streams of multiple :class:`~pskovedu.reactive._base.Watcher`
    instances into a single async iterator.

    Args:
        *watchers: Any number of :class:`~pskovedu.reactive._base.Watcher` instances
            to run concurrently.  Pass at least one; passing zero yields nothing.

    Example::

        d = Dispatcher(mark_watcher, homework_watcher)
        async for event in d.events():
            handle(event)
    """

    def __init__(self, *watchers: Watcher[Any]) -> None:
        self._watchers = watchers

    async def events(self) -> AsyncIterator[ReactiveEvent]:
        """Yield :class:`~pskovedu.reactive.events.ReactiveEvent` objects from all
        watchers, merged in arrival order.

        One :class:`asyncio.Task` is spawned per watcher.  Each task pumps events
        from the watcher's :meth:`~pskovedu.reactive._base.Watcher.events` generator
        into a shared :class:`asyncio.Queue`.  Any exception raised by a watcher
        is caught, logged, and swallowed — the other pumps continue unaffected.
        A sentinel :data:`_DONE` value is pushed when a pump exits so the consumer
        can track how many pumps are still alive and stop when all are gone.

        All pump tasks are cancelled in the ``finally`` block regardless of how the
        caller exits (normal completion, ``break``, or :exc:`asyncio.CancelledError`).
        """
        if not self._watchers:
            return

        queue: asyncio.Queue[ReactiveEvent | object] = asyncio.Queue()
        tasks: list[asyncio.Task[None]] = []

        async def _pump(watcher: Watcher[Any]) -> None:
            """Push events from one watcher into *queue*; swallow non-cancel errors."""
            try:
                async for event in watcher.events():
                    await queue.put(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception(
                    "watcher pump error — dropping watcher",
                    extra={"watcher": type(watcher).__name__},
                )
            finally:
                await queue.put(_DONE)

        try:
            for watcher in self._watchers:
                task = asyncio.create_task(_pump(watcher))
                tasks.append(task)

            active = len(tasks)
            while active > 0:
                item = await queue.get()
                if item is _DONE:
                    active -= 1
                else:
                    # item is guaranteed to be ReactiveEvent here
                    yield item  # type: ignore[misc]
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Await cancellation to avoid "Task was destroyed but it is pending"
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
