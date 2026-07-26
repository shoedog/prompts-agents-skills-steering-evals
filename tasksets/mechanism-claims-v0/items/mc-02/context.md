# replay_spool: compaction + seal for the external-sort spool

The spool spills sorted "run" files to a scratch directory; SpoolDir tracks
them in `self.runs`. `merge_sorted(inputs, out)` k-way-merges input runs
into one output run. `fsync_file` makes a run durable. MERGE_FANIN is the
merge fan-in constant (8). Scratch space is shared with other jobs and is
the binding constraint at full-population scale.

Contract:
- Compaction and sealing must never delete the only durable copy of data.
- `CHANGELOG.md` entries are operator-facing: capacity planning for shared
  scratch volumes is done from them, so their claims must be accurate.
- The diff adds group-wise compaction, sealing, and the changelog entry.
