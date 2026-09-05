"""Immutable, content-authenticated input snapshots for standalone replay."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from harness.structured.results import ResultsWriter, canonical_json


_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class InputEntry:
    path: str
    sha256: str


@dataclass(frozen=True)
class InputIndex:
    entries: tuple[InputEntry, ...]
    sha256: str


def _component(value: object, field: str) -> str:
    if not isinstance(value, str) or _COMPONENT.fullmatch(value) is None:
        raise ValueError(f"{field} must be one safe nonempty path component")
    return value


def _write_index_once(path: Path, payload: bytes) -> None:
    """Link exact index bytes into place without a replace window or newline."""
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
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise RuntimeError(f"input index already exists: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def _version_names(config: Mapping[str, Any]) -> tuple[str, ...]:
    raw = config.get("versions")
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("config.versions must be a nonempty sequence")
    names = tuple(
        _component(version.get("name") if isinstance(version, Mapping) else None, "version name")
        for version in raw
    )
    if len(set(names)) != len(names):
        raise ValueError("config.versions contains duplicate names")
    return names


def _samples_per_item(config: Mapping[str, Any]) -> int:
    value = config.get("samples_per_item")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("config.samples_per_item must be a positive integer")
    return value


def write_input_snapshots(
    writer: ResultsWriter,
    *,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    items: Mapping[str, Mapping[str, Any]],
    requests: Mapping[tuple[str, int], Mapping[str, Any]],
) -> InputIndex:
    """Write the closed EVAL-4 snapshot tree, its index, and its root digest."""
    if not all(isinstance(value, Mapping) for value in (config, manifest, items, requests)):
        raise TypeError("snapshot inputs must be mappings")
    versions = _version_names(config)
    sample_count = _samples_per_item(config)
    item_ids = tuple(sorted(_component(item_id, "item id") for item_id in items))
    if not item_ids:
        raise ValueError("items must not be empty")
    for item_id in item_ids:
        if items[item_id].get("id") != item_id:
            raise ValueError(f"item snapshot id mismatch: {item_id}")

    expected_request_keys = {
        (item_id, sample) for item_id in item_ids for sample in range(sample_count)
    }
    if set(requests) != expected_request_keys:
        missing = sorted(expected_request_keys - set(requests))
        extra = sorted(set(requests) - expected_request_keys)
        raise ValueError(f"request snapshot keys mismatch: missing={missing}, extra={extra}")

    schema = config.get("request_schema")
    validator = Draft202012Validator(schema) if isinstance(schema, Mapping) else None
    snapshots: list[tuple[PurePosixPath, Mapping[str, Any]]] = [
        (PurePosixPath("inputs/config.json"), config),
        (PurePosixPath("inputs/manifest.json"), manifest),
    ]
    snapshots.extend(
        (PurePosixPath("inputs", "items", f"{item_id}.json"), items[item_id])
        for item_id in item_ids
    )
    for item_id, sample in sorted(requests):
        supplied = requests[(item_id, sample)]
        if set(supplied) != set(versions):
            raise ValueError(
                f"request versions mismatch for {item_id} sample {sample}: "
                f"expected {sorted(versions)}, got {sorted(supplied)}"
            )
        versioned: dict[str, Any] = {}
        for version in sorted(versions):
            body = supplied[version]
            if not isinstance(body, Mapping):
                raise ValueError(f"request body for {version}/{item_id}/s{sample} must be an object")
            if validator is not None:
                errors = sorted(
                    validator.iter_errors(body),
                    key=lambda error: [str(part) for part in error.absolute_path],
                )
                if errors:
                    location = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
                    raise ValueError(
                        f"request schema failure for {version}/{item_id}/s{sample} "
                        f"at {location}: {errors[0].message}"
                    )
            versioned[version] = body
        snapshots.append(
            (
                PurePosixPath("inputs", "requests", f"{item_id}-s{sample}.json"),
                {"item_id": item_id, "sample": sample, "versions": versioned},
            )
        )

    entries: list[InputEntry] = []
    for relative, value in sorted(snapshots, key=lambda row: row[0].as_posix()):
        destination = writer.write_json_once(relative, value)
        entries.append(
            InputEntry(
                path=relative.as_posix(),
                sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
            )
        )
    index_value = {
        "entries": [
            {"path": entry.path, "sha256": entry.sha256}
            for entry in sorted(entries, key=lambda entry: entry.path)
        ]
    }
    index_bytes = canonical_json(index_value)
    digest = hashlib.sha256(index_bytes).hexdigest()
    _write_index_once(writer.root / "inputs/index.json", index_bytes)
    writer.write_json_once(
        PurePosixPath("run.json"),
        {
            "inputs_index_path": "inputs/index.json",
            "inputs_index_sha256": digest,
        },
    )
    return InputIndex(
        entries=tuple(sorted(entries, key=lambda entry: entry.path)),
        sha256=digest,
    )
