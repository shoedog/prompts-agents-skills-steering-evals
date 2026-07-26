# Slice C mining report — claude sessions in stockTrading

[Provenance: mined and authored by the sonnet slice-C agent 2026-07-25; the agent's own
file-write was harness-blocked (subagents return text, not files), so the orchestrator
persisted this verbatim from the agent's final report.]

Miner: sonnet. Corpus: 13 files per `sliceC-files.txt`. Citations use `<shortId>:<line>`
(shortId = first 8 hex chars of the session filename); line numbers are raw JSONL line
numbers in that file.

## Coverage

**Opened (linear read of most/all substantive turns):**
- `93bbfef1` (11 lines), `fe40f445` (12 lines) — read in full.
- `72fdfa7f` (98 lines) — read in full.
- `0cd43662` (141 lines) — read in full.
- `4abf5ab2` (219), `2ccba197` (338), `f1ece435` (172), `5f7b9a8d` (253) — head (prompt + first tool calls) and tail (final verdict) read in full; middle (Rust-source tool-result payloads) skimmed via compact tool-call listing, not deep-read line by line.
- `c813f4af` (537) — head (~100 lines) and tail (~60 lines) read in full; middle skimmed.

**Keyword/targeted-grep-skimmed (not linearly read):**
- `9bc8a39a` (8,111 lines) — the big Fable-orchestrator session. Ran targeted regex passes for cross-model markers (`codex`, `GPT-5`, `sol\b`, `/model`) and for S11 language (`never traced`, `without reading`, etc.), then read ~30 full assistant-text blocks in detail at the hit locations. Large stretches (background-task polling, raw Bash/grep output, file-write payloads) were not read.
- `e92c4a3d` (2,195 lines) — same targeted-grep approach, plus a full read of the tail (~95 lines) and of the wedge-detection passage in full.
- `f57999e7` (8,981) and `fb80415b` (6,145) — already mined per `slice-C.md`. This pass ran only a targeted S11-language grep against them (did not re-mine broadly); it surfaced one strong fresh citation in `fb80415b` (L5961, well clear of the already-catalogued L2042/L5932/L2344) and no fresh hits in `f57999e7`.

**What I did not cover:** I did not run the protocol's full two-pass keyword list (verify/refut/control/base/evidence/checkpoint/cap/escalate/disclos/probe/falsif/trace/cite/quarantine/premise/patience/precedent/recomput/adjudicat) exhaustively against all 13 files — for the two ~8–9K-line files especially, I used a narrower, cross-model/S11-targeted keyword set instead and traded exhaustiveness for depth on the hits that came back. Large fractions of `9bc8a39a`'s and `e92c4a3d`'s middles (mechanical bridge-polling loops, raw source dumps) are unread. No non-transcript files (ADRs, codex rollout JSONLs) were opened.

---

## Findings

### 1. Self-diagnosed reader/reasoner conflation, with a proposed role-split fix (S11)

**Pattern:** A reasoning model (Opus, in Fable orchestration) audited its own session for ungrounded claims and found a clean split: everything it had *opened a file to check* held up, and everything it had inferred from a plausible internal model — without opening the file — was wrong. It then proposed fixing this structurally by splitting retrieval from judgment across two models: a cheap model mechanically gathers verbatim bytes at every cited location (including *absence* of coverage and the strongest counter-evidence, not just supporting evidence), and the reasoning model adjudicates only from that table, never from memory. This is the clearest single enactment of the S11 focus question in the slice — it names the exact failure shape the owner nominated and proposes the exact success shape as the fix, unprompted.

**Evidence:**
- `fb80415b:5961` — "I reasoned from the conservation identity that full and scoped assertions cost the same, without tracing what a full assertion actually does."
- `fb80415b:5961` — "Reading migration 0008 would have taken thirty seconds ... Sol read it; I theorised about it."
- `fb80415b:5961` — "The mechanism is that a good internal model of a codebase is nearly as satisfying as the codebase, and there's no felt difference between recalling and inferring."
- `fb80415b:5961` — "Sonnet gathers; Opus adjudicates." (proposed fix; also: "Retrieve the falsifiers, not just the supports.")
- Supporting exhibit, single-agent flavor (same mechanism, no role split needed because the same agent reads before it asserts): `72fdfa7f:97` — "Key facts established from the code (not assumed)" — followed by a recommendation that reverses the task's own proposed fix because `stream.rs:522` (`write_run`), not `stream.rs:634` (`digest_runs`), is where the fault actually fires.

**Proposed form:** bridge feature (a generic "citation-verification table" node: cheap model retrieves verbatim bytes + negative space + falsifiers for every claim in an upstream draft, before a reasoning model adjudicates) + steering rule ("cite locations you have open in this turn, not locations you remember from an earlier turn or a handoff doc").

**Confidence:** high — decisive single case (an explicit, structured self-audit naming 4 failures and contrasting them with everything verified), reinforced by an independent single-agent enactment of the same underlying discipline in a different session.

---

### 2. Named-alternative-causes-ruled-out sections (debugging discipline, cross-session recurrence)

**Pattern:** Two different sessions, two different problem types, both produce an explicit "here are the other explanations, and here is the evidence that rules each one out" section before committing to a root cause — never fixing on the first plausible cause. One is a live, multi-hour infra-debugging arc (why does `codex-acp` keep failing to handshake through the bridge?) run as an explicit hypothesis→falsifier ladder across five distinct wrong turns before the real cause surfaces. The other is a static design review that structures its root-cause section as three named alternatives, each with the specific evidence that rules it out, before naming the actual defect. This is a clean, repeated enactment of the project's own debugging-discipline steering rule (not just single-shot use).

**Evidence:**
- `2ccba197:336` — "## Root cause (confirmed in code, alternatives ruled out)" — followed by three named alternatives ("Serving bug (legacy fallback broken): ruled out", "Coverage construction bug: ruled out", "Audit-tool divergence: ruled out"), each with its falsifying evidence.
- `9bc8a39a:561` — "Hypothesis: my Bash runs sandboxed without outbound network / interactive codex auth ... Falsifier: if network + auth are fine, a direct probe succeeds."
- `9bc8a39a:689` — "codex-acp's ACP init handshake times out when spawned from my sandboxed shell" (hypothesis 3 of 5, itself later superseded).
- `9bc8a39a:2328` — "Root cause (debugged hypothesis-by-probe): the bridge's handshake is `initialize → authenticate` under one 30s bound" — with the distinguishing timing evidence ("`authenticate(chat-gpt)` no response in 40s") that separated it from the four prior, falsified hypotheses.

**Proposed form:** template clause — any root-cause/adjudication write-up gets a mandatory "alternatives ruled out" subsection naming ≥1 competing explanation and the specific observation that killed it, not just the observation that confirmed the winner.

**Confidence:** high — two independent sessions, one of them showing the pattern enacted five times in sequence against a single stubborn bug.

---

### 3. Three-signal wedge detection + verify-before-kill gate for background cross-model workers

**Pattern:** Running codex/Fable workers as long background bridge jobs creates an ambiguous failure mode: is the worker still thinking, or dead? The orchestrator built and named an explicit three-part conjunctive test (target file mtime stale 25+ min, worker process at 0% CPU, and the task's own progress ladder — edits → staged → commit-msg — stalled) and was explicit that *no single signal is sufficient* (stale mtime + live CPU = thinking; fresh mtime + 0% CPU = a normal gap between actions). Critically, it also gates any kill on a completeness check against the task's acceptance criteria first — the process might be wedged *after* finishing — and scopes the kill to that run's PIDs only. This converts an ambiguous "is it stuck" judgment call into a checkable, low-false-positive detector.

**Evidence:**
- `e92c4a3d:1256` — "All three together = wedge. Any one alone isn't sufficient: stale mtime with CPU activity means it's thinking or running tests; 0% CPU with a fresh mtime is just a gap between actions."
- `e92c4a3d:1256` — "verify the work is actually complete against the task's acceptance criteria ... Stale-and-idle tells me the agent won't produce more; it doesn't tell me the work is done."
- `e92c4a3d:1256` — "targeted kill of that run's bridge + wrapper PIDs only (never broad-kill — your other sessions share this machine)."

**Proposed form:** detector signature (a2a-bridge watchdog rule: `no file activity ∧ 0% CPU ∧ contract-ladder stalled ∧ N minutes idle → flag`) + bridge feature (the session explicitly notes this "could be automated" on the bridge side, with the same three signals — worth building rather than re-deriving by hand each incident).

**Confidence:** high — a single session, but a decisive, fully mechanized case built from three real incidents the same night, with the negative ("any one alone isn't sufficient") stated as explicitly as the positive.

---

### 4. Mechanism-level falsification downgrades an inherited cross-model WRONG to an unproven SMELL

**Pattern:** A Fable session is dispatched specifically to re-verify a finding inherited from a codex/GPT-5.6-sol pass, with the instruction to verify against the live checkout rather than trust the task summary. Rather than either rubber-stamping the inherited finding or merely failing to find a counterexample, the reviewer traces the exact call path end to end and produces a *positive constructive proof* that the flagged precondition breach cannot produce a wrong value in this caller (the fallback the code takes under the breached precondition provably computes the same value the correct path would). That distinction — refuting via mechanism, not via absence-of-a-counterexample — is what lets it confidently reclassify an inherited WRONG as SMELL under the project's own WRONG/SMELL discipline, rather than either accepting or hand-wavingly dismissing it.

**Evidence:**
- `0cd43662:8` — "Verify claims against the live checkout rather than trusting the task summary."
- `0cd43662:136` — "No input or state produces a demonstrably incorrect G4c observation, so under WRONG/SMELL discipline this is a SMELL cluster ... not a WRONG."
- `0cd43662:136` — "the last price of this instrument before `E` ... is exactly what the fallback picks" (the constructive proof) → "ADJUSTER FINDING: NOT PROVEN."

**Proposed form:** steering rule / template clause for adjudication tasks: "a claim is refuted only by a mechanism-level proof that the flagged condition cannot produce a wrong output, not by failing to find one instance of harm" — i.e. absence of evidence is itself flagged as insufficient to downgrade a finding, but a constructive proof is sufficient.

**Confidence:** high — a single decisive case, but a clean before/after (inherited WRONG → adjudicated NOT PROVEN/SMELL) with the mechanism spelled out in the transcript, not asserted.

---

### 5. Cheapest-decisive-test-before-commit (recurring meta-pattern, 4 independent sessions)

**Pattern:** Across four unrelated tasks (a stalled-load recovery decision, a data-dedup judgment call, a diagnostic-tooling design choice, and an orchestrator-role disagreement with the operator), the agent's move at the moment of genuine uncertainty was consistently the same: don't argue or guess further, identify the cheapest available observation or trial that would decisively separate the live hypotheses, and either run it immediately if it's free, or explicitly defer the decision to that trial. This is distinct from simply "verify before acting" — it is specifically about locating the *minimum-cost discriminating test* among several plausible paths before spending on any of them.

**Evidence:**
- `93bbfef1:10` — "Exactly 46,182,413 → pure apply latency (W5 hypothesis A); short → spool dedup-collapse bug ... This is the decisive experiment and it's free."
- `fe40f445:11` — "Answer to Q4 — what would make this WRONG (falsifiers, either direction):" — falsifiers enumerated for a close judgment call before committing to the recommended disposition.
- `72fdfa7f:97` — "Falsification requirement: its first group in normative order must equal the replay's reported pair" (a cheap DuckDB check proposed as the gate for trusting a more expensive in-gate inventory).
- `9bc8a39a:8108` — "If you want to test the inversion, A-4 is the right lab ... That's a real experiment rather than a guess." (proposing a cheap, low-stakes slice as the resolution to an orchestrator-role disagreement rather than continued argument).

**Proposed form:** steering rule — "when two hypotheses/designs/roles remain plausible after argument, name the cheapest observation or trial that would separate them, and prefer running it over further arguing or committing."

**Confidence:** high — four independent sessions/incidents, same shape each time, none of them the already-catalogued patterns for this slice.

---

### 6. Axis-separation dissolves a false dilemma in a close judgment call

**Pattern:** Handed a data-disposition question framed as a single hard choice ("which of two colliding rows is more point-in-time-correct"), the reviewer's first move is to notice the question conflates two orthogonal axes (identity attribution vs. data vintage), show that the harder axis (identity) is actually invariant to the choice on offer, and thereby reduce the "hard" question to a narrower, tractable one (a pure data-fidelity judgment). This is a distinct move from simply answering carefully — it's recognizing that the framing itself, not the underlying facts, was the source of apparent difficulty, before spending analysis on the wrong question.

**Evidence:**
- `fe40f445:11` — "The load is being over-constrained by a false coupling"
- `fe40f445:11` — "Axis A (PIT identity) is invariant to the choice. Whichever row you retain, the date is attributed to the same instrument."

**Proposed form:** steering rule — "before analyzing a forced-choice question, check whether it silently bundles two separable axes and whether one of them is actually invariant to the choice; answer only the axis that isn't."

**Confidence:** low-medium — single occurrence, no other instance of this specific move observed in this slice, but the reasoning is decisive and self-contained within the transcript.

---

### 7. Graded (non-binary) resolution status with disclosed residual gaps

**Pattern:** When re-verifying a prior review's findings against an implemented fix, the reviewer avoids collapsing to a binary RESOLVED/UNRESOLVED where the truth is more nuanced: one item is marked "RESOLVED with disclosed residual" — the fix closes the load-bearing gap but leaves a narrower, explicitly named residual limitation that the artifact itself discloses (via a named field) rather than silently omitting. This avoids two failure modes at once: false-confidence ("fully resolved" when it isn't quite) and undersell (treating a materially-fixed item as still open because it isn't perfectly closed).

**Evidence:**
- `4abf5ab2:218` — "Persisted-coverage self-reference vs frozen plan — RESOLVED with disclosed residual." — followed by: "not re-reading the frozen archive object itself is explicitly disclosed in `expected_coverage_basis` and `omitted_checks`."

**Proposed form:** template clause — adjudication verdicts get a third status alongside RESOLVED/UNRESOLVED ("RESOLVED — residual disclosed") that requires naming both the closed gap and the named field/doc where the residual is disclosed to future readers.

**Confidence:** low-medium — single occurrence in this slice; plausibly a variant of the broader-catalog "honest-degraded-path gates" pattern rather than something wholly new, flagged here because the specific non-binary verdict vocabulary is a usable template clause on its own.

---

### 8. Diff-of-diffs anchoring for incremental re-review

**Pattern:** Across repeated re-review rounds of the same evolving diff, the reviewer does not re-read everything from scratch each round, nor does it assume "nothing changed" — it diffs the current diff-stat against what it read last round, proves the delta is exactly N lines, locates precisely which file and hunk changed, and confirms the rest is byte-identical to what it already verified before re-verifying only the delta plus re-confirming untouched load-bearing surfaces. This is a distinct, cheap correctness move for the "round 2/round 3 re-review" shape that recurs constantly in this multi-model repo's review loop.

**Evidence:**
- `c813f4af:502` — "The diff moved by exactly +1/-1 since my last read — I need to locate that changed line before anything else."
- `c813f4af:536` — "the one-line stat drift was a main.rs doc-comment edit ... the +/- line sets match byte-for-byte, and load_backend's hunk map is unchanged."
- `c813f4af:536` — "re-verified every load-bearing property directly from the current files rather than from prior conclusions."

**Proposed form:** template clause for multi-round review tasks: "before re-reviewing, diff the current diff against the last-reviewed diff; prove byte-identity of untouched hunks explicitly rather than assuming it, and scope fresh reading to the delta plus any surface the delta could affect."

**Confidence:** medium — one session, but the practice recurs across two consecutive rounds within it (implicit at L490, explicit at L502-536).

---

## Recurrence notes (upgrades to already-mined patterns)

- **Independent recomputation of peer findings** (known: `fb80415b:2344`) recurs in fresh sessions: `f1ece435:162` — hand-recomputed G4c `relative_error` for two samples and a four-term gate-count sum, independent of the audit tool's own arithmetic, before accepting its output; `9bc8a39a:920` — the orchestrator ran the full verification suite itself rather than trusting a subagent's "done" claim and caught a real gap ("the subagent left one unformatted test line"); `9bc8a39a:2647` — a later independent subagent re-verification "confirms exactly what I verified and committed."
- **Evidence-probing / adversarial-attack reviewer stance** (known: `f57999e7:5999-6057`) recurs at `5f7b9a8d:253` — "I attacked the following and could not produce an incorrect result" — applied here to the reviewer's own draft "no WRONG findings" conclusion before finalizing it, rather than to blocking someone else's claim.
- **Claim quarantine after a burned claim** (known: `fb80415b:2042,5932`) — no cross-session recurrence found in the fresh 11; one additional same-session incident at `fb80415b:5961` (used above for Finding 1 instead, since it's the stronger citation).
- **Audits dispatched against one's own oversell** (known: `f57999e7:7542`) — no clear recurrence found in the fresh 11; reporting this honestly as a gap rather than forcing a weak match.

## Cross-model handoff notes (focus question 3)

The repo's standard cross-model shape, seen repeatedly across `0cd43662`/`2ccba197`/`4abf5ab2`/`5f7b9a8d`/`c813f4af`/`f1ece435`: a fresh Fable session is dispatched read-only with a fixed template — "You are an independent senior reviewer ... Verify claims against the live checkout rather than trusting the task summary" — to re-adjudicate either a prior Fable review's findings (RESOLVED/UNRESOLVED per item) or an inherited codex/GPT-5.6-sol finding. `9bc8a39a` is the orchestrator-level view of the same machinery: Fable conducts, dispatches gpt-5.6-sol through a2a-bridge as an independent correctness/rigor lens, and — per the operator's own later challenge and the orchestrator's conceded-in-part response at `9bc8a39a:8095` — sol's demonstrated value in this repo is specifically as the adversarial critic that "caught the archive/checkpoint split-brain BLOCKER that two other lenses missed," not as conductor (a model reviewing its own architecture being "a weaker gate"). That role division (one model authors/conducts, a structurally different model attacks) is treated as load-bearing, evidenced, and explicitly defended under pushback rather than asserted.

## FAILURE nomination

**S11 failure shape, self-reported** — `fb80415b:5961`. The same message used for Finding 1 is, in its first half, a first-person catalogue of the failure shape the owner nominated: a strong reasoner (Opus) asserting code behavior it never traced, stated with enough specificity to be independently checkable:
- "I reasoned from the conservation identity that full and scoped assertions cost the same, without tracing what a full assertion actually does."
- "§16's rationale ... Plausible, never traced, and I carried it from a handoff into an ADR."
- "'~4,600 row tail' and 'most B-classes have checkable predicates' — both inferred from a summary table rather than measured."

This is unusual evidence: a self-nomination rather than an externally-caught instance, which is part of why it's strong — the agent had no incentive to invent these against itself. Confidence: high (named, specific, self-audited against a contrasting set of claims that *did* hold up).

## Anti-findings

None met the citation bar this pass. One minor operational friction worth a footnote rather than a full anti-finding: several plan-mode review sessions (`2ccba197:331-336`, `f1ece435:170`) write their verdict to a `.claude/plans/` file and then find `ExitPlanMode` unavailable in that session ("No matching deferred tools found"), falling back to pasting the full review as chat text. The fallback works fine, so this isn't a practice that "looked disciplined but didn't work" — just a small tooling gap that self-healed each time it fired.
