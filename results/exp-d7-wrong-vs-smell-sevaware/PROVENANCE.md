# exp-d7-wrong-vs-smell-sevaware — provenance

Rescore of `results/exp-d7-wrong-vs-smell/mid` (executor calls copied verbatim
by scripts/rejudge.py; only the judge re-ran) under the severity-aware rubric
rule added 2026-07-04 (harness/rubrics/review_judge.md): SMELL-tagged findings
are hedged observations — they score neither as false findings nor as defect
credit; WRONG-tagged and untagged findings score under the normal rules.

Why the rescore is legitimate and not post-hoc rescue:
- The rule was motivated by an INDEPENDENT audit (opus subagent) of every
  scored-false finding in BOTH arms against the actual task code, run before
  the rule was written: GENUINELY_FALSE = 0 in both arms; the treatment's
  excess FPs were 13 STYLE_AS_DEFECT items explicitly SMELL-tagged by the
  artifact's own contract. The original rubric scored the artifact's
  deliberately-downgraded observations as if they were asserted defects.
- The rule is symmetric (baseline has no tags; its scores are IDENTICAL in
  both scorings: 8/15 pass, 9 FP) and forward-binding for future runs.
- No truth files were edited. Truth-scope gaps found by the audit (both arms
  surfacing real unlisted defects, e.g. rh-14's genuine thread-ownership hole
  in a nominally clean item) are recorded in TRACKER.md as FORWARD-ONLY
  fixes, not applied here.

Both scorings are reported:
- Original contract (results/exp-d7-wrong-vs-smell/mid): baseline 8/15 pass /
  9 FP; treatment 2/15 / 22 FP. Recall 12/14 vs 13/14.
- Severity-aware (this dir): baseline 8/15 / 9 FP; treatment 10/15 / 4 FP.
  Recall unchanged (no seeded defect was SMELL-only-matched).

Honest bottom line: pass-rate delta is NOT significant (McNemar p=0.625 on
1-vs-3 discordant pairs, n=15) — treat it as noise. The real, replicated
effect is false-positive suppression: scored FPs 9→4; FP-rate among ASSERTED
findings 9/21 (43%) baseline vs 4/18 (22%) treatment, recall equal-or-better,
adherence 14/15, executor cost +12.1%. Echoes exp1's finding that these
artifacts buy precision, not recall — here more cheaply and with an explicit
severity split the owner can filter on.

Executor: claude-sonnet-5 (tier mid), taskset review-hard, judge codex
gpt-5.5 medium. First run of the source experiment was integrity-failed
(2 transient claude-CLI rc-1s) and fully re-run after a provider retry fix
(commit 182a4c6); the source dir holds the clean second run.
