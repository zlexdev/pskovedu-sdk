# pskovedu.auth.solvers — pluggable challenge solvers

| Module | Class | Purpose |
|---|---|---|
| `base.py` | `ChallengeSolver` ABC | Single `async solve(client) -> str` contract |
| `qr.py` | `QrSolver` | SSE QR stream driver → `X1_SSO` |

## Contract

```python
class ChallengeSolver(ABC):
    async def solve(self, client: Any) -> str:
        """Return X1_SSO cookie string."""
```

## QrSolver flow

1. Build QR display URL from `client.config.hosts[Host.PORTAL]`
2. Call `display_cb(url)` (sync or async) so caller can render QR
3. Open `client(SubscribeQr(uuid=...))` async generator (SSE stream)
4. Consume events: skip PING/WAITING, count errors, break on `qr-auth-confirmed`
5. Exchange one-time code via `client(ConfirmQr(code=...))` → `X1_SSO`

## Late imports

`pskovedu.methods.qr` and `pskovedu.protocol.sse` are imported at call-time
inside `QrSolver.solve()` so this module can be written before those sibling
modules exist.  `ImportError` surfaces at runtime with a clear message.
