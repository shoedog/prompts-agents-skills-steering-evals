# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Baseline defect recall is at ceiling (1.000): the treatment structurally cannot improve recall on this task set; recall deltas are uninterpretable and pass-rate deltas partly preordained. A harder task set is required to detect a recall improvement.
- Treatment defect recall is at ceiling (1.000): the baseline structurally cannot improve recall on this task set; recall deltas are uninterpretable and pass-rate deltas partly preordained. A harder task set is required to detect a recall improvement.
- Arm pass rates are not statistically distinguishable at n=5 (overlapping 95% CIs); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `smoke`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-haiku-4-5-20251001` (tier `weak`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `composites/review-shape` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/smoke`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 5 | 5/5 = 1.000  (95% CI 0.566–1.000) | fresh=50 cache_creation=41084 cache_read=55005 output=6590 logical_total=96139 | 0.1207 |
| treatment | 5 | 5/5 = 1.000  (95% CI 0.566–1.000) | fresh=50 cache_creation=41899 cache_read=55005 output=11184 logical_total=96954 | 0.1453 |

### Deltas (treatment − baseline), reported separately

- logical tokens: 815 (+0.8%)
- output tokens: 4594 (+69.7%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.0246 (+20.4%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings |
|---|---|---|---|---|---|---|---|
| baseline | 3 | 0 | 2 | 0 | 0.600 | 3/3 = 1.000 | 0 |
| treatment | 3 | 0 | 2 | 0 | 0.600 | 3/3 = 1.000 | 0 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 5  both_fail: 0  only_baseline: 0  only_treatment: 0

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
