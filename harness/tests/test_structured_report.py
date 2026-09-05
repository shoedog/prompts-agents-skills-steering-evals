from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from harness.structured.replay import LoadedRun
from harness.structured.report import render, summarize
from harness.structured.results import ResultsWriter, canonical_json
from harness.structured.snapshots import write_input_snapshots


REPORT_GOLDEN = Path(__file__).parent / "golden/structured/report.md"
METRICS_GOLDEN = Path(__file__).parent / "golden/structured/metrics.json"
CLASSES = ("correct", "swallowed_fatal")


def _response(label: str, confidence: float) -> dict:
    return {
        "class": label,
        "confidence": confidence,
        "rationale": "fixture evidence",
        "evidence_lines": [11],
    }


def _call(
    *,
    item_id: str,
    version: str,
    label: str,
    confidence: float,
    cost: float,
    duration: int,
    cache_hit: bool,
) -> dict:
    response = _response(label, confidence)
    return {
        "item_id": item_id,
        "version": version,
        "sample": 0,
        "final_document_valid": True,
        "sentinel_kind": "none",
        "raw": json.dumps(response, sort_keys=True),
        "duration_ms": duration,
        "replay_key": f"{version}/{item_id}/s0",
        "llm_envelope": {
            "schema_version": "1",
            "invocation_id": f"inv-{version}-{item_id}",
            "task": "classify_error_handling",
            "task_version": "baseline" if version == "baseline" else "candidate",
            "provider": "fixture",
            "model": "fixture-model",
            "provider_version": "fixture-1",
            "prompt_sha256": "a" * 64,
            "escalation_state": "first_valid",
            "first_tier_valid": True,
            "first_tier_sentinel": False,
            "final_sentinel": False,
            "cache_hit": cache_hit,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "cost_usd": cost,
            "response": response,
            "log_path": "fixture.jsonl",
        },
    }


def make_frozen_structured_run(root: Path) -> LoadedRun:
    run_path = root / "20260905T120000Z-fixture"
    writer = ResultsWriter(run_path)
    response_schema = {
        "type": "object",
        "required": ["class", "confidence", "rationale"],
        "additionalProperties": False,
        "properties": {
            "class": {"enum": list(CLASSES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
            "evidence_lines": {"type": "array", "items": {"type": "integer"}},
        },
    }
    request_schema = {
        "type": "object",
        "required": ["task", "task_version", "item_id"],
        "additionalProperties": False,
        "properties": {
            "task": {"const": "classify_error_handling"},
            "task_version": {"type": "string"},
            "item_id": {"type": "string"},
        },
    }
    config = {
        "kind": "structured_task",
        "id": "st-fixture",
        "task": "classify_error_handling",
        "taskset": "fixture-taskset",
        "split": "dev",
        "versions": [
            {
                "name": "baseline",
                "task_version": "baseline",
                "provider": {"kind": "fixture", "model": "fixture-model"},
            },
            {
                "name": "candidate",
                "task_version": "candidate",
                "provider": {"kind": "fixture", "model": "fixture-model"},
            },
        ],
        "baseline_version": "baseline",
        "samples_per_item": 1,
        "seed": 20260904,
        "asserts": [
            {"type": "schema", "hard": True},
            {"type": "label", "mode": "exact", "field": "class"},
        ],
        "stats": {"bootstrap_resamples": 40, "seed": 20260904},
        "request_schema": request_schema,
        "response_schema": response_schema,
    }
    manifest = {
        "taskset": "fixture-taskset",
        "schema_version": 2,
        "task": "classify_error_handling",
        "class_field": "class",
        "classes": list(CLASSES),
        "splits": {"dev": {"items": 2, "min_per_class": 1}},
        "items": [
            {"id": "eh-py-0001", "split": "dev", "contamination_risk": "low"},
            {"id": "eh-py-0002", "split": "dev", "contamination_risk": "low"},
        ],
    }
    items = {
        "eh-py-0001": {
            "id": "eh-py-0001",
            "task": "classify_error_handling",
            "expected": {"label": "correct"},
            "labels": {
                "primary": {"by": "a", "at": "2026-09-04"},
                "secondary": {"by": "b", "at": "2026-09-04", "agrees": True},
            },
        },
        "eh-py-0002": {
            "id": "eh-py-0002",
            "task": "classify_error_handling",
            "expected": {"label": "swallowed_fatal"},
            "labels": {
                "primary": {"by": "a", "at": "2026-09-04"},
                "secondary": {"by": "b", "at": "2026-09-04", "agrees": True},
            },
        },
    }
    requests = {}
    for item_id in sorted(items):
        requests[(item_id, 0)] = {
            version: {
                "task": "classify_error_handling",
                "task_version": version,
                "item_id": item_id,
            }
            for version in ("baseline", "candidate")
        }
    write_input_snapshots(
        writer,
        config=config,
        manifest=manifest,
        items=items,
        requests=requests,
    )
    calls = (
        _call(
            item_id="eh-py-0001",
            version="baseline",
            label="swallowed_fatal",
            confidence=0.8,
            cost=0.01,
            duration=100,
            cache_hit=False,
        ),
        _call(
            item_id="eh-py-0002",
            version="baseline",
            label="swallowed_fatal",
            confidence=0.9,
            cost=0.02,
            duration=200,
            cache_hit=True,
        ),
        _call(
            item_id="eh-py-0001",
            version="candidate",
            label="correct",
            confidence=0.95,
            cost=0.015,
            duration=120,
            cache_hit=False,
        ),
        _call(
            item_id="eh-py-0002",
            version="candidate",
            label="swallowed_fatal",
            confidence=0.85,
            cost=0.025,
            duration=180,
            cache_hit=True,
        ),
    )
    for call in calls:
        filename = f"{call['version']}-{call['item_id']}-{call['sample']}.json"
        writer.write_json_once(PurePosixPath("calls", filename), call)
        writer.write_json_once(
            PurePosixPath("asserts", filename),
            {"stored_only": True, "must_not_be_metric_authority": True},
        )
    return LoadedRun.load(run_path)


@pytest.fixture
def frozen_structured_run(tmp_path: Path) -> LoadedRun:
    return make_frozen_structured_run(tmp_path)


def test_report_matches_golden(frozen_structured_run):
    render(frozen_structured_run)
    assert (frozen_structured_run.path / "report.md").read_bytes() == REPORT_GOLDEN.read_bytes()
    assert (frozen_structured_run.path / "metrics.json").read_bytes() == METRICS_GOLDEN.read_bytes()


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
