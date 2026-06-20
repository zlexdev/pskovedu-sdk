# pskovedu.x1db — X1 ORM model registry

Runtime NAME↔SYS_GUID map built from ``X1_CONFIG.meta.models`` at session
bootstrap time.  SYS_GUIDs are installation-specific and must never be
hardcoded; this layer is the single source of truth for resolving them.

## Modules

| Module | Public API | Purpose |
|---|---|---|
| `registry.py` | `X1ModelRegistry` | Build and query NAME↔GUID map; `guid(name)`, `name(guid)`, `all()` |
| `constants.py` | `X1Model` StrEnum | Well-known model names as typed constants |

## Usage pattern

```python
shell = parse_shell(html)
reg = X1ModelRegistry.from_shell(shell)

guid = reg.guid(X1Model.JOURNAL)   # resolved at runtime from X1_CONFIG
```

## Design decisions

- `X1ModelRegistry` is a thin dict wrapper, not an EduObject — it has no
  client binding need and no Pydantic overhead.
- Duplicate NAME entries are logged as warnings; last write wins (consistent
  with portal behavior).
- `X1Model` StrEnum contains well-known names only; the registry holds ALL
  60+ names from the live config, including deployment-specific additions.
