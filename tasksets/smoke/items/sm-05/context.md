# batching_ok.batches

`batches(items, size)` splits `items` into consecutive non-overlapping lists
of length `size` (last may be shorter), covering each element once.

Contract:
- batches([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]].
- Every element appears exactly once, in order. `size >= 1`.
