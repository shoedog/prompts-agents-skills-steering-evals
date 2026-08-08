# Judge spot-check (human review)

## baseline — mc-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. docs/spool-format.md:8 — WRONG: doc states "there is no JSON anywhere on the write path," but `src/replay_spool.rs:53-56` encodes every record with `serde_json::to_writer`, making the write path JSON-based.
2. docs/spool-format.md:9-11 — WRONG: doc claims protobuf bar bytes are stored "raw" and spool size stays "roughly the size of the raw protobuf data plus framing overhead," but `Entry` (src/replay_spool.rs:9) derives plain `Serialize` with no `serde_bytes`, so `market_bar: Vec<u8>` is JSON-encoded as an array of decimal byte values under `serde_json`, several times larger than the raw bytes — invalidating the sizing guidance operators would use.
3. src/replay_spool.rs:28 — SMELL: `u32::try_from(body.len()).expect(...)` panics if a single encoded entry exceeds 4 GiB; more plausible now given JSON's size blowup on binary payloads, but no concrete record currently triggers it.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-01-d1
  description: The format doc added by this diff claims records use "our compact custom binary codec" with "no JSON anywhere on the write path" and protobuf bar bytes "stored raw". But encode_entry() serializes every record with `serde_json::to_writer` — only the framing (magic, u32 BE length prefixes, footer) is binary; the payload is JSON, and the `market_bar: Vec<u8>` protobuf bytes are rendered by serde_json as a JSON array of decimal integers (~3-4 chars per byte), not stored raw.
  acceptable_match: any finding that the record payload is serde_json / JSON (naming encode_entry or its `serde_json::to_writer` line in src/replay_spool.rs) contradicting the doc's custom-binary / no-JSON / raw-protobuf claim. Either direction (doc wrong, or code not matching doc) counts. CITATION REQUIRED — the finding must point at the implementing write-path line(s) (encode_entry / the serde_json call), not only at the doc hunk.
  reject_if: a finding that merely calls the encoding inefficient or the doc "possibly stale" without naming the serde_json payload vs binary-framing split; a finding that endorses or restates the custom-binary claim; or a finding citing only docs/spool-format.md lines with no reference to the implementing line(s) in src/replay_spool.rs (citation absent or citation-incorrect).
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the sha256 footer digest covers only the framed record stream, not the RUN_MAGIC header bytes; a header-corruption escape true of the new code but not the seeded doc-vs-code encoding contradiction.
- u32::try_from(body.len()).expect(...) panics rather than erroring on a >4 GiB record; real but out of scope for the seeded defect.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-01-d1']  false_findings=0  item_pass=True

## treatment — mc-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/replay_spool.rs:53 — `encode_entry` uses `serde_json::to_writer`, but docs/spool-format.md states "there is no JSON anywhere on the write path," a direct contradiction of the implemented codec.
2. docs/spool-format.md (added lines) — claims spool size is "roughly the size of the raw protobuf data plus framing overhead," but JSON-encoding `Vec<u8>` as a comma-separated decimal array inflates the payload ~3-4x over raw bytes, invalidating the scratch-volume sizing guidance operators rely on.
3. src/replay_spool.rs:24 — `u32::try_from(body.len()).expect("record fits u32")` panics if an encoded entry exceeds 4 GiB; JSON inflation from finding 1 makes this more reachable than the raw-protobuf size would suggest (SMELL, no concrete triggering input demonstrated).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-01-d1
  description: The format doc added by this diff claims records use "our compact custom binary codec" with "no JSON anywhere on the write path" and protobuf bar bytes "stored raw". But encode_entry() serializes every record with `serde_json::to_writer` — only the framing (magic, u32 BE length prefixes, footer) is binary; the payload is JSON, and the `market_bar: Vec<u8>` protobuf bytes are rendered by serde_json as a JSON array of decimal integers (~3-4 chars per byte), not stored raw.
  acceptable_match: any finding that the record payload is serde_json / JSON (naming encode_entry or its `serde_json::to_writer` line in src/replay_spool.rs) contradicting the doc's custom-binary / no-JSON / raw-protobuf claim. Either direction (doc wrong, or code not matching doc) counts. CITATION REQUIRED — the finding must point at the implementing write-path line(s) (encode_entry / the serde_json call), not only at the doc hunk.
  reject_if: a finding that merely calls the encoding inefficient or the doc "possibly stale" without naming the serde_json payload vs binary-framing split; a finding that endorses or restates the custom-binary claim; or a finding citing only docs/spool-format.md lines with no reference to the implementing line(s) in src/replay_spool.rs (citation absent or citation-incorrect).
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the sha256 footer digest covers only the framed record stream, not the RUN_MAGIC header bytes; a header-corruption escape true of the new code but not the seeded doc-vs-code encoding contradiction.
- u32::try_from(body.len()).expect(...) panics rather than erroring on a >4 GiB record; real but out of scope for the seeded defect.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-01-d1']  false_findings=1  item_pass=False

