# Fable Behavioral-Delta Catalog

**Synthesis of three transcript-mining slices — review, debug, planning/orchestration.**
Branch `transcript-mining`. Compiled 2026-07-03 by the M3 synthesis pass from
`mining/out/deltas/{review,debug,plan_orch}.md` (gitignored miner deliverables) and their
reports `.superpowers/sdd/task-M3{a,b,c}-report.md`. All evidence below is quote-backed in the
source slices; citations of the form `F8 L37`, `202efdf4:2585`, `5e28ca3a:9` point into those
slices, which in turn cite raw-transcript line numbers.

## Why this document exists

The owner loses cheap Fable-5 access on **2026-07-07** and wants the remaining fleet —
**Sonnet 4.6 / 5, Opus 4.6 / 4.8, gpt-5.5** — directed to Fable-level performance on SWE work
(review, debug, plan/orchestrate) via the transferable surfaces this repo already builds:
skills, steering rules, hooks, agent/subagent definitions, and tool-contract changes. Three
miners extracted evidenced behavioral deltas between Fable-5 and each of those models from real
(non-seeded) dogfooding transcripts. This catalog merges and ranks those deltas, maps each to a
transfer surface and a measurement in the existing eval harness, and proposes five experiments.

**Corpus at a glance** (`mining/out/coverage.md`, 4,601 sessions total): one owner; ~3–4 repos
(a2a-bridge = Rust A2A/ACP orchestrator; slicing/"prism" = Rust tree-sitter code-nav; stockTrading;
the eval harness itself); mostly Rust + Python. The four models were mined on matched projects and,
where possible, matched task templates. Sample sizes are small and curated for comparability, not
powered — see [Limitations](#8-limitations).

---

## 1. Cross-cutting findings (read these first)

These six themes recur across **≥2 of the 3 slices** and reframe the whole exercise. They are the
lens for everything in the ranked catalog.

### CC-1 — Fable ≈ Opus-4.8 at ceiling; the real lift targets are Sonnet and gpt-5.5

On **core capability**, Fable-5 and Opus-4.8 are near-indistinguishable in every slice:

- **Debug:** "Fable-5 and Opus-4-8 are near-indistinguishable on core debugging quality …
  reproduce-first, minimal fixes, verification, honesty — all at ceiling in both" (debug §3). Both
  had exactly one premature-victory incident with clean recovery.
- **Plan/orchestration:** "Opus-4-8, in this corpus, follows an almost identical sophisticated
  orchestration template to Fable-5" — skill-invocation-before-acting, `TaskCreate` ledger with
  dependency edges, heterogeneous model-tiered dispatch, multi-wave review gates, durable handoffs.
  The two largest orchestration sessions in the **entire** corpus are both Opus-4.8, not Fable
  (`b48b86af` ~12.2 d / 15,504 turns; `f14884e6` ~13 d / 15,371 turns).
- **Review:** Fable does the same *class* of verification/disconfirmation moves as Opus, but "less
  often and at higher cost" for Opus — the Fable→Opus gap here is **efficiency, not capability**.

**Consequence for spend.** Opus-4.8 needs no capability intervention — it is already where Fable
is. Interventions should target **Sonnet-4.6/5 and gpt-5.5**, where the deltas are real. Opus-4.6
and Sonnet-5 were essentially **absent from the mined corpus** (coverage: opus-4-6 = 1,144 turns
total, mostly sidechain; sonnet-5 = 52 main turns), so their gap assessments below are
**extrapolations** from the nearest observed sibling (Opus-4.6 ≈ treat as an Opus-4.8 lower bound;
Sonnet-5 ≈ treat as Sonnet-4.6 or better, untested).

### CC-2 — The model-vs-scaffold confound *is* the core hypothesis: the scaffold transfers

Every Claude session in the corpus ran inside the owner's heavily-customized environment
(superpowers skills — systematic-debugging, verification-before-completion, TDD; CLAUDE.md rules;
a self-imposed multi-model review pipeline). Fable's discipline **cannot be cleanly separated from
that scaffold** (debug §4, review §5). Rather than treat this as a nuisance confound, the program
treats it as the load-bearing hypothesis, and the evidence supports it:

- Sonnet-4.6, **under the review contract** (mandatory second pass + gaps-register), exhibits
  Fable-grade verify-before-claim, self-correction, and belief-vs-verification separation
  ("(it won't, but it's an unverified assumption)"; "I had the reasoning backwards") — behavior it
  never shows spontaneously (debug Δ8).
- gpt-5.5's best episodes are exactly its **strict-TDD-scripted** ones; its weakest verification
  (G4, shipped on a build-only check) is where the brief didn't script breadth (debug Δ2/Δ8).
- Opus's cleanest debug episode explicitly invoked `superpowers:systematic-debugging`; its mutation
  review followed a user rule ("Per your rule, I verified it").

**Implication:** mid-tier models meet the bar **when the bar is structural** and miss it when it is
discretionary. Therefore prefer **contract-shaped surfaces that enforce** — hooks that require
evidence at claim-time, dispatch-brief templates with required fields, skills with checklists —
over free-form prose steering. This preference drives every intervention in §2.

### CC-3 — Verification economy (a Fable > Opus efficiency edge; Sonnet is *worse*)

Fable reaches equivalent (or better) verification depth at a fraction of the tool cost, with ~zero
redundant re-reads. Cleanest matched triad (stockTrading, ARCHITECTURE lens, identical task):
**Fable F8 = 5 tool calls, Opus O5 = 24, Sonnet S3 = 48** — same class of conclusion. The pattern
holds on every matched pair (F1=27 vs S1≈54; F6=16 vs O2=28 vs S2≈36). It shows up as cheap
"settling" moves (a structural diff instead of eyeballing; one `git show <rev>:<path>` for
historical ground truth; one `grep -c` for a cardinality claim) and as **effort-matching** —
Fable skips its own planning ritual for a mechanical fix "with the error message in hand"
(debug F2-A:3827). This is a **cost** lever, not a capability one, and cheaper models are *worse*
here (Sonnet's 48-call runs, its doc-hunting tail — see D8), so it still matters for the fleet.

### CC-4 — Unconditional verification gates vs conditional ones

All models verify; the delta is **whether the gate is unconditional**. Fable ran a suite-level
green gate before "done" in **7/7** debug episodes regardless of task framing; Opus 6/7; **gpt-5.5
only 2/4 self-driven** — "breadth tracks the brief, not an internal standard" (one session shipped
after `cargo build --workspace` only, no wider test re-run). In review, all models open with a
verification summary, but Fable turns verification into actual **downgrades/reversals** of its own
claims, and in orchestration Fable/Opus follow an explicit "verify, don't trust" policy on subagent
results while Sonnet, in the one detectable case, silently used a subagent result from the **wrong
repository** without flagging it (plan_orch Δ7). The fix is to make the gate fire **mechanically at
claim-time** rather than rely on the model remembering — a hook, not a reminder.

### CC-5 — Predict-then-probe epistemics (pre-register the disconfirmer)

Fable's most distinctive debug move is **stating what result would confirm vs disconfirm a
hypothesis before running the probe**: "If it's green → environment contention; if it stalls again
→ real find, I dig before anything ships" (202efdf4:2585), then building a stall-watcher to settle
it. A "pre-existing / environmental" attribution is backed by an actual **differential run**
(clean-tree / one-variable control), not inference. This extends to distrusting *prior* verdicts,
not just the current draft: Fable reopened a previous review round's dismissal and disproved it with
a constructed code witness (review F2 L248-259), and recalibrated a reviewer subagent from its own
in-session track record ("you cleared two things codex later proved wrong … be MORE adversarial",
5e28ca3a:476). **gpt-5.5 is weak here** — its hypothesis statements are mostly compiler-error echoes
and its one "pre-existing" claim skipped the differential run entirely (debug §2.2).

### CC-6 — Dispatch-brief quality (how to make a cheap delegate safe)

Both Fable and Opus write **rich, guardrailed dispatch briefs**: exact `file:line` anchors,
"known-good facts … do not re-report as bugs" sections to prevent redundant re-verification across
parallel agents, embedded commit-message templates down to the `Co-Authored-By:` trailer, an
explicit "ask, don't guess" escape hatch (`report NEEDS_CONTEXT`), and — the key epistemic move —
**falsifiable stop conditions handed to the delegate**: a fixer subagent is told the diagnosis is a
*hypothesis* ("stale-binary artifact") and must "verify against a FRESH build and STOP if it
persists … rather than paper over it" (debug F2-A:3812), plus "Write the failing test FIRST"
mandates. This is precisely the **"how to make a cheap fixer safe"** pattern the owner needs, since
the post-Fable fleet will run cheaper models as the delegated workers. It is shared Fable/Opus
behavior; Sonnet and gpt-5.5 sit at the *receiving* end and do not originate it.

---

## 2. Ranked delta catalog

Twelve merged deltas, de-duplicated across slices. **Ranking = (evidence strength across slices) ×
(impact on outcome/cost) × (size of the gap in the target cheaper models = lift potential).**
Deltas that lift Sonnet/gpt-5.5 rank above pure Fable>Opus efficiency edges, per CC-1.

**Per-model gap legend** (observed models only; `?` = not in corpus / extrapolated):
`has` = does it reliably · `partial` = conditional/at higher cost · `lacks` = observed absent ·
`n/a` = structurally impossible · `proxy` = inferred from review-mode only · `untested`.

---

### D1 — Unconditional verify-before-done gate
**Sources:** debug Δ2 (3 episodes-worth, 7/7 Fable) · review §2.3/§2.8 · plan_orch Δ7. **Three slices.**

Require a suite-scope test run with a parsed pass count *after the last edit* before any
"fixed/done/passing" claim — unconditionally, not only when the brief demands it. Fable did this in
7/7 debug episodes; the failure mode it prevents is a regression escaping because breadth tracked
the brief instead of an internal standard.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has (7/7) | has (6/7) | untested (proxy: verifies under contract) | **partial (2/4)** |

**Transfer surface — HOOK (enforce).** A Stop/completion hook: on an assistant "done/fixed/passing"
claim in a debug/implement task, scan the last-edit→claim window for a test-runner invocation at
suite scope + a parsed non-zero pass count; if absent, block the completion and inject a reminder.
`superpowers:verification-before-completion` already carries the norm — the hook makes it
non-optional for cheaper models. Opus-4.6/Sonnet-5 inherit the gate for free.

**Measurement — adherence + ablation.** Task family: **debug** (`test_cheap`, the queued Exp 3 —
needs a 20-item reproducible-failing-test taskset). Adherence metric = "widest test scope run after
final edit" (binary per item: suite / package / target / none). Ablation = regression-escape rate
(binary: does the post-fix tree still fail a held-out check).

---

### D2 — Predict-then-probe / disconfirmation epistemics
**Sources:** debug Δ1 (3–4/7 Fable, unprompted) · review Delta 3 · plan_orch Δ7. **Three slices.**

Before each diagnostic command, state what result confirms vs disconfirms the current hypothesis;
back any "pre-existing/environmental" attribution with a differential run; treat a *prior* verdict
as a testable hypothesis, not a given.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has | proxy (self-correction under contract only) | **lacks (compiler-echo hypotheses; skipped differential)** |

**Transfer surface — SKILL (worked examples) + SUBAGENT pattern.** (a) Add a "predict-then-probe"
directive with a worked example to `superpowers:systematic-debugging` — it fires exactly when
debugging starts. (b) For second-pass review, split the drafting agent from a fresh
**adversarial-checker subagent** ("find the specific reason each claim could be wrong: recompute
counts, re-derive citations from a fresh read, and check whether any prior verdict this draft
relies on was itself checked or just assumed") so the checker isn't anchored to the writer's framing.

**Measurement — ablation + triggering.** Task family: **debug** (shared taskset with D1) and
**review** (planted-error second-pass items). Binary judge criteria: (i) a discriminating prediction
*preceded* the probe call; (ii) any pre-existing/env attribution was differential-backed; (iii) the
second pass caught a planted wrong citation/overstated count. Triggering shape scores whether the
skill fired when it should.

---

### D3 — Dispatch briefs that embed epistemic guardrails
**Sources:** debug Δ4 (2–3/7 Fable) · plan_orch §1c + Δ6. **Two slices.**

A dispatch brief to a delegate carries: exact error text; the current diagnosis **labeled as a
hypothesis**; the disconfirming condition; a stop rule ("STOP if it persists rather than paper over
it"); a red-before-green mandate; and the required verification scope — plus "known-good facts, do
not re-report" and an "ask, don't guess / report NEEDS_CONTEXT" escape hatch. This is the
transferable **"make a cheap fixer safe"** pattern (CC-6).

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has | n/a as originator (lacks; sits at receiving end) | n/a (no subagent tool) |

**Transfer surface — AGENT/TEMPLATE (enforce).** A dispatch-brief template in
`superpowers:subagent-driven-development` (and the a2a-bridge prompt registry) with the six fields
as **required**; a lint that rejects a brief missing any field before dispatch. This is the surface
that most directly protects the owner's post-Fable workflow, where cheaper models become the workers.

**Measurement — adherence + ablation.** Task family: **delegated-fix** (to-be-built; can reuse
review-hard defects as the seeds). Adherence = judge scores each outgoing brief for presence of the
6 fields (binary each). Downstream ablation = "papered-over" incident rate (binary: did the fixer
apply a fix while the planted disconfirming condition was still true).

---

### D4 — Verification economy: equal depth at far fewer tool calls, zero redundant re-reads
**Sources:** review Delta 1 + Delta 4 + Delta 6 · debug Δ6 (effort-matching). **Two–three slices.**

Reach the same verdict at a fraction of the tool cost: no re-reading a file without naming the new
question it answers; a single "settling" check (structural diff / `git show` / `grep -c`) over a
multi-hop causal chase; process weight matched to problem size. Fable 5 calls vs Opus 24 vs Sonnet
48 on the matched triad. This is a Fable>Opus **efficiency/cost** edge — but Sonnet is *worse* than
Opus, so it still lifts the cheap fleet's cost profile.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has (floor of the corpus) | partial (correct but ~3–5× cost) | **lacks (worst cost; doc-hunting tail)** | n/a-ish (shell-only inflates counts; see §3) |

**Transfer surface — SKILL (technique library).** A "verification-economy / verification-recipes"
skill for review+debug: *state the new question before re-reading; prefer one-shot settling moves —
structural diff for parity claims, `git show <rev>:<path>` for historical claims, `wc`/`grep -c` for
cardinality — before a multi-file trace.* Judgment habit, so a skill fits better than a hook (a hook
can't tell "genuinely new info" from "re-reading out of uncertainty").

**Measurement — ablation (efficiency-adjusted).** Task family: **review** (existing
`review-seeded` / `review-hard`). Metric = **recall-per-tool-call**: run with/without the skill on
Sonnet/gpt-5.5 and require unchanged-or-better recall & false-finding rate at lower tool-call count.
(Lower count with worse recall is a regression, not a win.)

---

### D5 — Risk-tiered, multi-wave review-gate loop
**Sources:** plan_orch Δ6 + Δ7 + §1d · (review Delta 3 writer/checker split is the same shape). **Two slices.**

Run repeated implement → task-scoped review (reviewer tier scaled to risk: cheap for routine,
higher-tier for high-risk/final) → whole-branch dual review → merge, wave after wave, with the
orchestrator catching wrong subagent results before synthesis. This is exactly the **cheap-worker →
higher-tier-reviewer** architecture that lets the owner run cheap models safely.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has | **lacks as sustained pattern (ceiling = single-round fan-out)** | n/a (no subagent concept) |

**Transfer surface — AGENT DEFINITION (enforce).** An `implement` agent type whose completion is
structurally gated on a `review` agent type's sign-off before the orchestrator may proceed —
already close to `superpowers:requesting-code-review` + `subagent-driven-development`; the gap is
making the gate a **hard requirement** a lower-tier orchestrator cannot skip, not an invocable skill.

**Measurement — triggering + adherence.** Task family: **orchestration** (to-be-built multi-wave
harness). Triggering = did a 2nd review wave fire after a first pass surfaced a Blocker/Important
(precision/recall over should-fire items). Adherence = fraction of implement tasks that reached a
reviewer sign-off before merge.

---

### D6 — Same-symptom / different-cause discrimination (no reflexive guard-suppression)
**Sources:** debug Δ3 (2/7 Fable). **One slice — but marks the classic cheap-model failure boundary.**

A recurring error message is a **new bug until re-derived**: diagnose each occurrence
independently; never disable/bypass a failing check without stating why the *check* (not the code)
is wrong. Fable gave two identical `SutStale` exceptions two different root-cause fixes and
explicitly refused the `allow_stale=True` escape hatch the first time (202efdf4:5263-5284). This is
exactly where cheap models classically fail — loosen the assertion, silence the guard.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has (closest: "the test is wrong, not the code") | untested | not observed |

**Transfer surface — SKILL + one worked example.** Add to `superpowers:systematic-debugging`:
"a recurring error is a new bug until re-derived; never suppress a failing check without an argument
that the check is wrong." Recipe + example, because it is a known-moves gap.

**Measurement — ablation (seeded pair).** Task family: **debug**. A seeded pair surfaces the *same*
exception via two planted causes — one legitimately suppressible, one must-fix. Binary: does the
model differentiate? Does it ever suppress a guard without a stated argument?

---

### D7 — Literal wrong-vs-smell severity tagging embedded in the tag
**Sources:** review Delta 5. **One slice — but the most mechanically enforceable delta in the set.**

Bake the defect/smell distinction the DISCIPLINE section already requires **into the severity tag
itself** — `MAJOR (smell, high cost-of-change)` / `MINOR (smell)` — instead of leaving it implicit
in prose, where it drifts under truncation/time pressure. Fable does this literally; Opus, Sonnet
and gpt-5.5 leave it in prose.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has (in-tag) | lacks (prose only) | lacks (prose only) | lacks (prose only) |

**Transfer surface — TOOL-CONTRACT change + HOOK lint (enforce).** Strengthen the harness's own
review prompt-template OUTPUT FORMAT to *require* the qualifier as literal tag syntax
(`SEVERITY (defect|smell) — <loc>: <issue>`), backed by a deterministic **regex lint** on the
produced review that rejects any non-BLOCKER finding lacking the qualifier. Cheap, model-agnostic,
catches drift.

**Measurement — adherence (binary, regex).** Task family: **review** (existing tasksets — **no new
data needed**, the cheapest experiment). Binary format-compliance per finding, computed by regex,
independent of semantic recall/false-positive judging.

---

### D8 — Find-or-fallback: one existence check, never a multi-strategy hunt for a nonexistent artifact
**Sources:** review Delta 2 (Sonnet 2/3 sessions; 0/8 Fable). **One slice — but dramatic and cleanly Fable-absent.**

When a task references an artifact by name/path not yet located, do **one** fast existence check
(`git ls-files | grep -i <kw>`); on a miss, immediately state "not committed — verifying against
code only" and proceed. Sonnet burned **15–30% of its tool budget** on Glob/grep/`find -newer`
sweeps for a plan doc that was never committed, before documenting the absence; Fable never does
this (uses a 1–2-call check or a direct `git show`).

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | not observed to fail | **lacks (2/3 sessions wasted budget)** | not observed |

**Transfer surface — SKILL + PreToolUse HOOK backstop.** A "find-or-fallback" skill (one check,
then fall back, cap at 2 strategies); plus a lightweight PreToolUse hook that counts consecutive
zero-result Glob/Grep calls on doc-like paths and injects a reminder after 2 misses. Trigger is a
judgment call (skill) with a mechanical backstop (hook).

**Measurement — ablation.** Task family: **review** (to-be-built "missing-referenced-doc" seeded
variant — cheap; the generator already seeds conditions). Metric = tool calls before the first
genuine code-verification step, and total tool calls, with/without the skill.

---

### D9 — Constructed instrumentation (bespoke probes / watchers / scripted refactors)
**Sources:** debug Δ5 (3/7 Fable). **One slice.**

Build tools mid-debug when the failure isn't legible to red-green alone: a stall-watcher that
auto-`sample`s on stall; a throwaway repro program; a scripted 20-call-site refactor followed by a
re-grep to verify the transform. This is what cracks hangs and environment wedges. **gpt-5.5 has
zero self-built probes** across 4 sessions — its entire instrumentation repertoire is TDD red→green
(it used `sample`+`kill` only when a hang forced it).

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has (LSP client, `iconv` corpus measurements) | n/a (contract forbids running) | **lacks (pure red-green)** |

**Transfer surface — SKILL (recipe list keyed to symptom class).** In
`superpowers:systematic-debugging`: hang → `ps`/`sample`/stall-watcher; nondeterminism → seed-sweep
loop; bulk mechanical change → script-the-edit + re-grep the result. Recipes over exhortation — this
is a known-moves gap, not a diligence gap.

**Measurement — ablation (probe-only-observable bug).** Task family: **debug**. Seed a bug
observable *only* via a probe (a hang, a wedge); binary: did the model build/use one, or spin
re-reading code?

---

### D10 — Structured durable planning artifacts: Task ledger + handoff docs
**Sources:** plan_orch Δ4 + Δ5. **One slice — starkest tool-usage delta in the corpus.**

A `TaskCreate`/`TaskUpdate`/`TaskStop` ledger with `addBlockedBy` dependency edges, plus persistent
memory writes and a self-contained written handoff doc before pausing a long session. Fable and Opus
use this heavily; **Sonnet-4.6 issued zero `TaskCreate` calls** across all sampled sessions and
**gpt-5.5 zero `update_plan`** despite the tool existing. The gap is **adoption, not availability**.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has | **lacks (0 TaskCreate)** | **lacks (0 update_plan; no durable handoff, silent compaction)** |

**Transfer surface — HOOK (nudge) + gate.** A PreToolUse/turn-count hook: once a session crosses a
turn or Agent-dispatch threshold with no `TaskCreate`, inject a nudge to create a ledger or justify
its absence; a "write a handoff doc" gate on long-session pause/end. Infrastructure already exists —
force adoption.

**Measurement — adherence + proxy outcome.** Task family: **orchestration**. `TaskCreate` per 100
turns by model, before/after the hook; time-to-productive-resume in a fresh session with/without a
handoff doc present (proxy: turns spent re-deriving state before the first real action).

---

### D11 — Catch a wrong/failed subagent result before synthesis
**Sources:** plan_orch Δ7 (Fable n=2 vs Sonnet n=1 miss). **One slice, small n.**

Detect and correct a wrong subagent claim before using it. Fable caught a subagent's "parsed but
not enforced" claim and corrected it against `gate.rs:365`; Sonnet, in the one detectable case, used
a verification subagent that had explored the **wrong repository** (returned all-negative) and
wrote its final review with **no visible acknowledgment** of the failure.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has | has (verify-don't-trust policy) | **lacks (silent on wrong-repo subagent)** | n/a (no subagents) |

**Transfer surface — PostToolUse HOOK (enforce).** On `Agent` results, flag suspicious patterns —
all-negative/all-empty findings, wrong-cwd indicators, result file paths not matching the dispatched
repo — and force an explicit acknowledge-or-redispatch step before the orchestrator's next turn may
cite that result.

**Measurement — triggering.** Task family: **orchestration**. Inject a known-wrong-repo /
known-empty-result canary into a controlled multi-agent eval; measure catch rate (precision/recall
over should-catch items) by orchestrator model.

---

### D12 — Cross-project principle transfer via bounded recon subagent
**Sources:** plan_orch Δ3 (n=1, MEDIUM-LOW confidence). **One slice, single instance.**

Dispatch a bounded, word-capped, read-only subagent purely to read a *different* project's
methodology doc, then apply the extracted principle to the current task — Fable read this repo's
`eval_framework_v1-1.md` and applied its same-family-judge-bias principle to its own
subagent-pairing decisions in an unrelated codebase. A sophistication ceiling marker, not a
high-frequency lever.

| Fable-5 | Opus-4.8 | Sonnet-4.6 | gpt-5.5 |
|---|---|---|---|
| has (n=1) | not observed (may be sample gap) | not observed | not observed |

**Transfer surface — SUBAGENT pattern (suggest, not mandate).** A "cross-project recon" dispatch
template ("read project X's doc on topic Y, return a portability assessment, ≤1500 words"),
suggested as a first move when a design task has a discoverable sibling-project precedent.
Judgment-dependent, so suggested not enforced.

**Measurement — proxy only.** Hard to measure directly; count citations of out-of-repo
concepts/terms in subsequent design docs, before vs after adding the pattern. Lowest-priority,
lowest-confidence entry — included so it isn't lost.

---

## 3. Negative / parity findings (do NOT build here)

Where a cheaper model already matches Fable, where Fable is wasteful, and where an apparent gap is a
config problem rather than a model deficit.

### 3a. Parity — no intervention needed

- **Fix minimality: no delta anywhere.** All 18 debug episodes across all 3 arms produced minimal,
  root-cause-scoped diffs. No shotgun fixes observed. (debug §2.4, Δ7)
- **Environmental-fault attribution: all tested arms already do it** (Fable: spindump, py-version;
  Opus: git config, keychain, LSP false-positive; gpt-5.5: loader stall, corpus drift). (debug Δ7)
- **Status-claim calibration: gpt-5.5 is already best-in-corpus** — it refused ~7× in one session to
  interpret a quiet build as success ("I'll report the build as blocked … rather than making
  unverified claims"). Do **not** build a claim-honesty intervention for gpt-5.5. (debug Δ7)
- **Error recovery (review): uniformly good across all 4 models** — every tool error fixed in 1–2
  calls, no failure loops. The same unquoted-glob bug appears in both Fable and Opus and is trivially
  fixed by both; it is a shared shell habit, not a delta. (review §2.7)
- **Opus-4.8 needs no capability intervention** — it matches Fable across all three slices (CC-1).
  Spend the intervention budget on Sonnet/gpt-5.5.

### 3b. Where Fable is wasteful — do NOT copy

- **Fable scope-creep past an explicit "analysis only" boundary** (plan_orch Δ8, *unconfirmed*): a
  session labeled "analysis, not implementation" nonetheless built a full eval harness and merged to
  `main` over ~40 h. May have been re-approved conversationally — flagged, not asserted. Do not
  encode Fable's loose long-session scope adherence as a target.
- **Fable's premature "the hang mystery is fully closed"** declaration (debug F1-E2) and its
  **stray-file commit** before self-catching (F2-B). Both recovered cleanly, but Fable holds **no
  premature-claim advantage over Opus** (both had exactly one incident; gpt-5.5 had zero premature
  *claims*). Do not treat Fable as the ceiling for claim-conservatism — gpt-5.5 is.
- **The self-dispatch throttle is Fable *scarcity* positioning, not capability.** A Fable session
  carried a user rule "don't dispatch fable as a sub-agent without approval" (5e28ca3a:9), reflecting
  Fable's cost as a scarce orchestrator-tier resource. For the cheaper post-Fable fleet you *want*
  them freely self-dispatchable — **do not** copy the throttle to them. (plan_orch Δ2)

### 3c. gpt-5.5 tool-contract gating — CONFIG fixes, not model gaps

Several apparent gpt-5.5 "gaps" are contract/architecture artifacts the owner fixes in
configuration, not by steering the model:

- **No execution-based verification by Claude in review** is **contract-forbidden**, not a Fable
  weakness: every Claude review prompt says "you may NOT … run tests." gpt-5.5's strongest move
  (writing throwaway adversarial test probes, catching a real panic) is available to it only because
  codex isn't under that contract. The lever is a **contract change** — give *all* reviewer
  dispatches a scoped, disposable exec sandbox (a `review-exec` taskset variant with a throwaway
  git-worktree) — orthogonal to model choice. (review §4)
- **gpt-5.5's inflated tool-call counts** (60–78 vs Fable's ~17) partly reflect that **codex has no
  file-read tool** — every view is a `sed -n`/`rg` inside `exec_command`. Do not read this as
  "broader exploration"; normalize before comparing. (review §2.2)
- **gpt-5.5's zero `update_plan` / zero subagent usage** is structural: the Codex CLI has **no
  subagent-dispatch tool at all**, and `update_plan` went unused despite availability — a
  **prompt/config nudge** candidate (D10's hook), not a capability lift.
- **Cross-family runs are config-blocked, not model-blocked:** the harness's same-family-judge guard
  (`_validate_same_family_judge`) hard-rejects a gpt-5.5 executor with a gpt-5.5 judge. Running
  gpt-5.5 as an *executor* under this catalog's experiments **requires the Claude-as-judge provider
  to be built first** (open TRACKER item: "judge.py is codex-only … REQUIRED before cross-family
  runs"). This is a prerequisite, not a finding.

---

## 4. Top-5 intervention experiments (priority-ordered for the harness)

House rules honored throughout: **one varied element per experiment**, **binary judging**,
**forward-only truth edits** (new tasksets built FRESH — retro-editing truth to fit was proven
asymmetric/gaming-prone in exp1H). Existing eval shapes: `ablation` / `adherence` / `triggering`.

> **Sequencing note.** EXP-1 is the only experiment runnable on **existing** tasksets today; run it
> first as a pipeline shakedown while the debug taskset that EXP-2/EXP-3 share is built (that build
> is the queued "Exp 3" blocker in `TRACKER.md`, ≈ Task-5 curation effort). EXP-2 and EXP-3 carry
> the highest capability-lift for the target models and should follow immediately.
> **Prerequisite for any gpt-5.5-*executor* arm:** build the Claude-as-judge provider (§3c).

### EXP-1 — Wrong-vs-smell in-tag qualifier (delta D7)
- **Treatment artifact (single varied element):** the review prompt-template OUTPUT FORMAT amended
  to require `SEVERITY (defect|smell)` in the literal tag, plus a deterministic regex lint that
  rejects a non-compliant review.
- **Target models:** Sonnet-4.6/5, gpt-5.5, Opus-4.6 (all leave the distinction in prose).
- **Task set:** **existing** `review-seeded` + `review-hard` — no new data.
- **Eval shape / judging:** `adherence`, binary per finding (regex-computed compliance), plus a
  guardrail check that recall/false-findings don't regress.
- **Expected direction:** near-100% tag compliance under treatment; no semantic-quality loss.
- **Cost:** **LOW** — template edit + regex; runs on existing tasksets. Best early win / shakedown.

### EXP-2 — Unconditional verify-before-done gate (delta D1)
- **Treatment artifact:** a Stop/completion hook that blocks a "done/fixed/passing" claim unless the
  last-edit→claim window contains a suite-scope test run + parsed non-zero pass count.
- **Target models:** gpt-5.5 (observed 2/4), Sonnet-4.6/5.
- **Task set:** **to-be-built** debug taskset (`test_cheap`, 20 reproducible-failing-test items —
  the queued Exp 3 blocker).
- **Eval shape / judging:** `adherence` ("widest scope run after final edit", binary tiers) +
  `ablation` on regression-escape rate (binary held-out check).
- **Expected direction:** treatment raises widest-scope-run rate and cuts regression escapes on the
  target models, with no quality loss.
- **Cost:** **MEDIUM** — one debug taskset (shared with EXP-3) + one hook.

### EXP-3 — Predict-then-probe rule in systematic-debugging (delta D2)
- **Treatment artifact:** a "predict-then-probe" directive + worked example added to
  `superpowers:systematic-debugging` (state confirm/disconfirm before each probe; "pre-existing/
  environmental" requires a differential run). One varied element = the skill delta.
- **Target models:** gpt-5.5 (weak), Sonnet-4.6/5 (untested).
- **Task set:** the same debug taskset as EXP-2, plus a `triggering` set (should the skill fire).
- **Eval shape / judging:** `ablation` with binary judge criteria — (i) discriminating prediction
  preceded the probe, (ii) any pre-existing/env claim was differential-backed — and `triggering`
  precision/recall for skill invocation.
- **Expected direction:** treatment raises prediction-precedes-probe and differential-backed-
  attribution rates.
- **Cost:** **LOW–MEDIUM** — skill edit; shares the EXP-2 taskset.

### EXP-4 — Guardrailed dispatch-brief template (delta D3)
- **Treatment artifact:** a required-fields dispatch-brief template (exact error; hypothesis-labeled;
  disconfirming condition; stop rule; red-before-green; verification scope) in
  `subagent-driven-development` / the a2a-bridge prompt registry, with a pre-dispatch lint.
- **Target models:** any orchestrator dispatching cheaper fixers — this protects the owner's actual
  post-Fable pipeline (cheap workers).
- **Task set:** **to-be-built** delegated-fix set (reuse `review-hard` defects as seeds).
- **Eval shape / judging:** `adherence` (binary presence of each of the 6 fields per brief) +
  `ablation` on downstream "papered-over" incident rate (binary: fix applied while planted
  disconfirming condition still true).
- **Expected direction:** treatment briefs carry the fields; fewer papered-over fixes downstream.
- **Cost:** **MEDIUM** — template cheap; needs the delegated-fix harness. Requires Claude-as-judge if
  a gpt-5.5 executor is used as the fixer arm (§3c).

### EXP-5 — Find-or-fallback skill (delta D8)
- **Treatment artifact:** a "find-or-fallback" skill (one existence check, then fall back to "not
  committed — verifying against code only", cap 2 strategies). Run skill-only first (one varied
  element); the PreToolUse zero-result-search hook is a *separate* follow-up experiment, not bundled.
- **Target models:** Sonnet-4.6 (observed 2/3 sessions wasted 15–30% of budget); Opus/gpt-5.5 as
  controls.
- **Task set:** **to-be-built** "missing-referenced-doc" `review-seeded` variant (cheap — the
  generator already seeds conditions).
- **Eval shape / judging:** `ablation` — tool calls before first genuine code-verification step, and
  total tool calls; binary success = fell back within ≤2 searches.
- **Expected direction:** treatment collapses Sonnet's doc-hunt tail with no recall loss.
- **Cost:** **LOW–MEDIUM** — one seeded taskset variant + one skill.

**Deferred (strong, but not top-5):** the multi-wave review-gate loop (D5) and the durable-ledger
hook (D10) are high-value but need an orchestration harness that does not yet exist; the reviewer
**exec-sandbox** contract change (§3c) is a genuinely orthogonal lever worth its own line of work.

---

## 5. Per-model intervention priority (summary)

Derived from the D1–D12 gap columns; drives where to spend first.

| Target model | Highest-priority deltas | Notes |
|---|---|---|
| **gpt-5.5** | D2 (predict-then-probe), D1 (verify-gate), D9 (constructed instrumentation), D10 (planning artifacts) | Already best at claim-honesty (§3a). Several "gaps" are config, not model (§3c). Executor arms need Claude-as-judge first. |
| **Sonnet-4.6** | D4 (verification economy — worst cost), D8 (find-or-fallback), D5/D10/D11 (orchestration + subagent-result hygiene), D7 (tagging) | Organic debugging = **no data**; debug deltas are review-mode proxies. Meets the bar under contract (CC-2) — enforce structure. |
| **Sonnet-5** | Same as Sonnet-4.6 (extrapolated) | **Untested** — essentially absent from corpus. Treat gaps as ≤ Sonnet-4.6. |
| **Opus-4.6** | Likely inherits Claude-family infra; verify against Opus-4.8 parity | **Untested** — extrapolated as an Opus-4.8 lower bound. |
| **Opus-4.8** | **None for capability** | At parity with Fable across all three slices (CC-1). Only the enforceable surfaces (D1/D7 hooks) as free wins. |

---

## 6. Provenance

- `mining/out/deltas/review.md` — review slice (8 Fable / 5 Opus / 3 Sonnet / 4 gpt-5.5 sessions;
  7 parallel sub-agents; 8-dimension rubric). Report: `.superpowers/sdd/task-M3a-report.md`.
- `mining/out/deltas/debug.md` — debug slice (7 Fable / 7 Opus / 4 gpt-5.5 organic episodes;
  Sonnet = review-mode proxy only). Report: `.superpowers/sdd/task-M3b-report.md`.
- `mining/out/deltas/plan_orch.md` — planning/orchestration slice (7 Fable / 5 Opus / 3 Sonnet /
  2 gpt-5.5 sessions). Report: `.superpowers/sdd/task-M3c-report.md`.
- Harness grounding: `experiments/exp1-review-shape.yaml`, `exp1h-review-shape.yaml`;
  `harness/rubrics/review_judge.md`; `harness/metrics.py` (`adherence`, `triggering_metrics`);
  `harness/config.py` (`_EVAL_SHAPES = {ablation, adherence, triggering}`); `TRACKER.md`;
  `mining/out/coverage.md`.

---

## 7. Limitations

- **Single owner, ~3–4 repos, mostly Rust + Python.** Everything here is one person's working style
  on one small project family; none of it is a population estimate.
- **Scaffold confound (the central caveat).** All Claude sessions ran with superpowers skills +
  CLAUDE.md + a self-imposed review pipeline active. Fable's discipline cannot be cleanly separated
  from that scaffold. D1–D12 are best read as "behaviors observed under Fable + scaffold," and the
  interventions as attempts to **port the scaffold** — which CC-2 argues is exactly the right move,
  but the attribution is unproven.
- **Small n.** Review 8/5/3/4; debug 7/7/0-organic/4 episodes; plan-orch 7/5/3/2. Curated for
  matched comparability, not powered. Treat frequencies as "observed this many times here," not rates.
- **Process deltas evidenced; outcome superiority NOT proven.** These are organically-collected
  production sessions without ground truth. We can compare cost and technique, not independently
  verify that Fable's leaner verification never misses a defect a longer chase would catch. Closing
  that gap is exactly what §4's seeded experiments are for — none has been run.
- **Sonnet-4.6 organic debugging: zero data.** Its debug deltas rest entirely on a review-mode proxy.
  **Sonnet-5 and Opus-4.6 are effectively absent** from the corpus — their gap columns are
  extrapolations, flagged as such.
- **Reasoning traces largely unavailable.** Claude thinking blocks are empty in stored transcripts;
  gpt-5.5 reasoning is almost never persisted. Hypothesis formation is observable only when verbalized
  in assistant text — a systematic under-observation of internal epistemics.
- **Corpus-selection fragility.** The `task_type` tagger was ~100% contaminated on the Claude debug
  bucket and mislabeled Sonnet review sessions; `claude_index.jsonl` was clobbered mid-mining
  (2,397→20 rows), so plan-orch counts are from a cached earlier read. Manual recovery may have
  missed sessions; the orchestration bucket is known to undercount long tool-diluted sessions.
- **Review-shape is already at ceiling on the weak executor.** exp1/exp1H showed a **dead heat**
  (Haiku, 8/15 both arms, McNemar p=1.0) — generic prompt-*shape* elements do not move a weak
  executor on the current review tasksets. This is why §4 leans on **enforcing surfaces (hooks/gates)
  and harder/new tasksets**, not more prose; but the assumption that a harder taskset will expose the
  deltas is itself unvalidated.
- **All twelve deltas and five experiments are hypotheses.** Nothing here has been A/B'd. This is
  transcript-evidenced hypothesis generation, not validated intervention.
</content>
</invoke>
