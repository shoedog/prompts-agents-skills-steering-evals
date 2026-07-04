"""Findings-block normalizer + get_assert tests.

The normalizer is deterministic and takes no model calls. The one get_assert
test mocks the codex judge (via harness.judge.run_codex) so no live call runs.
"""
import json
import os
from unittest.mock import patch

import pytest

from harness.asserts.judge_assert import get_assert, normalize_block


# --------------------------------------------------------------------------- #
# Normalizer — tolerant input, canonical output
# --------------------------------------------------------------------------- #
def test_normalize_markdown_wrapped_verdict():
    block = "## FINDINGS\n**VERDICT: REJECT**\n1. a.py:1 — bug"
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is True
    assert "VERDICT: REJECT" in text
    # the bold verdict line is NOT mis-parsed as a `*` bullet finding
    finding_lines = [ln for ln in text.splitlines() if ln[:2] == "1."]
    assert finding_lines == ["1. a.py:1 — bug"]


def test_normalize_approve_markdown_wrapped():
    block = "## FINDINGS\n> VERDICT: APPROVE\nNo findings."
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is False
    assert "VERDICT: APPROVE" in text
    assert "No findings." in text


def test_normalize_word_level_bold_verdict():
    # Bold wraps only the WORD, not the whole line: `VERDICT: **REJECT**`.
    block = "## FINDINGS\nVERDICT: **REJECT**\n1. a.py:1 — bug"
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is True
    # canonical re-render, no leftover markdown around the verdict word
    assert "VERDICT: REJECT" in text.splitlines()


def test_normalize_word_level_bold_verdict_approve():
    block = "## FINDINGS\nVERDICT: **APPROVE**\nNo findings."
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is False
    assert "VERDICT: APPROVE" in text.splitlines()


def test_normalize_bulleted_no_findings_is_not_treated_as_a_finding():
    # `- No findings.` must NOT be extracted as a real finding and re-rendered
    # `1. No findings.` — that would read as a false finding on a clean item.
    block = "## FINDINGS\nVERDICT: APPROVE\n- No findings."
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is False
    lines = text.strip().splitlines()
    assert "No findings." in lines
    assert not any(ln.startswith("1.") for ln in lines)


def test_normalize_paren_and_colon_numbering():
    block = "## FINDINGS\nVERDICT: REJECT\n1) first defect\n2: second defect"
    text, ok, _ = normalize_block(block)
    assert ok is True
    lines = text.strip().splitlines()
    assert "1. first defect" in lines
    assert "2. second defect" in lines


def test_normalize_bulleted_findings():
    block = "## FINDINGS\nVERDICT: REJECT\n- first\n* second\n+ third"
    text, ok, _ = normalize_block(block)
    assert ok is True
    lines = text.strip().splitlines()
    assert "1. first" in lines
    assert "2. second" in lines
    assert "3. third" in lines


def test_normalize_reject_with_no_findings_is_contradictory_parse_failure():
    # A REJECT that lists nothing must NOT silently render "No findings." (which
    # would read as a clean pass to the judge) — it is a parse failure.
    for body in ("No findings.", "", "the diff has problems somewhere"):
        block = f"## FINDINGS\nVERDICT: REJECT\n{body}"
        text, ok, _ = normalize_block(block)
        assert ok is False, body
        assert text == ""


def test_normalize_genuine_no_findings_is_explicit_empty():
    # Any casing of a genuine "No findings." is a valid explicit empty list.
    for body in ("No findings.", "no findings", "NO FINDINGS"):
        block = f"## FINDINGS\nVERDICT: APPROVE\n{body}"
        text, ok, flagged = normalize_block(block)
        assert ok is True, body
        assert flagged is False
        assert "No findings." in text


def test_normalize_approve_without_findings_or_marker_is_extraction_failure():
    # APPROVE with neither parseable findings nor an explicit "No findings."
    # is an extraction failure, distinct from the explicit-empty case above.
    block = "## FINDINGS\nVERDICT: APPROVE\nThe code reads fine to me."
    _, ok, _ = normalize_block(block)
    assert ok is False


