"""Panel fixtures for the standalone bash evidence guard.

Every shell command below is a concrete command from the v2 panel record:
SPEC.md (opus lane) or mining/out/guard-review/sol-review.md (Codex/sol lane).
The expected rules reflect SPEC.md v2 where it intentionally supersedes a
review proposal (notably the dropped ``|| true`` / ``; true`` heuristic).
"""
import contextlib
import io
import json
import sys
from pathlib import Path

import pytest


VALIDATORS = Path(__file__).resolve().parents[2] / "validators"
sys.path.insert(0, str(VALIDATORS))

import bash_evidence_guard as guard


def rules(command):
    """Return the panel rule IDs fired for one command string."""
    return [finding.rule for finding in guard.analyze_command(command)]


def run_hook(fn, payload, *args, **kwargs):
    """Run an adapter with a synthetic hook payload, like brief_lint's helper."""
    old_stdin = sys.stdin
    out, err = io.StringIO(), io.StringIO()
    try:
        sys.stdin = io.StringIO(payload)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn(*args, **kwargs)
    finally:
        sys.stdin = old_stdin
    return rc, out.getvalue(), err.getvalue()


# W1 through W7.  The case names retain the review reference so a future
# regression can be traced to the panel's exact counterexample.
@pytest.mark.parametrize("command, expected", [
    ("cargo test -p historical-backfill 2>&1 | tail -25", ["E1"]),  # W1
    ('bash -lc "cargo test 2>&1 | tail -25"', ["E1"]),  # W2
    ("bash -lc 'cargo test 2>&1 | tail -25'", ["E1"]),  # W2
    ("printf '%s\\n' \"$(cargo test 2>&1 | tail -25)\"", ["E1"]),  # W2
    ("printf '%s\\n' \"`cargo test 2>&1 | tail -25`\"", ["E1"]),  # W2
    ('printf "\\\" cargo test" | head -1', []),  # W2 literal data anti-finding
    ("cargo test && git log --oneline | head -5", []),  # W3
    ("printf 'banner\\n' | tail -1 ; cargo test", []),  # W3
    ("cargo test && git status --short | grep -c '^ M'", []),  # W3
    ("cargo test 2>&1 | tail -25 ; printf ok > marker 2>&1", ["E1"]),  # W4
    ("cargo test 2>&1 | tail -25 ; printf ok 2>&1 | tee note.log", ["E1"]),  # W4
    ("cargo test 2>&1 | tee /dev/null | tail -25", ["E1"]),  # W4
    ("cargo test 2>&1 | tail -25 ; rustc --version", ["E1"]),  # W4
    ("cargo test >full.log 2>&1 | tail -25", ["E2b"]),  # W4 capture/status split
    ("zsh -c 'set -e; ( false ); printf \"continued=YES\\n\"'", []),  # W5 control
    ("cargo test 2>&1 |& tail -25", ["E1"]),  # W6
    ("cargo test 2>&1 | /usr/bin/tail -25", ["E1"]),  # W6
    ("cargo test 2>&1 | env LC_ALL=C tail -25", ["E1"]),  # W6
    ("cmd || tail", []),  # W6: || is not a pipeline
    ("cargo nextest list | head -20", []),  # W7 compile/list anti-finding
    ("tox -e py311 2>&1 | tail -25", ["E1"]),  # W7
    ("ctest --output-on-failure 2>&1 | tail -25", ["E1"]),  # W7
    ("bun test 2>&1 | tail -25", ["E1"]),  # W7
    ("deno test 2>&1 | tail -25", ["E1"]),  # W7
])
def test_sol_w1_through_w7_fixture_matrix(command, expected):
    assert rules(command) == expected


def test_sol_w5_literal_incident_fires_e2a_despite_pipefail():
    """The real fb80415b incident ran under `set -euo pipefail`; pipefail is
    irrelevant to the subshell mechanism, so the literal fixture MUST fire
    (spec v2.1 correction — v2's global pipefail-absence requirement made
    the rule miss its own motivating incident)."""
    command = """set -euo pipefail
( cd /missing/table; shasum -a 256 _meta _txn ) > original-key-sha256.txt
printf '%s\\n' 'forensic_capture=PASS'"""
    assert rules(command) == ["E2a"]


def test_e2a_pipeline_branch_requires_pipefail_absent():
    fires = "set -e\nfalse | tail -1\necho gate PASS"
    safe = "set -eo pipefail\nfalse | tail -1\necho gate PASS"
    assert rules(fires) == ["E2a"]
    assert rules(safe) == []


@pytest.mark.parametrize("command", [
    "cargo test 2>&1 | head -25",
    "cargo test 2>&1 | tail -25",
    "cargo test 2>&1 | grep -c FAILED",
    "cargo test 2>&1 | grep -q FAILED",
    "cargo test 2>&1 | grep -m 1 FAILED",
    "cargo test 2>&1 | wc -l",
])
def test_sol_e1_decision_table_ship_warn(command):
    assert rules(command) == ["E1"]


