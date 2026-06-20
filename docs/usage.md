# Usage

## Two calling styles

### 1. Flat helpers (recommended)

`Client` exposes a typed async method per endpoint:

```python
week    = await client.get_diary(participant_guid)
report  = await client.get_marks_report(participant_guid, with_dates=True)
day     = await client.get_schedule(grade_guid)
```

### 2. Method objects

Every endpoint is also a Pydantic "method object" you pass to `client(...)`.
The flat helpers are thin wrappers over these:

```python
from pskovedu.methods.diary import GetDiary, GetMarksReport

week  = await client(GetDiary(participant_guid="..."))
marks = await client(GetMarksReport(participant_guid="...", with_dates=True))
```

Protocol dispatch (REST / Ext.Direct / SSE) is automatic — you never choose it.

## Pagination

Paginated endpoints return a `PageIterator` you drive with `async for`:

```python
from datetime import date
from pskovedu.methods.diary import DiaryPages

# Flat helper:
async for entry in await client.iter_diary(guid, start=date(2025, 9, 1)):
    print(entry.subject, entry.marks)

# Or via method object directly (auto-fetches pages):
async for entry in client(DiaryPages(participant_guid=guid, start=date(2025, 9, 1))):
    print(entry)
```

> Methods that return `EduPage[T]` (e.g. `get_grades()`) are **single-page**
> results — iterate their `.items`, not the page object:
> ```python
> grades = await client.get_grades()
> for g in grades.items:
>     ...
> ```

## Endpoint reference

Legend: ✅ verified working · ⚠️ affected by the
[Ext.Direct envelope bug](known-issues.md#ext-direct--x1-envelope-is-wrong)
(likely non-functional until fixed) · ❓ flow modeled, not end-to-end verified.

### Diary & marks (REST ✅)

```python
week    = await client.get_diary(guid, date="15.06.2026")        # DiaryWeek
report  = await client.get_marks_report(guid, with_dates=True)   # MarksReport
xls     = await client.get_diary_xls(guid)                       # bytes (XLS)
pages   = await client.iter_diary(guid, start=..., end=...)      # PageIterator[DiaryEntry]
```

- `date` is a `"DD.MM.YYYY"` string; omit for the current week.

### Schedule (REST ✅)

```python
day   = await client.get_schedule(grade_guid, date="17.06.2026")  # ScheduleDay
day   = await client.get_current_schedule()                       # ScheduleDay
pages = await client.iter_schedule(grade_guid, start=..., end=...) # PageIterator[ScheduleDay]
```

### Reference data (Ext.Direct ⚠️)

```python
await client.get_grades()        # EduPage[Grade]
await client.get_years()         # EduPage[Year]
await client.get_periods()       # EduPage[Period]
await client.get_teachers()      # EduPage[Teacher]
await client.get_grade_types()   # EduPage[GradeType]
await client.get_mark_types()    # EduPage[MarkType]
await client.get_participants()  # EduPage[ParticipantRef]
```

### Journals (Ext.Direct ⚠️)

```python
await client.get_journals()                  # EduPage[JournalRef]
await client.get_journal(journal_guid)       # Journal
await client.read_journal(grades=[...])      # EduPage[Journal]
await client.save_journal(...)               # mutation — see note below
await client.delete_journal(journal_guid)    # mutation
```

> **Journal writes are opt-in.** `save_journal` / `delete_journal` raise
> `MutationsDisabled` unless you build the client with
> `ClientConfig(allow_mutations=True)`. See
> [Gotchas](gotchas.md#journal-writes-are-opt-in).

### Notifications & reception (Ext.Direct ⚠️)

```python
notes = await client.get_user_notifications(limit=20)            # EduPage[UserNotification]
for n in notes.items:
    print(n.title)

slots = await client.get_reception("01.09.2025", "30.09.2025")   # EduPage[ReceptionSlot]
for s in slots.items:
    print(s)
```

### Reports & avatars (REST ✅)

```python
from pskovedu.models.enums import ReportForm, ReportFmt

xls  = await client.get_report(ReportForm.SOME_FORM, fmt=ReportFmt.XLS)  # bytes
html = await client.get_report(ReportForm.SOME_FORM)                     # _ReportHtml
png  = await client.get_avatar(uuid)                                     # bytes
```

### Raw X1 ORM access (Ext.Direct ⚠️)

For models without a dedicated helper:

```python
page = await client.x1_query("JOURNAL", where={...}, limit=50)  # X1PageModel
rec  = await client.x1_get("JOURNAL", guid)                     # X1RecordModel
```

### EJE module (REST ✅)

```python
await client.eje_homework()          # EjeResult
await client.eje_journal_planner()   # EjeResult
await client.eje_participants()      # EjeResult
await client.eje_topics()            # EjeResult
await client.eje_integrations()      # EjeResult
```

### Auth utilities

```python
cfg  = await client.get_oauth_config()   # OAuthConfig (REST)
chk  = await client.check_auth(token)    # AuthCheck
```

## Synchronous wrapper

For scripts/REPL without `async`/`await`, use `SyncClient` — it runs a private
event loop:

```python
from pskovedu.sync import SyncClient
from pskovedu.methods.reports import GetGrades

with SyncClient.from_cookie(x1_sso="...") as c:
    shell  = c.get_shell()
    grades = c(GetGrades())
```

## Errors

All SDK errors derive from `EduError` (in `pskovedu.exceptions`). Common ones:

| Exception | When |
|---|---|
| `AuthExpiredError` | HTTP 401 — session expired / not authenticated |
| `ForbiddenError` | HTTP 403 |
| `NotFoundError` | HTTP 404 |
| `ServerError` | HTTP 5xx |
| `ProtocolError` | response couldn't be decoded into the expected shape |
| `MutationsDisabled` | a write method called without `allow_mutations=True` |
| `AuthError` | QR/ESIA auth flow failure (timeout, errors) |
