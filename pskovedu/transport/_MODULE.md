# transport/

HTTP transport layer for the pskovedu SDK.

## Files

- `retry.py` — `RetryPolicy`: exponential backoff + jitter; reads
  `protocol.is_idempotent(method)` to gate retries on non-idempotent calls.
  Retryable statuses: 429, 500, 502, 503, 504.
- `sse.py` — (downstream) SSE line-parser → `EventStream[T]` async iterator.
  Required by the `[sse]` extra.
- `proxy.py` — (deferred, FP-7) `BaseProxyTransport` stub.

## RetryPolicy

```python
RetryPolicy(max_retries=2, base_delay_s=1.0, max_delay_s=30.0, jitter=True)
```

`is_retryable(method, protocol, status, exc)` → bool
`wait(attempt)` → coroutine (sleeps backoff duration)
