# totals (mapping lookups)

Helpers that read values out of a mapping.

Contract:
- `lookup(data, key)` returns the value for `key`, or None if it is absent.
- `label_for(data, key)` returns a human label for the value, or the
  placeholder '(unknown)' when the key is absent.
- `total_of(data, keys)` sums the values for the present keys; `collect`
  returns those values in order.
- `present_keys`, `missing_keys`, `count_present` are helpers.
