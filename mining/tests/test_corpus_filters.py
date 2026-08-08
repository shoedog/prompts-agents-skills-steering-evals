"""Unit tests for mining/scripts/corpus_filters.py (detector-precision batch +
lineage dedup, weekly-triage sign-off items 2 and 3, 2026-08-08)."""
from pathlib import Path

import corpus_filters as cf


# ---------------------------------------------------------------- exclusion

def test_repo_results_prefix_is_this_repos_results_dir():
    repo = Path(__file__).resolve().parent.parent.parent
    assert cf.REPO_RESULTS_PREFIX == str(repo).replace("/", "-") + "-results-"


def test_excludes_eval_sandbox_project_dirs(tmp_path):
    proj = tmp_path / (cf.REPO_RESULTS_PREFIX + "exp-w3a-negative-control-mid-sandbox-baseline-mc-04")
    proj.mkdir()
    session = proj / "abc.jsonl"
    session.touch()
    assert cf.is_excluded_claude_project(session)


def test_keeps_ordinary_project_dirs(tmp_path):
    for name in ("-Users-x-code-proj",
                 "-Users-x-code-sandbox-play",       # 'sandbox' outside this repo's results/
                 "-Users-x-code-my-results-exp"):    # 'results-exp' outside this repo
        proj = tmp_path / name
        proj.mkdir()
        session = proj / "abc.jsonl"
        session.touch()
        assert not cf.is_excluded_claude_project(session), name


# ---------------------------------------------------------------- strip_quoted

def test_strip_quoted_removes_quoted_spans():
    cmd = 'grep -rn "cargo test" tools/*.sh | head -20'
    assert "cargo test" not in cf.strip_quoted(cmd)
    assert "| head" in cf.strip_quoted(cmd)


def test_strip_quoted_keeps_unquoted_text():
    cmd = "cargo test -p historical-backfill 2>&1 | tail -25"
    assert cf.strip_quoted(cmd) == cmd


def test_strip_quoted_handles_single_quotes():
    assert "npm test" not in cf.strip_quoted("echo 'npm test done' | tail -1")


# ---------------------------------------------------------------- origin filter

def test_sdk_prompt_source_is_nonhuman():
    assert cf.is_nonhuman_user_turn({"promptSource": "sdk", "origin": {"kind": "human"}})


def test_task_notification_origin_is_nonhuman():
    assert cf.is_nonhuman_user_turn({"promptSource": "sdk",
                                     "origin": {"kind": "task-notification"}})


def test_typed_human_turn_is_human():
    assert not cf.is_nonhuman_user_turn({"promptSource": "typed", "origin": {"kind": "human"}})


def test_legacy_record_without_fields_is_human():
    # Old transcripts predate promptSource/origin; they are real human turns.
    assert not cf.is_nonhuman_user_turn({})


# ---------------------------------------------------------------- lineage dedup

def _row(uuid, session_id, path, detector="admission", bucket="strong",
         snippet="I was wrong", line_no=1):
    return {"corpus": "claude", "detector": detector, "bucket": bucket,
            "path": path, "session": Path(path).stem, "line_no": line_no,
            "ts": "2026-07-22T19:32:00.000Z", "model": "m", "cwd": "/x",
            "sidechain": False, "snippet": snippet,
            "uuid": uuid, "session_id": session_id}


def test_dedupe_collapses_copied_record_prefers_origin_file():
    parent = "/p/608a7a2a.jsonl"
    fork = "/p/9aea8b01.jsonl"
    rows = [
        _row("U1", "608a7a2a", fork),      # fork's copy listed FIRST on purpose
        _row("U1", "608a7a2a", parent),    # original
        _row("U3", "608a7a2a", fork, snippet="my mistake"),  # fork-native record
    ]
    kept, n_suppressed = cf.dedupe_rows(rows)
    assert n_suppressed == 1
    u1 = [r for r in kept if r["uuid"] == "U1"]
    assert len(u1) == 1
    assert u1[0]["path"] == parent  # origin file's copy survives
    assert len([r for r in kept if r["uuid"] == "U3"]) == 1


def test_dedupe_keeps_distinct_records_and_uuidless_rows():
    rows = [
        _row("U1", "s1", "/p/s1.jsonl"),
        _row("U2", "s1", "/p/s1.jsonl", snippet="other"),
        _row(None, None, "/p/s1.jsonl", detector="lineage_dupe", bucket="lineage_dupe"),
        _row(None, None, "/p/s2.jsonl", detector="lineage_dupe", bucket="lineage_dupe"),
    ]
    kept, n_suppressed = cf.dedupe_rows(rows)
    assert n_suppressed == 0
    assert len(kept) == 4


def test_dedupe_distinguishes_same_uuid_different_detector():
    # One record can legitimately fire two different detectors.
    rows = [
        _row("U1", "s1", "/p/s1.jsonl", detector="admission"),
        _row("U1", "s1", "/p/s1.jsonl", detector="user_correction"),
    ]
    kept, n_suppressed = cf.dedupe_rows(rows)
    assert n_suppressed == 0
    assert len(kept) == 2
