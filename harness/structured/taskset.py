from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

import yaml
from jsonschema import Draft202012Validator

from harness.structured.schema_ref import SchemaRefError
from harness.structured.schema_ref import resolve_schema_ref as _resolve_schema_ref


class TasksetError(ValueError):
    pass


@dataclass(frozen=True)
class InputRef:
    name: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class TaskItem:
    id: str
    task: str
    split: str
    expected: dict[str, Any]
    inputs: dict[str, InputRef]
    input_values: dict[str, dict[str, Any]]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Taskset:
    root: Path
    manifest: dict[str, Any]
    classes: Sequence[str]
    items: Sequence[TaskItem]
    request_schema: dict[str, Any]
    response_schema: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ignored(path: str, patterns: Sequence[str]) -> bool:
    candidate = PurePosixPath(path)
    return any(candidate.match(pattern) for pattern in patterns)


def sha256_directory(root: Path, *, ignore: Sequence[str]) -> str:
    """Hash a directory with the canonical eval-directory-sha256-v1 algorithm."""
    root = root.resolve()
    if not root.is_dir():
        raise TasksetError(f"directory input is not a directory: {root}")
    entries: list[tuple[bytes, bytes, bytes]] = []
    normalized_sources: dict[str, str] = {}

    def walk(directory: Path, relative_parts: tuple[str, ...]) -> None:
        try:
            children = list(os.scandir(directory))
        except OSError as exc:
            raise TasksetError(f"cannot read directory input {directory}: {exc}") from exc
        for entry in children:
            raw_parts = (*relative_parts, entry.name)
            if raw_parts[0] == ".git":
                continue
            raw_relative = PurePosixPath(*raw_parts).as_posix()
            normalized = unicodedata.normalize("NFC", raw_relative)
            if _ignored(normalized, ignore):
                continue
            prior = normalized_sources.get(normalized)
            if prior is not None and prior != raw_relative:
                raise TasksetError(
                    f"directory paths normalize to the same path: {prior!r} and {raw_relative!r}"
                )
            normalized_sources[normalized] = raw_relative
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise TasksetError(f"cannot stat directory entry {raw_relative}: {exc}") from exc
            path = Path(entry.path)
            if stat.S_ISDIR(mode):
                walk(path, raw_parts)
                continue
            if stat.S_ISLNK(mode):
                kind = b"l"
                try:
                    payload = os.readlink(os.fsencode(path))
                except OSError as exc:
                    raise TasksetError(f"cannot read symlink {raw_relative}: {exc}") from exc
            elif stat.S_ISREG(mode):
                kind = b"x" if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) else b"f"
                try:
                    payload = path.read_bytes()
                except OSError as exc:
                    raise TasksetError(f"cannot read directory entry {raw_relative}: {exc}") from exc
            else:
                raise TasksetError(f"unsupported file type in directory input: {raw_relative}")
            entries.append((normalized.encode("utf-8"), kind, payload))

    walk(root, ())
    outer = hashlib.sha256()
    for encoded_path, kind, payload in sorted(entries, key=lambda value: value[0]):
        entry_digest = hashlib.sha256(
            kind
            + b"\0"
            + encoded_path
            + b"\0"
            + str(len(payload)).encode("ascii")
            + b"\0"
            + payload
        ).digest()
        outer.update(entry_digest)
    return outer.hexdigest()


