"""Authenticated taskset input loading and hashing."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

import yaml

from harness.structured.taskset_types import InputRef, TasksetError


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


__all__ = ["sha256_directory", "sha256_file", "verified_json"]
