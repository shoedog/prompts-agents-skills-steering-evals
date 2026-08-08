#!/usr/bin/env python3
"""Shared precision filters for the mining detectors (2026-08-08 batch;
weekly-triage sign-off items 2+3).

Four defects in the measurement instrument, found by the 2026-08-07 triage
panel + cleanroom comparison, fixed here in one place so both detectors and
the triage pipeline agree:

  1. Corpus contamination: this repo's eval-harness sandbox transcripts
     (results/exp-* runs) live under ~/.claude/projects/ like real sessions;
     their PROMPT text trips the detectors (177 rows on 2026-08-07).
  2. Non-human "user" turns: SDK dispatch briefs and <task-notification>
     subagent reports are user-typed records only in shape; they are not the
     human correcting the agent.
  3. Quoted verbs: `grep -rn "cargo test" … | head` is discovery, not a
     truncated test run — command-verb matching must ignore quoted spans.
  4. Lineage double-counting: post-compaction continuation files copy the
     parent's records verbatim (same uuid; assistant records also keep the
     parent's session_id while user records carry none). Naive per-file
     mining counts one event once per file, inflating both row counts and
     the "across N sessions" priority denominator.

Runs under /usr/bin/python3 (3.9) in cron — keep 3.9-compatible.
"""
from __future__ import annotations

import re
from pathlib import Path

# ~/.claude project dirs are the session cwd with '/' -> '-'; anything under
# this repo's results/ dir is an eval-run sandbox, not a real work session.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_RESULTS_PREFIX = str(_REPO_ROOT).replace("/", "-") + "-results-"

_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')


def is_excluded_claude_project(session_path: Path) -> bool:
    """True when the session file lives in a project dir produced by this
    repo's eval runs (results/ sandboxes) — excluded from mining."""
    return Path(session_path).parent.name.startswith(REPO_RESULTS_PREFIX)


def strip_quoted(command: str) -> str:
    """Blank out quoted spans so verb patterns match only real shell words."""
    return _QUOTED.sub(" ", command)


def is_nonhuman_user_turn(obj: dict) -> bool:
    """True for user-typed records that are not the human at the keyboard:
    SDK-dispatched briefs and task-notification/subagent-origin turns.
    Records predating these fields are real human turns (fields absent)."""
    if obj.get("promptSource") == "sdk":
        return True
    origin = obj.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return True
    return False


def logical_session(obj: dict, path: Path) -> str:
    """The session an event logically belongs to: the record's session_id
    (stable across compaction chains) when present, else the file stem."""
    sid = obj.get("session_id")
    return sid if isinstance(sid, str) and sid else Path(path).stem


def _dedupe_preference(row: dict):
    """Sort key among duplicate rows: prefer the copy in its origin file
    (file stem == logical session), then the oldest file, then path order."""
    path = Path(row["path"]).expanduser()
    logical = row.get("session_id") or path.stem
    try:
        st = path.stat()
        born = getattr(st, "st_birthtime", None) or st.st_mtime
    except OSError:
        born = float("inf")
    return (0 if path.stem == logical else 1, born, str(path))


def dedupe_rows(rows: list) -> "tuple[list, int]":
    """Collapse rows emitted for byte-identical copied records (same uuid,
    same detector/bucket/snippet across files). Rows without a uuid are
    session-level or synthetic and pass through untouched. Returns
    (kept_rows, n_suppressed); kept rows preserve input order."""
    best: dict = {}
    for row in rows:
        uid = row.get("uuid")
        if not uid:
            continue
        key = (uid, row["detector"], row["bucket"], row["snippet"])
        cur = best.get(key)
        if cur is None or _dedupe_preference(row) < _dedupe_preference(cur):
            best[key] = row
    kept, n_suppressed = [], 0
    for row in rows:
        uid = row.get("uuid")
        if not uid:
            kept.append(row)
            continue
        key = (uid, row["detector"], row["bucket"], row["snippet"])
        if best.get(key) is row:
            kept.append(row)
        else:
            n_suppressed += 1
    return kept, n_suppressed
