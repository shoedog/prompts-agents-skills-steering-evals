"""Atomic structured report and trend output."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.structured.report_markdown import _report_markdown
from harness.structured.report_summary import summarize
from harness.structured.trends import append_trend_once

if TYPE_CHECKING:
    from harness.structured.replay import LoadedRun

_BULKY_KEYS = {"calls", "scored_rows", "worst_rows"}
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z(?:-.+)?$")
_TREND_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _trend_timestamp(run_id: str) -> str:
    if _RUN_ID.fullmatch(run_id) is None:
        raise ValueError(f"run id does not start with a UTC timestamp: {run_id!r}")
    return datetime.strptime(run_id[:16], "%Y%m%dT%H%M%SZ").strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _trend_rows(summary: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    experiment = summary["experiment"]
    task = experiment["task"]
    if not isinstance(task, str) or _TREND_COMPONENT.fullmatch(task) is None:
        raise ValueError("structured task must be one safe nonempty path component")
    run_id = experiment["run_id"]
    if not isinstance(run_id, str):
        raise ValueError("structured run id must be a string")
    timestamp = _trend_timestamp(run_id)
    versions = summary["versions"]
    rows = []
    for candidate_name, verdict in summary["promotions"].items():
        evidence = verdict["evidence"]
        if evidence.get("status") == "unavailable":
            continue
        metrics = evidence["metrics"]
        candidate = versions[candidate_name]
        baseline_name = evidence["population"]["baseline_version"]
        baseline = versions[baseline_name]
        candidate_version = candidate["identity"]["task_version"]
        baseline_version = baseline["identity"]["task_version"]
        for name, version in (
            (candidate_name, candidate_version),
            (baseline_name, baseline_version),
        ):
            if not isinstance(version, str) or not version:
                raise ValueError(
                    f"structured version {name} must have a nonempty task_version"
                )
        macro_f1 = metrics["macro_f1"]
        rows.append(
            {
                "ts": timestamp,
                "task": task,
                "experiment": experiment["id"],
                "run_id": run_id,
                "split": experiment["split"],
                "candidate": candidate_name,
                "version": candidate_version,
                "baseline_version": baseline_version,
                "n_items": evidence["population"]["n_items"],
                "macro_f1": candidate["classification"]["macro_f1"],
                "delta_macro_f1": macro_f1["delta"],
                "delta_ci": [macro_f1["lo"], macro_f1["hi"]],
                "schema_validity": candidate["classification"][
                    "schema_valid_for_eval"
                ]["rate"],
                "brier": candidate["calibration"]["score"],
                "kappa_vs_human": candidate["kappa_vs_human"],
                "cost_usd": candidate["cost"]["cost_usd"],
                "p95_ms": candidate["cost"]["p95_ms"],
                "promotable": verdict["promotable"],
            }
        )
    return task, rows


def render(run: LoadedRun) -> dict[str, Any]:
    """Complete a run by writing its report pair and appending candidate trends."""
    summary = summarize(run)
    task, trend_rows = _trend_rows(summary)
    _write_bytes_atomic(run.path / "report.md", _report_markdown(summary).encode("utf-8"))
    machine = {key: value for key, value in summary.items() if key not in _BULKY_KEYS}
    metrics_bytes = (
        json.dumps(
            machine,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        ).encode("utf-8")
        + b"\n"
    )
    _write_bytes_atomic(run.path / "metrics.json", metrics_bytes)
    trend_path = run.path.parents[1] / "trends" / f"{task}.jsonl"
    for row in trend_rows:
        append_trend_once(trend_path, row)
    return summary
