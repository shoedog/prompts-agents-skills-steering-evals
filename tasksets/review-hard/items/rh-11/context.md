# rate_window.RateWindow

A sliding-window event counter. The internal clock is integer
milliseconds; the public API takes timestamps in seconds.

Contract:
- `record(at_seconds)` records an event at `at_seconds`.
- `count_since(now_seconds)` returns how many recorded events fall within
  the window ending at `now_seconds`.
- `prune(now_seconds)` drops events older than the window and returns how
  many remain.
- `earliest`, `newest`, `in_window`, `total`, `span_ms`, `window_ms`,
  `reset`, `is_empty` are read-only/utility helpers over the same events.
