"""Deterministic reductions and reports for authenticated structured runs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness.metrics import mcnemar_p
from harness.stats.bootstrap import paired_delta_ci, percentile
from harness.stats.paired import flips
from harness.structured.assertion_context import assertion_context, call_number
from harness.structured.asserts import run_asserts
from harness.structured.calibration import brier, cohen_kappa
from harness.structured.metrics import (
    INVALID_PREDICTION,
    ScoredSample,
    classification_metrics,
    cost_latency,
    normalize_sample,
)
from harness.structured.promotion import promotion_verdict
from harness.structured.results import canonical_json
from harness.structured.trends import append_trend


if TYPE_CHECKING:
    from harness.structured.replay import LoadedRun


_BULKY_KEYS = {"calls", "scored_rows", "worst_rows"}
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z(?:-.+)?$")
_TREND_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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
    costs = cost_latency(calls)
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
    if not paired_ids:
        raise ValueError(f"no stage-error-free paired items for candidate {candidate_name}")
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
    )
    resamples = run.config["stats"]["bootstrap_resamples"]
    seed = run.config["stats"]["seed"]
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


def summarize(run: LoadedRun) -> dict[str, Any]:
    """Recompute assertions, metrics, paired evidence, and promotion from stored records."""
    versions = _version_names(run.config)
    baseline = run.config.get("baseline_version")
    if baseline not in versions:
        raise ValueError("baseline_version does not name a configured version")
    candidates = tuple(version for version in versions if version != baseline)
    classes = tuple(run.manifest.get("classes", ()))
    if not classes:
        raise ValueError("snapshot manifest must declare classes")
    grouped = _call_population(run, versions)
    human = _human_kappa(run.items, classes)
    version_summaries: dict[str, Any] = {}
    scored_by_version: dict[str, list[ScoredSample]] = {}
    for version in versions:
        version_summaries[version], scored_by_version[version] = _version_summary(
            run, version, grouped[version], classes, human
        )
    promotions = {}
    for candidate in candidates:
        promotions[candidate] = _comparison(
            run, baseline, candidate, grouped, classes
        )
    assert_rows = _assert_rows(run, grouped, classes)
    worst = sorted(
        assert_rows,
        key=lambda row: (
            not row["hard_failure"],
            -row["loss"],
            row["item_id"],
            row["version"],
            row["sample"],
        ),
    )[:10]
    config_sha256 = next(
        entry.sha256
        for entry in run.input_index.entries
        if entry.path == "inputs/config.json"
    )
    return {
        "experiment": {
            "id": run.config.get("id"),
            "kind": run.config.get("kind"),
            "run_id": run.path.name,
            "config_sha256": config_sha256,
            "task": run.config.get("task", run.manifest.get("task")),
            "taskset": run.config.get("taskset", run.manifest.get("taskset")),
            "split": run.config.get("split"),
            "n_items": len(run.items),
            "inputs_index_sha256": run.input_index.sha256,
        },
        "stats": {
            "resamples": run.config["stats"]["bootstrap_resamples"],
            "seed": run.config["stats"]["seed"],
            "method": "percentile",
            "alpha": 0.05,
        },
        "versions": version_summaries,
        "promotions": promotions,
        "recomputed_assert_records": len(assert_rows),
        "stored_assert_records": len(run.asserts),
        "calls": list(run.calls),
        "scored_rows": {
            version: [asdict(row) for row in rows]
            for version, rows in scored_by_version.items()
        },
        "worst_rows": worst,
    }


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:.6f}"
    return str(value)


def _confusion_table(confusion: Mapping[str, Mapping[str, int]]) -> list[str]:
    columns = []
    for row in confusion.values():
        for label in row:
            if label not in columns:
                columns.append(label)
    lines = [
        "| Expected \\ Predicted | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for truth, row in confusion.items():
        lines.append(
            f"| {truth} | " + " | ".join(str(row.get(label, 0)) for label in columns) + " |"
        )
    return lines


def _report_markdown(summary: Mapping[str, Any]) -> str:
    experiment = summary["experiment"]
    stats = summary["stats"]
    lines = [
        "# Structured evaluation report",
        "",
        f"- experiment: {experiment['id']}",
        f"- kind: {experiment['kind']}",
        f"- run id: {experiment['run_id']}",
        f"- config sha256: `{experiment['config_sha256']}`",
        f"- taskset / split: {experiment['taskset']} / {experiment['split']}",
        f"- item count: {experiment['n_items']}",
        f"- bootstrap: method={stats['method']}, resamples: {stats['resamples']}, seed: {stats['seed']}, alpha={stats['alpha']}",
    ]
    for version, values in summary["versions"].items():
        identity = values["identity"]
        lines.append(
            f"- version {version}: provider={identity['provider']}, model={identity['model']}, "
            f"task_version={identity['task_version']}"
        )
    for candidate, verdict in summary["promotions"].items():
        lines.append(f"- promotion verdict for {candidate}: {verdict['reason']}")

    lines.extend(["", "## Paired deltas", ""])
    for candidate, verdict in summary["promotions"].items():
        comparison = verdict["evidence"]
        population = comparison["population"]
        lines.extend(
            [
                f"### {population['baseline_version']} → {candidate}",
                "",
                f"Paired population identity: {population['baseline_version']}→{population['candidate_version']}; "
                f"n items: {population['n_items']}; population sha256: `{population['sha256']}`.",
                "",
                "| Metric | Baseline | Candidate | Delta | CI low | CI high | McNemar p | n items | Seed | Resamples | Population sha256 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        table_rows = list(comparison["metrics"].items()) + [
            (f"recall:{label} (gate)", evidence)
            for label, evidence in comparison["recall_cis"].items()
        ]
        for name, evidence in table_rows:
            lines.append(
                f"| {name} | {_fmt(evidence['baseline'])} | {_fmt(evidence['candidate'])} | "
                f"{_fmt(evidence['delta'])} | {_fmt(evidence['lo'])} | {_fmt(evidence['hi'])} | "
                f"{_fmt(evidence.get('mcnemar_p'))} | {evidence['n_items']} | {comparison['seed']} | "
                f"{comparison['resamples']} | `{population['sha256']}` |"
            )
        noisy = [
            name
            for name, evidence in table_rows
            if evidence["lo"] <= 0.0 <= evidence["hi"]
        ]
        if noisy:
            lines.extend(
                [
                    "",
                    "Caveat: these percentile CIs include 0, so the paired evidence does not "
                    f"separate the versions for: {', '.join(noisy)}.",
                ]
            )

    lines.extend(["", "## Confusion matrices", ""])
    for version, values in summary["versions"].items():
        lines.extend([f"### {version}", "", *_confusion_table(values["classification"]["confusion"]), ""])

    lines.extend(
        [
            "## Worst 10 by loss",
            "",
            "| Hard failure | Loss | Version | Item | Sample | Expected | Predicted | Confidence | First failing assert | Replay key |",
            "|---|---:|---|---|---:|---|---|---:|---|---|",
        ]
    )
    for row in summary["worst_rows"]:
        lines.append(
            f"| {_fmt(row['hard_failure'])} | {_fmt(row['loss'])} | {row['version']} | "
            f"{row['item_id']} | {row['sample']} | {row['expected']} | {row['predicted']} | "
            f"{_fmt(row['confidence'])} | {row['first_failing_assert']} | `{row['replay_key']}` |"
        )

    lines.extend(
        [
            "",
            "## Cost and provenance",
            "",
            "| Version | Calls | Total USD | Cache hit rate | p50 ms | p95 ms | Stage-error calls |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for version, values in summary["versions"].items():
        cost = values["cost"]
        lines.append(
            f"| {version} | {cost['calls']} | {_fmt(cost['cost_usd'])} | "
            f"{_fmt(values['cache_hit_rate'])} | {_fmt(cost['p50_ms'])} | {_fmt(cost['p95_ms'])} | "
            f"{values['stage_errors']['calls']} |"
        )
    lines.append("")
    for version, values in summary["versions"].items():
        classification = values["classification"]
        calibration = values["calibration"]
        lines.extend(
            [
                f"- {version} stage-error exclusions: {values['stage_errors']['item_ids']}",
                f"- {version} first-tier validity: {_fmt(classification['first_tier_valid']['rate'])} "
                f"({classification['first_tier_valid']['k']}/{classification['first_tier_valid']['n']})",
                f"- {version} schema_valid_for_eval: {_fmt(classification['schema_valid_for_eval']['rate'])} "
                f"({classification['schema_valid_for_eval']['k']}/{classification['schema_valid_for_eval']['n']})",
                f"- {version} repaired: {_fmt(classification['repaired']['rate'])} "
                f"({classification['repaired']['count']}/{classification['repaired']['n']})",
                f"- {version} Brier: {_fmt(calibration['score'])}; maximum-penalty rows: "
                f"{calibration['maximum_penalty']}/{calibration['n']}",
                f"- {version} κ model-vs-human: {_fmt(values['kappa_vs_human'])}; "
                f"κ human-vs-human: {_fmt(values['human_vs_human']['value'])} "
                f"(n={values['human_vs_human']['n_items']}; "
                f"{values['human_vs_human']['basis']})",
            ]
        )
    lines.extend(
        [
            "",
            "sentinel and `__invalid__` rows receive maximum Brier penalty and are never excluded.",
            "",
            "> PROVISIONAL — pending human spot-check.",
            "",
        ]
    )
    return "\n".join(lines)


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
        append_trend(trend_path, row)
    return summary
