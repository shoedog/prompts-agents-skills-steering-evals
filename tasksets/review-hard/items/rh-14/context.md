# guard.Guard

A re-entrant guard: nested `enter`/`exit` calls share one mutex.

Contract:
- `enter()` enters a (possibly nested) guarded section, acquiring the mutex
  on the outermost level.
- `exit()` leaves one level, releasing the mutex only when the outermost
  level closes.
- `force_reset()` aborts all levels and releases the mutex if held.
- `depth`, `held`, `is_root`, `state`, `reset`, `run`, `locked` are
  helpers over the same mutex/level.
