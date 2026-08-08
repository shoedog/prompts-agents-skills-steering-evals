# Judge spot-check (human review)

## baseline — mc-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/replay_spool.rs:53 (encode_entry) — WRONG: records are encoded with `serde_json::to_writer`, but docs/spool-format.md states "there is no JSON anywhere on the write path," a direct contradiction between the code and the doc added in the same diff.
2. docs/spool-format.md (added block, "Protobuf bar bytes are stored raw...size of the raw protobuf data plus framing overhead") — WRONG: since `market_bar: Vec<u8>` is JSON-serialized without `serde_bytes`, it's emitted as a comma-separated JSON array of decimal byte values, inflating spool size ~3-4x versus the raw protobuf bytes the doc claims, which will cause operators to under-provision scratch volumes per the stated contract.
3. src/replay_spool.rs:19-20 (RunWriter::push) — SMELL: `u32::try_from(body.len()).expect(...)` panics on any record body ≥ 4 GiB instead of returning an error; unreachable with normal single-bar payloads but no graceful handling.
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

## treatment — mc-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. docs/spool-format.md:8 (new) — Doc states "no JSON anywhere on the write path" but `encode_entry` in src/replay_spool.rs:53-56 encodes every record via `serde_json::to_writer`, so this is factually false (WRONG).
2. docs/spool-format.md:8-11 (new) — Doc states protobuf bar bytes are "stored raw" and the spool stays "roughly the size of the raw protobuf data plus framing overhead," but `Entry::market_bar` (src/replay_spool.rs:9-11) is a plain `Vec<u8>` with no `serde_bytes` annotation, so `serde_json` (src/replay_spool.rs:53-56) encodes it as a JSON array of decimal numbers, inflating size several-fold beyond raw bytes and contradicting both claims (WRONG).
3. src/replay_spool.rs:26 — `u32::try_from(body.len()).expect(...)` panics instead of returning an error if a record body exceeds 4GiB, an unhandled failure mode for outsized records (SMELL).
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

## baseline — mc-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. CHANGELOG.md:5-8 (WRONG) — Claims peak scratch usage is bounded to "one merge group... including seal," but since compaction only reduces run *count* (not total bytes), the ≤8 runs remaining after `compact_runs` still hold ~all the spool's data; `seal()`'s final `merge_sorted` over them still needs the full remaining dataset plus the full sealed output simultaneously on disk — the same 2x high-water mark the entry claims is gone. This is an operator-facing capacity-planning claim that is factually inaccurate.
2. src/replay_spool.rs:214-226 (SMELL) — If `fs::remove_file` fails partway through the group-deletion loop in `compact_runs`, `self.runs` has already been updated to drop those paths, so the un-removed files become untracked orphans, silently undercounted by `scratch_bytes()`.
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
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=1  item_pass=False

## treatment — mc-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. src/replay_spool.rs:230-234 — `seal` merges all remaining runs into `sealed` and only deletes them after, so when `self.runs` already holds the full remaining dataset (e.g., starting at exactly `MERGE_FANIN` runs, where `compact_runs` at line 212 is a no-op), peak scratch usage is ~2x total data, not bounded by "one merge group" as intended.
2. CHANGELOG.md:6-8 — claims peak scratch is bounded by one merge group "including seal" and that the old 2x seal-time high-water mark is gone; this is false (see finding 1), and since the contract states these entries drive shared-scratch capacity planning, the inaccurate claim can lead operators to under-provision.
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
**Judge:** verdict=REJECT (flagged)  found=['mc-02-d1']  false_findings=0  item_pass=True

