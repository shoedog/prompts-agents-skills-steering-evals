"""Finding-based reduction and rendering for authenticated analyzer runs."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, TYPE_CHECKING

from harness.stats.bootstrap import paired_delta_ci
from harness.structured.results import canonical_json, write_json_atomic

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


def _usable(call: Mapping[str, Any]) -> bool:
    return not call.get("stage_error") and not call.get("skipped")


def _aggregate(calls: list[dict[str, Any]], tier: str | None = None) -> dict[str, float | int]:
    if tier is None:
        rows = [call["match"] for call in calls]
    else:
        rows = [
            row
            for call in calls
            for row in call["strata"]
            if row["tier"] == tier
        ]
    return _rates(
        sum(int(row["tp"]) for row in rows),
        sum(int(row["fp"]) for row in rows),
        sum(int(row["fn"]) for row in rows),
    )


def _statistic(metric: str, *, macro: bool = False, tier: str | None = None):
    def reduce(calls: list[dict[str, Any]]) -> float:
        if macro:
            return sum(
                float(
                    _rates(
                        int(call["match"]["tp"]),
                        int(call["match"]["fp"]),
                        int(call["match"]["fn"]),
                    )[metric]
                )
                for call in calls
            ) / len(calls)
        return float(_aggregate(calls, tier)[metric])

    return reduce


def _paired_metric(
    baseline: dict[str, dict[str, Any]],
    candidate: dict[str, dict[str, Any]],
    statistic,
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    interval = paired_delta_ci(
        baseline, candidate, statistic, resamples=resamples, seed=seed
    )
    keys = sorted(baseline)
    return {
        "baseline": statistic([baseline[key] for key in keys]),
        "candidate": statistic([candidate[key] for key in keys]),
        **interval,
        "n_items": len(keys),
    }


def _comparison(run: LoadedRun, baseline: str, candidate: str) -> dict[str, Any]:
    baseline_calls = {
        call["item_id"]: call
        for call in run.calls
        if call["version"] == baseline and _usable(call)
    }
    candidate_calls = {
        call["item_id"]: call
        for call in run.calls
        if call["version"] == candidate and _usable(call)
    }
    item_ids = sorted(set(baseline_calls) & set(candidate_calls))
    population = {
        "item_ids": item_ids,
        "n_items": len(item_ids),
        "sha256": hashlib.sha256(canonical_json(item_ids)).hexdigest(),
    }
    if not item_ids:
        return {
            "promotable": False,
            "reason": "NOT PROMOTABLE: analyzer paired evidence unavailable (0 surviving pairs)",
            "evidence": {
                "status": "unavailable",
                "population": population,
                "metrics": {},
                "gate": {
                    "metric": "macro_f1",
                    "observed_ci_lo": None,
                    "operator": ">=",
                    "passed": False,
                    "threshold": 0.0,
                },
            },
        }
    left = {item_id: baseline_calls[item_id] for item_id in item_ids}
    right = {item_id: candidate_calls[item_id] for item_id in item_ids}
    resamples = int(run.config["stats"]["bootstrap_resamples"])
    seed = int(run.config["stats"]["seed"])
    metrics = {
        "macro_f1": _paired_metric(
            left, right, _statistic("f1", macro=True), resamples=resamples, seed=seed
        ),
        "micro_precision": _paired_metric(
            left, right, _statistic("precision"), resamples=resamples, seed=seed
        ),
        "micro_recall": _paired_metric(
            left, right, _statistic("recall"), resamples=resamples, seed=seed
        ),
        "micro_f1": _paired_metric(
            left, right, _statistic("f1"), resamples=resamples, seed=seed
        ),
        **{
            f"tier_{tier}_f1": _paired_metric(
                left,
                right,
                _statistic("f1", tier=tier),
                resamples=resamples,
                seed=seed,
            )
            for tier in ("asserted", "candidate")
        },
    }
    lower = float(metrics["macro_f1"]["lo"])
    promotable = lower >= 0.0
    return {
        "promotable": promotable,
        "reason": (
            f"PROMOTABLE: analyzer macro_f1_ci.lo={lower:g} is at least 0"
            if promotable
            else f"NOT PROMOTABLE: analyzer macro_f1_ci.lo={lower:g} is below 0"
        ),
        "evidence": {
            "status": "available",
            "population": population,
            "metrics": metrics,
            "gate": {
                "metric": "macro_f1",
                "observed_ci_lo": lower,
                "operator": ">=",
                "passed": promotable,
                "threshold": 0.0,
            },
        },
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
            "micro": _aggregate(scored),
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
    baseline = run.config["baseline_version"]
    promotions = {
        identity["name"]: _comparison(run, baseline, identity["name"])
        for identity in run.config["versions"]
        if identity["name"] != baseline
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
        "promotions": promotions,
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


def render_analyzer(run: LoadedRun) -> dict[str, Any]:
    metrics = summarize_analyzer(run)
    write_json_atomic(run.path / "metrics.json", metrics)
    (run.path / "report.md").write_text(_markdown(metrics))
    return metrics


__all__ = ["render_analyzer", "summarize_analyzer"]
