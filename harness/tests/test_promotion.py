"""Promotion-gate boundary tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from harness.structured.promotion import PromotionVerdict, promotion_verdict


def test_promotion_accepts_exact_zero_bounds():
    verdict = promotion_verdict(
        macro_f1_ci={"lo": 0.0, "hi": 0.04},
        schema_validity=0.99,
        recall_cis={"correct": {"lo": -0.1, "hi": 0.0}},
    )
    assert verdict.promotable is True
    assert "PROMOTABLE" in verdict.reason


@pytest.mark.parametrize(
    "macro_lo, validity, recall_hi, reason",
    [
        (-0.000001, 1.0, 0.1, "macro_f1_ci.lo"),
        (0.0, 0.989999, 0.1, "schema_validity"),
        (0.0, 1.0, -0.000001, "recall_ci.hi"),
    ],
)
def test_each_promotion_condition_can_veto(macro_lo, validity, recall_hi, reason):
    verdict = promotion_verdict(
        macro_f1_ci={"lo": macro_lo, "hi": 0.1},
        schema_validity=validity,
        recall_cis={"fatal": {"lo": -0.2, "hi": recall_hi}},
    )
    assert verdict.promotable is False
    assert reason in verdict.reason


def test_promotion_names_the_collapsing_recall_class():
    verdict = promotion_verdict(
        macro_f1_ci={"lo": 0.1, "hi": 0.2},
        schema_validity=1.0,
        recall_cis={
            "retry": {"lo": -0.3, "hi": -0.01},
            "fatal": {"lo": -0.1, "hi": 0.0},
        },
    )
    assert verdict.promotable is False
    assert "retry" in verdict.reason


def test_promotion_verdict_is_frozen():
    verdict = PromotionVerdict(promotable=True, reason="PROMOTABLE")
    with pytest.raises(FrozenInstanceError):
        verdict.promotable = False


def test_promotion_verdict_retains_structured_evidence_additively():
    evidence = {
        "metrics": {
            "macro_f1": {
                "baseline": 0.5,
                "candidate": 0.7,
                "delta": 0.2,
                "lo": 0.0,
                "hi": 0.4,
            }
        },
        "recall_cis": {"fatal": {"lo": -0.1, "hi": 0.2}},
        "population": {"n_items": 20, "sha256": "a" * 64},
        "resamples": 2000,
        "seed": 20260904,
    }
    verdict = promotion_verdict(
        macro_f1_ci={"lo": 0.0, "hi": 0.4},
        schema_validity=1.0,
        recall_cis=evidence["recall_cis"],
        evidence=evidence,
    )

    assert verdict.promotable is True
    assert verdict.evidence == evidence


@pytest.mark.parametrize(
    "macro_ci, validity, recall_cis, reason",
    [
        ({"lo": float("nan"), "hi": 0.1}, 1.0, {}, "macro_f1_ci.lo"),
        ({"lo": 0.2, "hi": 0.1}, 1.0, {}, "less than or equal"),
        ({"lo": 0.0, "hi": 0.1}, float("nan"), {}, "schema_validity"),
        ({"lo": 0.0, "hi": 0.1}, -0.1, {}, "schema_validity"),
        ({"lo": 0.0, "hi": 0.1}, 1.1, {}, "schema_validity"),
        (
            {"lo": 0.0, "hi": 0.1},
            1.0,
            {"fatal": {"lo": -0.1, "hi": float("inf")}},
            "recall_cis.*hi",
        ),
        ({"lo": 0.0, "hi": 0.1}, 1.0, [], "recall_cis.*mapping"),
    ],
)
def test_promotion_rejects_invalid_gate_inputs(
    macro_ci, validity, recall_cis, reason
):
    with pytest.raises(ValueError, match=reason):
        promotion_verdict(
            macro_f1_ci=macro_ci,
            schema_validity=validity,
            recall_cis=recall_cis,
        )
