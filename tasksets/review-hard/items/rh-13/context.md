# search.Search

A predicate-filtered, offset/limit paginated view over a list of items.

Contract:
- `find(pred, offset=0, limit=20)` returns items matching `pred`, skipping
  `offset` and capped at `limit`.
- `first(pred, n)` returns the first `n` matches.
- `page(pred, page_num, size)` returns the 1-indexed `page_num` page of
  `size` matches.
- `matching`, `count`, `batches`, `any`, `nth`, `all`, `size`, `is_empty`
  are read-only helpers.
