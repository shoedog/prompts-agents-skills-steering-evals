"""Locked append-only trend rows for structured evaluation runs."""

from __future__ import annotations

import fcntl
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
