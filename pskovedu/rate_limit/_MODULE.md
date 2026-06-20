# pskovedu.rate_limit

Per-host async token-bucket rate limiter.

## Public surface

| Class | File | Purpose |
|---|---|---|
| `HostRateLimiter` | `token_bucket.py` | Async token-bucket limiter keyed by logical host name |

## Contracts

- `acquire(host)` — async; sleeps until a token is available.  No-op when `rate_rps=None`.
- `set_rate(host, rps)` — runtime rate update; resets the bucket.
- `disable(host=None)` — disable per-host or globally.
- Bucket capacity = `max(1.0, rate_rps)` tokens (burst = 1 second of rate).
- Starts full (first request never waits).

## Wiring

`ClientConfig.rate_limit_rps` (default `4.0`) feeds the default rate.
`None` disables rate limiting globally.  Per-host overrides via `host_overrides` dict.
`HostRateLimiter` is DI-injected into the session funnel.