@pytest.mark.parametrize("command, expected", [
    # E1 is deferred for sed, but v2 E2b still warns because a runner pipeline
    # ending in any non-runner loses the runner's status.
    ("cargo test | sed -n '1,20p'", ["E2b"]),
    ("cargo test --no-run | tail -25", []),
    ("cargo test >full.log 2>&1", []),
])
def test_sol_e1_deferred_or_runner_scoped_allowances_do_not_fire(command, expected):
    assert rules(command) == expected


@pytest.mark.parametrize("command", [
    "false; rc=$?; printf '%s\\n' \"$rc\" >/dev/null",
    "false; rc=$?; printf '%s\\n' \"$rc\" >/dev/null; exit \"$rc\"",
    "cargo test || true",
    "cargo test ; true",
    "bash -c 'set -e; false | tail -1; printf \"continued=YES pipeline_status=%s\\n\" \"$?\"'",
    "bash -c 'set -eo pipefail; false | tail -1; printf \"continued=YES\\n\"'",
])
def test_sol_e2_dropped_or_non_runner_decision_table_shapes_do_not_fire(command):
    assert rules(command) == []


def test_sol_e2_tee_status_decision_fires_e2b():
    assert rules("cargo test 2>&1 | tee full.log") == ["E2b"]


@pytest.mark.parametrize("command, expected", [
    ("make test && git log --oneline | head -20", []),
    ('bash -lc "pytest -q | tail -5"', ["E1"]),
    ("npm test | tail -40 | tee f", ["E1"]),
    ("cargo test | tee /dev/null | tail -25", ["E1"]),
    ("cargo test >full.log 2>&1 | tail -25", ["E2b"]),
    ('grep -rn "cargo test" tools/*.sh | head -20', []),
    ("cargo test -p hb |& tail -25", ["E1"]),
])
def test_opus_stage_aware_fixtures(command, expected):
    assert rules(command) == expected


def test_opus_fb80415b_set_e_subshell_pass_sentinel_fires_e2a():
    command = """set -eu
( cd /missing/table; shasum -a 256 _meta _txn ) > original-key-sha256.txt
printf '%s\\n' 'forensic_capture=PASS'"""
    assert rules(command) == ["E2a"]


def test_opus_multiline_collect_only_does_not_allow_later_pytest_pipeline():
    command = "pytest --collect-only | head -5\npytest -q | tail -5"
    findings = guard.analyze_command(command)
    assert [finding.rule for finding in findings] == ["E1"]
    assert "pytest -q" in findings[0].subject


def test_escape_hatch_is_literal_and_logged_for_a_runner(monkeypatch, tmp_path):
    log = tmp_path / "guard.jsonl"
    monkeypatch.setenv("BASH_EVIDENCE_GUARD_LOG", str(log))
    command = "cargo test | tail -25 # evidence-ok: retained full CI artifact elsewhere"
    payload = {"tool_name": "Bash", "cwd": "/project", "tool_input": {"command": command}}
    rc, out, err = run_hook(guard.codex_hook_mode, json.dumps(payload))
    assert (rc, out, err) == (0, "", "")
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["command"] == command
    assert row["carrier"] == "codex"
    assert row["decision"] == "escape"
    assert row["rule"] is None


def test_claude_warn_wire_contract_and_log(monkeypatch, tmp_path):
    monkeypatch.setenv("BASH_EVIDENCE_GUARD_LOG", str(tmp_path / "guard.jsonl"))
    payload = {"tool_name": "Bash", "cwd": "/project", "tool_input": {
        "command": "pytest -q | tail -5"}}
    rc, out, err = run_hook(guard.hook_mode, json.dumps(payload))
    response = json.loads(out)
    assert rc == 0 and err == ""
    assert set(response) == {"systemMessage", "hookSpecificOutput"}
    assert "permissionDecision" not in out
    assert response["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "additionalContext" in response["hookSpecificOutput"]


def test_codex_warn_wire_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("BASH_EVIDENCE_GUARD_LOG", str(tmp_path / "guard.jsonl"))
    payload = {"tool_name": "Bash", "cwd": "/project", "tool_input": {
        "command": "cargo test | tail -25"}}
    rc, out, err = run_hook(guard.codex_hook_mode, json.dumps(payload))
    response = json.loads(out)
    assert rc == 0 and err == ""
    assert set(response["hookSpecificOutput"]) == {"hookEventName", "additionalContext"}
    assert "permissionDecision" not in out


def test_kiro_warn_and_deny_wire_contracts(monkeypatch, tmp_path):
    monkeypatch.setenv("BASH_EVIDENCE_GUARD_LOG", str(tmp_path / "guard.jsonl"))
    payload = {"tool_name": "execute_bash", "cwd": "/project", "tool_input": {
        "command": "cargo test | tail -25"}}
    rc, out, err = run_hook(guard.kiro_hook_mode, json.dumps(payload))
    assert rc == 1 and out == "" and "E1" in err
    rc, out, err = run_hook(guard.kiro_hook_mode, json.dumps(payload), deny=True)
    assert rc == 2 and out == "" and "E1" in err


@pytest.mark.parametrize("adapter", [guard.hook_mode, guard.codex_hook_mode, guard.kiro_hook_mode])
def test_all_adapters_ignore_malformed_stdin_quietly(adapter):
    assert run_hook(adapter, "{not json") == (0, "", "")
