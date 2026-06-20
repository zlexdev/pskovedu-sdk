# Gotchas

Pitfalls that will bite you, each with the fix.

## Cold start emits the entire existing dataset

A watcher starts with an empty snapshot, so the **first** poll classifies every
current mark / homework / slot as new and fires one event per item.

**Fix:** pass a `FileStorage` whose snapshot persists between runs — after the
first run, only genuine changes are emitted.

```python
from pskovedu.storage import FileStorage
async for ev in client.watch_marks(participant_guid="...", storage=FileStorage("state.json")):
    ...
```

## `X1_SSO` expiry is not auto-recovered

When the session cookie expires mid-run, the next call raises `AuthExpiredError`.
There is no silent re-auth loop.

**Fix:** catch `AuthExpiredError`, re-authenticate, and retry. For watchers, wrap
the whole `async for` (see [Reactive › auth expiry](reactive.md#handling-auth-expiry-in-watchers)).

## `PHPSESSID` alone does not authenticate

The portal sets both `X1_SSO` and `PHPSESSID`. A request carrying only
`PHPSESSID` is treated as logged-out and redirects to `/auth/login`.

**Fix:** authenticate with `X1_SSO` (that's what `from_cookie` uses).

## `events()` is an async generator — never `await` it

`watcher.events()`, `Dispatcher.events()`, and `LessonBell.events()` are async
generators.

```python
async for event in watcher.events():   # ✅
    ...
await watcher.events()                  # ❌ wrong — there's no coroutine to await
```

## Paginated getters return `EduPage`, not a list

`get_user_notifications()`, `get_reception()`, `get_grades()`, `get_participants()`,
etc. return `EduPage[T]`.

```python
page = await client.get_grades()
for g in page.items:   # ✅ iterate .items
    ...
```

For multi-page streams use the `iter_*` helpers or `async for x in client(SomePages(...))`.

## Dispatcher silently drops a failing watcher, not all watchers

If one watcher raises a non-`CancelledError` exception, it is logged and removed;
the remaining watchers keep running. Don't assume the whole dispatcher stopped —
check your logs.

## LessonBell — keep your `now` callable tz-consistent

Portal lesson times are local-naive. The default `now` returns a naive local
datetime to match. Passing a tz-aware `now` while other comparisons stay naive
raises `TypeError: can't subtract offset-naive and offset-aware datetimes`.

**Fix:** pick one frame. Either keep everything naive (default), or pass a
tz-aware `now` *and* keep all your own datetime handling tz-aware.

## `FileStorage` is single-process only

Its in-process `asyncio.Lock` is safe across async tasks in one process but does
**not** lock across OS processes. Two processes pointing at the same JSON file
clobber each other.

**Fix:** for multi-process deployments, implement `BaseStorage` over Redis or
another shared store.

## `async with Client(...)` is strongly recommended

Without the context manager, persisted cookies are not loaded/saved and the HTTP
transport is not closed cleanly.

```python
async with Client.from_cookie(x1_sso="...") as client:   # ✅ for anything long-lived
    ...
```

A bare `Client.from_cookie(...)` works for a one-shot call (the cookie is injected
immediately), but you lose persistence and clean shutdown.

## QR login times out after 120 seconds

`login_with_qr()` raises `AuthError` if no scan is detected within 120 s, or after
3 consecutive `qr-error` SSE events.

## Journal writes are opt-in

`ClientConfig.allow_mutations` defaults to `False`; `save_journal` /
`delete_journal` raise `MutationsDisabled` before any network call.

**Fix:** `Client(config=ClientConfig(allow_mutations=True))`.

## Ext.Direct / X1 endpoints may not work yet

Reference data, journals, notifications, reception, and raw X1 queries go through
the Ext.Direct protocol, which currently builds the wrong envelope. See
[Known issues](known-issues.md#ext-direct--x1-envelope-is-wrong). Prefer the
REST endpoints (diary, schedule) until that's fixed.
