"""Tests for report._sample_items' stratified, deterministic spot-check sampling,
and for the automatic honesty caveats + delta rows in render_report_md.

See task-8-report.md's "My own spot-check read" section for the concrete
incident this guards against: with 40 judge records (20 baseline + 20
treatment), `judge/*.json` sorts alphabetically by filename and
`"baseline-*"` sorts before `"treatment-*"`, so the naive `graded[:20]`
sample put ALL 20 sampled items in the baseline arm — a human spot-checking
never saw a single treatment-arm row. `_sample_items` must instead take up to
10 from EACH arm (cap stays 20 total), deterministically (no Date-based or
other nondeterministic randomness), interleaved so both arms are always
represented.

The caveat/delta tests below (results-integrity follow-up to task 8) guard
three automatic honesty additions to the GENERATED report:
  - recall-ceiling caveat: fires per arm when that arm's defect recall is 1.000.
  - CI-overlap ("noise") caveat: fires when the two arms' Wilson CIs overlap.
  - Deltas section: gains output-token and fresh-input-token rows alongside
    the existing logical-token and cost-USD rows.
All computed from synthetic metrics dicts shaped like the real `summarize()`
output — no model calls, no metric-value changes.
"""
import json

from harness.config import ExecutorCfg, ExperimentConfig, JudgeCfg, TokenBudget
from harness.metrics import load_rows
from harness.report import (
    _ci_overlap,
    _collect_caveats,
    _noise_caveat,
    _recall_ceiling_caveats,
    _sample_items,
    render_report_md,
)


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


# --------------------------------------------------------------------------- #
# Synthetic metrics builders (pass_rate()/confusion()-shaped dicts) for the
# caveat + delta tests below. No model calls, no results dir on disk.
# --------------------------------------------------------------------------- #
def _pr(k, n, lo, hi):
    """Synthetic pass_rate()-shaped dict with an explicit Wilson CI."""
    return {
        "k": k,
        "n": n,
        "rate": (k / n) if n else 0.0,
        "wilson_ci": (lo, hi),
        "judge_errors": 0,
    }


def _conf(found, total, rate=None, false_findings=0, neutral_matched=0):
    """Synthetic confusion()-shaped dict — only the defect_recall sub-dict
    matters to the caveat logic under test; the other fields are zeroed."""
    if rate is None:
        rate = (found / total) if total else 0.0
    return {
        "tp": 0, "fp": 0, "tn": 0, "fn": 0, "n": 0, "base_rate": 0.0,
        "defect_recall": {
            "found": found, "total": total, "rate": rate, "judge_id_mismatches": 0,
        },
        "false_findings_total": false_findings,
        "neutral_matched_total": neutral_matched,
    }


def _cfg():
    """Minimal ExperimentConfig, built directly (no YAML/disk validation) so
    render_report_md's Configuration section has something to read from."""
    return ExperimentConfig(
        id="synthetic-exp",
        task_family="review",
        eval_shape="ablation",
        baseline_prompt=["artifacts/baseline/review.md"],
        varied_element="composites/review-shape",
        varied_element_form="prompt",
        taskset="tasksets/review-seeded",
        executor=ExecutorCfg(model="claude-haiku-4-5", tier="weak"),
        judge=JudgeCfg(
            provider="codex", model="gpt-5.5", effort="medium",
            rubric="harness/rubrics/x.md", schema="harness/rubrics/x.json",
        ),
        token_budget=TokenBudget(max_cost_usd=10.0, max_items=20),
        negative_control=False,
    )


def _full_summary(**overrides):
    """A full summarize()-shaped dict (mirrors results/exp1-review-shape/weak/
    metrics.json's real shape) with non-triggering defaults for the pieces not
    under test; callers override just baseline_pass/treatment_pass/
    baseline_confusion/treatment_confusion/etc. as needed."""
    s = {
        "baseline_pass": _pr(17, 20, 0.10, 0.20),
        "treatment_pass": _pr(16, 20, 0.60, 0.80),
        "baseline_tokens": {
            "fresh_input": 200, "cache_creation": 165085, "cache_read": 220020,
            "output": 51929, "logical_total": 385305, "cost_usd": 0.612017,
        },
        "treatment_tokens": {
            "fresh_input": 200, "cache_creation": 168345, "cache_read": 220020,
            "output": 87670, "logical_total": 388565, "cost_usd": 0.797242,
        },
        "token_delta": {
            "fresh_input": {"abs": 0, "pct": 0.0},
            "cache_creation": {"abs": 3260, "pct": 1.9747402853075686},
            "cache_read": {"abs": 0, "pct": 0.0},
            "output": {"abs": 35741, "pct": 68.82666718018834},
            "logical_total": {"abs": 3260, "pct": 0.8460829732290004},
            "cost_usd": {"abs": 0.1852250000000002, "pct": 30.264682190200638},
        },
        "baseline_confusion": _conf(13, 15),
        "treatment_confusion": _conf(12, 15),
        "flips": {"both_pass": 15, "both_fail": 2, "only_baseline": 2, "only_treatment": 1},
        "adherence": {
            "review-shape.checklist": 1.0, "review-shape.disconfirm": 1.0,
            "review-shape.verify": 1.0, "review-shape.all_three": 1.0,
        },
        "flags": {
            "cost_adjusted_verdict": False, "harness_broken": False,
            "composite_floored": False, "judge_errors": 0,
        },
        "judge_errors": 0,
        "parse_failures": 0,
    }
    s.update(overrides)
    return s


