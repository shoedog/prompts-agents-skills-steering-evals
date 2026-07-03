# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Treatment defect recall is at ceiling (1.000): the baseline structurally cannot improve recall on this task set; recall deltas are uninterpretable and pass-rate deltas partly preordained. A harder task set is required to detect a recall improvement.
- Arm pass rates are not statistically distinguishable at n=20 (overlapping 95% CIs); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `exp2-negative-control`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-haiku-4-5-20251001` (tier `weak`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `negative_control` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/review-seeded`  negative_control: `True`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 20 | 19/20 = 0.950  (95% CI 0.764–0.991) | fresh=200 cache_creation=135519 cache_read=254066 output=52703 logical_total=389785 | 0.5602 |
| treatment | 20 | 19/20 = 0.950  (95% CI 0.764–0.991) | fresh=200 cache_creation=180585 cache_read=220020 output=54779 logical_total=400805 | 0.6573 |

### Deltas (treatment − baseline), reported separately

- logical tokens: 11020 (+2.8%)
- output tokens: 2076 (+3.9%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.0971 (+17.3%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |
|---|---|---|---|---|---|---|---|---|
| baseline | 14 | 0 | 6 | 0 | 0.700 | 14/15 = 0.933 | 0 | 0 |
| treatment | 14 | 0 | 6 | 0 | 0.700 | 15/15 = 1.000 | 1 | 0 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 18  both_fail: 0  only_baseline: 1  only_treatment: 1

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
