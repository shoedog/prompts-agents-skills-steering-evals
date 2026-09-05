# human-moves-eval

This repository contains the legacy two-arm review-ablation harness and a sibling structured evaluation path for schema-constrained tasks, analyzer findings, and pinned pipelines. The legacy generation and reduction bytes are guarded by `test_generation_leg_matches_golden`, `test_reduction_leg_matches_golden`, and `test_structured_replay_matches_goldens_byte_identically`.

## Setup and command checks

Use Python 3.12. The checked setup is:

```sh
uv venv --python 3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e .
npm install
```

These help commands are safe command checks and do not call a model (`test_documented_help_commands_exit_zero_without_model_calls`):

```sh
python -m harness.run --help
python -m harness.structured.run --help
python -m harness.structured.replay --help
```

The legacy review command is `.venv/bin/python -m harness.run experiments/smoke.yaml`. It can make paid provider and judge calls. Three CI jobs may spend: `live-smoke` runs `RUN_LIVE=1 .venv/bin/python -m pytest -q ci -k test_smoke_run` only on nightly schedules or manual dispatch and is currently estimated at about $2; `dev-set` runs the config named by `STRUCTURED_DEV_CONFIG` on structured-path changes; and `test-set` runs the config named by `STRUCTURED_TEST_CONFIG` on `v*` tags with `--allow-test`. Each structured config limits selected work with `token_budget.max_items`. The runner checks accumulated reported cost against `token_budget.max_cost_usd` after each provider invocation and raises after an overrun; it cannot prevent the first paid call, including when the configured maximum is zero. The legacy-smoke-specific boundary remains explicit: `test_smoke_run` stays marked `live` and skipped unless `RUN_LIVE=1`. Task 11 did not run it. The zero-cost structured stub is `.venv/bin/python -m harness.structured.run experiments/structured/st-smoke.yaml`; `test_structured_smoke_writes_exact_tree` checks its result shape with the same stub seam.

## Tasksets, pipelines, and analyzer modes

A taskset v2 input names a path and SHA-256. A file hash covers its exact bytes; a directory hash covers sorted NFC relative paths, file type or executable bit, byte length, bytes, and literal symlink target, while excluding `.git/` and declared ignore globs. Hash mismatch is rejected before JSON parsing or execution (`test_load_taskset_rejects_a_mutated_pinned_input`, `test_hash_check_precedes_json_parsing`, `test_directory_digest_matches_conformance_fixture`).

`harness.structured.pipeline.run_pipeline_item` implements `from_item`, `never`, and `if_absent`. A pinned prefix is hash-checked and schema-checked before a downstream stage runs; every stage output is written through `ResultsWriter`, and replay rows remain in stage order (`test_pinned_prefix_executes_only_classify`, `test_mutated_pinned_artifact_fails_before_downstream_execution`, `test_if_absent_executes_only_without_pin`). Runtime-harness `never` remains unavailable with the exact error `runtime harness stage not implemented`; `if_absent` may execute only when a harness executor was explicitly registered (`test_runtime_harness_never_is_the_exact_unimplemented_error`, `test_if_absent_without_registered_harness_records_stage_error`). `experiments/structured/pl-smoke.yaml` and `tasksets/structured/eh_pipeline/` are synthetic pin-selection fixtures, not a measured model comparison.

Analyzer `resolution` and `min_confidence` are separate knobs. Resolution accepts `nominal`, `scoped`, or `precise`; the emit floor accepts `exact` or `nameonly`. The runner never sends `--min-confidence nominal` (`test_analyzer_config_rejects_values_outside_closed_mode_vocabularies`, `test_mode_run_matches_recorded_sarif_and_emits_strata`).

## Results, replay, and exits

