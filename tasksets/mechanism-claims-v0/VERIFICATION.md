# mechanism-claims-v0 — execution verification (checklist items 1 + 2)

Date: 2026-07-25. Scope: manifest promotion-checklist lines 1 (execution-verify
every diff) and 2 (hunk-header arithmetic audit) ONLY. Fresh-model probe and
owner sign-off are NOT covered here and remain unticked.

Method: for every item, the diff was applied to a scratch tree (`git apply
--check`, `patch -p1 --dry-run`, then a real `git apply`), compiled/parsed with
the language's toolchain (rustc 1.94.0 via cargo; tsc 6.0.3 + node 26 for TS;
bash -n for shell), and then the truth.yaml `minimal_trigger` (seeded items) or
the prose claims themselves (clean items) were EXECUTED. Every claim below
cites a witness directory containing `run.sh` (re-runnable, self-contained),
`output.log` (full captured stdout/stderr with per-step exit codes — no
truncating pipes), and `WITNESS.md` (interpretation). The review-hard
convention commit (d49c319) was checked first: it shipped no verification
evidence files (verification lived in the commit message only), so the
`witnesses/<item-id>/` + `VERIFICATION.md` layout used here is new, not a
deviation from an existing convention.

## Per-item verdicts

| item  | label       | verdict         | witness                | mechanism (one line) |
|-------|-------------|-----------------|------------------------|----------------------|
| mc-01 | seeded:true | VERIFIED-SEEDED | `witnesses/mc-01/` | Doc hunk claims "custom binary codec / no JSON on the write path / protobuf stored raw"; executed `push()` of one 20-protobuf-byte Entry produced a 244-byte JSON payload with the bar bytes as a 64-char JSON integer array (3.20x) via `encode_entry()`'s `serde_json::to_writer`. |
| mc-02 | seeded:true | VERIFIED-SEEDED | `witnesses/mc-02/` | CHANGELOG claims the 2x seal-time high-water "is gone"; instrumented run measured compact peak = dataset + one group (1.40x) but seal peak = 2.00x dataset (all remaining runs + full sealed output), and on a 1.5x-dataset quota volume compact passed while `seal()` failed ENOSPC-style — `seal()` merges everything before deleting anything. Re-verified 2026-07-25 after the compact_runs curation fix (see below): seeded numbers reproduce exactly; new fault-injection step shows tracking stays consistent when a mid-compaction merge fails, and a pre-fix control arm reproduces the old silent data loss. |
| mc-03 | seeded:true | VERIFIED-SEEDED | `witnesses/mc-03/` | RESUME doc's "runnable now" command `backfill audit-canonical --spinoff-binding …` exits 2 at parse time with "--spinoff-binding is accepted only by load-canonical and adjudicate-canonical" — the accept-list guard added in the same diff excludes audit-canonical; controls show the flag works for both accept-listed subcommands and audit works flagless. |
| mc-04 | seeded:true | VERIFIED-SEEDED | `witnesses/mc-04/` | Doc comment promises `.`/`..` "preserved verbatim" (non-resolving); executed `foldSegments("a/./b/../c")` returns `["a","c"]` (skip + pop resolve them); bonus: leading `..` vanish so `foldsUnder("shared","../../shared/x")` is true. File itself passes `tsc --strict`. |
| mc-05 | seeded:true | VERIFIED-SEEDED | `witnesses/mc-05/` | Header comment claims script exit = test runner's exit; with fmt+clippy proven green and one failing test, bare `cargo test` exits 101 but `bash ci/run-suite.sh` exits 0 — `cargo test \| tail -40` under `set -eu` without pipefail reports tail's status; fmt breakage still exits 1 (not swallowed). |
| mc-06 | seeded:false| VERIFIED-CLEAN  | `witnesses/mc-06/` | Doc says framing binary + payload serde_json with ~3-4x bar blow-up + count/SHA-256 footer over the framed stream; all measured true (magic present; len prefixes exact; payloads parse + round-trip; blow-ups 3.20x/3.60x; recomputed SHA-256 equals stored). No unintended defect found (clippy clean; quirks are the truth.yaml neutral/tempting ones). |
| mc-07 | seeded:false| VERIFIED-CLEAN  | `witnesses/mc-07/` | RESUME's `backfill verify-archive --rebuild-index` runs exit 0 with `rebuild_index=true` — the `--rebuild-index` guard accept-lists verify-archive; the stricter adjacent guard governs `--emit-report` only, and all four cross-probes match the enumerated lists. Guard-before-dispatch message quirk witnessed (probe E): error either way, not a defect. |
| mc-08 | seeded:false| VERIFIED-CLEAN  | `witnesses/mc-08/` | Doc comments disclose the same code's true envelope: measured compact peak = dataset + one group (1.40x), seal peak = 2.00x dataset exactly as the "~2x at seal" note says, fsync-before-delete ordering witnessed; executable code proven byte-identical to mc-02's modulo `///` prose (pair discriminates on prose truthfulness alone). Clean label re-earned 2026-07-25: v0's label was falsified by an unintended compact_runs error-path defect (probe-found, missed by the original happy-path witness); repaired identically in both twins and re-witnessed incl. a fault-injection step proving no run is orphaned from tracking on a mid-compaction failure. |

