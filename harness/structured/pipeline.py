"""Pinned-prefix execution for one structured pipeline item."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, NotRequired, Protocol, Sequence, TypedDict

from jsonschema import Draft202012Validator

from harness.structured.results import ResultsWriter
from harness.structured.schema_ref import resolve_schema_ref
from harness.structured.taskset import TaskItem, TasksetError, verified_json


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIN_MODES = frozenset({"from_item", "never", "if_absent"})
_STAGE_TYPES = frozenset({"file", "prism", "harness", "llm"})
_HARNESS_UNAVAILABLE = "runtime harness stage not implemented"


class StageConfig(TypedDict):
    name: str
    type: Literal["file", "prism", "harness", "llm"]
    pin: Literal["from_item", "never", "if_absent"]
    task: NotRequired[str]


class VersionConfig(TypedDict):
    name: str
    task_version: str


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


def _schema(ref: str) -> dict[str, Any]:
    document, selected = resolve_schema_ref(_REPO_ROOT, ref)
    schema = dict(selected)
    if "$defs" in document and "$defs" not in schema:
        schema["$defs"] = document["$defs"]
    if "$schema" in document and "$schema" not in schema:
        schema["$schema"] = document["$schema"]
    return schema


_TARGET_DOCUMENT = _schema("contracts/targets.schema.json")
_TARGET = _schema("contracts/targets.schema.json#/$defs/target")
_OBSERVATION_DOCUMENT = _schema("contracts/observations.schema.json")
_OBSERVATION = _schema("contracts/observations.schema.json#/$defs/observation")
_CLASSIFICATION = _schema(
    "contracts/classify_error_handling.schema.json#/$defs/response"
)


def _validate_output(stage: StageConfig, value: dict[str, Any]) -> None:
    name = stage["name"]
    if name == "targets":
        schema = _TARGET_DOCUMENT if value.get("schema_version") == "1.0" else _TARGET
        label = "targets"
    elif name == "observation":
        schema = (
            _OBSERVATION_DOCUMENT
            if value.get("schema_version") == "1"
            else _OBSERVATION
        )
        label = "observation"
    elif name == "classify" or stage.get("task") == "classify_error_handling":
        schema = _CLASSIFICATION
        label = "classify"
    else:
        raise TasksetError(f"no output schema for pipeline stage {name!r}")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise TasksetError(
            f"{label} schema validation failed at {location}: {first.message}"
        )


def _stage_pin(item: TaskItem, name: str) -> tuple[dict[str, Any], bool]:
    raw_stages = item.raw.get("stages")
    if not isinstance(raw_stages, dict) or not isinstance(raw_stages.get(name), dict):
        raise TasksetError(f"item {item.id} has no stage declaration for {name}")
    declaration = raw_stages[name]
    return declaration, isinstance(declaration.get("pin"), str)


def _pinned(item: TaskItem, stage: StageConfig) -> dict[str, Any]:
    name = stage["name"]
    ref = item.inputs.get(name)
    if ref is None:
        raise TasksetError(f"item {item.id} has no pinned artifact for stage {name}")
    return verified_json(ref, ignore=item.raw.get("ignore", ()))


def _record_stage(
    *,
    writer: ResultsWriter,
    item: TaskItem,
    version: VersionConfig,
    stage: StageConfig,
    declaration: Mapping[str, Any],
    output: dict[str, Any],
    cache: str,
) -> dict[str, Any]:
    shared = declaration.get("shared") is True
    ref = writer.write_stage(
        version=version["name"],
        item_id=item.id,
        stage=stage["name"],
        value=output,
        sample=None if shared else 0,
        shared=shared,
    )
    return {
        "item_id": item.id,
        "version": version["name"],
        "stage": stage["name"],
        "type": stage["type"],
        "cache": cache,
        "status": "ok",
        "stage_ref": asdict(ref),
    }


def run_pipeline_item(
    item: TaskItem,
    version: VersionConfig,
    stages: Sequence[StageConfig],
    executors: ExecutorRegistry,
    writer: ResultsWriter,
) -> PipelineResult:
    """Run one item in stage order, replacing configured prefixes with pins."""
    if not isinstance(version.get("name"), str) or not version["name"]:
        raise TasksetError("pipeline version needs a nonempty name")
    replay: list[dict[str, Any]] = []
    outputs: dict[str, dict[str, Any]] = {}
    for stage in stages:
        name = stage.get("name")
        stage_type = stage.get("type")
        pin_mode = stage.get("pin")
        if not isinstance(name, str) or not name:
            raise TasksetError("pipeline stage needs a nonempty name")
        if stage_type not in _STAGE_TYPES:
            raise TasksetError(f"unknown pipeline stage type: {stage_type!r}")
        if pin_mode not in _PIN_MODES:
            raise TasksetError(f"unknown pipeline pin mode: {pin_mode!r}")
        declaration, has_pin = _stage_pin(item, name)
        use_pin = pin_mode == "from_item" or (pin_mode == "if_absent" and has_pin)
        if use_pin:
            if not has_pin:
                raise TasksetError(
                    f"item {item.id} has no pinned artifact for from_item stage {name}"
                )
            output = _pinned(item, stage)
            cache = "pinned"
        else:
            if stage_type == "file":
                raise TasksetError(f"file stage {name} requires a pinned artifact")
            if stage_type == "harness" and pin_mode == "never":
                raise TasksetError(_HARNESS_UNAVAILABLE)
            executor = executors.get(stage_type)
            if executor is None:
                if stage_type == "harness" and pin_mode == "if_absent":
                    replay.append(
                        {
                            "item_id": item.id,
                            "version": version["name"],
                            "stage": name,
                            "type": stage_type,
                            "cache": "miss",
                            "status": "error",
                            "error": _HARNESS_UNAVAILABLE,
                        }
                    )
                    return PipelineResult(tuple(replay), None, name)
                raise TasksetError(f"no executor registered for stage type {stage_type}")
            output = executor(
                stage=stage,
                item=item,
                version=version,
                inputs=dict(outputs),
                writer=writer,
            )
            if not isinstance(output, dict):
                raise TasksetError(f"pipeline stage {name} output must be one JSON object")
            cache = "miss"
        _validate_output(stage, output)
        outputs[name] = output
        replay.append(
            _record_stage(
                writer=writer,
                item=item,
                version=version,
                stage=stage,
                declaration=declaration,
                output=output,
                cache=cache,
            )
        )
    return PipelineResult(
        replay=tuple(replay),
        output=outputs[stages[-1]["name"]] if stages else None,
        stage_error=None,
    )


__all__ = [
    "ExecutorRegistry",
    "PipelineResult",
    "StageConfig",
    "StageExecutor",
    "VersionConfig",
    "run_pipeline_item",
]
