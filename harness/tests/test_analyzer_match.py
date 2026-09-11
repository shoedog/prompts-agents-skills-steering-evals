from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from harness.structured.asserts import get
from harness.structured.asserts.analyzer_match import analyzer_match_assert, match_findings


def finding(category: str, file: str, line: int, tier: str = "asserted") -> dict:
    return {"category": category, "file": file, "line": line, "tier": tier}


@pytest.mark.parametrize("delta, matched", [(0, True), (3, True), (4, False)])
def test_line_tolerance_boundary(delta, matched):
    result = match_findings(
        [finding("missing_counterpart", "a.py", 10)],
        [finding("missing_counterpart", "a.py", 10 + delta)],
        line_tolerance=3,
        negative_findings=[],
        max_findings=6,
    )
    assert (result.tp == 1) is matched


def test_one_emission_cannot_satisfy_two_expected_findings():
    result = match_findings(
        [finding("x", "a.py", 10), finding("x", "a.py", 16)],
        [finding("x", "a.py", 13)],
        line_tolerance=3,
        negative_findings=[],
        max_findings=6,
    )
    assert (result.tp, result.fn) == (1, 1)


def test_negative_hit_is_a_false_positive():
    result = match_findings(
        [finding("x", "a.py", 10)],
        [finding("x", "a.py", 10), finding("x", "a.py", 20)],
        line_tolerance=3,
        negative_findings=[finding("x", "a.py", 20)],
        max_findings=6,
    )
    assert (result.tp, result.fp, result.negative_hits) == (1, 1, 1)


def test_max_findings_surplus_adds_a_false_positive():
    expected = [finding("x", "a.py", line) for line in (10, 20, 30)]
    result = match_findings(
        expected,
        list(expected),
        line_tolerance=3,
        negative_findings=[],
        max_findings=2,
    )
    assert (result.tp, result.fp, result.surplus_fp) == (3, 1, 1)


def test_matches_record_exact_or_signed_tolerance_and_ignore_tier():
    result = match_findings(
        [finding("x", "a.py", 10, "asserted"), finding("x", "a.py", 30)],
        [finding("x", "a.py", 8, "candidate"), finding("x", "a.py", 30)],
        line_tolerance=3,
        negative_findings=[],
        max_findings=6,
    )
    assert [match["matched_by"] for match in result.matches] == ["exact_line", "tolerance(-2)"]
    with pytest.raises(FrozenInstanceError):
        result.tp = 0


def test_invalid_matching_limits_are_rejected():
    with pytest.raises(ValueError, match="line_tolerance"):
        match_findings([], [], line_tolerance=-1, negative_findings=[], max_findings=0)
    with pytest.raises(ValueError, match="max_findings"):
        match_findings([], [], line_tolerance=0, negative_findings=[], max_findings=-1)


def test_analyzer_match_is_registered_with_the_structured_assert_interface():
    assert get("analyzer_match") is analyzer_match_assert
    result = analyzer_match_assert(
        output={"findings": [finding("x", "a.py", 10)]},
        raw="recorded",
        expected={"findings": [finding("x", "a.py", 10)], "negative_findings": [], "max_findings": 1},
        item={},
        cfg={"match": {"line_tolerance": 3}},
    )
    assert (result.passed, result.score) == (True, 1.0)
