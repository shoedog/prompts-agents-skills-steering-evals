"""Locked append-only trend rows for structured evaluation runs."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

from harness.structured.results import canonical_json


def append_trend(path: Path, row: dict) -> None:
    """Append one canonical JSON line while holding an advisory file lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(row) + b"\n"
    with path.open("a+b") as output:
        fcntl.flock(output.fileno(), fcntl.LOCK_EX)
        try:
            output.seek(0, os.SEEK_END)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        finally:
            fcntl.flock(output.fileno(), fcntl.LOCK_UN)


def append_trend_once(path: Path, row: dict) -> bool:
    """Append unless this run/candidate identity already exists, under one lock."""
    identity_fields = ("experiment", "run_id", "version")
    if any(not isinstance(row.get(field), str) or not row[field] for field in identity_fields):
        raise ValueError(f"trend row needs nonempty identity fields: {identity_fields}")
    identity = tuple(row[field] for field in identity_fields)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(row) + b"\n"
    with path.open("a+b") as output:
        fcntl.flock(output.fileno(), fcntl.LOCK_EX)
        try:
            output.seek(0)
            for line in output.read().splitlines():
                existing = json.loads(line)
                if tuple(existing.get(field) for field in identity_fields) == identity:
                    return False
            output.seek(0, os.SEEK_END)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
            return True
        finally:
            fcntl.flock(output.fileno(), fcntl.LOCK_UN)


__all__ = ["append_trend", "append_trend_once"]
