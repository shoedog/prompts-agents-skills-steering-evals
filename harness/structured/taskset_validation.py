"""Taskset manifest and schema validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from harness.structured.schema_ref import SchemaRefError
from harness.structured.schema_ref import resolve_schema_ref as _resolve_schema_ref
from harness.structured.taskset_types import TasksetError


def resolve_schema_ref(root: Path, ref: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return _resolve_schema_ref(root, ref)
    except SchemaRefError as exc:
        raise TasksetError(str(exc)) from exc


def _schema_with_local_defs(
    document: dict[str, Any], selected: dict[str, Any]
) -> dict[str, Any]:
    schema = dict(selected)
    if "$defs" in document and "$defs" not in schema:
        schema["$defs"] = document["$defs"]
    if "$schema" in document and "$schema" not in schema:
        schema["$schema"] = document["$schema"]
    return schema


def _validate(
    value: Any, document: dict[str, Any], selected: dict[str, Any], label: str
) -> None:
    errors = sorted(
        Draft202012Validator(_schema_with_local_defs(document, selected)).iter_errors(
            value
        ),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        actionable = []

        def collect(error: Any) -> None:
            if error.context:
                for child in error.context:
                    collect(child)
            else:
                actionable.append(error)

        for error in errors:
            collect(error)
        branch_by_task = {
            "classify_error_handling": 0,
            "prism_analyzer": 1,
            "eh_pipeline": 2,
        }
        branch = branch_by_task.get(value.get("task")) if isinstance(value, dict) else None
        if branch is not None:
            matching = [
                error
                for error in actionable
                if list(error.absolute_schema_path)[:2] == ["oneOf", branch]
            ]
            if matching:
                actionable = matching
        first = sorted(
            actionable or errors,
            key=lambda error: (
                [str(part) for part in error.absolute_path],
                [str(part) for part in error.absolute_schema_path],
            ),
        )[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise TasksetError(
            f"{label} schema validation failed at {location}: {first.message}"
        )


def _validate_manifest(manifest: dict[str, Any]) -> None:
    allowed = {
        "taskset", "schema_version", "task", "request_schema", "response_schema",
        "labeling_guide", "class_field", "classes", "splits", "items", "line_tolerance",
    }
    unexpected = sorted(set(manifest) - allowed)
    if unexpected:
        raise TasksetError(f"unknown manifest field: manifest.{unexpected[0]}")
    required = {
        "taskset", "schema_version", "task", "labeling_guide", "splits", "items",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise TasksetError(f"manifest missing required fields: {missing}")
    if manifest["schema_version"] != 2:
        raise TasksetError("manifest schema_version must be 2")
    if not isinstance(manifest["items"], list) or not isinstance(manifest["splits"], dict):
        raise TasksetError("manifest items and splits must be collections")
    summary_allowed = {"id", "split", "contamination_risk"}
    summary_required = summary_allowed
    for index, summary in enumerate(manifest["items"]):
        if not isinstance(summary, dict):
            raise TasksetError(f"manifest.items[{index}] must be an object")
        unexpected = sorted(set(summary) - summary_allowed)
        if unexpected:
            raise TasksetError(
                f"unknown manifest item field: manifest.items[{index}].{unexpected[0]}"
            )
        missing = sorted(summary_required - summary.keys())
        if missing:
            raise TasksetError(
                f"manifest.items[{index}] missing required fields: {missing}"
            )
    for split, policy in manifest["splits"].items():
        if split not in {"dev", "test"} or not isinstance(policy, dict):
            raise TasksetError(f"invalid manifest split policy: {split!r}")
        policy_allowed = {"items", "min_per_class", "consulted"}
        unexpected = sorted(set(policy) - policy_allowed)
        if unexpected:
            raise TasksetError(
                f"unknown manifest split field: manifest.splits.{split}.{unexpected[0]}"
            )
        for field in ("items", "min_per_class"):
            value = policy.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise TasksetError(
                    f"manifest split {split} {field} must be a nonnegative integer"
                )
        actual = sum(
            1
            for summary in manifest["items"]
            if isinstance(summary, dict) and summary.get("split") == split
        )
        if policy["items"] != actual:
            raise TasksetError(
                f"manifest split {split} count mismatch: declared {policy['items']}, actual {actual}"
            )
    test_policy = manifest["splits"].get("test")
    if isinstance(test_policy, dict) and "consulted" in test_policy:
        consulted = test_policy["consulted"]
        if not isinstance(consulted, int) or isinstance(consulted, bool) or consulted < 0:
            raise TasksetError(
                "manifest split test consulted must be a nonnegative integer"
            )
    classes = manifest.get("classes", [])
    if not isinstance(classes, list) or len(set(classes)) != len(classes):
        raise TasksetError("manifest classes must be a list of unique values")
    if manifest["task"] == "classify_error_handling":
        classification = {"request_schema", "response_schema", "class_field", "classes"}
        missing = sorted(classification - manifest.keys())
        if missing:
            raise TasksetError(
                f"classification manifest missing required fields: {missing}"
            )


__all__ = ["resolve_schema_ref"]
