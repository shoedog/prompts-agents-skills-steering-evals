# merge.merge

`merge(base, extra=None)` returns a new dict combining `base` and `extra`.

Contract:
- Return a NEW dict; never mutate `base` or `extra`.
- `extra` overrides keys in `base`.
- If `extra` is omitted, return a copy of `base`.
