"""Judge tests — the codex CLI is always mocked; no live judge call is made."""
import json
from unittest.mock import patch

import pytest

from harness.judge import JudgeError, _parse_and_validate, judge_review


def _valid_payload(**over):
    base = {
        "parse_ok": True,
        "defects": [{"defect_id": "d1", "found": True}],
        "false_findings": 0,
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
