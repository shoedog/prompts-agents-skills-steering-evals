"""Assertion records and final-tree integrity checks."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

from harness.structured.assertion_context import assertion_context
from harness.structured.asserts import run_asserts
from harness.structured.replay import LoadedRun
from harness.structured.results import ResultsWriter, StageRef
from harness.structured.runner_types import IntegrityError
from harness.structured.taskset import TaskItem, sha256_file

def _write_assert_records(
    writer: ResultsWriter,
    *,
    calls: list[dict[str, Any]],
    items: Mapping[str, dict[str, Any]],
    config: dict[str, Any],
    classes: tuple[str, ...],
) -> None:
    for version in [entry["name"] for entry in config["versions"]]:
        for call in [row for row in calls if row["version"] == version]:
            relative = PurePosixPath(
                "asserts", f"{version}-{call['item_id']}-{call['sample']}.json"
            )
            context = assertion_context(
                calls, version=version, item_id=call["item_id"]
            )
            if context is None:
                writer.write_json_once(
                    relative,
                    {
                        "item_id": call["item_id"],
                        "version": version,
                        "sample": call["sample"],
                        "stage_error": call.get("stage_error", "excluded_by_stage_error"),
                        "asserts": [],
                    },
                )
                continue
            item_samples, populations = context
            results = run_asserts(
                output=call["output"],
                raw=call["raw"],
                expected=items[call["item_id"]]["expected"],
                item=items[call["item_id"]],
                cfg={**config, "classes": list(classes)},
                samples=item_samples,
                populations=populations,
            )
            writer.write_json_once(
                relative,
                {
                    "item_id": call["item_id"],
                    "version": version,
                    "sample": call["sample"],
                    "asserts": [asdict(result) for result in results],
                },
            )


def _shared_refs(
    writer: ResultsWriter, items: tuple[TaskItem, ...], versions: tuple[dict[str, Any], ...]
) -> dict[tuple[str, str], StageRef]:
    refs: dict[tuple[str, str], StageRef] = {}
    for version in versions:
        for item in items:
            stages = item.raw.get("stages", {})
            if not isinstance(stages, dict):
                continue
            shared = [
                (name, stage)
                for name, stage in sorted(stages.items())
                if isinstance(stage, dict) and stage.get("shared") is True
            ]
            if len(shared) > 1:
                raise ValueError(f"item {item.id} has multiple shared dependency stages")
            for name, stage in shared:
                value = item.input_values.get(name, {"pin": stage.get("pin")})
                refs[(version["name"], item.id)] = writer.write_stage(
                    version=version["name"],
                    item_id=item.id,
                    stage=name,
                    value={"item_id": item.id, "version": version["name"], "stage": name, "output": value},
                    sample=None,
                    shared=True,
                )
    return refs


def _verify_final_tree(
    run_dir: Path,
    *,
    loaded: LoadedRun,
    versions: tuple[str, ...],
    items: tuple[str, ...],
    samples: int,
    shared_refs: Mapping[tuple[str, str], StageRef],
) -> None:
    expected = {
        (version, item, sample)
        for version in versions
        for item in items
        for sample in range(samples)
    }
    for directory in ("calls", "asserts"):
        actual = set()
        for path in (run_dir / directory).glob("*.json"):
            value = json.loads(path.read_bytes())
            actual.add((value.get("version"), value.get("item_id"), value.get("sample")))
        if actual != expected:
            raise IntegrityError(
                f"{directory} identity mismatch: missing={sorted(expected - actual)}, "
                f"extra={sorted(actual - expected)}"
            )
    for ref in shared_refs.values():
        if sha256_file(run_dir / ref.path) != ref.sha256:
            raise IntegrityError(f"shared stage digest mismatch: {ref.path}")
    expected_stages = {
        (version, item, sample, "classify")
        for version, item, sample in expected
    }
    expected_stages.update(
        (
            version,
            item,
            None,
            Path(ref.path).stem.removeprefix(f"{version}-{item}-"),
        )
        for (version, item), ref in shared_refs.items()
    )
    actual_stages = {
        (
            stage.get("version"),
            stage.get("item_id"),
            stage.get("sample"),
            stage.get("stage"),
        )
        for stage in loaded.stages
    }
    if actual_stages != expected_stages:
        raise IntegrityError(
            "stage identity mismatch: "
            f"missing={sorted(expected_stages - actual_stages, key=repr)}, "
            f"extra={sorted(actual_stages - expected_stages, key=repr)}"
        )
    for name in ("replay.jsonl", "trace.jsonl", "metrics.json", "report.md"):
        if not (run_dir / name).is_file():
            raise IntegrityError(f"missing final result artifact: {name}")
    for name in ("replay", "trace"):
        rows = [
            json.loads(line)
            for line in (run_dir / f"{name}.jsonl").read_text().splitlines()
        ]
        keys = [(row.get("version"), row.get("item_id"), row.get("sample")) for row in rows]
        if keys != sorted(expected):
            raise IntegrityError(f"{name}.jsonl identity order mismatch: {keys}")
