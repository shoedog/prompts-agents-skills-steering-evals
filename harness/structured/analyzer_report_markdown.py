"""Markdown rendering for analyzer metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def analyzer_markdown(metrics: Mapping[str, Any]) -> str:
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
    lines.extend(["", "## Tier metrics", ""])
    for version, values in metrics["versions"].items():
        lines.extend(
            [
                f"### {version}",
                "",
                "| Tier | Precision | Recall | F1 | TP | FP | FN |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for tier, row in values["strata"].items():
            lines.append(
                f"| {tier} | {row['precision']:.6f} | {row['recall']:.6f} | "
                f"{row['f1']:.6f} | {row['tp']} | {row['fp']} | {row['fn']} |"
            )
        lines.append("")
    lines.extend(["## Paired analyzer deltas", ""])
    for candidate, verdict in metrics["promotions"].items():
        lines.extend([f"### {candidate}", "", f"- {verdict['reason']}"])
        evidence = verdict["evidence"]
        if evidence["status"] == "unavailable":
            lines.extend(["- evidence: unavailable (0 surviving pairs)", ""])
            continue
        population = evidence["population"]
        lines.extend(
            [
                f"- paired population: n={population['n_items']}, sha256=`{population['sha256']}`",
                "",
                "| Metric | Baseline | Candidate | Delta | CI low | CI high |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for metric, row in evidence["metrics"].items():
            lines.append(
                f"| {metric} | {row['baseline']:.6f} | {row['candidate']:.6f} | "
                f"{row['delta']:.6f} | {row['lo']:.6f} | {row['hi']:.6f} |"
            )
        lines.append("")
    return "\n".join((*lines, "", "> PROVISIONAL — pending human spot-check.", ""))


__all__ = ["analyzer_markdown"]
