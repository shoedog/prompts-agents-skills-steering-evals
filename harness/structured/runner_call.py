"""One-call execution and durable record writing."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

from harness.structured.cache import cache_key
from harness.structured.executors import ExecutionRequest, ExecutionResult, Executor
from harness.structured.normalization import normalize_response
from harness.structured.results import ResultsWriter, write_json_atomic
from harness.structured.runner_cache import (
    _duration_ms,
    _error_envelope,
    _lookup_identity,
    _preflight_cache_identity,
    _read_cached,
)
from harness.structured.runner_types import Clock, _Completed, _Work, _timestamp_parts

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
    normalized = normalize_response(envelope, response_validator)
    response = normalized.output
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
    call: dict[str, Any] = {
        "item_id": work.item.id,
        "version": version,
        "sample": work.sample,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "cache": cache_status,
        "input_sha256": dict(sorted(work.input_sha256.items())),
        "final_document_valid": normalized.final_document_valid,
        "sentinel_kind": normalized.sentinel_kind,
        "raw": normalized.raw,
        "output": normalized.output,
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
