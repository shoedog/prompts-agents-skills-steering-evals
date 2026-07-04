# leaderboard.Leaderboard

Keeps scores in ascending sorted order so rank queries can use binary
search.

Contract:
- `add(value)` inserts one score, keeping `_scores` globally sorted.
- `add_many(values)` bulk-inserts several scores, keeping `_scores`
  globally sorted.
- `rank(value)` returns how many stored scores are strictly less than
  `value`; `contains(value)` reports membership. Both assume `_scores` is
  sorted (binary search).
- `percentile`, `median`, `worst`, `top`, `size` are read-only queries.
