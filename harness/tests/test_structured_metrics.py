"""Pure structured-evaluation metric tests; no provider calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.metrics import wilson_ci
from harness.structured.metrics import (
    ScoredSample,
    classification_metrics,
    cost_latency,
    normalize_sample,
)


FIXTURE = Path(__file__).parent / "fixtures/metrics/eval3-truth-table.json"


def load_truth_table() -> list[dict]:
    return json.loads(FIXTURE.read_text())


def scored(
    item_id: str,
    *,
    truth: str,
    prediction: str | None,
    confidence: float | None,
    schema_valid: bool,
    first_tier_valid: bool = True,
    first_tier_sentinel: bool = False,
    final_sentinel: bool = False,
    escalation_state: str = "first_valid",
    sentinel_kind: str = "none",
) -> ScoredSample:
    forced_penalty = sentinel_kind != "none" or not schema_valid
    return ScoredSample(
        item_id=item_id,
        truth=truth,
        first_tier_valid=first_tier_valid,
        first_tier_sentinel=first_tier_sentinel,
        final_sentinel=final_sentinel,
        escalation_state=escalation_state,
        sentinel_kind=sentinel_kind,
        schema_valid_for_eval=schema_valid,
        repaired=not first_tier_valid,
        prediction=prediction,
        brier_confidence=0.0 if forced_penalty else confidence,
        brier_correct=False if forced_penalty else prediction == truth,
    )


def test_invalid_output_is_a_miss_for_truth_and_not_precision_credit():
    rows = [
        scored("a", truth="fatal", prediction="fatal", confidence=0.8, schema_valid=True),
        scored("b", truth="retry", prediction=None, confidence=None, schema_valid=False),
    ]
    metrics = classification_metrics(rows, classes=("fatal", "retry", "never_predicted"))
    assert metrics["confusion"]["retry"]["__invalid__"] == 1
    assert metrics["per_class"]["retry"]["recall"] == 0.0
    assert metrics["per_class"]["never_predicted"]["recall"] == 0.0
    assert "__invalid__" not in metrics["per_class"]


@pytest.mark.parametrize("case", load_truth_table(), ids=lambda case: case["id"])
def test_eval3_truth_table(case):
    envelope = case["call"]["llm_envelope"]
    assert {
        "first_tier_valid": envelope["first_tier_valid"],
        "first_tier_sentinel": envelope["first_tier_sentinel"],
        "final_sentinel": envelope["final_sentinel"],
        "escalation_state": envelope["escalation_state"],
        "final_class": envelope["response"]["class"],
        "final_confidence": envelope["response"]["confidence"],
        "sentinel_kind": case["call"]["sentinel_kind"],
    } == {
        key: case[key]
        for key in (
            "first_tier_valid",
            "first_tier_sentinel",
            "final_sentinel",
            "escalation_state",
            "final_class",
            "final_confidence",
            "sentinel_kind",
        )
    }
    actual = normalize_sample(case["call"], final_document_valid=case["final_document_valid"])
    assert {
        "schema_valid_for_eval": actual.schema_valid_for_eval,
        "repaired": actual.repaired,
        "prediction": actual.prediction,
        "brier_confidence": actual.brier_confidence,
        "brier_correct": actual.brier_correct,
    } == case["expected"]


def test_declared_class_metrics_and_validity_accounting_are_hand_checkable():
    rows = [
        scored("a", truth="fatal", prediction="fatal", confidence=0.9, schema_valid=True),
        scored(
            "b",
            truth="fatal",
            prediction="retry",
            confidence=0.6,
            schema_valid=True,
            first_tier_valid=False,
        ),
        scored("c", truth="retry", prediction="retry", confidence=0.7, schema_valid=True),
        scored(
            "d",
            truth="never_predicted",
            prediction=None,
            confidence=None,
            schema_valid=False,
            first_tier_valid=False,
        ),
    ]

    result = classification_metrics(rows, classes=("fatal", "retry", "never_predicted"))

    assert result["n"] == 4
    assert result["per_class"]["fatal"] == pytest.approx(
        {"tp": 1, "fp": 0, "fn": 1, "precision": 1.0, "recall": 0.5, "f1": 2 / 3}
    )
    assert result["per_class"]["retry"] == pytest.approx(
        {"tp": 1, "fp": 1, "fn": 0, "precision": 0.5, "recall": 1.0, "f1": 2 / 3}
    )
    assert result["per_class"]["never_predicted"] == {
        "tp": 0,
        "fp": 0,
        "fn": 1,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }
    assert result["macro_f1"] == pytest.approx(4 / 9)
    assert result["first_tier_valid"] == {
        "k": 2,
        "n": 4,
        "rate": 0.5,
        "wilson_ci": wilson_ci(2, 4),
    }
    assert result["schema_valid_for_eval"] == {
        "k": 3,
        "n": 4,
        "rate": 0.75,
        "wilson_ci": wilson_ci(3, 4),
    }
    assert result["repaired"] == {"count": 2, "n": 4, "rate": 0.5}


def test_classification_rejects_truth_outside_manifest_classes():
    rows = [scored("a", truth="unknown", prediction="fatal", confidence=0.8, schema_valid=True)]
    with pytest.raises(ValueError, match="truth label.*not declared"):
        classification_metrics(rows, classes=("fatal",))


def test_cost_latency_sums_full_call_population_and_linearly_interpolates():
    calls = [
        {"llm_envelope": {"cost_usd": 0.01}, "duration_ms": 30},
        {"cost_usd": 0.02, "duration_ms": 0},
        {"cost_usd": 0.03, "duration_ms": 20},
        {"cost_usd": 0.04, "duration_ms": 10},
    ]
    result = cost_latency(calls)
    assert result == {
        "calls": 4,
        "cost_usd": pytest.approx(0.1),
        "p50_ms": pytest.approx(15.0),
        "p95_ms": pytest.approx(28.5),
    }


def test_cost_latency_empty_population_is_explicit():
    assert cost_latency([]) == {"calls": 0, "cost_usd": 0.0, "p50_ms": None, "p95_ms": None}


@pytest.mark.parametrize("field", ["cost_usd", "duration_ms"])
def test_cost_latency_rejects_missing_or_non_numeric_values(field):
    call = {"cost_usd": 0.1, "duration_ms": 10}
    call[field] = None
    with pytest.raises(ValueError, match=field):
        cost_latency([call])
