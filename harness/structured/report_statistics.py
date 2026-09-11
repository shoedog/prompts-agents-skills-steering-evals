"""Statistical primitives for structured run reports."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from harness.metrics import mcnemar_p
from harness.stats.bootstrap import paired_delta_ci, percentile
from harness.stats.paired import flips
from harness.structured.assertion_context import call_number
from harness.structured.calibration import brier, cohen_kappa
from harness.structured.metrics import (
    INVALID_PREDICTION,
    ScoredSample,
    classification_metrics,
    normalize_sample,
)

def _version_names(config: Mapping[str, Any]) -> tuple[str, ...]:
    versions = config.get("versions")
    if not isinstance(versions, list) or not versions:
        raise ValueError("snapshot config versions must be a nonempty array")
    names = tuple(version.get("name") for version in versions if isinstance(version, dict))
    if len(names) != len(versions) or any(not isinstance(name, str) for name in names):
        raise ValueError("every snapshot config version must have a name")
    return names


def _prediction(row: ScoredSample) -> str:
    if not row.schema_valid_for_eval or row.prediction is None:
        return INVALID_PREDICTION
    return row.prediction


def _flatten_scored(bundles: Sequence[dict[str, Any]]) -> list[ScoredSample]:
    return [row for bundle in bundles for row in bundle["scored"]]


def _flatten_calls(bundles: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for bundle in bundles for call in bundle["calls"]]


def _classification_stat(classes: Sequence[str], field: str, label: str | None = None):
    def statistic(bundles: Sequence[dict[str, Any]]) -> float:
        reduced = classification_metrics(_flatten_scored(bundles), classes)
        if field == "macro_f1":
            return float(reduced["macro_f1"])
        assert label is not None
        return float(reduced["per_class"][label][field])

    return statistic


def _schema_validity(bundles: Sequence[dict[str, Any]]) -> float:
    rows = _flatten_scored(bundles)
    return sum(row.schema_valid_for_eval for row in rows) / len(rows)


def _brier_score(bundles: Sequence[dict[str, Any]]) -> float:
    return float(brier(_flatten_scored(bundles))["score"])


def _kappa(classes: Sequence[str]):
    def statistic(bundles: Sequence[dict[str, Any]]) -> float:
        rows = _flatten_scored(bundles)
        return cohen_kappa(
            [row.truth for row in rows],
            [_prediction(row) for row in rows],
            classes,
        )

    return statistic


def _cost_per_item(bundles: Sequence[dict[str, Any]]) -> float:
    return math.fsum(call_number(call, "cost_usd") for call in _flatten_calls(bundles)) / len(
        bundles
    )


def _p95_latency(bundles: Sequence[dict[str, Any]]) -> float:
    durations = [call_number(call, "duration_ms") for call in _flatten_calls(bundles)]
    return percentile(durations, 0.95)


def _paired_binary_p(
    baseline: Sequence[dict[str, Any]],
    candidate: Sequence[dict[str, Any]],
    outcome: Callable[[ScoredSample], bool | None],
) -> float:
    rows_a = []
    rows_b = []
    for side, target in ((baseline, rows_a), (candidate, rows_b)):
        for bundle in side:
            for sample, row in enumerate(bundle["scored"]):
                passed = outcome(row)
                if passed is not None:
                    target.append(
                        {
                            "item_id": f"{bundle['item_id']}:s{sample}",
                            "item_pass": passed,
                        }
                    )
    counts = flips(rows_a, rows_b)
    return mcnemar_p(counts["only_baseline"], counts["only_treatment"])


def _metric_evidence(
    baseline: Mapping[str, dict[str, Any]],
    candidate: Mapping[str, dict[str, Any]],
    statistic: Callable[[Sequence[dict[str, Any]]], float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    keys = sorted(baseline)
    baseline_rows = [baseline[key] for key in keys]
    candidate_rows = [candidate[key] for key in keys]
    interval = paired_delta_ci(
        baseline,
        candidate,
        statistic,
        resamples=resamples,
        seed=seed,
    )
    return {
        "baseline": statistic(baseline_rows),
        "candidate": statistic(candidate_rows),
        **interval,
        "n_items": len(keys),
    }


def _normalized_call(call: Mapping[str, Any], item: Mapping[str, Any]) -> ScoredSample:
    valid = call.get("final_document_valid")
    if not isinstance(valid, bool):
        raise ValueError(
            f"call {call.get('version')}/{call.get('item_id')}/s{call.get('sample')} "
            "must record final_document_valid"
        )
    return normalize_sample({**call, "expected": item["expected"]}, final_document_valid=valid)


def _version_identity(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    entry = next(version for version in config["versions"] if version["name"] == name)
    provider = entry.get("provider", {})
    return {
        "task_version": entry.get("task_version"),
        "provider": provider.get("kind") if isinstance(provider, Mapping) else None,
        "model": provider.get("model") if isinstance(provider, Mapping) else None,
    }


def _human_kappa(
    _items: Mapping[str, Mapping[str, Any]], _classes: Sequence[str]
) -> dict[str, Any]:
    """Report the current taskset's explicit inability to reconstruct this κ."""
    return {
        "value": None,
        "n_items": 0,
        "basis": "unavailable: taskset labels retain agreement flags, not secondary classes",
    }
