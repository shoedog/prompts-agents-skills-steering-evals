"""Tests for the cleanup-wave items that don't have an existing home:

  - scripts/check_spotcheck.py (item 4): empty-but-present `items: []` is
    PROVISIONAL/exit 0, not FAIL. Run as a subprocess, same pattern as
    ci/test_smoke.py and test_check_taskset.py use for the sibling
    scripts/check_*.py validators.
  - scripts/rejudge.py (item 8): `_rejudge_one` stamps the OUTPUT exp_id
    (not the source record's exp_id) and writes a native per-call trace log
    into the output dir. Loaded directly by file path (scripts/ is not a
    package) and exercised at the function level — no live judge/codex call,
    no full CLI invocation.

No model calls anywhere in this file.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECK_SPOTCHECK = str(REPO_ROOT / "scripts" / "check_spotcheck.py")


def _run_check_spotcheck(results_dir) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _CHECK_SPOTCHECK, str(results_dir)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# check_spotcheck.py: empty items: [] -> PROVISIONAL, exit 0 (item 4)
# --------------------------------------------------------------------------- #
def test_empty_items_list_is_provisional_exit_zero(tmp_path):
    (tmp_path / "spotcheck.yaml").write_text(yaml.safe_dump({"items": []}))
    proc = _run_check_spotcheck(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PROVISIONAL" in proc.stdout


def test_missing_items_key_still_fails(tmp_path):
    # Regression guard: distinct from the empty-list case above -- a missing
    # 'items' key entirely is still a malformed file, not "nothing to check".
    (tmp_path / "spotcheck.yaml").write_text(yaml.safe_dump({"other": []}))
    proc = _run_check_spotcheck(tmp_path)
    assert proc.returncode != 0


def test_non_list_items_still_fails(tmp_path):
    (tmp_path / "spotcheck.yaml").write_text(yaml.safe_dump({"items": "not-a-list"}))
    proc = _run_check_spotcheck(tmp_path)
    assert proc.returncode != 0


def test_unfilled_items_still_provisional_exit_zero(tmp_path):
    # Regression guard for the pre-existing (non-empty) provisional path.
    (tmp_path / "spotcheck.yaml").write_text(
        yaml.safe_dump({"items": [{"task_id": "t1", "arm": "baseline", "agree": None}]})
    )
    proc = _run_check_spotcheck(tmp_path)
    assert proc.returncode == 0
    assert "PROVISIONAL" in proc.stdout


def test_missing_file_fails(tmp_path):
    proc = _run_check_spotcheck(tmp_path)  # no spotcheck.yaml written at all
    assert proc.returncode != 0


# --------------------------------------------------------------------------- #
# scripts/rejudge.py loaded by file path (scripts/ is not a package).
# --------------------------------------------------------------------------- #
def _load_rejudge_module():
    spec = importlib.util.spec_from_file_location(
        "scripts_rejudge", str(REPO_ROOT / "scripts" / "rejudge.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts_rejudge"] = module
    spec.loader.exec_module(module)
    return module


rejudge = _load_rejudge_module()


def _src_record(tmp_path, **over):
    truth = tmp_path / "truth.yaml"
    truth.write_text("defects: []\n")
    base = {
        "exp_id": "SOURCE-exp-id",
        "arm": "baseline",
        "task_id": "t1",
        "tier": "weak",
        "seeded": False,
        "adherence_labels": {"checklist": True, "disconfirm": True, "verify": True},
        "truth_path": str(truth),
        "normalized_block": "## FINDINGS\nVERDICT: APPROVE\nNo findings.\n",
        "verdict_flagged": False,
        "parse_ok": True,
    }
    base.update(over)
    return base


def _judge_cfg():
    return {"provider": "codex", "model": "gpt-5.5", "effort": "medium",
            "rubric": "x", "schema": None}


# --------------------------------------------------------------------------- #
# exp_id stamping: OUTPUT id, never the source record's id (item 8)
# --------------------------------------------------------------------------- #
def test_rejudge_one_stamps_output_exp_id_not_source(tmp_path):
    src = _src_record(tmp_path)
    payload = {
        "parse_ok": True, "defects": [], "false_findings": 0,
        "neutral_matched": 0, "verdict_flagged": False, "judge_tokens": 42,
    }
    with patch("scripts_rejudge.judge_review", return_value=payload):
        rec = rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(tmp_path / "out"),
        )
    assert rec["exp_id"] == "OUTPUT-exp-id"
    assert rec["exp_id"] != src["exp_id"]


def test_rejudge_one_parse_failure_row_also_stamps_output_exp_id(tmp_path):
    src = _src_record(tmp_path, parse_ok=False)
    with patch("scripts_rejudge.judge_review") as mock_jr:
        rec = rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(tmp_path / "out"),
        )
    assert mock_jr.call_count == 0  # parse failure never reaches the judge
    assert rec["exp_id"] == "OUTPUT-exp-id"
    assert rec["parse_ok"] is False


def test_rejudge_one_judge_error_row_also_stamps_output_exp_id(tmp_path):
    src = _src_record(tmp_path)
    with patch("scripts_rejudge.judge_review", side_effect=rejudge.JudgeError("boom")):
        rec = rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(tmp_path / "out"),
        )
    assert rec["exp_id"] == "OUTPUT-exp-id"
    assert rec["judge_error"] is True


# --------------------------------------------------------------------------- #
# Native per-call trace log written into the OUTPUT dir (item 8)
# --------------------------------------------------------------------------- #
def test_rejudge_one_success_writes_trace_into_output_dir(tmp_path):
    src = _src_record(tmp_path)
    out_dir = tmp_path / "out"
    payload = {
        "parse_ok": True, "defects": [], "false_findings": 0,
        "neutral_matched": 0, "verdict_flagged": False, "judge_tokens": 42,
    }
    with patch("scripts_rejudge.judge_review", return_value=payload):
        rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(out_dir),
        )
    trace_path = out_dir / "trace.jsonl"
    assert trace_path.is_file()
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert any(e["kind"] == "rejudge_judge" for e in events)
    traced = [e for e in events if e["kind"] == "rejudge_judge"][0]
    assert traced["payload"]["exp_id"] == "OUTPUT-exp-id"
    assert traced["payload"]["task_id"] == "t1"


def test_rejudge_one_judge_error_writes_trace_into_output_dir(tmp_path):
    src = _src_record(tmp_path)
    out_dir = tmp_path / "out"
    with patch("scripts_rejudge.judge_review", side_effect=rejudge.JudgeError("boom")):
        rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(out_dir),
        )
    trace_path = out_dir / "trace.jsonl"
    assert trace_path.is_file()
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert any(e["kind"] == "rejudge_judge_error" for e in events)


def test_rejudge_one_parse_failure_writes_no_trace_file(tmp_path):
    # A carried-over source parse failure never calls the judge in the live
    # assert either, so it must not fabricate a trace event here.
    src = _src_record(tmp_path, parse_ok=False)
    out_dir = tmp_path / "out"
    with patch("scripts_rejudge.judge_review"):
        rejudge._rejudge_one(
            src, _judge_cfg(), str(tmp_path / "scratch"), "OUTPUT-exp-id",
            out_dir=str(out_dir),
        )
    assert not (out_dir / "trace.jsonl").exists()
