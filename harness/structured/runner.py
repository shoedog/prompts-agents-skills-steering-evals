"""Deterministic orchestration for structured-task evaluation runs.

Cache reuse requires either an executor-provided preflight identity or audited
``provider_version`` and ``prompt_sha256`` config pins. For
``LlmLayerExecutor``, those pins must change with the provider version or the
serialized prompt. The runner cannot prove that a live executor would emit the
configured pins, so stale pins can reuse an old entry.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from harness.providers.binpath import resolve_executable
from harness.resultsdir import check_structured_stale_results_dir
from harness.structured.asserts import Population, get, run_asserts
from harness.structured.cache import cache_key
from harness.structured.config import AnalyzerConfig, StructuredConfig
from harness.structured.executors import ExecutionRequest, ExecutionResult, Executor
from harness.structured.promotion import PromotionVerdict
from harness.structured.replay import LoadedRun
from harness.structured.report import render
from harness.structured.results import (
    ResultsWriter,
    StageRef,
    canonical_json,
    confined_run_dir,
    write_json_atomic,
)
from harness.structured.snapshots import write_input_snapshots
from harness.structured.taskset import TaskItem, assemble_request, load_taskset, sha256_file


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


def _config_snapshot(cfg: StructuredConfig, task: str) -> dict[str, Any]:
    try:
        taskset = cfg.taskset.relative_to(cfg.root).as_posix()
    except ValueError as error:
        raise ValueError("configured taskset is outside the repository root") from error
    return {
        "kind": cfg.kind,
        "id": cfg.id,
        "task": task,
        "taskset": taskset,
        "split": cfg.split,
        "versions": deepcopy(list(cfg.versions)),
        "baseline_version": cfg.baseline_version,
        "samples_per_item": cfg.samples_per_item,
        "seed": cfg.seed,
        "jobs": cfg.jobs,
        "asserts": deepcopy(list(cfg.asserts)),
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "request_schema": deepcopy(cfg.request_schema),
        "response_schema": deepcopy(cfg.response_schema),
    }


def _validate_versions(cfg: StructuredConfig) -> None:
    for version in cfg.versions:
        if not isinstance(version, dict):
            raise ValueError("every version must be an object")
        _safe_component(version.get("name"), "version name")
        task_version = version.get("task_version")
        if not isinstance(task_version, str) or not task_version:
            raise ValueError(f"version {version.get('name')!r} needs a nonempty task_version")
        provider = version.get("provider")
        if not isinstance(provider, dict):
            raise ValueError(f"version {version['name']!r} provider must be an object")
        for field in ("kind", "model"):
            if not isinstance(provider.get(field), str) or not provider[field]:
                raise ValueError(
                    f"version {version['name']!r} provider.{field} must be nonempty"
                )


def _validate_asserts(cfg: StructuredConfig) -> None:
    for number, entry in enumerate(cfg.asserts):
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
            raise ValueError(f"asserts[{number}] must have a string type")
        get(entry["type"])
        if entry["type"] == "cost_latency" and entry.get("population") not in {
            "per_item",
            "run",
        }:
            raise ValueError("cost_latency population must be 'per_item' or 'run'")


def _item_snapshot(item: TaskItem) -> dict[str, Any]:
    value = deepcopy(item.raw)
    slice_value = item.input_values.get("slice")
    if isinstance(slice_value, dict) and "rendered_slice" not in value:
        lines = slice_value.get("lines")
        rendered_numbers: list[int] = []
        if (
            isinstance(lines, list)
            and len(lines) == 2
            and all(isinstance(number, int) and not isinstance(number, bool) for number in lines)
        ):
            rendered_numbers = list(range(lines[0], lines[1] + 1))
        value["rendered_slice"] = {
            "text": slice_value.get("text", ""),
            "rendered_line_numbers": rendered_numbers,
        }
    return value


def _seed(base: int, version: str, item_id: str, sample: int) -> int:
    payload = canonical_json(
        {"seed": base, "version": version, "item_id": item_id, "sample": sample}
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 0x7FFFFFFF


def _lookup_identity(work: _Work) -> dict[str, Any]:
    provider = work.version["provider"]
    return {
        "stage_type": "llm",
        "model": provider["model"],
        "task_version": work.version["task_version"],
        "seed": work.seed,
        "sample": work.sample,
        "input_sha256": dict(sorted(work.input_sha256.items())),
        "request_sha256": hashlib.sha256(canonical_json(work.request)).hexdigest(),
    }


def _preflight_cache_identity(
    work: _Work, executor: Executor, request: ExecutionRequest
) -> tuple[str, str] | None:
    provider = work.version["provider"]
    declared = (provider.get("provider_version"), provider.get("prompt_sha256"))
    if all(isinstance(value, str) and value for value in declared):
        return declared  # type: ignore[return-value]
    probe = getattr(executor, "cache_identity", None)
    if probe is None:
        return None
    value = probe(request)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(not isinstance(part, str) or not part for part in value)
    ):
        raise ValueError("executor cache_identity must return (provider_version, prompt_sha256)")
    return value


def _read_cached(
    path: Path,
    *,
    lookup: Mapping[str, Any],
    provider_version: str,
    prompt_sha256: str,
) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_bytes())
        result = value["result"]
        envelope = result["envelope"]
        if value["lookup"] != lookup:
            return None
        if (
            envelope["provider_version"] != provider_version
            or envelope["prompt_sha256"] != prompt_sha256
        ):
            return None
        return result
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None


def _duration_ms(clock: Clock, started: float) -> int:
    elapsed = (clock.monotonic() - started) * 1000
    if not math.isfinite(elapsed):
        raise ValueError("clock produced a non-finite duration")
    return max(0, round(elapsed))


def _sentinel_kind(envelope: Mapping[str, Any]) -> str:
    if envelope.get("final_sentinel") is True:
        return "transport"
    response = envelope.get("response")
    label = response.get("class") if isinstance(response, Mapping) else None
    return "schema" if label in {"unclear", "invalid_output"} else "none"


def _error_envelope(work: _Work, error: BaseException) -> dict[str, Any]:
    digest = hashlib.md5(
        canonical_json(
            {
                "version": work.version["name"],
                "item": work.item.id,
                "sample": work.sample,
                "seed": work.seed,
                "error": type(error).__name__,
            }
        ),
        usedforsecurity=False,
    ).hexdigest()
    invocation = (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:]}"
    )
    provider = work.version["provider"]
    return {
        "schema_version": "1",
        "invocation_id": invocation,
        "task": work.item.task,
        "task_version": work.version["task_version"],
        "provider": provider["kind"],
        "model": provider["model"],
        "provider_version": "unavailable",
        "prompt_sha256": hashlib.sha256(canonical_json(work.request)).hexdigest(),
        "escalation_state": "provider_error",
        "first_tier_valid": None,
        "first_tier_sentinel": None,
        "final_sentinel": True,
        "cache_hit": False,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "cost_usd": 0.0,
        "response": {"class": "provider_error"},
        "log_path": "",
    }


def _run_one(
    work: _Work,
    *,
    executor: Executor,
    writer: ResultsWriter,
    clock: Clock,
    cache_root: Path,
    no_cache: bool,
    response_validator: Draft202012Validator,
) -> _Completed:
    version = work.version["name"]
    key = (version, work.item.id, work.sample)
    lookup = _lookup_identity(work)
    scratch_dir = (
        work.request_file.parent.parent
        / "scratch"
        / f"{version}-{work.item.id}-s{work.sample}"
    )
    execution_request = ExecutionRequest(
        task=work.item.task,
        task_version=work.version["task_version"],
        request_file=work.request_file,
        model=work.version["provider"]["model"],
        seed=work.seed,
        sample=work.sample,
        scratch_dir=scratch_dir,
    )
    identity = _preflight_cache_identity(work, executor, execution_request)
    cached = None
    if not no_cache and identity is not None:
        provider_version, prompt_sha256 = identity
        exact_key = cache_key(
            "llm",
            provider_version,
            work.version["provider"]["model"],
            work.version["task_version"],
            prompt_sha256,
            work.seed,
            work.sample,
            work.input_sha256,
        )
        cached = _read_cached(
            cache_root / f"{exact_key}.json",
            lookup=lookup,
            provider_version=provider_version,
            prompt_sha256=prompt_sha256,
        )
    started_at, _ = _timestamp_parts(clock.now())
    started = clock.monotonic()
    stage_error: str | None = None
    error_detail: dict[str, Any] | None = None
    if cached is not None:
        execution = ExecutionResult(
            envelope=deepcopy(cached["envelope"]),
            raw_stdout=cached["raw_stdout"],
            returncode=cached["returncode"],
        )
        duration_ms = cached["duration_ms"]
        cache_status = "hit"
    else:
        try:
            scratch_dir.mkdir(parents=True, exist_ok=False)
            execution = executor.run(execution_request)
            duration_ms = _duration_ms(clock, started)
            cache_status = "miss"
            envelope = execution.envelope
            if identity is not None:
                full_key = cache_key(
                    "llm",
                    envelope["provider_version"],
                    work.version["provider"]["model"],
                    work.version["task_version"],
                    envelope["prompt_sha256"],
                    work.seed,
                    work.sample,
                    work.input_sha256,
                )
                write_json_atomic(
                    cache_root / f"{full_key}.json",
                    {
                        "lookup": lookup,
                        "result": {
                            "envelope": envelope,
                            "raw_stdout": execution.raw_stdout,
                            "returncode": execution.returncode,
                            "duration_ms": duration_ms,
                        },
                    },
                )
        except Exception as error:
            duration_ms = _duration_ms(clock, started)
            cache_status = "miss"
            stage_error = "classify"
            envelope = _error_envelope(work, error)
            execution = ExecutionResult(envelope=envelope, raw_stdout="", returncode=1)
            error_detail = {
                "type": type(error).__name__,
                "message": str(error),
                "child_returncode": getattr(error, "returncode", None),
                "stdout_tail": getattr(error, "stdout_tail", ""),
                "stderr_tail": getattr(error, "stderr_tail", ""),
            }

    envelope = deepcopy(execution.envelope)
    response = envelope.get("response")
    response_errors = (
        list(response_validator.iter_errors(response)) if isinstance(response, dict) else [None]
    )
    final_document_valid = not response_errors
    sentinel_kind = _sentinel_kind(envelope)
    stage_value: dict[str, Any] = {
        "item_id": work.item.id,
        "version": version,
        "sample": work.sample,
        "stage": "classify",
        "status": "error" if stage_error else "ok",
    }
    if error_detail is None:
        stage_value["response"] = response
    else:
        stage_value["error"] = error_detail
    writer.write_stage(
        version=version,
        item_id=work.item.id,
        stage="classify",
        value=stage_value,
        sample=work.sample,
        shared=False,
    )
    raw_response = (
        json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if isinstance(response, dict)
        else ""
    )
    call: dict[str, Any] = {
        "item_id": work.item.id,
        "version": version,
        "sample": work.sample,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "cache": cache_status,
        "input_sha256": dict(sorted(work.input_sha256.items())),
        "final_document_valid": final_document_valid,
        "sentinel_kind": sentinel_kind,
        "raw": raw_response,
        "output": response if isinstance(response, dict) else None,
        "replay_key": f"{version}/{work.item.id}/s{work.sample}",
        "llm_envelope": envelope,
    }
    if stage_error is not None:
        call["stage_error"] = stage_error
        call["stage_error_detail"] = error_detail
    if work.shared_ref is not None:
        call["stage_ref"] = asdict(work.shared_ref)
    writer.write_json_once(
        PurePosixPath("calls", f"{version}-{work.item.id}-{work.sample}.json"), call
    )
    replay = {
        "item_id": work.item.id,
        "version": version,
        "sample": work.sample,
        "stage": "classify",
        "provider": envelope["provider"],
        "provider_version": envelope["provider_version"],
        "model": envelope["model"],
        "task_version": envelope["task_version"],
        "prompt_sha256": envelope["prompt_sha256"],
        "seed": work.seed,
        "input_sha256": dict(sorted(work.input_sha256.items())),
        "cache": cache_status,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "cost_usd": envelope["cost_usd"],
        "replay_key": call["replay_key"],
    }
    if work.shared_ref is not None:
        replay["stage_ref"] = asdict(work.shared_ref)
    if stage_error is not None:
        replay["stage_error"] = stage_error
    trace = {
        "item_id": work.item.id,
        "version": version,
        "sample": work.sample,
        "stage": "classify",
        "status": "error" if stage_error else "ok",
        "started_at": started_at,
        "duration_ms": duration_ms,
    }
    return _Completed(key, call, replay, trace)


def _write_assert_records(
    writer: ResultsWriter,
    *,
    calls: list[dict[str, Any]],
    items: Mapping[str, dict[str, Any]],
    config: dict[str, Any],
    classes: tuple[str, ...],
) -> None:
    for version in [entry["name"] for entry in config["versions"]]:
        run_calls = [
            call
            for call in calls
            if call["version"] == version and not call.get("stage_error")
        ]
        run_samples = [dict(call) for call in run_calls]
        run_population = (
            run_samples,
            Population(
                "run",
                item_count=len({call["item_id"] for call in run_calls}),
                sample_count=len(run_calls),
            ),
        ) if run_calls else None
        for call in [row for row in calls if row["version"] == version]:
            relative = PurePosixPath(
                "asserts", f"{version}-{call['item_id']}-{call['sample']}.json"
            )
            if call.get("stage_error"):
                writer.write_json_once(
                    relative,
                    {
                        "item_id": call["item_id"],
                        "version": version,
                        "sample": call["sample"],
                        "stage_error": call["stage_error"],
                        "asserts": [],
                    },
                )
                continue
            item_calls = [row for row in run_calls if row["item_id"] == call["item_id"]]
            item_samples = [dict(row) for row in item_calls]
            populations = {
                "per_item": (
                    item_samples,
                    Population("per_item", item_count=1, sample_count=len(item_samples)),
                )
            }
            if run_population is not None:
                populations["run"] = run_population
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


def _analyzer_artifact_key(version: str) -> str:
    return f"mode-{hashlib.sha256(version.encode()).hexdigest()[:16]}"


def _analyzer_config_snapshot(cfg: AnalyzerConfig, task: str) -> dict[str, Any]:
    try:
        taskset = cfg.taskset.relative_to(cfg.root).as_posix()
    except ValueError as error:
        raise ValueError("configured taskset is outside the repository root") from error
    return {
        "kind": "analyzer",
        "id": cfg.id,
        "task": task,
        "taskset": taskset,
        "split": cfg.split,
        "versions": [{"name": mode.version, **asdict(mode)} for mode in cfg.modes],
        "baseline_version": cfg.baseline_version,
        "samples_per_item": 1,
        "asserts": deepcopy(list(cfg.asserts)),
        "match": {
            "rule": "category_file_line",
            "line_tolerance": cfg.line_tolerance,
        },
        "stats": deepcopy(cfg.stats),
        "token_budget": deepcopy(cfg.token_budget),
        "prism_bin": cfg.prism_bin,
    }


def _analyzer_rates(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def _analyzer_metrics(
    cfg: AnalyzerConfig,
    *,
    run_dir: Path,
    items: tuple[TaskItem, ...],
    calls: list[dict[str, Any]],
) -> dict[str, Any]:
    versions: dict[str, Any] = {}
    for mode in cfg.modes:
        mode_calls = [call for call in calls if call["version"] == mode.version]
        error_ids = sorted(
            {call["item_id"] for call in mode_calls if call.get("stage_error")}
        )
        skipped = [call for call in mode_calls if call.get("skipped")]
        scored = [
            call
            for call in mode_calls
            if call["item_id"] not in error_ids and not call.get("skipped")
        ]
        totals = {
            field: sum(int(call["match"][field]) for call in scored)
            for field in ("tp", "fp", "fn")
        }
        per_item = [
            _analyzer_rates(
                int(call["match"]["tp"]),
                int(call["match"]["fp"]),
                int(call["match"]["fn"]),
            )
            for call in scored
        ]
        strata = {}
        for tier in ("asserted", "candidate"):
            tier_rows = [
                row
                for call in scored
                for row in call["strata"]
                if row["tier"] == tier
            ]
            strata[tier] = _analyzer_rates(
                sum(int(row["tp"]) for row in tier_rows),
                sum(int(row["fp"]) for row in tier_rows),
                sum(int(row["fn"]) for row in tier_rows),
            )
        versions[mode.version] = {
            "identity": asdict(mode),
            "n_items": len(scored),
            "n_expected": sum(int(call["match"]["tp"]) + int(call["match"]["fn"]) for call in scored),
            "n_emitted": sum(len(call["output"]["findings"]) for call in scored),
            "micro": _analyzer_rates(**totals),
            "macro": {
                metric: (
                    sum(float(row[metric]) for row in per_item) / len(per_item)
                    if per_item
                    else 0.0
                )
                for metric in ("precision", "recall", "f1")
            },
            "strata": strata,
            "stage_errors": {
                "calls": sum(bool(call.get("stage_error")) for call in mode_calls),
                "item_ids": error_ids,
            },
            "skipped": {
                "calls": len(skipped),
                "item_ids": sorted(call["item_id"] for call in skipped),
                "reasons": sorted({call["skipped"] for call in skipped}),
            },
        }
    return {
        "experiment": {
            "id": cfg.id,
            "kind": "analyzer",
            "run_id": run_dir.name,
            "taskset": cfg.taskset.relative_to(cfg.root).as_posix(),
            "split": cfg.split,
            "n_items": len(items),
        },
        "stats": deepcopy(cfg.stats),
        "versions": versions,
        "promotions": {},
    }


def _analyzer_report(metrics: Mapping[str, Any]) -> str:
    experiment = metrics["experiment"]
    lines = [
        "# Analyzer evaluation report",
        "",
        f"- experiment: {experiment['id']}",
        f"- run id: {experiment['run_id']}",
        f"- taskset / split: {experiment['taskset']} / {experiment['split']}",
        f"- item count: {experiment['n_items']}",
        "",
        "| Mode | Items | Precision | Recall | F1 | Expected | Emitted | Stage errors | Skipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for version, values in metrics["versions"].items():
        micro = values["micro"]
        lines.append(
            f"| {version} | {values['n_items']} | {micro['precision']:.6f} | "
            f"{micro['recall']:.6f} | {micro['f1']:.6f} | {values['n_expected']} | "
            f"{values['n_emitted']} | {values['stage_errors']['calls']} | "
            f"{values['skipped']['calls']} |"
        )
    return "\n".join((*lines, "", "> PROVISIONAL — pending human spot-check.", ""))


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

    metrics = _analyzer_metrics(cfg, run_dir=run_dir, items=items, calls=calls)
    writer.write_json(PurePosixPath("metrics.json"), metrics)
    (run_dir / "report.md").write_text(_analyzer_report(metrics))
    loaded = LoadedRun.load(run_dir)
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
        promotion=None,
        stage_errors=sum(bool(call.get("stage_error")) for call in calls),
    )


def run_structured(
    cfg: StructuredConfig,
    *,
    executor_factory: ExecutorFactory,
    clock: Clock,
    force: bool,
    no_cache: bool,
    only: frozenset[str],
) -> RunResult:
    """Run one validated structured-task config into an authenticated result tree."""
    _validate_versions(cfg)
    _validate_asserts(cfg)
    taskset = load_taskset(
        cfg.taskset,
        split=cfg.split,
        max_items=cfg.token_budget["max_items"],
    )
    by_id = {item.id: item for item in taskset.items}
    unknown = sorted(only - by_id.keys())
    if unknown:
        raise ValueError(f"unknown --only item: {unknown[0]}")
    items = tuple(by_id[item_id] for item_id in sorted(only or by_id.keys()))
    if not items:
        raise ValueError("structured run selected no items")
    versions = tuple(deepcopy(list(cfg.versions)))
    config = _config_snapshot(cfg, taskset.manifest["task"])
    item_snapshots = {item.id: _item_snapshot(item) for item in items}
    requests: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        for sample in range(cfg.samples_per_item):
            requests[(item.id, sample)] = {
                version["name"]: assemble_request(
                    item,
                    task_version=version["task_version"],
                    request_schema=cfg.request_schema,
                )
                for version in versions
            }

    started_at, compact = _timestamp_parts(clock.now())
    del started_at
    config_digest = hashlib.sha256(canonical_json(config) + b"\n").hexdigest()
    run_dir = confined_run_dir(cfg.root, cfg.id, f"{compact}-{config_digest[:8]}")
    if not check_structured_stale_results_dir(run_dir, force=force):
        raise StaleRunError(f"stale structured results: {run_dir}")
    writer = ResultsWriter(run_dir)
    write_input_snapshots(
        writer,
        config=config,
        manifest=taskset.manifest,
        items=item_snapshots,
        requests=requests,
    )
    executors = {version["name"]: executor_factory(version) for version in versions}
    shared_refs = _shared_refs(writer, items, versions)
    cache_root = cfg.root / ".cache" / "structured"

    completed: list[_Completed] = []
    with tempfile.TemporaryDirectory(prefix="structured-run-", dir=cfg.root) as temporary:
        temporary_root = Path(temporary)
        work_items: list[_Work] = []
        for version in versions:
            for item in items:
                for sample in range(cfg.samples_per_item):
                    request_file = (
                        temporary_root
                        / "requests"
                        / f"{version['name']}-{item.id}-s{sample}.json"
                    )
                    write_json_atomic(request_file, requests[(item.id, sample)][version["name"]])
                    work_items.append(
                        _Work(
                            version=version,
                            item=item,
                            sample=sample,
                            seed=_seed(cfg.seed, version["name"], item.id, sample),
                            request=requests[(item.id, sample)][version["name"]],
                            request_file=request_file,
                            input_sha256={
                                name: ref.sha256 for name, ref in sorted(item.inputs.items())
                            },
                            shared_ref=shared_refs.get((version["name"], item.id)),
                        )
                    )
        response_validator = Draft202012Validator(cfg.response_schema)
        max_cost = float(cfg.token_budget["max_cost_usd"])
        spent = 0.0
        budget_reached = False
        next_work = 0
        with ThreadPoolExecutor(max_workers=cfg.jobs) as pool:
            futures: dict[Future[_Completed], int] = {}

            def submit(work_index: int) -> None:
                work = work_items[work_index]
                future = pool.submit(
                    _run_one,
                    work,
                    executor=executors[work.version["name"]],
                    writer=writer,
                    clock=clock,
                    cache_root=cache_root,
                    no_cache=no_cache,
                    response_validator=response_validator,
                )
                futures[future] = work_index

            while next_work < len(work_items) and len(futures) < cfg.jobs:
                submit(next_work)
                next_work += 1

            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=futures.__getitem__):
                    futures.pop(future)
                    if future.cancelled():
                        continue
                    result = future.result()
                    completed.append(result)
                    if result.call["cache"] == "miss":
                        spent += float(result.call["llm_envelope"]["cost_usd"])
                if spent > 0.0 and spent >= max_cost:
                    budget_reached = True
                    for future in futures:
                        future.cancel()
                if not budget_reached:
                    while next_work < len(work_items) and len(futures) < cfg.jobs:
                        submit(next_work)
                        next_work += 1

        if budget_reached:
            raise RuntimeError(
                "token_budget.max_cost_usd reached after provider invocation: "
                f"reported ${spent:.6f} against ${max_cost:.6f}"
            )

    completed.sort(key=lambda value: value.key)
    calls = [value.call for value in completed]
    for value in completed:
        writer.append_event("replay", value.replay)
        writer.append_event("trace", value.trace)
    _write_assert_records(
        writer,
        calls=calls,
        items=item_snapshots,
        config=config,
        classes=tuple(taskset.classes),
    )
    loaded = LoadedRun.load(run_dir)
    render(loaded)
    _verify_final_tree(
        run_dir,
        loaded=loaded,
        versions=tuple(version["name"] for version in versions),
        items=tuple(item.id for item in items),
        samples=cfg.samples_per_item,
        shared_refs=shared_refs,
    )
    metrics = json.loads((run_dir / "metrics.json").read_bytes())
    promotion_value = next(iter(metrics["promotions"].values()), None)
    promotion = PromotionVerdict(**promotion_value) if promotion_value is not None else None
    return RunResult(
        run_dir=run_dir,
        metrics=metrics,
        promotion=promotion,
        stage_errors=sum(bool(call.get("stage_error")) for call in loaded.calls),
    )


__all__ = [
    "Clock",
    "ExecutorFactory",
    "IntegrityError",
    "RunResult",
    "StaleRunError",
    "SystemClock",
    "run_analyzer",
    "run_structured",
]
