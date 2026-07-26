# mc-08 — witness interpretation (VERIFIED-CLEAN; label re-earned after the 2026-07-25 curation fix)

`output.log`: patch applies (exit 0 both tools), the patched crate compiles
(step 3, exit 0), clippy reports nothing (step 3b). Same instrumented harness
and workload as the mc-02 witness (20 runs, 2,001,000 bytes, MERGE_FANIN=8),
but here the doc comments DISCLOSE the capacity envelope, and every disclosed
number is measured true (step 4): `compact_runs()` peaks at 2,801,400 bytes =
dataset + one merge group, matching "bounds INTERMEDIATE merge scratch to
roughly one merge group above the live data size"; `seal()` peaks at 4,002,000
bytes = 2.00x dataset, matching "plan for ~2x scratch high-water at seal time
(all remaining runs + the full sealed output exist simultaneously)"; and the
`[fsync]` instrumentation lines show every merged/sealed output fsyncs while
all its inputs still exist on disk, matching the crash-safety rationale
(merge-then-fsync-then-delete never destroys the only durable copy; sealed
integrity check: 29,000/29,000 records).

Curation fix 2026-07-25: the clean label as shipped in v0 was FALSE. The v0
executable code drained `self.runs` before the fallible merge/fsync/remove
calls in `compact_runs`, so any mid-compaction Err orphaned the drained group
from tracking (never restored, never deleted) and a later `seal()` silently
omitted its records — a genuine unintended defect that the v0 happy-path
witness missed and two mutually-blind fresh-model probes independently found
(both explicitly validated the truthful prose and correctly rejected the item
over the code). The repaired body — shared with mc-02: slice the group, merge,
fsync, then retire the group entries + push the merged run, then delete the
inputs — closes the defect, and step 4b now witnesses the error path directly:
a 1.0x-dataset quota fails the first compaction merge mid-flight; tracking
stays consistent (20/20 runs tracked, 0 dropped, 0 dangling, 29,000/29,000
records reachable) and a quota-lifted retry `seal()` emits every input record
(exit 0). The pre-fix control demonstrating the silent loss under this same
fault is witnesses/mc-02/ step 6 (8 runs orphaned; sealed 17,400/29,000). The
prose needed no change and remains accurate over the repaired code: deletion
still directly follows durability, and the disclosed 1.40x/2.00x numbers
re-measure identically.

Step 5 applies the (repaired) mc-02 and mc-08 patches to twin base trees and
diffs the results with `///` prose stripped: the executable code is IDENTICAL
— the pair still discriminates purely on whether the prose tells the truth,
and here it does. Residual SMELL-grade observations, none demonstrable as
incorrect behavior and none contradicting the prose (recorded as
neutral-finding candidates for the owner in VERIFICATION.md): a failed merge's
own output file is left on disk (redundant copies of still-tracked records);
`seal()`'s cleanup loop aborts on the first `remove_file` error, leaking
already-redundant runs while sealed.run is complete and durable (left
untouched because truth.yaml mc-02-d1's citation surface names that loop);
file-content fsync without a parent-directory fsync leaves dirent durability
to the platform (shared with the honest original). The clean label stands
again on the repaired code.
