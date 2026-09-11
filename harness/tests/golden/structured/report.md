# Structured evaluation report

- experiment: st-fixture
- kind: structured_task
- run id: 20260905T120000Z-fixture
- config sha256: `437eb4c6b424bb44db19704aaefc123c424bdbede83b29d8a8bc4fe59f5717f1`
- taskset / split: fixture-taskset / dev
- item count: 2
- bootstrap: method=percentile, resamples: 40, seed: 20260904, alpha=0.05
- version baseline: provider=fixture, model=fixture-model, task_version=baseline
- version candidate: provider=fixture, model=fixture-model, task_version=candidate
- version candidate-alt: provider=fixture, model=fixture-model, task_version=candidate-alt
- promotion verdict for candidate: PROMOTABLE: macro_f1_ci.lo>=0, schema_validity>=0.99, and every recall_ci.hi>=0
- promotion verdict for candidate-alt: PROMOTABLE: macro_f1_ci.lo>=0, schema_validity>=0.99, and every recall_ci.hi>=0

## Paired deltas

### baseline → candidate

Paired population identity: baseline→candidate; n items: 2; population sha256: `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f`.

| Metric | Baseline | Candidate | Delta | CI low | CI high | McNemar p | n items | Seed | Resamples | Population sha256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| macro_f1 | 0.333333 | 1.000000 | 0.666667 | 0.000000 | 0.666667 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| f1:correct | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| f1:swallowed_fatal | 0.666667 | 1.000000 | 0.333333 | 0.000000 | 0.333333 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| schema_validity | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| brier | 0.325000 | 0.012500 | -0.312500 | -0.637500 | 0.012500 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| kappa | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| cost_per_item | 0.015000 | 0.020000 | 0.005000 | 0.005000 | 0.005000 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| p95_latency_ms (population=version, n=2) | 195.000000 | 177.000000 | -18.000000 | -20.000000 | 20.000000 | n/a | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| recall:correct (gate) | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |
| recall:swallowed_fatal (gate) | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 2 | 20260904 | 40 | `44b90d10dac01f41ff72f8d71090eae76dc4fb0a452255d594d3adaf42b5a46f` |

Caveat: these percentile CIs include 0, so the paired evidence does not separate the versions for: macro_f1, f1:correct, f1:swallowed_fatal, schema_validity, brier, kappa, p95_latency_ms, recall:correct (gate), recall:swallowed_fatal (gate).
### baseline → candidate-alt

Paired population identity: baseline→candidate-alt; n items: 2; population sha256: `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c`.

| Metric | Baseline | Candidate | Delta | CI low | CI high | McNemar p | n items | Seed | Resamples | Population sha256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| macro_f1 | 0.333333 | 1.000000 | 0.666667 | 0.000000 | 0.666667 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| f1:correct | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| f1:swallowed_fatal | 0.666667 | 1.000000 | 0.333333 | 0.000000 | 0.333333 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| schema_validity | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| brier | 0.325000 | 0.012500 | -0.312500 | -0.637500 | 0.012500 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| kappa | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| cost_per_item | 0.015000 | 0.020000 | 0.005000 | 0.005000 | 0.005000 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| p95_latency_ms (population=version, n=2) | 195.000000 | 177.000000 | -18.000000 | -20.000000 | 20.000000 | n/a | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| recall:correct (gate) | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |
| recall:swallowed_fatal (gate) | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 2 | 20260904 | 40 | `249c556a9c01c9008bde76c3fc5ac8446be4145d7301dcb8876b57f9c419574c` |

Caveat: these percentile CIs include 0, so the paired evidence does not separate the versions for: macro_f1, f1:correct, f1:swallowed_fatal, schema_validity, brier, kappa, p95_latency_ms, recall:correct (gate), recall:swallowed_fatal (gate).

## Confusion matrices

### baseline

| Expected \ Predicted | correct | swallowed_fatal | __invalid__ |
|---|---:|---:|---:|
| correct | 0 | 1 | 0 |
| swallowed_fatal | 0 | 1 | 0 |

### candidate

| Expected \ Predicted | correct | swallowed_fatal | __invalid__ |
|---|---:|---:|---:|
| correct | 1 | 0 | 0 |
| swallowed_fatal | 0 | 1 | 0 |

