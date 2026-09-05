from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from harness.structured.pipeline import (
    PipelineResult,
    run_pipeline_item,
)
from harness.structured.results import ResultsWriter
from harness.structured.taskset import InputRef, TaskItem, TasksetError


TARGET_ID = "1" * 64


def _target() -> dict[str, Any]:
    return {
        "id": TARGET_ID,
        "site": {"file": "svc/client.py", "line": 44, "symbol": "fetch"},
        "kind": "external_call",
        "category": "missing_error_handling",
        "expected": {"property": "error_handled"},
        "source_algorithm": "absence",
        "confidence": "exact",
        "tier": "asserted",
        "severity": "warning",
        "description": "transient failure is not retried",
        "parse_quality": "clean",
    }


def _observation() -> dict[str, Any]:
    return {
        "target_id": TARGET_ID,
        "site": {"file": "svc/client.py", "line": 44, "symbol": "fetch"},
        "reached": True,
        "fault": {
            "catalog_id": "http.timeout",
            "kind": "http",
            "name": "TimeoutError",
            "retryable": True,
            "fatal": False,
        },
        "observed": {
            "outcome": "propagated",
            "duration_ms": 8,
            "test": {"id": "test_fetch", "status": "passed"},
        },
        "log_excerpt": "TimeoutError propagated",
    }


def _classification() -> dict[str, Any]:
    return {
        "class": "no_retry_on_transient",
        "confidence": 0.9,
        "rationale": "The retryable timeout propagated without a retry.",
        "evidence_lines": [44],
    }


def _write_pin(root: Path, name: str, value: dict[str, Any]) -> InputRef:
    path = root / f"{name}.json"
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(payload)
    return InputRef(name=name, path=path, sha256=hashlib.sha256(payload).hexdigest())


class RecordingExecutors(dict):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str]] = []

    def add(self, stage_type: str, output: dict[str, Any]) -> None:
        def execute(*, stage, item, version, inputs, writer):
            del item, version, inputs, writer
            self.calls.append((stage_type, stage["name"]))
            return output

        self[stage_type] = execute


class PipelineFixture(dict):
    def __init__(self, root: Path) -> None:
        self.root = root
        target = _write_pin(root, "targets", _target())
        observation = _write_pin(root, "observation", _observation())
        raw = {
            "id": "plx-py-0001",
            "task": "eh_pipeline",
            "language": "python",
            "source": "synthetic",
            "split": "dev",
            "contamination_risk": "low",
            "stages": {
                "targets": {"pin": target.path.name, "sha256": target.sha256, "shared": True},
                "observation": {
                    "pin": observation.path.name,
                    "sha256": observation.sha256,
                    "shared": True,
                },
                "classify": {"pin": None},
            },
            "expected": {"classify": {"label": "no_retry_on_transient"}},
        }
        item = TaskItem(
            id=raw["id"],
            task=raw["task"],
            split=raw["split"],
            expected=raw["expected"],
            inputs={"targets": target, "observation": observation},
            input_values={"targets": _target(), "observation": _observation()},
            raw=raw,
        )
        super().__init__(
            item=item,
            version={"name": "v1", "task_version": "2026-09-04.1"},
            stages=(
                {"name": "targets", "type": "prism", "pin": "from_item"},
                {"name": "observation", "type": "harness", "pin": "from_item"},
                {
                    "name": "classify",
                    "type": "llm",
                    "pin": "never",
                    "task": "classify_error_handling",
                },
            ),
            writer=ResultsWriter(root / "results"),
        )

    def __call__(self, *, pin: str, artifact: bool) -> dict[str, Any]:
        item = self["item"]
        raw = dict(item.raw)
        raw["stages"] = dict(item.raw["stages"])
        raw["stages"]["observation"] = {
            "pin": item.inputs["observation"].path.name if artifact else None,
            **({"sha256": item.inputs["observation"].sha256} if artifact else {}),
        }
        selected = TaskItem(
            id=item.id,
            task=item.task,
            split=item.split,
            expected=item.expected,
            inputs={"observation": item.inputs["observation"]} if artifact else {},
            input_values={"observation": _observation()} if artifact else {},
            raw=raw,
        )
        return {
            "item": selected,
            "version": self["version"],
            "stages": ({"name": "observation", "type": "harness", "pin": pin},),
            "writer": ResultsWriter(self.root / f"results-{pin}-{artifact}"),
        }


@pytest.fixture
def pipeline_fixture(tmp_path) -> PipelineFixture:
    return PipelineFixture(tmp_path)


@pytest.fixture
def recording_executors() -> RecordingExecutors:
    executors = RecordingExecutors()
    executors.add("harness", _observation())
    executors.add("llm", _classification())
    return executors