def test_normalize_no_verdict_is_parse_failure():
    block = "## FINDINGS\nsome prose but no verdict line at all"
    text, ok, flagged = normalize_block(block)
    assert (text, ok, flagged) == ("", False, False)


# --------------------------------------------------------------------------- #
# Exotic verdict markdown (cleanup-wave item 10): three variants a weak
# executor might plausibly produce, probed individually.
# --------------------------------------------------------------------------- #
def test_normalize_verdict_as_markdown_heading_already_handled():
    # `## VERDICT: REJECT` as its own heading line. The leading-decoration
    # character class already includes `#` (and the whitespace after it), so
    # this was already handled before this cleanup wave — asserted here as a
    # regression guard, not a new fix.
    block = "## FINDINGS\n## VERDICT: REJECT\n1. a.py:1 — bug"
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is True
    assert "VERDICT: REJECT" in text.splitlines()


def test_normalize_bold_label_colon_outside_verdict():
    # The LABEL is bolded and the colon sits OUTSIDE the closing `**`:
    # `**VERDICT**: REJECT` — distinct from the already-covered
    # `VERDICT: **REJECT**` (bold on the answer word) and
    # `**VERDICT: REJECT**` (bold on the whole line). Fixed by widening
    # _VERDICT_RE to tolerate markdown decoration between the word `VERDICT`
    # and its colon, not just before/after.
    block = "## FINDINGS\n**VERDICT**: REJECT\n1. a.py:1 — bug"
    text, ok, flagged = normalize_block(block)
    assert ok is True
    assert flagged is True
    assert "VERDICT: REJECT" in text.splitlines()


@pytest.mark.xfail(
    reason=(
        "Genuinely ambiguous, not a small regex widening: a markdown table "
        "with VERDICT and REJECT in SEPARATE cells (`| VERDICT | REJECT |`) "
        "splits the label from the value across cell boundaries, so there is "
        "no contiguous 'VERDICT:'-shaped token for _VERDICT_RE to widen "
        "toward without actually parsing table structure (`|`-delimited "
        "cells) -- which risks matching unrelated table rows that merely "
        "mention the words VERDICT/REJECT as data. Left as documented "
        "unsupported input rather than fixed."
    ),
    strict=True,
)
def test_normalize_verdict_split_across_markdown_table_cells_is_ambiguous():
    block = "## FINDINGS\n| Field | Value |\n|---|---|\n| VERDICT | REJECT |\n1. a.py:1 — bug"
    _, ok, _ = normalize_block(block)
    assert ok is True


# --------------------------------------------------------------------------- #
# get_assert — a malformed judge response becomes a judge_error row (finding 3)
# --------------------------------------------------------------------------- #
def test_get_assert_malformed_judge_defects_writes_judge_error_row(tmp_path):
    truth = tmp_path / "truth.yaml"
    truth.write_text("defects:\n  - id: d1\n")
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the findings block.")
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    judge_cfg = {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
        "rubric": str(rubric), "schema": None,
    }
    context = {"vars": {
        "task_id": "t1", "arm": "baseline", "exp_id": "e1", "tier": "weak",
        "seeded": True, "truth_path": str(truth), "results_dir": str(results_dir),
        "judge_json": json.dumps(judge_cfg),
    }}
    output = "workspace text\n## FINDINGS\nVERDICT: REJECT\n1. real.py:1 — a real defect"
    # defect entry is missing its defect_id -> validation fails on both attempts.
    malformed = json.dumps({
        "parse_ok": True,
        "defects": [{"found": True}],
        "false_findings": 0,
        "verdict_flagged": True,
    })

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": malformed}
        res = get_assert(output, context)

    assert res["pass"] is False
    assert "judge_error" in res["reason"]
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_error"] is True
    assert rec["item_pass"] is False
    assert rec["truth_defect_ids"] == ["d1"]
    assert mock_run.call_count == 2  # retried once before failing


