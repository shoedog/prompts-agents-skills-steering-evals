"""Calibration and agreement tests for structured evaluations."""

from __future__ import annotations

import pytest

from harness.structured.calibration import brier, cohen_kappa
from harness.tests.test_structured_metrics import scored


def test_brier_gives_sentinels_and_invalid_documents_maximum_penalty():
    rows = [
        scored("a", truth="fatal", prediction="fatal", confidence=0.8, schema_valid=True),
        scored("b", truth="retry", prediction="fatal", confidence=0.7, schema_valid=True),
        scored("c", truth="retry", prediction=None, confidence=None, schema_valid=False),
        scored(
            "d",
            truth="fatal",
            prediction="unclear",
            confidence=0.0,
            schema_valid=True,
            final_sentinel=True,
            sentinel_kind="schema",
        ),
    ]
    result = brier(rows)
    assert result["score"] == pytest.approx(
        ((0.8 - 1.0) ** 2 + (0.7 - 0.0) ** 2 + 1.0 + 1.0) / 4
    )
    assert result["n"] == 4
    assert result["maximum_penalty"] == 2


def test_brier_bins_are_half_open_except_the_last_and_include_every_row():
    rows = [
        scored("a", truth="a", prediction="a", confidence=0.0, schema_valid=True),
        scored("b", truth="a", prediction="b", confidence=0.099, schema_valid=True),
        scored("c", truth="a", prediction="a", confidence=0.1, schema_valid=True),
        scored("d", truth="a", prediction="a", confidence=0.999, schema_valid=True),
        scored("e", truth="a", prediction="a", confidence=1.0, schema_valid=True),
        scored("f", truth="a", prediction=None, confidence=None, schema_valid=False),
    ]
    bins = brier(rows)["bins"]
    assert len(bins) == 10
    assert [entry["n"] for entry in bins] == [3, 1, 0, 0, 0, 0, 0, 0, 0, 2]
    assert bins[0]["lower"] == 0.0 and bins[0]["upper"] == 0.1
    assert bins[0]["accuracy"] == pytest.approx(2 / 3)
    assert bins[-1]["lower"] == 0.9 and bins[-1]["upper"] == 1.0
    assert bins[-1]["mean_confidence"] == pytest.approx(0.9995)
    assert bins[-1]["accuracy"] == 1.0


def test_brier_empty_population_has_ten_empty_bins():
    result = brier([])
    assert result["score"] == 0.0
    assert result["n"] == 0
    assert result["maximum_penalty"] == 0
    assert len(result["bins"]) == 10
    assert all(entry["n"] == 0 for entry in result["bins"])


def test_cohen_kappa_matches_hand_worked_binary_example():
    assert cohen_kappa(
        expected=("a", "a", "b", "b"),
        predicted=("a", "b", "b", "b"),
        labels=("a", "b"),
    ) == pytest.approx(0.5)


def test_cohen_kappa_counts_invalid_prediction_as_disagreement():
    assert cohen_kappa(
        expected=("a", "b"),
        predicted=("a", "__invalid__"),
        labels=("a", "b"),
    ) == pytest.approx(1 / 3)


def test_cohen_kappa_returns_one_for_identical_constant_ratings():
    assert cohen_kappa(("a", "a"), ("a", "a"), ("a", "b")) == 1.0


def test_cohen_kappa_rejects_mismatched_lengths_and_undeclared_truth():
    with pytest.raises(ValueError, match="equal-length"):
        cohen_kappa(("a",), ("a", "b"), ("a", "b"))
    with pytest.raises(ValueError, match="expected label.*not declared"):
        cohen_kappa(("missing",), ("a",), ("a", "b"))
