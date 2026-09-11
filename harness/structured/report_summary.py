"""Top-level structured report summary assembly."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from harness.structured.metrics import ScoredSample
from harness.structured.report_comparison import _comparison
from harness.structured.report_reduction import (
    _assert_rows,
    _call_population,
    _cost_population,
    _version_summary,
)
from harness.structured.report_statistics import _human_kappa, _version_names

if TYPE_CHECKING:
    from harness.structured.replay import LoadedRun

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
        "run_cost": _cost_population(list(run.calls), "run"),
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