def resolve_schema_ref(root: Path, ref: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return _resolve_schema_ref(root, ref)
    except SchemaRefError as exc:
        raise TasksetError(str(exc)) from exc


def _schema_with_local_defs(document: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    schema = dict(selected)
    if "$defs" in document and "$defs" not in schema:
        schema["$defs"] = document["$defs"]
    if "$schema" in document and "$schema" not in schema:
        schema["$schema"] = document["$schema"]
    return schema


def _validate(value: Any, document: dict[str, Any], selected: dict[str, Any], label: str) -> None:
    errors = sorted(
        Draft202012Validator(_schema_with_local_defs(document, selected)).iter_errors(value),
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
        raise TasksetError(f"{label} schema validation failed at {location}: {first.message}")


def _load_yaml_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise TasksetError(f"cannot load {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TasksetError(f"{label} must contain one YAML object: {path}")
    return value


def _inside(root: Path, path: Path) -> bool:
    return root == path or root in path.parents


def _repo_root(taskset_root: Path) -> Path:
    for candidate in (taskset_root, *taskset_root.parents):
        if (candidate / "contracts").is_dir():
            return candidate.resolve()
    raise TasksetError(f"cannot locate repo contracts directory above {taskset_root}")


def _input_ref(taskset_root: Path, name: str, value: Any) -> InputRef:
    if not isinstance(value, dict):
        raise TasksetError(f"input {name} must be an object")
    raw_path = value.get("path")
    expected = value.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise TasksetError(f"input {name} path must be a nonempty string")
    if not isinstance(expected, str) or len(expected) != 64:
        raise TasksetError(f"input {name} sha256 must be 64 lowercase hex characters")
    path = (taskset_root / raw_path).resolve()
    root = taskset_root.resolve()
    if not _inside(root, path):
        raise TasksetError(f"input path escapes taskset root: {name} {raw_path}")
    return InputRef(name=name, path=path, sha256=expected)


def _verify_hash(ref: InputRef, *, ignore: Sequence[str]) -> bytes | None:
    try:
        if ref.path.is_dir():
            payload = None
            actual = sha256_directory(ref.path, ignore=ignore)
        else:
            payload = ref.path.read_bytes()
            actual = hashlib.sha256(payload).hexdigest()
    except OSError as exc:
        raise TasksetError(f"cannot hash {ref.name} {ref.path}: {exc}") from exc
    if actual != ref.sha256:
        raise TasksetError(
            f"sha256 mismatch for {ref.name} {ref.path}: expected {ref.sha256}, got {actual}"
        )
    return payload


def verified_json(ref: InputRef, *, ignore: Sequence[str] = ()) -> dict[str, Any]:
    payload = _verify_hash(ref, ignore=ignore)
    if payload is None:
        raise TasksetError(f"{ref.name} is a directory, not a JSON artifact: {ref.path}")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TasksetError(f"cannot parse {ref.name} JSON {ref.path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TasksetError(f"{ref.name} must contain one JSON object: {ref.path}")
    return value


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
            raise TasksetError(f"unknown manifest split field: manifest.splits.{split}.{unexpected[0]}")
        for field in ("items", "min_per_class"):
            value = policy.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise TasksetError(f"manifest split {split} {field} must be a nonnegative integer")
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
            raise TasksetError("manifest split test consulted must be a nonnegative integer")
    classes = manifest.get("classes", [])
    if not isinstance(classes, list) or len(set(classes)) != len(classes):
        raise TasksetError("manifest classes must be a list of unique values")
    if manifest["task"] == "classify_error_handling":
        classification = {"request_schema", "response_schema", "class_field", "classes"}
        missing = sorted(classification - manifest.keys())
        if missing:
            raise TasksetError(f"classification manifest missing required fields: {missing}")


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
    taskset_document, taskset_schema = resolve_schema_ref(repo_root, "contracts/taskset_v2.schema.json")
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
                input_specs[name] = {"path": stage["pin"], "sha256": stage.get("sha256")}
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
                values["observation"], observation_document, observation_schema, "observation"
            )
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
            "target": item.input_values["target"],
            "slice": item.input_values["slice"],
            "fault": observation["fault"],
            "observation": observed,
            "dependency_semantics": dependency,
        }
    except KeyError as exc:
        raise TasksetError(f"item {item.id} cannot assemble request; missing {exc.args[0]}") from exc
    errors = sorted(
        Draft202012Validator(request_schema).iter_errors(request),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise TasksetError(f"request schema validation failed at {location}: {first.message}")
    return request
