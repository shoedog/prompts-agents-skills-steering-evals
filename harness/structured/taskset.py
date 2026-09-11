"""Public facade for structured taskset loading and request assembly."""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

from harness.structured.taskset_inputs import (
    _verify_hash as _verify_hash_impl,
    sha256_directory,
    sha256_file,
)
from harness.structured.taskset_loader import load_taskset
from harness.structured.taskset_request import assemble_request, target_for_observation
from harness.structured.taskset_types import InputRef, TaskItem, Taskset, TasksetError
from harness.structured.taskset_validation import resolve_schema_ref


def _verify_hash(ref: InputRef, *, ignore: Sequence[str]) -> bytes | None:
    """Compatibility seam for callers that patch hash verification."""
    return _verify_hash_impl(ref, ignore=ignore)


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


__all__ = [
    "InputRef",
    "TaskItem",
    "Taskset",
    "TasksetError",
    "assemble_request",
    "load_taskset",
    "resolve_schema_ref",
    "sha256_directory",
    "sha256_file",
    "target_for_observation",
    "verified_json",
]
