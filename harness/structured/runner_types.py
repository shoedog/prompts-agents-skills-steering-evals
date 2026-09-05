"""Shared types and identifiers for structured runners."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from harness.structured.executors import Executor
from harness.structured.promotion import PromotionVerdict
from harness.structured.results import StageRef
from harness.structured.taskset import TaskItem

_TIMESTAMP = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")
_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

class Clock(Protocol):
    def now(self) -> str: ...

    def monotonic(self) -> float: ...


class ExecutorFactory(Protocol):
    def __call__(self, version: dict[str, Any]) -> Executor: ...


class SystemClock:
    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def monotonic(self) -> float:
        return time.monotonic()


class StaleRunError(RuntimeError):
    pass


class IntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    metrics: dict
    promotion: PromotionVerdict | None
    stage_errors: int


@dataclass(frozen=True)
class _Work:
    version: dict[str, Any]
    item: TaskItem
    sample: int
    seed: int
    request: dict[str, Any]
    request_file: Path
    input_sha256: dict[str, str]
    shared_ref: StageRef | None


@dataclass(frozen=True)
class _Completed:
    key: tuple[str, str, int]
    call: dict[str, Any]
    replay: dict[str, Any]
    trace: dict[str, Any]


def _timestamp_parts(value: str) -> tuple[str, str]:
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        raise ValueError(f"clock returned a non-UTC-second timestamp: {value!r}")
    year, month, day, hour, minute, second = match.groups()
    return value, f"{year}{month}{day}T{hour}{minute}{second}Z"


def _safe_component(value: object, field: str) -> str:
    if not isinstance(value, str) or _COMPONENT.fullmatch(value) is None:
        raise ValueError(f"{field} must be one safe nonempty path component")
    return value
