# Experiment report — PROVISIONAL

> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, then run `scripts/check_spotcheck.py`.

Estimand: the effect of the varied review-procedure element on review quality, CONDITIONAL on a shared binary output format. Workspace section labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment.

## Caveats

- Treatment defect recall is at ceiling (1.000): the baseline structurally cannot improve recall on this task set; recall deltas are uninterpretable and pass-rate deltas partly preordained. A harder task set is required to detect a recall improvement.
- Arm pass rates are not statistically distinguishable at n=7 (overlapping 95% CIs and McNemar exact p=1.00 on 1 vs 2 discordant pairs); treat the pass-rate delta as noise, not effect.

## Configuration

- id: `exp-w3a-cite-or-label`  task_family: `review`  eval_shape: `ablation`
- executor: `claude-sonnet-5` (tier `mid`)
- baseline_prompt: ['artifacts/baseline/review.md', 'artifacts/baseline/output_format.md', 'artifacts/elements/wrong-vs-smell/steering.md']
- varied element: `elements/cite-or-label` (form `steering`) -> `steering.md`
- taskset: `tasksets/mechanism-claims-v0`  negative_control: `False`
- judge: `codex/gpt-5.5` effort `medium`

## Per-arm results

| arm | n | pass | tokens | cost USD |
|---|---|---|---|---|
| baseline | 7 | 5/7 = 0.714  (95% CI 0.359–0.918) | fresh=14 cache_creation=54982 cache_read=23023 output=34447 logical_total=78019 | 0.8651 |
| treatment | 7 | 6/7 = 0.857  (95% CI 0.487–0.974) | fresh=14 cache_creation=55717 cache_read=23023 output=46678 logical_total=78754 | 1.0535 |

## Judge-side tokens

- baseline: judge_tokens=13751 (missing=0)
- treatment: judge_tokens=25539 (missing=0)

### Deltas (treatment − baseline), reported separately

- logical tokens: 735 (+0.9%)
- output tokens: 12231 (+35.5%)
- fresh input tokens: 0 (+0.0%)
- cost USD: +0.1884 (+21.8%)

## Confusion matrix (verdict) + base rate

| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |
|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 0 | 2 | 0 | 0.714 | 4/5 = 0.800 | 2 | 1 |
| treatment | 5 | 0 | 2 | 0 | 0.714 | 5/5 = 1.000 | 1 | 2 |

- judge_id_mismatches (judge-returned defect ids not in ground truth; excluded from recall): baseline=0 treatment=0

## Paired flip table (joined on task_id)

- both_pass: 4  both_fail: 0  only_baseline: 1  only_treatment: 2
- McNemar exact p-value (two-sided, on the discordant pairs): 1.000

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
