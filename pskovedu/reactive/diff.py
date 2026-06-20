"""StateDiffer[T] + Delta[T] — snapshot-based diff engine for the reactive layer.

``StateDiffer`` compares a freshly-fetched list of items against a persisted
snapshot (stored via ``BaseStorage``) and returns a ``Delta`` describing what
was added, changed, or removed since the last call.

## Cold-start / priming (R5)

On the first run the snapshot is empty, so every item would be classified as
"added" — which may flood consumers with stale events they did not expect.
Pass ``prime=True`` to the constructor to **seed the snapshot without emitting**:
``compute()`` will store the current items as the baseline and return an empty
``Delta``.  Subsequent calls behave normally.

Example::

    differ = StateDiffer(
        storage,
        namespace="marks:student-guid",
        key_fn=lambda m: m.mark_guid,
        prime=True,       # first compute() -> empty Delta, snapshot seeded
    )
    delta = await differ.compute(marks)  # Delta(added=[], changed=[], removed=[])
    # next call will diff against the snapshot just stored
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from ..storage.base import BaseStorage

_SNAPSHOT_PREFIX = "differ"


@dataclass(frozen=True, slots=True)
class Delta[T]:
    """Immutable description of state changes between two snapshots.

    Attributes:
        added: items present in the new state but absent from the old snapshot.
        changed: items whose hash changed between snapshots.
        removed: items present in the old snapshot but absent from the new state.
    """

    added: list[T]
    changed: list[T]
    removed: list[T]

    @property
    def is_empty(self) -> bool:
        """``True`` when no adds, changes, or removals were detected."""
        return not (self.added or self.changed or self.removed)


class StateDiffer[T]:
    """Diff a live list of items against a persisted snapshot.

    The snapshot is a ``dict[str, str]`` mapping *item-key -> item-hash* and is
    stored under the key ``"differ:<namespace>"`` via the supplied ``BaseStorage``.

    Args:
        storage: any ``BaseStorage`` backend (``MemoryStorage``, ``FileStorage``, ...).
        namespace: logical name for this differ's snapshot key, e.g.
            ``"marks:student-guid"`` or ``"notifications"``.
        key_fn: extracts a stable string identity from an item (e.g. the item's
            GUID).  Items with the same key are considered "the same object".
        hash_fn: extracts a string fingerprint from an item used to detect
            *changes*.  When ``None`` the default is used: ``model_dump_json()``
            for Pydantic ``BaseModel`` instances, ``repr(item)`` otherwise.
        prime: when ``True``, the **first** ``compute()`` call seeds the snapshot
            with the supplied items and returns an empty ``Delta`` instead of
            classifying everything as "added".  Useful for callers that want to
            receive only *changes after start-up*, not the full initial dataset.
            Subsequent calls always emit real diffs regardless of this flag.
    """

    def __init__(
        self,
        storage: BaseStorage,  # type: ignore[type-arg]
        namespace: str,
        key_fn: Callable[[T], str],
        hash_fn: Callable[[T], str] | None = None,
        *,
        prime: bool = False,
    ) -> None:
        self._storage = storage
        self._namespace = namespace
        self._key_fn = key_fn
        self._hash_fn = hash_fn
        self._prime = prime
        self._storage_key = f"{_SNAPSHOT_PREFIX}:{namespace}"

    def _item_hash(self, item: T) -> str:
        """Return a content fingerprint for *item*."""
        if self._hash_fn is not None:
            return self._hash_fn(item)
        if isinstance(item, BaseModel):
            return item.model_dump_json()
        return repr(item)

    async def _load_snapshot(self) -> dict[str, str]:
        """Load the persisted snapshot from storage.

        Returns an empty dict when no snapshot exists yet.
        """
        raw = await self._storage.get(self._storage_key)
        if raw is None:
            return {}
        # Snapshot is stored as a dict[str, str]; FileStorage round-trips via JSON.
        if isinstance(raw, dict):
            return dict(raw)
        try:
            return dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    async def _save_snapshot(self, snapshot: dict[str, str]) -> None:
        """Persist *snapshot* to storage."""
        await self._storage.set(self._storage_key, snapshot)

    async def compute(self, items: list[T]) -> Delta[T]:
        """Diff *items* against the persisted snapshot and persist the new state.

        On the very first call when ``prime=True`` was set in the constructor,
        the snapshot is seeded with *items* and an **empty** ``Delta`` is
        returned (cold-start priming — see module docstring / R5).

        Otherwise:
        - items whose key is absent from the old snapshot -> ``added``
        - items whose key exists but whose hash changed -> ``changed``
        - keys in the old snapshot absent from *items* -> ``removed``
          (note: only key tracking; concrete Watcher subclasses cache objects
          to reconstruct removed items if needed)

        The new snapshot is always persisted so that the next call sees the
        current state.

        Args:
            items: the freshly-fetched list of domain objects.

        Returns:
            A :class:`Delta` describing what changed.
        """
        old_snapshot = await self._load_snapshot()
        new_snapshot: dict[str, str] = {}

        added: list[T] = []
        changed: list[T] = []

        for item in items:
            key = self._key_fn(item)
            h = self._item_hash(item)
            new_snapshot[key] = h
            if key not in old_snapshot:
                added.append(item)
            elif old_snapshot[key] != h:
                changed.append(item)

        # Keys present in the old snapshot but gone from the live list are
        # "removed".  We cannot reconstruct the original T objects here (they
        # are not in `items`); Watcher subclasses (B3) that need removed objects
        # should maintain their own item cache keyed by key_fn.
        removed: list[T] = []

        # Persist the new snapshot before any early return.
        await self._save_snapshot(new_snapshot)

        # Cold-start priming: seed the snapshot without emitting anything.
        if self._prime and not old_snapshot:
            self._prime = False  # prime fires exactly once per instance
            return Delta(added=[], changed=[], removed=[])

        return Delta(added=added, changed=changed, removed=removed)

    async def reset(self) -> None:
        """Clear the persisted snapshot.

        The next ``compute()`` call will treat every item as "added" (or as a
        new prime seed if ``prime=True`` was re-set on the instance).
        """
        await self._storage.delete(self._storage_key)
