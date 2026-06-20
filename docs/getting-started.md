# Getting started

## Install

Not on PyPI — install from GitHub:

```bash
pip install "git+https://github.com/zlexdev/pskovedu-sdk.git"
```

Requires **Python 3.12+**. Dependencies (`httpx`, `pydantic`, `pydantic-settings`,
`structlog`, `selectolax`, `anyio`) install automatically.

## Build a client

The client is async-first. The two ways to get an authenticated client are the
`X1_SSO` cookie (fastest) or the QR/ESIA login flow — see
[Authentication](authentication.md) for both.

```python
import asyncio
from pskovedu import Client

async def main() -> None:
    async with Client.from_cookie(x1_sso="YOUR_X1_SSO") as client:
        shell = await client.get_shell()
        # The logged-in user's identity is in shell.role_meta (X1_CONFIG.meta.au).
        print(shell.role_meta.name if shell.role_meta else "authenticated")

asyncio.run(main())
```

> **Why `async with`?** The context manager restores persisted cookies on enter
> and saves state + closes the HTTP transport on exit. You *can* skip it for a
> one-shot script, but then nothing is persisted and the connection pool is not
> closed cleanly. See [Gotchas](gotchas.md#async-with-client-is-strongly-recommended).

## Your first real data call

`get_diary` is a plain REST endpoint and is **verified working** against captures:

```python
async with Client.from_cookie(x1_sso="YOUR_X1_SSO") as client:
    # participant_guid identifies a student (a parent account may have several).
    week = await client.get_diary("B22275F0B52B8A7663899CA8BF970212")
    for entry in week.entries:
        print(entry.subject, entry.marks)
```

> Getting a `participant_guid`: it comes from `get_participants()`, **but** that
> call goes through the Ext.Direct protocol which currently has a
> [known envelope bug](known-issues.md#ext-direct--x1-envelope-is-wrong). Until
> that's fixed, read the GUID from the diary participant page (`#participant[data-guid]`)
> or a browser session.

## Where to next

- [Authentication](authentication.md) — how to obtain `X1_SSO`, or use QR login
- [Usage](usage.md) — every endpoint family with examples
- [Reactive layer](reactive.md) — live event streams (marks, homework, schedule…)
- [Known issues & status](known-issues.md) — what actually works today
