# Configuration

## ClientConfig

`ClientConfig` is a `pydantic-settings` model. Construct it explicitly or let the
client use defaults:

```python
from pskovedu.config import ClientConfig
from pskovedu import Client

config = ClientConfig(
    request_timeout_s=30.0,
    retries=2,
    rate_limit_rps=4.0,
)

async with Client(config=config) as client:
    ...
```

### Fields

| Field | Default | Meaning |
|---|---|---|
| `hosts` | portal/passport/ESIA/SFD map | logical host → base URL (override for a test proxy) |
| `jwt_refresh_skew_s` | `300` | seconds before JWT expiry to refresh proactively |
| `allow_mutations` | `False` | when `False`, journal write methods raise `MutationsDisabled` |
| `cache_ttl_s` | `3600` | reference-data cache TTL; `0` disables |
| `rate_limit_rps` | `4.0` | per-host request cap (req/s); `None` disables |
| `breaker_hosts` | gosuslugi infra | hosts with the circuit breaker enabled |
| `request_timeout_s` | `30.0` | per-request network timeout |
| `retries` | `2` | retries for idempotent requests on transient failures |
| `user_agent` | browser UA | `User-Agent` header on every request |

## Environment variables

`ClientConfig` reads env vars with the `PSKOVEDU_` prefix (field name uppercased):

```env
PSKOVEDU_REQUEST_TIMEOUT_S=30
PSKOVEDU_RETRIES=2
PSKOVEDU_RATE_LIMIT_RPS=4.0
PSKOVEDU_ALLOW_MUTATIONS=false
```

```python
config = ClientConfig()   # picks up PSKOVEDU_* from the environment
```

## Using a proxy

The HTTP transport is injectable. Build an `httpx.AsyncClient` with a proxy and
hand it to `HttpxSession`, then pass that as the client's `session`:

```python
import httpx
from pskovedu import Client
from pskovedu.sessions.httpx_session import HttpxSession

http = httpx.AsyncClient(
    proxy="http://user:pass@host:port",
    follow_redirects=True,
    timeout=httpx.Timeout(30.0),
)

client = Client(session=HttpxSession(client=http))
client._cookies["X1_SSO"] = "..."   # or use Client.from_cookie + custom session

# remember to close the proxy client when done (or use async with on the Client)
```

> This pattern (custom `httpx.AsyncClient` → `HttpxSession(client=...)`) is the
> supported way to control proxies, TLS, connection limits, and timeouts. It was
> used to live-test the SDK through an HTTP proxy.

## Custom storage

Cookies and watcher snapshots persist through a `BaseStorage`. Built-ins:

```python
from pskovedu.storage import MemoryStorage, FileStorage

Client(storage=MemoryStorage())            # default — nothing persists
Client(storage=FileStorage("state.json"))  # JSON file (single process only)
```

`FileStorage` is safe across async tasks in one process but **not** across OS
processes — see [Gotchas](gotchas.md#filestorage-is-single-process-only). For
multi-process deployments, implement `BaseStorage` over Redis or similar.

## Multi-account key namespacing

Share one storage backend across accounts by namespacing keys:

```python
Client.from_cookie(
    x1_sso="...",
    key_builder=lambda k: f"account_42_{k}",
)
```
