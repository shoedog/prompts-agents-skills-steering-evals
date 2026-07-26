# Wave-3 steering-move experiment queue — DRAFT (2026-07-25, pending owner review)

Moves (2)-(5) of the Wave-3 line (TRACKER "Failure-mode mitigation waves"; evidence
~/Documents/agent-failure-modes-2026-07-25.md sections 4-B/D and 8). Move (1)
cite-or-label is drafted: `experiments/exp-w3a-cite-or-label.yaml` (+ its negative-control
companion) over the new SEED taskset `tasksets/mechanism-claims-v0`. This file only
sketches; the owner curates TRACKER — no entries were added there.

Harness facts constraining every sketch (verified against harness/ this session):
executors are toolless single-turn `claude -p` calls (claude_cli.py disallows
Bash/Read/etc.), the graded surface is the hard-coded `## FINDINGS` + `VERDICT` block
(judge_assert.py), judge output keys are hard-coded to the review vocabulary (judge.py
`_REQUIRED_KEYS`), adherence metrics are keyed to review-shape.* labels only (metrics.py
`_DIRECTIVES`; TRACKER backlog), and a negative control is a companion config, not a
third arm (run.py ARMS is baseline/treatment).

## w3b — rewrite-from-source-not-memory (D2; mode 8, `608a7a2a` L3183)
- Deployment form: steering (`elements/rewrite-from-source/steering.md`, ~1 sentence:
  consolidation folds diff every claim against the source doc, never rewrite from memory).
- Taskset need: NEW — `consolidation-drift-v0`: context quotes a short source doc
  (handoff/spec excerpt), the diff is a consolidation rewrite (roadmap/summary fold);
  seeded items carry one memory-drift claim (number changed, mechanism conflated, scope
  blurred — the L3183 pattern), clean items are faithful folds with tempting rewordings.
- Judge rubric: stock review judge; drift = the seeded "defect", acceptable_match
  requires quoting/citing the source line the rewrite contradicts.
- Blocker (honesty note): in review shape this measures drift DETECTION, not drift-free
  PRODUCTION — the move's real target is the agent's own rewriting. Production form
  needs a free-form deliverable + a claims-vs-source judge, i.e. new assert/judge keys;
  do not force that into the current harness. Detection is still a fair first signal
  (same discipline, opposite direction), and the production form can ride the planned
  adherence-key generalization.

## w3c — pushback-re-runs-the-witness (D3; R5: 2 of ~4 pushbacks overturned)
- Deployment form: steering (before rejecting a reviewer WRONG, re-run their witness;
  in-harness proxy wording: trace the witness against the code before adjudicating).
- Taskset need: NEW but cheaply derivable — `pushback-adjudication-v0`: context carries
  a prior reviewer's WRONG finding + its witness argument; the diff is the code. Seeded
  = reviewer is right (pass = REJECT restating the defect with citation); clean =
  reviewer is wrong (pass = APPROVE, no findings). Seed material exists: review-hard
  truth + real graded findings (TP and FP) in results/exp-d7*/judge/ — curation is
  reframing, not invention.
- Judge rubric: stock review judge; acceptable_match on seeded items requires engaging
  the witness's concrete scenario, reject_if bare deference ("reviewer says so").
- Blocker: true witness RE-EXECUTION is impossible for a toolless executor — the exp
  validates witness-tracing-before-pushback only. The re-RUN half stays a template
  clause (forensics places D3 as steering + adjudication-template) or a bench/-style
  live-session check like exp-3's.

## w3d — handoff-claim quarantine (D1; mode 9, `fb80415b` L334)
- Deployment form: steering (actionable handoff claims are unverified until traced this
  session; verify named entry points first).
- Taskset need: NONE beyond mechanism-claims-v0 — mc-03/mc-07 ARE handoff-claim items
  (RESUME "next step (runnable now)" vs the flag accept-list). If exp-w3a shows the
  cite-or-label rule already moves those items, D1's steering half may be subsumed;
  a dedicated run is a ~4-item v1 extension reframing context as session start ("you
  just resumed from this handoff") rather than a new set.
- Judge rubric: unchanged (the citation bar is already in those items' truth).
- Blocker: none for the steering half. The SessionStart-hook half is config
  engineering per the forensics placement table, not an exp.

## w3e — velocity governor (candidate; forensics section 8)
- Proposed form: conditional steering (probes chaining faster than ~N min ⇒ mandatory
  confirms-if / falsifies-if / cannot-see header before the next probe).
- NOT expressible in this harness — say so rather than force it: the trigger condition
  is inter-probe wall-clock cadence inside an agentic session; single-turn toolless
  items have no probes and no clock. eval_shape `triggering` exists in metrics.py but
  nothing in the promptfoo path produces should_trigger/did_trigger rows for timing.
- Honest path: (a) observational — mining/ already timestamps probe chains; add a
  cadence detector and measure header-presence vs wrong-conclusion incidents
  (recurrence-after-admission metric, TRACKER Wave-2/3 line); (b) if causal evidence
  is required, a bench/-style live-session A/B (exp-3 pattern), outside this harness.
  The B5 header itself is Wave-2 validator/template work either way.

## Taskset reuse summary
- mechanism-claims-v0 (new, SEED, unverified): serves (1) now and (4) with a small v1
  extension — the only Wave-3 moves needing zero fresh curation once it is verified.
- review-hard: serves none of (2)-(5) directly, but with results/exp-d7*/ judge records
  it SEEDS (3) at low cost.
- (2) needs the one genuinely new set (consolidation-drift-v0); (5) needs no taskset
  because it should not run in this harness.

Verification status of this queue: sketches checked against harness/config.py,
gen_promptfoo.py, judge.py, judge_assert.py, metrics.py, run.py and ci/test_smoke.py
as of 2026-07-25; no harness changes assumed anywhere above. DRAFT — owner review
gates everything.
