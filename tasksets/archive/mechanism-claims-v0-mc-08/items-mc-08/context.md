# replay_spool: compaction + seal (documented capacity envelope)

The spool spills sorted "run" files to a scratch directory; SpoolDir tracks
them in `self.runs`. `merge_sorted(inputs, out)` k-way-merges input runs
into one output run. `fsync_file` makes a run durable. MERGE_FANIN is the
merge fan-in constant (8). Scratch space is shared with other jobs and is
the binding constraint at full-population scale.

Contract:
- Compaction and sealing must never delete the only durable copy of data.
- Doc comments on these methods are the capacity-planning reference for
  operators provisioning shared scratch volumes; they must be accurate.
- The diff adds group-wise compaction and sealing with their doc comments.
