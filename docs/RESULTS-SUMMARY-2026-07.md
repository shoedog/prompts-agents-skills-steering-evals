# Fable-parity research — results summary & next steps (2026-07-04)

Goal (set 2026-07-03): before Fable 5 leaves the Claude Code plan on
2026-07-07, determine whether Sonnet 4.6/5, Opus 4.6/4.8, and gpt-5.5 can be
directed to Fable-level performance via skills, prompting, steering, hooks,
and agents — and capture the Fable reference data that makes the question
answerable forever.

## What was built and captured

- **18 Fable reference captures** (~$119 total): 8 implement, 2 refactor,
  1 infra, 1 research, 1 debug, 2 plan_design + 2 design memos, 1 smoke —
  every previously-empty category covered. Each pairs with its original
  gpt-5.5 session as a ready-made comparison arm. All state protected by
  git tags; all outputs backed up (local + iCloud).
- A replayable bench harness (clone-at-pre-tag, verbatim envelopes, replay
  preface, source-repo guard, mechanical evidence, --executor codex,
  --inject-dir treatments) and a blind dual-family judging pipeline
  (randomized A/B, sealed keys, isolated judge cwds, schema-forced verdicts).
- A design taskset of 7 vindicated-outcome architecture items whose oracles
  are downstream repo history (hard to game).

## Results, one line each (details in the linked docs)

1. **Implement/refactor parity** (reference-judging): gpt-5.5 is near
   outcome-parity with unaided Fable at ~1/3 the output tokens; Fable's one
   reproducible premium is TEST RIGOR (7/11 tests-stronger).
2. **D7 wrong-vs-smell** (exp-d7): halves Sonnet-5's asserted-finding false
   positives (43%→22%) at +12% cost, recall unchanged. Deployed as global
   steering in both CLIs. Method lesson: artifacts that change the output
   contract need judge-contract updates.
3. **D1 as instruction** (exp-d1): within-model gains (4/6 unanimous) but
   4/6 adherence and the Fable test-rigor gap persists. Instruction is weak.
4. **D1 as ENFORCEMENT** (exp-2, the headline): a Stop-gate hook requiring
   VERIFICATION.md inverted Fable's edge — steered Sonnet-5's tests judged
   stronger than the Fable reference 12/12 (unanimous, both judge families),
   materially better 9/12, at ~85% of Fable's cost. 100% adherence.
   **Deployed user-level for BOTH claude (settings.json Stop hook) and codex
   (hooks.json Stop hook, smoke-verified on gpt-5.5).**
5. **Design/architecture** (design-taskset + Fable design refs): gpt-5.5
   high = xhigh (27/32) ≥ Opus 4.8 (24/32) ≈ Fable (mechanism-strong but
   impact-sizing over-optimistic 10-100x, 2-of-2) ≫ **Sonnet 5 (8/32,
   collapsed, plus the only read-only violation observed)**. Effort dial
   gave gpt-5.5 nothing on these items.
6. **Debug**: Fable materially better + tests stronger (DBG-03, unanimous),
   consistent with the IMPL-12 latent-bug probe. Deepest remaining Fable
   premium alongside mechanism analysis.

## The routing playbook (post-July-7)

| Work | Route to | With |
|---|---|---|
| Implement/refactor | Sonnet 5 | verify-gate hook (live) — beats unaided-Fable reference at 85% cost |
| Code review | Sonnet 5 / any | D7 WRONG/SMELL steering (live, both CLIs) |
| Architecture / GO-NO-GO / specs | gpt-5.5 **high** (xhigh not needed); Opus 4.8 as Claude-side alternative | instrumentation gate on ANY impact forecast — no model was calibrated |
| Debug / root-cause | strongest available; pre-July-7 organic Fable; after: Opus 4.8 or gpt-5.5 + hook | verify-gate hook covers the regression-test half of the gap |
| Never | Sonnet 5 for design memos | — |

## Caveats that travel with all of this

Small n (6-15 per experiment); one owner's repos and task styles;
survivorship in the reference originals; blind-judge limits (style tells,
agentic judges); replay variance is real (DES-05: all four fresh arms —
including the original's own config — missed the vindicated direction).

## Next steps (proposed order)

1. **Trust the codex hook** (owner, 1 min): `/hooks` in interactive codex.
2. **Live-fire validation week**: use the routing playbook for real work;
   the hooks log naturally (VERIFICATION.md per session) — collect a week of
   organic adherence/outcome data instead of more bench runs.
3. **Owner spotchecks** (pending): 3 split judging rows (IMPL-03/05,
   REF-03) + exp1h spotcheck file — calibrates the judges that produced
   everything above.
4. **Debug-gap experiment** (the one remaining unclosed premium): mine
   debug tasksets (TRACKER exp 3), test whether hook+predict-then-probe
   (D2) closes Fable's debug edge on Sonnet/Opus.
5. **Variance pass**: re-run 2-3 design items x3 replicas on gpt-5.5 high to
   size run-to-run variance before trusting any single-replay verdict.
6. **Second-wave references** (optional, API-priced after July 7): IMPL-09
   flagship + remaining shortlist only if a specific question needs them.

Docs: reference-judging-2026-07.md · exp-d7 (results/…-sevaware/PROVENANCE.md)
· exp-d1-verify-before-done.md · exp-2-verify-hook.md ·
design-taskset-results.md · fable-delta-catalog.md · HANDOFF-2026-07-03.md
