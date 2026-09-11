"""Taskset manifest and item loader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from harness.structured.taskset_inputs import (
    _inside,
    _input_ref,
    _load_yaml_object,
    _repo_root,
    _verify_hash,
    verified_json,
)
from harness.structured.taskset_request import target_for_observation
from harness.structured.taskset_types import InputRef, TaskItem, Taskset, TasksetError
from harness.structured.taskset_validation import (
    _validate,
    _validate_manifest,
    resolve_schema_ref,
)


def load_taskset(root: Path, *, split: str, max_items: int) -> Taskset:
    root = Path(root).resolve()
    if split not in {"dev", "test"}:
        raise TasksetError(f"unknown split {split!r}; expected dev or test")
    if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items <= 0:
        raise TasksetError("max_items must be a positive integer")
    manifest = _load_yaml_object(root / "manifest.yaml", "manifest")
    _validate_manifest(manifest)
    guide_raw = manifest["labeling_guide"]
    if not isinstance(guide_raw, str) or not guide_raw:
        raise TasksetError("manifest labeling_guide must be a nonempty path string")
    guide = (root / guide_raw).resolve()
    if not _inside(root, guide):
        raise TasksetError(f"labeling_guide path escapes taskset root: {guide_raw}")
    if not guide.is_file():
        raise TasksetError(f"labeling_guide does not exist: {guide}")
    if split not in manifest["splits"]:
        raise TasksetError(f"split {split!r} is absent from manifest")
    repo_root = _repo_root(root)
    request_schema: dict[str, Any] = {}
    response_schema: dict[str, Any] = {}
    if "request_schema" in manifest:
        _, request_schema = resolve_schema_ref(repo_root, manifest["request_schema"])
    if "response_schema" in manifest:
        _, response_schema = resolve_schema_ref(repo_root, manifest["response_schema"])
    taskset_document, taskset_schema = resolve_schema_ref(
        repo_root, "contracts/taskset_v2.schema.json"
    )
    target_document, target_schema = resolve_schema_ref(
        repo_root, "contracts/targets.schema.json#/$defs/target"
    )
    observation_document, observation_schema = resolve_schema_ref(
        repo_root, "contracts/observations.schema.json#/$defs/observation"
    )

    summaries = manifest["items"]
    summary_by_id: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        if not isinstance(summary, dict) or not isinstance(summary.get("id"), str):
            raise TasksetError("each manifest item must have a string id")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", summary["id"]) is None:
            raise TasksetError(f"invalid manifest item id: {summary['id']!r}")
        if summary["id"] in summary_by_id:
            raise TasksetError(f"duplicate manifest item id: {summary['id']}")
        summary_by_id[summary["id"]] = summary

    loaded: list[TaskItem] = []
    selected = sorted(
        (summary for summary in summaries if summary.get("split") == split),
        key=lambda summary: summary["id"],
    )[:max_items]
    for summary in selected:
        item_path = root / "items" / f"{summary['id']}.yaml"
        raw = _load_yaml_object(item_path, "taskset item")
        _validate(raw, taskset_document, taskset_schema, f"item {summary['id']}")
        for field in ("id", "split", "contamination_risk"):
            if raw.get(field) != summary.get(field):
                raise TasksetError(
                    f"manifest/item {field} mismatch for {summary['id']}: "
                    f"{summary.get(field)!r} != {raw.get(field)!r}"
                )
        if raw.get("task") != manifest.get("task"):
            raise TasksetError(f"manifest/item task mismatch for {summary['id']}")
        ignores = raw.get("ignore", [])
        refs: dict[str, InputRef] = {}
        values: dict[str, dict[str, Any]] = {}
        input_specs = dict(raw.get("inputs", {}))
        for name, stage in raw.get("stages", {}).items():
            if isinstance(stage, dict) and isinstance(stage.get("pin"), str):
                input_specs[name] = {
                    "path": stage["pin"],
                    "sha256": stage.get("sha256"),
                }
        for name, value in input_specs.items():
            if name == "dependency_semantics":
                continue
            ref = _input_ref(root, name, value)
            refs[name] = ref
            if ref.path.is_dir():
                _verify_hash(ref, ignore=ignores)
            elif ref.path.suffix.lower() == ".json":
                values[name] = verified_json(ref, ignore=ignores)
            else:
                _verify_hash(ref, ignore=ignores)
        if "target" in values:
            _validate(values["target"], target_document, target_schema, "target")
        if "observation" in values:
            _validate(
                values["observation"],
                observation_document,
                observation_schema,
                "observation",
            )
            if "target" in values:
                target_for_observation(values["target"], values["observation"])
            elif "targets" in values:
                target_for_observation(values["targets"], values["observation"])
        loaded.append(
            TaskItem(
                id=raw["id"],
                task=raw["task"],
                split=raw["split"],
                expected=raw["expected"],
                inputs=refs,
                input_values=values,
                raw=raw,
            )
        )
    return Taskset(
        root=root,
        manifest=manifest,
        classes=tuple(manifest.get("classes", [])),
        items=tuple(loaded),
        request_schema=request_schema,
        response_schema=response_schema,
    )


__all__ = ["load_taskset"]
