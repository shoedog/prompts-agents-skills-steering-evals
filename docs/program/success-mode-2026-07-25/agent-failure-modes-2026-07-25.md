# Multi-agent orchestration failure modes — transcript forensics

**Date:** 2026-07-25 · **Corpora:** stockTrading Claude orchestrators (Opus 4.8 Jul 20–24, Opus 5 Jul 24–25), ssot-agents orchestrators (Opus 4.8 marathon Jul 21–24 + Opus 5 Jul 24–25, found under the `~/code` project dir, not the repo dir), Codex a2a-bridge sessions (261 rollouts Jul 4–25), bridge-spawned workers (445 rollouts Jul 22–25, 27 deep-sampled), plus a guardrail inventory of all three repos + global config.

**Method:** five parallel forensic analysts; incidents admitted only with a concrete transcript citation (session basename + line/timestamp + quote); user-correction messages and orchestrator self-admissions used as incident markers; WRONG (provably wrong, named failure) separated from SMELL (risky pattern, no demonstrated harm). Frequencies are lower bounds — errors no reviewer caught don't appear in transcripts.

---

## 1. Failure taxonomy

| # | Mode | Where | Exemplar | Measured cost |
|---|------|-------|----------|---------------|
| 1 | Mechanism claims without tracing code | Opus 4.8 + 5, both repos | "custom binary encoding, not JSON" — it was serde_json (`f57999e7` L7288→L7330) | 49-min run killed at 22 GB free on shared volume |
| 2 | Read-but-misread (comprehension, not access) | Opus 4.8 + 5 | "I had read this exact function and still misread it" (`608a7a2a` L1341); both Appendix-B type holes survived visual reads, caught only by compiled witness code (L7645) | Overturned pushbacks, extra review rounds |
| 3 | Verification claims from evidence that proves nothing | Opus 4.8 + 5 | Test campaign reported off `\| tail -8` which discarded every PASS/FAIL and made the exit code `tail`'s (`608a7a2a` L2692); Opus 5 shipped two "observed facts… my probes never established" into a signed amendment (`53d4f209`) | False green relayed; reviewer round to catch |
| 4 | Overgeneralizing from thin/invalid probes | Opus 4.8 + 5 | ±7-day corporate-action probe "falsified" a hypothesis it was structurally incapable of testing (`fb80415b` L1966→L2092); Kiro chat witness "proved precedence" — it didn't (L4555) | Wrong committed conclusion (`d1c364e`), voided later |
| 5 | Anchored/over-constrained ad-hoc briefs | Opus 5 (D1–D6), Opus 4.8 (rescope) | Panel brief with option menus incl. one impossible option (`fb80415b` L1522→L1568); post-interrupt rerun told "Read only [the doc]… do not inspect unrelated files" then endorsed claims with no repo access (`66466fe6`) | Killed Sol run + redone Fable run; unverifiable endorsement |
| 6 | Axiom injection into dispatches | Opus 5 | "treat the observed facts as given data… review the reasoning built on them, not the observations" — two facts later admitted unestablished | Reviewer effort spent on false premises |
| 7 | Under-scoped patch presented as complete | Opus 5 | 14-location patch against a concept threaded through ~40 locations (`53d4f209`) | 6 doc rewrites, 5 Sol dispatches, ~5 h |
| 8 | Memory-rewrite drift at consolidation | Opus 4.8 | "my handoff states this correctly — I got it right there and then blurred it when rewriting from memory" (`608a7a2a` L3183) | Conflated mechanisms in the consolidated record |
| 9 | Unverified handoff claims relayed at session start | Opus 5 | "The handoff's next step is not runnable, and I repeated that claim to you" — `--spinoff-binding` not accepted by that subcommand (`fb80415b` L334) | Survived ~35 min until an expensive Sol review caught it |
| 10 | Review-loop churn without convergence contract | Codex/Sol | 11 consecutive REVISE closures over ~15 h (R2b2d); 14 REVISE then round-15 APPROVE overnight for a four-document design (r3d); round-10 gated on a `WRONG/MINOR` doc fold | 6–14 fresh multi-MB/multi-M-token Sol rounds per feature |
| 11 | Null-final turn death | gpt-5.6-sol | Turn consumed 17.6 M tokens, compacted, emitted `task_complete` with `last_agent_message: null` — an entire closure review with no verdict (`rollout-2026-07-20T17-49-14`) | Multi-M-token rounds discarded; operator re-authors fresh runs |
| 12 | Zero-output spawn deaths, trusted by the bridge | gpt-5.6-sol workers | 7/445 spawns died with no output; bridge emitted `task_complete` anyway; one retry died byte-identically (95,059 B twice) — a loop repeating a poisoned request | ~19-min pipeline stall; wasted retries |
| 13 | Line-number-anchored implementer prompts | Codex era (Jul 6–7) | `server.rs:3049`, `main.rs:6210` anchors drifting as prior tasks land → 59 `apply_patch verification failed` across 22 sessions | Patch-loop thrash |
| 14 | Phantom tool advertisements | Bridge templates | 76/445 worker sessions (17%) told to prefer prism/lsp tools that aren't mounted; workers burn turns discovering and narrating fallback | Wasted turns, narration noise |
| 15 | Promise-then-stop | Codex (gpt-5.5, TUI) | Asked to commit+push, ended turn still narrating; user: "commit and push you only added a doc" | User prodding; full-suite run for a docs change |