### candidate-alt

| Expected \ Predicted | correct | swallowed_fatal | __invalid__ |
|---|---:|---:|---:|
| correct | 1 | 0 | 0 |
| swallowed_fatal | 0 | 1 | 0 |

## Contamination risk bands

| Version | Risk band | Declared items | Scored items | Scored samples | Macro F1 | Schema-valid rate | Brier | Stage-error calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | low | 2 | 2 | 2 | 0.333333 | 1.000000 | 0.325000 | 0 |
| baseline | medium | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| baseline | high | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| candidate | low | 2 | 2 | 2 | 1.000000 | 1.000000 | 0.012500 | 0 |
| candidate | medium | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| candidate | high | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| candidate-alt | low | 2 | 2 | 2 | 1.000000 | 1.000000 | 0.012500 | 0 |
| candidate-alt | medium | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
| candidate-alt | high | 0 | 0 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |
## Worst 10 by loss

| Hard failure | Loss | Version | Item | Sample | Expected | Predicted | Confidence | First failing assert | Replay key |
|---|---:|---|---|---:|---|---|---:|---|---|
| false | 0.800000 | baseline | eh-py-0001 | 0 | correct | swallowed_fatal | 0.800000 | expected 'correct', got 'swallowed_fatal' | `baseline/eh-py-0001/s0` |
| false | 0.150000 | candidate | eh-py-0002 | 0 | swallowed_fatal | swallowed_fatal | 0.850000 | none | `candidate/eh-py-0002/s0` |
| false | 0.150000 | candidate-alt | eh-py-0002 | 0 | swallowed_fatal | swallowed_fatal | 0.850000 | none | `candidate-alt/eh-py-0002/s0` |
| false | 0.100000 | baseline | eh-py-0002 | 0 | swallowed_fatal | swallowed_fatal | 0.900000 | none | `baseline/eh-py-0002/s0` |
| false | 0.050000 | candidate | eh-py-0001 | 0 | correct | correct | 0.950000 | none | `candidate/eh-py-0001/s0` |
| false | 0.050000 | candidate-alt | eh-py-0001 | 0 | correct | correct | 0.950000 | none | `candidate-alt/eh-py-0001/s0` |

## Cost and provenance

run p95 ms (population=run, n=6): 195.000000

| Version | Calls | Total USD | Cache hit rate | p50 ms | p95 ms (population=version) | Stage-error calls |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 2 | 0.030000 | 0.500000 | 150.000000 | 195.000000 (n=2) | 0 |
| candidate | 2 | 0.040000 | 0.500000 | 150.000000 | 177.000000 (n=2) | 0 |
| candidate-alt | 2 | 0.040000 | 0.500000 | 150.000000 | 177.000000 (n=2) | 0 |

- baseline stage-error exclusions: []
- baseline first-tier validity: 1.000000 (2/2)
- baseline schema_valid_for_eval: 1.000000 (2/2)
- baseline repaired: 0.000000 (0/2)
- baseline Brier: 0.325000; maximum-penalty rows: 0/2
- baseline κ model-vs-human: 0.000000; κ human-vs-human: n/a (n=0; unavailable: taskset labels retain agreement flags, not secondary classes)
- candidate stage-error exclusions: []
- candidate first-tier validity: 1.000000 (2/2)
- candidate schema_valid_for_eval: 1.000000 (2/2)
- candidate repaired: 0.000000 (0/2)
- candidate Brier: 0.012500; maximum-penalty rows: 0/2
- candidate κ model-vs-human: 1.000000; κ human-vs-human: n/a (n=0; unavailable: taskset labels retain agreement flags, not secondary classes)
- candidate-alt stage-error exclusions: []
- candidate-alt first-tier validity: 1.000000 (2/2)
- candidate-alt schema_valid_for_eval: 1.000000 (2/2)
- candidate-alt repaired: 0.000000 (0/2)
- candidate-alt Brier: 0.012500; maximum-penalty rows: 0/2
- candidate-alt κ model-vs-human: 1.000000; κ human-vs-human: n/a (n=0; unavailable: taskset labels retain agreement flags, not secondary classes)

sentinel and `__invalid__` rows receive maximum Brier penalty and are never excluded.

> PROVISIONAL — pending human spot-check.