## baseline — mc-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/replay_spool.rs:212-216 (WRONG) — in `compact_runs`, `self.runs` is drained/updated to drop the group's paths before the `fs::remove_file` loop runs; if a deletion in the middle of the group fails, the function returns `Err` but the remaining un-removed files in that group are no longer tracked in `self.runs`, permanently leaking scratch space that `scratch_bytes()` will silently undercount.
2. src/replay_spool.rs:227-229 (WRONG) — in `seal`, a mid-loop `fs::remove_file` failure returns `Err` and drops `self` (owned by value), destroying the only record of which remaining runs still need deletion, so any un-removed files from that final group are permanently orphaned with no future chance of cleanup.
3. CHANGELOG.md (SMELL) — the "peak scratch bounded by one merge group at every stage" claim holds only on the error-free path; given findings 1–2, a deletion failure under shared-scratch contention (the exact scenario the changelog is meant to help operators plan for) can cause unbounded orphaned-file accumulation that the claim doesn't account for.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-02-d1
  description: The changelog claims peak scratch is now "bounded by one merge group at every stage, including seal" and that the 2x seal-time high-water "is gone". But seal() merges ALL remaining runs into one full-size sealed.run BEFORE deleting any input: at the moment merge_sorted returns, scratch simultaneously holds every remaining run (jointly ~the full dataset after compact_runs) plus the complete sealed output. The 2x high-water at seal is unchanged; compact_runs only bounds the intermediate merges.
  acceptable_match: any finding that seal() holds all remaining runs plus the full sealed output on disk at once (merge-then-delete ordering), so the 2x seal-time peak persists and the changelog claim is false. CITATION REQUIRED — the finding must point at the implementing seal() line(s) (the merge_sorted-over-self.runs call and/or the post-merge remove_file loop), not only at the changelog hunk.
  reject_if: a finding that only questions deleting files in general, praises or restates the bounded-peak claim, says "the changelog may overstate" without naming seal()'s merge-then-delete ordering, or cites only CHANGELOG.md with no reference to the implementing line(s) in src/replay_spool.rs.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- seal() re-runs merge_sorted even when compact_runs left exactly one run, paying an avoidable full copy; true of the new code but not the seeded false-capacity-claim defect.
