# pskovedu.reactive — snapshot-diff engine and event-driven watcher layer

Sits *above* `Client` (consumes its read methods, never imported by the
transport or protocol layers).  Converts repeated API polls into a typed
stream of `ReactiveEvent` objects via a snapshot-diff backbone.

## Modules

| File | Purpose |
|------|---------|
| `diff.py` | `Delta[T]` (frozen dataclass) + `StateDiffer[T]` — diffs a live list against a `BaseStorage` snapshot; supports cold-start priming (`prime=True`) |
| `events.py` | Frozen-slots event hierarchy rooted at `ReactiveEvent` |
| `_base.py` | `Watcher[T]` ABC — interval/backoff poll loop + differ integration |
| `watchers.py` | Five concrete watchers: `MarkWatcher`, `HomeworkWatcher`, `ScheduleWatcher`, `ReceptionWatcher`, `NotificationWatcher` |
| `bell.py` | `LessonBell` — local, network-free lesson-bell scheduler |
| `dispatcher.py` | `Dispatcher` — merges N watcher streams into one async iterator |
| `__init__.py` | Re-exports all public names |

---

## diff.py — `Delta[T]` and `StateDiffer[T]`

### `Delta[T]`

Frozen dataclass (`slots=True`). Immutable description of one poll cycle's diff.

```python
@dataclass(frozen=True, slots=True)
class Delta[T]:
    added:   list[T]   # present in new state, absent from old snapshot
    changed: list[T]   # key existed but content hash changed
    removed: list[T]   # in old snapshot, absent from new state

    @property
    def is_empty(self) -> bool: ...
```

### `StateDiffer[T]`

Stores a `dict[key → content-hash]` snapshot under `"differ:<namespace>"` in
any `BaseStorage` backend.

```python
class StateDiffer[T]:
    def __init__(
        self,
        storage: BaseStorage,
        namespace: str,                          # e.g. "marks:student-guid"
        key_fn: Callable[[T], str],
        hash_fn: Callable[[T], str] | None = None,  # default: model_dump_json() / repr()
        *,
        prime: bool = False,   # seed snapshot silently on first compute()
    ) -> None: ...

    async def compute(self, items: list[T]) -> Delta[T]: ...
    async def reset(self) -> None: ...            # clears persisted snapshot
```

**Cold-start priming (`prime=True`):** the first `compute()` call seeds the
snapshot and returns an empty `Delta` — callers receive only *changes after
start-up*, not the full initial dataset.  The flag auto-clears after firing.

**Hash default:** `model_dump_json()` for Pydantic `BaseModel` instances,
`repr(item)` otherwise.

---

## events.py — event hierarchy

All events are frozen dataclasses (`slots=True`) that inherit from `ReactiveEvent`.

```python
@dataclass(frozen=True, slots=True)
class ReactiveEvent:
    at: datetime   # UTC wall-clock of the poll cycle that detected this event
```

| Class | Extra fields | Emitted when |
|---|---|---|
| `NewMark` | `mark: Any`, `participant_guid: str` | Previously unseen grade appears |
| `MarkChanged` | `before: Any`, `after: Any` | Existing mark value/metadata changes |
| `NewHomework` | `entry: Any` | New diary/homework entry detected |
| `ScheduleChanged` | `kind: ScheduleChangeKind`, `lesson: Any` | Lesson diff detected |
| `NewReception` | `slot: Any` | New reception slot becomes available |
| `NewNotification` | `notification: Any` | New portal notification detected |
| `LessonStarting` | `lesson: Any`, `lead: timedelta` | Fires `lead` time before lesson start |
| `Bell` | `lesson: Any`, `phase: Literal["begin", "end"]` | Exact lesson start or end |
| `LessonEnded` | `lesson: Any` | Lesson concluded (mirrors `Bell(phase="end")`) |

### `ScheduleChangeKind` (StrEnum)

```python
class ScheduleChangeKind(StrEnum):
    CANCELLED = "cancelled"
    MOVED     = "moved"
    TEACHER   = "teacher"
    ROOM      = "room"
    ADDED     = "added"
```

---

## _base.py — `Watcher[T]` abstract base

Three abstract hooks; the base wires them into a resilient poll-diff-emit loop.

```python
class Watcher[T](ABC):
    def __init__(
        self,
        client: Client,
        *,
        interval: float = 30.0,      # seconds between successful polls
        backoff_max: float = 300.0,  # upper bound for exponential backoff on error
        storage: BaseStorage[Any] | None = None,
        # defaults to client._storage when available, else a fresh MemoryStorage
    ) -> None: ...

    # — abstract hooks (subclasses must implement) —

    @abstractmethod
    async def poll(self) -> list[T]: ...
    # Fetch a fresh list of domain objects from the API.

    @abstractmethod
    def key_fn(self, item: T) -> str: ...
    # Extract a stable string identity (e.g. a GUID) from one item.

    @abstractmethod
    def to_events(self, delta: Delta[T]) -> Iterable[ReactiveEvent]: ...
    # Map a Delta to zero or more ReactiveEvent instances.

    # — provided by the base —

    async def deltas(self) -> AsyncIterator[Delta[T]]: ...
    # Loops indefinitely: poll → diff → yield non-empty Delta → sleep interval.
    # Backoff: starts at 5 s, doubles on each error, capped at backoff_max (default 300 s).
    # asyncio.CancelledError propagates immediately; all other exceptions are swallowed.

    async def events(self) -> AsyncIterator[ReactiveEvent]: ...
    # Drives deltas() and flattens each Delta through to_events().
```