# --------------------------------------------------------------------------- #
# Recall-ceiling caveat
# --------------------------------------------------------------------------- #
def test_recall_ceiling_caveat_fires_for_baseline_at_ceiling():
    # Matches results/exp1-review-shape/weak/metrics.json exactly: baseline
    # 15/15 = 1.000, treatment 14/15 = 0.933.
    caveats = _recall_ceiling_caveats(_conf(15, 15), _conf(14, 15))
    assert len(caveats) == 1
    assert caveats[0] == (
        "Baseline defect recall is at ceiling (1.000): the treatment "
        "structurally cannot improve recall on this task set; recall deltas "
        "are uninterpretable and pass-rate deltas partly preordained. A "
        "harder task set is required to detect a recall improvement."
    )


def test_recall_ceiling_caveat_fires_for_treatment_at_ceiling():
    caveats = _recall_ceiling_caveats(_conf(12, 15), _conf(15, 15))
    assert len(caveats) == 1
    assert caveats[0].startswith("Treatment defect recall is at ceiling (1.000)")
    assert "the baseline structurally cannot improve recall" in caveats[0]


def test_recall_ceiling_caveat_fires_for_both_arms_at_ceiling():
    # Matches results/smoke/weak/metrics.json exactly: both arms 3/3 = 1.000.
    caveats = _recall_ceiling_caveats(_conf(3, 3), _conf(3, 3))
    assert len(caveats) == 2
    assert caveats[0].startswith("Baseline defect recall is at ceiling")
    assert caveats[1].startswith("Treatment defect recall is at ceiling")


def test_recall_ceiling_caveat_silent_when_below_ceiling():
    caveats = _recall_ceiling_caveats(_conf(14, 15), _conf(13, 15))
    assert caveats == []


def test_recall_ceiling_caveat_silent_when_total_is_zero():
    # Guards the total-truthy check: a fabricated rate of 1.0 with total=0
    # (no seeded defects to recall at all) must not be treated as a ceiling.
    zero_conf = {
        "tp": 0, "fp": 0, "tn": 0, "fn": 0, "n": 0, "base_rate": 0.0,
        "defect_recall": {"found": 0, "total": 0, "rate": 1.0, "judge_id_mismatches": 0},
        "false_findings_total": 0,
    }
    caveats = _recall_ceiling_caveats(zero_conf, zero_conf)
    assert caveats == []


# --------------------------------------------------------------------------- #
# CI-overlap ("noise") caveat
# --------------------------------------------------------------------------- #
def test_ci_overlap_true_when_intervals_intersect():
    # Matches results/exp1-review-shape/weak/metrics.json's pass-rate CIs.
    b_pr = _pr(17, 20, 0.6395811352592431, 0.9476312541037835)
    t_pr = _pr(16, 20, 0.5839825677481065, 0.9193423374202019)
    assert _ci_overlap(b_pr, t_pr) is True


def test_ci_overlap_false_when_intervals_disjoint():
    b_pr = _pr(2, 20, 0.05, 0.25)
    t_pr = _pr(18, 20, 0.75, 0.95)
    assert _ci_overlap(b_pr, t_pr) is False


def test_ci_overlap_true_at_touching_boundary():
    b_pr = _pr(10, 20, 0.10, 0.50)
    t_pr = _pr(10, 20, 0.50, 0.90)
    assert _ci_overlap(b_pr, t_pr) is True


def test_noise_caveat_fires_with_overlapping_cis_and_reports_n():
    b_pr = _pr(17, 20, 0.10, 0.60)
    t_pr = _pr(16, 20, 0.40, 0.90)
    caveat = _noise_caveat(b_pr, t_pr)
    assert caveat == (
        "Arm pass rates are not statistically distinguishable at n=20 "
        "(overlapping 95% CIs); treat the pass-rate delta as noise, not "
        "effect."
    )


