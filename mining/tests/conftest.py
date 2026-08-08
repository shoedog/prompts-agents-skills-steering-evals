"""Shared fixtures for mining-pipeline tests: synthetic claude/codex corpora.

Claude fixture records mirror the real transcript schema closely enough for
the detectors: top-level type/uuid/timestamp/session_id/cwd/isSidechain plus
a message with role/content (and model for assistant turns). session_id is
the LOGICAL session (stamped on assistant records; absent on user records,
matching the real corpus), while the filename is the physical session.
"""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def assistant_record(text, uuid, session_id, ts="2026-08-01T10:00:00.000Z",
                     cwd="/Users/x/code/proj", content_blocks=None, model="claude-fable-5"):
    return {
        "type": "assistant", "uuid": uuid, "session_id": session_id,
        "timestamp": ts, "cwd": cwd, "isSidechain": False,
        "message": {"role": "assistant", "model": model,
                    "content": content_blocks if content_blocks is not None
                    else [{"type": "text", "text": text}]},
    }


def user_record(text, uuid, ts="2026-08-01T10:00:00.000Z",
                cwd="/Users/x/code/proj", prompt_source="typed",
                origin_kind="human"):
    rec = {
        "type": "user", "uuid": uuid, "timestamp": ts, "cwd": cwd,
        "isSidechain": False,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }
    if prompt_source is not None:
        rec["promptSource"] = prompt_source
    if origin_kind is not None:
        rec["origin"] = {"kind": origin_kind}
    return rec


def bash_record(command, uuid, session_id, ts="2026-08-01T10:00:00.000Z"):
    return assistant_record(
        None, uuid, session_id, ts=ts,
        content_blocks=[{"type": "tool_use", "name": "Bash",
                         "input": {"command": command}}])


def edit_record(file_path, uuid, session_id, new_string="checkpoint note",
                ts="2026-08-01T10:00:00.000Z"):
    return assistant_record(
        None, uuid, session_id, ts=ts,
        content_blocks=[{"type": "tool_use", "name": "Edit",
                         "input": {"file_path": file_path,
                                   "old_string": "x", "new_string": new_string}}])


def write_claude_session(claude_root, project, stem, records):
    proj = claude_root / project
    proj.mkdir(parents=True, exist_ok=True)
    path = proj / f"{stem}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def write_codex_rollout(codex_root, name, events, day="2026/08/01"):
    d = codex_root / day
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def codex_agent_message(text, ts="2026-08-01T10:00:00.000Z"):
    return {"type": "event_msg", "timestamp": ts,
            "payload": {"type": "agent_message", "message": text}}


@pytest.fixture
def corpora(tmp_path):
    claude_root = tmp_path / "claude_projects"
    codex_root = tmp_path / "codex_sessions"
    claude_root.mkdir()
    codex_root.mkdir()
    return claude_root, codex_root
