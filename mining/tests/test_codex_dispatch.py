"""Tests for codex_dispatch.py — the null-final hook with error
classification (weekly-triage sign-off item 1, owner-approved 2026-08-08).

Grounded in the two real incidents:
- rollout-2026-08-05T19-31 L11983: OAuth refresh death after 5.2h —
  task_complete{last_agent_message: null, error.codex_error_info:
  "unauthorized"}. Blind respawn would have re-burned the run.
- rollout-2026-07-24T01-54 L11-12: credit exhaustion — task_complete with NO
  error field; the signal is the preceding token_count event's
  rate_limits.credits.has_credits == false.

End-to-end tests drive main() against a fake `codex` binary (no API calls).
"""
import json
import stat
import sys

import pytest

import codex_dispatch as cd


# ---------------------------------------------------------------- fixtures

def token_count(total_tokens=1000, has_credits=True):
    return {"type": "event_msg", "timestamp": "2026-08-08T10:00:00.000Z",
            "payload": {"type": "token_count",
                        "info": {"total_token_usage": {"total_tokens": total_tokens}},
                        "rate_limits": {"credits": {"has_credits": has_credits}}}}


def task_complete(last_agent_message, error=None, duration_ms=1234):
    p = {"type": "task_complete", "last_agent_message": last_agent_message,
         "duration_ms": duration_ms}
    if error is not None:
        p["error"] = error
    return {"type": "event_msg", "timestamp": "2026-08-08T10:00:01.000Z", "payload": p}


def write_rollout(root, session_id, events, day="2026/08/08"):
    d = root / day
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"rollout-2026-08-08T10-00-00-{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


BANNER = """OpenAI Codex v0.146.0
--------
workdir: /x
model: gpt-5.6-sol
session id: {sid}
--------
"""


# ---------------------------------------------------------------- units

def test_parse_session_id():
    assert cd.parse_session_id(BANNER.format(sid="019fdfc7-9564-7af2-a5a4-172f46c6d899")) \
        == "019fdfc7-9564-7af2-a5a4-172f46c6d899"
    assert cd.parse_session_id("no banner here") is None


def test_find_rollout(tmp_path):
    p = write_rollout(tmp_path, "019faaaa-1111-7000-8000-000000000001",
                      [task_complete("done")])
    assert cd.find_rollout("019faaaa-1111-7000-8000-000000000001", tmp_path) == p
    assert cd.find_rollout("019fdead-0000-7000-8000-000000000000", tmp_path) is None


def test_read_terminal_events(tmp_path):
    p = write_rollout(tmp_path, "019faaaa-1111-7000-8000-000000000002", [
        token_count(total_tokens=555, has_credits=True),
        task_complete(None, error={"codex_error_info": "unauthorized",
                                   "message": "refresh token was already used"},
                      duration_ms=18736748),
    ])
    t = cd.read_terminal_events(p)
    assert t["task_complete"]["duration_ms"] == 18736748
    assert t["has_credits"] is True
    assert t["last_total_tokens"] == 555


def test_classify_auth_death():
    v = cd.classify({"task_complete": {"last_agent_message": None,
                                       "error": {"codex_error_info": "unauthorized",
                                                 "message": "refresh token was already used"},
                                       "duration_ms": 18736748},
                     "has_credits": True, "last_total_tokens": 5, "had_output": True})
    assert v["kind"] == "auth"
    assert v["infrastructure"] and not v["retryable"]


def test_classify_credit_death():
    # the real credit death: empty final, NO error field, has_credits false
    v = cd.classify({"task_complete": {"last_agent_message": None, "duration_ms": 1901},
                     "has_credits": False, "last_total_tokens": 7, "had_output": False})
    assert v["kind"] == "credit"
    assert v["infrastructure"] and not v["retryable"]


def test_classify_other_error_not_retryable():
    v = cd.classify({"task_complete": {"last_agent_message": "",
                                       "error": {"message": "internal server error"}},
                     "has_credits": True, "last_total_tokens": 1, "had_output": False})
    assert v["kind"] == "error"
    assert not v["retryable"]


def test_classify_empty_no_error_is_retryable():
    v = cd.classify({"task_complete": {"last_agent_message": None},
                     "has_credits": True, "last_total_tokens": 1, "had_output": True})
    assert v["kind"] == "empty-no-error"
    assert v["retryable"] and not v["infrastructure"]


def test_classify_ok_and_no_completion():
    ok = cd.classify({"task_complete": {"last_agent_message": "findings: none"},
                      "has_credits": True, "last_total_tokens": 1, "had_output": True})
    assert ok["kind"] == "ok"
    dead = cd.classify({"task_complete": None, "has_credits": None,
                        "last_total_tokens": None, "had_output": False})
    assert dead["kind"] == "no-completion"
    assert dead["retryable"]


# ---------------------------------------------------------------- end-to-end

