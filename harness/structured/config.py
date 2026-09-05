from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from harness.structured.schema_ref import SchemaRefError, resolve_schema_ref


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER_RESOLUTIONS = frozenset({"nominal", "scoped", "precise"})
ANALYZER_CONFIDENCE_FLOORS = frozenset({"exact", "nameonly"})


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class StructuredConfig:
    kind: str
    id: str
    taskset: Path
    split: str
    versions: Sequence[dict[str, Any]]
    baseline_version: str
    samples_per_item: int
    seed: int
    jobs: int
    asserts: Sequence[dict[str, Any]]
    stats: dict[str, Any]
    token_budget: dict[str, Any]
    root: Path
    request_schema: dict[str, Any]
    response_schema: dict[str, Any]


@dataclass(frozen=True)
class AnalyzerConfig:
    id: str
    taskset: Path
    split: str
    modes: Sequence[Any]
    baseline_version: str
    prism_bin: str | None
    line_tolerance: int
    asserts: Sequence[dict[str, Any]]
    stats: dict[str, Any]
    token_budget: dict[str, Any]
    root: Path


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{name} must be a positive integer")
    return value


def _inside(root: Path, path: Path) -> bool:
    return root == path or root in path.parents


def _path_inside(root: Path, raw: str, name: str) -> Path:
    path = (root / raw).resolve()
    if not _inside(root, path):
        raise ConfigError(f"{name} path escapes repo root: {raw}")
    return path


