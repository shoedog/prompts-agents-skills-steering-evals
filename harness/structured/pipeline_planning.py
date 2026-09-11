"""No-spend planning for authenticated pipeline requests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from harness.structured.config import PipelineConfig
from harness.structured.pipeline import VersionConfig, validate_request
from harness.structured.pipeline_stages import request_body
from harness.structured.taskset import TaskItem, TasksetError


def config_snapshot(cfg: PipelineConfig, task: str) -> dict[str, Any]:
    versions = []
    for version in cfg.versions:
        versions.append(
            {
                **deepcopy(version),
                "provider": {
                    "kind": "llm_layer",
                    "model": version.get("model", version["name"]),
                },
            }
        )
    return {
        "kind": "pipeline",
        "id": cfg.id,
        "task": task,
        "taskset": cfg.taskset.relative_to(cfg.root).as_posix(),
        "split": cfg.split,
        "stages": deepcopy(list(cfg.stages)),
        "versions": versions,
        "baseline_version": cfg.baseline_version,
        "samples_per_item": 1,
        "seed": cfg.seed,
        "jobs": cfg.jobs,
        "asserts": deepcopy(list(cfg.asserts)),
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "request_schema": deepcopy(cfg.request_schema),
        "response_schema": deepcopy(cfg.response_schema),
    }


def plan_requests(
    items: Sequence[TaskItem], cfg: PipelineConfig
) -> dict[tuple[str, str], dict[str, Any]]:
    planned: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        available: dict[str, dict[str, Any]] = {}
        declarations = item.raw.get("stages", {})
        for stage in cfg.stages:
            if stage["type"] == "llm":
                break
            name = stage["name"]
            declaration = declarations.get(name, {})
            has_pin = isinstance(declaration.get("pin"), str)
            use_pin = stage["pin"] == "from_item" or (
                stage["pin"] == "if_absent" and has_pin
            )
            if use_pin and name in item.input_values:
                available[name] = item.input_values[name]
        if not {"targets", "observation"}.issubset(available):
            continue
        for raw_version in cfg.versions:
            version: VersionConfig = {**deepcopy(raw_version), "seed": cfg.seed}
            try:
                request = request_body(item=item, version=version, inputs=available)
                validate_request(request)
            except (KeyError, TypeError, ValueError) as error:
                raise TasksetError(
                    f"pipeline planning failed for item {item.id}: {error}"
                ) from error
            planned[(item.id, version["name"])] = request
    return planned


__all__ = ["config_snapshot", "plan_requests"]
