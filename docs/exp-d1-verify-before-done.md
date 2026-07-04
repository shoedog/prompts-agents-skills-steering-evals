# EXP-D1 — verify-before-done artifact on implement tasks (2026-07-04)

Question: does a 118-token verify-before-done artifact (run the full suite +
report totals; add tests that fail on pre-change code; state verified vs
not-verified; stop-and-report out-of-scope failures) move claude-sonnet-5
toward Fable's measured test-rigor edge on real implement tasks?

Setup: 6 bench implement tasks (IMPL-01/03/04/05/06/08 — verbatim envelopes,
mechanical oracles, existing Fable + gpt-5.5 references). Two Sonnet-5 arms
via the bench runner (baseline = verbatim envelope; treatment = artifact
prepended). Blind pairwise dual-family judging (codex gpt-5.5 xhigh +
claude-sonnet-5, isolated cwds, randomized arm order): 6 within-model pairs +
12 gap-to-Fable pairs. Zero judge errors.

## Results

**Mechanical oracles: no effect.** Both arms 5/6 evidence-pass with the
IDENTICAL failure (IMPL-04 `cargo clippy -D warnings`). Cost +17.5%
($20.80 vs $17.71; both ≈40% of Fable's $31 on the same six).

**Within-model (baseline vs D1), materially-better verdicts:**

| Task | codex | sonnet judge |
|---|---|---|
| IMPL-01 | **d1** (tests too) | **d1** (tests too) |
| IMPL-03 | baseline | parity |
| IMPL-04 | parity | parity |
| IMPL-05 | **d1** | **d1** |
| IMPL-06 | **d1** (tests too) | **d1** (tests too) |
| IMPL-08 | **d1** | **d1** |

D1 unanimously better on 4/6; zero unanimous baseline wins (one codex-only).
Sign test on the 4-0 unanimous rows: p≈0.125 — directionally consistent
across both judge families but not significant at n=6.

**Gap to Fable (tests-stronger verdicts per arm, 6 tasks):**

| Arm | fable stronger | sonnet stronger | parity |
|---|---|---|---|
| baseline (codex / sonnet judge) | 5 / 5 | 0 / 0 | 1 / 1 |
| d1 (codex / sonnet judge) | 4 / 4 | 1 / 0 | 1 / 2 |

The artifact shifts ~1 task from fable-stronger toward parity. **Fable's test
rigor edge substantially survives D1.**

**Adherence: partial (4/6)** — two treatment reports lack explicit
verified/not-verified statements. Likely cause: several envelopes carry their
own strict process rules (verification caps, "do not run workspace builds",
controller-runs-the-gates), which conflict with the prepended artifact. A
prompt-form artifact competes with the envelope; the HOOK form (EXP-2) is
enforced post-hoc and cannot be argued with — the natural next arm.

## Reading

1. D1-prompt is worth deploying as-is for implement dispatches: unanimous
   within-model quality gains on 4/6 tasks at +17.5% cost, no downside
   detected.
2. It is NOT sufficient for Fable-parity on test rigor — the gap persists
   (5/6 → 4/6). Next levers: the enforcement hook (EXP-2), a stronger
   test-design artifact (explicit negative-case checklist per new code path),
   or accepting the gap and routing verification-critical work differently.
3. IMPL-04's clippy failure in BOTH arms (where Fable passed) suggests a
   lint-gate blind spot in Sonnet that a process artifact does not fix —
   candidates: a hook that runs clippy, or an fmt/clippy line in the artifact.

Artifacts: arms in bench/out-sonnet-{baseline,d1}/ (gitignored; backed up),
pairs in bench/judging/D1W-*, D1F-*; artifact at
artifacts/elements/verify-before-done/prompt.md (commit 239ca92).
