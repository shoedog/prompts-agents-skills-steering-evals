"""Validation of authenticated structured replay inputs."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from harness.structured.snapshots import InputEntry


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_HEADER_KEYS = {"inputs_index_path", "inputs_index_sha256"}


class ReplayInputError(ValueError):
    """The supplied results tree cannot authenticate its replay inputs."""


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayInputError(f"cannot parse {label}: {error}") from error
    if not isinstance(value, dict):
        raise ReplayInputError(f"{label} must contain one JSON object")
    return value


def _validate_run_header(header: dict[str, Any]) -> tuple[str, str]:
    unknown = sorted(set(header) - _RUN_HEADER_KEYS)
    if unknown:
        raise ReplayInputError(f"run.json unknown key: {unknown[0]}")
    missing = sorted(_RUN_HEADER_KEYS - set(header))
    if missing:
        raise ReplayInputError(f"run.json missing key: {missing[0]}")
    for key in sorted(_RUN_HEADER_KEYS):
        if not isinstance(header[key], str):
            raise ReplayInputError(f"run.json key {key} must be a string")
    index_path = header["inputs_index_path"]
    digest = header["inputs_index_sha256"]
    if index_path != "inputs/index.json":
        raise ReplayInputError("run.json inputs_index_path must be inputs/index.json")
    if _SHA256.fullmatch(digest) is None:
        raise ReplayInputError(
            "run.json inputs_index_sha256 must be 64 lowercase hex characters"
        )
    return index_path, digest


def _validate_index(value: dict[str, Any]) -> tuple[InputEntry, ...]:
    if set(value) != {"entries"} or not isinstance(value["entries"], list):
        raise ReplayInputError("input index must contain exactly one entries array")
    entries: list[InputEntry] = []
    seen: set[str] = set()
    for number, raw in enumerate(value["entries"]):
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256"}:
            raise ReplayInputError(f"invalid input index entry {number}")
        relative = raw["path"]
        digest = raw["sha256"]
        if not isinstance(relative, str):
            raise ReplayInputError(
                f"input index entry {number} path must be a string"
            )
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or not pure.parts
            or pure.parts[0] != "inputs"
            or relative == "inputs/index.json"
        ):
            raise ReplayInputError(f"unsafe input path: {relative}")
        if relative in seen:
            raise ReplayInputError(f"duplicate input path: {relative}")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ReplayInputError(f"invalid sha256 for input path: {relative}")
        seen.add(relative)
        entries.append(InputEntry(relative, digest))
    if entries != sorted(entries, key=lambda entry: entry.path):
        raise ReplayInputError("input index entries are not sorted by path")
    return tuple(entries)


def _regular_input_files(inputs_root: Path) -> set[str]:
    actual: set[str] = set()
    try:
        candidates = sorted(inputs_root.rglob("*"))
    except OSError as error:
        raise ReplayInputError(f"cannot walk inputs directory: {error}") from error
    for candidate in candidates:
        relative = candidate.relative_to(inputs_root.parent).as_posix()
        try:
            mode = candidate.lstat().st_mode
        except OSError as error:
            raise ReplayInputError(
                f"cannot stat input snapshot {relative}: {error}"
            ) from error
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ReplayInputError(
                f"input snapshot is not a regular file: {relative}"
            )
        actual.add(relative)
    return actual


def _snapshot_objects(
    payloads: dict[str, bytes], entries: tuple[InputEntry, ...]
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    values = {
        entry.path: _json_object(payloads[entry.path], entry.path) for entry in entries
    }
    required = {"inputs/config.json", "inputs/manifest.json"}
    missing = sorted(required - values.keys())
    if missing:
        raise ReplayInputError(f"missing required input snapshot: {missing[0]}")
    config = values.pop("inputs/config.json")
    manifest = values.pop("inputs/manifest.json")
    items: dict[str, dict[str, Any]] = {}
    requests: dict[tuple[str, int], dict[str, Any]] = {}
    for relative, value in values.items():
        pure = PurePosixPath(relative)
        if len(pure.parts) == 3 and pure.parts[:2] == ("inputs", "items"):
            item_id = pure.stem
            if value.get("id") != item_id:
                raise ReplayInputError(f"item snapshot id mismatch: {relative}")
            items[item_id] = value
            continue
        if len(pure.parts) == 3 and pure.parts[:2] == ("inputs", "requests"):
            item_id = value.get("item_id")
            sample = value.get("sample")
            if (
                not isinstance(item_id, str)
                or not isinstance(sample, int)
                or isinstance(sample, bool)
                or sample < 0
                or pure.name != f"{item_id}-s{sample}.json"
            ):
                raise ReplayInputError(
                    f"request snapshot identity mismatch: {relative}"
                )
            if set(value) != {"item_id", "sample", "versions"}:
                raise ReplayInputError(f"request snapshot is not closed: {relative}")
            requests[(item_id, sample)] = value
            continue
        raise ReplayInputError(f"unknown input snapshot path: {relative}")
    if not items:
        raise ReplayInputError("input snapshot tree contains no items")

    raw_versions = config.get("versions")
    if not isinstance(raw_versions, list) or not raw_versions:
        raise ReplayInputError("snapshot config versions must be a nonempty array")
    versions = []
    for value in raw_versions:
        name = value.get("name") if isinstance(value, dict) else None
        if not isinstance(name, str) or not name:
            raise ReplayInputError(
                "snapshot config version must have a nonempty name"
            )
        versions.append(name)
    if len(set(versions)) != len(versions):
        raise ReplayInputError("snapshot config contains duplicate version names")
    sample_count = config.get("samples_per_item")
    if (
        not isinstance(sample_count, int)
        or isinstance(sample_count, bool)
        or sample_count <= 0
    ):
        raise ReplayInputError("snapshot config samples_per_item must be positive")
    expected_requests = {
        (item_id, sample) for item_id in items for sample in range(sample_count)
    }
    missing_requests = sorted(expected_requests - requests.keys())
    extra_requests = sorted(requests.keys() - expected_requests)
    if missing_requests:
        item_id, sample = missing_requests[0]
        raise ReplayInputError(f"missing request snapshot: {item_id}-s{sample}")
    if extra_requests:
        item_id, sample = extra_requests[0]
        raise ReplayInputError(f"unexpected request snapshot: {item_id}-s{sample}")
    request_schema = config.get("request_schema")
    validator = (
        Draft202012Validator(request_schema)
        if isinstance(request_schema, dict)
        else None
    )
    for key in sorted(requests):
        request = requests[key]
        versioned = request.get("versions")
        if not isinstance(versioned, dict) or set(versioned) != set(versions):
            raise ReplayInputError(
                f"request versions mismatch: {key[0]}-s{key[1]}"
            )
        if validator is not None:
            for version in sorted(versions):
                errors = sorted(
                    validator.iter_errors(versioned[version]),
                    key=lambda error: [str(part) for part in error.absolute_path],
                )
                if errors:
                    raise ReplayInputError(
                        f"request schema failure: {version}/{key[0]}/s{key[1]}: "
                        f"{errors[0].message}"
                    )
    return config, manifest, items, requests


__all__ = ["ReplayInputError"]
