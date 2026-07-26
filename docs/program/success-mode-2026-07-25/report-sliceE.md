I’ll mine only the Slice E file list, using the required two-pass method: first marker scans with bounded context, then deep skims of the largest sessions/rollouts. I’ll keep evidence and interpretation separate, verify every cited line/quote, and remain read-only.The corpus is present and readable: 77 files total (13 Claude, 64 Codex), with no missing paths. The initial scan found 289 marker-bearing records but is noisy because tool commands and embedded instructions dominate; I’m narrowing the read to user/assistant/tool-result records and will cite only transcript lines whose text I re-open and verify.Several high-value patterns are emerging beyond the catalog: reviewers repeatedly found defects by tracing every execution entry path (cold, warm/dispatcher, and direct A2A), and they treated green focused tests as insufficient when the fixture did not exercise the newly identified state. I’m now doing the citation pass—re-opening exact physical lines and extracting short verbatim quotes—before drafting the report.# Coverage

Opened and keyword-scanned all 77 listed files: 13 Claude and 64 Codex. Deep-skimmed the 8 largest Claude sessions and 10 largest Codex rollouts, with targeted spot checks elsewhere. Eleven files under 50 lines were keyword-only. I did not read every raw tool/developer payload end-to-end. The requested report file could not be saved because `~/Documents/success-mining` is read-only.

# Findings

## 1. Current-tree citation gate

**EVIDENCE**

- `~/.claude/projects/-Users-wesleyjinks-code-a2a-bridge/18df8fb0-7984-47a0-ba3b-05993d525bd2.jsonl:108` — “All five code citations verified; the spec is not in the repo.”
- `~/.codex/sessions/2026/07/25/rollout-2026-07-25T18-19-07-019f9bca-33d2-7d80-8c67-80fbc297cdaf.jsonl:78` — “I confirmed the persistent checkpoint schema stores only `output TEXT` plus status/usage, not raw bytes or segment metadata.”
- `~/.codex/sessions/2026/07/25/rollout-2026-07-25T19-48-21-019f9c1b-e5bc-7ab3-aace-0baf31c65e29.jsonl:147` — “The draft’s checkout anchor was wrong for this run.”

**INTERPRETATION**

Pattern: reviewers rechecked the live checkout and artifact presence before trusting inherited claims, then retained only code-grounded conclusions. This prevented stale-head and absent-spec assumptions from becoming authoritative findings.

**Proposed form:** steering rule requiring current `HEAD`, artifact presence, and exact code anchors before section-level adjudication.

**Confidence:** High.

## 2. Alternative-path scope correction

**EVIDENCE**

- `~/.claude/projects/-Users-wesleyjinks-code-a2a-bridge/0986fd17-ee31-4126-a41f-bb12397c908b.jsonl:150` — “five sequential data layers all carry flat `String` outputs with no segment metadata”
- `~/.claude/projects/-Users-wesleyjinks-code-a2a-bridge/18df8fb0-7984-47a0-ba3b-05993d525bd2.jsonl:108` — “I did not explore whether the cut could be applied entirely inside the translator.”
- Same line — “The blast radius I described is real only if the spec requires threading provenance METADATA.”

**INTERPRETATION**

Pattern: the second pass distinguished a worst-case metadata-propagation architecture from a smaller translator-local alternative, correcting an over-sized implementation estimate. This makes planning more precise and avoids unnecessary redesign.

**Proposed form:** design-review template requiring at least one lower-cost implementation path and explicit scope assumptions.

**Confidence:** Medium.

## 3. All-entry-path caller census

**EVIDENCE**

- `~/.codex/sessions/2026/07/25/rollout-2026-07-25T11-11-28-019f9a42-add1-7960-85bc-fc5b615c7cf8.jsonl:117` — “I’m checking other turn-harvest seams because the task says the distinct empty-final failure should be inherited by all callers”
- `...11-11-28-019f9a42-add1-7960-85bc-fc5b615c7cf8.jsonl:158` — “Warm served workflows bypass the new preflight/fallback ladder entirely.”
- `...11-11-28-019f9a42-add1-7960-85bc-fc5b615c7cf8.jsonl:189` — “Non-workflow local A2A turns still treat no-text `Done` as success.”

**INTERPRETATION**

Pattern: the reviewer followed the feature through cold workflow, warm dispatcher, and direct A2A paths instead of trusting one green branch. That exposed multiple concrete bypasses before merge.

**Proposed form:** bridge feature requiring an entry-path matrix and one negative regression per path.

**Confidence:** High.

