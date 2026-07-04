# allocate (integer split helpers)

Splits an integer `total` across a list of weights.

Contract:
- `allocate(total, ws)` returns one integer share per weight, and the
  shares sum exactly to `total`.
- `allocate_budget(total, categories)` splits `total` across a
  name->weight mapping and returns a name->amount dict.
- `_share`, `total_weight`, `largest_index`, `rebalance`, `percentages`,
  `scaled`, `is_empty` are supporting helpers.
