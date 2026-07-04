# repo.Repo

An in-memory row store (`table -> list of rows`, newest last) with a
predicate-filtered, offset/limit query API.

Contract:
- `query(table, predicate, offset=0, limit=100)` returns rows matching
  `predicate`, skipping `offset` and capped at `limit`.
- `first_page(table, predicate, size)` returns the first `size` matches.
- `page(table, predicate, page_num, size)` returns the 1-indexed
  `page_num` page of `size` matches.
- `recent(table, limit)` returns the first `limit` rows of the table.
- `count`, `exists`, `all_pages`, `table_names`, `size` are helpers.