- sealed.run has a fixed name, so re-sealing into the same scratch dir would clobber a prior sealed run; real edge case, out of scope for the seeded defect.
```
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=2  item_pass=False

## treatment — mc-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/replay_spool.rs:217-220 — WRONG: in `compact_runs`, `self.runs` is updated (drain+push) before all group files are removed; if `fs::remove_file` fails or the process is interrupted mid-loop, the remaining un-removed files become permanently untracked orphans, leaking shared scratch space indefinitely.
2. src/replay_spool.rs:232-233 — WRONG: same pattern in `seal`; since `self` is consumed by the function, a partial failure in the removal loop leaves the un-removed remainder of `self.runs` unreachable once `self` is dropped, with no path to clean them up.
3. CHANGELOG.md:9 — SMELL: "the old 2x ... high-water mark ... is gone" reads as fixing pre-existing behavior, but the diff shows `compact_runs`/`seal` as entirely new code with nothing removed, so there was no "old" version of this code path to regress from.
4. src/replay_spool.rs — SMELL: no tests accompany `compact_runs`/`seal`, despite them being the safety-critical logic the stated contract (never delete the only durable copy) depends on.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-02-d1
  description: The changelog claims peak scratch is now "bounded by one merge group at every stage, including seal" and that the 2x seal-time high-water "is gone". But seal() merges ALL remaining runs into one full-size sealed.run BEFORE deleting any input: at the moment merge_sorted returns, scratch simultaneously holds every remaining run (jointly ~the full dataset after compact_runs) plus the complete sealed output. The 2x high-water at seal is unchanged; compact_runs only bounds the intermediate merges.
  acceptable_match: any finding that seal() holds all remaining runs plus the full sealed output on disk at once (merge-then-delete ordering), so the 2x seal-time peak persists and the changelog claim is false. CITATION REQUIRED — the finding must point at the implementing seal() line(s) (the merge_sorted-over-self.runs call and/or the post-merge remove_file loop), not only at the changelog hunk.
  reject_if: a finding that only questions deleting files in general, praises or restates the bounded-peak claim, says "the changelog may overstate" without naming seal()'s merge-then-delete ordering, or cites only CHANGELOG.md with no reference to the implementing line(s) in src/replay_spool.rs.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- seal() re-runs merge_sorted even when compact_runs left exactly one run, paying an avoidable full copy; true of the new code but not the seeded false-capacity-claim defect.
- sealed.run has a fixed name, so re-sealing into the same scratch dir would clobber a prior sealed run; real edge case, out of scope for the seeded defect.
```
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=2  item_pass=False

## baseline — mc-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. docs/RESUME-g4c.md:12 (paired with src/main.rs ~134) — The doc's "Next step (runnable now)" command `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` is rejected by the flag-acceptance check, which only allows `--spinoff-binding` for `load-canonical`/`adjudicate-canonical`, so the mandated next step fails with a `CliError::Config` before running.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-03-d1
  description: The handoff doc added by this diff instructs the next session to run `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` as a "runnable now" step. The acceptance guard added in the same diff enumerates the accepting subcommands as exactly load-canonical and adjudicate-canonical; audit-canonical is not in the list, so the documented command exits at parse time with "--spinoff-binding is accepted only by load-canonical and adjudicate-canonical".
  acceptable_match: any finding that audit-canonical rejects --spinoff-binding (the accept-list guard excludes it), so the RESUME next step is not runnable as written. CITATION REQUIRED — the finding must point at the implementing guard line(s) in src/main.rs (the matches! accept-list or the returned Config error), not only at the RESUME doc line.
  reject_if: a finding that says the doc "may be stale" or "should be double-checked" without naming the accept-list; a finding claiming --spinoff-binding does not exist at all (it exists for the two load-path subcommands); or a finding citing only docs/RESUME-g4c.md with no reference to the implementing guard in src/main.rs.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the guard's error message does not name the offending subcommand the user actually typed; a minor usability gap in the new code, not the seeded unrunnable-handoff defect.
- audit_canonical() takes no binding parameter, so supporting the documented replay would need a code change, not just a doc fix; true consequence, same underlying defect only if the accept-list is named.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-03-d1']  false_findings=0  item_pass=True

