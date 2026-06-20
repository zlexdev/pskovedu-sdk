# sessions/

HTTP session layer: the `make_request` funnel and its concrete httpx backend.

## base.py — BaseSession (ABC)

`make_request(client, method) -> T` — THE funnel:
1. Auth ensure (``auth_manager.ensure(client)`` or minimal cookie injection).
2. ``protocol.build_request(method, config, host_url)`` → ``PreparedRequest``.
3. Optional ``rate_limiter.acquire(host_url)``.
4. Optional ``breaker.allow(host, path)`` → raises ``BreakerOpen``.
5. ``_send_with_retry(prepared, config, method, protocol)`` → ``RawResponse``.
   - Retry loop: ``RetryPolicy.is_retryable`` gates retries; ``RetryPolicy.wait``
     sleeps backoff+jitter between attempts.
   - 401 → ``AuthExpiredError`` (caller intercepts for refresh+retry-once).
6. ``protocol.decode_response(method, raw)`` → typed result.
7. If result is ``EduObject``: ``result.as_(client)`` (recursive bind).

`open_stream(client, method) -> EventStream` — SSE sibling of the funnel:
shares the auth + encode head (`_prepare`) then, instead of reading one
`RawResponse`, opens a long-lived streaming response (`_open_sse`), maps the
handshake status, and wraps it in `transport.sse.SseStream`. Iterating the
returned `EventStream` yields `SseEvent`s until the method's `__terminal_event__`;
the connection closes when iteration ends or the consumer breaks early.

`_resolve_host(config, method)` — `__host__` key → base URL (Host enum or str).
`_prepare(client, method, protocol, config, host_url)` — shared head of
`make_request` + `open_stream`: auth ensure → `build_request` → cookie inject.
`_inject_cookies(prepared, cookies)` — minimal pre-auth cookie path.
`_map_status(status, url)` — maps HTTP codes to typed `EduError` subclasses.
`_send(prepared, config)` — abstract; implemented by `HttpxSession`.
`_open_sse(prepared)` — abstract; opens a streaming response for SSE.
`close()` — abstract; closes transport.

## httpx_session.py — HttpxSession

Concrete `BaseSession` backed by `httpx.AsyncClient`.
- Shared connection pool across requests.
- JSON body serialised to bytes before send.
- Cookie jars managed by auth layer (injected via `_inject_cookies` path).
- `_open_sse(prepared)` — `send(..., stream=True)`; `SseStream` owns `aclose()`.
- `close()` closes the `AsyncClient` if owned.
