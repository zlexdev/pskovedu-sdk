# pskovedu.pagination

Date-window pagination for diary and schedule fetch loops.

## Public surface

| Class | File | Purpose |
|---|---|---|
| `DateWindowPaginator` | `date_window.py` | Generates consecutive `DateWindow` instances for a date range |

## Contracts

- `DateWindowPaginator(start, end, step="week")` — validates `start <= end`.
- Iterates sync (`__iter__`) and async (`__aiter__`).
- `windows()` → `list[DateWindow]` — pre-compute all windows.
- `total_windows()` → `int` — count without materializing.
- Final window clipped to `end` (no overshooting).

## Steps

- `"week"` — 7-day windows (Mon–Sun alignment not enforced; portal returns
  the week containing the passed date regardless).
- `"day"` — 1-day windows for fine-grained schedule iteration.