FAKE_CODEX = """#!/bin/bash
# fake codex: `login status` honours FAKE_LOGIN_OK; `exec` prints a banner,
# copies the scripted rollout into the fake sessions root, and echoes stdin
# consumption; invocation count kept in $FAKE_COUNT_FILE.
if [ "$1" = "login" ]; then
  [ "${FAKE_LOGIN_OK:-1}" = "1" ] && { echo "Logged in using ChatGPT"; exit 0; }
  echo "Not logged in"; exit 1
fi
n=$(cat "$FAKE_COUNT_FILE" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$FAKE_COUNT_FILE"
sid=$(sed -n "${n}p" "$FAKE_SID_LIST")
echo "OpenAI Codex v0.146.0"
echo "session id: $sid"
cat > /dev/null   # consume stdin like the real thing
exit "${FAKE_EXEC_RC:-0}"
"""


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    """Fake codex bin + sessions root, wired via the env vars the wrapper honours."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "codex"
    fake.write_text(FAKE_CODEX)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    crash_log = tmp_path / "crashes.jsonl"
    monkeypatch.setenv("CODEX_DISPATCH_BIN", str(fake))
    monkeypatch.setenv("CODEX_DISPATCH_SESSIONS_ROOT", str(sessions))
    monkeypatch.setenv("CODEX_DISPATCH_NO_NOTIFY", "1")
    monkeypatch.setenv("FAKE_COUNT_FILE", str(tmp_path / "count"))
    monkeypatch.setenv("FAKE_SID_LIST", str(tmp_path / "sids"))
    return {"tmp": tmp_path, "sessions": sessions, "crash_log": crash_log,
            "sid_list": tmp_path / "sids", "count": tmp_path / "count"}


def run_main(fake_env, tmp_path, extra_args=(), stdin_text="prompt\n"):
    log = tmp_path / "dispatch.log"
    argv = ["codex_dispatch.py", "--log", str(log),
            "--crash-log", str(fake_env["crash_log"]), *extra_args, "--", "-"]
    old_argv, old_stdin = sys.argv, sys.stdin
    sys.argv = argv
    import io
    sys.stdin = io.StringIO(stdin_text)
    try:
        rc = cd.main()
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin
    return rc, log


def seed(fake_env, sids_and_events):
    """Script the fake codex: one sid per invocation + its rollout content."""
    fake_env["sid_list"].write_text("\n".join(sid for sid, _ in sids_and_events) + "\n")
    for sid, events in sids_and_events:
        if events is not None:
            write_rollout(fake_env["sessions"], sid, events)


def crash_records(fake_env):
    if not fake_env["crash_log"].exists():
        return []
    return [json.loads(l) for l in fake_env["crash_log"].read_text().splitlines()]


def test_e2e_success(fake_env, tmp_path):
    seed(fake_env, [("019f0000-0000-7000-8000-000000000010",
                     [token_count(), task_complete("all good, 3 findings")])])
    rc, _ = run_main(fake_env, tmp_path)
    assert rc == 0
    assert crash_records(fake_env) == []


def test_e2e_auth_death_alerts_and_does_not_retry(fake_env, tmp_path, capsys):
    seed(fake_env, [("019f0000-0000-7000-8000-000000000011",
                     [token_count(total_tokens=42),
                      task_complete(None, error={"codex_error_info": "unauthorized",
                                                 "message": "refresh token was already used"},
                                    duration_ms=18736748)])])
    rc, _ = run_main(fake_env, tmp_path, extra_args=("--retry-once",))
    assert rc == 97
    assert fake_env["count"].read_text().strip() == "1"  # no respawn on infrastructure death
    recs = crash_records(fake_env)
    assert len(recs) == 1
    assert recs[0]["kind"] == "auth"
    assert recs[0]["duration_ms"] == 18736748
    assert recs[0]["last_total_tokens"] == 42
    assert "INFRASTRUCTURE" in capsys.readouterr().err


def test_e2e_empty_no_error_retries_once_then_succeeds(fake_env, tmp_path):
    seed(fake_env, [
        ("019f0000-0000-7000-8000-000000000012", [token_count(), task_complete(None)]),
        ("019f0000-0000-7000-8000-000000000013", [token_count(), task_complete("done")]),
    ])
    rc, _ = run_main(fake_env, tmp_path, extra_args=("--retry-once",))
    assert rc == 0
    assert fake_env["count"].read_text().strip() == "2"
    # the failed first round is still recorded — never silently absorbed
    assert [r["kind"] for r in crash_records(fake_env)] == ["empty-no-error"]


def test_e2e_empty_without_retry_flag_fails_loudly(fake_env, tmp_path):
    seed(fake_env, [("019f0000-0000-7000-8000-000000000014",
                     [token_count(), task_complete(None)])])
    rc, _ = run_main(fake_env, tmp_path)
    assert rc == 98  # an empty final NEVER passes as success
    assert [r["kind"] for r in crash_records(fake_env)] == ["empty-no-error"]


def test_e2e_preflight_refuses_when_logged_out(fake_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_LOGIN_OK", "0")
    seed(fake_env, [("019f0000-0000-7000-8000-000000000015", None)])
    rc, _ = run_main(fake_env, tmp_path)
    assert rc == 97
    assert not fake_env["count"].exists()  # exec never launched
    assert [r["kind"] for r in crash_records(fake_env)] == ["preflight-auth"]
    assert "INFRASTRUCTURE" in capsys.readouterr().err
