"""Runner integrity-guard tests — filesystem only, no promptfoo / model calls."""
import json
from unittest.mock import patch

import pytest

import harness.run as run_mod
from harness import config as config_mod
from harness.metrics import IntegrityError
from harness.run import (
    _arm_cost,
    _check_arm_integrity,
    _check_stale_results_dir,
    _count_arm_calls,
    _count_arm_judges,
    _stale_result_files,
    build_parser,
)


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
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1", "t2", "t3"]) is False
    err = capsys.readouterr().err
    assert "INTEGRITY FAILURE" in err
    assert "1/3" in err


def test_check_arm_integrity_flags_silent_zero_arm(tmp_path, capsys):
    (tmp_path / "calls").mkdir()  # no call records at all
    ids = ["t1", "t2", "t3", "t4", "t5"]
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=ids) is False
    assert "0/5" in capsys.readouterr().err


def test_check_arm_integrity_passes_when_complete(tmp_path):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t2")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    _write_judge(judge, "baseline", "t2")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1", "t2"]) is True


def test_check_arm_integrity_flags_judge_shortfall_even_when_calls_complete(tmp_path, capsys):
    # calls/ complete (2/2) but judge/ short (1/2) — an assert-crash shortfall
    # that must NOT read as a clean, smaller-n run just because calls/ is full.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t2")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1", "t2"]) is False
    err = capsys.readouterr().err
    assert "INTEGRITY FAILURE" in err
    assert "judge" in err
    assert "1/2" in err


def test_check_arm_integrity_flags_silent_zero_judge_dir(tmp_path, capsys):
    # judge/ dir doesn't even exist yet — must count as 0, not error out.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1"]) is False
    assert "0/1" in capsys.readouterr().err


def test_check_arm_integrity_catches_unexpected_id_even_when_count_matches(tmp_path, capsys):
    # The whole point of exact-id validation: a stale leftover file from a
    # PRIOR run (t99, not in this run's manifest) plus a missing id for THIS
    # run (t2) nets out to the same COUNT (2) as a clean 2-item run — a
    # count-only check (the pre-fix behavior) would have read this as clean.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t99")  # stale leftover, not in expected_ids
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    _write_judge(judge, "baseline", "t99")
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1", "t2"]) is False
    err = capsys.readouterr().err
    assert "INTEGRITY FAILURE" in err
    assert "missing ids: ['t2']" in err
    assert "unexpected ids: ['t99']" in err


def test_check_arm_integrity_catches_missing_id_with_matching_count(tmp_path, capsys):
    # Same idea, isolated to calls/: t2 was never written, t1 was written
    # twice under two different (wrong) ids — count matches, id set doesn't.
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    _write_call(calls, "baseline", "t3")  # unexpected
    assert _check_arm_integrity(str(tmp_path), "baseline", expected_ids=["t1", "t2"]) is False
    err = capsys.readouterr().err
    assert "missing ids: ['t2']" in err
    assert "unexpected ids: ['t3']" in err


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


# --------------------------------------------------------------------------- #
# Stale results-dir guard — a re-run over a results dir that already has
# calls/ or judge/ files must refuse (not silently mix old and new records);
# --force clears explicitly instead of auto-deleting on its own initiative.
# --------------------------------------------------------------------------- #
def test_stale_result_files_empty_for_clean_dir(tmp_path):
    assert _stale_result_files(str(tmp_path)) == []


def test_stale_result_files_finds_calls_and_judge_json(tmp_path):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    assert len(_stale_result_files(str(tmp_path))) == 2


def test_check_stale_results_dir_passes_when_clean(tmp_path):
    assert _check_stale_results_dir(str(tmp_path), force=False) is True


def test_check_stale_results_dir_refuses_without_force(tmp_path, capsys):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    assert _check_stale_results_dir(str(tmp_path), force=False) is False
    err = capsys.readouterr().err
    assert "REFUSING" in err
    assert str(tmp_path) in err
    # a refusal must NOT delete anything itself
    assert (calls / "baseline-t1.json").exists()


def test_check_stale_results_dir_force_clears_calls_and_judge(tmp_path):
    calls = tmp_path / "calls"
    _write_call(calls, "baseline", "t1")
    judge = tmp_path / "judge"
    _write_judge(judge, "baseline", "t1")
    assert _check_stale_results_dir(str(tmp_path), force=True) is True
    assert not calls.exists()
    assert not judge.exists()


def test_build_parser_force_flag_defaults_false_and_is_settable():
    p = build_parser()
    assert p.parse_args(["experiments/smoke.yaml"]).force is False
    assert p.parse_args(["experiments/smoke.yaml", "--force"]).force is True


# --------------------------------------------------------------------------- #
# run_experiment integration — the real smoke.yaml config (so gen_promptfoo
# has genuine artifacts/taskset files to read) with results_dir redirected
# into tmp_path via an instance override, so the real results/smoke/weak dir
# is never touched. The eval invocation (`_run_arm`, which would otherwise
# shell out to `npx promptfoo`) is always mocked — no promptfoo/model call is
# ever made by these tests.
# --------------------------------------------------------------------------- #
def _smoke_cfg_with_tmp_results_dir(tmp_path):
    cfg = config_mod.load("experiments/smoke.yaml")
    results_dir = tmp_path / "results"
    # ExperimentConfig is a plain (non-frozen, non-slotted) dataclass, so an
    # instance attribute shadows the class method for this one cfg object.
    cfg.results_dir = lambda: results_dir
    return cfg, results_dir


def test_run_experiment_refuses_on_stale_dir_without_force(monkeypatch, tmp_path, capsys):
    cfg, results_dir = _smoke_cfg_with_tmp_results_dir(tmp_path)
    monkeypatch.setattr(run_mod.config_mod, "load", lambda path: cfg)

    stale_calls = results_dir / "calls"
    _write_call(stale_calls, "baseline", "stale-item")

    arm_invocations = []
    monkeypatch.setattr(run_mod, "_run_arm", lambda *a, **k: arm_invocations.append(a) or 0)

    exit_code = run_mod.run_experiment("experiments/smoke.yaml")

    assert exit_code != 0
    assert arm_invocations == []  # never reached the (mocked) eval invocation
    assert "REFUSING" in capsys.readouterr().err
    assert (stale_calls / "baseline-stale-item.json").exists()  # untouched


def test_run_experiment_force_clears_stale_and_proceeds(monkeypatch, tmp_path):
    cfg, results_dir = _smoke_cfg_with_tmp_results_dir(tmp_path)
    monkeypatch.setattr(run_mod.config_mod, "load", lambda path: cfg)

    stale_calls = results_dir / "calls"
    _write_call(stale_calls, "baseline", "stale-item")
    stale_judge = results_dir / "judge"
    _write_judge(stale_judge, "baseline", "stale-item")

    arm_invocations = []
    monkeypatch.setattr(run_mod, "_run_arm", lambda *a, **k: arm_invocations.append(a) or 0)
    monkeypatch.setattr(
        run_mod.report_mod, "render",
        lambda cfg_, rd: {"flags": {"harness_broken": False}, "judge_errors": 0},
    )

    run_mod.run_experiment("experiments/smoke.yaml", force=True)

    # proceeded past the stale-dir guard: the (mocked) eval invocation ran
    # for both the baseline and treatment arm...
    assert len(arm_invocations) == 2
    # ...and the stale leftover file from the PRIOR run is gone — force
    # cleared it before generating/running, so it can never be glob'd
    # together with anything from this run.
    assert not (stale_calls / "baseline-stale-item.json").exists()
