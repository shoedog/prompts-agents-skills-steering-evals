# Slice F report — slicing/prism development sessions (S11 trial)

[Provenance: mined and authored by the sonnet slice-F agent 2026-07-25; the agent's own
file-write was harness-blocked (subagents return text, not files), so the orchestrator
persisted this verbatim from the agent's final report.]

Miner: Sonnet 5 (reader role). Per slice-F.md, findings below use strict EVIDENCE / INTERPRETATION separation: EVIDENCE blocks contain only file:line + verbatim quotes (≤25 words, contiguous spans I directly read); INTERPRETATION blocks contain my reading. Quotes were re-extracted via direct JSON field access (not eyeballed from grep context) and spot-verified a second time before inclusion.

## Coverage

**Claude sessions (14/14 opened):**
- Deep-mined (full-length, keyword-anchored navigation through the entire file): `f14884e6` (63,393 lines — already-mined patterns L40707/L40863/L57056-57222 skipped per brief; mined for *additional* patterns), `73fbee07` (19,939 lines), `cfb7783b` (10,441 lines).
- Substantially read (keyword scan + multiple targeted context reads each): `a5567ef8` (144 lines), `448072d5` (133), `639ff586` (131), `26009bad` (98), `4fbce847` (81) — these five turned out to be one recurring session type (a "second-pass" self-review dispatch; see Finding 2).
- Lightly scanned: `29ceeab0` (41 lines, 3 keyword hits, nothing distinct beyond the prism-nav skill's own doc text).
- Confirmed near-empty (metadata/attachments only, no assistant reasoning — verified via type-distribution check before skipping): `96f11566`, `bedbda8d`, `e375320a`, `15a3c6c5`, `c2debc40` (1-19 lines each).

**Codex rollouts (407/407 keyword-scanned; a minority deep-read):**
- Built a batch scanner (~30 markers: verify/refut/regression/invariant/caught/overclaim/root-caus/silent/fabricat/etc., extracting text from message/reasoning/function_call/function_call_output payloads) and ran it over all 407 files (105,420 lines total, 9s runtime). Every file produced ≥1 hit, so the "skip <50-line rollouts unless hit" rule in practice meant none were mechanically skippable; I triaged by hit density instead.
- Deep-read with full context extraction: the top 3 by size — `rollout-2026-06-22T18-08-24` (12,785 lines, 2,544 hits), `rollout-2026-06-29T19-47-18` (11,687 lines, 1,150 hits), `rollout-2026-06-18T20-59-08` (6,551 lines, 803 hits).
- **Gap, reported honestly:** files ranked #4–10 by size (1,786 down to 727 lines) were keyword-scanned but not context-deep-read — I prioritized citation quality on the top 3 plus ~20 hit-anchored spot-verifications across other dates (06/07, 06/10, 06/11, 06/12, 06/13×3, 06/14×2, 06/16, 06/17×3, 06/18, 06/21, 07/03×2, 07/04×2) once cross-file recurrence made individual findings strong. A dedicated pass on #4–10 might surface more.
- ~50 files were a repeated 12-line template (an isolated codex call acting as a pure JSON adjudicator between prism and a compiler oracle on disputed call-graph edges — automated harness infrastructure, not narrative sessions). Spot-checked one in full; did not mine the rest individually as they're mechanically identical.

**Not covered:** systematic reading of codex files #4–10 by size; the ~340 codex files with <20 keyword hits beyond their automated snippets; sidechain/subagent-internal transcripts that may exist outside these 421 files.

---

## Findings

### 1. Safe-failure-direction as a declared, reviewer-verified design invariant

**EVIDENCE:**
- `f14884e6-cefd-43bc-b20c-e1352316304f.jsonl:5455` — design-spec document (Write tool content), §7 Invariants: "every unresolved/external/ambiguous path falls through unchanged. The model never *guesses* a file."
- `f14884e6-cefd-43bc-b20c-e1352316304f.jsonl:9834` — subagent implementation report, after a failing-test-first TDD cycle: "ambiguous or zero mappings still fall through"
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — durable `pipeline-lessons.md`, doctrine #7: "State the direction in the brief; reviewers verify each ambiguity resolves toward it."

**INTERPRETATION:** Across two separate claude sessions (and, per my read, echoed in the Rust source itself — e.g. a `debug_assert!` in a codex-read file that "fail[s] loudly in debug so a future non-Variable in a chain surfaces here instead of silently fabricating an empty node," `rollout-2026-06-10T14-06-30-...jsonl:155`, not counted as a primary citation above since I didn't re-verify it as carefully), prism's team treats "which direction is safe to fail toward" as a first-class, *named* design input rather than an implicit judgment call. It gets a standard spec section (I saw "## Recall-Safety Invariant" as a section header a third time at `73fbee07...jsonl:263`), gets enforced by TDD (write the ambiguous-case test, confirm it fails, implement the fall-through), and gets written into review instructions as a checkable property ("reviewers verify each ambiguity resolves toward it") rather than left to reviewer intuition. This is the recall-safety pattern's strongest form: not just "the code happens to be conservative" but "the brief states the unsafe direction; the reviewer's job includes checking every ambiguity resolves away from it." Proposed form: steering rule / template clause — any spec for a fact-producing system should have a mandatory "safe failure direction" section, and review prompts should ask reviewers to verify ambiguities resolve toward it. Confidence: **high** (3 independent enactments across 2 files, at design-doc, implementation, and review-protocol layers).

---

### 2. Second-pass self-review under a read-only bounded contract, with a mandatory overclaim register

**EVIDENCE:**
- `26009bad-171b-4fdc-ac43-63984816d9da.jsonl:5` — dispatch prompt: "You MAY use READ-ONLY tools (read/list/grep, `git diff`/`log`/`show`) to VERIFY your draft's claims against the ACTUAL spec + code."
- `26009bad-171b-4fdc-ac43-63984816d9da.jsonl:97` — resulting register entry: "MINOR #4 (`index_module_deferred`) was overstated; the spec already hedges it."
- `639ff586-aca2-4811-b0d6-194ccd0c8307.jsonl:94` — same protocol, different session, catching a real spec gap: "the dominant modern JS/TS export idiom) will NOT resolve via R4c, and the spec never says so."

**INTERPRETATION:** This is a distinct dispatch template — nearly identical boilerplate ("READ-ONLY + BOUNDED CONTRACT — follow exactly") recurs verbatim across 5 of the 14 claude sessions (`a5567ef8`, `448072d5`, `639ff586`, `26009bad`, `4fbce847`), always structured the same way: hand the model **its own first-pass draft**, restrict it to read-only tools, and require it to produce a **"GAPS/UNCERTAINTIES REGISTER"** — an explicit, numbered list of what the draft "got wrong, overstated, or left unverified" — *before* producing the refined output. I also found the identical framing in codex sessions, e.g. `rollout-2026-06-13T11-06-19-019ec1f2-de6f-7780-adc3-75c9252b09a3.jsonl:9`: "verify each draft claim against code rather than relying on the first-pass notes," and `rollout-2026-06-11T11-52-55-019eb7d0-cdd2-78d0-900f-dceb8de6f570.jsonl:28`: "reading the live files rather than trusting the pasted patch" — suggesting the practice is used cross-model, not just as a claude-specific habit. This is related to but distinct from the already-mined "verify-first premise measurement" (that pattern checks a premise before starting work; this one forces a *second pass over one's own completed analysis* and produces a structured self-downgrade record as a required artifact, not just a verification step). Proposed form: template clause — a reusable "second-pass, read-only, produce an overclaim register before refining" prompt, usable by any agent re-checking its own output. Confidence: **high** (5 claude enactments + cross-model echoes in codex).

---

### 3. "Line anchors rot; symbols don't" — a citation-format rule born, then adopted a day later in a different tool

**EVIDENCE:**
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — `pipeline-lessons.md`, rule 6: "Briefs written against a moving main should name symbols to grep (`property_accesses` → every plumbing site) rather than line numbers, or mark anchors as hints."
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — same rule, stated cause: "Post-#158 anchors were stale within one round."
- `rollout-2026-07-04T17-05-33-019f2f61-4b63-7a33-8fec-c6f944edc1cb.jsonl:15` — a codex task brief written the next day: "Locate code by the SYMBOLS named here; line anchors are hints that rot."

**INTERPRETATION:** This is the single most S11-relevant finding in the slice: it is prism's own team discovering, inside their own tooling corpus, exactly the citation-rot failure mode this trial is designed to catch — a line-number citation that was accurate when written and silently wrong by the next round — and then converting it into a durable, portable rule. The chain is dated: the lesson doc (`73fbee07`) is timestamped "2026-07-02 → 2026-07-03"; the adopting codex brief is `rollout-2026-07-04T17-05-33`, one day later, and literally reuses the word "rot." I found the same clause again in a second, independent codex brief the same day (`rollout-2026-07-04T22-46-30-019f3099-7064-77a2-9382-14e039b24141.jsonl:15`: "Locate code by the SYMBOLS named here; line anchors are hints"), and that brief additionally uses **"[ANCHOR ROT]"** as a first-class finding-severity tag — the concept became load-bearing vocabulary, not just a one-off caveat. Proposed form: steering rule — cross-round or cross-session briefs should cite grep-able symbols, not line numbers, or explicitly flag anchors as hints; this is directly actionable for any multi-session agent pipeline (and for this very mining program's own citation discipline). Confidence: **high** (a traced, dated propagation from lesson to adoption, across two different session files).

---

### 4. Hypothesis-driven debugging + a fail-loud gate that proved itself on first live use

**EVIDENCE:**
- `cfb7783b-25ea-489c-8ff1-bded11daafac.jsonl:4428` — "my original diagnosis was wrong — there is no prism cache bug. Fable caught it and I confirmed it."
- `cfb7783b-25ea-489c-8ff1-bded11daafac.jsonl:5001` — "on its very first live use, it caught a real regression I'd introduced, and the debugging discipline paid off exactly as designed."
- `cfb7783b-25ea-489c-8ff1-bded11daafac.jsonl:5049` — "turning what would have been another silent zero-prism run into a five-minute fix."

**INTERPRETATION:** This transcript appears to be the origin/first-validation session for what is now the user's global CLAUDE.md "debugging discipline" steering rule (the session literally writes to progress.md at line 4470: "CLAUDE.md gained a debugging-discipline rule 2026-07-05 — hypothesis+falsifier before each probe, name an alternative same-symptom cause + separating observation before fixing"). The full arc, all in one session: (1) the agent has a wrong diagnosis ("cache not shared"); (2) a peer agent (Fable) proposes an alternative (binary-version skew); (3) rather than accepting either uncritically, the agent finds a separating observation (matched binaries → 0.9s warm init) and confirms Fable's alternative; (4) the discipline is written down explicitly; (5) minutes later, applying that same discipline, a newly-added "warm-gate" check fires on a real bug the agent itself introduced (a clap arg-order mistake: `--cache-dir` must precede the subcommand); (6) rather than accept the first plausible cause, the agent rules out two alternatives before pinning the real one. This is a rare case where the transcript shows a practice declared and then *immediately, empirically* paying off, not just asserted as good practice — high evidentiary value regardless of the CLAUDE.md provenance question. Proposed form: this is already a steering rule in this user's environment; the value here is the concrete before/after proof-of-work, useful as a worked example when explaining the rule to other agents/users. Confidence: **high** (single session, but a complete, decisive, multi-step causal chain).

---

### 5. A caught regression class immediately rewrites the review protocol

**EVIDENCE:**
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — "a P9 fix wave restructured candidate extraction to fix a shadow-detection MAJOR and silently regressed *caller attribution*"
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — the adjustment: "the re-review prompt must explicitly ask \"what behavior did the restructure carry, and does it still hold?\""
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15671` — confirmed operationalized one round later: "grep-symbols over line anchors in briefs, restructure-aware re-review prompts, and an explicit safe-failure-direction per brief"

**INTERPRETATION:** A concrete failure (fixing one bug silently broke unrelated caller-attribution behavior; "only the re-re-review caught it") is traced to a *class* ("restructures regress orthogonally" — code that moves/reshapes rather than patches in place tends to carry hidden behavior with it) and converted into a standing change to the re-review prompt template, which I then confirmed was actually used in the next round rather than just proposed. This is a tighter, more mechanistic sibling of the known-catalog "design-review ladder" — the interesting part isn't that there's a review ladder, it's that a *specific failure mode discovered mid-pipeline* rewrote a specific *prompt clause* within the same session, with the change traceable to the next round's actual brief text. Proposed form: bridge feature / detector signature — when a fix wave is classified as a restructure (moves or reshapes existing code) rather than a patch, automatically add "what behavior did this carry, and does it still hold?" to the re-review prompt. Confidence: **high** (declared, then confirmed operationalized in the same transcript).

---

### 6. Never trust a bare exit code — triage "harness noise" from a real regression via the artifact

**EVIDENCE:**
- `rollout-2026-06-18T20-59-08-019eddd1-66f7-7c23-9f0b-9f8635076a77.jsonl:348` — "The quick run exited `2` without stdout, which the phase3 handoff notes can mean `baseline_invalid` rather than a regression."
- `rollout-2026-06-29T19-47-18-019f1635-9538-7473-ab57-ea4fefd34ec3.jsonl:1594` — "The quick run is the known non-regression class: `sut_error_rate` is 0.0, while `baseline_invalid` is true from corpus SHA drift"
- `rollout-2026-06-22T18-08-24-019ef1ce-87a8-7d72-9aa4-f2707fe7fdf8.jsonl:9677` — "I'm reading that run metadata directly rather than relying on the silent exit code."

**INTERPRETATION:** This recurs across 3 independent codex sessions spanning three weeks (06-18, 06-22, 06-29), always the same shape: the benchmark harness can exit non-zero or silently for reasons that are *not* a real regression (stale corpus SHA, oracle errors, a pre-existing "baseline_invalid" condition), and the disciplined move every time is to open the actual run-report JSON and read the named invalidity reason rather than trust the process-level signal (exit code, blank stdout). A fourth instance in the same file as the first (`rollout-2026-06-18T20-59-08...jsonl:1118`: "I'm going to inspect the fresh Tier-A report artifacts to distinguish an actual regression from the baseline-validity drift we saw before") shows this specific agent applying its own earlier lesson later in the same session. This is squarely an S11-relevant success shape: refusing to let a cheap proxy signal (exit code) stand in for reading the actual evidence artifact, with a named, recognized "known non-regression class" taxonomy to prevent both false alarms and (more importantly) prevent a real regression from being waved off as "probably just the known noise." Proposed form: detector signature / template clause — any harness-wrapping agent prompt should instruct: on non-zero/silent exit, read the artifact's structured invalidity reason before classifying pass/fail. Confidence: **high** (4 citations, 3 independent files, one self-recurrence).

---

### 7. Ledger + handoff survives compaction and cross-agent handoffs, including explicit file-ownership locking

**EVIDENCE:**
- `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:15627` — `pipeline-lessons.md` rule 8: "Both saved this execution across multiple compactions with zero re-dispatched work."
- `cfb7783b-25ea-489c-8ff1-bded11daafac.jsonl:12` — a brand-new session resuming that exact handoff: "resume with a plain \"continue\" and the handoff + ledger will carry it."
- `rollout-2026-06-22T18-08-24-019ef1ce-87a8-7d72-9aa4-f2707fe7fdf8.jsonl:65` — a handoff doc read mid-session enforcing cross-agent coordination: "Another LLM is resolving it (owns `src/repo_loader.rs` right now — do NOT touch)."

**INTERPRETATION:** I can directly observe the mechanism working, not just being described: `73fbee07` declares the ledger+handoff discipline and claims it survived several compactions; `cfb7783b` is a **different session** that opens by literally resuming from that same handoff chain, and its first substantive user turn confirms the resume worked ("adjudication is on batch 4 of 7... the P13 codex implementer is still working... The ledger has everything blow-by-blow"). Separately, in the codex corpus, the same handoff-doc mechanism is used not just for temporal continuity but for **concurrent-agent mutual exclusion** — a handoff doc explicitly marks a file as owned by another running agent, with an instruction not to touch it, which is a lightweight lock protocol implemented entirely in a markdown doc rather than any tooling. Proposed form: doc template / bridge feature — a standard handoff-doc slot for "currently owned by / do not touch," separate from the "where things stand" narrative section. Confidence: **high** (mechanism observed working across a real session boundary, plus a distinct concurrent-ownership use).

---

### 8. Cross-session memory bootstrap where each rule carries the incident that justified it

**EVIDENCE:**
- `f14884e6-cefd-43bc-b20c-e1352316304f.jsonl:24` — session-opening move: "I'll start by orienting myself: verifying the git state and reading the three context files."
- `f14884e6-cefd-43bc-b20c-e1352316304f.jsonl:47` — durable workflow-preference memory, read at that session's start: "This loop caught two critical bugs and four important issues across rounds 1-4 of the data-flow-visualization PR (#85) that internal review missed."
- `f14884e6-cefd-43bc-b20c-e1352316304f.jsonl:45` — a second memory file read in the same bootstrap, whose frontmatter records `originSessionId: cdced055-3b42-4b98-b70f-c0d9d31fc14c` — a different, earlier session than the one reading it.

**INTERPRETATION:** At session start, before touching code, the agent reads a stack of documents in order: a handoff doc, a design spec, a codex spec-review record, then two durable memory files — one project-state ("where Phase-IP stands"), one workflow-preference ("how this user likes reviews done"). The workflow-preference file is structured so every rule has an explicit "Why:" clause citing a specific past incident and its outcome (the citation above; the same file also justifies a force-push-squash policy with "Round-3 review flagged a bisectability gap; user picked option (b)... without hesitation"). The `originSessionId` metadata is the load-bearing proof this isn't just an in-session note — it's evidence the memory was authored in a genuinely earlier, different session and successfully informed a later one, which is the "durable-store hygiene" class the slice brief flagged as likely under-represented. Proposed form: memory-file template — every durable workflow rule should carry a "Why" pointing at the specific incident (PR #, round #, or dated event) that justified it, not just the rule; this makes rules auditable and harder to silently drop. Confidence: **medium-high** (rich single-file evidence; I did not find a second independent instance of the "Why:"-annotated format elsewhere in my coverage, so I can't yet claim this specific *format* recurs, though the underlying read-memory-at-bootstrap behavior clearly does, e.g. Finding 7).

---

### 9. A durable, greppable index of past sessions, reused with an explicit re-verification caveat

**EVIDENCE:**
- `rollout-2026-06-22T18-08-24-019ef1ce-87a8-7d72-9aa4-f2707fe7fdf8.jsonl:2205` — task-group memory file content: "re-check branch names, PR numbers, and exact tests if the checkout or failure surface has changed"
- `rollout-2026-06-22T18-08-24-019ef1ce-87a8-7d72-9aa4-f2707fe7fdf8.jsonl:2205` — an index entry inside the same file: "root-caused the repo_loader workspace-members regression behind PR #124"

**INTERPRETATION:** Separately from claude's project-memory files (Finding 8), codex has its own durable cross-session mechanism at `~/.codex/memories/skills/<task-group>/`: an accumulating index of `rollout_summaries/*.md` entries, each tagged with cwd, source rollout path, timestamp, thread ID, and a one-line outcome. What makes this a success pattern rather than just a log is the explicit `reuse_rule` clause pairing reuse with a recheck condition — the memory is licensed for reuse *only* if the caveat ("branch names, PR numbers, exact tests... checkout or failure surface") still holds, which is exactly the kind of grounding discipline that prevents stale-precedent errors. This is a second, independently-evolved implementation of the same underlying principle as Finding 8 (durable, incident-grounded, reuse-gated memory), built on a different agent platform — suggestive that the principle itself, not the specific file format, is what's worth extracting. Proposed form: doc/bridge feature — any cross-session memory index should pair each reusable entry with an explicit "safe to reuse if / recheck if" condition, not just a summary. Confidence: **medium** (single file; I did not deep-read enough other codex sessions referencing this same task-group index to confirm the reuse actually happened downstream, only that the caveat and precedent were both present).

---

## FAILURE nominations

None with a citable transcript basis. I specifically searched both corpora for wasted-effort/hindsight/should-have-caught language (`wasted`, `in hindsight`, `should have caught`, `went unnoticed`, `wrong assum...`) and found only cases where a *reviewer* was flagging a hypothetical risk pre-emptively (success shape, not failure) or where a stall was worked through methodically to a correct resolution. This slice's corpus is unusually weighted toward caught-and-fixed issues — plausibly because prism's own pipeline (TDD + dual review + regression pinning, per Findings 1–6) suppresses the kind of silent, durable failure this program looks for. I would not conclude failures are absent, only that I did not find one meeting the citation bar within my coverage.

## Anti-findings

None found meeting the citation bar. I looked specifically at a long silent-Cargo-process stall in `rollout-2026-06-22T18-08-24...jsonl` (roughly lines 10378–10555) as a candidate — many turns spent polling a hung build — but the resolution was methodical (ruled out shell path, internal lock, cross-repo contention, in that order, before isolating the cause) and correct, so it reads as unglamorous-but-working process discipline, not a practice that looked good and failed.

## Recurrence note (already-mined pattern, fresh citation)

Verify-first premise measurement (already mined at `f14884e6:L40707`) recurs with a fresh, concrete catch at `73fbee07-2241-4f0a-8f99-923e29dc04ef.jsonl:28`: "I'll start by verifying the seeded map against the actual repo layout (the brief itself warns of drift)" — the brief's own seeded file-tree map was checked against `ls` output before subagents were dispatched against it. Not counted as a primary finding per the skip instruction; noted per the "recurrence notes with fresh citations welcome" allowance.
