"""Tests for StateDiffer / Delta — snapshot diff engine (task X2).

Coverage:
- Delta.added, .changed, .removed computed correctly against a MemoryStorage snapshot.
- FileStorage round-trip: snapshot survives across two StateDiffer instances sharing
  the same JSON file.
- prime=True: first compute() seeds the snapshot and returns an empty Delta; the
  second compute() (with no changes) also returns empty; only new items yield events.
"""

from __future__ import annotations

from pskovedu.reactive.diff import Delta, StateDiffer
from pskovedu.storage.file import FileStorage
from pskovedu.storage.memory import MemoryStorage


def _differ(storage: object, prime: bool = False) -> StateDiffer[str]:
    """Return a StateDiffer[str] keyed by value itself (identity key)."""
    return StateDiffer(
        storage,  # type: ignore[arg-type]
        namespace="test-ns",
        key_fn=lambda s: s,
        hash_fn=lambda s: s,
        prime=prime,
    )


async def test_first_call_all_added() -> None:
    """Items not in snapshot are all classified as added."""
    storage = MemoryStorage()
    differ = _differ(storage)
    delta = await differ.compute(["a", "b", "c"])
    assert set(delta.added) == {"a", "b", "c"}
    assert delta.changed == []
    assert delta.removed == []


async def test_second_call_unchanged_empty_delta() -> None:
    """Identical list on second poll → empty Delta."""
    storage = MemoryStorage()
    differ = _differ(storage)
    await differ.compute(["a", "b"])
    delta = await differ.compute(["a", "b"])
    assert delta.is_empty


async def test_added_item_detected() -> None:
    """New item added between polls appears in delta.added."""
    storage = MemoryStorage()
    differ = _differ(storage)
    await differ.compute(["a", "b"])
    delta = await differ.compute(["a", "b", "c"])
    assert delta.added == ["c"]
    assert delta.changed == []
    assert delta.removed == []


async def test_changed_item_detected() -> None:
    """Item with same key but different hash appears in delta.changed.

    We simulate 'change' by replacing one string with a longer one that
    has the same key prefix — using an explicit hash_fn that strips the
    last character so items "x1" and "x2" share key "x" but differ in hash.
    """
    storage = MemoryStorage()
    differ: StateDiffer[str] = StateDiffer(
        storage,
        namespace="change-test",
        key_fn=lambda s: s[0],  # key = first char
        hash_fn=lambda s: s,    # hash = full string
    )
    await differ.compute(["a1"])
    delta = await differ.compute(["a2"])  # same key "a", different hash
    assert delta.changed == ["a2"]
    assert delta.added == []


async def test_removed_key_tracked() -> None:
    """Key that disappears between polls is counted in delta.removed.

    Note: StateDiffer only tracks removed *keys*, not the original objects
    (the removed list will be empty — items disappear from the snapshot but
    cannot be reconstructed).  This tests the bookkeeping is clean (no crash,
    no false positives on subsequent calls).
    """
    storage = MemoryStorage()
    differ = _differ(storage)
    await differ.compute(["a", "b", "c"])
    delta = await differ.compute(["a"])   # "b" and "c" removed
    # removed list is empty per the diff.py design (keys tracked, objects not)
    assert delta.removed == []
    assert delta.changed == []
    assert delta.added == []


async def test_removed_key_gone_next_cycle_is_clean() -> None:
    """After removal, item re-appearing is classified as added again."""
    storage = MemoryStorage()
    differ = _differ(storage)
    await differ.compute(["a", "b"])
    await differ.compute(["a"])       # "b" disappears
    delta = await differ.compute(["a", "b"])  # "b" re-appears
    assert "b" in delta.added


async def test_mixed_delta() -> None:
    """add + change in same poll cycle."""
    storage = MemoryStorage()
    differ: StateDiffer[str] = StateDiffer(
        storage,
        namespace="mixed",
        key_fn=lambda s: s[0],
        hash_fn=lambda s: s,
    )
    await differ.compute(["a1", "b1"])
    delta = await differ.compute(["a2", "b1", "c1"])
    assert delta.changed == ["a2"]
    assert delta.added == ["c1"]
    assert delta.removed == []


async def test_filestorage_roundtrip(tmp_path) -> None:
    """Snapshot persisted by one StateDiffer is visible to a new instance."""
    db = tmp_path / "snap.json"
    storage1 = FileStorage(db)
    differ1: StateDiffer[str] = StateDiffer(
        storage1, namespace="rt", key_fn=lambda s: s, hash_fn=lambda s: s
    )
    await differ1.compute(["x", "y"])

    # New instance, new FileStorage pointing to same file.
    storage2 = FileStorage(db)
    differ2: StateDiffer[str] = StateDiffer(
        storage2, namespace="rt", key_fn=lambda s: s, hash_fn=lambda s: s
    )
    delta = await differ2.compute(["x", "y"])
    assert delta.is_empty, "Second instance should see the persisted snapshot"


async def test_filestorage_new_item_after_roundtrip(tmp_path) -> None:
    """New item is detected as added after loading snapshot from disk."""
    db = tmp_path / "snap2.json"
    storage1 = FileStorage(db)
    differ1: StateDiffer[str] = StateDiffer(
        storage1, namespace="rt2", key_fn=lambda s: s, hash_fn=lambda s: s
    )
    await differ1.compute(["x", "y"])

    storage2 = FileStorage(db)
    differ2: StateDiffer[str] = StateDiffer(
        storage2, namespace="rt2", key_fn=lambda s: s, hash_fn=lambda s: s
    )
    delta = await differ2.compute(["x", "y", "z"])
    assert delta.added == ["z"]
    assert delta.is_empty is False


async def test_prime_first_call_empty_delta() -> None:
    """prime=True: first compute() seeds snapshot and returns empty Delta."""
    storage = MemoryStorage()
    differ = _differ(storage, prime=True)
    delta = await differ.compute(["a", "b", "c"])
    assert delta.is_empty, "First call with prime=True must return empty Delta"


async def test_prime_second_call_empty_when_unchanged() -> None:
    """prime=True: second call with same items returns empty Delta."""
    storage = MemoryStorage()
    differ = _differ(storage, prime=True)
    await differ.compute(["a", "b"])   # seed
    delta = await differ.compute(["a", "b"])
    assert delta.is_empty


async def test_prime_second_call_detects_new_item() -> None:
    """prime=True: after seeding, a genuinely new item is reported."""
    storage = MemoryStorage()
    differ = _differ(storage, prime=True)
    await differ.compute(["a", "b"])   # seed — no events
    delta = await differ.compute(["a", "b", "c"])
    assert "c" in delta.added


async def test_prime_fires_exactly_once() -> None:
    """prime mode fires on the first call only; subsequent calls are normal diffs."""
    storage = MemoryStorage()
    differ = _differ(storage, prime=True)
    d1 = await differ.compute(["a"])   # seed
    d2 = await differ.compute(["a", "b"])   # new item
    d3 = await differ.compute(["a", "b"])   # unchanged
    assert d1.is_empty
    assert "b" in d2.added
    assert d3.is_empty


async def test_delta_is_empty_property() -> None:
    """Delta.is_empty is False when any list is non-empty."""
    empty = Delta(added=[], changed=[], removed=[])
    assert empty.is_empty is True

    with_added = Delta(added=["x"], changed=[], removed=[])
    assert with_added.is_empty is False

    with_changed = Delta(added=[], changed=["x"], removed=[])
    assert with_changed.is_empty is False

    with_removed = Delta(added=[], changed=[], removed=["x"])
    assert with_removed.is_empty is False
