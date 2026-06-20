# methods/

Typed endpoint classes for the pskovedu SDK (aiogram-style method-as-class).

## Pattern

Every API endpoint is a `BaseMethod[T]` subclass.  The instance is the request
bundle; awaiting it executes through the bound client.

```python
shell = await client(GetShell())        # universal __call__
shell = await client.get_shell()       # flat Client sugar
```

## Base classes

- `_base.py` — `BaseMethod[T]`: `__init_subclass__` (validate + resolve_returning),
  `as_()`, `emit()`, `__await__`. ClassVars: `__host__`, `__returning__`,
  `__protocol__`, `__breaker_path__`, REST vars, ExtDirect vars, X1 vars, SSE vars.
- `_bases.py` — per-protocol bases that pin `__protocol__` once:
  - `RestMethod[T]` → `RestProtocol`
  - `ExtDirectMethod[T]` → `ExtDirectProtocol` (lazy import)
  - `X1Method[T]` → `X1Protocol` (lazy import)
  - `SseSubscription[T]` → `SseProtocol` (lazy import, `[sse]` extra)

## Domain files (spine — T1–T9 scope)

- `session.py` — `GetShell` → `_ShellHtml` (HtmlParsed); identity lives in the
  parsed `ShellConfig.role_meta` (`X1_CONFIG.meta.au`), not a `/session` endpoint

## Domain files (downstream agents)

`schedule.py`, `diary.py`, `reports.py`, `journal.py`, `scheduler.py`,
`monitoring.py`, `reception.py`, `x1.py`, `avatar.py`, `qr.py`.

## Domain files (X2/X3 additions)

### `reports_print.py` — print/monitor reports

Extends the reports surface with two download formats driven by `ReportForm`.

```python
class GetReportXls(_ReportBase, RestMethod[bytes]):
    """Download a report as a raw Excel file.
    Adds ?format=xls to the query string; returns raw bytes.
    """
    form: ReportForm
    params: dict[str, str] = {}   # arbitrary extra query-string pairs

class GetReportHtml(_ReportBase, RestMethod[_ReportHtml]):
    """Fetch a report rendered as HTML.
    Returns _ReportHtml(raw_html=...) — no JSON parsing.
    """
    form: ReportForm
    params: dict[str, str] = {}
```

`_ReportBase` resolves `{base}/{tail}` from `REPORT_FORM_META[form]` and
serialises `params` as flat query-string pairs via a custom `model_serializer`.
`GetReportXls` injects `format=xls` on top.  The bytes passthrough path in
`RestProtocol.decode_response` is triggered by the `bytes` return type.

`ReportForm` is a `StrEnum` in `pskovedu.models.enums`; `REPORT_FORM_META`
maps each member to the `(base, tail)` URL segments.

**Client sugar:** `await client.get_report(form, fmt=None, **params)` —
returns `bytes` when `fmt="xls"` or `fmt` is `None` (default), returns
`_ReportHtml` when `fmt="html"`.

### `eje.py` — EJE read endpoints

Five read-only GET endpoints into the EJE (electronic grade journal) module.
All share `_Eje(RestMethod[EjeResult])` which pins `__http_method__ = "GET"`.

| Class | REST path | Purpose |
|---|---|---|
| `EjeHomework` | `GET /eje/homework/teacher/` | Homework data |
| `EjeJournalPlanner` | `GET /eje/journal-planner/journal/` | Journal planner |
| `EjeParticipants` | `GET /eje/participants-list/index/` | Participants list |
| `EjeTopics` | `GET /eje/topics/index/` | Topics index |
| `EjeIntegrations` | `GET /eje/integrations/list/` | Integrations list |

All return `EjeResult` (shape: unverified — marked `# unverified shape` in
source pending live endpoint confirmation).

**Client sugar:** `await client.eje_homework()`, `eje_journal_planner()`,
`eje_participants()`, `eje_topics()`, `eje_integrations()`.

### `util.py` — auth utilities

```python
class CheckAuth(RestMethod[AuthCheck]):
    """Validate a session token.
    REST: GET one.pskovedu.ru/common-api/check-auth?value=<token>
    """
    value: str

class GetOAuthConfig(RestMethod[OAuthConfig]):
    """Fetch the ESIA OAuth2 / QR configuration object (~40 fields).
    REST: GET esia.gosuslugi.ru/aas/oauth2/config  (Host.ESIA)
    No parameters.
    """
```

**Client sugar:** `await client.check_auth(token)`, `await client.get_oauth_config()`.

### `qr.py` — QR authentication

Three classes that implement the ESIA QR login flow.

```python
class GenerateQr(RestMethod[QrGenerate]):
    """Mint a new QR session.
    REST: POST esia.gosuslugi.ru/qr-delegate/qr/generate  (empty body)
    Returns QrGenerate carrying the QR image URL and a session uuid.
    """

class QrAuthEvent(SseSubscription[None]):
    """SSE subscription for QR-code authentication.
    REST: GET esia.gosuslugi.ru/qr-delegate/qr/subscribe/{uuid}
    Yields SseEvent objects; terminal event: SseEvent.QR_AUTH_CONFIRMED.
    """
    uuid: Uuid

class ConfirmQr(RestMethod[QrConfirm]):
    """Exchange a one-time QR auth code for an X1 SSO token.
    REST: POST esia.gosuslugi.ru/qr-delegate/qr/confirm  body: {"code": <str>}
    Returns QrConfirm carrying the X1_SSO cookie value.
    """
    code: str

SubscribeQr = QrAuthEvent   # short alias for method-style call
```

See `auth/_MODULE.md` § QR login flow for the end-to-end sequence.

## Naming convention

- Class name = PascalCase verb+noun: `GetDiary`, `SaveJournal`, `DeleteJournal`.
- File = domain noun: `diary.py`, `journal.py`.
- Required docstring on every public method-class.
- Internal helpers are prefixed with `_` (`_ReportBase`, `_ReportHtml`, `_Eje`).
