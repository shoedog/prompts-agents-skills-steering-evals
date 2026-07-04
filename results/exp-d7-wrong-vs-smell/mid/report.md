# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Arm pass rates are not statistically distinguishable at n=15 (overlapping 95% CIs, though McNemar exact p=0.03 on 6 vs 0 discordant pairs alone would not flag noise); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `exp-d7-wrong-vs-smell`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-sonnet-5` (tier `mid`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `elements/wrong-vs-smell` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/review-hard`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 15 | 8/15 = 0.533  (95% CI 0.301–0.752) | fresh=30 cache_creation=202949 cache_read=222885 output=102207 logical_total=425864 | 2.8178 |
| treatment | 15 | 2/15 = 0.133  (95% CI 0.037–0.379) | fresh=30 cache_creation=178206 cache_read=250444 output=134271 logical_total=428680 | 3.1585 |

## Judge-side tokens

- baseline: judge_tokens=130088 (missing=0)
- treatment: judge_tokens=54735 (missing=0)

### Deltas (treatment − baseline), reported separately

- logical tokens: 2816 (+0.7%)
- output tokens: 32064 (+31.4%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.3408 (+12.1%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |
|---|---|---|---|---|---|---|---|---|
| baseline | 10 | 1 | 4 | 0 | 0.667 | 12/14 = 0.857 | 9 | 0 |
| treatment | 10 | 2 | 3 | 0 | 0.667 | 13/14 = 0.929 | 22 | 0 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 2  both_fail: 7  only_baseline: 6  only_treatment: 0
- McNemar exact p-value (two-sided, on the discordant pairs): 0.031

## Treatment-arm adherence (per directive)

- `review-shape.checklist`: 0.000
- `review-shape.disconfirm`: 0.000
- `review-shape.verify`: 0.000
- `review-shape.all_three`: 0.000

## Flags

- cost_adjusted_verdict: False
- harness_broken: False
- composite_floored: False
- judge_errors: 0
- parse failures (unparseable findings block): 0

---
_Not aggregated across tiers._
