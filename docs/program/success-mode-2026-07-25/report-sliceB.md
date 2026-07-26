I’ll mine only the supplied Slice B file list, starting with the 81 Claude clone sessions, then a size-ranked keyword pass over the Codex rollouts. I’ll keep the report read-only and cite only transcript lines I directly inspect.The Claude slice is dominated by reviewer/second-pass/synthesis sessions; I’m separating enacted mechanics from prompt boilerplate. The strongest early candidates are exact-boundary freezes, full-diff recovery after empty structural slices, trait-implementation coverage checks, and tests rejected when they only simulate concurrency sequentially. I’m now checking whether Codex adds genuine debug/fix-round machinery beyond that.## Coverage

- Corpus listed: 488 files; all existed.
- Keyword-skimmed: 81 Claude + 407 Codex JSONL files, streamed line-by-line.
- Deep-skimmed: 10 largest Claude sessions; targeted context reads in 7 Codex rollouts.
- Skipped: no listed files. I did not inspect unlisted transcripts or read any transcript wholesale.

## Findings

### 1. Falsifier-plus-alternative-cause probe ledger

Pattern — Strong reviews state a hypothesis, expected result, falsifier, and competing explanation before each probe, then record the result before continuing. This separates checkout/controller mistakes, test-only code, and genuinely duplicated behavior instead of confirming the first plausible story.

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/23/rollout-2026-07-23T19-29-40-019f91be-11b1-72c1-b3c6-ee6b977b10d9.jsonl:14` — “for each read-only check I’ll state the hypothesis, expected result, falsifier, and an alternative cause”

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/23/rollout-2026-07-23T21-51-26-019f923f-da0c-7731-bbc1-29a48878dcc2.jsonl:28` — “The exact memory keys had no hit, which falsifies a direct indexed B3-remediation note.”

Proposed form — Steering rule and probe-log template.

Confidence — High.

### 2. Empty navigation evidence triggers explicit fallback inspection

Pattern — When a structural slice is empty or navigation tools are unavailable, reviewers do not interpret that as “no findings.” They switch to complete diff, direct source, and caller tracing, while explicitly limiting claims based on the missing tool.

Evidence — `/Users/wesleyjinks/.claude/projects/-Users-wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/0fafd49b-c60d-4446-b7bb-4939da7a5d55.jsonl:19` — “Empty slice — no structural findings pre-computed. Moving to the diff.”

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/23/rollout-2026-07-23T10-15-28-019f8fc2-af64-7770-a101-a8392d8b838f.jsonl:41` — “The navigation tools are not exposed in this session, so I’m continuing with the permitted Git/search evidence.”

Proposed form — Detector: empty slice/tool failure ⇒ mandatory full-diff and caller-audit fallback.

Confidence — High.

### 3. Test causal-power audit

Pattern — Reviewers check whether a test can actually produce the behavior it claims to cover. They caught “concurrency” tests whose synchronous backend and single-threaded executor made the test sequential, so the old broken implementation would pass identically.

Evidence — `/Users/wesleyjinks/.claude/projects/-Users-wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/0fafd49b-c60d-4446-b7bb-4939da7a5d55.jsonl:314` — “The production code is correct; the test won’t catch a regression back to the old double-preflight bug.”

Evidence — `/Users/wesleyjinks/.claude/projects/-Users/wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/ffafe2ad-0363-4043-9775-e198e1790209.jsonl:321` — “The test just doesn’t distinguish it from the old double-preflight bug.”

Proposed form — Test-review detector for immediately-ready futures, single-thread runtimes, absent barriers, and assertions unchanged by reverting the fix.

Confidence — High.

### 4. Entry-path × mode acceptance matrix

Pattern — Good reviewers enumerate all execution chokepoints and mode combinations, not just the path where the feature was first wired. This caught lint bypasses through inbound submit/batch paths and warm-served preflight bypasses.

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/25/rollout-2026-07-25T17-10-54-019f9b8b-bd9f-75c0-8e13-318b01328f7e.jsonl:99` — “A workflow task submitted through `a2a-bridge submit` / JSON-RPC or `run-batch` can still carry … straight into worker prompts”

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/25/rollout-2026-07-25T03-47-28-019f98ac-2cea-76f1-8e07-e04d582e67d3.jsonl:103` — “`preflight = true` is bypassed for served warm workflow runs.”

Proposed form — Acceptance template requiring a matrix of cold/warm, CLI/serve/submit, and `--out`/default modes.

Confidence — High.

### 5. Empty-result artifacts are observable success, not absence

Pattern — Reviewers verify that clean runs still emit a durable result artifact. This preserves the operational distinction between “lint passed” and “lint never ran or failed to write.”

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/25/rollout-2026-07-25T19-04-22-019f9bf3-9e4b-7732-8735-0de4205f1262.jsonl:98` — “a clean result is still the result operators need to distinguish ‘lint passed’ from ‘lint never ran / artifact write failed.’”

Evidence — `/Users/wesleyjinks/.claude/projects/-Users-wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/c2deadb9-47b8-4a9f-a2be-e5feac0fb865.jsonl:16` — “Item 9 incomplete — clean brief-lint runs produce no artifact”

Proposed form — Regression matrix covering empty/non-empty reports with and without output redirection.

Confidence — High.

### 6. Fix rounds preserve the intended failure locus

Pattern — When a cross-cutting behavior change invalidates an old fixture, the fix round restores the fixture’s intended failure point instead of weakening the assertion. A separate compile fix stayed equally narrow: cloning the map key while rechecking cache identity and eviction semantics.

Evidence — `/Users/wesleyjinks/.claude/projects/-Users/wesleyjinks-code--a2a-implement-impl-81776-qo3xg4zy/ab0075d6-09dd-4092-adbf-e0d3f80d3f70.jsonl:392` — “Adding `Update::Text("checkpoint complete")` before `Done` makes the checkpoint response non-empty so the executor proceeds normally to the failing store write.”

Evidence — `/Users/wesleyjinks/.codex/sessions/2026/07/25/rollout-2026-07-25T19-44-38-019f9c18-7c9d-79c0-ac1c-cc736cfdde6a.jsonl:53` — “replacing `entry(cache_key)` with `entry(cache_key.clone())`”

Proposed form — Fix-round clause: repair only the confirmed defect, then re-prove the original failure locus and adjacent invariants.

Confidence — Medium.

## FAILURE nominations

### FAILURE — Structural presence mistaken for behavioral execution

Pattern — One reviewer marked an acceptance item complete because the path and helper existed, without tracing the empty-report branch that returned before writing. A second reader corrected the claim by following the actual state transition.

Evidence — `/Users/wesleyjinks/.claude/projects/-Users-wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/c2deadb9-47b8-4a9f-a2be-e5feac0fb865.jsonl:16` — “Reviewer B’s evidence confirms the path infrastructure exists, not that it fires on clean runs.”

Proposed form — Detector requiring every acceptance PASS to cite an input/state that reaches the claimed side effect.

Confidence — High.

### FAILURE — Fake concurrency oracle

Pattern — A test named for concurrent single-flight used synchronous operations on a single-threaded runtime, so it validated sequential caching while presenting itself as a race test.

Evidence — `/Users/wesleyjinks/.claude/projects/-Users/wesleyjinks-code--a2a-implement-impl-24382-8nsy7nlq/ffafe2ad-0363-4043-9775-e198e1790209.jsonl:321` — “`tokio::join!` is effectively sequential”

Proposed form — Detector signature: concurrency claim plus ready futures, no yield/barrier, and no assertion that fails under the pre-change implementation.

Confidence — High.