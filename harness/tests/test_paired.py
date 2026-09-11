"""Exact-key paired flip tests for structured evaluation rows."""

from __future__ import annotations

import pytest

from harness.metrics import mcnemar_p
from harness.stats.paired import flips


def test_flips_exact_join_excludes_missing_and_stage_error_rows():
    rows_a = [
        {"item_id": "both-pass", "item_pass": True},
        {"item_id": "both-fail", "item_pass": False},
        {"item_id": "only-a", "item_pass": True},
        {"item_id": "only-b", "item_pass": False},
        {"item_id": "missing-b", "item_pass": True},
        {"item_id": "error-a", "item_pass": True, "stage_error": "llm"},
        {"item_id": "error-b", "item_pass": True},
    ]
    rows_b = [
        {"item_id": "both-pass", "item_pass": True},
        {"item_id": "both-fail", "item_pass": False},
        {"item_id": "only-a", "item_pass": False},
        {"item_id": "only-b", "item_pass": True},
        {"item_id": "missing-a", "item_pass": True},
        {"item_id": "error-a", "item_pass": True},
        {"item_id": "error-b", "item_pass": True, "stage_error": "prism"},
    ]

    result = flips(rows_a, rows_b)

    assert result == {
        "both_pass": 1,
        "both_fail": 1,
        "only_baseline": 1,
        "only_treatment": 1,
    }
    assert mcnemar_p(result["only_baseline"], result["only_treatment"]) == 1.0


def test_flips_supports_declared_join_and_pass_fields():
    assert flips(
        [{"case": "x", "ok": False}],
        [{"case": "x", "ok": True}],
        key="case",
        passed="ok",
    ) == {
        "both_pass": 0,
        "both_fail": 0,
        "only_baseline": 0,
        "only_treatment": 1,
    }


@pytest.mark.parametrize("side", ["baseline", "candidate"])
def test_flips_rejects_duplicate_join_keys(side):
    duplicate = [
        {"item_id": "x", "item_pass": True},
        {"item_id": "x", "item_pass": False},
    ]
    single = [{"item_id": "x", "item_pass": True}]
    rows_a, rows_b = (
        (duplicate, single) if side == "baseline" else (single, duplicate)
    )

    with pytest.raises(ValueError, match=f"duplicate {side}.*'x'"):
        flips(rows_a, rows_b)