A structured run writes `calls/`, `stages/`, `asserts/`, `replay.jsonl`, `trace.jsonl`, `metrics.json`, and `report.md`, plus immutable `inputs/config.json`, `inputs/manifest.json`, `inputs/items/`, and `inputs/requests/`. Canonical `inputs/index.json` lists every snapshot hash, and `run.json` authenticates the exact index bytes. Replay reads only this tree, authenticates the index and every snapshot before reading result records, invokes zero executors, and regenerates `metrics.json` and `report.md` byte-for-byte (`test_structured_smoke_writes_exact_tree`, `test_snapshot_index_has_exact_digest_pair_and_closed_versioned_requests`, `test_replay_refuses_a_mutated_snapshot_before_loading_results`, `test_replay_uses_no_executor_and_reproduces_reductions`, `test_documented_replay_command_reproduces_outputs_byte_for_byte`). Run the documented CLI as:

```sh
.venv/bin/python -m harness.structured.replay RESULTS_DIR
```

Completed structured reductions append one canonical row per candidate to `results/trends/<task>.jsonl`; existing bytes are preserved when later runs append (`test_render_appends_one_trend_row_per_candidate_and_preserves_prefix`, `test_trends_append_without_rewriting_existing_line`).

Structured runner exits are: 0 for a completed run whether promotion passes or fails; 1 for validation or integrity errors; 2 for argparse errors; 4 for stale-result refusal; and 5 for a test split without `--allow-test`. Child exits become recorded stage errors rather than runner exits (`test_promotion_verdict_prints_and_exits_zero`, `test_only_rejects_unknown_item_before_executor_creation`, `test_parser_has_exact_defaults_repeatable_only_and_argparse_exit_two`, `test_stale_refusal_returns_four_without_deleting`, `test_test_split_without_allow_test_exits_five_before_writes`, `test_child_exit_one_through_six_records_stage_error_and_cli_exits_zero`).

## Promotion, holdout, and evidence limits

`PROMOTABLE` requires the paired-bootstrap 95% lower bound for candidate minus baseline macro-F1 to be at least zero, schema validity to be at least 0.99, and no per-class recall delta whose own 95% upper bound is below zero. The runner reports the verdict and exits 0; CI owns the blocking decision (`test_promotion_accepts_exact_zero_bounds`, `test_each_promotion_condition_can_veto`, `test_dev_set_uses_an_executable_nonpromotion_gate`). Test splits are held out: local or CI access requires `--allow-test`, and the release-tag job increments `splits.test.consulted` in a separate commit (`test_test_split_without_allow_test_exits_five_before_writes`, `test_structured_workflow_has_the_exact_cost_and_holdout_matrix`).

The five seeded classification items and the pipeline item are synthetic smoke data. Their metrics test mechanics only and cannot support a quality or promotion claim. The human-vs-human κ is unavailable because taskset v2 stores `secondary.agrees` without the secondary class (`test_human_kappa_is_unavailable_when_secondary_classes_are_not_retained`). For harness cache reads, configured `provider_version` and `prompt_sha256` are an audited deployment identity and must change with the provider or serialized prompt; without a preflight identity the harness safely executes and leaves no reusable entry (`test_prompt_identity_change_cannot_reuse_a_stale_cache_entry`, `test_executor_without_cache_identity_always_executes_and_leaves_no_cache_record`).

## Conformance custody and known failures

Two local fixtures have canonical byte-pinned mirrors under `/Users/wesleyjinks/code/tools/contracts/fixtures/eval/`: `harness/tests/fixtures/directory_digest_v1/` pairs with `directory-digest-v1/`, and `harness/tests/fixtures/conformance/structured-smoke-001/` pairs with `structured-smoke-001/`. `test_directory_digest_matches_conformance_fixture`, `test_structured_request_to_tree_is_byte_pinned_and_repeatable`, and the mirror comparisons recorded in the Task 11 report are their evidence.

The required non-live suite currently has four known pre-existing failures. Task 11 neither fixes nor re-baselines them:

- `harness/tests/test_codex_executor.py::test_claude_provider_yaml_unchanged_regression`
- `mining/tests/test_triage_store_scrub.py::test_scrub_marks_sandbox_and_lineage_rows`
- `mining/tests/test_triage_store_scrub.py::test_scrub_is_idempotent`
- `mining/tests/test_triage_store_scrub.py::test_scrub_without_matching_parent_leaves_row_alone`

Their unchanged identity and the exact before/after totals are recorded in the Task 11 report. The report also records the skipped paid live smoke and both canonical mirror comparisons.
