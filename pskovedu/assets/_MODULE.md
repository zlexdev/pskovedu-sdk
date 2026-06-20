# pskovedu.assets

Binary asset download utilities.

## Public surface

| Class | File | Purpose |
|---|---|---|
| `FileCache` | `cache.py` | URL-keyed SHA-256 file cache with TTL eviction |
| `XlsExport` | `xls.py` | Wrapper for raw XLS bytes with `.save(dir)` helper |
| `AssetDownloader` | `downloader.py` | Session-aware binary fetcher (avatar, XLS); delegates caching to `FileCache` |

## Contracts

- `FileCache.get(url)` → `bytes | None` — cache miss returns `None`, never raises.
- `FileCache.put(url, data)` — atomic: bin file then ts file.
- `AssetDownloader.download(url)` → `bytes` — raises `httpx.HTTPStatusError` on non-2xx.
- `AssetDownloader.download_xls(url)` → `XlsExport`.

## Wiring

`AssetDownloader` is DI-injected into the `Client` via constructor.
`FileCache` is optional; pass `None` to disable caching.
No domain knowledge here — callers construct the URL from method class-vars.
