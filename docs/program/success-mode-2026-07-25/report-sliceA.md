I’ll mine only the paths in `sliceA-files.txt`, prioritizing by rollout size exactly as requested. I’ll first inventory the corpus without loading whole files, then run a streamed keyword pass, select the largest/highest-signal sessions for bounded context and first/last-line skims, and build findings only from quotes I personally verify at exact line anchors.The manifest contains all 531 advertised rollouts. I’m now ranking them by byte size (metadata only) so the deep sample is not biased by filename order; I’ll separately record any missing paths before scanning content.The compact extractor itself hit a quoting syntax error before reading transcript content. The cause is local and unambiguous: a nested empty-string literal closed the outer `python -c` string; replacing that expression with a precomputed variable should make the first 30 records parse, while any JSON/schema issue would fail afterward at `json.loads` or field access.All 531 paths exist; none has fewer than 50 physical JSONL lines, so the “tiny rollout” exclusion does not remove any file mechanically. The top 65 account for the intended deep-plus-keyword sample; next I’m extracting only compact session metadata and user/assistant message prefixes to identify task families before interpreting keyword hits.I caught an inventory bug before using it in analysis: my byte counter counted literal `\n` escape sequences inside JSON strings, not record terminators. The physical anchor evidence (`sed` near line 42,328 matched `tail`) predicts `wc -l` near 42k for the largest file; if not, the file has an unusual trailing structure. I’m recomputing with record iteration and will use only the corrected counts.The corrected corpus has 724,171 JSONL records; 18 files are under 50 records. I’m treating ranks 1–15 as the deep set and ranks 16–65 as the additional keyword set. The first structured scan excludes developer/system prompt text so the saturated steering language does not masquerade as enacted behavior.The high-signal scan is already surfacing a useful variant beyond the saturated expect/falsify rule: good sessions explicitly mark a malformed probe or wrong path as “not evidence,” then reset to schema/path discovery before updating the hypothesis. I’m now tracing candidate episodes forward to their outcomes and searching specifically for the S11 paired shapes—unsupported behavioral assertion versus read-first correction.I’ve traced several episodes to green outcomes, including an exact 11/11 closure after restoring a dropped inventory obligation and two independent cases where tests were repaired through canonical fixtures while production validation stayed strict. I’m doing the third end-to-end-ish skim now on a bounded implementation session to counterbalance the two very long orchestrator histories.# Success-mode transcript mining report — sliceA

## 1. Coverage

- Corpus manifest: 531 rollout paths; all 531 present, totaling 724,171 JSONL records.

- Ranked all files by byte size.

- Keyword-skimmed the largest 65 rollouts: ranks 1–15 received candidate/context analysis; ranks 16–65 received the additional keyword pass.

- Deep-skimmed first/last approximately 200 records of three sessions:
  - `019f632e-0947-76f1-ba30-fd8fcdf89bfb` — `ssot-agents`
  - `019f5c53-cc73-7092-a5e6-a5ef38f83ef5` — `stockTrading`
  - `019f605b-ee40-74d0-9266-2b56ef9e872a` — `stockTrading`

- Read focused record neighborhoods for selected episodes in the top 15 and for high-signal ranks 44 and 47.

- Content-skipped 466 rollouts: 448 files below rank 65 and all 18 files under 50 records. These received inventory/record-count processing only.

- I did not read any rollout wholesale, semantically inspect ranks 66–531, or establish corpus-wide frequency. No external sources or prior-memory evidence were used.

- Per the read-only slice brief, the report was not written to `~/Documents/success-mining/`.

## 2. Findings

### 1. Probe admissibility before belief updates

**Pattern.** Successful sessions treated malformed commands, incorrect schemas, and zero-test selections as failures of the probe—not evidence about the domain hypothesis. They corrected the probe while explicitly leaving the hypothesis unchanged. This is a distinctive addition to expect/falsify discipline: observations must first pass an evidence-admission check.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:4224` — “That size probe was invalidated by an unmatched shell glob, so it yielded no evidence.”

- `~/.codex/sessions/2026/07/18/rollout-2026-07-18T09-57-47-019f75f2-b265-7502-bf2e-bc324e1898a4.jsonl:11945` — “The first metadata SELECT used a non-existent status column, so it yielded no live evidence.”

- `~/.codex/sessions/2026/07/18/rollout-2026-07-18T10-09-36-019f75fd-830a-7c01-a36d-40395fb4143b.jsonl:12148` — “The first command collected zero tests because `--exact` needs the module-qualified name, so it is not evidence.”

**Proposed form.** Detector signature: flag hypothesis updates following zero selected tests, parse/schema errors, shell expansion failures, or timed-out diagnostics unless the observation is first classified as admissible.

**Confidence.** High — repeated across independent sessions and failure types.

### 2. First-error semantics trigger complete enumeration

**Pattern.** When the agent learned that G11 reports only the first sorted collision, it changed the search topology instead of continuing a fix-and-retry loop. It performed a systemic replay, researched all six latent collisions, and resolved them before the next write attempt. All six then passed together, eliminating a series of expensive transactional retries.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:3582` — “G11 reports only the first sorted overlap (`BPAC`), not the full six-item set.”