Smaller confirmed items: framing mixed into evidence docs consumed as fact downstream (`fb80415b` L1610); pass-2 prompts re-inject pass-1 streaming narration (worker F4); static-only APPROVEs indistinguishable from test-backed ones (worker F5); "43 GiB free" read off the wrong volume, self-caught (`fb80415b` L289); logical-vs-physical disk assumption behind the 22 GB near-miss (`f57999e7` L6929→L6998); Codex reviewers re-reporting fixed inherited items / reclassifying declared non-goals until standing prompt clauses suppressed it; 9 "fresh clean-room" review rounds run as 9 turns of one shared-context session (7 compactions) — the same session that died of capacity.

**Explicitly NOT found (checked):** compaction-related degradation on the Claude side (both `/compact`s were user-managed with written handoffs; post-compact conduct *increased* verification); duplicated worker work (same-timestamp "twins" are deliberate two-lens diversity); hallucinated paths, editing-unread-files, premature "done", or test-weakening in the worker sample (implementers reported out-of-scope failures rather than re-baselining); sandbox/approval thrash on Codex; misreading truncated output on Codex (it re-reads in chunks).

---

## 2. Five reframes

**R1 — The orchestrator's own claims are the least-verified artifact in the system.** Worker output is checked hard in every corpus ("I now verify it myself — not on sol's say-so"; Opus 5 independently falsified a Fable hypothesis in flight). What goes unchecked until a reviewer or the user catches it: the orchestrator's mechanism claims, spec claims, fix-completeness claims, relayed handoff claims, and consolidation rewrites. Modes 1–4 and 7–9 are all self-claim failures. Reviews DO catch them — that's the "extensive reviews" tax being paid retail, one round per unverified claim.

**R2 — "Not reading code" is three different failures with three different fixes.** Under-reading (mode 1: fix = cite-the-lines-or-label-it-assumption); read-but-misread (mode 2: fix = compiled witnesses for type/contract claims — visual reads demonstrably insufficient twice); and Codex's inversion, over-reading (exhaustive chunked sweeps re-freezing boundaries every round until context death — fix = convergence contract, not more reading).

**R3 — "Too specific prompts" is real but narrow: it lives in ad-hoc briefs, not the evolved templates.** The 445-session bridge corpus REFUTES it — dense, premise-loaded prompts paired with mandatory falsification licenses ("Pressure-test this hard", "Also search for any regression elsewhere", "Independently verify rather than trusting those claims") produced three documented premise refutations by workers and zero trapped-by-scope cases. The confirmed instances are all interactively authored: the D1–D6 option-menu panel, the "treat observed facts as given data" axiom injection, the post-interrupt "read only the doc" rescope, and the line-anchored implementer prompts. The delta between templated and ad-hoc dispatches is the finding: **the discipline exists, it just isn't mandatory where prompts are written on the fly.**

**R4 — Admissions don't prevent within-session recurrence for attention-class failures, but do for structure-class ones.** Opus 5 over-claimed twice in one session by its own count ("both times treating a suggestive pattern as a settled cause without tracing the code") — the first admission didn't stop the second, because velocity-driven attention lapses recur under velocity. But after the D1–D6 anchoring admission, every subsequent brief that session was structurally open — the fix stuck because it changed an artifact (the brief template), not a resolution. Steering that manufactures artifacts (required headers, templates, ledgers) will outperform steering that asks for vigilance.

