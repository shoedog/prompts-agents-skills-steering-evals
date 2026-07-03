# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

> NOTE — Rescore of exp1-review-shape executor outputs under neutral-findings scoring; executor calls shared verbatim with results/exp1-review-shape/.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Baseline defect recall is at ceiling (1.000): the treatment structurally cannot improve recall on this task set; recall deltas are uninterpretable and pass-rate deltas partly preordained. A harder task set is required to detect a recall improvement.
- Arm pass rates are not statistically distinguishable at n=20 (overlapping 95% CIs); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `exp1-review-shape-rescored`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-haiku-4-5-20251001` (tier `weak`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md']
- varied element: `composites/review-shape` (form `prompt`) -> `prompt.md`
- taskset: `tasksets/review-seeded`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 20 | 18/20 = 0.900  (95% CI 0.699–0.972) | fresh=200 cache_creation=165085 cache_read=220020 output=51929 logical_total=385305 | 0.6120 |
| treatment | 20 | 18/20 = 0.900  (95% CI 0.699–0.972) | fresh=200 cache_creation=168345 cache_read=220020 output=87670 logical_total=388565 | 0.7972 |

### Deltas (treatment − baseline), reported separately

- logical tokens: 3260 (+0.8%)
- output tokens: 35741 (+68.8%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.1852 (+30.3%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |
|---|---|---|---|---|---|---|---|---|
| baseline | 14 | 1 | 5 | 0 | 0.700 | 15/15 = 1.000 | 2 | 1 |
| treatment | 14 | 1 | 5 | 0 | 0.700 | 14/15 = 0.933 | 1 | 3 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 17  both_fail: 1  only_baseline: 1  only_treatment: 1

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
