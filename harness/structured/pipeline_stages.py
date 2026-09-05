"""Executable stage adapters for structured pipelines."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from harness.providers.binpath import resolve_executable
from harness.structured.executors import ExecutionRequest, LlmLayerExecutor
from harness.structured.pipeline import StageConfig, VersionConfig, validate_request
from harness.structured.results import ResultsWriter, canonical_json, write_json_atomic
from harness.structured.taskset import TaskItem, target_for_observation


def request_body(
    *, item: TaskItem, version: VersionConfig, inputs: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    target_value = inputs.get("targets", item.input_values.get("targets", {}))
    observation = inputs.get("observation", item.input_values.get("observation", {}))
    target = target_for_observation(target_value, observation)
    site = target.get("site", {}) if isinstance(target, dict) else {}
    line = site.get("line", 1)
    observed = dict(observation.get("observed", {}))
    if "log_excerpt" in observation:
        observed["log_excerpt"] = observation["log_excerpt"]
    return {
        "task": "classify_error_handling",
        "task_version": version["task_version"],
        "target": target,
        "slice": {
            "text": f"{line}: {target.get('description', 'pipeline target')}",
            "file": site.get("file", "unknown"),
            "function": site.get("symbol", "unknown"),
            "language": item.raw.get("language", "unknown"),
            "lines": [line, line],
        },
        "fault": observation.get("fault"),
        "observation": observed,
        "dependency_semantics": {"source": "none"},
    }


class LlmStage:
    def __init__(self, scratch: Path) -> None:
        self.scratch = scratch
        self.envelope: dict[str, Any] | None = None
        self.request: dict[str, Any] | None = None

    def __call__(
        self,
        *,
        stage: StageConfig,
        item: TaskItem,
        version: VersionConfig,
        inputs: Mapping[str, dict[str, Any]],
        writer: ResultsWriter,
    ) -> dict[str, Any]:
        del writer
        request = request_body(item=item, version=version, inputs=inputs)
        validate_request(request)
        self.request = request
        request_file = self.scratch / f"{version['name']}-{item.id}.json"
        write_json_atomic(request_file, request)
        execution = LlmLayerExecutor().run(
            ExecutionRequest(
                task=stage["task"],
                task_version=version["task_version"],
                request_file=request_file,
                model=str(version.get("model", version["name"])),
                seed=int(version["seed"]),
                sample=0,
                scratch_dir=self.scratch,
            )
        )
        self.envelope = dict(execution.envelope)
        response = self.envelope.get("response")
        if not isinstance(response, dict):
            raise ValueError("llm pipeline stage response must be one JSON object")
        return response


def run_prism_stage(
    *,
    stage: StageConfig,
    item: TaskItem,
    version: VersionConfig,
    inputs: Mapping[str, dict[str, Any]],
    writer: ResultsWriter,
) -> dict[str, Any]:
    del version, inputs, writer
    repo, diff = item.inputs.get("repo"), item.inputs.get("diff")
    if repo is None or diff is None:
        raise ValueError(f"pipeline prism stage {item.id} requires repo and diff inputs")
    executable = resolve_executable("prism")
    argv = [
        executable,
        "--repo",
        str(repo.path),
        "--diff",
        str(diff.path),
        "-a",
        str(stage.get("algorithm", item.raw.get("algorithm", "absence"))),
        "--format",
        "json",
    ]
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"prism stage exited with code {completed.returncode}: {completed.stderr[-1000:]}"
        )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("prism stage stdout must contain one JSON object")
    return value


def error_envelope(version: VersionConfig, request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "invocation_id": "00000000-0000-4000-8000-000000000000",
        "task": "classify_error_handling",
        "task_version": version["task_version"],
        "provider": "unavailable",
        "model": str(version.get("model", version["name"])),
        "provider_version": "unavailable",
        "prompt_sha256": hashlib.sha256(canonical_json(request)).hexdigest(),
        "escalation_state": "provider_error",
        "first_tier_valid": None,
        "first_tier_sentinel": None,
        "final_sentinel": True,
        "cache_hit": False,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "cost_usd": 0.0,
        "response": {"class": "provider_error"},
        "log_path": "",
    }


__all__ = ["LlmStage", "error_envelope", "request_body", "run_prism_stage"]
