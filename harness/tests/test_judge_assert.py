"""Findings-block normalizer + get_assert tests.

The normalizer is deterministic and takes no model calls. The one get_assert
test mocks the codex judge (via harness.judge.run_codex) so no live call runs.
"""
import json
import os
from unittest.mock import patch

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
        "parse_ok": True, "defects": [], "false_findings": 0, "verdict_flagged": False,
    })

    with patch("harness.judge.run_codex") as mock_run:
        mock_run.return_value = {"output": payload}
        get_assert(output, context)

    assert mock_run.call_args.kwargs["cwd"] == os.path.join(str(results_dir), "judge_scratch")
