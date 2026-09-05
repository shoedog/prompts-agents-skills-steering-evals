"""Authenticated orchestration for analyzer evaluation runs."""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Any

from harness.providers.binpath import resolve_executable
from harness.resultsdir import check_structured_stale_results_dir
from harness.structured.analyzer_report import render_analyzer
from harness.structured.asserts import run_asserts
from harness.structured.config import AnalyzerConfig
from harness.structured.promotion import PromotionVerdict
from harness.structured.replay import LoadedRun
from harness.structured.results import ResultsWriter, canonical_json, confined_run_dir
from harness.structured.runner_cache import _duration_ms
from harness.structured.runner_config import (
    _analyzer_artifact_key,
    _analyzer_config_snapshot,
    _item_snapshot,
)
from harness.structured.runner_types import (
    Clock,
    IntegrityError,
    RunResult,
    StaleRunError,
    _timestamp_parts,
)
from harness.structured.snapshots import write_input_snapshots
from harness.structured.taskset import load_taskset

def run_analyzer(
    cfg: AnalyzerConfig,
    *,
    clock: Clock,
    force: bool,
    only: frozenset[str],
) -> RunResult:
    """Run an analyzer config through the authenticated structured results layout."""
    from harness.structured.analyzer import AnalyzerExecutorError, probe_flags, run_analyzer_item

    taskset = load_taskset(
        cfg.taskset, split=cfg.split, max_items=cfg.token_budget["max_items"]
    )
    by_id = {item.id: item for item in taskset.items}
    unknown = sorted(only - by_id.keys())
    if unknown:
        raise ValueError(f"unknown --only item: {unknown[0]}")
    items = tuple(by_id[item_id] for item_id in sorted(only or by_id.keys()))
    if not items:
        raise ValueError("analyzer run selected no items")
    pairs = tuple(
        (mode, item)
        for mode in cfg.modes
        for item in items
        if item.raw.get("language") == mode.language
    )
    if not pairs:
        raise ValueError("analyzer run selected no language-applicable items")

    config = _analyzer_config_snapshot(cfg, taskset.manifest["task"])
    config_digest = hashlib.sha256(canonical_json(config) + b"\n").hexdigest()
    _, compact = _timestamp_parts(clock.now())
    run_dir = confined_run_dir(cfg.root, cfg.id, f"{compact}-{config_digest[:8]}")
    if not check_structured_stale_results_dir(run_dir, force=force):
        raise StaleRunError(f"stale structured results: {run_dir}")
    writer = ResultsWriter(run_dir)
    item_snapshots = {item.id: _item_snapshot(item) for item in items}
    requests = {
        (item.id, 0): {
            mode.version: {
                "mode": asdict(mode),
                "input_sha256": {
                    name: ref.sha256 for name, ref in sorted(item.inputs.items())
                },
            }
            for mode in cfg.modes
        }
        for item in items
    }
    write_input_snapshots(
        writer,
        config=config,
        manifest=taskset.manifest,
        items=item_snapshots,
        requests=requests,
    )

    executable = None
    flags = None
    probe_error: Exception | None = None
    try:
        if cfg.prism_bin is not None:
            executable = os.environ.get(cfg.prism_bin.removeprefix("env:"))
        executable = executable or resolve_executable("prism")
        flags = probe_flags(executable)
    except Exception as error:
        probe_error = error
        executable = executable or "prism"

    calls: list[dict[str, Any]] = []
    for mode, item in pairs:
        started_at, _ = _timestamp_parts(clock.now())
        started = clock.monotonic()
        result = None
        error: Exception | None = probe_error
        if error is None:
            try:
                result = run_analyzer_item(
                    item,
                    mode,
                    binary=executable,
                    flags=flags,
                    line_tolerance=cfg.line_tolerance,
                )
            except Exception as caught:
                error = caught
        duration_ms = _duration_ms(clock, started)
        artifact_key = _analyzer_artifact_key(mode.version)
        input_sha256 = {name: ref.sha256 for name, ref in sorted(item.inputs.items())}
        call: dict[str, Any] = {
            "item_id": item.id,
            "version": mode.version,
            "sample": 0,
            "started_at": started_at,
            "duration_ms": duration_ms,
            "cost_usd": 0.0,
            "cache": "miss",
            "input_sha256": input_sha256,
            "replay_key": f"{mode.version}/{item.id}/s0",
        }
        if error is not None:
            detail = {"type": type(error).__name__, "message": str(error)}
            stage_value = {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "stage": "analyzer",
                "status": "error",
                "error": detail,
            }
            call.update(
                {
                    "final_document_valid": False,
                    "raw": "",
                    "output": None,
                    "stage_error": "analyzer",
                    "stage_error_detail": detail,
                }
            )
        elif result is not None and result.stage_record is None:
            reason = result.version_record["skipped"]
            stage_value = {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "stage": "analyzer",
                "status": "skipped",
                "skipped": reason,
            }
            call.update(
                {
                    "final_document_valid": False,
                    "raw": "",
                    "output": None,
                    "skipped": reason,
                }
            )
        else:
            if result is None or result.stage_record is None or result.match is None:
                raise AnalyzerExecutorError("analyzer result omitted a completed stage")
            output = {"findings": list(result.findings)}
            stage_value = {
                **result.stage_record,
                "sample": 0,
                "status": "ok",
            }
            call.update(
                {
                    "final_document_valid": True,
                    "raw": canonical_json(output).decode(),
                    "output": output,
                    "match": asdict(result.match),
                    "strata": list(result.strata),
                }
            )
        stage_ref = writer.write_stage(
            version=artifact_key,
            item_id=item.id,
            stage="analyzer",
            value=stage_value,
            sample=0,
            shared=False,
        )
        call["stage_ref"] = asdict(stage_ref)
        writer.write_json_once(
            PurePosixPath("calls", f"{artifact_key}-{item.id}-0.json"), call
        )
        if call.get("stage_error"):
            assert_record = {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "stage_error": "analyzer",
                "asserts": [],
            }
        elif call.get("skipped"):
            assert_record = {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "skipped": call["skipped"],
                "asserts": [],
            }
        else:
            assertions = run_asserts(
                output=call["output"],
                raw=call["raw"],
                expected=item.expected,
                item=item_snapshots[item.id],
                cfg=config,
                samples=[call],
            )
            assert_record = {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "asserts": [asdict(assertion) for assertion in assertions],
            }
        writer.write_json_once(
            PurePosixPath("asserts", f"{artifact_key}-{item.id}-0.json"), assert_record
        )
        argv = stage_value.get("argv", [executable, "--help"])
        replay = {
            "item_id": item.id,
            "version": mode.version,
            "sample": 0,
            "stage": "analyzer",
            "provider": "prism",
            "provider_version": str(executable),
            "model": mode.algorithm,
            "task_version": mode.version,
            "prompt_sha256": hashlib.sha256(canonical_json(argv)).hexdigest(),
            "seed": cfg.stats["seed"],
            "input_sha256": input_sha256,
            "cache": "miss",
            "started_at": started_at,
            "duration_ms": duration_ms,
            "cost_usd": 0.0,
            "replay_key": call["replay_key"],
            "stage_ref": asdict(stage_ref),
        }
        if call.get("stage_error"):
            replay["stage_error"] = "analyzer"
        if call.get("skipped"):
            replay["skipped"] = call["skipped"]
        writer.append_event("replay", replay)
        writer.append_event(
            "trace",
            {
                "item_id": item.id,
                "version": mode.version,
                "sample": 0,
                "stage": "analyzer",
                "status": stage_value["status"],
                "started_at": started_at,
                "duration_ms": duration_ms,
            },
        )
        calls.append(call)

    loaded = LoadedRun.load(run_dir)
    metrics = render_analyzer(loaded)
    expected = {(mode.version, item.id, 0) for mode, item in pairs}
    for records, label in (
        (loaded.calls, "calls"),
        (loaded.stages, "stages"),
        (loaded.asserts, "asserts"),
    ):
        actual = {
            (record.get("version"), record.get("item_id"), record.get("sample"))
            for record in records
        }
        if actual != expected:
            raise IntegrityError(
                f"analyzer {label} identity mismatch: missing={sorted(expected - actual)}, "
                f"extra={sorted(actual - expected)}"
            )
    return RunResult(
        run_dir=run_dir,
        metrics=metrics,
        promotion=(
            PromotionVerdict(**next(iter(metrics["promotions"].values())))
            if metrics["promotions"]
            else None
        ),
        stage_errors=sum(bool(call.get("stage_error")) for call in calls),
    )
