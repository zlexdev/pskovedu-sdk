# pskovedu.breaker

Circuit breaker protecting gosuslugi.ru infrastructure.

## Public surface

| Class | File | Purpose |
|---|---|---|
| `CircuitBreaker` | `breaker.py` | Per-(host, path) state machine: CLOSED → OPEN → HALF_OPEN → CLOSED |

## Contracts

- `before_call(host, path)` — raises `BreakerOpen` when circuit is OPEN.
- `on_success(host, path)` — resets failure count, closes circuit.
- `on_failure(host, path)` — increments failure count, opens when threshold reached.
- `enroll(host, path)` — opt a pair into the breaker (idempotent).
- `reset(host, path)` — manual CLOSED reset (admin/test use).
- `state(host, path)` → `str` — `"closed"` | `"open"` | `"half_open"`.

## Default enrollment

`ClientConfig.breaker_hosts` (`esia.gosuslugi.ru`, `sfd.gosuslugi.ru`) are
enrolled with path `"/"` on first access.  Other hosts pass through unless
explicitly enrolled.

## Parameters (defaults)

- `failure_threshold=5` — consecutive failures before opening.
- `recovery_s=30` — seconds in OPEN state before HALF_OPEN probe.
