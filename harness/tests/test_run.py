"""Runner integrity-guard tests — filesystem only, no promptfoo / model calls."""
import json

from harness.run import _check_arm_integrity, _count_arm_calls


def _write_call(calls_dir, arm, task_id):
    calls_dir.mkdir(parents=True, exist_ok=True)
    (calls_dir / f"{arm}-{task_id}.json").write_text(json.dumps({"arm": arm}))


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
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_items=2) is True