## treatment — mc-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. docs/RESUME-g4c.md (Next step section) — the documented "runnable now" command `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` will fail with a `CliError::Config` because src/main.rs's new acceptance check (src/main.rs, `if !matches!(cmd.as_str(), "load-canonical" | "adjudicate-canonical") ...`) rejects `--spinoff-binding` for `audit-canonical`, violating the contract that the handoff doc's next step must be executable exactly as written.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-03-d1
  description: The handoff doc added by this diff instructs the next session to run `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` as a "runnable now" step. The acceptance guard added in the same diff enumerates the accepting subcommands as exactly load-canonical and adjudicate-canonical; audit-canonical is not in the list, so the documented command exits at parse time with "--spinoff-binding is accepted only by load-canonical and adjudicate-canonical".
  acceptable_match: any finding that audit-canonical rejects --spinoff-binding (the accept-list guard excludes it), so the RESUME next step is not runnable as written. CITATION REQUIRED — the finding must point at the implementing guard line(s) in src/main.rs (the matches! accept-list or the returned Config error), not only at the RESUME doc line.
  reject_if: a finding that says the doc "may be stale" or "should be double-checked" without naming the accept-list; a finding claiming --spinoff-binding does not exist at all (it exists for the two load-path subcommands); or a finding citing only docs/RESUME-g4c.md with no reference to the implementing guard in src/main.rs.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the guard's error message does not name the offending subcommand the user actually typed; a minor usability gap in the new code, not the seeded unrunnable-handoff defect.
- audit_canonical() takes no binding parameter, so supporting the documented replay would need a code change, not just a doc fix; true consequence, same underlying defect only if the accept-list is named.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-03-d1']  false_findings=0  item_pass=True

## baseline — mc-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/pathfold.ts:4-7 vs 13-17 — Doc comment promises `.`/`..` segments are preserved verbatim, but the implementation resolves them (drops `.`, pops on `..`); e.g. `foldSegments("a/../b")` returns `["b"]` instead of the documented `["a", "..", "b"]`, breaking the documented division of labor with the downstream alias-resolution stage.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-04-d1
  description: The doc comment promises foldSegments is "purely lexical and non-resolving" with `.` and `..` "preserved verbatim in the output". The loop does the opposite: `.` segments are skipped (never emitted) and `..` pops the previously emitted segment — i.e. the function RESOLVES dot segments. The alias-resolution stage written against the comment will never see a dot segment, and `a/b/../c` folds equal to `a/c`.
  acceptable_match: any finding that the loop skips `.` and/or pops on `..` (resolution happens), contradicting the preserved-verbatim / non-resolving doc claim. Naming either the skip or the pop with the contradiction suffices; the leading-`..`-vanishes phrasing (pop on empty is a no-op) also counts. CITATION REQUIRED — the finding must point at the implementing loop line(s) in src/pathfold.ts, not only quote the doc comment.
  reject_if: a finding that only asks for tests or types, flags style, or says the comment "seems ambitious" without naming the skip/pop behavior; or a finding with no reference to the loop line(s) (citation absent, or pointing only at the comment block).
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- splitting an absolute path yields a leading empty segment which the `seg === ""` branch drops, so absolute and repo-relative spellings collide; true of the new code, not the seeded doc-vs-loop contradiction.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-04-d1']  false_findings=0  item_pass=True

