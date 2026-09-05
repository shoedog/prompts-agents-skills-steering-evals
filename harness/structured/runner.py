"""Public API for structured and analyzer evaluation runners."""

from __future__ import annotations

from harness.structured.analyzer_runner import run_analyzer as _run_analyzer
from harness.structured.config import AnalyzerConfig, StructuredConfig
from harness.structured.runner_types import (
    Clock,
    ExecutorFactory,
    IntegrityError,
    RunResult,
    StaleRunError,
    SystemClock,
)
from harness.structured.structured_runner import _run_structured
from harness.structured.taskset import load_taskset


def run_analyzer(
    cfg: AnalyzerConfig,
    *,
    clock: Clock,
    force: bool,
    only: frozenset[str],
) -> RunResult:
    """Run through the public seam while retaining its taskset patch point."""
    return _run_analyzer(
        cfg,
        clock=clock,
        force=force,
        only=only,
        taskset_loader=load_taskset,
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
    """Run through the public seam while retaining its taskset patch point."""
    return _run_structured(
        cfg,
        executor_factory=executor_factory,
        clock=clock,
        force=force,
        no_cache=no_cache,
        only=only,
        taskset_loader=load_taskset,
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