## 4. Green-test versus state-coverage audit

**EVIDENCE**

- `~/.codex/sessions/2026/07/19/rollout-2026-07-19T11-10-57-019f7b5c-0c45-7111-a452-8a05985870e0.jsonl:502` — “The focused reruns are green: transaction 20/0, state/root/locks 15/0, preflight 11/0”
- `~/.codex/sessions/2026/07/19/rollout-2026-07-19T11-51-49-019f7b81-735a-7e53-8340-449b5b68040c.jsonl:614` — “I found two contract-level reducer scenarios worth proving from the code”
- Same rollout `:652` — “They do not cover the two newly identified states”

**INTERPRETATION**

Pattern: green focused suites were treated as evidence for named fixtures only; the reviewer compared those fixtures against newly constructed counterexample states and kept the residuals open.

**Proposed form:** test report field distinguishing passed scenarios from uncovered state dimensions, especially time, purpose, topology, and caller path.

**Confidence:** High.

## 5. Environment refusal separated from code failure

**EVIDENCE**

- `~/.codex/sessions/2026/07/19/rollout-2026-07-19T12-50-27-019f7bb7-23c7-7763-b26b-509fe0dc34d3.jsonl:401` — “that is an execution-environment refusal, not a code result.”
- Same line — “I’m rerunning the same bounded local tests with only the filesystem permission needed for their temp fixtures”
- Same rollout `:491` — “The residuals are structural rather than failures of those named tests.”

**INTERPRETATION**

Pattern: the worker classified setup failure separately, reran the identical bounded tests with minimal capability, and still reported remaining structural issues. This avoids both false regressions and false closure.

**Proposed form:** detector signature for `setup_incomplete` versus test failure, with same-command retry and preserved offline scope.

**Confidence:** High.

## 6. Minimal host-semantics probe

**EVIDENCE**

- `~/.codex/sessions/2026/07/19/rollout-2026-07-19T11-10-57-019f7b5c-0c45-7111-a452-8a05985870e0.jsonl:279` — “If macOS `flock` makes two separate opens in one process conflict, the file lock still closes that gap”
- Same rollout `:300` — “The probe returned `second_blocked`”
- Same line — “the file lock closes the independently reopened-root case as well.”

**INTERPRETATION**

Pattern: an uncertain kernel/topology assumption was reduced to a disposable probe with competing predicted outcomes, then the result changed the adjudication. This is a compact way to resolve platform semantics without speculative reasoning.

**Proposed form:** steering template: hypothesis → expected/falsifying observation → bounded probe → result → disposition.

**Confidence:** Medium.

## 7. Explicit synthetic/provider topology boundaries

**EVIDENCE**

- `~/.codex/sessions/2026/07/18/rollout-2026-07-18T21-56-31-019f7884-b8e8-7842-9b71-30f25d5a507c.jsonl:244` — “The injected SIGINT/SIGTERM selector coverage is honestly separate from real OS delivery”
- Same line — “explicit unexercised boundary”
- `~/.codex/sessions/2026/07/16/rollout-2026-07-16T12-17-31-019f6c25-e9b1-73b0-bdf1-503bb79a2229.jsonl:137` — “the current binary explicitly provider-unexercised.”

**INTERPRETATION**

Pattern: test evidence was labeled by topology—synthetic selector injection, real OS delivery, provider execution, and host/container behavior were not conflated. This kept degraded-path conclusions honest.

**Proposed form:** evidence schema fields for execution topology and unexercised boundaries.

**Confidence:** High.

# FAILURE nominations

## FAILURE — First-pass review asserted against an absent artifact

**EVIDENCE**

- `~/.codex/sessions/2026/07/25/rollout-2026-07-25T19-48-21-019f9c1b-e5bc-7ab3-aace-0baf31c65e29.jsonl:26` — “current HEAD is `5b1b97a...`, not the draft’s `65e38a9d...`”
- Same rollout `:147` — “The draft overstated that it had verified the ‘actual spec.’”
- `~/.claude/projects/-Users-wesleyjinks-code-a2a-bridge/18df8fb0-7984-47a0-ba3b-05993d525bd2.jsonl:108` — “my draft’s section-level claims rest entirely on my paraphrases of it.”

**INTERPRETATION**

The initial review produced authoritative-looking section findings without verifying the source artifact or exact checkout. A later pass corrected the head, marked the spec unavailable, and retracted unsupported claims.

**Proposed form:** detector blocking section-level verdicts when the cited artifact/path/hash is absent or the review head differs from the draft.

**Confidence:** High.

