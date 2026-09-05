"""Authenticated results-tree orchestration for pipeline configs."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from harness.resultsdir import check_structured_stale_results_dir
from harness.structured.asserts import run_asserts
from harness.structured.config import PipelineConfig
from harness.structured.pipeline import VersionConfig, run_pipeline_item
from harness.structured.normalization import normalize_response
from harness.structured.pipeline_stages import (
    LlmStage,
    error_envelope,
    request_body,
    run_prism_stage,
)
from harness.structured.replay import LoadedRun
from harness.structured.report import render
from harness.structured.results import ResultsWriter, canonical_json, confined_run_dir
from harness.structured.runner import StaleRunError
from harness.structured.snapshots import write_input_snapshots
from harness.structured.taskset import load_taskset


@dataclass(frozen=True)
class PipelineRunResult:
    run_dir: Path
    metrics: dict[str, Any]
    promotion: None
    stage_errors: int


def _config_snapshot(cfg: PipelineConfig, task: str) -> dict[str, Any]:
    versions = []
    for version in cfg.versions:
        versions.append(
            {
                **deepcopy(version),
                "provider": {
                    "kind": "llm_layer",
                    "model": version.get("model", version["name"]),
                },
            }
        )
    return {
        "kind": "pipeline",
        "id": cfg.id,
        "task": task,
        "taskset": cfg.taskset.relative_to(cfg.root).as_posix(),
        "split": cfg.split,
        "stages": deepcopy(list(cfg.stages)),
        "versions": versions,
        "baseline_version": cfg.baseline_version,
        "samples_per_item": 1,
        "seed": cfg.seed,
        "jobs": cfg.jobs,
        "asserts": deepcopy(list(cfg.asserts)),
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "request_schema": deepcopy(cfg.request_schema),
        "response_schema": deepcopy(cfg.response_schema),
    }


def run_pipeline(
    cfg: PipelineConfig,
    *,
    clock: Any,
    force: bool,
    only: frozenset[str],
) -> PipelineRunResult:
    taskset = load_taskset(
        cfg.taskset, split=cfg.split, max_items=cfg.token_budget["max_items"]
    )
    by_id = {item.id: item for item in taskset.items}
    unknown = sorted(only - by_id.keys())
    if unknown:
        raise ValueError(f"unknown --only item: {unknown[0]}")
    items = tuple(by_id[item_id] for item_id in sorted(only or by_id))
    if not items:
        raise ValueError("pipeline run selected no items")
    llm_stage = next(stage for stage in cfg.stages if stage["type"] == "llm")
    config = _config_snapshot(cfg, llm_stage["task"])
    digest = hashlib.sha256(canonical_json(config) + b"\n").hexdigest()
    timestamp = datetime.fromisoformat(clock.now().replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("clock returned a non-UTC timestamp")
    compact = timestamp.strftime("%Y%m%dT%H%M%SZ")
    run_dir = confined_run_dir(cfg.root, cfg.id, f"{compact}-{digest[:8]}")
    if not check_structured_stale_results_dir(run_dir, force=force):
        raise StaleRunError(f"stale structured results: {run_dir}")
    writer = ResultsWriter(run_dir)
    calls: list[dict[str, Any]] = []
    requests: dict[tuple[str, int], dict[str, Any]] = {}
    item_snapshots: dict[str, dict[str, Any]] = {}
    total_cost = 0.0
    response_validator = Draft202012Validator(cfg.response_schema)
    with tempfile.TemporaryDirectory(prefix="pipeline-run-", dir=cfg.root) as temporary:
        for item in items:
            snapshot = deepcopy(item.raw)
            snapshot["expected"] = deepcopy(item.expected.get("classify", item.expected))
            item_snapshots[item.id] = snapshot
            versioned_requests: dict[str, Any] = {}
            for raw_version in cfg.versions:
                version: VersionConfig = {
                    **deepcopy(raw_version),
                    "seed": cfg.seed,
                }
                started_at = clock.now()
                started = time.monotonic()
                llm = LlmStage(Path(temporary))
                result = run_pipeline_item(
                    item,
                    version,
                    cfg.stages,
                    {"llm": llm, "prism": run_prism_stage},
                    writer,
                )
                request = llm.request or request_body(
                    item=item, version=version, inputs=item.input_values
                )
                versioned_requests[version["name"]] = request
                envelope = llm.envelope or error_envelope(version, request)
                normalized = normalize_response(envelope, response_validator)
                duration_ms = max(0, round((time.monotonic() - started) * 1000))
                call: dict[str, Any] = {
                    "item_id": item.id,
                    "version": version["name"],
                    "sample": 0,
                    "started_at": started_at,
                    "duration_ms": duration_ms,
                    "cost_usd": envelope["cost_usd"],
                    "cache": "miss",
                    "input_sha256": {
                        name: ref.sha256 for name, ref in sorted(item.inputs.items())
                    },
                    "final_document_valid": normalized.final_document_valid,
                    "sentinel_kind": normalized.sentinel_kind,
                    "raw": normalized.raw,
                    "output": normalized.output,
                    "replay_key": f"{version['name']}/{item.id}/s0",
                    "llm_envelope": envelope,
                }
                if result.stage_error is not None:
                    call["stage_error"] = result.stage_error
                    call["stage_error_detail"] = {
                        "message": result.replay[-1]["error"]
                    }
                elif result.replay:
                    call["stage_ref"] = result.replay[-1]["stage_ref"]
                writer.write_json_once(
                    PurePosixPath("calls", f"{version['name']}-{item.id}-0.json"), call
                )
                for row in result.replay:
                    replay_row = {**row, "sample": row.get("sample", 0)}
                    if row["stage"] == llm_stage["name"]:
                        replay_row.update(
                            {
                                "provider": envelope["provider"],
                                "provider_version": envelope["provider_version"],
                                "model": envelope["model"],
                                "task_version": envelope["task_version"],
                                "prompt_sha256": envelope["prompt_sha256"],
                                "seed": cfg.seed,
                                "cost_usd": envelope["cost_usd"],
                                "replay_key": call["replay_key"],
                            }
                        )
                    writer.append_event("replay", replay_row)
                    writer.append_event(
                        "trace",
                        {
                            "item_id": item.id,
                            "version": version["name"],
                            "sample": replay_row["sample"],
                            "stage": row["stage"],
                            "status": row["status"],
                            "started_at": started_at,
                            "duration_ms": duration_ms,
                        },
                    )
                calls.append(call)
                total_cost += float(envelope["cost_usd"])
                if total_cost > float(cfg.token_budget["max_cost_usd"]):
                    raise RuntimeError("pipeline token budget exceeded")
            requests[(item.id, 0)] = versioned_requests

    write_input_snapshots(
        writer,
        config=config,
        manifest=taskset.manifest,
        items=item_snapshots,
        requests=requests,
    )
    for call in calls:
        relative = PurePosixPath(
            "asserts", f"{call['version']}-{call['item_id']}-{call['sample']}.json"
        )
        if call.get("stage_error"):
            record = {
                "item_id": call["item_id"],
                "version": call["version"],
                "sample": call["sample"],
                "stage_error": call["stage_error"],
                "asserts": [],
            }
        else:
            assertions = run_asserts(
                output=call["output"],
                raw=call["raw"],
                expected=item_snapshots[call["item_id"]]["expected"],
                item=item_snapshots[call["item_id"]],
                cfg={**config, "classes": list(taskset.classes)},
                samples=[call],
            )
            record = {
                "item_id": call["item_id"],
                "version": call["version"],
                "sample": call["sample"],
                "asserts": [asdict(assertion) for assertion in assertions],
            }
        writer.write_json_once(relative, record)
    summary = render(LoadedRun.load(run_dir))
    metrics = json.loads((run_dir / "metrics.json").read_bytes())
    del summary
    return PipelineRunResult(
        run_dir=run_dir,
        metrics=metrics,
        promotion=None,
        stage_errors=sum(bool(call.get("stage_error")) for call in calls),
    )


__all__ = ["PipelineRunResult", "run_pipeline"]