## treatment — mc-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/pathfold.ts:13 — `foldSegments` drops `.` segments, contradicting the doc comment's promise (lines 4-7) that `.` segments are "preserved verbatim in the output"; `foldSegments("a/./b")` yields `["a","b"]` instead of `["a",".","b"]`.
2. src/pathfold.ts:14-16 — `foldSegments` resolves `..` by popping the previous segment, contradicting the doc comment's promise that `..` segments are preserved verbatim and that resolution is left to the alias-resolution stage; `foldSegments("a/../b")` yields `["b"]` instead of `["a","..","b"]`, silently performing resolution the module contract says it must not do.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-04-d1
  description: The doc comment promises foldSegments is "purely lexical and non-resolving" with `.` and `..` "preserved verbatim in the output". The loop does the opposite: `.` segments are skipped (never emitted) and `..` pops the previously emitted segment — i.e. the function RESOLVES dot segments. The alias-resolution stage written against the comment will never see a dot segment, and `a/b/../c` folds equal to `a/c`.
  acceptable_match: any finding that the loop skips `.` and/or pops on `..` (resolution happens), contradicting the preserved-verbatim / non-resolving doc claim. Naming either the skip or the pop with the contradiction suffices; the leading-`..`-vanishes phrasing (pop on empty is a no-op) also counts. CITATION REQUIRED — the finding must point at the implementing loop line(s) in src/pathfold.ts, not only quote the doc comment.
  reject_if: a finding that only asks for tests or types, flags style, or says the comment "seems ambitious" without naming the skip/pop behavior; or a finding with no reference to the loop line(s) (citation absent, or pointing only at the comment block).
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- splitting an absolute path yields a leading empty segment which the `seg === ""` branch drops, so absolute and repo-relative spellings collide; true of the new code, not the seeded doc-vs-loop contradiction.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-04-d1']  false_findings=0  item_pass=True

## baseline — mc-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ci/run-suite.sh:19 — WRONG: pipeline exit status is `tail`'s, not `cargo test`'s (no `pipefail`), so a failing test suite (e.g. cargo test exit 101) still yields script exit 0, making CI report green on a failing suite, contradicting the stated contract and the header comment's exit-policy claim.
2. ci/run-suite.sh:19 — WRONG: the full `cargo test` output is discarded after piping through `tail -40`; nothing tees it to a log file, so the header comment's claim that "full output stays in the job log" is false — on-call engineers debugging a red run cannot recover output beyond the last 40 lines.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-05-d1
  description: The header comment claims the script's exit status is the test runner's own exit code. The tests run as `cargo test --workspace 2>&1 | tail -40` with only `set -eu` in effect: without `set -o pipefail` (or an explicit PIPESTATUS check), a pipeline's status is its LAST command's — tail's, which succeeds whether or not cargo test failed. A failing suite exits the script 0 and CI goes green.
  acceptable_match: any finding that the final pipeline's exit status is tail's (missing pipefail / PIPESTATUS), so the exit-policy comment is false and a failing suite passes CI. CITATION REQUIRED — the finding must point at the implementing line(s) (the `cargo test ... | tail` pipeline, optionally together with the `set -eu` line), not only at the comment.
  reject_if: a finding that generically requests "better error handling" or more logging without naming the pipeline-exit mechanism; a finding that claims fmt/clippy failures are also swallowed (they are not piped and do fail the script under set -e); or a finding citing only the comment lines.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- tail -40 hides all but the last 40 lines of failure detail from the step summary; a real observability gap the comment even documents, but not the seeded exit-status defect.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-05-d1']  false_findings=0  item_pass=True

## treatment — mc-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ci/run-suite.sh:18 — `cargo test --workspace 2>&1 | tail -40` is a pipeline without `set -o pipefail`, so the script's exit status reflects `tail`'s exit code (always 0) rather than `cargo test`'s; a failing test suite still produces a 0 exit status, making CI report green despite failing tests, directly violating the script's stated contract.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: mc-05-d1
  description: The header comment claims the script's exit status is the test runner's own exit code. The tests run as `cargo test --workspace 2>&1 | tail -40` with only `set -eu` in effect: without `set -o pipefail` (or an explicit PIPESTATUS check), a pipeline's status is its LAST command's — tail's, which succeeds whether or not cargo test failed. A failing suite exits the script 0 and CI goes green.
  acceptable_match: any finding that the final pipeline's exit status is tail's (missing pipefail / PIPESTATUS), so the exit-policy comment is false and a failing suite passes CI. CITATION REQUIRED — the finding must point at the implementing line(s) (the `cargo test ... | tail` pipeline, optionally together with the `set -eu` line), not only at the comment.
  reject_if: a finding that generically requests "better error handling" or more logging without naming the pipeline-exit mechanism; a finding that claims fmt/clippy failures are also swallowed (they are not piped and do fail the script under set -e); or a finding citing only the comment lines.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- tail -40 hides all but the last 40 lines of failure detail from the step summary; a real observability gap the comment even documents, but not the seeded exit-status defect.