def load_config(
    path: str | Path, *, root: Path = REPO_ROOT
) -> StructuredConfig | AnalyzerConfig:
    root = Path(root).resolve()
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = root / config_path
    config_path = config_path.resolve()
    if not _inside(root, config_path):
        raise ConfigError(f"config path escapes repo root: {path}")
    try:
        raw = yaml.safe_load(config_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load config {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("structured config must contain one YAML object")
    kind = raw.get("kind")
    if kind == "analyzer":
        return load_analyzer_config(config_path, root=root)
    if kind != "structured_task":
        raise ConfigError(f"unknown structured kind: {kind!r}")
    experiment_id = raw.get("id")
    if not isinstance(experiment_id, str) or not experiment_id.startswith("st-"):
        raise ConfigError("structured_task id must start with st-")
    split = raw.get("split")
    if split not in {"dev", "test"}:
        raise ConfigError("split must be dev or test")
    versions = raw.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ConfigError("versions must be a nonempty list")
    names = [version.get("name") for version in versions if isinstance(version, dict)]
    if len(names) != len(versions) or any(not isinstance(name, str) or not name for name in names):
        raise ConfigError("every version must have a nonempty name")
    if len(set(names)) != len(names):
        raise ConfigError("duplicate version name")
    baseline = raw.get("baseline_version")
    if baseline not in names:
        raise ConfigError("baseline_version must name one declared version")
    samples = _positive_int(raw.get("samples_per_item"), "samples_per_item")
    jobs = _positive_int(raw.get("jobs", 4), "jobs")
    stats = raw.get("stats")
    if not isinstance(stats, dict):
        raise ConfigError("stats must be an object")
    _positive_int(stats.get("bootstrap_resamples"), "bootstrap_resamples")
    budget = raw.get("token_budget")
    if not isinstance(budget, dict):
        raise ConfigError("token_budget must be an object")
    _positive_int(budget.get("max_items"), "max_items")
    taskset_raw = raw.get("taskset")
    if not isinstance(taskset_raw, str):
        raise ConfigError("taskset must be a path string")
    taskset = _path_inside(root, taskset_raw, "taskset")
    if not taskset.is_dir():
        raise ConfigError(f"taskset directory does not exist: {taskset}")
    try:
        _, request_schema = resolve_schema_ref(root, raw.get("request_schema", ""))
        _, response_schema = resolve_schema_ref(root, raw.get("response_schema", ""))
    except SchemaRefError as exc:
        raise ConfigError(str(exc)) from exc
    asserts = raw.get("asserts")
    if not isinstance(asserts, list):
        raise ConfigError("asserts must be a list")
    seed = raw.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ConfigError("seed must be an integer")
    return StructuredConfig(
        kind=kind,
        id=experiment_id,
        taskset=taskset,
        split=split,
        versions=tuple(versions),
        baseline_version=baseline,
        samples_per_item=samples,
        seed=seed,
        jobs=jobs,
        asserts=tuple(asserts),
        stats=stats,
        token_budget=budget,
        root=root,
        request_schema=request_schema,
        response_schema=response_schema,
    )


def load_analyzer_config(path: str | Path, *, root: Path = REPO_ROOT) -> AnalyzerConfig:
    """Load the analyzer config shape without changing ``load_config``'s interface."""
    root = Path(root).resolve()
    config_path = Path(path)
    config_path = (config_path if config_path.is_absolute() else root / config_path).resolve()
    if not _inside(root, config_path):
        raise ConfigError(f"config path escapes repo root: {path}")
    try:
        raw = yaml.safe_load(config_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load config {config_path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("kind") != "analyzer":
        raise ConfigError("analyzer config must contain kind: analyzer")
    experiment_id = raw.get("id")
    if not isinstance(experiment_id, str) or not experiment_id.startswith("an-"):
        raise ConfigError("analyzer id must start with an-")
    split = raw.get("split")
    if split not in {"dev", "test"}:
        raise ConfigError("split must be dev or test")
    taskset_raw = raw.get("taskset")
    if not isinstance(taskset_raw, str):
        raise ConfigError("taskset must be a path string")
    taskset = _path_inside(root, taskset_raw, "taskset")
    if not taskset.is_dir():
        raise ConfigError(f"taskset directory does not exist: {taskset}")
    axes = raw.get("modes")
    names = ("algorithm", "language", "resolution", "min_confidence")
    if not isinstance(axes, dict) or any(
        not isinstance(axes.get(name), list)
        or not axes[name]
        or any(not isinstance(value, str) or not value for value in axes[name])
        for name in names
    ):
        raise ConfigError(f"modes must declare nonempty string lists for {names}")
    invalid_resolutions = sorted(set(axes["resolution"]) - ANALYZER_RESOLUTIONS)
    if invalid_resolutions:
        raise ConfigError(
            "modes.resolution values must be one of "
            f"{sorted(ANALYZER_RESOLUTIONS)}; got {invalid_resolutions}"
        )
    invalid_confidences = sorted(
        set(axes["min_confidence"]) - ANALYZER_CONFIDENCE_FLOORS
    )
    if invalid_confidences:
        raise ConfigError(
            "modes.min_confidence values must be one of "
            f"{sorted(ANALYZER_CONFIDENCE_FLOORS)}; got {invalid_confidences}"
        )
    from harness.structured.analyzer import AnalyzerMode

    modes = tuple(
        AnalyzerMode(algorithm, language, resolution, confidence)
        for algorithm in axes["algorithm"]
        for language in axes["language"]
        for resolution in axes["resolution"]
        for confidence in axes["min_confidence"]
    )
    baseline = raw.get("baseline_version")
    if baseline not in {mode.version for mode in modes}:
        raise ConfigError("baseline_version must name one expanded analyzer mode")
    match = raw.get("match")
    tolerance = match.get("line_tolerance") if isinstance(match, dict) else None
    if not isinstance(tolerance, int) or isinstance(tolerance, bool) or tolerance < 0:
        raise ConfigError("match.line_tolerance must be a nonnegative integer")
    if not isinstance(match, dict) or match.get("rule") != "category_file_line":
        raise ConfigError("analyzer match.rule must be category_file_line")
    asserts = raw.get("asserts")
    if not isinstance(asserts, list) or {entry.get("type") for entry in asserts if isinstance(entry, dict)} != {"analyzer_match"}:
        raise ConfigError("analyzer asserts must contain analyzer_match")
    stats, budget = raw.get("stats"), raw.get("token_budget")
    if not isinstance(stats, dict) or not isinstance(budget, dict):
        raise ConfigError("stats and token_budget must be objects")
    _positive_int(stats.get("bootstrap_resamples"), "bootstrap_resamples")
    if not isinstance(stats.get("seed"), int) or isinstance(stats.get("seed"), bool):
        raise ConfigError("stats.seed must be an integer")
    _positive_int(budget.get("max_items"), "max_items")
    prism_bin = raw.get("prism_bin")
    if prism_bin is not None and (
        not isinstance(prism_bin, str) or not prism_bin.startswith("env:") or len(prism_bin) == 4
    ):
        raise ConfigError("prism_bin must be env:VARIABLE when present")
    return AnalyzerConfig(
        experiment_id, taskset, split, modes, baseline, prism_bin, tolerance,
        tuple(asserts), stats, budget, root,
    )
