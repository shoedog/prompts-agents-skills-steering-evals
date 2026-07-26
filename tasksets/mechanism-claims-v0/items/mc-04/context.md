# pathfold: lexical segment folding for the alias resolver

Part of a config-driven path alias system: repo-relative paths are split
into segments, folded, and later bound against an alias table by a separate
resolution stage. The division of labor between the two stages is part of
the module's public contract — downstream code decides where dot-segment
handling happens based on the doc comments here.

Contract:
- `foldSegments(path)` produces the canonical segment list for a path.
- `foldsUnder(root, child)` reports whether `child` folds to a path under
  `root`; it is used to scope alias tables to subtrees.
- Doc comments in this module are load-bearing: the alias-resolution stage
  is written against what they promise.
- The diff adds the module (new file).