Label status: all five seeded contradictions are real and were demonstrated by
execution in the form truth.yaml describes. Clean items mc-06/mc-07 held under
execution with nothing disqualifying. mc-08's clean label, however, was
REFUTED as shipped in v0 — the unintended-defect hunt here missed a genuine
error-path defect in the mc-02/mc-08 shared code that two fresh-model probes
later converged on — and was re-earned on 2026-07-25 after the curation fix
documented below. Post-fix, all three clean items hold (details +
neutral-grade observations in each WITNESS.md; base rate is intact again).

## Hunk-header arithmetic audit (checklist line 2)

`witnesses/hunk-audit/` (`audit.py` + `output.log`): all 12 hunks across the 8
patches are internally consistent — declared old/new counts equal the recounted
context/deletion/addition body lines, cross-hunk start offsets match cumulative
deltas (incl. the `-0,0 +1,N` new-file convention on mc-01/04/05/06), every
body line carries a valid prefix, no stray lines / CRLF / missing final
newline. `HUNK-AUDIT RESULT: PASS`, exit 0. Cross-checked by `git apply
--check` (exit 0, all 8) and `patch -p1 --dry-run` (exit 0, all 8) in each
item witness. One cosmetic note (not an arithmetic defect): mc-02's CHANGELOG
hunk ends with a `+` blank line at EOF, drawing a `git apply` whitespace
warning. Caveat: absolute start-line positions for the four modify-style
patches (mc-02/03/07/08) are unverifiable because the taskset ships no base
tree; applying against reconstructed bases succeeds with the benign offsets
`patch` reports. Counts and structure — the auditable part — are fully
consistent. Re-audited 2026-07-25 after the curation fix changed the
replay_spool.rs hunks to `-204,9 +204,38` (mc-02) and `-204,9 +204,47`
(mc-08): all 12 hunks still OK, `HUNK-AUDIT RESULT: PASS`, exit 0
(`witnesses/hunk-audit/output.log` regenerated; both patches also re-passed
`git apply --check` and `patch -p1 --dry-run` in the re-run item witnesses).

## Curation fix (2026-07-25): mc-02/mc-08 shared compact_runs error path

Why required: two mutually-blind fresh-model probes (raw log:
`~/Documents/w2-tasks/probe-results-mechanism-claims-v0.md`, sections mc-02
and mc-08) independently found an UNINTENDED genuine defect in the
reconstruction code shared by mc-02 (seeded) and mc-08 (clean twin), which the
happy-path execution witnesses above had missed: `compact_runs` drained the
group out of `self.runs` (`self.runs.drain(..MERGE_FANIN)`) BEFORE the
fallible `merge_sorted`/`fsync_file`/`remove_file` calls, so any Err returned
early with the group's files permanently untracked — never restored to
`self.runs`, never deleted — and a later `seal()` silently omitted their data.
Consequence: mc-08's clean label was false as written (one probe rejected it
while explicitly validating all the truthful prose — a correct review punished
by the item), inverting the pair's discriminating power; in mc-02 the same
defect was noise beside the intended CHANGELOG seed.

