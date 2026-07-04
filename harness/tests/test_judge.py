"""Judge tests — the codex CLI is always mocked; no live judge call is made."""
import json
from unittest.mock import patch

import pytest

from harness.judge import (
    JudgeError,
    _parse_and_validate,
    _render_ground_truth,
    judge_review,
)


def _valid_payload(**over):
    base = {
        "parse_ok": True,
        "defects": [{"defect_id": "d1", "found": True}],
        "false_findings": 0,
        "neutral_matched": 0,
        "verdict_flagged": True,
    }
    base.update(over)
    return base


def test_parse_and_validate_accepts_well_formed():
    data = _parse_and_validate(json.dumps(_valid_payload()))
    assert data["defects"] == [{"defect_id": "d1", "found": True}]


def test_parse_and_validate_rejects_defect_missing_id():
    bad = _valid_payload(defects=[{"found": True}])
    with pytest.raises(ValueError):
        _parse_and_validate(json.dumps(bad))


def test_parse_and_validate_rejects_non_bool_found():
    # found=1 (int) is malformed even though it is truthy.
    bad = _valid_payload(defects=[{"defect_id": "d1", "found": 1}])
    with pytest.raises(ValueError):
        _parse_and_validate(json.dumps(bad))


def test_parse_and_validate_rejects_non_object_defect_entry():
    bad = _valid_payload(defects=["d1"])
    with pytest.raises(ValueError):
        _parse_and_validate(json.dumps(bad))


def test_parse_and_validate_requires_neutral_matched_key():
    bad = _valid_payload()
    del bad["neutral_matched"]
    with pytest.raises(ValueError):
        _parse_and_validate(json.dumps(bad))


def test_parse_and_validate_rejects_non_int_neutral_matched():
    # neutral_matched must be a real integer, not a string and not a bool.
    for bad_val in ("1", 1.5, True):
        bad = _valid_payload(neutral_matched=bad_val)
        with pytest.raises(ValueError):
            _parse_and_validate(json.dumps(bad))


def test_parse_and_validate_accepts_positive_neutral_matched():
    data = _parse_and_validate(json.dumps(_valid_payload(neutral_matched=2)))
    assert data["neutral_matched"] == 2


# --------------------------------------------------------------------------- #
# Ground-truth rendering: neutral_findings appear for SEEDED items only.
# --------------------------------------------------------------------------- #
def test_render_ground_truth_renders_neutral_findings_for_seeded():
    truth = {
        "seeded": True,
        "defects": [{"id": "d1", "description": "the real defect"}],
        "neutral_findings": ["a true-but-out-of-scope observation"],
    }
    rendered = _render_ground_truth(truth)
    assert "SEEDED" in rendered
    assert "neutral_findings" in rendered
    assert "a true-but-out-of-scope observation" in rendered
    assert "NEITHER credited" in rendered


def test_render_ground_truth_omits_neutral_section_for_seeded_without_neutral():
    truth = {"seeded": True, "defects": [{"id": "d1", "description": "x"}]}
    assert "neutral_findings" not in _render_ground_truth(truth)


def test_render_ground_truth_clean_item_never_renders_neutral_findings():
    # A clean item carries no neutral_findings (check_taskset forbids it), and
    # the renderer's clean branch must never surface one even if a stray key
    # slipped in — clean items stay strict.
    truth = {
        "seeded": False,
        "defects": [],
        "clean_rationale": "all good",
        "tempting_non_defects": ["a tempting non-defect"],
        "neutral_findings": ["should not be shown on a clean item"],
    }
    rendered = _render_ground_truth(truth)
    assert "CLEAN" in rendered
    assert "neutral_findings" not in rendered
    assert "should not be shown on a clean item" not in rendered


# --------------------------------------------------------------------------- #
# judge_review threads tokens_used (from run_codex) onto the returned dict.
# --------------------------------------------------------------------------- #
def test_judge_review_threads_tokens_used_as_judge_tokens(tmp_path):
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the block.")
    payload = _valid_payload()

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": json.dumps(payload), "tokens_used": 4321}
        data = judge_review(
            "## FINDINGS\nVERDICT: REJECT\n1. x",
            {"defects": [{"id": "d1"}]},
            {"rubric": str(rubric), "schema": None},
        )
    assert data["judge_tokens"] == 4321


def test_judge_review_judge_tokens_is_none_when_codex_didnt_report_it(tmp_path):
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the block.")
    payload = _valid_payload()

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": json.dumps(payload)}  # no tokens_used key
        data = judge_review(
            "## FINDINGS\nVERDICT: REJECT\n1. x",
            {"defects": [{"id": "d1"}]},
            {"rubric": str(rubric), "schema": None},
        )
    assert data["judge_tokens"] is None


def test_judge_review_malformed_defect_entry_raises_judge_error_after_retry(tmp_path):
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the block.")
    malformed = json.dumps(_valid_payload(defects=[{"found": True}]))  # no defect_id

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": malformed}
        with pytest.raises(JudgeError):
            judge_review("## FINDINGS\nVERDICT: REJECT\n1. x",
                         {"defects": [{"id": "d1"}]},
                         {"rubric": str(rubric), "schema": None})
    # retried once before giving up (two attempts total).
    assert mock_run.call_count == 2