def test_get_assert_pins_judge_cwd_to_results_dir_scratch_not_repo_root(tmp_path):
    # Judge blinding (final whole-branch review) is only a prompt-level
    # contract unless get_assert also pins the judge process's cwd away from
    # this worker's own cwd (repo root at eval-run time). get_assert must
    # forward cwd=<results_dir>/judge_scratch through judge_review down to
    # run_codex.
    truth = tmp_path / "truth.yaml"
    truth.write_text("defects: []\n")
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the block.")
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    judge_cfg = {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
        "rubric": str(rubric), "schema": None,
    }
    context = {"vars": {
        "task_id": "t1", "arm": "baseline", "exp_id": "e1", "tier": "weak",
        "seeded": False, "truth_path": str(truth), "results_dir": str(results_dir),
        "judge_json": json.dumps(judge_cfg),
    }}
    output = "workspace text\n## FINDINGS\nVERDICT: APPROVE\nNo findings."
    payload = json.dumps({
        "parse_ok": True, "defects": [], "false_findings": 0,
        "neutral_matched": 0, "verdict_flagged": False,
    })

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload}
        get_assert(output, context)

    assert mock_run.call_args.kwargs["cwd"] == os.path.join(str(results_dir), "judge_scratch")


def test_get_assert_stores_neutral_matched_and_neutral_never_blocks_pass(tmp_path):
    # A seeded item whose only extra finding matches a neutral_findings entry:
    # neutral_matched is stored on the row, false_findings stays 0, and the item
    # still PASSES (all defects found, flagged, no false findings). A neutral
    # match neither credits nor blocks — the item-pass rule is unchanged.
    truth = tmp_path / "truth.yaml"
    truth.write_text(
        "seeded: true\n"
        "defects:\n  - id: d1\n"
        "neutral_findings:\n  - an out-of-scope true observation\n"
    )
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the findings block.")
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    judge_cfg = {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
        "rubric": str(rubric), "schema": None,
    }
    context = {"vars": {
        "task_id": "t1", "arm": "treatment", "exp_id": "e1", "tier": "weak",
        "seeded": True, "truth_path": str(truth), "results_dir": str(results_dir),
        "judge_json": json.dumps(judge_cfg),
    }}
    output = (
        "workspace text\n## FINDINGS\nVERDICT: REJECT\n"
        "1. real.py:1 — the seeded defect\n"
        "2. real.py:9 — an out-of-scope true observation"
    )
    payload = json.dumps({
        "parse_ok": True,
        "defects": [{"defect_id": "d1", "found": True}],
        "false_findings": 0,
        "neutral_matched": 1,
        "verdict_flagged": True,
    })

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload}
        res = get_assert(output, context)

    assert res["pass"] is True
    rec = json.loads((results_dir / "judge" / "treatment-t1.json").read_text())
    assert rec["neutral_matched"] == 1
    assert rec["false_findings"] == 0
    assert rec["item_pass"] is True


def test_get_assert_parse_failure_row_carries_zero_neutral_matched(tmp_path):
    truth = tmp_path / "truth.yaml"
    truth.write_text("seeded: true\ndefects:\n  - id: d1\n")
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the findings block.")
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    judge_cfg = {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
        "rubric": str(rubric), "schema": None,
    }
    context = {"vars": {
        "task_id": "t1", "arm": "baseline", "exp_id": "e1", "tier": "weak",
        "seeded": True, "truth_path": str(truth), "results_dir": str(results_dir),
        "judge_json": json.dumps(judge_cfg),
    }}
    # No VERDICT line -> parse failure -> no judge call.
    output = "workspace text\n## FINDINGS\nnothing parseable here"
    with patch("harness.judge.run_codex") as mock_run:
        res = get_assert(output, context)
    assert res["pass"] is False
    assert mock_run.call_count == 0
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["neutral_matched"] == 0