The fix (both `diff.patch` files, identical executable change; all prose
untouched): `compact_runs` now takes the group by slice-clone
(`self.runs[..MERGE_FANIN].to_vec()`), performs the fallible merge+fsync, and
only after they succeed retires the group entries (`drain`) and pushes the
merged run, then deletes the inputs. The disk-operation order (merge, fsync,
delete-inputs) is unchanged, so every measured number and both items' prose
surfaces are unchanged; only the in-memory tracking update moved to the
durability point. `seal()` is byte-identical to v0 in both items: the seeded
2x-at-seal mechanism (merge-everything-then-delete) and the mc-02 CHANGELOG
contradiction are untouched. Witness re-runs reproduce the v0 numbers exactly
(1.40x compact peak, 2.00x seal peak, ENOSPC-style quota failure, driver exit
3); mc-08's disclosed numbers ("roughly one merge group above the live data
size", "~2x at seal") re-measure true; and the pair cross-check re-proves the
twins' executable code identical modulo `///` prose.

New witness coverage: both runners now execute a fault-injection mode (driver
mode "fault": a 1.0x-dataset quota fails the first compaction merge
mid-flight) demonstrating tracking consistency under failure — 0 runs dropped
from tracking, 0 dangling entries, 29,000/29,000 records still reachable via
`self.runs`, and a quota-lifted retry `seal()` emitting every record (exit 0)
— plus a control arm in `witnesses/mc-02/` (step 6) that reverts
`compact_runs` to the v0 drain-first body and reproduces the defect under the
same fault: 8 runs orphaned from tracking and a retry `seal()` returning Ok
with 17,400 of 29,000 records (silent data loss, exit 6).

truth.yaml impact: none required. Both files use symbolic locations
("seal()", "compact_runs()", "the remove_file loop"), so no
line-number/location or hunk_lines reference shifted; acceptable_match /
reject_if and all other bar wording are byte-unchanged.

Neutral-finding candidates for the owner (deliberately NOT fixed here):

- `seal()`'s cleanup loop `fs::remove_file(run)?` aborts on the first failure,
  leaking the remaining (already-redundant) runs and returning Err although
  sealed.run is complete and durable (probe-graded WRONG-low in mc-08, SMELL
  in mc-02; no data loss, failure is loud). Left untouched deliberately:
  truth.yaml mc-02-d1's hunk_lines/acceptable_match name seal()'s post-merge
  remove_file loop as citation surface, so editing that line risks bar drift,
  and the change is not needed to make mc-08's prose true (the doc makes no
  claim about cleanup-failure handling). Owner may accept it as a
  neutral/tempting entry in both truth.yamls or request a follow-up edit.
- A failed compaction merge leaves its own output file on disk, untracked;
  the file holds only copies of still-tracked records (no data loss — the
  step-5 fault witness shows 29,000/29,000 records reachable with exactly one
  such residue file), and a retry allocates a fresh path. Same class of
  error-path residue; candidate for the same owner decision.

Checklist status after this fix: box 1 (execution-verify every diff) was
RE-EARNED for mc-02 and mc-08 on 2026-07-25 — both witnesses were re-run
end-to-end against the repaired patches, including the new fault-injection
coverage, and the other six items' witnesses are untouched and remain valid —
so box 1's existing tick stands. Box 2 re-earned via the regenerated hunk
audit. Boxes 3 (fresh-model probe) and 4 (owner sign-off) remain unticked;
mc-02 and mc-08 need a fresh post-fix probe pass before box 3 can be graded
(the pre-fix probe results for these two items are superseded).

## Shims log (every shim is in the item's `run.sh`; none touches a seeded mechanism)

- mc-01: wrapper `Cargo.toml` (serde =1.0.228 derive / serde_json =1.0.150 /
  sha2 =0.10.9), `src/lib.rs` (`pub mod replay_spool;`), `src/bin/trigger.rs`
  harness, base `docs/spool-format.md` pre-image (`TBD.`).
