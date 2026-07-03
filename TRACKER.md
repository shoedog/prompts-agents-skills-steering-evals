# Tracker

Owner-approved backlog (2026-07-03). Items move to "Done" with the commit that closes them.

## Harness improvements (codex final-review triage)
- [ ] Judge-side dollar tracking — codex judge tokens/USD not folded into cost; $10 budget gate enforces executor cost only.
- [ ] McNemar-based noise trigger — replace/augment the conservative CI-overlap caveat with a McNemar test on the paired flips table.
- [ ] moves.yaml metadata polish — fold row-13 imperative-twin contrast into context-narrative-overview notes; sensitivity-notes evidence_tier general→human (conservative fill); revisit differential-diagnosis test_cheap hedge.
- [ ] codex_cli TOML escaping guard for effort values (fixed vocab today).
- [ ] report.py: when composite_floored fires, physically lead with defect-recall/confusion (currently banner-only).
- [ ] check_spotcheck.py: empty-but-present items list should read PROVISIONAL, not FAIL.
- [ ] ci/test_smoke.py: content-level (not existence-only) checks on report.md/spotcheck.yaml.
- [ ] judge_assert: probe exotic verdict markdown (tables, heading-verdicts) beyond current variants.

## Experiments not running next (queued after exp2)
- [ ] Exp 3 — failure-signature list on debugging tasks (test_cheap). Blocker: needs a 20-item reproducible-failing-test task set (same manifest/truth pattern); curation ≈ Task-5 effort.
- [ ] Exp 4 — rejected-alternatives-with-boundary-conditions on design tasks (must_test; genuine evidence gap). Blocker: design task set + binary design-quality judge rubric; ≈ 2× exp 3 effort.
- [ ] Harder review items — 10–15 items with 60–120-line multi-hunk diffs to pull baseline recall off ceiling; prerequisite for a meaningful exp 1 re-run.
- [ ] Exp 1 re-run on the harder set (after ceiling is fixed).

## Done
- [x] Exp 1 — review shape vs plain review (inconclusive at ceiling; +30% USD cost finding) — d14a2b3, caveats b741014.
