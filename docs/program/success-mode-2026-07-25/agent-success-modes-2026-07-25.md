# Agent success modes — curated catalog + candidate artifacts (v1 draft)

Status: DRAFT FOR OWNER REVIEW — nothing here is promoted; promotion is owner-gated exactly
like the failure side. Program: the success-mode pass (owner-approved 2026-07-25 ~evening),
the inversion of the failure-mode mitigation program: mine what WORKS → validate causal
claims (exp-NN) → operationalize (SSOT steering / templates / bridge features / detectors) →
promote with sign-off.

Companion evidence: `~/Documents/HANDOFF-2026-07-25-failure-mode-program.md` (checkpoint log
= the incident-by-incident record), `~/Documents/w2-tasks/` (verdicts, verify dirs, run
logs), failure-side twin `~/Documents/agent-failure-modes-2026-07-25.md`.
Mining dual: `mining/scripts/detect_success_signatures.py` (in build at time of writing;
outputs land in `mining/out/success_*.{jsonl,md}`).

Method note (honesty bar): every entry below is OBSERVATIONAL — validated in the sense of
"worked repeatedly under real load on 2026-07-25 and is documented," not exp-controlled.
Entries whose value claim is CAUSAL (doing X produces better outcomes than not-X) get an exp
plan before steering-tier promotion; entries that are PROCEDURAL (X is a discipline whose
absence is a documented failure mode) can promote on owner judgment without an exp, same as
"Verify before done."

---

## 1. Catalog

Legend — Form: steering = SSOT carrier rule; template = prompt/workflow template clause;
bridge = a2a-bridge feature; detector = mining signature; doc = protocol/principle document.
Priority: NOW = draft ready in §2; NEXT = build after NOW batch; EXP = needs experiment
before steering promotion.

### S1. Fix-vs-redispatch decision rule — Form: steering + bridge. Priority: NOW (steering), NEXT (bridge)
Pattern: when a reviewed artifact is rejected, classify the findings first. Closed,
enumerable findings (each names input/state + incorrect result + a bounded fix) → targeted
fix ON THE EXISTING ARTIFACT. Open-class findings (the reviewer is sampling an inexhaustible
defect class — each round finds NEW instances of the same kind) → stop retrying, escalate to
spec/design. Fresh restarts are almost never optimal: they re-derive context and re-roll the
same distribution.
Evidence: 6/6 targeted operator-fixes merged clean (W2a unreachable+E0004, W2d validator,
W2a-2 cap authority, W2c cap family, cleanup-1 E0382 — checkpoint log 09:20→23:10); the
W2b classifier line as the open-class exemplar (3 rounds, oscillating heuristic boundary,
resolved only by design escalation). Prior bridge behavior (fresh clean tries on repeated
REJECT) is the documented anti-pattern.
Bridge form: a third arm in the convergence contract's REJECT handling — classify findings
closed/open (reviewer-tagged), route closed→fix-on-artifact, open→halt+escalate.

### S2. Attribution-control-before-blame — Form: steering + bridge. Priority: NOW (steering), NEXT (bridge)
Pattern: before attributing a regression to a change, run the BASE artifact in the SAME
environment that produced the failure. "It was green before" is not a control unless the
green was in the same topology.
Evidence: overturned two wrong attributions in one day — W2d (my "green at e8ed61f ⇒ W2d
broke it" was host-green vs container-red; base failed identically in-container; true cause
a latent 2026-07-18 validator bug) and W2a-2 (292MB debug binary vs duplicated stale cap
constant, latent since e159915). Both times the control converted a wrong blame into a real
root cause + a latent-bug fix.
Bridge form: verify pipeline auto-runs a base-control when a hermetic gate fails on a suite
the diff plausibly didn't touch (first-hermetic-reach heuristic), and stamps the hand-off
with the control's result.

### S3. Design-review ladder — Form: doc + template (named workflow). Priority: NEXT
Pattern: unconvergeable implementation churn escalates to: specialist DESIGN draft →
adversarial spec-review panel (repo access, verify claims in source) → revision with a
findings-RESOLUTION TABLE → re-review that verifies each claimed resolution real-vs-hollow →
normative errata folded into the spec → implementation charters cut from the spec.
Convergence signature: finding class shifts coherence → code-grounding → wire-edge (v1→v2→v3),
which is what converging TOWARD ground truth looks like.
Evidence: W2b Attested Prefix Cut — 3 panel rounds to READY-TO-PLAN after 3 implement
rounds had churned; spec now in-repo (docs/design/attested-prefix-cut-v3.md + §18 errata);
Task P chartered off it same-day.
Form: write the ladder as a repeatable bridge workflow doc (design → spec-review loop with
READY-TO-PLAN gate + resolution-table mandate + errata convention).