- Same file, line 2706 — “The systemic replay has now eliminated first-failure uncertainty.”

- Same file, line 4477 — “Live result: all six G11 collisions and the new episode bounds passed.”

**Proposed form.** Steering rule: once a failing gate is shown to return only its first error, enumerate the complete defect population before the next state-changing retry.

**Confidence.** High — decisive multi-stage enactment with a verified outcome.

### 3. Separate approval, orchestration-yield, and execution clocks

**Pattern.** Good sessions used artifact timestamps and process/table state to decompose apparent latency. A command yielding before final output was not called a timeout, and nine minutes awaiting approval were not attributed to QuestDB. This prevented healthy work from being killed or operational thresholds from being “fixed” for UI latency.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:7207` — “The apparent timeout was only the command yielding before its final output.”

- Same file, line 7227 — “The other ~9 minutes were the command waiting for your approval, not QuestDB stabilization.”

- `~/.codex/sessions/2026/07/14/rollout-2026-07-14T05-21-05-019f605b-ee40-74d0-9266-2b56ef9e872a.jsonl:7001` — “Approval accounted for the long pause; the cached aggregate rerun has only just started executing.”

**Proposed form.** Bridge feature: emit separate timestamps for approval requested/granted, executor start, first process output, yield, and process completion.

**Confidence.** High — repeated and supported by exact timestamps and terminal state.

### 4. Calibrate bounds on the densest representative, then split policies

**Pattern.** A sparse 31-day window passing was not enough to choose a production bound. The agent measured the densest retained month, verified all 192,330 rows bit-exactly, and only then adopted 31-day payload windows. It preserved the independent 366-day count-vector policy and added a regression preventing the two controls from collapsing together.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:40901` — “Before choosing 31 days for production, I’m measuring the densest retained monthly population.”

- Same file, line 40943 — “keep 366-day windows for the count-vector barrier, but cap candidate PGwire payload windows at 31 days.”

- Same file, line 40981 — “Focused regressions are green: 2 passed, 0 failed.”

**Proposed form.** Template clause: every operational cap must name its worst observed representative and identify adjacent controls that must remain independently parameterized.

**Confidence.** High — live validation plus green regression coverage.

### 5. Repair invalid fixtures through canonical constructors

**Pattern.** When strengthened validation broke tests, the successful response was to determine whether production compatibility was required or whether the tests had forged impossible state. In two modules, the agent replaced forged bindings with the canonical test constructor while keeping validation strict. This prevents test maintenance from teaching production code to accept unauthenticated objects.

**Evidence.**

- `~/.codex/sessions/2026/07/15/rollout-2026-07-15T00-43-54-019f6484-8480-7720-a594-3139394fd6fb.jsonl:4696` — “first prove the failures come from test-only forged binding bytes.”

- Same file, line 4839 — “Fixed the four GP1 tests without weakening production validation.”

- `~/.codex/sessions/2026/07/15/rollout-2026-07-15T00-44-01-019f6484-a019-7df0-9a10-93dcc9fd604d.jsonl:4863` — “Migrated both forged GP2 bindings to `frozen_identity_binding_for_test`; validation remains strict.”

**Proposed form.** Steering rule: when validation breaks a test, first classify the fixture as constructible or forged; repair forged fixtures through the production-equivalent constructor.

**Confidence.** High — two independent enactments with full module suites green.

### 6. Broader gates do not automatically subsume narrower proofs

