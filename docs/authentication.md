# Authentication

## How the portal authenticates

`one.pskovedu.ru` is a PHP/Yii application fronted by an SSO layer. An
authenticated browser session carries **two** cookies:

| Cookie | Role |
|---|---|
| `X1_SSO` | Primary SSO master cookie — this is what authenticates API calls |
| `PHPSESSID` | PHP session cookie — secondary, set alongside `X1_SSO` |

> **`PHPSESSID` alone is not enough.** A request with only `PHPSESSID` is treated
> as unauthenticated and redirects to `/auth/login`. The SDK authenticates with
> `X1_SSO`. (This was confirmed by live testing — see
> [Known issues](known-issues.md).)

There is **no portal `/session` profile endpoint.** The logged-in user's identity
is injected into the app shell as the `X1_CONFIG.meta.au` JS global, exposed by the
SDK as `ShellConfig.role_meta` via `client.get_shell()`.

## Option 1 — cookie auth (recommended)

Grab `X1_SSO` from a logged-in browser:

1. Log in at `https://one.pskovedu.ru`.
2. DevTools → **Application** → **Cookies** → `https://one.pskovedu.ru`.
3. Copy the value of `X1_SSO`.

```python
from pskovedu import Client

async with Client.from_cookie(x1_sso="PASTE_X1_SSO_HERE") as client:
    shell = await client.get_shell()
    print(shell.role_meta.name if shell.role_meta else "authenticated")
```

`from_cookie` injects the cookie into every outbound request immediately — no
login round-trip needed.

### Persisting the session

Pass `session_file` to persist cookies between runs (uses `FileStorage`):

```python
async with Client.from_cookie(x1_sso="...", session_file="session.json") as client:
    ...
# Cookies are saved on exit and restored on the next run's __aenter__.
```

## Option 2 — QR login via Gosuslugi (ESIA)

Drives the full QR delegate flow over SSE (generate → display → confirm →
cookie injection), then bootstraps the shell.

```python
from pskovedu import Client

async def show_qr(url: str) -> None:
    # Render or print — the user scans it in the Gosuslugi mobile app.
    print("Scan in Gosuslugi:", url)

async with Client() as client:
    shell = await client.login_with_qr(display_cb=show_qr)   # blocks until confirmed
    print("Logged in as:", shell.role_meta.name if shell.role_meta else "?")
```

- `display_cb` may be **sync or async** — both are awaited correctly.
  Its type is `Callable[[str], None | Coroutine[Any, Any, None]]`.
- `login_with_qr()` returns a `ShellConfig` (the bootstrapped shell), **not** a
  profile object.

> **QR login times out after 120 seconds** of no scan, or after 3 consecutive
> `qr-error` SSE events — it raises `AuthError`. See
> [Gotchas](gotchas.md#qr-login-times-out-after-120-seconds).

## Token expiry

`X1_SSO` can expire mid-run. When it does, the next call raises
`AuthExpiredError` (HTTP 401). **There is no silent re-auth loop** — you must
re-authenticate (`from_cookie` with a fresh cookie, or `login_with_qr` again).

```python
from pskovedu.exceptions import AuthExpiredError

try:
    week = await client.get_diary(guid)
except AuthExpiredError:
    # cookie died — re-login and retry yourself
    ...
```

Wrap long-running watchers in your own reconnect logic around `AuthExpiredError`
(see [Reactive layer](reactive.md#handling-auth-expiry-in-watchers)).

## Note on the SFD session token

You may see references to a `Session` JWT in the codebase. That is the
**QR/ESIA session token** from `POST sfd.gosuslugi.ru/session`
(`{"token": "<JWT>"}`), used internally during QR auth. Its payload is only
`{sessionId, exp, iat, jti}` — it is a session token, **not** a user profile.
You normally never touch it directly.
