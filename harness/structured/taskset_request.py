"""Taskset target joins and request assembly."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from harness.structured.taskset_types import TaskItem, TasksetError


def target_for_observation(
    target_value: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    target_id = observation.get("target_id")
    if not isinstance(target_id, str) or not target_id:
        raise TasksetError("observation target_id is missing")
    listed = target_value.get("targets")
    candidates = listed if isinstance(listed, list) else [target_value]
    matches = [
        target
        for target in candidates
        if isinstance(target, dict) and target.get("id") == target_id
    ]
    if len(matches) > 1:
        raise TasksetError(f"observation target_id is ambiguous: {target_id}")
    if not matches:
        if len(candidates) == 1:
            candidate_id = (
                candidates[0].get("id") if isinstance(candidates[0], dict) else None
            )
            raise TasksetError(
                "observation target_id mismatch: "
                f"observation={target_id!r}, target={candidate_id!r}"
            )
        raise TasksetError(
            f"observation target_id does not match any target: {target_id}"
        )
    return matches[0]


def assemble_request(
    item: TaskItem, *, task_version: str, request_schema: dict[str, Any]
) -> dict[str, Any]:
    try:
        observation = item.input_values["observation"]
        dependency = item.raw["inputs"]["dependency_semantics"]
        observed = dict(observation["observed"])
        if "log_excerpt" in observation:
            observed["log_excerpt"] = observation["log_excerpt"]
        request: dict[str, Any] = {
            "task": item.task,
            "task_version": task_version,
            "target": target_for_observation(item.input_values["target"], observation),
            "slice": item.input_values["slice"],
            "fault": observation["fault"],
            "observation": observed,
            "dependency_semantics": dependency,
        }
    except KeyError as exc:
        raise TasksetError(
            f"item {item.id} cannot assemble request; missing {exc.args[0]}"
        ) from exc
    errors = sorted(
        Draft202012Validator(request_schema).iter_errors(request),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise TasksetError(
            f"request schema validation failed at {location}: {first.message}"
        )
    return request


__all__ = ["assemble_request", "target_for_observation"]