**R5 — Failures cluster at predictable moments.** Overnight high-velocity probe→conclude loops (02:50–04:40 both repos); consolidation/rewrite-from-memory steps; session starts from handoffs; pushback-on-reviewer moments (2 of ~4 pushbacks overturned); and supervision of subagent-authored code the orchestrator never traced (the common substrate of every stockTrading mode-1 incident). These moments are cheap to instrument.

---

## 3. What's already working — don't spend here

- The bridge role templates (falsification licenses, read-only contracts, file:line evidence demands, WRONG/SMELL tagging) — copy them, don't redesign them.
- User-managed compaction with written handoffs/RESUME files — no degradation observed.
- Worker-side conduct: 2.0% dead sessions, zero duplicated work, zero hallucinated paths, honest out-of-scope-failure reporting.
- The review lattice catches essentially everything eventually (fable cross-review confirmed all six Opus-5 WRONG mechanisms and found two additional false claims). The problem is cost-per-catch, not miss rate.
- Existing enforcement: global Stop-time verify gate (exp-2), WRONG/SMELL severity discipline (exp-d7), debugging discipline (exp-3), bridge deterministic verify-in-container, mutation-gate test discipline in ssot-agents, the exp-NN harness + transcript mining in prompts-skills-steering.

---

## 4. Mitigations

Ordered by measured cost of the failures they target. "Validate:" notes sketch the exp-NN move (artifact + form + taskset + judge + control) where applicable; bridge items are engineering tickets, not moves.

### A. Loop mechanics — the biggest token sink (bridge config/code)

**A1. Convergence contract for review loops.** Round 1 must demand exhaustiveness ("report every blocker now; findings that could have been found this round but surface later count against the review"). Rounds 2+ adjudicate inherited items and may add findings only in changed lines. Cap ~3 rounds; past the cap, REVISE requires a NEW WRONG with a concrete failure scenario — severity-aware gating so a `WRONG/MINOR` doc fold can never gate (R2b2d round 10 violated the severity discipline that already governs the Claude side). Targets mode 10: 6–14 rounds × multi-M tokens per feature is the single largest measured waste.
*Validate: rerun a completed review arc (e.g. r3d's four documents) under the contract vs the historical baseline; judge = findings-completeness by round 3 + total tokens.*

**A2. Null-final = failure, handled by the bridge.** Treat `task_complete` with empty `last_agent_message` as a failed round: auto-respawn in a FRESH session (never resume the context id), log a distinct event, and alert after two identical deaths (the byte-identical 95,059-B twins were a retry loop repeating a poisoned request). Emit a crash-reason record for mid-work aborts. Targets modes 11–12.

**A3. Verdict-early incremental output contract for reviewers.** Require the gate line + numbered findings to be emitted incrementally as discovered (restated at the end), so a capacity death leaves a partial artifact instead of 17.6 M tokens of nothing. Complements A2.

**A4. Preflight + fallback ladder.** PONG smoke test per (model id × CLI version) before batch spawning; auto-fallback sol → 5.5 → 5.4 (this exact recovery worked manually on Jul 10 in 4 minutes — automate it). Note the corrected fact: the hard crash was sol × codex-acp × CLI 0.133.0; on 0.144.1 sol runs but null-final-dies at capacity.

**A5. Hygiene: gate tool advertisements on session config** (mount prism/lsp for Codex workers or template-strip the paragraphs — 17% of sessions waste turns); **sanitize harvested drafts** before re-injection into pass-2 prompts (strip streaming narration, harvest the deliverable section); **symbol anchors, never line numbers, in implementer prompts** (59 apply_patch failures).

### B. Claim-evidence contracts — the wrong-claim killer (steering + templates; exp-able)

**B1. Cite-or-label rule.** Any claim of the form "X does / doesn't / can't Y" about code requires a same-session read of the implementing lines with an inline `file:line` citation; claims of ABSENCE require the searches run, enumerated ("state clearly it does NOT exist, with the searches you ran" — already your gold-standard Explore prompt; promote to global rule). Anything else must be written as "assumption:". Every stockTrading mode-1 incident was corrected by a <1-minute read that happened after the claim; this moves it before.
*Validate: steering-rule move on a mechanism-claims taskset mined from these transcripts (the six mode-1 incidents are seed items); judge = claim-has-citation + correctness; control = current CLAUDE.md.*

**B2. Evidence-integrity rule for pass/fail claims.** Test/campaign results may only be asserted from full output captured to a file plus the runner's own exit code — never through truncating pipes; the claim cites the capture path. Candidate enforcement: extend `verify_gate.sh` to require capture-file links in VERIFICATION.md, and/or a PostToolUse check flagging `| tail`/`| head` on test commands. Targets mode 3.

**B3. Probe ledger.** Any "observed fact" cited in a design or shipped to a worker as given data must link the probe command + output that established it; unlinked facts must be labeled assumptions, and reviewers instructed to treat them as unverified. Kills axiom injection (mode 6) at the source — the `prompt:null` incident and the version-fact drift (2.1.211→2.1.216 across prompts) are both un-linkable facts that mutated in relay.

**B4. Compile-witness gate for type/contract-shape claims.** Visual reads failed twice on Appendix-B; the reviewer's compiled counterexamples caught both. Rule: type-level acceptance/shape claims in specs get a compiled witness (same ethos as ssot's mutation gates — "prove the check can go red").

