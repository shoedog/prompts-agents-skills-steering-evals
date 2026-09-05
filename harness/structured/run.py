"""Command-line entry point for structured evaluation experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from harness.structured.config import AnalyzerConfig, PipelineConfig, REPO_ROOT, load_config
from harness.structured.executors import ExecutionRequest, ExecutionResult, LlmLayerExecutor
from harness.structured.results import canonical_json
from harness.structured.runner import StaleRunError, SystemClock, run_analyzer, run_structured


class _StubExecutor:
    def __init__(self, version: dict[str, Any]) -> None:
        self.version = version

    def cache_identity(self, request: ExecutionRequest) -> tuple[str, str]:
        body = json.loads(request.request_file.read_text())
        return "structured-stub-1", hashlib.sha256(canonical_json(body)).hexdigest()

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        body = json.loads(request.request_file.read_text())
        request_sha = hashlib.sha256(canonical_json(body)).hexdigest()
        identity = hashlib.md5(
            canonical_json(
                {
                    "version": self.version["name"],
                    "request": request_sha,
                    "sample": request.sample,
                    "seed": request.seed,
                }
            ),
            usedforsecurity=False,
        ).hexdigest()
        response = {
            "class": "correct",
            "confidence": 1.0,
            "rationale": "stub fixture",
            "evidence_lines": [],
        }
        envelope = {
            "schema_version": "1",
            "invocation_id": (
                f"{identity[:8]}-{identity[8:12]}-{identity[12:16]}-"
                f"{identity[16:20]}-{identity[20:]}"
            ),
            "task": request.task,
            "task_version": request.task_version,
            "provider": "stub",
            "model": request.model,
            "provider_version": "structured-stub-1",
            "prompt_sha256": request_sha,
            "escalation_state": "first_valid",
            "first_tier_valid": True,
            "first_tier_sentinel": False,
            "final_sentinel": False,
            "cache_hit": False,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "cost_usd": 0.0,
            "response": response,
            "log_path": "stub",
        }
        return ExecutionResult(
            envelope=envelope,
            raw_stdout=json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
            returncode=0,
        )


def _default_executor_factory(version: dict[str, Any]):
    provider = version["provider"]
    if provider["kind"] == "stub":
        return _StubExecutor(version)
    if provider["kind"] == "llm_layer":
        return LlmLayerExecutor()
    raise ValueError(f"unknown structured provider kind: {provider['kind']!r}")


_CLOCK = SystemClock()
_EXECUTOR_FACTORY = _default_executor_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a structured evaluation experiment")
    parser.add_argument("experiment")
    parser.add_argument("--split", choices=("dev", "test"))
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    return parser


def _root_for(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        return REPO_ROOT
    for parent in (candidate.parent, *candidate.parents):
        if (parent / "contracts").is_dir():
            return parent
    return REPO_ROOT


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.experiment, root=_root_for(args.experiment))
        split = args.split or cfg.split
        if split == "test" and not args.allow_test:
            print("[structured] REFUSING test split without --allow-test", file=sys.stderr)
            return 5
        if args.jobs <= 0:
            raise ValueError("--jobs must be a positive integer")
        if isinstance(cfg, AnalyzerConfig):
            cfg = replace(cfg, split=split)
            result = run_analyzer(
                cfg,
                clock=_CLOCK,
                force=args.force,
                only=frozenset(args.only),
            )
        elif isinstance(cfg, PipelineConfig):
            from harness.structured.pipeline_runner import run_pipeline

            cfg = replace(cfg, split=split, jobs=args.jobs)
            result = run_pipeline(
                cfg,
                clock=_CLOCK,
                force=args.force,
                only=frozenset(args.only),
            )
        else:
            cfg = replace(cfg, split=split, jobs=args.jobs)
            result = run_structured(
                cfg,
                executor_factory=_EXECUTOR_FACTORY,
                clock=_CLOCK,
                force=args.force,
                no_cache=args.no_cache,
                only=frozenset(args.only),
            )
    except StaleRunError:
        return 4
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        print(f"[structured] ERROR: {error}", file=sys.stderr)
        return 1
    if result.promotion is not None:
        print(result.promotion.reason)
    else:
        print("NO PROMOTION CANDIDATE")
    print(f"RESULTS_DIR={result.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
