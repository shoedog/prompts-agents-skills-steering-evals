"""Per-version reductions for authenticated structured runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from harness.structured.assertion_context import assertion_context
from harness.structured.asserts import run_asserts
from harness.structured.calibration import brier, cohen_kappa
from harness.structured.metrics import (
    INVALID_PREDICTION,
    ScoredSample,
    classification_metrics,
    cost_latency,
)
from harness.structured.report_statistics import (
    _normalized_call,
    _prediction,
    _version_identity,
    _version_names,
)

_RISK_BANDS = ("low", "medium", "high")

def _assert_rows(
    run: Any,
    calls_by_version_item: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    classes: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cfg = {**run.config, "classes": list(classes)}
    for version in _version_names(run.config):
        excluded_item_ids = _stage_error_item_ids(calls_by_version_item[version])
        for item_id in sorted(calls_by_version_item[version]):
            if item_id in excluded_item_ids:
                continue
            item_calls = calls_by_version_item[version][item_id]
            context = assertion_context(run.calls, version=version, item_id=item_id)
            if context is None:
                continue
            item_samples, populations = context
            for call in item_calls:
                envelope = call.get("llm_envelope")
                output = envelope.get("response") if isinstance(envelope, Mapping) else None
                if not isinstance(output, dict):
                    output = None
                results = run_asserts(
                    output=output,
                    raw=str(call.get("raw", "")),
                    expected=run.items[item_id]["expected"],
                    item=run.items[item_id],
                    cfg=cfg,
                    samples=item_samples,
                    populations=populations,
                )
                failed = [result for result in results if not result.passed]
                scored = _normalized_call(call, run.items[item_id])
                confidence = scored.brier_confidence if scored.brier_confidence is not None else 0.0
                forced = (
                    not scored.schema_valid_for_eval
                    or scored.sentinel_kind != "none"
                    or scored.prediction == INVALID_PREDICTION
                )
                loss = 1.0 if forced else abs(confidence - float(_prediction(scored) == scored.truth))
                rows.append(
                    {
                        "item_id": item_id,
                        "version": version,
                        "sample": call["sample"],
                        "expected": scored.truth,
                        "predicted": _prediction(scored),
                        "confidence": confidence,
                        "loss": loss,
                        "hard_failure": any(not result.passed and result.hard for result in results),
                        "first_failing_assert": failed[0].detail if failed else "none",
                        "replay_key": call.get(
                            "replay_key", f"{version}/{item_id}/s{call['sample']}"
                        ),
                        "asserts": [asdict(result) for result in results],
                    }
                )
    return rows


def _stage_error_item_ids(grouped: Mapping[str, Sequence[Mapping[str, Any]]]) -> set[str]:
    return {
        item_id
        for item_id, calls in grouped.items()
        if any(call.get("stage_error") for call in calls)
    }


def _cost_population(calls: Sequence[dict[str, Any]], kind: str) -> dict[str, Any]:
    reduced = cost_latency(calls)
    reduced["population"] = {
        "kind": kind,
        "n_calls": len(calls),
        "n_items": len({call["item_id"] for call in calls}),
        "n_versions": len({call["version"] for call in calls}),
    }
    return reduced


def _call_population(run: Any, versions: Sequence[str]) -> dict[str, dict[str, list[dict]]]:
    grouped: dict[str, dict[str, list[dict]]] = {
        version: {item_id: [] for item_id in run.items} for version in versions
    }
    seen: set[tuple[str, str, int]] = set()
    for call in run.calls:
        version = call.get("version")
        item_id = call.get("item_id")
        sample = call.get("sample")
        identity = (version, item_id, sample)
        if (
            version not in grouped
            or item_id not in run.items
            or not isinstance(sample, int)
            or isinstance(sample, bool)
        ):
            raise ValueError(f"call has unknown identity: {identity}")
        if identity in seen:
            raise ValueError(f"duplicate call identity: {identity}")
        seen.add(identity)
        grouped[version][item_id].append(call)
    expected = {
        (version, item_id, sample)
        for version in versions
        for item_id in run.items
        for sample in range(run.config["samples_per_item"])
    }
    if seen != expected:
        raise ValueError(
            f"call identity set mismatch: missing={sorted(expected - seen)}, "
            f"extra={sorted(seen - expected)}"
        )
    for version in versions:
        for item_id in run.items:
            grouped[version][item_id].sort(key=lambda call: call["sample"])
    return grouped


def _risk_band_summaries(
    run: Any,
    grouped: Mapping[str, list[dict]],
    classes: Sequence[str],
) -> dict[str, Any]:
    declared: dict[str, list[str]] = {band: [] for band in _RISK_BANDS}
    manifest_items = {
        item.get("id"): item for item in run.manifest.get("items", ())
    }
    for item_id in sorted(run.items):
        manifest_item = manifest_items.get(item_id)
        if not isinstance(manifest_item, Mapping):
            raise ValueError(f"manifest has no item summary for {item_id!r}")
        band = manifest_item.get("contamination_risk")
        if band not in declared:
            raise ValueError(f"item {item_id!r} has invalid contamination_risk {band!r}")
        item_band = run.items[item_id].get("contamination_risk")
        if item_band is not None and item_band != band:
            raise ValueError(
                f"item {item_id!r} contamination_risk disagrees with manifest"
            )
        declared[band].append(item_id)

    summaries = {}
    for band in _RISK_BANDS:
        item_ids = declared[band]
        band_grouped = {item_id: grouped[item_id] for item_id in item_ids}
        excluded = _stage_error_item_ids(band_grouped)
        scored_item_ids = [item_id for item_id in item_ids if item_id not in excluded]
        scored = [
            _normalized_call(call, run.items[item_id])
            for item_id in scored_item_ids
            for call in grouped[item_id]
        ]
        summaries[band] = {
            "population": {
                "declared_item_ids": item_ids,
                "n_declared_items": len(item_ids),
                "n_scored_items": len(scored_item_ids),
                "n_scored_samples": len(scored),
            },
            "classification": classification_metrics(scored, classes),
            "calibration": brier(scored),
            "stage_errors": {
                "calls": sum(
                    bool(call.get("stage_error"))
                    for item_id in item_ids
                    for call in grouped[item_id]
                ),
                "item_ids": sorted(excluded),
            },
        }
    return summaries


def _version_summary(
    run: Any,
    version: str,
    grouped: Mapping[str, list[dict]],
    classes: Sequence[str],
    human_kappa: dict[str, Any],
) -> tuple[dict[str, Any], list[ScoredSample]]:
    excluded_item_ids = _stage_error_item_ids(grouped)
    stage_error_calls = [
        call for item_id in sorted(grouped) for call in grouped[item_id] if call.get("stage_error")
    ]
    calls = [call for item_id in sorted(grouped) for call in grouped[item_id]]
    scored = [
        _normalized_call(call, run.items[item_id])
        for item_id in sorted(grouped)
        for call in grouped[item_id]
        if item_id not in excluded_item_ids
    ]
    classification = classification_metrics(scored, classes)
    calibration = brier(scored)
    costs = _cost_population(calls, "version")
    predictions = [_prediction(row) for row in scored]
    return (
        {
            "identity": _version_identity(run.config, version),
            "classification": classification,
            "calibration": calibration,
            "kappa_vs_human": cohen_kappa(
                [row.truth for row in scored], predictions, classes
            ),
            "human_vs_human": human_kappa,
            "risk_bands": _risk_band_summaries(run, grouped, classes),
            "cost": costs,
            "cache_hit_rate": (
                sum(bool(call["llm_envelope"].get("cache_hit")) for call in calls) / len(calls)
                if calls
                else 0.0
            ),
            "stage_errors": {
                "calls": len(stage_error_calls),
                "item_ids": sorted(excluded_item_ids),
            },
        },
        scored,
    )
