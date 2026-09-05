"""Hash-first loading and zero-executor replay of structured results trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from jsonschema import Draft202012Validator

from harness.structured.results import canonical_json
from harness.structured.snapshots import InputEntry, InputIndex


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_HEADER_KEYS = {"inputs_index_path", "inputs_index_sha256"}


class ReplayInputError(ValueError):
    """The supplied results tree cannot authenticate its replay inputs."""


@dataclass(frozen=True)
class LoadedRun:
    path: Path
    run_header: dict[str, Any]
    config: dict[str, Any]
    manifest: dict[str, Any]
    items: dict[str, dict[str, Any]]
    requests: dict[tuple[str, int], dict[str, Any]]
    calls: tuple[dict[str, Any], ...]
    stages: tuple[dict[str, Any], ...]
    asserts: tuple[dict[str, Any], ...]
    input_index: InputIndex

    @classmethod
    def load(cls, path: Path) -> LoadedRun:
        return _load_run(Path(path))


@dataclass(frozen=True)
class ReplayResult:
    executor_calls: Literal[0]
    metrics: dict[str, Any]


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayInputError(f"cannot parse {label}: {error}") from error
    if not isinstance(value, dict):
        raise ReplayInputError(f"{label} must contain one JSON object")
    return value


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReplayInputError(f"cannot read {label}: {path}: {error}") from error


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
            raise ReplayInputError(f"input index entry {number} path must be a string")
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
            raise ReplayInputError(f"cannot stat input snapshot {relative}: {error}") from error
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ReplayInputError(f"input snapshot is not a regular file: {relative}")
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
        entry.path: _json_object(payloads[entry.path], entry.path)
        for entry in entries
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
                raise ReplayInputError(f"request snapshot identity mismatch: {relative}")
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
            raise ReplayInputError("snapshot config version must have a nonempty name")
        versions.append(name)
    if len(set(versions)) != len(versions):
        raise ReplayInputError("snapshot config contains duplicate version names")
    sample_count = config.get("samples_per_item")
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count <= 0:
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
    validator = Draft202012Validator(request_schema) if isinstance(request_schema, dict) else None
    for key in sorted(requests):
        request = requests[key]
        versioned = request.get("versions")
        if not isinstance(versioned, dict) or set(versioned) != set(versions):
            raise ReplayInputError(f"request versions mismatch: {key[0]}-s{key[1]}")
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


def load_result_records(root: Path) -> dict[str, tuple[dict[str, Any], ...]]:
    """Load stored result records; callers invoke this only after input authentication."""
    loaded: dict[str, tuple[dict[str, Any], ...]] = {}
    for name in ("calls", "stages", "asserts"):
        directory = root / name
        records = []
        if directory.exists():
            for path in sorted(directory.glob("*.json")):
                records.append(_json_object(_read(path, f"result record {path}"), str(path)))
        loaded[name] = tuple(records)
    return loaded


def _load_run(root: Path) -> LoadedRun:
    header = _json_object(_read(root / "run.json", "run.json"), "run.json")
    relative_index_path, digest = _validate_run_header(header)
    index_path = root / relative_index_path
    index_bytes = _read(index_path, "inputs/index.json")
    actual_index_digest = hashlib.sha256(index_bytes).hexdigest()
    if actual_index_digest != digest:
        raise ReplayInputError(
            "inputs_index_sha256 mismatch: "
            f"expected {digest}, got {actual_index_digest}"
        )
    index_value = _json_object(index_bytes, "inputs/index.json")
    if index_bytes != canonical_json(index_value):
        raise ReplayInputError("input index is not canonical JSON")
    entries = _validate_index(index_value)
    listed = {entry.path for entry in entries}
    actual = _regular_input_files(root / "inputs") - {"inputs/index.json"}
    missing = sorted(listed - actual)
    if missing:
        raise ReplayInputError(f"missing input snapshot: {missing[0]}")
    unlisted = sorted(actual - listed)
    if unlisted:
        raise ReplayInputError(f"unlisted input snapshot: {unlisted[0]}")
    authenticated_payloads: dict[str, bytes] = {}
    for entry in entries:
        payload = _read(root / entry.path, entry.path)
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != entry.sha256:
            raise ReplayInputError(
                f"sha256 mismatch for {entry.path}: expected {entry.sha256}, got {actual_digest}"
            )
        authenticated_payloads[entry.path] = payload
    config, manifest, items, requests = _snapshot_objects(authenticated_payloads, entries)
    records = load_result_records(root)
    return LoadedRun(
        path=root,
        run_header=header,
        config=config,
        manifest=manifest,
        items=items,
        requests=requests,
        calls=records["calls"],
        stages=records["stages"],
        asserts=records["asserts"],
        input_index=InputIndex(entries=entries, sha256=digest),
    )


def replay(results_dir: Path) -> ReplayResult:
    """Authenticate a supplied tree and deterministically rewrite its reductions."""
    from harness.structured.report import render

    run = LoadedRun.load(results_dir)
    summary = render(run)
    metrics = {
        key: value
        for key, value in summary.items()
        if key not in {"calls", "scored_rows", "worst_rows"}
    }
    json_metrics = json.loads(canonical_json(metrics))
    return ReplayResult(executor_calls=0, metrics=json_metrics)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Authenticate and replay a structured evaluation results tree"
    )
    parser.add_argument("results_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = replay(args.results_dir)
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        print(f"[structured replay] ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result.metrics, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LoadedRun",
    "ReplayInputError",
    "ReplayResult",
    "build_parser",
    "load_result_records",
    "main",
    "replay",
]