# --------------------------------------------------------------------------- #
# Judge-side token/cost tracking (cleanup-wave item 2): judge_tokens threaded
# through from run_codex's tokens_used, judge_cost_usd computed only when the
# judge config carries an (optional) usd_per_mtok rate.
# --------------------------------------------------------------------------- #
def _judge_context(tmp_path, judge_cfg_extra=None, seeded=True):
    truth = tmp_path / "truth.yaml"
    truth.write_text("defects:\n  - id: d1\n" if seeded else "defects: []\n")
    rubric = tmp_path / "rubric.md"
    rubric.write_text("Grade the findings block.")
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    judge_cfg = {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
        "rubric": str(rubric), "schema": None,
    }
    if judge_cfg_extra:
        judge_cfg.update(judge_cfg_extra)
    context = {"vars": {
        "task_id": "t1", "arm": "baseline", "exp_id": "e1", "tier": "weak",
        "seeded": seeded, "truth_path": str(truth), "results_dir": str(results_dir),
        "judge_json": json.dumps(judge_cfg),
    }}
    return context, results_dir


def test_get_assert_stores_judge_tokens_on_the_record(tmp_path):
    context, results_dir = _judge_context(tmp_path)
    output = "workspace\n## FINDINGS\nVERDICT: REJECT\n1. real.py:1 — the seeded defect"
    payload = json.dumps({
        "parse_ok": True,
        "defects": [{"defect_id": "d1", "found": True}],
        "false_findings": 0, "neutral_matched": 0, "verdict_flagged": True,
    })
    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload, "tokens_used": 555}
        get_assert(output, context)
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_tokens"] == 555
    assert rec["judge_cost_usd"] is None  # no usd_per_mtok in this judge config


def test_get_assert_judge_tokens_null_when_codex_omits_tokens_used(tmp_path):
    context, results_dir = _judge_context(tmp_path, seeded=False)
    output = "workspace\n## FINDINGS\nVERDICT: APPROVE\nNo findings."
    payload = json.dumps({
        "parse_ok": True, "defects": [], "false_findings": 0,
        "neutral_matched": 0, "verdict_flagged": False,
    })
    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload}  # no tokens_used key at all
        get_assert(output, context)
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_tokens"] is None
    assert rec["judge_cost_usd"] is None


def test_get_assert_computes_judge_cost_usd_when_usd_per_mtok_present(tmp_path):
    context, results_dir = _judge_context(tmp_path, judge_cfg_extra={"usd_per_mtok": 6.0})
    output = "workspace\n## FINDINGS\nVERDICT: REJECT\n1. real.py:1 — the seeded defect"
    payload = json.dumps({
        "parse_ok": True,
        "defects": [{"defect_id": "d1", "found": True}],
        "false_findings": 0, "neutral_matched": 0, "verdict_flagged": True,
    })
    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload, "tokens_used": 500_000}
        get_assert(output, context)
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_tokens"] == 500_000
    assert rec["judge_cost_usd"] == pytest.approx(3.0)  # 0.5 Mtok * $6/Mtok


def test_get_assert_parse_failure_row_carries_null_judge_tokens(tmp_path):
    context, results_dir = _judge_context(tmp_path)
    output = "workspace\n## FINDINGS\nnothing parseable here"
    with patch("harness.judge.run_codex") as mock_run:
        get_assert(output, context)
    assert mock_run.call_count == 0
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_tokens"] is None
    assert rec["judge_cost_usd"] is None


def test_get_assert_judge_error_row_carries_null_judge_tokens(tmp_path):
    context, results_dir = _judge_context(tmp_path)
    output = "workspace\n## FINDINGS\nVERDICT: REJECT\n1. real.py:1 — a real defect"
    malformed = json.dumps({
        "parse_ok": True, "defects": [{"found": True}],  # missing defect_id -> JudgeError
        "false_findings": 0, "verdict_flagged": True,
    })
    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": malformed}
        get_assert(output, context)
    rec = json.loads((results_dir / "judge" / "baseline-t1.json").read_text())
    assert rec["judge_error"] is True
    assert rec["judge_tokens"] is None
    assert rec["judge_cost_usd"] is None
