# query_cache.QueryCache

Caches `loader(table, where)` results keyed on `(table, where)`.

Contract:
- `fetch(table, where, loader)` returns the cached result for
  `(table, where)`, calling `loader` and storing it on a miss.
- `invalidate(table, where)` drops the cached result for that exact
  `(table, where)` pair.
- `invalidate_table(table)` drops every cached result for `table`, any
  filters.
- `cached`, `tables`, `keys`, `size`, `has_table`, `is_empty`, `clear`
  are read-only/utility helpers.
