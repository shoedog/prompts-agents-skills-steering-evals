# EXP-2 — verify-before-done as a Stop-gate HOOK (2026-07-04)

Treatment: no prompt change at all. A `.claude/` Stop hook injected into the
workspace blocks session end until `VERIFICATION.md` exists at the repo root
with required shape (full-suite totals, `## Verified`, `## Not verified`);
the block reason carries the D1 discipline (tests that fail on pre-change
code, one negative/edge case per new path, stop-and-report out-of-scope
failures). Loop-guarded at 2 blocks; clean-tree no-op path (added after the
smoke test, where Sonnet twice REFUSED to fabricate verification for a no-op
task — principled, and the right gate design lesson).

Arms on the same 6 implement tasks (mechanical oracles all effectively green
across every arm modulo the documented pre-existing IMPL-04 graph.rs lint):

| arm | cost | adherence |
|---|---|---|
| sonnet-5 baseline | $17.71 | — |
| sonnet-5 + D1 prompt | $20.80 (+17.5%) | 4/6 verify statements |
| sonnet-5 + verify HOOK | $26.36 (+49%) | **6/6 VERIFICATION.md, one block each** |
| gpt-5.5 high (replay) | plan tokens only | — |
| Fable 5 (reference) | ~$31 | — |

## Results (blind pairwise, dual judges, randomized arms, 0 errors)

**HOOK vs BASELINE (within-model):** tests-stronger → hook **12/12**
judge-verdicts; materially-better → hook 9/12 (codex 4–2, sonnet judge 5–1).

**HOOK vs FABLE — the headline:** tests-stronger → **hook 12/12, unanimous
across both judge families** (sign test on 6 unanimous tasks: p≈0.03).
Materially-better → hook 9/12 (codex 4–1–1, sonnet judge 5–1). The Stop-gate
did not merely close Fable's test-rigor gap — **it inverted it.**

**GPT-5.5 replay vs FABLE (control/executor matrix):** dead even on
materially-better (codex 3–3; sonnet judge 3–2–1) with Fable tests-stronger
4/6 — replicating the organic-session finding under identical replay
conditions. The prompt-form D1 arm (earlier) shifted Fable's edge only 5/6 →
4/6. Enforcement, not instruction, is what moved it.

## Reading

1. **The parity program's core question now has a demonstrated YES on
   implement tasks (n=6): Sonnet-5 + a 30-line enforcement hook produced
   work blind-judged at-or-above the Fable reference, at ~85% of Fable's
   dollar cost — including inverting Fable's single strongest dimension.**
2. Mechanism: the artifact ladder was instruction (4/6 adherence, weak
   effect) → enforcement (6/6 adherence, inverting effect). Hooks are
   cheap, model-agnostic, and cannot be argued with; the D1 text only
   works when something makes it binding.
3. Costs rise with enforcement (+49% over baseline) but remain below Fable.
4. Caveats: n=6, one task family (Rust implement), same-6-task reuse across
   arms (no cross-arm contamination — each arm was an independent fresh
   clone — but task-selection effects are shared), judges see only diffs,
   and "Fable reference" is unaided Fable — Fable+hook was not run. The
   result claims steered-Sonnet ≥ unaided-Fable, not Sonnet ≥ Fable.

Artifacts: bench/hooks-d1/ (treatment), bench/out-sonnet-d1hook/,
bench/out-gpt55/ (arm outputs, backed up), bench/judging/HKW-*, HKF-*,
G5F-* (briefs/keys/verdicts). Runner support: --inject-dir / --executor
codex (commit 9bd645c).
