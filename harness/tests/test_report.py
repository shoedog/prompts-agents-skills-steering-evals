"""Tests for report._sample_items' stratified, deterministic spot-check sampling.

See task-8-report.md's "My own spot-check read" section for the concrete
incident this guards against: with 40 judge records (20 baseline + 20
treatment), `judge/*.json` sorts alphabetically by filename and
`"baseline-*"` sorts before `"treatment-*"`, so the naive `graded[:20]`
sample put ALL 20 sampled items in the baseline arm — a human spot-checking
never saw a single treatment-arm row. `_sample_items` must instead take up to
10 from EACH arm (cap stays 20 total), deterministically (no Date-based or
other nondeterministic randomness), interleaved so both arms are always
represented.
"""
import json

from harness.metrics import load_rows
from harness.report import _sample_items


def _judge_row(arm, task_id, parse_ok=True, judge_error=False):
    return {
        "arm": arm,
        "task_id": task_id,
        "parse_ok": parse_ok,
        "judge_error": judge_error,
        "seeded": True,
        "verdict_flagged": False,
        "defects": [],
        "false_findings": 0,
        "item_pass": True,
    }


def _write_judge_dir(tmp_path, rows):
    judge_dir = tmp_path / "judge"
    judge_dir.mkdir()
    for i, r in enumerate(rows):
        # Filename order deliberately does NOT match desired sample order
        # (mirrors the real judge/*.json glob: baseline-* sorts before
        # treatment-* alphabetically), so a pass here can't be an artifact of
        # write order happening to match task_id order.
        path = judge_dir / f"{r['arm']}-{r['task_id']}.json"
        path.write_text(json.dumps(r))
    return tmp_path


def _load_judges(tmp_path):
    _, judges = load_rows(str(tmp_path))
    return judges


def test_sample_items_splits_10_and_10_from_40_synthetic_records(tmp_path):
    rows = [_judge_row("baseline", f"t{i:02d}") for i in range(1, 21)] + [
        _judge_row("treatment", f"t{i:02d}") for i in range(1, 21)
    ]
    _write_judge_dir(tmp_path, rows)
    judges = _load_judges(tmp_path)

    sample = _sample_items(judges)

    assert len(sample) == 20
    counts = {}
    for r in sample:
        counts[r["arm"]] = counts.get(r["arm"], 0) + 1
    assert counts == {"baseline": 10, "treatment": 10}


def test_sample_items_is_deterministic_and_alternates_arms(tmp_path):
    rows = [_judge_row("baseline", f"t{i:02d}") for i in range(1, 21)] + [
        _judge_row("treatment", f"t{i:02d}") for i in range(1, 21)
    ]
    _write_judge_dir(tmp_path, rows)
    judges = _load_judges(tmp_path)

    sample1 = _sample_items(judges)
    sample2 = _sample_items(judges)
    assert sample1 == sample2  # deterministic: no randomness, no Date-based seed

    arms_in_order = [r["arm"] for r in sample1]
    assert arms_in_order == ["baseline", "treatment"] * 10

    baseline_task_ids = [r["task_id"] for r in sample1 if r["arm"] == "baseline"]
    treatment_task_ids = [r["task_id"] for r in sample1 if r["arm"] == "treatment"]
    assert baseline_task_ids == sorted(baseline_task_ids)
    assert treatment_task_ids == sorted(treatment_task_ids)
    assert baseline_task_ids == [f"t{i:02d}" for i in range(1, 11)]
    assert treatment_task_ids == [f"t{i:02d}" for i in range(1, 11)]


def test_sample_items_5_and_5_from_10_synthetic_records(tmp_path):
    # Mirrors results/smoke/weak's shape: 10 total records, 5 per arm.
    rows = [_judge_row("baseline", f"sm-{i:02d}") for i in range(1, 6)] + [
        _judge_row("treatment", f"sm-{i:02d}") for i in range(1, 6)
    ]
    _write_judge_dir(tmp_path, rows)
    judges = _load_judges(tmp_path)

    sample = _sample_items(judges)

    assert len(sample) == 10
    counts = {}
    for r in sample:
        counts[r["arm"]] = counts.get(r["arm"], 0) + 1
    assert counts == {"baseline": 5, "treatment": 5}


def test_sample_items_caps_at_10_per_arm_when_one_arm_has_fewer(tmp_path):
    rows = [_judge_row("baseline", f"t{i:02d}") for i in range(1, 21)] + [
        _judge_row("treatment", f"t{i:02d}") for i in range(1, 6)  # only 5
    ]
    _write_judge_dir(tmp_path, rows)
    judges = _load_judges(tmp_path)

    sample = _sample_items(judges)

    counts = {}
    for r in sample:
        counts[r["arm"]] = counts.get(r["arm"], 0) + 1
    assert counts == {"baseline": 10, "treatment": 5}
    assert len(sample) == 15


def test_sample_items_excludes_judge_error_and_unparsed_rows(tmp_path):
    rows = [
        _judge_row("baseline", "t01", judge_error=True),  # excluded: judge_error
        _judge_row("baseline", "t02", parse_ok=False),  # excluded: not parse_ok
        _judge_row("treatment", "t01"),  # included
    ]
    _write_judge_dir(tmp_path, rows)
    judges = _load_judges(tmp_path)

    sample = _sample_items(judges)

    assert len(sample) == 1
    assert sample[0]["arm"] == "treatment"
    assert sample[0]["task_id"] == "t01"
