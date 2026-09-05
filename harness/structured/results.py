"""Atomic, collision-refusing storage for structured evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from harness.tracing import trace_call


class ResultCollisionError(RuntimeError):
    """A run attempted to replace an immutable structured result artifact."""


def confined_run_dir(root: Path, experiment_id: str, run_id: str) -> Path:
    """Resolve a run below ``results/`` before any stale-file handling."""
    results_root = (Path(root) / "results").resolve(strict=False)
    run_dir = results_root / experiment_id / run_id
    resolved = run_dir.resolve(strict=False)
    try:
        resolved.relative_to(results_root)
    except ValueError as error:
        raise ValueError(f"structured run directory escapes results/: {run_dir}") from error
    return run_dir


@dataclass(frozen=True)
class StageRef:
    path: str
    sha256: str


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def _write_temporary(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def write_json_atomic(path: Path, value: Any) -> None:
    payload = canonical_json(value) + b"\n"
    path = Path(path)
    temporary = _write_temporary(path, payload)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ResultsWriter:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._resolved_root = self.root.resolve(strict=False)
        self._event_lock = threading.Lock()

    def _destination(self, relative_path: PurePosixPath) -> Path:
        if (
            not isinstance(relative_path, PurePosixPath)
            or relative_path.is_absolute()
            or str(relative_path) == "."
            or ".." in relative_path.parts
        ):
            raise ValueError(f"expected a non-empty relative artifact path: {relative_path!s}")
        destination = self.root.joinpath(*relative_path.parts)
        resolved = destination.resolve(strict=False)
        try:
            resolved.relative_to(self._resolved_root)
        except ValueError as error:
            raise ValueError(
                f"artifact destination is outside results root: {relative_path!s}"
            ) from error
        return destination

    def write_json(self, relative_path: PurePosixPath, value: Any) -> Path:
        destination = self._destination(relative_path)
        write_json_atomic(destination, value)
        return destination

    def write_json_once(self, relative_path: PurePosixPath, value: Any) -> Path:
        destination = self._destination(relative_path)
        payload = canonical_json(value) + b"\n"
        temporary = _write_temporary(destination, payload)
        try:
            try:
                os.link(temporary, destination)
            except FileExistsError as error:
                raise ResultCollisionError(
                    f"structured result already exists: {relative_path.as_posix()}"
                ) from error
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def write_stage(
        self,
        *,
        version: str,
        item_id: str,
        stage: str,
        value: Any,
        sample: int | None,
        shared: bool,
    ) -> StageRef:
        for field, component in (
            ("version", version),
            ("item_id", item_id),
            ("stage", stage),
        ):
            if not component or component in {".", ".."} or "/" in component:
                raise ValueError(f"{field} must be one non-empty path component")
        if shared:
            if sample is not None:
                raise ValueError("shared stages forbid a sample")
            filename = f"{version}-{item_id}-{stage}.json"
        else:
            if sample is None:
                raise ValueError("non-shared stages require a sample")
            filename = f"{version}-{item_id}-s{sample}-{stage}.json"
        relative_path = PurePosixPath("stages", filename)
        destination = self.write_json_once(relative_path, value)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return StageRef(path=relative_path.as_posix(), sha256=digest)

    def append_event(self, name: Literal["replay", "trace"], row: dict) -> None:
        if name not in {"replay", "trace"}:
            raise ValueError(f"unknown event name: {name}")
        payload = canonical_json(row) + b"\n"
        destination = self._destination(PurePosixPath(f"{name}.jsonl"))
        with self._event_lock:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("ab") as output:
                output.write(payload)
        if name == "trace":
            trace_call("structured", row, results_dir=None)