**Backoff shape:** initial 5 s, doubles on each consecutive failure, capped at
`backoff_max`.  A successful poll resets the counter to 5 s.  Identical
semantics to `pskovedu.polling.watch_notifications`.

**Storage namespacing:** each `Watcher` instance registers its `StateDiffer`
under `"<ClassName>:<id(self)>"` so multiple watchers sharing one storage
backend never collide.

---

## watchers.py — five concrete watchers

All accept the same keyword arguments as `Watcher.__init__` via `**kw`.

### `MarkWatcher(client, participant_guid, **kw)`

Polls the marks report for one diary participant.  Emits `NewMark` for each
new grade and `MarkChanged` when an existing mark changes.

- `poll()` → `list[SubjectMark]`
- `key_fn` → `mark.mark_guid`

### `HomeworkWatcher(client, participant_guid, **kw)`

Polls the diary for new homework entries.  Emits `NewHomework` for each added
diary entry; removals and mutations are ignored.

- `poll()` → `list[DiaryEntry]`

### `ScheduleWatcher(client, grade_guid, **kw)`

Polls the class schedule and classifies lesson-level changes.  Emits
`ScheduleChanged` with the appropriate `ScheduleChangeKind`.

- `poll()` → `list[Lesson]`
- `key_fn` → `lesson.sys_guid`
- `_classify(before, after)` — best-effort: `CANCELLED`, `MOVED`, `TEACHER`, `ROOM`, `ADDED`.

### `ReceptionWatcher(client, start, end, *, audience=None, **kw)`

Polls reception slots in the given date range.  Emits `NewReception` for
newly available slots.

- `poll()` → `list[ReceptionSlot]`
- `start` / `end` — `"DD.MM.YYYY"` strings.

### `NotificationWatcher(client, **kw)`

Polls user portal notifications.  Emits `NewNotification` for each new entry.

- `poll()` → `list[UserNotification]`

---

## bell.py — `LessonBell`

Local bell scheduler built from a single `ScheduleDay`.  Pure datetime
arithmetic; no network calls.

```python
class LessonBell:
    def __init__(
        self,
        schedule: ScheduleDay,
        *,
        lead: timedelta = timedelta(minutes=5),
        now: Callable[[], datetime] = _local_now,    # injected for testing
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,  # injected for testing
    ) -> None: ...
```

| Method | Returns | Notes |
|---|---|---|
| `planned()` | `list[tuple[datetime, ReactiveEvent]]` | Pure, no I/O — full sorted event schedule for the day |
| `async events()` | `AsyncIterator[ReactiveEvent]` | Real-time: drives `planned()`, sleeps until each event is due |
| `current_lesson()` | `LessonTime \| None` | Slot currently in progress per `now()` |
| `next_lesson()` | `LessonTime \| None` | Next upcoming slot per `now()`; `None` if none left today |
| `time_to_bell()` | `timedelta \| None` | Time until the next bell event; `None` if none left |

**Events produced by `planned()`:** `LessonStarting` (at `begin − lead`),
`Bell(phase="begin")` at lesson start, `Bell(phase="end")` + `LessonEnded`
at lesson end.

**`now` / `sleep` injection:** both are constructor parameters so unit tests
can substitute a fake clock and a no-op sleep without patching globals.

**Timezone:** the default `_local_now()` returns a naive local datetime
(matching portal convention).  Pass a tz-aware callable to `now` to get
tz-aware datetimes throughout.

---

## dispatcher.py — `Dispatcher`

Merges event streams from multiple `Watcher` instances into one async iterator,
events yielded in arrival order.

```python
class Dispatcher:
    def __init__(self, *watchers: Watcher[Any]) -> None: ...

    async def events(self) -> AsyncIterator[ReactiveEvent]: ...
    # Spawns one asyncio.Task per watcher.
    # Each task pumps events into a shared asyncio.Queue.
    # Stops when all pumps finish or the calling task is cancelled.
```

Non-cancellation errors inside a pump task are logged and swallowed so one
failing watcher never brings down the others.

```python
# Example — watch marks and homework concurrently
dispatcher = Dispatcher(
    MarkWatcher(client, participant_guid="..."),
    HomeworkWatcher(client, participant_guid="..."),
)
async for event in dispatcher.events():
    print(event)
```

---

## Public exports (`reactive/__init__.py`)

```python
from pskovedu.reactive import (
    Delta, StateDiffer,
    Watcher,
    MarkWatcher, HomeworkWatcher, ScheduleWatcher,
    ReceptionWatcher, NotificationWatcher,
    Dispatcher,
    # event types live in pskovedu.reactive.events
)
```