**B5. Structural probe-validity header.** Your exp-3 discipline already requires predict/falsify — the transcripts show it gets *skipped at velocity* ("I ran the probes but skipped that step both times"). Make it an artifact instead of an instruction: evidence-doc template with a required header — `confirms-if / falsifies-if / cannot-see`. The ±7-day probe fails the third field instantly. Templates get filled; instructions get skipped.

### C. Dispatch contracts (templates; copy from what already works)

**C1. Open-brief default for decision/panel dispatches.** Facts file (file:line facts, run numbers, DB output only) separate from an optional, labeled framing file; orchestrator's opinion withheld or explicitly marked refutable ("The conclusion in the brief is mine and may be wrong… argue the opposite case first and hardest"); option menus only when the USER specified the options. Opus 5's own L1605/L2097 text is the template — promote it verbatim.
*Validate: A/B on a decision-panel taskset; judge = did the panel surface options/corrections outside the brief's frame.*

**C2. Falsification license required on every premise-loaded brief.** "Premise + pressure-test-this-hard + also-search-elsewhere" is what separates the clean 445-session corpus from the D1–D6 incident. Make those clauses required fields in ad-hoc dispatches (a lint over dispatch files: premise detected → license clause present?). Corollary: never narrow a verifier's scope below what its claims require — the Jul-15 "read only the doc" rerun endorsed falsifiability claims it had no repo access to check.

**C3. Provenance tiers in every relay.** Controller→critic messages and fix-claims must separate "re-ran this turn" from "supplied, not re-verified" (the format one Fable worker used unprompted); reviewer verdicts carry a verification-tier marker (`STATIC-ONLY APPROVE` vs test-backed) so synthesizers can't conflate them. Fix-completeness claims are the weakest relay link (the five-omitted-gates UNRESOLVED).

### D. Session-lifecycle guardrails (cheap, targeted at R5's moments)

**D1. Handoff quarantine.** Every actionable handoff claim ("next step: run X with flag Y") is unverified until greped/traced this session; spend the first minutes verifying entry points named. A SessionStart hook can inject the reminder when a handoff/RESUME file is present.
**D2. Rewrite-from-source rule.** Consolidation steps (handoff→roadmap folds) must diff claims against the source doc, never rewrite from memory (mode 8).
**D3. Pushback requires re-running the witness.** Before rejecting a reviewer's WRONG, re-execute their witness/repro; 2 of ~4 pushbacks were overturned.
**D4. Physical-`du` sampling in the first minutes of any run on a shared volume** (the 22 GB near-miss came from logical-bytes math).
**D5. Fill two inventory gaps:** give ssot-agents an in-repo brief (only orchestrator repo with zero local steering); mount the two validated global rules (WRONG/SMELL, debugging discipline) into containerized bridge workers, which currently run steering-free on prompt contracts alone.

### E. Observability — close the loop (multiplies the exp harness)

**E1. Automate incident mining as a standing detector.** You already have `mining/` indexing both corpora. Add signature detectors that feed TRACKER nominations automatically: assistant admission phrases ("you're right, I", "my mistake", "I should have", "this one is on me", "I over-claimed"), user correction phrases, null-final `task_complete`, apply_patch failure loops, `| tail`-on-test-command, phantom-tool fallback narrations. Each detector is a labeled incident stream — this analysis, continuous instead of one-off.
**E2. Track recurrence-after-admission as the severity metric.** An admitted failure that recurs in-session (the double over-claim) outranks one that doesn't (post-D1–D6 briefs); it distinguishes attention-class failures (need artifacts/hooks) from structure-class ones (steering suffices).

---

## 5. Model-routing notes (observed, not benchmarked)

