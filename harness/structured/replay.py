"""Hash-first loading and zero-executor replay of structured results trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from harness.structured.replay_inputs import (
    ReplayInputError,
    _regular_input_files,
    _snapshot_objects,
    _validate_index,
    _validate_run_header,
)
from harness.structured.results import canonical_json
from harness.structured.snapshots import InputIndex


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
    run = LoadedRun.load(results_dir)
    if run.config.get("kind") == "analyzer":
        from harness.structured.analyzer_report import render_analyzer

        metrics = render_analyzer(run)
    else:
        from harness.structured.report import render

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