```
**Judge:** verdict=REJECT (flagged)  found=['mc-05-d1']  false_findings=0  item_pass=True

## baseline — mc-06 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. src/target_spool.rs:29 — SMELL: `push()` panics via `.expect()` on record bodies >u32::MAX instead of returning an `Err`, inconsistent with its `Result`-returning signature (only reachable with an unrealistic >4GB single record).
2. docs/target-spool-format.md:9-13 — SMELL: doc specifies the record-count footer field exists but omits its byte width (u64/8 bytes), leaving external implementers to guess despite the doc being the stated reference for reconstructing the format.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: every mechanism claim in the format doc checks out against the write path it documents. Framing binary — create() writes RUN_MAGIC, push() writes u32 BE length prefixes (len.to_be_bytes), finish() writes the count + Sha256 footer over exactly the framed bytes the digest.update calls covered. Payload serde_json — push() encodes via serde_json::to_vec, so the protobuf market_bar bytes (a Vec<u8>) do serialize as a JSON integer array with the stated ~3-4x blow-up. The doc claims the trade is deliberate and scopes the writer to the small target-only population, matching the context; it directs operators to size scratch from JSON record sizes. Doc and code agree; there is no defect to report.
tempting_non_defects (a finding matching one of these is a false finding):
- the binary magic header, length prefixes, and SHA-256 footer "contradict the JSON claim" — they do not; the doc says framing is binary and the payload is JSON, which is exactly what create/push/finish implement.
- storing protobuf bytes inside JSON is a 3-4x size blow-up and "should be flagged as the spool disk-usage bug" — the blow-up is real, stated in the doc itself, and deliberately scoped to the small population; reporting it as a defect repeats the doc instead of contradicting it.
- names like TargetRunWriter / RUN_MAGIC "imply a custom binary codec, so the doc must be wrong about JSON" — the names describe the framing layer; the payload encoding is decided by the serde_json call, which matches the doc.
- push() uses serde_json::to_vec while the sibling full-population spool uses to_writer; a style difference, not a defect.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — mc-06 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. src/target_spool.rs:28 — `u32::try_from(body.len()).expect(...)` panics instead of returning an error if a serialized record ever exceeds u32::MAX bytes (SMELL, not reachable under the stated small target-only workload).
2. src/target_spool.rs:29-33 — if the length-prefix write succeeds but the body write fails, `push` returns early leaving a dangling incomplete frame in `out` with no digest update, and no API to detect/recover from this partial state (SMELL, standard "abandon writer on I/O error" pattern).
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: every mechanism claim in the format doc checks out against the write path it documents. Framing binary — create() writes RUN_MAGIC, push() writes u32 BE length prefixes (len.to_be_bytes), finish() writes the count + Sha256 footer over exactly the framed bytes the digest.update calls covered. Payload serde_json — push() encodes via serde_json::to_vec, so the protobuf market_bar bytes (a Vec<u8>) do serialize as a JSON integer array with the stated ~3-4x blow-up. The doc claims the trade is deliberate and scopes the writer to the small target-only population, matching the context; it directs operators to size scratch from JSON record sizes. Doc and code agree; there is no defect to report.
tempting_non_defects (a finding matching one of these is a false finding):
- the binary magic header, length prefixes, and SHA-256 footer "contradict the JSON claim" — they do not; the doc says framing is binary and the payload is JSON, which is exactly what create/push/finish implement.
- storing protobuf bytes inside JSON is a 3-4x size blow-up and "should be flagged as the spool disk-usage bug" — the blow-up is real, stated in the doc itself, and deliberately scoped to the small population; reporting it as a defect repeats the doc instead of contradicting it.
- names like TargetRunWriter / RUN_MAGIC "imply a custom binary codec, so the doc must be wrong about JSON" — the names describe the framing layer; the payload encoding is decided by the serde_json call, which matches the doc.
- push() uses serde_json::to_vec while the sibling full-population spool uses to_writer; a style difference, not a defect.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — mc-07 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. src/main.rs:~110 (comment above the `--emit-report` check) — SMELL: comment claims `--emit-report is a load-pipeline artifact` (implying `load-canonical` only), but the code correctly accepts it for both `load-canonical` and `adjudicate-canonical`, making the comment inaccurate/misleading about scope.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: the handoff's next step is runnable exactly as written. The documented command is `backfill verify-archive --rebuild-index`; the acceptance guard for --rebuild-index enumerates verify-archive and load-canonical, so the parse succeeds, and the dispatch arm passes rebuild_index through to verify_archive(). The stricter-looking guard immediately below it governs a DIFFERENT flag (--emit-report, restricted to the two load-path subcommands) and is irrelevant to the documented command, which does not use --emit-report. Doc and code agree; the correct review is APPROVE with no findings.
tempting_non_defects (a finding matching one of these is a false finding):
- pattern-matching the --emit-report restriction onto --rebuild-index ("verify-archive is excluded by the guard, so the RESUME step is unrunnable") — the exclusion list read is from the WRONG guard; the --rebuild-index guard explicitly names verify-archive as accepting.
- claiming the RESUME step must also pass --emit-report because the context mentions both flags — the doc'd command needs only --rebuild-index, and emit_report stays None, which every guard permits.
- the boolean --rebuild-index is parsed with `= true` while --emit-report uses next_value; an intentional bool-vs-valued flag difference, not a defect.
- complaining that the guard error messages do not name the subcommand the user typed — a usability preference, not an incorrect behavior, and identical to the codebase's existing style for --dry-run.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — mc-07 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. src/main.rs:~114-124 — SMELL: flag-acceptance checks run before the subcommand-validity check, so an unrecognized subcommand combined with `--rebuild-index`/`--emit-report` reports "accepted only by X/Y" instead of "unknown subcommand", a misleading (but still erroring) message.
2. src/main.rs:~127-131 — SMELL: call sites for `verify_archive`/`load_canonical`/`adjudicate_canonical` gain new parameters, but the diff doesn't show the matching function-definition changes, so compilability can't be verified from this diff alone.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: the handoff's next step is runnable exactly as written. The documented command is `backfill verify-archive --rebuild-index`; the acceptance guard for --rebuild-index enumerates verify-archive and load-canonical, so the parse succeeds, and the dispatch arm passes rebuild_index through to verify_archive(). The stricter-looking guard immediately below it governs a DIFFERENT flag (--emit-report, restricted to the two load-path subcommands) and is irrelevant to the documented command, which does not use --emit-report. Doc and code agree; the correct review is APPROVE with no findings.
tempting_non_defects (a finding matching one of these is a false finding):
- pattern-matching the --emit-report restriction onto --rebuild-index ("verify-archive is excluded by the guard, so the RESUME step is unrunnable") — the exclusion list read is from the WRONG guard; the --rebuild-index guard explicitly names verify-archive as accepting.
- claiming the RESUME step must also pass --emit-report because the context mentions both flags — the doc'd command needs only --rebuild-index, and emit_report stays None, which every guard permits.
- the boolean --rebuild-index is parsed with `= true` while --emit-report uses next_value; an intentional bool-vs-valued flag difference, not a defect.
- complaining that the guard error messages do not name the subcommand the user typed — a usability preference, not an incorrect behavior, and identical to the codebase's existing style for --dry-run.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True
