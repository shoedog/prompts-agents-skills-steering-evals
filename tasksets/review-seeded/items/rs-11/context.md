# batching.chunk

`chunk(seq, size)` splits a sequence into consecutive, NON-overlapping lists
of length `size` (the last may be shorter), covering every element once.

Contract:
- chunk([0,1,2,3,4], 2) -> [[0,1],[2,3],[4]].
- Every element of `seq` appears in exactly one chunk, in order.
- `size >= 1`.