def test_noise_caveat_silent_when_cis_disjoint():
    b_pr = _pr(2, 20, 0.05, 0.25)
    t_pr = _pr(18, 20, 0.75, 0.95)
    assert _noise_caveat(b_pr, t_pr) is None


def test_noise_caveat_reports_both_ns_when_arms_differ_in_size():
    b_pr = _pr(10, 15, 0.20, 0.80)
    t_pr = _pr(12, 20, 0.30, 0.85)
    caveat = _noise_caveat(b_pr, t_pr)
    assert "n=15/20" in caveat


# --------------------------------------------------------------------------- #
# _collect_caveats ordering
# --------------------------------------------------------------------------- #
def test_collect_caveats_orders_ceiling_before_noise():
    s = _full_summary(
        baseline_pass=_pr(17, 20, 0.10, 0.60),
        treatment_pass=_pr(16, 20, 0.40, 0.90),
        baseline_confusion=_conf(15, 15),
        treatment_confusion=_conf(14, 15),
    )
    caveats = _collect_caveats(s)
    assert len(caveats) == 2
    assert "ceiling" in caveats[0]
    assert "distinguishable" in caveats[1]


def test_collect_caveats_empty_when_neither_condition_holds():
    s = _full_summary(
        baseline_pass=_pr(2, 20, 0.05, 0.25),
        treatment_pass=_pr(18, 20, 0.75, 0.95),
        baseline_confusion=_conf(13, 15),
        treatment_confusion=_conf(12, 15),
    )
    assert _collect_caveats(s) == []


# --------------------------------------------------------------------------- #
# render_report_md: caveats section placement + deltas section rows
# --------------------------------------------------------------------------- #
def test_render_report_md_places_caveats_section_after_estimand_before_config():
    s = _full_summary(
        baseline_pass=_pr(17, 20, 0.10, 0.60),
        treatment_pass=_pr(16, 20, 0.40, 0.90),
        baseline_confusion=_conf(15, 15),
        treatment_confusion=_conf(14, 15),
    )
    md = render_report_md(_cfg(), s)
    estimand_idx = md.index("Estimand:")
    caveats_idx = md.index("## Caveats")
    config_idx = md.index("## Configuration")
    assert estimand_idx < caveats_idx < config_idx
    assert "Baseline defect recall is at ceiling (1.000)" in md
    assert "structurally cannot improve recall on this task set" in md
    assert "Arm pass rates are not statistically distinguishable" in md


def test_render_report_md_omits_caveats_section_when_neither_fires():
    s = _full_summary(
        baseline_pass=_pr(2, 20, 0.05, 0.25),
        treatment_pass=_pr(18, 20, 0.75, 0.95),
        baseline_confusion=_conf(13, 15),
        treatment_confusion=_conf(12, 15),
    )
    md = render_report_md(_cfg(), s)
    assert "## Caveats" not in md


def test_render_report_md_deltas_include_output_and_fresh_input_rows():
    s = _full_summary()
    md = render_report_md(_cfg(), s)
    deltas_section = md.split("### Deltas")[1].split("## Confusion matrix")[0]
    assert "logical tokens: 3260 (+0.8%)" in deltas_section
    assert "output tokens: 35741 (+68.8%)" in deltas_section
    assert "fresh input tokens: 0 (+0.0%)" in deltas_section
    assert "cost USD: +0.1852 (+30.3%)" in deltas_section


def test_render_report_md_confusion_table_surfaces_neutral_matched_column():
    s = _full_summary(
        baseline_confusion=_conf(15, 15, false_findings=2, neutral_matched=1),
        treatment_confusion=_conf(14, 15, false_findings=1, neutral_matched=3),
    )
    md = render_report_md(_cfg(), s)
    conf_section = md.split("## Confusion matrix")[1].split("## Paired flip")[0]
    header = [ln for ln in conf_section.splitlines() if ln.startswith("| arm |")][0]
    assert "neutral matched" in header
    body = [ln for ln in conf_section.splitlines()
            if ln.startswith("| baseline |") or ln.startswith("| treatment |")]
    # trailing cell is the neutral count (baseline=1, treatment=3)
    assert body[0].rstrip().endswith("| 1 |")
    assert body[1].rstrip().endswith("| 3 |")


def test_render_report_md_renders_provenance_note_when_given():
    s = _full_summary()
    note = "Rescore of exp1-review-shape executor outputs under neutral-findings scoring"
    md = render_report_md(_cfg(), s, note=note)
    assert f"> NOTE — {note}" in md
    # note precedes the estimand line
    assert md.index("> NOTE —") < md.index("Estimand:")


def test_render_report_md_omits_note_line_when_none():
    md = render_report_md(_cfg(), _full_summary())
    assert "> NOTE —" not in md
