# Agent success modes — catalog v2 (curated families)

Status: DRAFT FOR OWNER REVIEW. v2 curates the full Wave S0-S1 mining pool (~45 patterns:
seed catalog S1-S12 + rider + slices A-F) into seven families. Per-item detail lives in
the slice reports (docs/program/success-mode-2026-07-25/report-slice*.md + rider); this
document is the promotion map. Citation key: A3 = slice A finding 3; R5 = rider item 5;
S# = v1 seed entry. Confidence carried from the reports; nothing here is promoted without
sign-off.

---

## Family 1 — Convergence discipline (anchor: S1+S8)

Core (v1, NOW): declared round caps, honored; closed-enumerable findings → fix on
artifact; open-class → escalate to design. Draft steering text in v1 §2.1.
Mined additions:
- First-error semantics → complete enumeration before retry (A2, high) — when a gate
  provably reports only its first failure, enumerate the whole defect population first.
  Form: steering clause appended to the v1 draft.
- Fix rounds preserve the intended failure locus (B6, med) — repair the defect, re-prove
  the original failure point; never weaken the assertion. Form: fix-brief template clause.
- Restructure-aware re-review (F5, high) — a fix wave that MOVES code gets "what behavior
  did the restructure carry, and does it still hold?" added to its re-review prompt.
  Form: bridge re-review prompt clause.
- Diff-of-diffs anchoring (C8, med) — round N re-review diffs against round N-1's diff,
  proves byte-identity of untouched hunks, reads only the delta. Form: re-review template.
Promotion rec: extend the v1 §2.1 steering draft with the A2 clause; the three template
clauses go to the bridge prompt templates as one batch.

## Family 2 — Evidence admissibility & attribution (anchor: S2)

Core (v1, NOW): base-in-same-environment before blame. Draft in v1 §2.2.
Mined additions:
- Probe admissibility before belief updates (A1, high) — malformed probes are failures of
  the probe, not evidence; classify admissible before updating. Enacted by the miner
  itself mid-run. Form: steering clause (pairs with the exp-3 rule) + detector.
- Exit-0-is-not-evidence + observational-equivalence check (D-F7, high; F6, high) — name
  another mechanism producing identical output before claiming discrimination; on
  silent/nonzero exits read the artifact's structured invalidity reason, never the code.
  Form: steering clause + harness template line.
- Separate approval/orchestration/execution clocks (A3, high) — decompose apparent
  latency before blaming components. Form: bridge feature (timestamp set).
- Named separator per attribution step + precedent lookup for accepted controls (R9,
  high) — every step names its discriminating experiment; known controls come from
  history, not re-derivation. Form: debugging-discipline appendix.
- Minimal host-semantics probe (E6, med) — platform uncertainty → disposable probe with
  competing predictions. Form: worked-example doc (same family as exp-3 rule).
- Environment-refusal vs code-failure classification (E5, high) — setup failures classed
  separately, same-command minimal-capability rerun, remaining structural issues still
  reported. Form: detector (setup_incomplete vs failure) + template.
- Execution-topology labels on evidence (E7, high) — synthetic/real-OS/provider/container
  never conflated; unexercised boundaries named. Form: evidence schema fields
  (verification_schema_check candidate rule).
Promotion rec: ONE new steering rule "Evidence admissibility" merging A1 + D-F7 (draft
below, §Promotion queue); the rest land as schema/template/bridge items.

## Family 3 — Review & adjudication epistemics (anchor: S9 + WRONG/SMELL)

Mined additions:
- Mechanism-level falsification bar for downgrades (C4, high) — WRONG→SMELL only via
  constructive proof the flagged condition cannot produce a wrong output; absence of a
  counterexample never suffices. Form: steering clause extending the WRONG/SMELL rule.
- Evidence-probing reviewer blockers — skepticism runs upward (R7, high; enacted again
  by the Task P panel disclosure flow). Form: adjudication template clause.
- Independent recomputation of peer findings (R3; recurrences C: f1ece435:162,
  9bc8a39a:920/2647, D: 53d4f209:1506/1758 — now 6+ enactments, the pool's most
  recurrent pattern). Form: steering clause.
- Graded adjudication scorecard with self-error accounting (R5, high) +
  RESOLVED-with-disclosed-residual third status (C7, low-med). Form: verdict template.
- Evidence-provenance partition: Rerun / Supplied / Asserted-but-unverified, enforced in
  brief AND report (D-F8, high). Form: review-input + report template blocks.
