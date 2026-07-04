# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Arm pass rates are not statistically distinguishable at n=15 (overlapping 95% CIs and McNemar exact p=1.00 on 1 vs 1 discordant pairs); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `exp1h-review-shape`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-haiku-4-5-20251001` (tier `weak`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `composites/review-shape` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/review-hard`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 15 | 8/15 = 0.533  (95% CI 0.301–0.752) | fresh=150 cache_creation=134455 cache_read=165015 output=107249 logical_total=299620 | 0.8218 |
| treatment | 15 | 8/15 = 0.533  (95% CI 0.301–0.752) | fresh=150 cache_creation=136900 cache_read=165015 output=116877 logical_total=302065 | 0.8748 |

## Judge-side tokens

- baseline: judge_tokens=190695 (missing=0)
- treatment: judge_tokens=183573 (missing=0)

### Deltas (treatment − baseline), reported separately

- logical tokens: 2445 (+0.8%)
- output tokens: 9628 (+9.0%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.0530 (+6.5%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |
|---|---|---|---|---|---|---|---|---|
| baseline | 10 | 2 | 3 | 0 | 0.667 | 11/14 = 0.786 | 8 | 0 |
| treatment | 10 | 1 | 4 | 0 | 0.667 | 11/14 = 0.786 | 5 | 0 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 7  both_fail: 6  only_baseline: 1  only_treatment: 1
- McNemar exact p-value (two-sided, on the discordant pairs): 1.000

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
