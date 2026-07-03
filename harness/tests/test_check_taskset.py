"""check_taskset.py neutral_findings enforcement (seeded-only) + real tasksets.

Runs the validator as a subprocess (as ci/test_smoke.py does) over synthetic
minimal tasksets built in tmp_path, plus the two real committed tasksets to
prove the new rule doesn't regress them. No model calls.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECK = str(REPO_ROOT / "scripts" / "check_taskset.py")

_DIFF = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-x\n+y\n"

_DEFECT = {
    "id": "s1-d1",
    "defect_class": "example",
    "location": "f.py:1",
    "hunk_lines": "1-1",
    "description": "d",
    "root_cause": "r",
    "bad_behavior": "b",
    "minimal_trigger": "t",
    "acceptable_match": "a",
    "reject_if": "j",
}


def _run(taskset_dir):
    return subprocess.run(
        [sys.executable, _CHECK, str(taskset_dir)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )


def _write_item(root: Path, iid: str, truth: str):
    d = root / "items" / iid
    d.mkdir(parents=True)
    (d / "context.md").write_text(f"# {iid}\n")
    (d / "diff.patch").write_text(_DIFF)
    (d / "truth.yaml").write_text(truth)


def _seeded_truth(neutral: str | None = None) -> str:
    import yaml
    t = {"seeded": True, "defects": [dict(_DEFECT)]}
    if neutral is not None:
        t["neutral_findings"] = [neutral] if isinstance(neutral, str) else neutral
    return yaml.safe_dump(t, sort_keys=False)


def _clean_truth(neutral=None) -> str:
    import yaml
    t = {
        "seeded": False,
        "defects": [],
        "clean_rationale": "all good",
        "tempting_non_defects": ["a tempting non-defect"],
    }
    if neutral is not None:
        t["neutral_findings"] = neutral
    return yaml.safe_dump(t, sort_keys=False)


def _manifest(root: Path, items):
    body = "taskset: t\ntask_family: review\nitems:\n"
    for iid, seeded in items:
        body += f"- id: {iid}\n  seeded: {str(seeded).lower()}\n"
    (root / "manifest.yaml").write_text(body)


def test_neutral_findings_allowed_on_seeded(tmp_path):
    _write_item(tmp_path, "s1", _seeded_truth("a true out-of-scope observation"))
    _write_item(tmp_path, "c1", _clean_truth())
    _manifest(tmp_path, [("s1", True), ("c1", False)])
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_neutral_findings_rejected_on_clean(tmp_path):
    _write_item(tmp_path, "s1", _seeded_truth())
    _write_item(tmp_path, "c1", _clean_truth(neutral=["not allowed here"]))
    _manifest(tmp_path, [("s1", True), ("c1", False)])
    proc = _run(tmp_path)
    assert proc.returncode != 0
    assert "clean item must not carry neutral_findings" in proc.stdout


def test_neutral_findings_must_be_nonempty_list_when_present(tmp_path):
    _write_item(tmp_path, "s1", _seeded_truth(neutral=[]))
    _manifest(tmp_path, [("s1", True)])
    proc = _run(tmp_path)
    assert proc.returncode != 0
    assert "neutral_findings must be a non-empty list" in proc.stdout


def test_neutral_findings_entries_must_be_nonempty_strings(tmp_path):
    _write_item(tmp_path, "s1", _seeded_truth(neutral=["", "  "]))
    _manifest(tmp_path, [("s1", True)])
    proc = _run(tmp_path)
    assert proc.returncode != 0
    assert "must be a non-empty string" in proc.stdout


@pytest.mark.parametrize("taskset", ["review-seeded", "smoke"])
def test_real_tasksets_still_pass(taskset):
    proc = _run(REPO_ROOT / "tasksets" / taskset)
    assert proc.returncode == 0, proc.stdout + proc.stderr
