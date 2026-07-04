"""Metrics tests — synthetic rows only, no model calls, no promptfoo."""
import json

import pytest

from harness.metrics import (
    IntegrityError,
    TierMixError,
    _load_json_glob,
    adherence,
    confusion,
    delta,
    flags,
    judge_token_totals,
    mcnemar_p,
    pass_rate,
    paired_flips,
    token_totals,
    triggering_metrics,
    wilson_ci,
)


def _judge_row(arm="baseline", tier="weak", **kw):
    base = {
        "arm": arm,
        "tier": tier,
        "task_id": kw.pop("task_id", "t0"),
        "seeded": kw.pop("seeded", True),
        "verdict_flagged": kw.pop("verdict_flagged", False),
        "item_pass": kw.pop("item_pass", False),
        "judge_error": kw.pop("judge_error", False),
        "defects": kw.pop("defects", []),
        "false_findings": kw.pop("false_findings", 0),
        "adherence_labels": kw.pop("adherence_labels", {"checklist": False, "disconfirm": False, "verify": False}),
    }
    base.update(kw)
    return base


def _call_row(arm="baseline", tier="weak", **kw):
    base = {
        "arm": arm,
        "tier": tier,
        "fresh_input_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "input_tokens_logical": 0,
        "cost_usd": 0.0,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
def test_wilson_ci_known_case():
    lo, hi = wilson_ci(7, 10)
    assert lo == pytest.approx(0.397, abs=0.005)
    assert hi == pytest.approx(0.892, abs=0.005)


def test_wilson_ci_zero_n():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_pass_rate_excludes_judge_errors_but_counts_them():
    rows = [
        _judge_row(item_pass=True, judge_error=False),
        _judge_row(item_pass=False, judge_error=False),
        _judge_row(item_pass=True, judge_error=True),   # excluded from k/n
        _judge_row(arm="treatment", item_pass=True),    # other arm ignored
    ]
    pr = pass_rate(rows, "baseline")
    assert pr["n"] == 2
    assert pr["k"] == 1
    assert pr["rate"] == pytest.approx(0.5)
    assert pr["judge_errors"] == 1


def test_token_totals_and_delta_breakdown():
    calls = [
        _call_row(fresh_input_tokens=100, cache_creation_tokens=200,
                  cache_read_tokens=300, output_tokens=50,
                  input_tokens_logical=600, cost_usd=0.01),
        _call_row(fresh_input_tokens=10, cache_creation_tokens=20,
                  cache_read_tokens=30, output_tokens=5,
                  input_tokens_logical=60, cost_usd=0.002),
        _call_row(arm="treatment", fresh_input_tokens=120, cache_creation_tokens=180,
                  cache_read_tokens=400, output_tokens=70,
                  input_tokens_logical=700, cost_usd=0.02),
    ]
    b = token_totals(calls, "baseline")
    assert b["fresh_input"] == 110
    assert b["cache_creation"] == 220
    assert b["cache_read"] == 330
    assert b["output"] == 55
    assert b["logical_total"] == 660
    assert b["cost_usd"] == pytest.approx(0.012)

    t = token_totals(calls, "treatment")
    assert t["logical_total"] == 700

    d = delta(b, t)
    assert d["logical_total"]["abs"] == 40
    assert d["logical_total"]["pct"] == pytest.approx(40 / 660 * 100)
    assert d["cost_usd"]["abs"] == pytest.approx(0.02 - 0.012)


def test_confusion_hand_built_six_rows():
    rows = [
        _judge_row(seeded=True, verdict_flagged=True, truth_defect_ids=["a", "b"],
                   defects=[{"defect_id": "a", "found": True}, {"defect_id": "b", "found": True}]),  # TP, 2/2
        _judge_row(seeded=True, verdict_flagged=True, truth_defect_ids=["c"],
                   defects=[{"defect_id": "c", "found": True}]),  # TP, 1/1
        _judge_row(seeded=True, verdict_flagged=False, truth_defect_ids=["d"],
                   defects=[{"defect_id": "d", "found": False}]),  # FN, 0/1
        _judge_row(seeded=False, verdict_flagged=True, false_findings=1),  # FP
        _judge_row(seeded=False, verdict_flagged=False),  # TN
        _judge_row(seeded=False, verdict_flagged=False),  # TN
    ]
    c = confusion(rows, "baseline")
    assert (c["tp"], c["fp"], c["tn"], c["fn"]) == (2, 1, 2, 1)
    assert c["n"] == 6
    assert c["base_rate"] == pytest.approx(0.5)  # (TP+FN)/n = 3/6
    assert c["defect_recall"]["found"] == 3
    assert c["defect_recall"]["total"] == 4
    assert c["defect_recall"]["rate"] == pytest.approx(0.75)
    assert c["defect_recall"]["judge_id_mismatches"] == 0
    assert c["false_findings_total"] == 1
    assert c["neutral_matched_total"] == 0  # no rows carried neutral matches


def test_confusion_sums_neutral_matched_across_rows_separate_from_false_findings():
    # Neutral matches are summed independently of false findings: a seeded row
    # can carry neutral_matched>0 while contributing 0 to false_findings_total.
    rows = [
        _judge_row(seeded=True, verdict_flagged=True, truth_defect_ids=["a"],
                   defects=[{"defect_id": "a", "found": True}],
                   false_findings=0, neutral_matched=2),
        _judge_row(seeded=True, verdict_flagged=True, truth_defect_ids=["b"],
                   defects=[{"defect_id": "b", "found": True}],
                   false_findings=1, neutral_matched=1),
        _judge_row(seeded=False, verdict_flagged=False),  # no neutral key -> 0
    ]
    c = confusion(rows, "baseline")
    assert c["neutral_matched_total"] == 3
    assert c["false_findings_total"] == 1


def test_defect_recall_anchored_to_truth_not_judge_ids():
    # Truth seeds d1 + d2. The judge:
    #   - found d1 (a real truth id)                -> counts toward recall
    #   - reported d99 as found (hallucinated id)   -> ignored for recall, mismatch
    #   - never returned d2 at all (omitted truth id) -> still in the denominator
    rows = [
        _judge_row(
            seeded=True, verdict_flagged=True, truth_defect_ids=["d1", "d2"],
            defects=[
                {"defect_id": "d1", "found": True},
                {"defect_id": "d99", "found": True},
            ],
        ),
    ]
    c = confusion(rows, "baseline")
    dr = c["defect_recall"]
    assert dr["total"] == 2                      # both seeded truth defects
    assert dr["found"] == 1                       # only d1; d99 is not truth, d2 omitted
    assert dr["rate"] == pytest.approx(0.5)
    assert dr["judge_id_mismatches"] == 1         # d99 tallied separately


def test_load_json_glob_collects_named_integrity_errors(tmp_path):
    (tmp_path / "good.json").write_text(json.dumps({"ok": True}))
    (tmp_path / "truncated.json").write_text('{"ok": true')     # never closed
    (tmp_path / "garbage.json").write_text("not json at all")
    with pytest.raises(IntegrityError) as exc:
        _load_json_glob(str(tmp_path / "*.json"))
    msg = str(exc.value)
    assert "truncated.json" in msg
    assert "garbage.json" in msg
    assert "good.json" not in msg                 # the parseable file is not flagged


def test_paired_flips_joins_on_task_id():
    rows = [
        _judge_row(task_id="t1", item_pass=True),
        _judge_row(task_id="t1", arm="treatment", item_pass=True),   # both_pass
        _judge_row(task_id="t2", item_pass=True),
        _judge_row(task_id="t2", arm="treatment", item_pass=False),  # only_baseline
        _judge_row(task_id="t3", item_pass=False),
        _judge_row(task_id="t3", arm="treatment", item_pass=True),   # only_treatment
        _judge_row(task_id="t4", item_pass=False),
        _judge_row(task_id="t4", arm="treatment", item_pass=False),  # both_fail
        _judge_row(task_id="t5", item_pass=True),
        _judge_row(task_id="t5", arm="treatment", item_pass=True, judge_error=True),  # excluded
    ]
    fp = paired_flips(rows)
    assert fp == {"both_pass": 1, "both_fail": 1, "only_baseline": 1, "only_treatment": 1}


def test_adherence_treatment_directive_rates():
    rows = [
        _judge_row(arm="treatment", adherence_labels={"checklist": True, "disconfirm": True, "verify": True}),
        _judge_row(arm="treatment", adherence_labels={"checklist": True, "disconfirm": False, "verify": True}),
        _judge_row(arm="baseline", adherence_labels={"checklist": True, "disconfirm": True, "verify": True}),
    ]
    a = adherence(rows)
    assert a["review-shape.checklist"] == pytest.approx(1.0)
    assert a["review-shape.disconfirm"] == pytest.approx(0.5)
    assert a["review-shape.verify"] == pytest.approx(1.0)
    assert a["review-shape.all_three"] == pytest.approx(0.5)


def test_tier_mix_raises():
    rows = [
        _judge_row(tier="weak", item_pass=True),
        _judge_row(tier="strong", item_pass=True),
    ]
    with pytest.raises(TierMixError):
        pass_rate(rows, "baseline")
    with pytest.raises(TierMixError):
        confusion(rows, "baseline")


def test_triggering_metrics_synthetic_ten_rows():
    rows = (
        [{"should_trigger": True, "did_trigger": True} for _ in range(4)]
        + [{"should_trigger": True, "did_trigger": False}]
        + [{"should_trigger": False, "did_trigger": True} for _ in range(2)]
        + [{"should_trigger": False, "did_trigger": False} for _ in range(3)]
    )
    m = triggering_metrics(rows)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (4, 2, 3, 1)
    assert m["n"] == 10
    assert m["precision"] == pytest.approx(4 / 6)
    assert m["recall"] == pytest.approx(0.8)
    assert m["base_rate"] == pytest.approx(0.5)


def test_flags_cost_adjusted_verdict():
    assert flags(0.5, 0.7, 25.0, False, 0)["cost_adjusted_verdict"] is True
    assert flags(0.5, 0.7, 10.0, False, 0)["cost_adjusted_verdict"] is False
    assert flags(0.7, 0.5, 25.0, False, 0)["cost_adjusted_verdict"] is False  # no win


def test_flags_harness_broken():
    assert flags(0.4, 0.6, 5.0, True, 0)["harness_broken"] is True
    assert flags(0.6, 0.4, 5.0, True, 0)["harness_broken"] is False  # treatment lost
    assert flags(0.4, 0.6, 5.0, False, 0)["harness_broken"] is False  # not a control


def test_flags_composite_floored():
    assert flags(0.10, 0.12, 0.0, False, 0)["composite_floored"] is True
    assert flags(0.10, 0.20, 0.0, False, 0)["composite_floored"] is False
    assert flags(0.20, 0.10, 0.0, False, 0)["composite_floored"] is False


def test_flags_judge_errors_passthrough():
    assert flags(0.5, 0.5, 0.0, False, 3)["judge_errors"] == 3


# --------------------------------------------------------------------------- #
# McNemar exact p-value (binomial sign test on discordant-pair counts)
# --------------------------------------------------------------------------- #
def test_mcnemar_p_zero_discordant_pairs_is_one():
    # No flips in either direction at all -- maximal non-significance, not
    # an undefined/divide-by-zero case.
    assert mcnemar_p(0, 0) == 1.0


def test_mcnemar_p_one_vs_one_is_one():
    # Hand-computed: n=2, P(X<=1|n=2,p=.5) = (C(2,0)+C(2,1))/4 = 3/4 = 0.75;
    # p = 2*0.75 = 1.5, capped at 1.0. Matches the report caveat's own
    # worked example ("McNemar exact p=1.00 on 1 vs 1 discordant pairs").
    assert mcnemar_p(1, 1) == pytest.approx(1.0)


def test_mcnemar_p_symmetric_in_its_arguments():
    # b vs c and c vs b must give the same two-sided p-value.
    assert mcnemar_p(2, 8) == pytest.approx(mcnemar_p(8, 2))


def test_mcnemar_p_highly_asymmetric_is_significant():
    # n=16, all 16 discordant pairs favor one side: P(X<=0|16,.5) = 0.5**16.
    # p = 2 * 0.5**16, tiny -- far below the 0.05 noise-screen threshold.
    p = mcnemar_p(0, 16)
    assert p < 0.05
    assert p == pytest.approx(2 * (0.5 ** 16))


def test_mcnemar_p_known_hand_computed_value():
    # n=10, b=2, c=8: P(X<=2|n=10,p=.5) = (C(10,0)+C(10,1)+C(10,2))/1024
    #                                    = (1+10+45)/1024 = 56/1024 = 0.0546875
    # p = 2 * 0.0546875 = 0.109375 (well under 1.0, no capping needed).
    assert mcnemar_p(2, 8) == pytest.approx(0.109375)


def test_mcnemar_p_never_exceeds_one():
    for b, c in ((1, 1), (2, 2), (3, 3), (0, 0), (5, 4)):
        assert mcnemar_p(b, c) <= 1.0


# --------------------------------------------------------------------------- #
# Judge-side token/cost totals
# --------------------------------------------------------------------------- #
def _judge_tok_row(arm="baseline", judge_tokens=None, judge_cost_usd=None, **kw):
    return _judge_row(arm=arm, judge_tokens=judge_tokens, judge_cost_usd=judge_cost_usd, **kw)


def test_judge_token_totals_sums_available_tokens_and_counts_missing():
    rows = [
        _judge_tok_row(judge_tokens=1000),
        _judge_tok_row(judge_tokens=2000),
        _judge_tok_row(judge_tokens=None),  # parse-failure / judge_error row
        _judge_tok_row(arm="treatment", judge_tokens=500),
    ]
    jt = judge_token_totals(rows, "baseline")
    assert jt["judge_tokens_total"] == 3000
    assert jt["judge_tokens_missing"] == 1
    assert jt["judge_cost_usd_total"] is None  # no row carried a cost estimate


def test_judge_token_totals_cost_total_none_when_absent_not_zero():
    rows = [_judge_tok_row(judge_tokens=1000, judge_cost_usd=None)]
    jt = judge_token_totals(rows, "baseline")
    assert jt["judge_cost_usd_total"] is None


def test_judge_token_totals_sums_cost_when_present():
    rows = [
        _judge_tok_row(judge_tokens=1_000_000, judge_cost_usd=0.5),
        _judge_tok_row(judge_tokens=2_000_000, judge_cost_usd=1.0),
    ]
    jt = judge_token_totals(rows, "baseline")
    assert jt["judge_tokens_total"] == 3_000_000
    assert jt["judge_cost_usd_total"] == pytest.approx(1.5)
    assert jt["judge_tokens_missing"] == 0


def test_judge_token_totals_tier_mix_raises():
    rows = [
        _judge_tok_row(tier="weak", judge_tokens=1),
        _judge_tok_row(tier="strong", judge_tokens=1),
    ]
    with pytest.raises(TierMixError):
        judge_token_totals(rows, "baseline")
