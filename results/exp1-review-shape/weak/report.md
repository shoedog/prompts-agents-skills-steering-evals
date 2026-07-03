# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Configuration

- id: `exp1-review-shape`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-haiku-4-5-20251001` (tier `weak`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `composites/review-shape` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/review-seeded`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 20 | 17/20 = 0.850  (95% CI 0.640–0.948) | fresh=200 cache_creation=165085 cache_read=220020 output=51929 logical_total=385305 | 0.6120 |
| treatment | 20 | 16/20 = 0.800  (95% CI 0.584–0.919) | fresh=200 cache_creation=168345 cache_read=220020 output=87670 logical_total=388565 | 0.7972 |

### Deltas (treatment − baseline), reported separately

- logical tokens: 3260 (+0.8%)
- cost USD: +0.1852 (+30.3%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings |
|---|---|---|---|---|---|---|---|
| baseline | 14 | 1 | 5 | 0 | 0.700 | 15/15 = 1.000 | 3 |
| treatment | 14 | 1 | 5 | 0 | 0.700 | 14/15 = 0.933 | 4 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 15  both_fail: 2  only_baseline: 2  only_treatment: 1

## Treatment-arm adherence (per directive)

- `review-shape.checklist`: 1.000
- `review-shape.disconfirm`: 1.000
- `review-shape.verify`: 1.000
- `review-shape.all_three`: 1.000

## Flags

- cost_adjusted_verdict: False
- harness_broken: False
- composite_floored: False
- judge_errors: 0
- parse failures (unparseable findings block): 0

---
_Not aggregated across tiers._
