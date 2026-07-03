# parsing.strip_prefix

`strip_prefix(s, prefix)` removes `prefix` from the start of `s`.

Contract:
- If `s` starts with `prefix`, return `s` with exactly that leading prefix
  removed (only at the very start).
- If `s` does not start with `prefix`, return `s` unchanged.
- Do NOT remove characters that merely appear in `prefix` (this is not
  `str.lstrip`).
