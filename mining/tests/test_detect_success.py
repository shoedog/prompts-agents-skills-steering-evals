"""Behavioral tests for the success detector: lineage dedup, sandbox
exclusion, and the codex.expect_falsify_probe nomination demotion
(weekly-triage sign-off items 2 and 3, 2026-08-08)."""
import sys

import corpus_filters as cf
import detect_success_signatures as dss

from conftest import (assistant_record, codex_agent_message, edit_record,
                      write_claude_session, write_codex_rollout)


def scan(claude_root, monkeypatch):
    monkeypatch.setattr(dss, "CLAUDE_ROOT", claude_root)
    rows = dss.Rows()
    n, bad, qualifying, meta = dss.scan_claude(rows, None)
    return rows, qualifying


def rows_for(rows, detector):
    return [r for r in rows.rows if r["detector"] == detector]


def test_sandbox_eval_transcripts_are_excluded(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, cf.REPO_RESULTS_PREFIX + "exp-w3a-sandbox-baseline-mc-02", "aaa",
        [assistant_record("the base-control run fails identically at base.", "U1", "aaa")])
    rows, _ = scan(claude_root, monkeypatch)
    assert rows.rows == []


def test_copied_refutation_counted_once(corpora, monkeypatch):
    claude_root, _ = corpora
    copied = assistant_record(
        "The reviewer refuted claim 1(a); accepting the correction into the record.",
        "U1", "aaa", ts="2026-07-22T19:32:00.000Z")
    write_claude_session(claude_root, "-Users-x-code-proj", "aaa", [copied])
    write_claude_session(claude_root, "-Users-x-code-proj", "bbb", [
        copied,
        assistant_record("continuing.", "U2", "aaa"),
    ])
    rows, _ = scan(claude_root, monkeypatch)
    refut = rows_for(rows, "refutation_accepted")
    assert len(refut) == 1
    assert refut[0]["session"] == "aaa"
    # counts/key_sessions must agree with the deduplicated rows
    assert rows.counts["claude.refutation_accepted.prose"] == 1
    assert rows.key_sessions["claude.refutation_accepted.prose"] == {"aaa"}


def test_checkpoint_cadence_not_inflated_by_copied_edits(corpora, monkeypatch):
    claude_root, _ = corpora
    edits = [edit_record("/Users/x/HANDOFF-prog.md", f"E{i}", "aaa",
                         ts=f"2026-07-22T19:3{i}:00.000Z") for i in range(3)]
    write_claude_session(claude_root, "-Users-x-code-proj", "aaa", edits)
    # fork copies all three edit records, adds none of its own
    write_claude_session(claude_root, "-Users-x-code-proj", "bbb",
                         edits + [assistant_record("continuing.", "U2", "aaa")])
    rows, qualifying = scan(claude_root, monkeypatch)
    cadence = rows_for(rows, "checkpoint_cadence")
    assert len(cadence) == 1  # one logical session, not one per file
    assert set(qualifying) == {"aaa"}
    assert qualifying["aaa"] == 3  # 3 distinct edits, not 6


def test_codex_expect_falsify_demoted_from_nominations(corpora, monkeypatch, tmp_path):
    claude_root, codex_root = corpora
    write_codex_rollout(
        codex_root, "rollout-2026-08-01T10-00-00-abc",
        [codex_agent_message(
            "Expected: incremental dir measured in gigabytes; falsifier: a small "
            "fraction, which would point to duplicated dependency builds. "
            "Hypothesis falsified by the probe.")])
    out_dir = tmp_path / "out"
    monkeypatch.setattr(dss, "CLAUDE_ROOT", claude_root)
    monkeypatch.setattr(dss, "CODEX_ROOT", codex_root)
    monkeypatch.setattr(dss, "OUT_DIR", out_dir)
    monkeypatch.setattr(sys, "argv", ["detect_success_signatures.py"])
    dss.main()

    noms = (out_dir / "success_nominations.md").read_text()
    baseline = (out_dir / "success_baseline.md").read_text()
    assert "## codex.expect_falsify_probe" not in noms  # demoted from the feed
    assert "codex.expect_falsify_probe" in baseline     # still an adoption metric
    assert "| codex.expect_falsify_probe.prose | 1 |" in baseline