### S4. Impossibility-argument-first — Form: template clause. Priority: NEXT (partially exists)
Pattern: design briefs explicitly LICENSE refuting the task premise. The specialist proving
"no text-only classifier satisfies never-truncate" was the single highest-leverage move of
the W2b line — it killed round 4+ of a dead approach and reframed the spec.
Evidence: w2b-sol-design-brief.md (open-brief, "marker-anchoring labeled
candidate-not-premise") → impossibility argument in v1 §1.
Form: dispatch-brief-contract clause: "If the brief's framing is wrong, your first
deliverable is the refutation with evidence — a proven 'this frame cannot work' outranks a
compliant artifact inside a broken frame."

### S5. Provenance-disclosed operator fixes — Form: doc + template. Priority: NEXT
Pattern: when the operator patches an agent's artifact, the fix goes in a SEPARATE commit,
authorship is named in the review input, and reviewers are directed to scrutinize the
post-hoc fixes HARDEST. Every such review today engaged the fixes specifically (including
catching my spec-authorship error on W2b v2).
Evidence: w2a-review-input.md pattern; W2d 4678088 disclosure; cleanup-1 cache_key fix
light-review; reviewer engagement visible in all verdict files.
Form: short operator-fix protocol doc + a review-input template block (provenance tiers:
agent / operator / debug-agent; per-commit attribution; scrutiny directive).

### S6. Warm-specialist reuse — Form: orchestrator guidance + EXP. Priority: EXP
Pattern: continue a context-loaded specialist via SendMessage instead of dispatching fresh.
The warm debug agent solved three successive container-topology cases (W2d 8-test batch,
W2a-2 cap, W2c family) each faster than the last, carrying the topology model forward.
Evidence: checkpoint entries 12:15, 13:55, 18:35 — same agent, three root-causes, latency
visibly shrinking (no controlled timing).
Causal claim ("faster/cheaper than fresh") is measurable → exp: matched diagnosis tasks,
warm-continue vs fresh-dispatch arms, wall-clock + tokens + probe count. Guidance rule can
promote as NEXT; the quantified claim waits for the exp.

### S7. Checkpoint-after-every-stage + durable evidence dirs — Form: template + validator extension. Priority: NEXT
Pattern: one live handoff doc checkpointed after every stage (newest-first log), plus
per-gate evidence dirs (fmt/clippy/build/test logs each ending in an EXIT line + STATUS
file). The program crossed multiple session compactions/gaps losslessly; every done-claim is
re-derivable from disk.
Evidence: this program's handoff + w2-tasks/*-verify/ dirs; the 09:15 truth-correction was
POSSIBLE because the prior session's claim could be checked against its stdout file.
Form: handoff/evidence-dir template doc + verification_schema_check extension (S-rule:
evidence dir per gate with exit codes) — warn-only first, same rollout as the other schema
rules.

### S8. Convergence cap declared before the round — Form: steering (merged into S1 draft) + bridge config. Priority: NOW
Pattern: declare the retry cap BEFORE dispatching the round, then honor it — cap reached ⇒
park + escalate, never silently extend. W2b round 3 was declared the cap at 15:10 and
honored at 17:00 despite green gates on the fix (the temptation case: "just one more").
Evidence: checkpoint 15:10 ("ROUND 3 IS THE CAP") → 17:00 (HELD FOR OWNER); taxonomy
documents 11-14-round churn elsewhere when no cap existed.
Bridge form: max_review_rounds config honored by the convergence contract (bridge already
has max_attempts for verify; this is the review-round analogue).

### S9. Two-lens review with per-reviewer accounting — Form: detector + TRACKER metric. Priority: NEXT
Pattern: two independent reviewers + synthesis that DECOMPOSES disagreements into
confirmed/refuted/scope-dispute per reviewer, accumulating reviewer-accountability data
(codex post-merge REJECT on W2a: 1 confirmed / 1 refuted / 1 scope → the confirmed one
became W2a-2, a real gap).
Evidence: w2a codex adjudication (checkpoint ~11:30); every W2 verdict file carries the
decomposition.
Form: mining signature (refutation/confirmation accounting present in verdicts) + a TRACKER
metric line (per-reviewer confirmed:refuted ratio over time) — data plumbing before any
steering claim.

### S10. Gates must price in the honest degraded path — Form: doc (principle) + applied instances. Priority: NOW
Pattern: an enforcement gate that only accepts success-shaped evidence trains fabrication.
Every hard gate needs (a) the pass form, (b) an honest-degraded form — env-limited marker +
NAMED exclusions carried into the done-claim — and (c) reason text that TEACHES the
compliant degraded form. The egress catch was exactly this: the gate blocking the honest
"container can't run the suite" report was the bug, not the report.
Evidence: verify_gate.sh egress catch (4/4 synthetic Stop cases), codex/kiro gate parity
builds, the SSOT rule's egress sentence.
Draft in §2.3.

### S11. Reader-grounds-reasoner pairing — Form: orchestration pattern + EXP. Priority: NEXT (pattern doc), EXP (causal claim)
Pattern (owner-nominated 2026-07-25, observed by owner + Opus): strong reasoners (opus,
sol, fable) sometimes miss reading through/tracing the code — plausibly because inference
strength substitutes for reading (hypothesis, not established). Pair them with a
strong-READER model (sonnet, luna) whose deliverable is verbatim excerpts + file:line
citations; the reasoner must anchor claims to the reader's citations. Synergy with
cite-or-label (exp-w3a) and cite_check validator: the reader supplies exactly the currency
the citation bar demands.
Evidence: owner observation (sessions TBD — mining fan-out should look for both the failure
shape [reasoner asserting untraced code behavior] and the success shape [reader-supplied
citations correcting a reasoner]). Note: today's W2b panel rounds partially enacted this —
the round-2 panel's value was largely CODE-GROUNDING sol's coherent-but-unanchored spec.
Form: orchestration pattern doc + bridge workflow variant (reader node feeding a reasoner
node); exp-s3: reasoner-alone vs reader+reasoner on code-tracing tasks, measuring
wrong-assertion rate and citation validity.
LIVE TRIAL (owner-directed 2026-07-25 ~22:00): mining slices E (a2a-bridge, luna) and F
(slicing/prism, sonnet) are structured as the trial's read half — EVIDENCE blocks
(file:line + verbatim quotes, 2-3 per finding) strictly separated from INTERPRETATION, so
a reasoner (fable/opus/sol) can evaluate findings from citations alone. Trial metrics at
the reasoner pass: citation validity (spot-check quotes), evidence sufficiency (could the
reasoner judge without re-reading?), finding acceptance rate, novel-vs-known ratio.

### Mined nominations pool (Wave S0 qualitative rider, 2026-07-25 — pending curation into numbered entries)
Nine novel patterns from 5 high-signal historical sessions (slicing, stockTrading ×2, ssot
marathon, codex bridge-orchestrator), each with session:line evidence:
verify-first premise measurement; refutation propagated to durable memory; independent
recomputation of peer findings; claim quarantine after a burned claim; graded adjudication
scorecard with self-error accounting; gate-vacuity audit ("can every gate fail?");
evidence-probing reviewer blockers before compliance (skepticism runs upward);
precedent lookup for accepted controls + named separator per attribution step; declared
liveness patience window + dischargeable objections.
Full writeups: ~/Documents/success-mining/rider-findings-2026-07-25.md. Curation happens
when the model-mix mining fan-out (owner-directed) reports.

### F-nominations routed to the FAILURE taxonomy (not success artifacts)
- F1. Resource-residue-after-completion (owner-nominated 2026-07-25): clones/targets/cache
  volumes not reaped when their purpose ends (~375 GB docker cache volumes; retained clones
  are deliberate provenance — the failure is UNDECIDED residue, no reap policy). → mining
  nomination + a reap-policy owner decision.
- F2. Evidence-destroying error classification: an error path that collapses variants and
  discards the underlying message (smoke.config classifier eating 4 ConfigX variants;
  workflow node failures needing RUST_LOG archaeology). Observed 2× on 2026-07-25;
  cleanup-2 fixes the instance; the CLASS goes to the taxonomy (dual of S10: error paths
  must carry evidence forward, not summarize it away).

---

## 2. Draft artifacts (NOW batch — for owner sign-off, NOT applied)

### 2.1 Steering rule candidate: "Convergence discipline" (S1+S8)

Proposed for the SSOT carrier (all three targets), tier: instruction; enforcement candidates
later (bridge convergence contract). Draft text:

> ## Convergence discipline (candidate: observational 2026-07-25; exp pending)
> Declare the retry/review-round cap before dispatching the round, and honor it — cap
> reached means park and escalate, never silently extend. On a rejected artifact, classify
> the findings before choosing the next move: closed enumerable findings (each names the
> input or state, the incorrect result, and a bounded fix) get a targeted fix on the
> existing artifact; open-class findings (each round surfaces new instances of the same
> kind) mean stop retrying and escalate to spec or design. A fresh restart is almost never
> the right move — it discards context and re-rolls the same distribution.

### 2.2 Steering rule candidate: "Attribution control" (S2)

> ## Attribution control (candidate: observational 2026-07-25; exp pending)
> Before attributing a failure to a change, run the base (pre-change) artifact in the same
> environment that produced the failure. Green in a different environment is not a control —
> it confounds environment with regression. State the control's result next to the
> attribution; an attribution without a same-environment control is a hypothesis, not a
> finding.

### 2.3 Principle doc candidate: "Honest degraded paths in enforcement gates" (S10)

> When you build a gate (stop hook, verify gate, schema check, review gate), specify three
> things or the gate is unfinished:
> 1. The PASS form — what fully compliant evidence looks like.
> 2. The HONEST-DEGRADED form — the compliant way to report "the checked thing was
>    impossible here": an environment-limitation marker PLUS named exclusions, carried into
>    the done-claim. If the gate cannot accept this, agents that hit real limits are trained
>    to fabricate the pass form.
> 3. TEACHING reason text — the block message states both accepted forms, so the first
>    failure teaches the compliant path instead of inviting retries-until-fabrication.
> Litmus: for every gate, ask "what does the honest agent in the worst environment do?" If
> the answer is "fail forever" or "lie," the gate is the bug. Instances: verify_gate.sh
> egress catch; codex/kiro parity gates; the egress sentence in "Verify before done."

### 2.4 Detector duals (S6-adjacent; build delegated, uncommitted)

`detect_success_signatures.py` v1 detectors: attribution_control, refutation_accepted,
cap_honored, provenance_disclosed, expect_falsify_probe, checkpoint_cadence (session-level).
Same architecture as the failure detector: high-precision strong buckets, known-incident
validation (2026-07-25 session as ground truth), baseline + nominations outputs. Purpose:
(a) find historical exemplars the seed list missed, (b) measure whether promoted success
practices RECUR after promotion — the dual of recurrence-after-admission.

---

## 3. Validation plan (what needs an exp before steering-tier causal claims)

- exp-s1 (warm-specialist reuse, S6): matched diagnosis tasks; arms = warm-continue vs
  fresh-dispatch; metrics = wall-clock, tokens, probes-to-root-cause. Needs task curation
  (~exp-3-shaped effort).
- exp-s2 (convergence discipline steering text, S1/S8): exp-w3 harness shape — does the
  rule text change fix-vs-redispatch choices on synthetic REJECT scenarios? Can ride the
  mechanism-claims harness pattern after exp-w3a runs.
- S2/S5/S7/S10 are procedural-discipline rules (absence = documented failure mode);
  recommend owner-judgment promotion without exp, same tier as "Verify before done."
- S9 needs data plumbing first (verdict-file accounting parser), then it IS the metric.

## 4. Proposed promotion queue for the owner

1. Sign off §2.1 + §2.2 wording → SSOT carrier → emit (same rollout as Verify-before-done).
2. Accept §2.3 as docs/ principle page (prompts-skills-steering or ssot-agents — your call).
3. Detector duals: review baseline once built → add success_nominations triage to the
   existing daily cron (one-line addition, owner-gated since cron is live infra).
4. NEXT batch build order (my recommendation): S5 operator-fix protocol → S3 ladder doc →
   S7 template+validator extension → S4 brief clause → S9 accounting parser.
5. EXP queue: exp-s1, exp-s2 (after exp-w3a; shares harness).

### S12. Custody promotion (commit-for-protection) — Form: steering + protocol habit. Priority: NOW (owner-initiated 2026-07-25)
Pattern: at every stable point, work products leave ephemeral custody (scratchpad,
untracked files, single mutable copies) for durable custody (commit/push; non-repo docs get
a repo snapshot). Protection is measured by what survives losing any one store. Transcripts
are a partial safety net ONLY for content that transited an agent's tools — bytes that
never passed through a captured read/write leave no shadow.
Evidence (2026-07-25, both polarities, same evening): the six mining reports survived
harness-blocked file writes because their bytes landed in append-only transcripts and were
re-persisted; the clobbered untracked VERIFICATION.md was UNRECOVERABLE — five channels
exhausted (no APFS snapshots; no Write/Edit record anywhere; the clobbering session never
read it and its Write.originalFile was null; no read-side capture in any claude project
dir; codex all-July mentions were brief boilerplate). Adjacent mined patterns: slice D F4
tail (verification artifacts promoted from scratchpad into repo), slice F finding 7
(ledger+handoff durable custody).
Candidate steering line: "At each checkpoint, commit or snapshot anything you'd mourn —
untracked + single-copy means one accident from gone."

#### S11 TRIAL RESULT (fable reasoner pass, 2026-07-26 — full eval: success-mining/s11-trial-eval-2026-07-26.md)
14 citations sampled: ZERO fabricated; 64% verbatim-at-line; defects all mechanical (3
spliced-fragment "quotes", 1 line drift, 1 sibling-file transposition). Acceptance 17/17
findings from EVIDENCE blocks alone; novelty ~12/17. VERDICT: strategy works; formalize
with (1) one-quote-one-span rule, (2) mechanical citation checker gating reports
(candidate mining/scripts/check_citations.py), (3) per-file quote verification. exp-s3
still owed for the causal counterfactual.
