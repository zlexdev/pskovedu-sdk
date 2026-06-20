# pskovedu.auth — authentication layer

Owns all credential state: cookies, JWT, and the three login paths.
``BaseSession.make_request`` calls ``auth_manager.ensure(client)`` before every
request — this is the only call site for cookie/JWT injection.

## Modules

| Module | Public API | Purpose |
|---|---|---|
| `cookies.py` | `CrossHostCookieJar` | Single jar spanning `*.pskovedu.ru` + `*.gosuslugi.ru`; SameSite=None tolerant |
| `session_token.py` | `SessionToken` | Decode JWT once, cache claims, `needs_refresh(skew_s)` |
| `store.py` | `TokenStore` | Persist token + jar via `BaseStorage`; JSON-serialisable format |
| `esia.py` | `extract_client_secret(location_url)`, `replay_oauth(transport, login, password)` | F001 parse + 8-step ESIA headless replay |
| `manager.py` | `AuthManager`, `AuthState` | State machine UNAUTH→COOKIE_ONLY→SESSIONED; `ensure(client)`, `login_with_*` |
| `solvers/base.py` | `ChallengeSolver` ABC | Pluggable challenge resolver contract |
| `solvers/qr.py` | `QrSolver` | Drive SSE QR stream → `SubscribeQr` + `ConfirmQr` methods |

## State machine

```
UNAUTH ──login_with_*──► COOKIE_ONLY ──GET /session──► SESSIONED
                                                             │
                                              (JWT refresh on exp-skew via ensure())
```

## ensure() contract

```python
# Called by BaseSession.make_request before every request:
await auth_manager.ensure(client)
```

- `UNAUTH`: no-op (request proceeds without auth)
- `COOKIE_ONLY`: injects jar into `client._cookies`; calls `GET /session` to upgrade
- `SESSIONED`: injects jar + `Authorization: Bearer <jwt>`; refreshes if `needs_refresh(skew_s)`

## Security notes

- `client_secret` is never hardcoded — extracted at runtime from 302 Location (F001)
- `X1_SSO` and JWT are redacted in all structlog output
- ESIA replay is marked `experimental`; own-account use only
- `CrossHostCookieJar.for_url()` only forwards cookies to `_TRUSTED_DOMAINS`

## QR login flow

`AuthManager.login_with_qr` drives the full ESIA QR auth sequence:

```
GenerateQr (POST)
    └─► receive QrGenerate { image_url, uuid }
            │
            ▼  display image_url to user (via display_cb)
QrAuthEvent SSE stream open_stream(uuid)
    └─► yield SseEvent objects until SseEvent.QR_AUTH_CONFIRMED
            │
            ▼
ConfirmQr (POST, body: {"code": one_time_code})
    └─► receive QrConfirm { x1_sso: "<cookie>" }
            │
            ▼
AuthState → COOKIE_ONLY (X1_SSO injected into CrossHostCookieJar)
    └─► GET /session → SESSIONED
```

### `QrSolver` (`solvers/qr.py`)

Implements `ChallengeSolver` ABC.  Drives the SSE stream via `SubscribeQr` /
`ConfirmQr` method classes (late-imported to avoid circular imports).

```python
class QrSolver(ChallengeSolver):
    async def solve(self, client: Client, display_cb: DisplayCallback) -> str:
        ...
    # display_cb receives the QR image URL for the caller to render/show.
    # Returns the X1_SSO cookie string on success.
```

**Client sugar:** `await client.login_with_qr(display_cb)` — constructs a
`QrSolver`, calls `AuthManager.login_with_*`, and transitions the client to
`SESSIONED` in one call.

## Dependencies (sibling agents)

- `pskovedu.methods.qr.SubscribeQr` / `ConfirmQr` — imported late in `QrSolver`
- `pskovedu.protocol.sse` — consumed by the methods layer, not directly by auth

## Out of scope

- session mint: documented-not-implemented, lib auths via X1_SSO (see `.plans/pskovedu-endpoints-watchers/_research/session-mint-findings.md`)
