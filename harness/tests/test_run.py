"""Runner integrity-guard tests — filesystem only, no promptfoo / model calls."""
import json

import pytest

from harness.metrics import IntegrityError
from harness.run import _arm_cost, _check_arm_integrity, _count_arm_calls, _count_arm_judges


def _write_call(calls_dir, arm, task_id):
    calls_dir.mkdir(parents=True, exist_ok=True)
    (calls_dir / f"{arm}-{task_id}.json").write_text(json.dumps({"arm": arm}))


def _write_judge(judge_dir, arm, task_id):
    judge_dir.mkdir(parents=True, exist_ok=True)
    (judge_dir / f"{arm}-{task_id}.json").write_text(json.dumps({"arm": arm}))


def test_count_arm_calls_counts_only_that_arm(tmp_path):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t2")
    _write_call(calls, "treatment", "t1")
    assert _count_arm_calls(str(tmp_path), "baseline") == 2
    assert _count_arm_calls(str(tmp_path), "treatment") == 1


def test_check_arm_integrity_flags_shortfall(tmp_path, capsys):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")  # only 1 of 3 expected
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=3) is False
    err = capsys.readouterr().err
    assert "INTEGRITY FAILURE" in err
    assert "1/3" in err


def test_check_arm_integrity_flags_silent_zero_arm(tmp_path, capsys):
    (tmp_path / "calls").mkdir()  # no call records at all
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=5) is False
    assert "0/5" in capsys.readouterr().err


def test_check_arm_integrity_passes_when_complete(tmp_path):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t2")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    _write_judge(judge, "baseline", "t2")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=2) is True


def test_check_arm_integrity_flags_judge_shortfall_even_when_calls_complete(tmp_path, capsys):
    # calls/ complete (2/2) but judge/ short (1/2) — an assert-crash shortfall
    # that must NOT read as a clean, smaller-n run just because calls/ is full.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t2")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=2) is False
    err = capsys.readouterr().err
    assert "INTEGRITY FAILURE" in err
    assert "judge" in err
    assert "1/2" in err


def test_check_arm_integrity_flags_silent_zero_judge_dir(tmp_path, capsys):
    # judge/ dir doesn't even exist yet — must count as 0, not error out.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=1) is False
    assert "0/1" in capsys.readouterr().err


def test_count_arm_judges_counts_only_that_arm(tmp_path):
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    _write_judge(judge, "treatment", "t1")
    assert _count_arm_judges(str(tmp_path), "baseline") == 1
    assert _count_arm_judges(str(tmp_path), "treatment") == 1


# --------------------------------------------------------------------------- #
# _arm_cost — routes truncated files through metrics' named IntegrityError
# --------------------------------------------------------------------------- #
def test_arm_cost_sums_cost_usd_across_arm_call_records(tmp_path):
    calls = tmp_path / "calls"
    calls.mkdir()
    (calls / "baseline-t1.json").write_text(json.dumps({"arm": "baseline", "cost_usd": 0.01}))
    (calls / "baseline-t2.json").write_text(json.dumps({"arm": "baseline", "cost_usd": 0.02}))
    (calls / "treatment-t1.json").write_text(json.dumps({"arm": "treatment", "cost_usd": 100.0}))
    assert _arm_cost(str(tmp_path), "baseline") == pytest.approx(0.03)


def test_arm_cost_raises_integrity_error_on_truncated_file(tmp_path):
    calls = tmp_path / "calls"
    calls.mkdir()
    (calls / "baseline-t1.json").write_text(json.dumps({"arm": "baseline", "cost_usd": 0.01}))
    (calls / "baseline-t2.json").write_text("{not valid json")
    with pytest.raises(IntegrityError):
        _arm_cost(str(tmp_path), "baseline")
