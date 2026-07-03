# human-moves-eval

Evaluation harness for measuring whether structural "moves" (prompts,
skills, steering artifacts) change model behavior on code-review tasks,
relative to a strong-simple baseline and a negative control.

## Layout

- `moves.yaml` — catalog of moves under test
- `scripts/` — validation/lint scripts
- `artifacts/` — baseline, elements, runtime, negative-control content
- `tasksets/` — smoke and review-seeded task sets
- `harness/` — runner, providers, asserts, rubrics, tests
- `experiments/` — experiment configs
- `ci/` — CI test entrypoints
- `results/` — per-experiment run outputs

## Setup

```
uv venv --python 3.12 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install -e .
npm install
```

## How to run

```
.venv/bin/python -m harness.run experiments/smoke.yaml
```
