"""Behavioral tests for the failure detector's precision batch + lineage dedup
(weekly-triage sign-off items 2 and 3, 2026-08-08).

Each test drives scan_claude over a synthetic corpus and asserts on emitted
rows — the same surface the nominations/baseline reports are built from.
"""
import corpus_filters as cf
import detect_failure_signatures as dfs

from conftest import (assistant_record, bash_record, user_record,
                      write_claude_session)


def scan(claude_root, monkeypatch):
    monkeypatch.setattr(dfs, "CLAUDE_ROOT", claude_root)
    rows = dfs.Rows()
    n, bad, admissions, forks = dfs.scan_claude(rows, None)
    return rows, admissions, forks


def rows_for(rows, detector):
    return [r for r in rows.rows if r["detector"] == detector]


# ---------------------------------------------------------------- exclusion

def test_sandbox_eval_transcripts_are_excluded(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, cf.REPO_RESULTS_PREFIX + "exp-w3a-sandbox-treatment-mc-01", "aaa",
        [user_record("did you actually read the diff?", "U1"),
         assistant_record("I was wrong about the cache key.", "U2", "aaa")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert rows.rows == []


# ---------------------------------------------------------------- origin filter

def test_sdk_dispatch_briefs_are_not_user_corrections(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [user_record("re-read the target region before patching", "U1",
                     prompt_source="sdk")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert rows_for(rows, "user_correction") == []


def test_task_notifications_are_not_user_corrections(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [user_record("<task-notification>you didn't check L42</task-notification>",
                     "U1", prompt_source="sdk", origin_kind="task-notification")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert rows_for(rows, "user_correction") == []


def test_typed_human_correction_still_detected(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [user_record("you didn't run the full suite", "U1")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert len(rows_for(rows, "user_correction")) == 1


def test_legacy_turn_without_origin_fields_still_detected(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [user_record("you didn't run the full suite", "U1",
                     prompt_source=None, origin_kind=None)])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert len(rows_for(rows, "user_correction")) == 1


# ---------------------------------------------------------------- pipe precision

def test_quoted_test_verb_is_not_a_truncated_test(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [bash_record('grep -rn "cargo test" tools/*.sh .github/workflows/*.yml | head -20',
                     "U1", "aaa")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert rows_for(rows, "pipe_truncated_test") == []


def test_quoted_check_verb_is_not_a_truncated_check(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [bash_record('echo "test suite banner" | head -5', "U1", "aaa")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert rows_for(rows, "pipe_truncated_check") == []


def test_real_truncated_test_still_detected(corpora, monkeypatch):
    claude_root, _ = corpora
    write_claude_session(
        claude_root, "-Users-x-code-proj", "aaa",
        [bash_record("cargo test -p historical-backfill 2>&1 | tail -25", "U1", "aaa")])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert len(rows_for(rows, "pipe_truncated_test")) == 1


# ---------------------------------------------------------------- lineage dedup

def fork_corpus(claude_root):
    """Parent 'aaa' with two admissions; fork 'bbb' copying the first record
    verbatim (same uuid/session_id, its own file) plus one fork-native
    admission. Mirrors the 9aea8b01 <- 608a7a2a compaction fork."""
    copied = assistant_record("I was wrong about the cache key.", "U1", "aaa",
                              ts="2026-07-22T19:32:00.000Z")
    write_claude_session(claude_root, "-Users-x-code-proj", "aaa", [
        copied,
        assistant_record("My mistake — the flag was inverted.", "U2", "aaa",
                         ts="2026-07-22T19:40:00.000Z"),
    ])
    write_claude_session(claude_root, "-Users-x-code-proj", "bbb", [
        copied,
        assistant_record("I misread the timeout units.", "U3", "aaa",
                         ts="2026-07-22T20:00:00.000Z"),
    ])


def test_copied_admission_counted_once_and_attributed_to_origin(corpora, monkeypatch):
    claude_root, _ = corpora
    fork_corpus(claude_root)
    rows, _, _ = scan(claude_root, monkeypatch)
    admissions = rows_for(rows, "admission")
    assert len(admissions) == 3  # U1 once, U2, U3 — not 4
    u1 = [r for r in admissions if r["snippet"].startswith("I was wrong")]
    assert len(u1) == 1
    assert u1[0]["session"] == "aaa"  # origin file's copy survives


def test_copied_user_correction_counted_once(corpora, monkeypatch):
    claude_root, _ = corpora
    copied = user_record("you didn't run the full suite", "U9",
                         ts="2026-07-22T19:32:00.000Z")
    write_claude_session(claude_root, "-Users-x-code-proj", "aaa", [copied])
    write_claude_session(claude_root, "-Users-x-code-proj", "bbb", [
        copied,
        assistant_record("ok.", "U3", "aaa"),
    ])
    rows, _, _ = scan(claude_root, monkeypatch)
    assert len(rows_for(rows, "user_correction")) == 1


def test_recurrence_metric_not_inflated_by_copies(corpora, monkeypatch):
    claude_root, _ = corpora
    fork_corpus(claude_root)
    _, admissions, _ = scan(claude_root, monkeypatch)
    # Logical session 'aaa' has exactly 3 distinct strong admissions (U1,U2,U3);
    # the fork's copy of U1 must not add a 4th, and 'bbb' must not appear as
    # its own session.
    assert set(admissions) == {"aaa"}
    assert len(admissions["aaa"]) == 3


def test_file_level_lineage_dupe_detector_still_fires(corpora, monkeypatch):
    claude_root, _ = corpora
    fork_corpus(claude_root)
    rows, _, forks = scan(claude_root, monkeypatch)
    assert ("bbb.jsonl", "aaa.jsonl") in forks
    assert len(rows_for(rows, "lineage_dupe")) == 1
