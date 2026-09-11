"""Paired comparison evidence for structured run reports."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from typing import Any

from harness.structured.promotion import promotion_verdict
from harness.structured.report_reduction import _stage_error_item_ids
from harness.structured.report_statistics import (
    _brier_score,
    _classification_stat,
    _cost_per_item,
    _kappa,
    _metric_evidence,
    _normalized_call,
    _p95_latency,
    _paired_binary_p,
    _schema_validity,
)
from harness.structured.results import canonical_json

def _comparison(
    run: Any,
    baseline_name: str,
    candidate_name: str,
    grouped: Mapping[str, Mapping[str, list[dict]]],
    classes: Sequence[str],
) -> dict[str, Any]:
    paired_ids = [
        item_id
        for item_id in sorted(run.items)
        if not any(
            call.get("stage_error")
            for version in (baseline_name, candidate_name)
            for call in grouped[version][item_id]
        )
    ]
    candidate_excluded = _stage_error_item_ids(grouped[candidate_name])
    candidate_complete_ids = sorted(set(run.items) - candidate_excluded)
    candidate_complete_rows = [
        _normalized_call(call, run.items[item_id])
        for item_id in candidate_complete_ids
        for call in grouped[candidate_name][item_id]
    ]
    candidate_complete_validity = (
        sum(row.schema_valid_for_eval for row in candidate_complete_rows)
        / len(candidate_complete_rows)
        if candidate_complete_rows
        else None
    )
    resamples = run.config["stats"]["bootstrap_resamples"]
    seed = run.config["stats"]["seed"]
    population_value = {
        "baseline_version": baseline_name,
        "candidate_version": candidate_name,
        "item_ids": paired_ids,
        "samples_per_item": run.config["samples_per_item"],
    }
    population = {
        **population_value,
        "n_items": len(paired_ids),
        "sha256": hashlib.sha256(canonical_json(population_value)).hexdigest(),
    }
    if not paired_ids:
        return {
            "promotable": False,
            "reason": "NOT PROMOTABLE: paired evidence unavailable (0 surviving pairs)",
            "evidence": {
                "status": "unavailable",
                "metrics": {},
                "recall_cis": {},
                "population": population,
                "resamples": resamples,
                "seed": seed,
                "method": "percentile",
                "alpha": 0.05,
                "stage_error_excluded_item_ids": sorted(run.items),
                "candidate_complete_scored_population": {
                    "item_ids": candidate_complete_ids,
                    "n_items": len(candidate_complete_ids),
                    "n_samples": len(candidate_complete_rows),
                    "schema_validity": candidate_complete_validity,
                },
            },
        }
    bundles: dict[str, dict[str, dict[str, Any]]] = {baseline_name: {}, candidate_name: {}}
    for version in bundles:
        for item_id in paired_ids:
            calls = grouped[version][item_id]
            bundles[version][item_id] = {
                "item_id": item_id,
                "calls": calls,
                "scored": [_normalized_call(call, run.items[item_id]) for call in calls],
            }
    baseline = bundles[baseline_name]
    candidate = bundles[candidate_name]
    metric_stats: list[tuple[str, Callable[[Sequence[dict[str, Any]]], float]]] = [
        ("macro_f1", _classification_stat(classes, "macro_f1")),
    ]
    metric_stats.extend(
        (f"f1:{label}", _classification_stat(classes, "f1", label)) for label in classes
    )
    metric_stats.extend(
        (
            ("schema_validity", _schema_validity),
            ("brier", _brier_score),
            ("kappa", _kappa(classes)),
            ("cost_per_item", _cost_per_item),
            ("p95_latency_ms", _p95_latency),
        )
    )
    metrics = {
        name: _metric_evidence(
            baseline,
            candidate,
            statistic,
            resamples=resamples,
            seed=seed,
        )
        for name, statistic in metric_stats
    }
    metrics["p95_latency_ms"]["population"] = {
        "kind": "version",
        "n_calls": len(paired_ids) * int(run.config["samples_per_item"]),
    }
    metrics["schema_validity"]["mcnemar_p"] = _paired_binary_p(
        list(baseline.values()),
        list(candidate.values()),
        lambda row: row.schema_valid_for_eval,
    )
    recall_cis = {}
    for label in classes:
        evidence = _metric_evidence(
            baseline,
            candidate,
            _classification_stat(classes, "recall", label),
            resamples=resamples,
            seed=seed,
        )
        evidence["mcnemar_p"] = _paired_binary_p(
            list(baseline.values()),
            list(candidate.values()),
            lambda row, selected=label: row.prediction == selected if row.truth == selected else None,
        )
        recall_cis[label] = evidence
    evidence = {
        "metrics": metrics,
        "recall_cis": recall_cis,
        "population": population,
        "resamples": resamples,
        "seed": seed,
        "method": "percentile",
        "alpha": 0.05,
        "stage_error_excluded_item_ids": sorted(set(run.items) - set(paired_ids)),
        "candidate_complete_scored_population": {
            "item_ids": candidate_complete_ids,
            "n_items": len(candidate_complete_ids),
            "n_samples": len(candidate_complete_rows),
            "schema_validity": candidate_complete_validity,
        },
    }
    verdict = promotion_verdict(
        macro_f1_ci=metrics["macro_f1"],
        schema_validity=candidate_complete_validity,
        recall_cis=recall_cis,
        evidence=evidence,
    )
    return asdict(verdict)
