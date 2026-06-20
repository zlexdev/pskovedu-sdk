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

> 📖 **Полное руководство в [`docs/`](docs/README.md)** (на английском) — [старт](docs/getting-started.md) · [авторизация](docs/authentication.md) · [использование](docs/usage.md) · [реактивный слой](docs/reactive.md) · [конфигурация](docs/configuration.md) · [архитектура](docs/architecture.md) · [подводные камни](docs/gotchas.md) · [известные проблемы и статус](docs/known-issues.md).

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
        shell = await client.get_shell()
        # Идентичность берётся из shell (X1_CONFIG.meta.au), а не из /session
        print(shell.role_meta.name if shell.role_meta else "authenticated")

asyncio.run(main())
```

> У портала **нет эндпоинта `/session` с профилем**. Личность залогиненного
> пользователя приходит в shell как глобал `X1_CONFIG.meta.au` — он доступен как
> `ShellConfig.role_meta` через `get_shell()`.

### QR-авторизация через Госуслуги

```python
async def show_qr(url: str) -> None:
    print("Отсканируйте QR в приложении Госуслуги:", url)

async with Client() as client:
    shell = await client.login_with_qr(display_cb=show_qr)
    print("Вошли как:", shell.role_meta.name if shell.role_meta else "?")
```

---

## Примеры

### Дневник и оценки

```python
from datetime import date
from pskovedu.methods.diary import DiaryPages

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
    notifications = await client.get_user_notifications()
    for n in notifications.items:
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
from pskovedu.reactive import LessonBell, LessonStarting, Bell, LessonEnded
from datetime import timedelta

schedule_day = await client.get_schedule(grade_guid="...")
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
    retries=2,
    rate_limit_rps=4.0,
)
```

Через переменные окружения (префикс `PSKOVEDU_`):

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_RETRIES=2
PSKOVEDU_RATE_LIMIT_RPS=4.0
PSKOVEDU_ALLOW_MUTATIONS=false
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

## Подводные камни

### Первый запуск вываливает все существующие данные
Наблюдатель стартует с пустым снимком, поэтому на первом опросе каждая оценка /
задание / слот классифицируется как новая и порождает событие. Чтобы не получить
лавину при старте — передайте `FileStorage` с уже существующим снимком от
прошлого запуска.

### Истечение `X1_SSO` не восстанавливается автоматически
При протухании куки следующий запрос выбрасывает `AuthExpiredError`. Петли
автоматической переавторизации нет — оберните долгоживущие наблюдатели в
собственный reconnect-обработчик.

### `events()` — асинхронный генератор, не awaitable
`watcher.events()`, `Dispatcher.events()`, `LessonBell.events()` — асинхронные
генераторы. Используйте `async for event in watcher.events():`, никогда не `await`.

### Dispatcher молча дропает упавший наблюдатель, а не всё
Если один наблюдатель кидает не-`CancelledError` — он логируется и удаляется,
остальные продолжают работать. Выход из `async for` корректно отменяет все задачи.

### LessonBell — не смешивайте tz-aware и naive datetime
Портал возвращает локальные naive-строки. `now` по умолчанию тоже naive. Если
передаёте tz-aware `now` — следите, чтобы все остальные сравнения дат тоже были
aware, иначе получите `TypeError`.

### `FileStorage` — только для одного процесса
`asyncio.Lock` защищает только внутри одного процесса. Два процесса, работающих
с одним JSON-файлом, перетрут данные друг друга.

### `async with Client(...)` настоятельно рекомендуется
Без контекст-менеджера куки не сохраняются при остановке и HTTP-транспорт не
закрывается. Используйте `async with` для долгоживущего кода.

### QR-авторизация истекает через 120 секунд
`login_with_qr()` кидает `AuthError`, если QR не сканировали 120 с или
случилось 3 `qr-error` SSE-события подряд.

### Методы с пагинацией возвращают `EduPage`, а не список
`get_user_notifications()`, `get_reception()`, `get_participants()` и т.д.
возвращают `EduPage[T]`. Итерируйте `.items`, или используйте
`async for x in client(SomePages(...))`.

### Запись в журнал отключена по умолчанию
`ClientConfig.allow_mutations` по умолчанию `False`. Методы вроде `save_journal`
бросают `MutationsDisabled`, пока не установите `ClientConfig(allow_mutations=True)`.

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