- Current-tree citation gate (E1, high) + its failure dual (E FAILURE: review asserted
  against absent artifact) — HEAD, artifact presence, exact anchors before section-level
  adjudication. Form: review-template gate.
- Review-of-uncompiled-artifact guard (tonight's Task P process finding): verify-state
  must reach reviewers in a form that distinguishes "gate X failed" from "nothing after
  gate X ever ran"; three review rounds examined code whose --locked gates all failed
  pre-compile. Form: bridge fix (verify report carries per-gate reached/failed) +
  failure-taxonomy entry.
Promotion rec: C4 clause onto the existing WRONG/SMELL steering rule (small edit, big
bite); D-F8 + E1 into the review-input template with S5's provenance block; the bridge
verify-report fix into cleanup-2's scope.

## Family 4 — Claim hygiene (anchor: S11, trial-validated)

- Reader-grounds-reasoner (S11): trial VALIDATED 2026-07-26 (zero fabrication, 17/17
  evaluable from evidence blocks; formalization fixes: one-quote-one-span, mechanical
  citation checker gating reports, per-file verification). exp-s3 still owed for the
  causal counterfactual. Form: orchestration pattern doc + check_citations.py +
  bridge reader-node workflow variant.
- Self-authored claim ledger → refutation task, ambiguity defaults REFUTED, refutations
  supply the narrower truth (D-F1, high). Form: dispatch template + steering clause.
- Second-pass overclaim register under read-only bounded contract (F2, high — 5 verbatim
  enactments + cross-model echoes). Form: reusable dispatch template.
- Claim quarantine after a burned claim (R4, high) — per-claim-class probation.
  Form: steering line.
- Cheapest-decisive-test-before-commit (C5, high — 4 independent sessions). Form:
  steering line.
- Audits dispatched against one's own oversell (R8) + impeaches-me-first triage (D-F3
  part). Form: adjudication template clause.
- FAILURE dual routed to taxonomy: fact-shaped hypotheses contaminating cleanroom briefs
  (A-FAILURE-1, high) — uncited "Current facts" in dispatch prompts. Candidate
  brief_lint rule: behavioral premises must be labeled FACT-with-source or
  HYPOTHESIS-verify.
Promotion rec: D-F1 + F2 as the family's two template artifacts (they operationalize S11
without waiting for exp-s3); C5 + R4 as candidate steering lines in one batch.

## Family 5 — Gate & test integrity (anchor: S10)

Mined additions:
- Gate-vacuity audit — every gate must be able to fail (R6) — the complement of S10.
- Test causal-power audit (B3, high) + fake-concurrency-oracle FAILURE dual (B) — can
  this test catch the regression it names? Detector: concurrency claims with ready
  futures/no barrier/assertions unchanged by reverting the fix.
