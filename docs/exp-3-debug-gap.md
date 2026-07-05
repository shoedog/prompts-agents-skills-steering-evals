# EXP-3 — the debug gap (2026-07-05)

Question: does the validated steering stack (verify-gate hook, now live for
all arms + D2 predict-then-probe prompt artifact) close Fable's debug edge —
the one premium that survived EXP-2 — on Sonnet 5, Opus 4.8, and gpt-5.5?

Setup: 4 debug tasks with mechanical oracles (DBG-01 CI-failure investigate,
DBG-02 blocker-fix, DBG-03 fix-your-own-bug, INFRA-01 CI awk fix) × 6 arms
(3 models × {live-env baseline, +D2}) + 2 fresh Fable references. IMPORTANT
FRAMING: every arm and both new references ran in the CURRENT live
environment (verify hook active, D7 steering present) — see
bench/out/DBG-01/CAVEAT-env-drift.md. Efforts: sonnet high (owner default),
opus CLI default, gpt-5.5 high, Fable xhigh. Dual blind judges, 68 calls, 0
errors.

## Headline: Fable's debug edge survives the full steering stack

Vs-Fable pairs (DBG-02/03 + INFRA-01, tests-stronger, 6 verdicts/arm):
**every single arm lost 4 and tied 2 — no arm beat Fable on any debug pair**
(identical pattern across all six arms; the 2 parities are the trivial
INFRA-01). Overall materially-better: Fable 3-4/6 per arm, arms ≤1/6.
Unlike implement work — where the hook INVERTED Fable's edge — debugging is
a capability gap, not a process gap: on DBG-02 Fable ran WITH the same hook
as the arms and still won, at comparable cost ($18.93 vs $12.77-15.55).

## D2 predict-then-probe: real value, concentrated on hard debugging

Within-model (base vs +D2), 18 verdict-pairs:
- **DBG-02 (hardest): D2 better 12/12** — every model, both judges, verdict
  AND tests. The hypothesis→probe→log discipline demonstrably improves deep
  multi-cause debugging.
- DBG-03: noise (splits both directions). INFRA-01: parity 12/12 (too easy).
- Cost: roughly neutral (sonnet +$3.29, opus −$1.33).

Deploy verdict: D2 is worth adding to debug dispatches — its effect size on
hard problems is the largest within-model result after the hook itself.

## DBG-01 (the terse "Investigate" prompt): diagnosis parity, action varies

All 7 graded reports (6 arms + the Fable reference itself) matched the root
cause. Fable and both gpt-5.5 arms stopped at diagnosis; Opus fixed in both
arms; Sonnet flipped (base fixed — though with a fix shape the judges scored
as NOT matching the landed union-fix — d2 diagnosed). **Opus-d2 was the only
perfect 8/8 score** (root cause + fmt + fixed + fix-shape match, both
judges). The fix/diagnose split tracks model family and run variance, not
D2 (gpt-5.5 diagnosed in both arms); the earlier D2-anchoring worry is down
to one unreplicated flip.

## Routing conclusion (updates the playbook)

- Debug is Fable's most durable premium: pre-July-7, route hard debugging to
  Fable; after, expect a real quality deficit on deep multi-cause bugs.
- Best available substitute config: **Opus 4.8 + D2 + hook** (perfect
  DBG-01, 4/4 evidence both arms, $22.74/4 tasks) with **gpt-5.5 + D2**
  close behind (its DBG-02 was the only arm to take a verdict off Fable).
- Sonnet 5 is fine for routine debug (4/4 baseline evidence) but weakest on
  fix-shape quality.
- Add D2 to debug dispatch templates; keep the hook (it fired usefully in
  every dirty-tree session including Fable's own reference).

Caveats: n=4 tasks (one trivial), single replay per cell, live-env framing
differs from pre-deployment experiments, DBG-01's ambiguous prompt makes its
evidence gate interpretation-sensitive (treated as diagnosis-only in
judging).

Artifacts: bench/out-dbg-*/ (6 arms), bench/out/DBG-0{1,2}/ (references),
bench/judging/DBG1CM-*, DBGW-*, DBGF-*; D2 artifact
artifacts/elements/predict-then-probe/prompt.md.
