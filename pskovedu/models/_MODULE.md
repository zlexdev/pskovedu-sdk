# models/

Per-domain Pydantic v2 DTOs for the pskovedu SDK.

## Base

- `_base.py` — `EduObject` (bound-model base with `as_()` recursive bind, `_require_client()`, `client` property) and `HtmlParsed` marker.

## Value types (`common.py`)

- `Guid` — `Annotated[str, AfterValidator(validate_guid)]` — 30–40 hex chars, optional braces.
- `Uuid` — `Annotated[str, AfterValidator(validate_uuid)]` — RFC 4122 UUID string.
- `MarkWeight` — `Annotated[Decimal, ...]` — never float.
- `DateWindow(EduObject)` — `start: date`, `end: date`.
- `EduPage[T](EduObject)` — `items: list[T]`.
- `HomeworkMode(StrEnum)` — `CURRENT | PREVIOUS | ALL`.
- `ReceptionType(StrEnum)` — `PARENT | STUDENT | ALL`.

## Session (`session.py`)

- `Session(EduObject)` — JWT fields: `session_id`, `exp`, `iat` (UTC datetime), `jti` (UUID); `expired` property.
- `RoleMeta(EduObject)` — `X1_CONFIG.meta.au` fields (X1 wire names, aliased).
- `X1ModelRef(EduObject)` — single `meta.models` entry: `sys_guid`, `name`, `alias`.
- `ShellConfig(EduObject)` — bootstrap result: `remoting_api_url`, `remoting_actions`, `role_meta`, `models`; `model_guid(name)` lookup.

## Downstream files (written by other agents)

`schedule.py`, `diary.py`, `reports.py`, `journal.py`, `monitoring.py`,
`reception.py`, `x1.py`, `esia.py`, `notifications.py`.

## Conventions

- `ConfigDict(populate_by_name=True, strict=True)` on every model.
- `StrEnum` for all enums; wire camelCase → Python snake_case via `Field(alias=...)`.
- `Decimal` for mark weights; UTC `datetime` with tzinfo everywhere.
- No `model.dict()` — always `model.model_dump()`.
