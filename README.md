<div align="center">

# pskovedu-sdk

**Async Python SDK for the pskovedu.ru electronic journal**

Pskov Region Education Portal · one.pskovedu.ru

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Typed](https://img.shields.io/badge/typed-py.typed-informational)](pskovedu/py.typed)
[![Vibe coded](https://img.shields.io/badge/vibe-coded-blueviolet)](https://en.wikipedia.org/wiki/Vibe_coding)

[Русская версия →](README.ru.md)

</div>

> **Note:** This library is mostly vibe-coded — built through AI-assisted development. The API surface, types, and logic are correct to the best of our knowledge, but treat it as experimental. Feel free to fork and adapt.

> 📖 **Full usage guide in [`docs/`](docs/README.md)** — [getting started](docs/getting-started.md) · [authentication](docs/authentication.md) · [usage](docs/usage.md) · [reactive layer](docs/reactive.md) · [configuration](docs/configuration.md) · [architecture](docs/architecture.md) · [gotchas](docs/gotchas.md) · [known issues & status](docs/known-issues.md).

---

## Overview

`pskovedu` is a fully typed, async-first Python client for the **one.pskovedu.ru** electronic journal — the education portal of Pskov Region, Russia. It covers:

- **Authentication** — `X1_SSO` cookie injection, QR-code login via Gosuslugi (ESIA), full ESIA OAuth flow
- **API** — REST, Ext.Direct RPC (`POST /extjs/direct`), SSE streams, HTML parsing
- **Reactive layer** — push-style async iterators for marks, homework, schedule changes, notifications, and reception slots
- **Lesson bell** — local scheduler that emits typed events from a `ScheduleDay` without any network calls
- **Typed** — `py.typed` marker, full mypy / pyright strict-mode support

---

## Requirements

- Python **3.12+**
- Dependencies (installed automatically): `httpx`, `pydantic`, `pydantic-settings`, `structlog`, `selectolax`, `anyio`

---

## Installation

The package is not on PyPI — install directly from GitHub.

### pip (one-liner)

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git"
```

### requirements.txt

```
pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git
```

### pyproject.toml (PEP 508)

```toml
[project]
dependencies = [
    "pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git",
]
```

### Pin to a specific commit

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git@COMMIT_SHA"
```

### Development install (editable)

```bash
git clone https://github.com/zlexdev/pskovedu-sdk.git
cd pskovedu-sdk
pip install -e ".[dev]"

# Run tests
pytest
```

---

## Quick start

### Cookie auth

The fastest way to bootstrap a client if you already have an `X1_SSO` session cookie:

```python
import asyncio
from pskovedu import Client

async def main():
    async with Client.from_cookie(x1_sso="YOUR_X1_SSO") as client:
        shell = await client.get_shell()
        # Identity comes from the shell (X1_CONFIG.meta.au), not a /session endpoint
        print(shell.role_meta.name if shell.role_meta else "authenticated")

asyncio.run(main())
```

> The portal has **no `/session` profile endpoint**. The logged-in user's identity
> is injected into the app shell as the `X1_CONFIG.meta.au` global, exposed here as
> `ShellConfig.role_meta` via `get_shell()`.

### QR login via Gosuslugi

```python
import asyncio
from pskovedu import Client

async def show_qr(url: str) -> None:
    # Display or print the URL — user scans it in the Gosuslugi mobile app
    print("Scan QR in Gosuslugi:", url)

async def main():
    async with Client() as client:
        shell = await client.login_with_qr(display_cb=show_qr)   # blocks until confirmed
        print("Logged in as:", shell.role_meta.name if shell.role_meta else "?")

asyncio.run(main())
```

---

## Core concepts

### Client

`Client` is the single entry point. Every API call is a typed method-object:

```python
result = await client(SomeMethod(arg=value))
```

Paginated endpoints return an async iterator:

```python
async for entry in client(DiaryPages(participant_guid="...")):
    print(entry.subject, entry.marks)
```

### Methods

Each endpoint is a Pydantic dataclass that declares its HTTP method, URL, and return type:

```python
from pskovedu.methods.diary import GetDiary, GetMarksReport

week      = await client(GetDiary(participant_guid="..."))
marks     = await client(GetMarksReport(participant_guid="..."))
```

Protocol dispatch is automatic — REST, Ext.Direct RPC, SSE, and X1 all go through the same `client(...)` funnel.

---

## Examples

### Diary

```python
from datetime import date
from pskovedu.methods.diary import DiaryPages

async with Client.from_cookie(x1_sso="...") as client:
    participants = await client.get_participants()
    guid = participants[0].guid

    # Current week
    week = await client.get_diary(guid)
    for entry in week.entries:
        print(f"{entry.subject}: {entry.marks}")

    # Marks report (выписка оценок)
    report = await client.get_marks_report(guid)
    for subj in report.subjects:
        print(f"{subj.name}  avg={subj.avg_mark}")

    # Stream multiple weeks
    async for entry in client(DiaryPages(participant_guid=guid, start=date(2025, 9, 1))):
        print(entry)
```

### Schedule

```python
    schedule = await client.get_schedule(grade_guid="...")
    for lesson in schedule.lessons:
        print(lesson.time_start, lesson.subject, lesson.teacher)
```

### Notifications

```python
    notifications = await client.get_user_notifications()
    for n in notifications.items:
        print(n.title, n.created_at)
```

### Reception slots

```python
    slots = await client.get_reception(start="01.09.2025", end="30.09.2025")
    for slot in slots:
        print(slot.teacher, slot.time_start)
```

---

## Reactive layer

The reactive module converts repeated API polls into a typed `async for` stream with snapshot diffing — changes are detected automatically, duplicates suppressed.

### Single watcher

```python
from pskovedu.reactive import MarkWatcher
from pskovedu.reactive.events import NewMark, MarkChanged

async with Client.from_cookie(x1_sso="...") as client:
    watcher = MarkWatcher(client, participant_guid="...", interval=30.0)

    async for event in watcher.events():
        match event:
            case NewMark(mark=m):
                print("New mark:", m.value, "in", m.subject)
            case MarkChanged(before=b, after=a):
                print(f"Mark changed: {b.value} → {a.value}")
```

### Multiple watchers via Dispatcher

```python
from pskovedu.reactive import Dispatcher, MarkWatcher, NotificationWatcher, HomeworkWatcher

async with Client.from_cookie(x1_sso="...") as client:
    dispatcher = Dispatcher(
        MarkWatcher(client, participant_guid="..."),
        HomeworkWatcher(client, participant_guid="..."),
        NotificationWatcher(client),
    )

    async for event in dispatcher.events():
        print(type(event).__name__, event)
```

### Persistent snapshots

Pass a `FileStorage` so watcher snapshots survive restarts:

```python
from pskovedu.storage import FileStorage
from pskovedu.reactive import MarkWatcher

storage = FileStorage(path="/var/lib/mybot/state.json")
watcher = MarkWatcher(client, participant_guid="...", storage=storage)
```

### Available watchers

| Class | Emits |
|---|---|
| `MarkWatcher` | `NewMark`, `MarkChanged` |
| `HomeworkWatcher` | `NewHomework` |
| `ScheduleWatcher` | `ScheduleChanged` |
| `ReceptionWatcher` | `NewReception` |
| `NotificationWatcher` | `NewNotification` |

---

## Lesson bell

`LessonBell` runs entirely locally — no network calls. Give it a `ScheduleDay` and iterate:

```python
from pskovedu.reactive import LessonBell, LessonStarting, Bell, LessonEnded
from datetime import timedelta

schedule_day = await client.get_schedule(grade_guid="...")
bell = LessonBell(schedule_day, lead=timedelta(minutes=5))

async for event in bell.events():
    match event:
        case LessonStarting(lesson=l, lead=td):
            print(f"Lesson starting in {td}: {l.subject}")
        case Bell(lesson=l, phase="begin"):
            print(f"▶ {l.subject} started")
        case Bell(lesson=l, phase="end"):
            print(f"■ {l.subject} ended")
```

---

## Configuration

```python
from pskovedu.config import ClientConfig

config = ClientConfig(
    request_timeout_s=30.0,
    retries=2,
    rate_limit_rps=4.0,
)

async with Client(config=config) as client:
    ...
```

All settings accept environment variables with the `PSKOVEDU_` prefix:

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_RETRIES=2
PSKOVEDU_RATE_LIMIT_RPS=4.0
PSKOVEDU_ALLOW_MUTATIONS=false
```

---

## Package layout

```
pskovedu/
├── client.py          # Client — single entry point
├── config.py          # ClientConfig (pydantic-settings)
├── constants.py       # Hosts, paths, Ext.Direct action/method enums
├── exceptions.py      # Typed exception hierarchy
│
├── methods/           # One file per domain: diary, schedule, reports, …
├── models/            # Pydantic response models
│
├── reactive/
│   ├── events.py      # ReactiveEvent hierarchy (NewMark, Bell, …)
│   ├── diff.py        # StateDiffer[T] — snapshot-diff engine
│   ├── _base.py       # Watcher[T] ABC — poll → diff → emit loop
│   ├── watchers.py    # MarkWatcher, HomeworkWatcher, …
│   ├── dispatcher.py  # Dispatcher — merges N watchers into one stream
│   └── bell.py        # LessonBell — local lesson-bell scheduler
│
├── auth/              # AuthManager, QR/ESIA solvers, session tokens
├── protocol/          # REST, Ext.Direct, SSE, X1 wire protocols
├── transport/         # Retry + backoff, SSE streaming
├── storage/           # MemoryStorage, FileStorage (BaseStorage ABC)
├── parsers/           # HTML parsers: shell, participant, schedule, bundles
├── sessions/          # HttpxSession (BaseSession ABC)
├── pagination/        # PageIterator
├── breaker/           # CircuitBreaker
├── rate_limit/        # TokenBucket rate limiter
└── utils/             # JWT decode, URL encoding helpers
```

---

## Gotchas

### Cold start emits the entire existing dataset
A watcher starts with an empty snapshot, so the **first** poll classifies every
current mark / homework / slot as new and fires one event per item. To suppress
this flood on startup, pass a `FileStorage` whose snapshot already exists from a
previous run — subsequent restarts emit only changes since last stop.

### `X1_SSO` expiry is not auto-recovered
When the session cookie expires mid-run the next call raises `AuthExpiredError`.
There is no silent re-auth loop. Wrap long-running watchers in your own
reconnect logic around `AuthExpiredError`.

### `events()` is an async generator — do not `await` it
`watcher.events()`, `Dispatcher.events()`, and `LessonBell.events()` are async
generators. Use `async for event in watcher.events():` — never `await` them.

### Dispatcher silently drops a failing watcher, not all watchers
If one watcher raises a non-`CancelledError` exception it is logged and removed;
the remaining watchers continue. Breaking out of the `async for` cancels all
pump tasks cleanly.

### LessonBell — keep your `now` callable tz-consistent
Portal lesson times are local-naive strings. The default `now` returns a naive
local datetime to match. If you pass a tz-aware `now`, make sure all other
datetime comparisons in your code are also tz-aware — mixing raises
`TypeError: can't subtract offset-naive and offset-aware datetimes`.

### `FileStorage` is single-process only
Its in-process `asyncio.Lock` is safe across async tasks in one process but does
**not** lock across OS processes. Two processes pointing at the same JSON file
will clobber each other.

### `async with Client(...)` is strongly recommended
Without the context manager the session cookies are not persisted on shutdown and
the HTTP transport is not closed gracefully. Use `async with` for anything
long-lived.

### QR login times out after 120 seconds
`login_with_qr()` raises `AuthError` if no scan is detected within 120 s or
after 3 consecutive `qr-error` SSE events.

### Paginated methods return `EduPage`, not a list
`get_user_notifications()`, `get_reception()`, `get_participants()` etc. return
`EduPage[T]`. Iterate `.items`, or use `async for x in client(SomePages(...))` for
auto-fetching streams.

### Journal writes are opt-in
`ClientConfig.allow_mutations` defaults to `False`. Methods like `save_journal`
raise `MutationsDisabled` until you set `ClientConfig(allow_mutations=True)`.

---

## License

MIT — see [LICENSE](LICENSE).
