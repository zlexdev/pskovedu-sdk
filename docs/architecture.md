# Architecture

## How the real portal works

`one.pskovedu.ru` is a PHP/Yii application with a Sencha Ext.Direct front end.
There are **three** distinct ways it serves data, all observed in browser
captures:

### 1. Plain REST (JSON or HTML)

Some endpoints are ordinary REST URLs returning JSON or HTML:

```
GET /edv/index/diary/{participant_guid}?date=DD.MM.YYYY      → JSON  (diary)
GET /schedule/index/schedule/grade/{grade_guid}/{date}       → JSON  (schedule)
GET /edv/index/participant                                   → HTML  (diary participant page)
GET /                                                         → HTML  (app shell)
```

These are the **verified-working** part of the SDK.

### 2. Ext.Direct RPC (`POST /extjs/direct`)

Most data goes through a single generic RPC endpoint. The JS defines exactly one
action with one method:

```js
RemotingProvider({ url: "/extjs/direct", actions: { X1API: [{ direct: { len: 1 } }] } })
```

The real envelope is **nested** — `X1API.direct` wraps a `{service, method,
params, ctx}` call object:

```json
{
  "action": "X1API",
  "method": "direct",
  "data": [{ "service": "utility", "method": "getusernotifications", "params": [], "ctx": {} }],
  "type": "rpc",
  "tid": 1
}
```

Responses are arrays of X1 ORM records (`SYS_GUID`, `SYS_STATE`, `SYS_USER`, …).

> The SDK's current `ExtDirectProtocol` builds a **different, flat** envelope, so
> these calls don't work yet — see
> [Known issues](known-issues.md#ext-direct--x1-envelope-is-wrong).

### 3. SSE (QR auth)

The QR/ESIA login flow uses Server-Sent Events through the `qr-delegate`
subsystem, plus a session-token exchange at `POST sfd.gosuslugi.ru/session`.

### User identity

There is **no `/session` profile endpoint** on the portal. The logged-in user's
identity lives in the `X1_CONFIG.meta.au` JS global injected into the shell HTML
(the app reads it as `X1.user`). The SDK parses it into `ShellConfig.role_meta`
via `client.get_shell()`.

## How the SDK is layered

```
Client (facade)                    flat helpers: get_diary(), watch_marks(), …
  └─ method objects                typed Pydantic request bundles (one per endpoint)
       └─ Protocol                 REST | ExtDirect | SSE | X1 — picks the wire format
            └─ BaseSession         the make_request funnel (auth → build → send → decode)
                 └─ HttpxSession   httpx.AsyncClient transport (injectable: proxy, TLS…)
```

Cross-cutting concerns wrap the funnel:

- **AuthManager** — injects `X1_SSO` (and JWT, for the QR flow) before each request.
- **RetryPolicy** — retries idempotent requests on transient failures.
- **CircuitBreaker** — trips per host (gosuslugi infra by default).
- **HostRateLimiter** — token-bucket per host.
- **BaseStorage** — cookie + watcher-snapshot persistence.

### The reactive layer sits *above* the client

```
Watcher[T]  poll() ──▶ StateDiffer.compute() ──▶ Delta ──▶ to_events() ──▶ ReactiveEvent
   │
   ├─ MarkWatcher / HomeworkWatcher / ScheduleWatcher / ReceptionWatcher / NotificationWatcher
   ├─ Dispatcher   merges N watcher streams into one
   └─ LessonBell   local, network-free schedule → bell events
```

Watchers consume the client's read methods; they never touch the transport
directly. See [Reactive layer](reactive.md).
