# pskovedu-sdk

Async Python SDK for the **one.pskovedu.ru** electronic journal — the Pskov Region education portal.

> [Русская версия →](README.md)

---

## Features

- **Authentication** — `X1_SSO` cookie, QR-code via Gosuslugi (ESIA), full ESIA OAuth flow
- **Typed API** — every endpoint is a dataclass method with a typed return annotation; `await client(Method(...))` and `async for`
- **Protocols** — REST, Ext.Direct RPC (`POST /extjs/direct`), SSE, HTML parsing
- **Reactive watchers** — `async for event in watcher.events()` for marks, homework, schedule, notifications, reception slots
- **`Dispatcher`** — merges multiple watchers into a single event stream
- **Lesson bell** — `LessonBell` runs locally from a schedule day, emitting `Bell`, `LessonStarting`, `LessonEnded`
- **Storage** — `MemoryStorage` / `FileStorage`; snapshots persist across restarts
- **Circuit breaker** and **rate limiter** built into the transport layer
- **py.typed** — full mypy / pyright strict-mode support

---

## Requirements

Python **3.12+**. Dependencies: `httpx`, `pydantic`, `pydantic-settings`, `structlog`, `selectolax`, `anyio`.

---

## Installation

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git"
```

In `requirements.txt`:

```
pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git
```

---

## Quick start

### Cookie auth

```python
import asyncio
from pskovedu import Client

async def main():
    async with Client.from_cookie(x1_sso="YOUR_X1_SSO") as client:
        session = await client.get_session()
        print(session.display_name)

asyncio.run(main())
```

### QR login via Gosuslugi

```python
async def show_qr(url: str) -> None:
    print("Scan in the Gosuslugi app:", url)

async with Client() as client:
    await client.login_qr(show_qr)
    session = await client.get_session()
    print(session.display_name)
```

### Diary and marks

```python
async with Client.from_cookie(x1_sso="...") as client:
    participants = await client.get_participants()
    guid = participants[0].guid

    week = await client.get_diary(guid)
    for entry in week.entries:
        print(entry.subject, entry.marks)

    report = await client.get_marks_report(guid)
    for subj in report.subjects:
        print(subj.name, subj.avg_mark)
```

### Reactive watchers

```python
from pskovedu import Client
from pskovedu.reactive import MarkWatcher, NotificationWatcher, Dispatcher
from pskovedu.reactive.events import NewMark, NewNotification

async with Client.from_cookie(x1_sso="...") as client:
    dispatcher = Dispatcher(
        MarkWatcher(client, participant_guid="..."),
        NotificationWatcher(client),
    )

    async for event in dispatcher.events():
        match event:
            case NewMark(mark=m):
                print("New mark:", m)
            case NewNotification(notification=n):
                print("Notification:", n.title)
```

### Lesson bell

```python
from pskovedu.reactive import LessonBell

schedule_day = await client.get_schedule_day(...)
bell = LessonBell(schedule_day)

async for event in bell.events():
    print(event)  # LessonStarting | Bell | LessonEnded
```

---

## Package layout

```
pskovedu/
├── client.py          # Client — single entry point
├── methods/           # Typed method classes (one file per domain)
├── models/            # Pydantic response models
├── reactive/          # Watchers, events, Dispatcher, LessonBell
├── auth/              # AuthManager, QR/ESIA/cookie solvers
├── protocol/          # REST, ExtDirect, SSE, X1
├── transport/         # Retry, SSE streaming
├── storage/           # MemoryStorage, FileStorage
├── parsers/           # HTML parsers (shell, participant, schedule, bundles)
└── config.py          # ClientConfig (pydantic-settings)
```

---

## Configuration

```python
from pskovedu.config import ClientConfig

config = ClientConfig(
    request_timeout_s=30.0,
    poll_interval_s=60.0,
)
```

All settings are available as environment variables prefixed `PSKOVEDU_`:

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_POLL_INTERVAL_S=60
```

---

## License

MIT — see [LICENSE](LICENSE).
