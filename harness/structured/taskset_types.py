"""Shared taskset data types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


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


__all__ = ["InputRef", "TaskItem", "Taskset", "TasksetError"]
