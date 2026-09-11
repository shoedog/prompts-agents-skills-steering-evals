"""Cache identity and failure envelopes for structured calls."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from harness.structured.executors import ExecutionRequest, Executor
from harness.structured.results import canonical_json
from harness.structured.runner_types import Clock, _Work

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
