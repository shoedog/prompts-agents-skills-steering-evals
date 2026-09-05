"""Finding-based reduction and rendering for authenticated analyzer runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TYPE_CHECKING

from harness.structured.results import write_json_atomic

if TYPE_CHECKING:
    from harness.structured.replay import LoadedRun


def _rates(tp: int, fp: int, fn: int) -> dict[str, float | int]:
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


def summarize_analyzer(run: LoadedRun) -> dict[str, Any]:
    versions: dict[str, Any] = {}
    for identity in run.config["versions"]:
        version = identity["name"]
        mode_calls = [call for call in run.calls if call["version"] == version]
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
            _rates(
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
            strata[tier] = _rates(
                sum(int(row["tp"]) for row in tier_rows),
                sum(int(row["fp"]) for row in tier_rows),
                sum(int(row["fn"]) for row in tier_rows),
            )
        versions[version] = {
            "identity": {key: value for key, value in identity.items() if key != "name"},
            "n_items": len(scored),
            "n_expected": sum(
                int(call["match"]["tp"]) + int(call["match"]["fn"])
                for call in scored
            ),
            "n_emitted": sum(len(call["output"]["findings"]) for call in scored),
            "micro": _rates(**totals),
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
            "id": run.config["id"],
            "kind": "analyzer",
            "run_id": run.path.name,
            "taskset": run.config["taskset"],
            "split": run.config["split"],
            "n_items": len(run.items),
        },
        "stats": dict(run.config["stats"]),
        "versions": versions,
        "promotions": {},
    }


def _markdown(metrics: Mapping[str, Any]) -> str:
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


def render_analyzer(run: LoadedRun) -> dict[str, Any]:
    metrics = summarize_analyzer(run)
    write_json_atomic(run.path / "metrics.json", metrics)
    (run.path / "report.md").write_text(_markdown(metrics))
    return metrics


__all__ = ["render_analyzer", "summarize_analyzer"]
