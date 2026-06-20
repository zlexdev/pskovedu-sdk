# Reactive layer

The reactive layer turns repeated polling into a typed `async for` event stream.
Each watcher polls an endpoint on an interval, diffs the result against a stored
snapshot, and emits one event per change.

> The reactive watchers poll the same endpoints as the flat helpers, so a watcher
> built on an [Ext.Direct ⚠️ endpoint](known-issues.md#ext-direct--x1-envelope-is-wrong)
> (marks, reception) inherits that endpoint's status. `ScheduleWatcher` rides the
> REST schedule endpoint (✅).

## Flat helpers (recommended)

`Client` exposes `watch_*` methods that return an async iterator directly:

```python
from pskovedu.reactive.events import NewMark, MarkChanged

async with Client.from_cookie(x1_sso="...") as client:
    async for event in client.watch_marks(participant_guid="...", interval=30.0):
        match event:
            case NewMark(mark=m):
                print("New mark:", m)
            case MarkChanged(before=b, after=a):
                print("Changed:", b, "→", a)
```

Available helpers (all accept `interval`, `backoff_max`, `storage`):

| Helper | Watches | Emits |
|---|---|---|
| `client.watch_marks(participant_guid, …)` | marks | `NewMark`, `MarkChanged` |
| `client.watch_homework(participant_guid, …)` | diary | `NewHomework` |
| `client.watch_schedule(grade_guid, …)` | schedule | `ScheduleChanged` |
| `client.watch_reception(start, end, …)` | reception slots | `NewReception` |

## Watcher classes

The helpers wrap watcher classes you can also use directly (and feed to a
`Dispatcher`):

```python
from pskovedu.reactive import MarkWatcher, NotificationWatcher

watcher = MarkWatcher(client, participant_guid="...", interval=30.0)
async for event in watcher.events():
    ...
```

| Class | Constructor |
|---|---|
| `MarkWatcher` | `(client, participant_guid, *, interval, backoff_max, storage)` |
| `HomeworkWatcher` | `(client, participant_guid, …)` |
| `ScheduleWatcher` | `(client, grade_guid, …)` |
| `ReceptionWatcher` | `(client, start, end, audience=None, …)` |
| `NotificationWatcher` | `(client, …)` |

## Merging streams — Dispatcher

`Dispatcher` runs several watchers concurrently (one `asyncio.Task` each) and
merges their events into one stream in arrival order:

```python
from pskovedu.reactive import Dispatcher, MarkWatcher, HomeworkWatcher, NotificationWatcher

dispatcher = Dispatcher(
    MarkWatcher(client, participant_guid="..."),
    HomeworkWatcher(client, participant_guid="..."),
    NotificationWatcher(client),
)

async for event in dispatcher.events():
    print(type(event).__name__, event)
```

- A watcher that raises (anything except `CancelledError`) is **logged and
  dropped**; the others keep running.
- Breaking out of the `async for` cancels all pump tasks cleanly.

## Persistence & cold start

A watcher's first poll has an empty snapshot, so **every** current item is
classified as new and emitted. To avoid this flood on every restart, pass a
`FileStorage` whose snapshot persists between runs:

```python
from pskovedu.storage import FileStorage

storage = FileStorage("watch-state.json")
async for event in client.watch_marks(participant_guid="...", storage=storage):
    ...
```

On the first ever run you'll still get the initial batch (there's nothing to diff
against yet); subsequent runs emit only genuine changes.

See [Gotchas](gotchas.md#cold-start-emits-the-entire-existing-dataset) for detail.

## Intervals & backoff

- `interval` (default `30.0s`) — delay between **successful** polls.
- On a transient error the watcher backs off exponentially up to `backoff_max`
  (default `300.0s`), then resets after the next success.
- `asyncio.CancelledError` always propagates immediately.

## Handling auth expiry in watchers

`X1_SSO` expiry surfaces as `AuthExpiredError` inside the poll loop and is
**not** auto-recovered. For long-running watchers, wrap the stream and
re-authenticate on failure:

```python
from pskovedu.exceptions import AuthExpiredError

while True:
    try:
        async for event in client.watch_marks(participant_guid="...", storage=storage):
            handle(event)
    except AuthExpiredError:
        await reauthenticate(client)   # your logic: fresh cookie / QR
        continue
```

## Lesson bell

`LessonBell` is **local and network-free** — it computes the bell schedule from a
single `ScheduleDay` and emits events as each is due:

```python
from datetime import timedelta
from pskovedu.reactive import LessonBell, LessonStarting, Bell, LessonEnded

day  = await client.get_schedule(grade_guid="...")
bell = client.lesson_bell(day, lead=timedelta(minutes=5))   # or LessonBell(day, lead=...)

async for event in bell.events():
    match event:
        case LessonStarting(lesson=l, lead=td):
            print(f"{l.subject} starts in {td}")
        case Bell(lesson=l, phase="begin"):
            print(f"▶ {l.subject}")
        case Bell(lesson=l, phase="end"):
            print(f"■ {l.subject}")
        case LessonEnded(lesson=l):
            print(f"done: {l.subject}")
```

`bell.planned()` returns the full sorted `(datetime, event)` schedule without
sleeping — handy for previewing or testing.

> **Timezone gotcha:** lesson times are local-naive. The default `now` returns a
> naive local datetime to match. If you pass a tz-aware `now`, keep *all* your
> datetime comparisons tz-aware or you'll hit
> `TypeError: can't subtract offset-naive and offset-aware datetimes`. See
> [Gotchas](gotchas.md#lessonbell--keep-your-now-callable-tz-consistent).

## `events()` is an async generator

`watcher.events()`, `Dispatcher.events()`, and `LessonBell.events()` are async
**generators**. Always `async for` them — never `await` them.