def executed_stages(pipeline: dict[str, Any], executors: RecordingExecutors) -> list[str]:
    executors.calls.clear()
    run_pipeline_item(**pipeline, executors=executors)
    return [stage for _stage_type, stage in executors.calls]


def mutate_pin(pipeline: dict[str, Any], stage: str) -> None:
    pipeline["item"].inputs[stage].path.write_text("{}")


def test_pinned_prefix_executes_only_classify(pipeline_fixture, recording_executors):
    result = run_pipeline_item(**pipeline_fixture, executors=recording_executors)
    assert recording_executors.calls == [("llm", "classify")]
    assert [row["stage"] for row in result.replay] == ["targets", "observation", "classify"]
    assert [row["cache"] for row in result.replay[:2]] == ["pinned", "pinned"]
    assert result.output == _classification()


def test_if_absent_executes_only_without_pin(pipeline_fixture, recording_executors):
    assert executed_stages(pipeline_fixture(pin="if_absent", artifact=True), recording_executors) == []
    assert executed_stages(pipeline_fixture(pin="if_absent", artifact=False), recording_executors) == [
        "observation"
    ]


def test_mutated_pinned_artifact_fails_before_downstream_execution(
    pipeline_fixture, recording_executors
):
    mutate_pin(pipeline_fixture, "targets")
    with pytest.raises(TasksetError, match="sha256 mismatch"):
        run_pipeline_item(**pipeline_fixture, executors=recording_executors)
    assert recording_executors.calls == []


def test_runtime_harness_never_is_the_exact_unimplemented_error(
    pipeline_fixture, recording_executors
):
    pipeline = pipeline_fixture(pin="never", artifact=False)
    with pytest.raises(TasksetError, match="^runtime harness stage not implemented$"):
        run_pipeline_item(**pipeline, executors=recording_executors)


def test_if_absent_without_registered_harness_records_stage_error(pipeline_fixture):
    result = run_pipeline_item(
        **pipeline_fixture(pin="if_absent", artifact=False), executors={}
    )
    assert result == PipelineResult(
        replay=(
            {
                "item_id": "plx-py-0001",
                "version": "v1",
                "stage": "observation",
                "type": "harness",
                "cache": "miss",
                "status": "error",
                "error": "runtime harness stage not implemented",
            },
        ),
        output=None,
        stage_error="observation",
    )


def test_invalid_stage_output_is_rejected_before_the_next_executor(
    pipeline_fixture, recording_executors
):
    recording_executors.add("harness", {"reached": True})
    pipeline = pipeline_fixture(pin="if_absent", artifact=False)
    pipeline["stages"] = (
        *pipeline["stages"],
        {"name": "classify", "type": "llm", "pin": "never"},
    )
    with pytest.raises(TasksetError, match="observation schema validation failed"):
        run_pipeline_item(**pipeline, executors=recording_executors)
    assert recording_executors.calls == [("harness", "observation")]


def test_file_stage_reads_and_validates_its_item_pin(pipeline_fixture):
    pipeline_fixture["stages"] = (
        {"name": "targets", "type": "file", "pin": "from_item"},
    )
    result = run_pipeline_item(**pipeline_fixture, executors={})
    assert result.output == _target()
    assert result.replay[0]["cache"] == "pinned"


def test_unpinned_prism_stage_uses_only_the_registered_prism_executor(
    pipeline_fixture, recording_executors
):
    recording_executors.add("prism", _target())
    item = pipeline_fixture["item"]
    raw = dict(item.raw)
    raw["stages"] = {**item.raw["stages"], "targets": {"pin": None}}
    pipeline_fixture["item"] = TaskItem(
        id=item.id,
        task=item.task,
        split=item.split,
        expected=item.expected,
        inputs={},
        input_values={},
        raw=raw,
    )
    pipeline_fixture["stages"] = (
        {"name": "targets", "type": "prism", "pin": "never"},
    )
    result = run_pipeline_item(**pipeline_fixture, executors=recording_executors)
    assert recording_executors.calls == [("prism", "targets")]
    assert result.output == _target()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (("type", "unknown", "unknown pipeline stage type"),
     ("pin", "sometimes", "unknown pipeline pin mode")),
)
def test_pipeline_rejects_unknown_stage_policy(
    pipeline_fixture, recording_executors, field, value, message
):
    stage = {"name": "targets", "type": "file", "pin": "from_item"}
    stage[field] = value
    pipeline_fixture["stages"] = (stage,)
    with pytest.raises(TasksetError, match=message):
        run_pipeline_item(**pipeline_fixture, executors=recording_executors)
