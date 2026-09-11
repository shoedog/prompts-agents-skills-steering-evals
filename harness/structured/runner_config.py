"""Validated snapshots and deterministic keys for structured runners."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from harness.structured.asserts import get
from harness.structured.config import AnalyzerConfig, StructuredConfig
from harness.structured.results import canonical_json
from harness.structured.runner_types import _safe_component
from harness.structured.taskset import TaskItem

def _config_snapshot(cfg: StructuredConfig, task: str) -> dict[str, Any]:
    try:
        taskset = cfg.taskset.relative_to(cfg.root).as_posix()
    except ValueError as error:
        raise ValueError("configured taskset is outside the repository root") from error
    return {
        "kind": cfg.kind,
        "id": cfg.id,
        "task": task,
        "taskset": taskset,
        "split": cfg.split,
        "versions": deepcopy(list(cfg.versions)),
        "baseline_version": cfg.baseline_version,
        "samples_per_item": cfg.samples_per_item,
        "seed": cfg.seed,
        "jobs": cfg.jobs,
        "asserts": deepcopy(list(cfg.asserts)),
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "request_schema": deepcopy(cfg.request_schema),
        "response_schema": deepcopy(cfg.response_schema),
    }


def _validate_versions(cfg: StructuredConfig) -> None:
    for version in cfg.versions:
        if not isinstance(version, dict):
            raise ValueError("every version must be an object")
        _safe_component(version.get("name"), "version name")
        task_version = version.get("task_version")
        if not isinstance(task_version, str) or not task_version:
            raise ValueError(f"version {version.get('name')!r} needs a nonempty task_version")
        provider = version.get("provider")
        if not isinstance(provider, dict):
            raise ValueError(f"version {version['name']!r} provider must be an object")
        for field in ("kind", "model"):
            if not isinstance(provider.get(field), str) or not provider[field]:
                raise ValueError(
                    f"version {version['name']!r} provider.{field} must be nonempty"
                )


def _validate_asserts(cfg: StructuredConfig) -> None:
    for number, entry in enumerate(cfg.asserts):
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
            raise ValueError(f"asserts[{number}] must have a string type")
        get(entry["type"])
        if entry["type"] == "cost_latency" and entry.get("population") not in {
            "run",
            "version",
        }:
            raise ValueError("cost_latency population must be 'run' or 'version'")


def _item_snapshot(item: TaskItem) -> dict[str, Any]:
    value = deepcopy(item.raw)
    slice_value = item.input_values.get("slice")
    if isinstance(slice_value, dict) and "rendered_slice" not in value:
        lines = slice_value.get("lines")
        rendered_numbers: list[int] = []
        if (
            isinstance(lines, list)
            and len(lines) == 2
            and all(isinstance(number, int) and not isinstance(number, bool) for number in lines)
        ):
            rendered_numbers = list(range(lines[0], lines[1] + 1))
        value["rendered_slice"] = {
            "text": slice_value.get("text", ""),
            "rendered_line_numbers": rendered_numbers,
        }
    return value


def _seed(base: int, version: str, item_id: str, sample: int) -> int:
    payload = canonical_json(
        {"seed": base, "version": version, "item_id": item_id, "sample": sample}
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 0x7FFFFFFF

def _analyzer_artifact_key(version: str) -> str:
    return f"mode-{hashlib.sha256(version.encode()).hexdigest()[:16]}"


def _analyzer_config_snapshot(cfg: AnalyzerConfig, task: str) -> dict[str, Any]:
    try:
        taskset = cfg.taskset.relative_to(cfg.root).as_posix()
    except ValueError as error:
        raise ValueError("configured taskset is outside the repository root") from error
    return {
        "kind": "analyzer",
        "id": cfg.id,
        "task": task,
        "taskset": taskset,
        "split": cfg.split,
        "versions": [{"name": mode.version, **asdict(mode)} for mode in cfg.modes],
        "baseline_version": cfg.baseline_version,
        "samples_per_item": 1,
        "asserts": deepcopy(list(cfg.asserts)),
        "match": {
            "rule": "category_file_line",
            "line_tolerance": cfg.line_tolerance,
        },
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "prism_bin": cfg.prism_bin,
    }
