"""Watcher[T] — abstract base for all reactive poll-diff-emit watchers.

Subclasses declare three abstract hooks:

- :meth:`poll` — fetch the current list of domain objects from the API.
- :meth:`key_fn` — extract a stable string identity from one item.
- :meth:`to_events` — map a :class:`~pskovedu.reactive.diff.Delta` to
  zero or more :class:`~pskovedu.reactive.events.ReactiveEvent` instances.

The base wires them together:

- ``deltas()`` — an :class:`~collections.abc.AsyncIterator` that loops
  forever, calling ``poll()`` then :class:`~pskovedu.reactive.diff.StateDiffer`
  and yielding non-empty :class:`~pskovedu.reactive.diff.Delta` values.
  Backoff (5 s → *backoff_max*, exponential) swallows transient exceptions;
  :exc:`asyncio.CancelledError` propagates immediately.  A successful poll
  resets the backoff counter and sleeps *interval* seconds before the next poll.
- ``events()`` — flattens each ``Delta`` through :meth:`to_events` and yields
  the resulting :class:`~pskovedu.reactive.events.ReactiveEvent` objects.

The backoff loop shape is lifted verbatim from
:func:`pskovedu.polling.watch_notifications` so both surfaces have identical
resilience semantics.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from typing import TYPE_CHECKING, Any

from ..storage.base import BaseStorage
from ..storage.memory import MemoryStorage
from .diff import Delta, StateDiffer
from .events import ReactiveEvent

if TYPE_CHECKING:
    from ..client import Client

log = logging.getLogger(__name__)


class Watcher[T](ABC):
    """Abstract base for reactive SDK watchers.

    Args:
        client: authenticated :class:`~pskovedu.client.Client` instance.
        interval: seconds between successful polls (default ``30.0``, matching
            :func:`~pskovedu.polling.watch_notifications`).
        backoff_max: upper bound for exponential back-off on error (default ``300.0``).
        storage: persistence backend for the snapshot diff; defaults to the
            client's own ``_storage`` when available, otherwise a fresh
            :class:`~pskovedu.storage.memory.MemoryStorage`.
    """

    def __init__(
        self,
        client: Client,
        *,
        interval: float = 30.0,
        backoff_max: float = 300.0,
        storage: BaseStorage[Any] | None = None,
    ) -> None:
        self._client = client
        self._interval = interval
        self._backoff_max = backoff_max

        if storage is not None:
            _storage: BaseStorage[Any] = storage
        elif hasattr(client, "_storage") and isinstance(client._storage, BaseStorage):
            _storage = client._storage
        else:
            _storage = MemoryStorage()

        # Use the class name as namespace prefix so multiple watcher types
        # sharing the same storage object do not collide.
        namespace = f"{type(self).__name__}:{id(self)}"
        self._differ: StateDiffer[T] = StateDiffer(
            _storage,
            namespace=namespace,
            key_fn=self.key_fn,
        )


    @abstractmethod
    async def poll(self) -> list[T]:
        """Fetch the current list of domain objects from the API.

        Returns:
            A fresh list of typed items representing the current remote state.
        """

    @abstractmethod
    def key_fn(self, item: T) -> str:
        """Extract a stable string identity from *item*.

        The key must be unique within the watcher's domain and must not change
        between polls for the same logical object.

        Args:
            item: a domain object returned by :meth:`poll`.

        Returns:
            A stable string key (e.g. a GUID).
        """

    @abstractmethod
    def to_events(self, delta: Delta[T]) -> Iterable[ReactiveEvent]:
        """Map *delta* to zero or more :class:`~pskovedu.reactive.events.ReactiveEvent` instances.

        Called once per non-empty :class:`~pskovedu.reactive.diff.Delta` produced
        by the differ.  Implementations should yield events for each meaningful
        change in ``delta.added``, ``delta.changed``, and ``delta.removed``.

        Args:
            delta: the diff produced by this poll cycle.

        Returns:
            An iterable of :class:`~pskovedu.reactive.events.ReactiveEvent` objects
            (may be empty even for a non-empty delta when the watcher chooses to
            filter certain change kinds).
        """


    async def deltas(self) -> AsyncIterator[Delta[T]]:
        """Yield non-empty :class:`~pskovedu.reactive.diff.Delta` objects as they arrive.

        Loops indefinitely:

        1. Calls :meth:`poll` to fetch the current state.
        2. Runs the :class:`~pskovedu.reactive.diff.StateDiffer` to detect changes.
        3. Yields the :class:`~pskovedu.reactive.diff.Delta` when it is non-empty.
        4. Sleeps *interval* seconds before the next poll.

        On any non-cancellation exception the loop backs off exponentially
        (starting at 5 s, doubling on each failure, capped at *backoff_max*),
        then retries — transient network errors never propagate to the caller.
        :exc:`asyncio.CancelledError` propagates immediately, stopping the loop.

        The backoff logic is lifted verbatim from
        :func:`pskovedu.polling.watch_notifications`.
        """
        backoff: float = 5.0

        while True:
            try:
                items = await self.poll()
                delta = await self._differ.compute(items)
                if not delta.is_empty:
                    yield delta
                backoff = 5.0
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception(
                    "watcher poll error — backing off",
                    extra={"watcher": type(self).__name__, "backoff": backoff},
                )
                await asyncio.sleep(min(backoff, self._backoff_max))
                backoff = min(backoff * 2, self._backoff_max)

    async def events(self) -> AsyncIterator[ReactiveEvent]:
        """Yield :class:`~pskovedu.reactive.events.ReactiveEvent` objects as they are detected.

        Drives :meth:`deltas` and maps each :class:`~pskovedu.reactive.diff.Delta`
        through :meth:`to_events`, yielding the resulting events one by one.

        Example::

            watcher = MarkWatcher(client, participant_guid="...")
            async for event in watcher.events():
                print(event)
        """
        async for delta in self.deltas():
            for event in self.to_events(delta):
                yield event