## baseline — mc-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. docs/RESUME-g4c.md:9-13 (paired with src/main.rs ~131-141) — the handoff's literal runnable command `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` will fail at parse time because `--spinoff-binding` is rejected for every subcommand except `load-canonical`/`adjudicate-canonical`, violating the contract that the next-step section must run exactly as written.
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
1. src/main.rs:134-141 (rejection check) + docs/RESUME-g4c.md:12 — the RESUME doc's "runnable now" command (`backfill audit-canonical --spinoff-binding out/rev9-bindings.json`) is rejected by the new acceptance check, which only allows `--spinoff-binding` for `load-canonical`/`adjudicate-canonical`, not `audit-canonical`; the documented next step is not executable as written.
2. src/main.rs:146 — `audit_canonical(&opts)` never accepts or forwards `spinoff_binding`, so even if the rejection in finding 1 were removed, the audit path has no mechanism to consume the frozen bindings, contradicting the doc's claim that the command "reproduces rev 9's inputs bit-for-bit."
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
1. src/pathfold.ts:14-15 — `foldSegments` drops `.` segments (`if (seg === ".") continue;`), contradicting its doc comment's explicit promise that `.` and `..` are "preserved verbatim in the output"; e.g. `foldSegments(".")` returns `[]` instead of the documented `["."]`.
2. src/pathfold.ts:16-19 — `foldSegments` resolves `..` by popping the previous segment instead of preserving it verbatim as documented; e.g. `foldSegments("a/../b")` returns `["b"]` instead of the documented `["a", "..", "b"]`, breaking the load-bearing contract this module states downstream alias-resolution code relies on.
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
1. src/pathfold.ts:13-17 (contradicting doc at src/pathfold.ts:4-7) — WRONG: `foldSegments("a/../b")` resolves to `["b"]` by popping on `..` and dropping `.`, contradicting the doc comment's explicit promise that `.` and `..` are "preserved verbatim in the output"; per the module's stated contract this breaks the downstream alias-resolution stage's ability to handle dot segments itself.
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
1. ci/run-suite.sh:19 — WRONG: `cargo test --workspace 2>&1 | tail -40` is piped without `pipefail` set, so if `cargo test` fails (e.g., exit 101) but `tail` succeeds (exit 0), the pipeline's exit status is 0, causing the script to exit 0 and CI to report green on a failing test suite.
2. ci/run-suite.sh:4-6 — WRONG: the header comment asserts "the script's exit status is the test runner's own exit code," which is false given the missing `pipefail` (see finding 1); this directly misleads on-call engineers who the contract says rely on this comment to debug red/green CI.
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
1. ci/run-suite.sh:19 — `cargo test --workspace 2>&1 | tail -40` is piped without `set -o pipefail` (only `set -eu` is set at ci/run-suite.sh:8), so the pipeline's exit status is `tail`'s (always 0), meaning a failing test suite still makes the script exit 0 and CI report green.
2. ci/run-suite.sh:6-7 — the header comment claims "the script's exit status is the test runner's own exit code, so the CI step fails exactly when the suite fails," which is false given the bug in finding 1, misleading on-call engineers who trust this comment as documented in the task's stated contract.
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
**Judge:** verdict=REJECT (flagged)  found=['mc-05-d1']  false_findings=1  item_pass=False

## baseline — mc-06 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. src/target_spool.rs:32 — (SMELL) `u32::try_from(body.len()).expect(...)` panics instead of returning an error if a single JSON-encoded record exceeds 4GB; given the doc's noted 3-4x JSON blow-up on protobuf bytes this is a latent crash path, though not shown to trigger at current record sizes.
2. docs/target-spool-format.md — (SMELL) the footer description omits the record-count field's byte width (u64/8 bytes), leaving downstream readers built from this doc alone to guess it, risking a misimplemented parser.
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
1. src/target_spool.rs:34 — SMELL: `push()` uses `.expect()` on `u32::try_from(body.len())`, so a serialized record body over 4 GiB panics instead of returning the `io::Result` error the rest of the API promises (no concrete triggering input identified, since `MarketBar` records are expected to be small).
2. src/target_spool.rs (whole file) — SMELL: no unit tests accompany a new integrity-bearing binary format (framing, big-endian length prefix, running SHA-256, footer), despite the doc stating other tooling relies on this format staying accurate.
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
1. src/main.rs:108-118 — SMELL: flag-acceptance checks run before subcommand-name validation, so an unrecognized subcommand paired with a rejected flag (e.g. `foobar --rebuild-index`) surfaces the flag-acceptance error instead of "unknown subcommand"; not incorrect, just a minor message-precedence choice.
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
1. src/main.rs:96-130 (approx., the modified `run` function) — SMELL: the diff updates call sites for `verify_archive`/`load_canonical`/`adjudicate_canonical` to pass new arguments but includes no corresponding changes to those functions' definitions, so arity-compatibility with the new call signatures can't be confirmed from this diff alone.
2. src/main.rs (flag-guard `if` blocks) — SMELL: when `cmd` is unrecognized and a restricted flag is also present, the flag-acceptance error fires before the "unknown subcommand" check, reporting a less-relevant message for typo'd subcommands.
3. src/main.rs (comment above the guard blocks) — SMELL: the comment says `--rebuild-index` is for "the archive walkers" only, but the guard accepts it for both `verify-archive` and `load-canonical`, which isn't clearly justified from the diff's visible context.
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
