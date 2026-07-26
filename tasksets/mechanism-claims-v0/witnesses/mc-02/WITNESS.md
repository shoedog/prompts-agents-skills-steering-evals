# mc-02 — witness interpretation (VERIFIED-SEEDED; re-verified after the 2026-07-25 curation fix)

`output.log`: patch applies (git apply exit 0; one cosmetic "new blank line at
EOF" whitespace warning on the CHANGELOG hunk) and the patched crate compiles
(step 3, exit 0). The scaled minimal_trigger uses 20 spilled runs = 2,001,000
bytes with MERGE_FANIN=8; a scratch meter samples total directory bytes at the
end of every `merge_sorted` (the instant inputs and the full output coexist).
Measurement run (step 4a): during `compact_runs()` the peak is 2,801,400 bytes
= exactly dataset + one merge group (1.40x) — the per-group deletion works
there — but during `seal()` the merge of all 6 remaining runs into
`sealed.run` puts the directory at 4,002,000 bytes = 2.00x dataset (log line
45), i.e. "all remaining runs + full sealed output" simultaneously — precisely
the high-water the CHANGELOG hunk claims "is gone". Quota run (step 4b), the
truth.yaml 100 GiB-data/150 GiB-volume trigger scaled to 2 MB/3 MB:
`compact_runs` passes within the 1.5x-dataset volume, then `seal()` fails
ENOSPC-style at 4,002,000 bytes demand (driver exit 3). The `[fsync]` lines
show sealed.run fsyncs while every input still exists, confirming the
merge-everything-then-delete ordering in `seal()` is the mechanism. Seeded
defect mc-02-d1 is real: the changelog's "bounded by one merge group at every
stage, including seal" capacity claim is false. (Integrity cross-check: the
sealed run contains all 29,000 input records, so the measurement is of a
correct merge, not an artifact of a broken shim.)

Curation fix 2026-07-25 (steps 5–6): v0's `compact_runs` drained the group out
of `self.runs` BEFORE the fallible merge/fsync/remove calls — an unintended
genuine error-path defect (converged on by two mutually-blind fresh-model
probes) sitting beside the intended CHANGELOG seed. The repaired body slices
the group, performs merge+fsync, and only then retires the group entries and
pushes the merged run; `seal()` is byte-identical to v0. Step 5 (fault
injection: 1.0x-dataset quota fails the first compaction merge mid-flight):
tracking stays consistent — 20/20 runs still tracked, 0 dropped from tracking,
0 dangling entries, 29,000/29,000 records reachable — and a quota-lifted retry
`seal()` emits all 29,000 records (exit 0; the failed merge's own output file
remains on disk as redundant residue — copies of still-tracked records, no
data loss — recorded as a neutral-finding candidate in VERIFICATION.md).
Step 6 (control: the pre-fix drain-first body under the same fault): 8 runs
vanish from tracking and the retry `seal()` returns Ok with only 17,400 of
29,000 records — silent data loss, exit 6 — demonstrating exactly why the fix
was required. Steps 4a/4b re-measured after the fix are numerically identical
to the v0 run (1.40x compact peak, 2.00x seal peak/demand, quota exit 3): the
seeded mechanism is untouched by the repair.
