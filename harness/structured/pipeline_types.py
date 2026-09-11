"""Shared pipeline execution types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, NotRequired, Protocol, TypedDict

from harness.structured.results import ResultsWriter
from harness.structured.taskset import TaskItem


class StageConfig(TypedDict):
    name: str
    type: Literal["file", "prism", "harness", "llm"]
    pin: Literal["from_item", "never", "if_absent"]
    task: NotRequired[str]
    algorithm: NotRequired[str]


class VersionConfig(TypedDict):
    name: str
    task_version: str
    stage: NotRequired[str]
    model: NotRequired[str]
    seed: NotRequired[int]


class StageExecutor(Protocol):
    def __call__(
        self,
        *,
        stage: StageConfig,
        item: TaskItem,
        version: VersionConfig,
        inputs: Mapping[str, dict[str, Any]],
        writer: ResultsWriter,
    ) -> dict[str, Any]: ...


ExecutorRegistry = Mapping[str, StageExecutor]


@dataclass(frozen=True)
class PipelineResult:
    replay: tuple[dict[str, Any], ...]
    output: dict[str, Any] | None
    stage_error: str | None


__all__ = [
    "ExecutorRegistry",
    "PipelineResult",
    "StageConfig",
    "StageExecutor",
    "VersionConfig",
]
