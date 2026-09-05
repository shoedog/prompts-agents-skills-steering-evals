"""Markdown rendering for structured report summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
            ]
        )
        if comparison.get("status") == "unavailable":
            lines.extend(["", "evidence unavailable: 0 surviving pairs.", ""])
            continue
        lines.extend(
            [
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
            label = name
            if name == "p95_latency_ms":
                descriptor = evidence["population"]
                label = (
                    "p95_latency_ms "
                    f"(population={descriptor['kind']}, n={descriptor['n_calls']})"
                )
            lines.append(
                f"| {label} | {_fmt(evidence['baseline'])} | {_fmt(evidence['candidate'])} | "
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
            "## Contamination risk bands",
            "",
            "| Version | Risk band | Declared items | Scored items | Scored samples | Macro F1 | Schema-valid rate | Brier | Stage-error calls |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for version, values in summary["versions"].items():
        for band, band_values in values["risk_bands"].items():
            population = band_values["population"]
            classification = band_values["classification"]
            lines.append(
                f"| {version} | {band} | {population['n_declared_items']} | "
                f"{population['n_scored_items']} | {population['n_scored_samples']} | "
                f"{_fmt(classification['macro_f1'])} | "
                f"{_fmt(classification['schema_valid_for_eval']['rate'])} | "
                f"{_fmt(band_values['calibration']['score'])} | "
                f"{band_values['stage_errors']['calls']} |"
            )

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
            f"run p95 ms (population=run, n={summary['run_cost']['population']['n_calls']}): "
            f"{_fmt(summary['run_cost']['p95_ms'])}",
            "",
            "| Version | Calls | Total USD | Cache hit rate | p50 ms | p95 ms (population=version) | Stage-error calls |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for version, values in summary["versions"].items():
        cost = values["cost"]
        lines.append(
            f"| {version} | {cost['calls']} | {_fmt(cost['cost_usd'])} | "
            f"{_fmt(values['cache_hit_rate'])} | {_fmt(cost['p50_ms'])} | "
            f"{_fmt(cost['p95_ms'])} (n={cost['population']['n_calls']}) | "
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
