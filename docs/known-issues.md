# Known issues & status

This SDK is reverse-engineered from browser captures (HAR) and the portal's
JavaScript bundle. This page is the honest map of what is verified vs. what is
not. **Read it before relying on any endpoint.**

## Status legend

- ✅ **Verified** — observed working against real captures / live testing.
- ⚠️ **Known bug** — structurally wrong vs. the real portal; likely non-functional.
- ❓ **Unverified** — modeled from inference, not confirmed end-to-end.

## Endpoint status

| Area | Protocol | Status | Notes |
|---|---|---|---|
| `get_diary`, `iter_diary`, `get_diary_xls` | REST | ✅ | Returns JSON/XLS; confirmed in captures |
| `get_marks_report` | REST | ✅ | |
| `get_schedule`, `get_current_schedule`, `iter_schedule` | REST | ✅ | Returns JSON; confirmed |
| `get_shell` | REST + HTML parse | ❓ | Endpoint real; `X1.user`/`X1_CONFIG` field shapes not fully verified against an authenticated shell |
| `get_avatar`, `get_report` | REST | ❓ | Paths modeled; not live-verified |
| `eje_*` | REST | ❓ | Paths modeled; not live-verified |
| `get_oauth_config`, `check_auth` | REST | ❓ | |
| `get_grades`/`years`/`periods`/`teachers`/`grade_types`/`mark_types` | Ext.Direct | ⚠️ | Envelope bug (below) |
| `get_participants` | Ext.Direct | ⚠️ | Envelope bug |
| `get_journals`, `get_journal`, `read_journal`, `save_journal`, `delete_journal` | Ext.Direct | ⚠️ | Envelope bug |
| `get_user_notifications` | Ext.Direct / X1 | ⚠️ | Envelope bug + X1 model-GUID resolution depends on shell bootstrap |
| `get_reception` | Ext.Direct | ⚠️ | Envelope bug |
| `x1_query`, `x1_get`, `monitoring_*` | Ext.Direct / X1 | ⚠️ | Envelope bug |
| QR / ESIA login (`login_with_qr`) | SSE + SFD token | ❓ | Flow modeled; SFD session-token exchange confirmed, full handshake not end-to-end verified |

## Ext.Direct / X1 envelope is wrong

**The bug.** The portal's `POST /extjs/direct` expects a single generic action
with a **nested** call object:

```json
{
  "action": "X1API",
  "method": "direct",
  "data": [{ "service": "utility", "method": "getusernotifications", "params": [], "ctx": {} }],
  "type": "rpc",
  "tid": 1
}
```

The SDK's `ExtDirectProtocol` instead builds a **flat** envelope
(`{action, method, data: [positional args], type, tid}`) where `action` is the
service name. That does not match `X1API.direct`, so every Ext.Direct / X1 call is
expected to fail until the protocol is rewritten to:

1. Always use `action="X1API"`, `method="direct"`.
2. Wrap the real call as `data[0] = {service, method, params, ctx}`.

Until then, prefer the REST endpoints (diary, schedule).

## Removed: portal `/session` profile endpoint

Earlier versions exposed `client.get_session()` hitting `GET /session` on the
portal. **That endpoint does not exist** — it returns a Yii "Url could not be
matched" page. The only real `/session` is `POST sfd.gosuslugi.ru/session` (the
QR/ESIA session token, no profile). User identity comes from the shell
(`get_shell().role_meta`). `get_session()` has been removed; use `get_shell()`.

## Auth model

- Authentication requires the **`X1_SSO`** cookie. `PHPSESSID` alone is
  insufficient (redirects to `/auth/login`). ✅ confirmed by live testing.
- Token expiry is **not** auto-recovered — `AuthExpiredError` is raised; you
  re-authenticate. ✅

## Contributing fixes

This is intentionally a fork-and-adapt project. The highest-value fix is the
Ext.Direct envelope (it unblocks the majority of endpoints). The real envelope
shape is documented above and in [architecture.md](architecture.md).
