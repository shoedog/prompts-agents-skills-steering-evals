"""Validation for the pipeline-specific structured config shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from harness.structured.config import (
    REPO_ROOT,
    ConfigError,
    PipelineConfig,
    _inside,
    _path_inside,
    _positive_int,
)
from harness.structured.schema_ref import SchemaRefError, resolve_schema_ref


def load_pipeline_config(path: str | Path, *, root: Path = REPO_ROOT) -> PipelineConfig:
    root = Path(root).resolve()
    config_path = Path(path)
    config_path = (config_path if config_path.is_absolute() else root / config_path).resolve()
    if not _inside(root, config_path):
        raise ConfigError(f"config path escapes repo root: {path}")
    try:
        raw = yaml.safe_load(config_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load config {config_path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("kind") != "pipeline":
        raise ConfigError("pipeline config must contain kind: pipeline")
    experiment_id = raw.get("id")
    if not isinstance(experiment_id, str) or not experiment_id.startswith("pl-"):
        raise ConfigError("pipeline id must start with pl-")
    split = raw.get("split")
    if split not in {"dev", "test"}:
        raise ConfigError("split must be dev or test")
    taskset_raw = raw.get("taskset")
    if not isinstance(taskset_raw, str):
        raise ConfigError("taskset must be a path string")
    taskset = _path_inside(root, taskset_raw, "taskset")
    if not taskset.is_dir():
        raise ConfigError(f"taskset directory does not exist: {taskset}")

    stages = raw.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ConfigError("pipeline stages must be a nonempty list")
    stage_names: list[str] = []
    for number, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ConfigError(f"stages[{number}] must be an object")
        name = stage.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"stages[{number}].name must be nonempty")
        if stage.get("type") not in {"file", "prism", "harness", "llm"}:
            raise ConfigError(f"stages[{number}].type is invalid")
        if stage.get("pin") not in {"from_item", "never", "if_absent"}:
            raise ConfigError(f"stages[{number}].pin is invalid")
        if stage.get("type") == "llm" and (
            not isinstance(stage.get("task"), str) or not stage["task"]
        ):
            raise ConfigError(f"stages[{number}].task must name the LLM task")
        stage_names.append(name)
    if len(set(stage_names)) != len(stage_names):
        raise ConfigError("duplicate pipeline stage name")

    versions = raw.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ConfigError("versions must be a nonempty list")
    version_names: list[str] = []
    for number, version in enumerate(versions):
        if not isinstance(version, dict):
            raise ConfigError(f"versions[{number}] must be an object")
        name = version.get("name")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"versions[{number}].name must be nonempty")
        if version.get("stage") not in stage_names:
            raise ConfigError(f"versions[{number}].stage must name a pipeline stage")
        if not isinstance(version.get("task_version"), str) or not version["task_version"]:
            raise ConfigError(f"versions[{number}].task_version must be nonempty")
        if "model" in version and (
            not isinstance(version["model"], str) or not version["model"]
        ):
            raise ConfigError(f"versions[{number}].model must be nonempty")
        version_names.append(name)
    if len(set(version_names)) != len(version_names):
        raise ConfigError("duplicate version name")
    baseline = raw.get("baseline_version")
    if baseline not in version_names:
        raise ConfigError("baseline_version must name one declared version")
    samples = _positive_int(raw.get("samples_per_item"), "samples_per_item")
    if samples != 1:
        raise ConfigError("pipeline samples_per_item must be 1")
    seed = raw.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ConfigError("seed must be an integer")
    jobs = _positive_int(raw.get("jobs", 4), "jobs")
    asserts = raw.get("asserts")
    if not isinstance(asserts, list):
        raise ConfigError("asserts must be a list")
    stats, budget = raw.get("stats"), raw.get("token_budget")
    if not isinstance(stats, dict) or not isinstance(budget, dict):
        raise ConfigError("stats and token_budget must be objects")
    _positive_int(stats.get("bootstrap_resamples"), "bootstrap_resamples")
    if not isinstance(stats.get("seed"), int) or isinstance(stats.get("seed"), bool):
        raise ConfigError("stats.seed must be an integer")
    _positive_int(budget.get("max_items"), "max_items")
    max_cost = budget.get("max_cost_usd")
    if not isinstance(max_cost, (int, float)) or isinstance(max_cost, bool) or max_cost < 0:
        raise ConfigError("token_budget.max_cost_usd must be nonnegative")
    llm_tasks = {stage["task"] for stage in stages if stage.get("type") == "llm"}
    if llm_tasks != {"classify_error_handling"}:
        raise ConfigError("pipeline v1 requires one classify_error_handling LLM task")
    try:
        _, request_schema = resolve_schema_ref(
            root, "contracts/classify_error_handling.schema.json#/$defs/request"
        )
        _, response_schema = resolve_schema_ref(
            root, "contracts/classify_error_handling.schema.json#/$defs/response"
        )
    except SchemaRefError as exc:
        raise ConfigError(str(exc)) from exc
    return PipelineConfig(
        "pipeline", experiment_id, taskset, split, tuple(stages), tuple(versions),
        baseline, samples, seed, jobs, tuple(asserts), stats, budget, root,
        request_schema, response_schema,
    )


__all__ = ["load_pipeline_config"]
