from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from harness.structured.replay import LoadedRun
from harness.structured.report import render, summarize


REPORT_GOLDEN = Path(__file__).parent / "golden/structured/report.md"
METRICS_GOLDEN = Path(__file__).parent / "golden/structured/metrics.json"
STRUCTURED_FIXTURE = (
    Path(__file__).parent
    / "fixtures/structured/results/st-fixture/20260905T120000Z-fixture"
)
CLASSES = ("correct", "swallowed_fatal")


def make_frozen_structured_run(root: Path) -> LoadedRun:
    run_path = (
        root
        / "results"
        / "st-fixture"
        / "20260905T120000Z-fixture"
    )
    shutil.copytree(STRUCTURED_FIXTURE, run_path)
    return LoadedRun.load(run_path)


@pytest.fixture
def frozen_structured_run(tmp_path: Path) -> LoadedRun:
    return make_frozen_structured_run(tmp_path)


def test_report_matches_golden(frozen_structured_run):
    render(frozen_structured_run)
    assert (frozen_structured_run.path / "report.md").read_bytes() == REPORT_GOLDEN.read_bytes()
    assert (frozen_structured_run.path / "metrics.json").read_bytes() == METRICS_GOLDEN.read_bytes()


def test_render_appends_one_trend_row_per_candidate_and_preserves_prefix(
    frozen_structured_run,
):
    trend_path = (
        frozen_structured_run.path.parents[1]
        / "trends"
        / "classify_error_handling.jsonl"
    )
    assert not trend_path.exists()

    summary = render(frozen_structured_run)
    first = trend_path.read_bytes()
    rows = [json.loads(line) for line in first.splitlines()]
    assert [row["version"] for row in rows] == ["candidate", "candidate-alt"]
    assert len(rows) == len(summary["promotions"])
    assert rows[0] == {
        "ts": "2026-09-05T12:00:00Z",
        "task": "classify_error_handling",
        "experiment": "st-fixture",
        "run_id": "20260905T120000Z-fixture",
        "split": "dev",
        "version": "candidate",
        "baseline_version": "baseline",
        "n_items": 2,
        "macro_f1": 1.0,
        "delta_macro_f1": pytest.approx(2 / 3),
        "delta_ci": [0.0, pytest.approx(2 / 3)],
        "schema_validity": 1.0,
        "brier": pytest.approx(0.0125),
        "kappa_vs_human": 1.0,
        "cost_usd": 0.04,
        "p95_ms": 177.0,
        "promotable": True,
    }

    second_path = frozen_structured_run.path.with_name("20260905T130000Z-fixture")
    shutil.copytree(STRUCTURED_FIXTURE, second_path)
    render(LoadedRun.load(second_path))
    assert trend_path.read_bytes().startswith(first)
    assert len(trend_path.read_bytes().splitlines()) == 4


def test_render_rejects_missing_candidate_task_version_before_writing(
    frozen_structured_run,
):
    frozen_structured_run.config["versions"][1].pop("task_version")
    trend_path = (
        frozen_structured_run.path.parents[1]
        / "trends"
        / "classify_error_handling.jsonl"
    )

    with pytest.raises(
        ValueError,
        match="structured version candidate must have a nonempty task_version",
    ):
        render(frozen_structured_run)

    assert not (frozen_structured_run.path / "report.md").exists()
    assert not (frozen_structured_run.path / "metrics.json").exists()
    assert not trend_path.exists()


def test_report_order_and_required_evidence_are_explicit(frozen_structured_run):
    summary = render(frozen_structured_run)
    report = (frozen_structured_run.path / "report.md").read_text()
    headings = [
        "# Structured evaluation report",
        "## Paired deltas",
        "## Confusion matrices",
        "## Worst 10 by loss",
        "## Cost and provenance",
    ]
    assert [report.index(heading) for heading in headings] == sorted(
        report.index(heading) for heading in headings
    )
    for text in (
        "percentile",
        "resamples: 40",
        "seed: 20260904",
        "stage-error exclusions",
        "first-tier validity",
        "schema_valid_for_eval",
        "sentinel and `__invalid__` rows receive maximum Brier penalty",
        "model-vs-human",
        "human-vs-human",
        "population sha256",
    ):
        assert text in report
    evidence = summary["promotions"]["candidate"]["evidence"]
    assert evidence["population"]["n_items"] == 2
    assert set(evidence["metrics"]) >= {
        "macro_f1",
        "schema_validity",
    }
    assert set(evidence["recall_cis"]) == set(CLASSES)


def test_machine_reduction_omits_only_bulky_rows(frozen_structured_run):
    full = summarize(frozen_structured_run)
    render(frozen_structured_run)
    machine = json.loads((frozen_structured_run.path / "metrics.json").read_bytes())
    assert "calls" in full and "scored_rows" in full and "worst_rows" in full
    assert set(full) - set(machine) == {"calls", "scored_rows", "worst_rows"}
    assert machine["promotions"]["candidate"]["evidence"]["population"]["sha256"]


def test_human_kappa_is_unavailable_when_secondary_classes_are_not_retained(
    frozen_structured_run,
):
    frozen_structured_run.items["eh-py-0002"]["labels"]["secondary"]["agrees"] = False

    values = summarize(frozen_structured_run)["versions"]["baseline"]["human_vs_human"]

    assert values == {
        "value": None,
        "n_items": 0,
        "basis": "unavailable: taskset labels retain agreement flags, not secondary classes",
    }


def test_promotion_validity_uses_candidate_complete_scored_population(
    frozen_structured_run,
):
    for call in frozen_structured_run.calls:
        if call["version"] == "baseline" and call["item_id"] == "eh-py-0002":
            call["stage_error"] = "classify"
        if call["version"] == "candidate" and call["item_id"] == "eh-py-0002":
            call["final_document_valid"] = False

    summary = summarize(frozen_structured_run)
    verdict = summary["promotions"]["candidate"]

    assert summary["versions"]["candidate"]["classification"][
        "schema_valid_for_eval"
    ]["rate"] == 0.5
    assert verdict["promotable"] is False
    assert "schema_validity=0.5" in verdict["reason"]
    assert verdict["evidence"]["candidate_complete_scored_population"] == {
        "item_ids": ["eh-py-0001", "eh-py-0002"],
        "n_items": 2,
        "n_samples": 2,
        "schema_validity": 0.5,
    }
