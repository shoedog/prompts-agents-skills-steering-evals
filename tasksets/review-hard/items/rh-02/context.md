# memo.Memo

Memoizes `compute(a, b, opts)`, caching each result under the triple
`(a, b, opts)` where `opts` is an options dict.

Contract:
- `get(a, b, opts=None)` returns the cached result for `(a, b, opts)`,
  computing and storing it on a miss.
- `invalidate(a, b)` drops any cached result for `(a, b)` so the next
  `get` recomputes.
- `peek`/`contains` inspect the cache for `(a, b, opts)` without computing;
  `warm`, `keys`, `size`, `clear` are bulk/utility helpers.