- mc-02: wrapper `Cargo.toml`; base `src/replay_spool.rs` reconstruction
  (SpoolDir fields/new/spill, `next_run_path` + `scratch_bytes` context lines,
  `merge_sorted`, `fsync_file`, MERGE_FANIN=8) with a scratch-usage meter
  sampled at the end of `merge_sorted` and an optional ENOSPC-simulating
  quota — instrumentation lives ONLY in base support code; `compact_runs`/
  `seal` come solely from the patch; `src/bin/driver.rs`; `CHANGELOG.md`
  pre-image. 2026-07-25: driver gained the "fault" mode (quota-induced
  mid-compaction Err + tracking-consistency checks + retry seal) and the
  runner a step-6 control arm that reverts compact_runs to the pre-fix body
  via an exact-string python replacement (asserts the fixed body is present
  exactly once, so drift fails loudly) — still no shim touches a seeded
  mechanism.
- mc-03: wrapper `Cargo.toml`; base `src/main.rs` (CliError, next_value, Opts,
  stub subcommands printing their args, pre-image `run()`); base
  `docs/RESUME-g4c.md` through its "Next step" header; `out/rev9-bindings.json`
  created before the trigger. Note: the base pre-image intentionally carries
  the post-state two-arg stub signatures (the diff rewrites the call sites but
  not the definitions), so only the PATCHED tree compiles — the pre-image is a
  patch target, not a buildable state.
- mc-04: `trigger.ts` harness only (throws instead of `process.exit` to stay
  free of node-only globals).
- mc-05: fixture crate `Cargo.toml` + `src/lib.rs` (one passing + one seeded
  failing test), normalized once with `cargo fmt` during prep; script run via
  `bash ci/run-suite.sh` (patch carries no exec bit); badfmt copy for probe C.
- mc-06: as mc-01 (wrapper crate, lib.rs, trigger harness, doc pre-image).
- mc-07: as mc-03 (base main.rs with verify_archive/load_canonical/
  adjudicate_canonical stubs, RESUME-archive pre-image).
- mc-08: base extracted verbatim from the mc-02 runner (shared base by
  construction; `use mc02::` → `use mc08::` rename in the driver), plus the
  prose-stripped pair diff vs mc-02; inherits the driver "fault" mode via the
  same extraction (step 4b, 2026-07-25).

## Not executed, and why

- mc-02/mc-08 at literal scale: the truth.yaml trigger names 100 GiB of runs on
  a 150 GiB volume; executed at 2 MB / 3 MB (same 1.5x ratio, same fan-in, same
  code paths) — the mechanism is scale-invariant and the measured 2.00x demand
  + quota failure is the claimed behavior. No 100 GiB run was performed.
- Absolute hunk start positions for mc-02/03/07/08 (no base tree exists to
  check them against; see hunk-audit caveat).
- truth.yaml `provenance` references (sessions/repos) were treated as
  background per the verification brief and not re-mined; verification stands
  on the reconstructions alone.
- mc-05 ran under macOS bash 3.2.57 (the `bash` on PATH); the pipeline-status
  semantics exercised are POSIX-mandated, but no other bash version was run.

## Environment

macOS (Darwin 25.5.0), cargo/rustc 1.94.0 (+ rustfmt 1.8.0, clippy 0.1.94),
git 2.50.1 (Apple Git-155), Apple patch 2.0-12u11, node v26.0.0, tsc 6.0.3,
python3 for audit.py. Build trees under the session scratchpad; nothing
committed.

## Owner adjudications

- 2026-08-07 (exp-w3a spotcheck, baseline mc-02): CITATION REQUIRED bar stands
  AS WRITTEN — a finding naming the correct mechanism but citing only the
  doc/CHANGELOG hunk scores a false finding, not an uncredited match. The
  rubric's reject_if says exactly this; the judge applied it correctly.
- Forward-only amendments directed at the same time (NEXT curation pass, not
  retroactive): (1) ground truth must carry EXPLICIT citation anchors —
  file + line range with a stated ± margin — per defect, so citation matching
  is mechanical (check_citations.py-style), not judge interpretation; today's
  truth names constructs ("the merge_sorted-over-self.runs call") and leaves
  line resolution to the judge, which the owner is skeptical of. (2) Items
  whose acceptable_match needs multiple citations should WEIGHT them, so runs
  can measure accuracy when several anchors are required. (3) Preference
  order: implementing-code citations over doc/changelog citations.
