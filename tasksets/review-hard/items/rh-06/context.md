# settings.Settings

A read-only view over a defaults dict, with override composition.

Contract:
- `defaults()` returns the baseline defaults.
- `effective(extra)` returns the defaults with `extra` applied on top and
  must NOT change the stored defaults.
- `get`/`has` look up a single default; `changed_keys(extra)` lists keys
  whose value `extra` would change.
- `as_dict`, `keys`, `size`, `is_empty`, `without` are read-only helpers
  that never mutate the stored defaults.