- **Opus 4.8:** errors cluster at consolidation/rewrite moments and pushback; corrections mostly wait for a challenge.
- **Opus 5:** faster and broader (70 tool calls in a 12-min review vs 4.8's ~19/session median on comparable one-shots); errors are precision misses at speed; self-corrects fastest and repairs structure within-session; also produced the best dispatch boilerplate in either corpus.
- **Fable 5:** the error-catcher in both repos — confirmed all six Opus-5 WRONG mechanisms, found two additional false claims (a false-absence claim and a wrong call-graph attribution), flagged its own unverified items, and no Fable worker was caught wrong by a later pass in these corpora. Use for cross-review/adjudication of flagship-model claims.
- **gpt-5.6-sol:** exhaustive reader, strongest at line-by-line closure sweeps; mortal at context capacity (null-final) and drips findings across rounds without a convergence contract. Pair Sol's depth with A1–A3.
- 158/445 worker spawns ran sol; Claude workers were fable-5, sonnet-5, opus-4-8. No model-id config errors in any transcript.

---

## 6. Caveats

- Frequencies are lower bounds; silent errors no reviewer caught leave no transcript trace.
- The bridge-worker corpus contains no open-ended "investigate X" prompts, so the too-specific hypothesis is refuted there only for the roles that exist (reviewers/architects/implementers/synthesizers); the confirmed instances all come from the in-session ad-hoc corpus.
- Model-behavior comparisons are observational (different tasks, different eras), not controlled.

---

## 7. Implementation strategy (cross-provider: Claude, Codex, Kiro)

### Decision rule for choosing among implementation options

For each mitigation, pick the **most deterministic, most provider-independent chokepoint that can carry it**, in this order:

1. **Bridge pipeline code/config** — every provider's workers flow through it; enforcement is deterministic and provider-blind by construction.
2. **File-format validators** — small provider-blind scripts that check artifacts (briefs, VERIFICATION.md, evidence docs); any agent from any provider must produce the artifact, and a script — not a model — judges it.
3. **Prompt/dispatch templates** — text is inherently portable across providers.
4. **Per-provider hooks** — uneven support; use only where the event exists (the ssot-agents capability catalog is the authority on which provider supports what).
5. **Steering instructions** — weakest tier, context-budget-limited, and the transcripts prove instructions get skipped at velocity (exp-3 was in context during both over-claims). Reserve for judgment rules that can't be mechanized, and only after exp-NN validation.

**Corollary (R4):** prefer mechanisms that manufacture artifacts over mechanisms that request vigilance. Templates get filled; instructions get skipped.

### The three shared validators (build once, mount everywhere)

- **`brief-lint`** — validates dispatch briefs: premise detected → falsification license + search-elsewhere clause present; option menu present → user-specified flag required; line-number anchors → reject (symbols only); "given data"/claimed totals → probe-ledger link required; advertised tools → present in session config. Mount at: (a) `a2a-bridge` submit path (covers ALL providers' workers, templated and ad-hoc — the ad-hoc path is exactly where failures live), (b) Claude PreToolUse hook matching the Task tool (covers native in-session spawns that bypass the bridge).
- **`cite-check`** — extracts `file:line` citations (and quoted snippets) from specs/briefs/evidence docs and verifies they resolve against the checkout — file exists, line range exists, quote matches. Makes the cite-or-label rule enforceable instead of aspirational; catches stale/fabricated citations deterministically. Mount at: brief-lint, verify-gate, optionally pre-commit for `docs/` specs. (Prism's slicing infrastructure is a natural home.)
- **`verification-schema-check`** — VERIFICATION.md must link full-output capture files, carry runner exit codes, and separate "re-ran this turn" / "supplied, unverified" tiers; reviewer verdict lines must carry a verification-tier token (`STATIC-ONLY APPROVE` vs test-backed). Called from the existing Claude Stop hook, the existing Codex stop-hook port, and compiled to Kiro's equivalent where supported.

### Per-mitigation placement

| Mitigation | Layer | Cross-provider mechanism |
|---|---|---|
| A1 convergence contract | Bridge workflow config + synth/reviewer templates; bridge counts rounds and enforces the cap + severity-aware gate format | Provider-blind (bridge) |
| A2 null-final = failure, twin-death alert, crash records | Bridge code (Rust) + tests | Provider-blind |
| A3 verdict-early incremental output | Reviewer templates + bridge harvest parser | Provider-blind |
| A4 PONG preflight + fallback ladder | Bridge code/config | Provider-blind |
| A5 tool-ad gating, draft sanitization, symbol anchors | Bridge templating/harvest + brief-lint | Provider-blind |
| B1 cite-or-label | cite-check validator at chokepoints + one steering line | Validator provider-blind; steering via SSOT compile |
| B2 evidence-integrity for pass/fail | verification-schema-check called from each provider's stop hook | Validator shared; hook wiring per provider via SSOT |
| B3 probe ledger | Doc template + brief-lint (unlinked "given facts" rejected) | Provider-blind |
| B4 compile-witness for type claims | Review-contract template clause; later a CI gate for specs | Template (portable) |
| B5 confirms-if/falsifies-if/cannot-see header | Evidence-doc template + brief-lint presence check | Provider-blind |
| C1 open-brief default (facts vs framing files) | Dispatch template library + brief-lint | Provider-blind |
| C2 falsification license required | brief-lint rule | Provider-blind |
| C3 provenance tiers in relays | Output-contract templates + bridge harvest validation | Provider-blind |
| D1 handoff quarantine | Handoff-file schema (claims tagged verified/unverified) + SessionStart hook where supported, steering line otherwise | SSOT compiles hook-or-steering per capability catalog |
| D2 rewrite-from-source | Steering (judgment rule) — exp-validate first | SSOT compile to all three |
| D3 pushback re-runs the witness | Steering + adjudication-template clause | SSOT + template |
| D4 physical-du sampling | Runbook/steering line; optionally a bridge livegate-style watchdog for long runs | SSOT / bridge |
| D5 ssot-agents repo brief; container steering mount | Direct config changes (bridge containers mount the compiled AGENTS.md) | SSOT output mounted |
| E1/E2 mining detectors + recurrence metric | prompts-skills-steering `mining/` (reads both corpora already) | Provider-blind |

### Author once, compile per provider

Anything that must exist per-provider (steering text, hook wiring) should be authored **once in ssot-agents and compiled** to CLAUDE.md / AGENTS.md / Kiro steering and to each provider's hook config where the capability catalog says the event exists — with automatic steering-text fallback where it doesn't. This rollout is the natural dogfood case for the compiler, and it closes three inventory gaps as a byproduct: hand-duplicated global rules, the bare Kiro surface, and steering-free containerized workers.

### Sequencing

- **Wave 0 (first, ~a day):** E1 mining detectors — establishes before/after baselines (REVISE-round distribution, null-final rate, citation coverage, admission/correction rates) so every later wave is measurable. Include transcript dedupe (post-compact forks like `9aea8b01` duplicate sessions) and treat `<synthetic>` model entries as failed-turn signatures.
- **Wave 1 (days):** pure config/template edits — A1 round caps + severity gate, A5, C1–C3 templates, D5. Immediate token savings, no new code.
- **Wave 2 (a week-ish):** the three validators + bridge mounting (A2–A4, B1–B3, B5 enforcement). Engineering tickets with tests, not experiments.
- **Wave 3 (exp cycles):** the steering-only judgment rules (B1's rule text, D1–D3) through the exp-NN loop, promoted with `(validated: exp-NN)` tags via SSOT compile.
- **Steering-budget discipline:** global steering stays lean (~5 validated rules max). If a mitigation can be an artifact, template, or validator, it must not become an instruction — instruction-tier accretion is how steering dies, and the transcripts show instructions are the tier that fails under velocity anyway.

## 8. Additional findings (post-report addenda)

- **Doc drift teaches agents false environment beliefs:** stockTrading CLAUDE.md claims project hooks exist that don't. Steering that describes enforcement should be generated from the actual settings (SSOT), never hand-written — an agent that believes a lint-on-stop hook exists may skip linting.
- **The bridge submit path is the keystone chokepoint:** ad-hoc orchestrator briefs (the confirmed failure locus, per R3) currently bypass every template contract. brief-lint at submit + the PreToolUse[Task] mount gives one deterministic gate over *every* dispatch, templated or freehand, to any provider.
- **Candidate (unvalidated): velocity governor.** Wrong-conclusion incidents cluster in overnight probe→conclude loops minutes apart. A conditional rule — when probes chain faster than ~N minutes, the B5 header becomes mandatory before the next probe — targets the exact conditions where discipline drops. Worth an exp before adoption.
- **Handoff files deserve a schema:** the existing handoff/RESUME practice works (compaction caused zero incidents); formalizing a "claims" section with verified/unverified tags is what makes D1's quarantine mechanical.
