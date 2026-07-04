# Tracker

Owner-approved backlog (2026-07-03). Items move to "Done" with the commit that closes them.

## Harness improvements (codex final-review triage)
- [ ] Judge-token parse undercount: 5/30 exp1H codex judge calls reported anomalously low "tokens used" (partial parse) — totals are a floor; harden the codex_cli token parse.
- [ ] Claude-as-judge provider (judge.py is codex-only) — REQUIRED before cross-family runs with a gpt-5.5 executor (same-family guard otherwise forces an override).
- [ ] Forward-only truth tightening for review-hard (FRESH runs only — retro edits proven asymmetric/gaming-prone by exp1H review): rh-06 split-finding granularity (rubric: credit interaction named across multiple findings), rh-10 neutral siblings, rh-14 documented robustness angles.
- [ ] Judge cost rate wiring: usd_per_mtok plumbing exists (judge tolerant-read + executor config field) but no experiment YAML sets a rate; verify config.py accepts judge.usd_per_mtok and set real rates.
- [ ] executor/judge effort enum validation in config.py (surfaces only at call time today).
- [ ] rejudge.py judge_cost_usd stays None (no rate source) — unify with rate wiring above.
- [ ] Generalize adherence directive keys — currently hard-keyed to review-shape.* labels; reads 0.000 for other treatments (cosmetic today, blocking for adherence-battery experiments).

## Scope extension (owner-added 2026-07-03)

## Experiments not running next (queued after exp2)
- [ ] Exp 3 — failure-signature list on debugging tasks (test_cheap). Blocker: needs a 20-item reproducible-failing-test task set (same manifest/truth pattern); curation ≈ Task-5 effort.
- [ ] Exp 4 — rejected-alternatives-with-boundary-conditions on design tasks (must_test; genuine evidence gap). Blocker: design task set + binary design-quality judge rubric; ≈ 2× exp 3 effort.
- [ ] Exp 1 re-run on the harder set (after ceiling is fixed).

## Done
- [x] Exp 1H — review shape vs plain on review-hard: DEAD HEAT off ceiling (8/15 both arms, identical 11/14 defect sets, McNemar p=1.0, +6.5% USD; treatment false findings 5 vs 8) — 3f2ad05. Combined with exp1-rescored: no detectable review-shape gain on Haiku; consistent noise-suppression glimmer.
- [x] Cleanup wave: McNemar trigger, judge token tracking, stratified spotcheck, empty-items PROVISIONAL, floored reorder, ci content gates, TOML guard (+fullmatch), rejudge exp_id+trace, moves.yaml polish, verdict-markdown probes — fa8fc89/c83bc64/5a079e8.
- [x] Custom agents 4th deployment form (agent.md ×15, lint, config enum, frontmatter stripping) — f094e4f/9a0f5cb.
- [x] Multi-family executor tiers: codex executor provider + same-family-judge guard + tokens-only cost; gpt-5.5 live-verified, gpt-4o-mini NOT entitled on this login, qwen untested — 9b1f033.
- [x] Harder review items: tasksets/review-hard (15 items, cross-hunk, execution-verified 29/29) — d49c319/5fd2c70.
- [x] Exp 1 — review shape vs plain review (inconclusive at ceiling; +30% USD cost finding) — d14a2b3, caveats b741014.
- [x] Exp 1 rescored under neutral-findings scope — arms identical 18/20; original baseline edge was judge-scope artifact — 94bcaf3.
- [x] Judge spot-check — 20/20 agreement (+12/12 clean supplementary), AI stand-in disclosed — 981fb1f.
- [x] Exp 2 — negative control: true-negative VALIDATED (19/20 both arms, +2.8% logical tokens, +17.3% cost, zero gain, harness_broken armed and correctly silent) — 7ebf80e.