- Pinned negatives that cannot go vacuous (D-F3, high; @ts-expect-error pattern —
  Rust analogue: tests asserting compile_fail / #[should_panic] with pinned messages) +
  one-variable witnesses (AF-1's two conditions).
- Forged-fixture repair via canonical constructors, validation stays strict (A5, high —
  2 independent enactments).
- Broader gates don't subsume narrower proofs — predicate-retention rule (A6, high).
- Entry-path × mode acceptance matrix (B4 + E3, high; cross-slice, partially
  shared-incident) — cold/warm/serve/submit/batch × flags, one negative per path.
- Green-tests vs state-coverage audit (E4, high) — passed fixtures ≠ covered states.
- Empty-result artifacts are observable success (B5, high) — "passed" and "never ran"
  must be distinguishable downstream (same nerve as the review-of-uncompiled finding).
- Lexical canonicality above permissive parsers (A7, med) — encode(parse(t)) == t at
  identity-bearing boundaries.
- Safe-failure-direction as a reviewer-verified spec section (F1, high).
- Impeaches-me-first triage (D-F3, high) — adjudicate the finding that contradicts your
  own verification before all others.
Promotion rec: this family is template/detector-heavy — bundle as a "test-integrity
review checklist" doc + 2 detector signatures (fake-oracle, unpinned-negatives); F1's
"safe failure direction" becomes a design-brief template section.

## Family 6 — Durable custody & memory (anchor: S7 + S12)

Mined additions:
- Two-tier handoff (memory index → cold-start doc) with POST-WRITE RECONCILIATION,
  verified lossless on the read side (D-F9, high).
- Ledger + handoff as concurrent-agent mutual exclusion ("owned by X — do NOT touch")
  (F7, high).
- Memory rules carry their justifying incident ("Why: PR#/round/date") (F8, med-high) +
  reuse-gated memory ("safe to reuse if / recheck if") (F9, med).
- Refutation chases the refuted claim into every durable store (R2, high).
- Round-trip shipped-bytes identity — verify the committed artifact, not the scratch
  copy; review the dimension your gate is blind to (D-F4, high).
- Anchor-rot rule — symbols over line numbers in cross-session briefs (F3, high;
  self-demonstrated by the trial's citation defects).
- S12 custody promotion (owner-initiated): commit/snapshot at every stable point;
  transcripts shadow only tool-transited bytes (proven both directions 2026-07-25/26).
Promotion rec: S12 steering line (v1 draft) + a handoff-template doc absorbing D-F9/F7/
F8/R2; D-F4 as a bridge verify-node candidate; F3 into the dispatch-brief contract.

## Family 7 — Orchestration & liveness (anchor: S6)

Mined additions:
- Steer-running-agents-in-place: UNCHANGED / REVERSED-in-caps / peer-artifact-by-
  commit-ref / write-surface partition / who-merges (D-F5, high). Form: SendMessage
  re-steer template.
- Three-signal wedge detection + verify-before-kill (C3, high) + declared patience
  window (R9) + one-teardown-discriminator-then-single-retry (A8, high) + separate
  clocks (A3, cross-listed) — together: the liveness tradecraft cluster. Form: bridge
  watchdog feature (conjunctive detector; kill gated on acceptance-criteria check;
  scoped kill) + doc.
- Pre-dispatch premise probe WITH POSITIVE CONTROL (D-F2, high; extends R1
  verify-first premise) — negative observations need a control proving the apparatus
  could produce the signal. Form: steering clause + `control:` field in evidence-capture
  task specs.
- Empty navigation evidence triggers explicit fallback (B2, high).
- Densest-representative calibration + adjacent controls stay independently
  parameterized (A4, high). Form: template clause for operational caps.
- Dischargeable objections — the objection states its own discharge conditions (R9).
- Instrument isolation (tonight, applied): child sessions of harnesses isolated from
  user-global hooks; fixed-token probes assert the token; instruments never target real
  repos (.b2a-scratch rule). Form: DONE (harness patch + guard + PROBE.md rule) +
  hard-won-facts entries.
Promotion rec: the wedge-watchdog bridge feature is this family's flagship build; D-F2's
control clause joins the dispatch-brief contract; D-F5 template lands as-is.

---

## Failure-taxonomy handoff (mined failure nominations, routed)

F1 resource-residue (owner, v1) · F2 evidence-destroying error classification (v1; new
instances: bridge verify "FAIL at fmt" masking never-compiled state; smoke.config) ·
fact-shaped brief premises (A) · structural-presence-mistaken-for-execution (B) ·
fake-concurrency oracle (B) · framework injection destroys terse probes (D; FIXED for
the exp harness, open for other spawn sites) · S11 untraced-mechanism assertion (D + C
origin citation + my recovery-exhausted self-datum) · review-of-uncompiled-artifact
(tonight) · silent --input drop sans {{input}} (tonight; bridge defect nomination) ·
prompt-contract-only read-only + real-repo cwd (tonight; rules applied).

## Promotion queue for the owner (v2)

1. Steering batch (5 small texts, SSOT carrier on sign-off): v1 §2.1 Convergence
   discipline + A2 clause; v1 §2.2 Attribution control; NEW "Evidence admissibility"
   (A1 + D-F7: "A malformed probe yields no evidence about the hypothesis — classify the
   observation admissible before updating. Before claiming an observation proves X, name
   another mechanism that would produce identical output; if you can, report the weaker
   claim. Exit status is never behavioral evidence."); C4 clause appended to WRONG/SMELL
   ("a WRONG downgrades to SMELL only via a mechanism-level proof the condition cannot
   produce a wrong output"); S12 custody line.
2. Template batch: review-input (S5 provenance + D-F8 partition + E1 current-tree gate);
   dispatch-brief additions (S4 impossibility license + D-F2 positive control + F3
   symbols-over-anchors + A-FAILURE-1 FACT/HYPOTHESIS labels); D-F1 claim-ledger + F2
   overclaim-register reusable prompts; D-F5 re-steer template.
3. Build batch: check_citations.py (S11 formalization); wedge-watchdog bridge feature;
   verify-report reached/failed disclosure (cleanup-2 scope); test-integrity checklist
   doc + 2 detectors.
4. EXP queue (unchanged + one): exp-s1 warm-reuse; exp-s2 convergence-text; exp-s3
   reader+reasoner counterfactual.
5. Cron: add success_nominations triage to the daily 07:00 run.
