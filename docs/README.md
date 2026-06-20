# pskovedu-sdk documentation

Usage guide for the async Python SDK for **one.pskovedu.ru** (Pskov Region
education portal).

> Primary README: [English](../README.md) · [Русский](../README.ru.md)

## Contents

1. [Getting started](getting-started.md) — install, build a client, make your first call
2. [Authentication](authentication.md) — cookie auth, QR/ESIA login, how the cookies work, expiry
3. [Usage](usage.md) — the method-object pattern, flat helpers, pagination, per-domain examples
4. [Reactive layer](reactive.md) — watchers, `Dispatcher`, `LessonBell`, snapshot persistence
5. [Configuration](configuration.md) — `ClientConfig`, env vars, proxies, custom transport/storage
6. [Architecture](architecture.md) — how the real portal works, how the SDK is layered
7. [Gotchas](gotchas.md) — pitfalls that will bite you, with fixes
8. [Known issues & status](known-issues.md) — what's verified, what's reverse-engineered, what's broken

## ⚠️ Read this first

This library is **mostly reverse-engineered and vibe-coded**. The portal exposes
no public API spec — its surface was inferred from browser captures (HAR) and the
app's JavaScript bundle. As a result:

- **Some endpoints are verified working** (REST: diary, schedule).
- **Some have a known protocol bug** (Ext.Direct / X1 calls — see
  [known-issues.md](known-issues.md)).
- **Treat everything as experimental.** Fork and adapt.

See [Known issues & status](known-issues.md) for the precise verified/unverified
matrix before relying on any endpoint.
