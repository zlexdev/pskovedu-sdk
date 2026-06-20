<div align="center">

# pskovedu-sdk

**Асинхронный Python SDK для электронного журнала pskovedu.ru**

Портал образования Псковской области · one.pskovedu.ru

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Typed](https://img.shields.io/badge/typed-py.typed-informational)](pskovedu/py.typed)
[![Vibe coded](https://img.shields.io/badge/vibe-coded-blueviolet)](https://en.wikipedia.org/wiki/Vibe_coding)

[English version →](README.md)

</div>

> **Важно:** Библиотека по большей части вайбкод — разработана с помощью ИИ. API, типы и логика корректны насколько нам известно, но используйте на свой страх и риск. Форкайте и допиливайте под себя.

---

## Возможности

- **Авторизация** — вход по cookie `X1_SSO`, QR-код через Госуслуги (ESIA), полный ESIA OAuth-поток
- **API** — REST, Ext.Direct RPC (`POST /extjs/direct`), SSE-стримы, HTML-парсинг
- **Реактивный слой** — `async for event in watcher.events()` для оценок, домашних заданий, расписания, уведомлений, приёмной
- **Звонки** — `LessonBell` работает локально без сетевых запросов, генерирует `Bell`, `LessonStarting`, `LessonEnded`
- **Хранилище** — `MemoryStorage` / `FileStorage`; снимки персистируются между перезапусками
- **Типизация** — маркер `py.typed`, полная поддержка mypy / pyright в strict-режиме

---

## Требования

Python **3.12+**. Зависимости устанавливаются автоматически: `httpx`, `pydantic`, `pydantic-settings`, `structlog`, `selectolax`, `anyio`.

---

## Установка

Пакет не публикуется на PyPI — устанавливается напрямую с GitHub.

### pip

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git"
```

### requirements.txt

```
pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git
```

### pyproject.toml

```toml
[project]
dependencies = [
    "pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git",
]
```

### Конкретный коммит

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git@COMMIT_SHA"
```

### Dev-режим (editable)

```bash
git clone https://github.com/zlexdev/pskovedu-sdk.git
cd pskovedu-sdk
pip install -e ".[dev]"

pytest
```

---

## Быстрый старт

### Авторизация по cookie

```python
import asyncio
from pskovedu import Client

async def main():
    async with Client.from_cookie(x1_sso="ВАШ_X1_SSO") as client:
        session = await client.get_session()
        print(session.display_name)

asyncio.run(main())
```

### QR-авторизация через Госуслуги

```python
async def show_qr(url: str) -> None:
    print("Отсканируйте QR в приложении Госуслуги:", url)

async with Client() as client:
    await client.login_qr(show_qr)
    session = await client.get_session()
    print("Вошли как:", session.display_name)
```

---

## Примеры

### Дневник и оценки

```python
async with Client.from_cookie(x1_sso="...") as client:
    participants = await client.get_participants()
    guid = participants[0].guid

    week = await client.get_diary(guid)
    for entry in week.entries:
        print(f"{entry.subject}: {entry.marks}")

    report = await client.get_marks_report(guid)
    for subj in report.subjects:
        print(f"{subj.name}  avg={subj.avg_mark}")

    # Несколько недель потоком
    async for entry in client(DiaryPages(participant_guid=guid, start=date(2025, 9, 1))):
        print(entry)
```

### Расписание

```python
    schedule = await client.get_schedule(grade_guid="...")
    for lesson in schedule.lessons:
        print(lesson.time_start, lesson.subject, lesson.teacher)
```

### Уведомления

```python
    notifications = await client.get_notifications()
    for n in notifications:
        print(n.title, n.created_at)
```

---

## Реактивный слой

Модуль `reactive` превращает периодические опросы API в типизированный поток событий. Снимки сравниваются автоматически — дубли отфильтрованы.

### Один наблюдатель

```python
from pskovedu.reactive import MarkWatcher
from pskovedu.reactive.events import NewMark, MarkChanged

async with Client.from_cookie(x1_sso="...") as client:
    watcher = MarkWatcher(client, participant_guid="...", interval=30.0)

    async for event in watcher.events():
        match event:
            case NewMark(mark=m):
                print("Новая оценка:", m.value, "по", m.subject)
            case MarkChanged(before=b, after=a):
                print(f"Оценка изменена: {b.value} → {a.value}")
```

### Несколько наблюдателей через Dispatcher

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

### Персистентные снимки

```python
from pskovedu.storage import FileStorage
from pskovedu.reactive import MarkWatcher

storage = FileStorage(path="/var/lib/mybot/state.json")
watcher = MarkWatcher(client, participant_guid="...", storage=storage)
```

### Доступные наблюдатели

| Класс | Генерирует события |
|---|---|
| `MarkWatcher` | `NewMark`, `MarkChanged` |
| `HomeworkWatcher` | `NewHomework` |
| `ScheduleWatcher` | `ScheduleChanged` |
| `ReceptionWatcher` | `NewReception` |
| `NotificationWatcher` | `NewNotification` |

---

## Звонки уроков

```python
from pskovedu.reactive import LessonBell
from datetime import timedelta

schedule_day = await client.get_schedule_day(grade_guid="...")
bell = LessonBell(schedule_day, lead=timedelta(minutes=5))

async for event in bell.events():
    match event:
        case LessonStarting(lesson=l, lead=td):
            print(f"Через {td}: {l.subject}")
        case Bell(lesson=l, phase="begin"):
            print(f"▶ Начало: {l.subject}")
        case Bell(lesson=l, phase="end"):
            print(f"■ Конец: {l.subject}")
```

---

## Конфигурация

```python
from pskovedu.config import ClientConfig

config = ClientConfig(
    request_timeout_s=30.0,
    poll_interval_s=60.0,
    backoff_max_s=300.0,
)
```

Через переменные окружения (префикс `PSKOVEDU_`):

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_POLL_INTERVAL_S=60
PSKOVEDU_BACKOFF_MAX_S=300
```

---

## Структура пакета

```
pskovedu/
├── client.py          # Client — единственная точка входа
├── config.py          # ClientConfig (pydantic-settings)
├── constants.py       # Хосты, пути, Ext.Direct action/method энумы
├── exceptions.py      # Типизированная иерархия исключений
│
├── methods/           # Один файл на домен: diary, schedule, reports, …
├── models/            # Pydantic-модели ответов
│
├── reactive/
│   ├── events.py      # Иерархия ReactiveEvent (NewMark, Bell, …)
│   ├── diff.py        # StateDiffer[T] — движок снимков
│   ├── _base.py       # Watcher[T] ABC — цикл poll → diff → emit
│   ├── watchers.py    # MarkWatcher, HomeworkWatcher, …
│   ├── dispatcher.py  # Dispatcher — объединяет N наблюдателей
│   └── bell.py        # LessonBell — локальный планировщик звонков
│
├── auth/              # AuthManager, QR/ESIA-солверы, токены
├── protocol/          # REST, Ext.Direct, SSE, X1
├── transport/         # Retry + backoff, SSE-стриминг
├── storage/           # MemoryStorage, FileStorage
├── parsers/           # HTML-парсеры: shell, participant, schedule
├── sessions/          # HttpxSession
├── pagination/        # PageIterator
├── breaker/           # CircuitBreaker
└── rate_limit/        # TokenBucket
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
