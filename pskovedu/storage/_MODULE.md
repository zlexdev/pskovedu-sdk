# storage/

Abstract and concrete key-value stores for SDK state persistence (tokens + cookie jars).

## base.py — BaseStorage[T] (ABC)

```python
async def get(key: str) -> T | None
async def set(key: str, value: T) -> None
async def delete(key: str) -> None
```

## memory.py — MemoryStorage (default)

In-process ``dict``; data lost on process exit.  Used when no ``storage=`` is
passed to ``Client()``.

## file.py — FileStorage

JSON-on-disk; single file path, all keys share the file.  Thread-safe for
single-process use via `asyncio.Lock` + `asyncio.to_thread`.  Suitable for
bot scripts and CLI tools that restart between runs.

```python
storage = FileStorage("session.json")
client = Client(storage=storage)
```

## Future backends (not in this scope)

- `redis.py` — Redis backend for multi-process deployments (external extra).
