# pskovedu.parsers — HTML / HAR extraction layer

Stateless functions that turn raw HTML or HAR bytes into typed Python objects.
No network calls; no state. Every function is pure and independently testable.

## Modules

| Module | Public API | Purpose |
|---|---|---|
| `shell.py` | `parse_shell(html, url) -> ShellConfig` | Extract `window.REMOTING_API` + `window.X1_CONFIG` |
| `participant.py` | `parse_participant(html, url) -> ParticipantInfo` | `#participant[data-guid/role]` + `.one-participant` FIO/grade/school |
| `schedule.py` | `parse_schedule_globals(html) -> ScheduleGlobals` | `window.schedule_subject_guid/type` + role flags |
| `har.py` | `load_har_bootstrap(path) -> HarBootstrap` | Pull X1_SSO + ESIA cookies + shell globals from `.har` |
| `bundles.py` | `parse_bundle_urls(html) -> BundleUrls` | Versioned `<script>`/`<link>` build URLs |

## Key data contracts

- `ShellConfig` → `pskovedu.models.session` (re-exported from foundation layer)
- `ParticipantInfo` → `dataclass(slots=True, frozen=True)` — not an EduObject (no client binding needed)
- `ScheduleGlobals` → `dataclass(slots=True, frozen=True)`
- `HarBootstrap` → `dataclass(slots=True)` with `.x1_sso` property

## Error surface

- `HtmlParseError(what, url)` — from `pskovedu.exceptions` — raised when a required element is missing
- Missing optional elements (`.one-participant`, schedule globals) are logged as warnings and defaulted

## Design decisions

- Regex + `json.loads` over a full HTML parser — avoids BeautifulSoup dependency;
  the portal injects clean JSON objects (no JS expressions).
- Balanced-brace scanner (`_try_parse_json_block`) handles multi-line JSON objects
  without relying on trailing semicolons.
- HAR extraction collects cookies from both request and response sides of each
  entry (chronological last-write-wins for cookie updates).
