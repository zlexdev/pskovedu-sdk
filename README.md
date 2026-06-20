# pskovedu-sdk

Асинхронный Python SDK для электронного журнала **one.pskovedu.ru** — портала образования Псковской области.

> [English version →](README.en.md)

---

## Возможности

- **Авторизация** — вход по cookie `X1_SSO`, QR-код через Госуслуги (ESIA), ESIA OAuth-поток
- **Типизированный API** — каждый эндпоинт — датакласс-метод с аннотацией возврата; `await client(Method(...))` и `async for`
- **Протоколы** — REST, Ext.Direct RPC (`POST /extjs/direct`), SSE, HTML-парсинг
- **Реактивные наблюдатели** — `async for event in watcher.events()` для оценок, домашних заданий, расписания, уведомлений, приёмной
- **`Dispatcher`** — объединяет несколько наблюдателей в один поток событий
- **Звонки** — `LessonBell` считает расписание уроков локально, генерирует `Bell`, `LessonStarting`, `LessonEnded`
- **Хранилище** — `MemoryStorage` / `FileStorage`; снимки персистируются между перезапусками
- **Circuit breaker** и **rate limiter** встроены в транспорт
- **py.typed** — полная поддержка mypy / pyright в strict-режиме

---

## Требования

Python **3.12+**. Зависимости: `httpx`, `pydantic`, `pydantic-settings`, `structlog`, `selectolax`, `anyio`.

---

## Установка

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git"
```

В `requirements.txt`:

```
pskovedu @ git+https://github.com/zlexdev/pskovedu-sdk.git
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
    print(session.display_name)
```

### Дневник и оценки

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

### Реактивные наблюдатели

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
                print("Новая оценка:", m)
            case NewNotification(notification=n):
                print("Уведомление:", n.title)
```

### Звонки уроков

```python
from pskovedu.reactive import LessonBell

schedule_day = await client.get_schedule_day(...)
bell = LessonBell(schedule_day)

async for event in bell.events():
    print(event)  # LessonStarting | Bell | LessonEnded
```

---

## Структура пакета

```
pskovedu/
├── client.py          # Client — единственная точка входа
├── methods/           # Типизированные классы-методы (один файл на домен)
├── models/            # Pydantic-модели ответов
├── reactive/          # Наблюдатели, события, Dispatcher, LessonBell
├── auth/              # AuthManager, QR/ESIA/cookie-солверы
├── protocol/          # REST, ExtDirect, SSE, X1
├── transport/         # Retry, SSE-стриминг
├── storage/           # MemoryStorage, FileStorage
├── parsers/           # HTML-парсеры (shell, participant, schedule, bundles)
└── config.py          # ClientConfig (pydantic-settings)
```

---

## Конфигурация

```python
from pskovedu.config import ClientConfig

config = ClientConfig(
    request_timeout_s=30.0,
    poll_interval_s=60.0,
)
```

Все параметры доступны через переменные окружения с префиксом `PSKOVEDU_`:

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_POLL_INTERVAL_S=60
```

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
