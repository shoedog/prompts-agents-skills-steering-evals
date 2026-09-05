# Structured evaluation report

- experiment: st-smoke
- kind: structured_task
- run id: 20260904T184011Z-7658236e
- config sha256: `7658236e848e5a232fcc828bb16f6ce96e0ca5ec8cc521b1a05ac388e286dd86`
- taskset / split: taskset / dev
- item count: 1
- bootstrap: method=percentile, resamples: 20, seed: 20260904, alpha=0.05
- version v1: provider=stub, model=fake-model, task_version=2026-09-04.1

## Paired deltas


## Confusion matrices

### v1

| Expected \ Predicted | correct | swallowed_fatal | retried_non_retryable | no_retry_on_transient | partial_as_success | resource_leak_on_error | missing_timeout | unbounded_retry | unclear | __invalid__ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| correct | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| swallowed_fatal | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| retried_non_retryable | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_retry_on_transient | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| partial_as_success | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| resource_leak_on_error | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| missing_timeout | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| unbounded_retry | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| unclear | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Worst 10 by loss

| Hard failure | Loss | Version | Item | Sample | Expected | Predicted | Confidence | First failing assert | Replay key |
|---|---:|---|---|---:|---|---|---:|---|---|
| false | 0.200000 | v1 | eh-py-0001 | 0 | correct | correct | 0.800000 | missing rationale terms: ['TimeoutError', 'propagated']; citations outside rendered slice: [1]; missing evidence lines: [11] | `v1/eh-py-0001/s0` |

## Cost and provenance

| Version | Calls | Total USD | Cache hit rate | p50 ms | p95 ms | Stage-error calls |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 1 | 0.001000 | 0.000000 | 0.000000 | 0.000000 | 0 |

- v1 stage-error exclusions: []
- v1 first-tier validity: 1.000000 (1/1)
- v1 schema_valid_for_eval: 1.000000 (1/1)
- v1 repaired: 0.000000 (0/1)
- v1 Brier: 0.040000; maximum-penalty rows: 0/1
- v1 κ model-vs-human: 1.000000; κ human-vs-human: n/a (n=0; unavailable: taskset labels retain agreement flags, not secondary classes)

sentinel and `__invalid__` rows receive maximum Brier penalty and are never excluded.

> PROVISIONAL — pending human spot-check.