**Pattern.** A full physical-collision scan looked stronger than the old inventory gate but proved a different property. Review caught that noncolliding extra current-version rows could now escape. The agent restored exact-set inventory proof alongside the broad collision scan, and the replay suite returned to 11/11.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:42552` — “the full collision scan correctly ignores unrelated noncolliding rows, but that also removed the separate ‘no extra current-version Polygon rows’ inventory proof.”

- Same file, line 42632 — “every closure surface now marks admission pending, `git diff --check` is green, and replay is 11/11.”

**Proposed form.** Steering rule: before replacing a gate with a broader scan, list the old gate’s predicates and retain every predicate not logically implied by the new scan.

**Confidence.** High — concrete escaped input, correction, and verified closure.

### 7. Enforce lexical canonicality above permissive parsers

**Pattern.** The session discovered that library parsers accepted non-zero-padded dates and leading-zero integers. At an identity-bearing archive boundary, semantic parse success was therefore insufficient. The fix required round-trip canonical spelling and added negative cases, closing alternate encodings without inventing a new parser.

**Evidence.**

- `~/.codex/sessions/2026/07/13/rollout-2026-07-13T10-33-43-019f5c53-cc73-7092-a5e6-a5ef38f83ef5.jsonl:42588` — “Chrono accepts non-zero-padded dates and integer parsing accepts leading zeros.”

- Same line — “I’ve made the archive grammar round-trip canonical (`YYYY-MM-DD`, canonical decimal ID/epoch) and added negatives.”

- Same file, line 42632 — “replay is 11/11.”

**Proposed form.** Template clause: for authenticated or identity-bearing text, require `encode(parse(token)) == token` and test accepted library aliases as negatives.

**Confidence.** Medium — decisive but confined to one implementation episode.

### 8. One discriminating teardown before the single retry

**Pattern.** After pytest stalled, the agent interrupted once to capture the waiting stack, tested `import hypothesis` separately, then performed exactly one fresh-process retry. Reproduction ended further cycling and produced an honest incomplete-suite report with a precise stale-entry-point boundary. The distinctive mechanism beyond a convergence cap is the small discriminator between teardown and retry.

**Evidence.**

- `~/.codex/sessions/2026/07/14/rollout-2026-07-14T05-21-05-019f605b-ee40-74d0-9266-2b56ef9e872a.jsonl:7065` — “A standalone `import hypothesis` distinguishes them.”

- Same file, line 7071 — “I’m rerunning pytest once in a fresh process.”

- Same file, line 7091 — “The fresh pytest process reproduced the same post-test stall.”

- Same file, line 7097 — “I’m leaving the shared virtualenv untouched and recording pytest as incomplete.”

**Proposed form.** Steering rule: after a suspected environmental stall, capture one teardown trace, run one minimal discriminator, allow one fresh-process retry, then stop on reproduction.

**Confidence.** High — the bounded sequence isolated the failure without dependency churn.

## 3. FAILURE nominations

### FAILURE 1. Fact-shaped hypotheses contaminated a cleanroom brief

**Pattern.** A controller asked a reader to inspect the live repository but seeded the prompt with provider behavior labeled as “Current facts” and a specific protocol staging shape. The read-first pass corrected both the walk boundary and the relationship between C-PORT-9A and plan/observe/verify. The recovery was good, but a less skeptical reader could have laundered those premises into the design.

**Evidence.**

- `~/.codex/sessions/2026/07/14/rollout-2026-07-14T18-29-49-019f632e-0947-76f1-ba30-fd8fcdf89bfb.jsonl:42035` — “Current facts: Claude 2.1.216 documents managed then CLI agents then project then user then plugin, discovers project agents by walking up from cwd.”

- Same line — “Propose: exact profile/facade/API and types; pure-data plan-observe-verify staging.”

- Same file, line 42165 — “One correction to the brief up front. C-PORT-9A has no plan-observe-verify staging.”

- Same file, line 42188 — “Claude scans from CWD only to the repository root, with nearest-wins documented.”

**Proposed form.** Detector signature: cleanroom prompts must label behavioral premises as either `FACT — path:line/source` or `HYPOTHESIS — verify`; reject uncited “current facts.”

**Confidence.** High — direct assertion/correction pair, followed by explicit normative-design repair.

## 4. Anti-findings

### Tool-protocol discipline around the wrong executable

**Pattern.** The patch recovery looked careful because every retry preserved the intended write boundary, but multiple transport variants were tried before checking whether `command -v apply_patch` identified a real patch utility. It was actually an app arg0 dispatcher and hung even on `--help`. Fingerprinting the executable immediately after the first unexplained hang would have removed several cycles.

**Evidence.**

- `~/.codex/sessions/2026/07/14/rollout-2026-07-14T18-29-49-019f632e-0947-76f1-ba30-fd8fcdf89bfb.jsonl:42198` — “The repository patch service is still wedged—even a 25-line add has produced no result after a full minute.”

- Same file, line 42268 — “Both wrapper and interactive stdin paths failed without writing the tree.”

- Same file, line 42309 — “The executable at `command -v apply_patch` is not the patch utility.”

**Proposed form.** Detector signature: after the first unexpected tool hang, require executable identity/help/version inspection before retrying with a different transport.

**Confidence.** Medium — one clear churn episode with an eventually confirmed cause.