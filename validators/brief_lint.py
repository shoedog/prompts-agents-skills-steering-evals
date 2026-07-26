#!/usr/bin/env python3
"""brief-lint — dispatch-brief validator (Wave 2 of the 2026-07-25 failure-mode plan).

Lints ad-hoc dispatch briefs against the contract in
a2a-bridge/prompts/dispatch-brief-contract.md. Provider-blind: the same rules
apply to briefs handed to claude, codex, or kiro workers.

Rules (each traces to an evidenced incident in
~/Documents/agent-failure-modes-2026-07-25.md):
  R1 premise-without-license   VIOLATION  a conclusion/claimed-result is embedded
                               with no falsification license ("pressure-test",
                               "independently verify", "may be wrong", "argue the
                               opposite", "search elsewhere"). [D1-D6 panel; "all
                               addressed" premises; claimed test totals]
  R2 option-menu               WARN       an option menu with no marker that the
                               options are user/operator-specified and no open-brief
                               language. [D1-D6 offered a factually impossible option]
  R3 line-number-anchors       WARN (implement role only, --role implement)
                               `file.ext:NNN` edit anchors drift as prior tasks land.
                               [59 apply_patch failures Jul 6-7] For review briefs,
                               file:line EVIDENCE citations are good — not flagged.
  R4 given-facts-no-probe      VIOLATION  "treat as given / given data / observed
                               facts" with no probe/command/output/capture reference
                               nearby. [axiom injection: two "given" facts were never
                               established]

Modes:
  brief_lint.py FILE [--role review|implement] [--strict]
  brief_lint.py --hook          Claude Code PreToolUse hook mode: reads the hook
                                JSON on stdin, lints Task/Agent tool_input prompt
                                text, ALWAYS exits 0 (warn-only feedback via
                                permissionDecision "allow" + reason). Never blocks.
  brief_lint.py --codex-hook    Codex CLI PreToolUse hook mode (spawn_agent /
                                "Agent"): warn-only via hookSpecificOutput
                                additionalContext + top-level systemMessage.
                                NEVER emits permissionDecision (cannot deny);
                                always exits 0. Codex ignores plain stdout for
                                PreToolUse; only the JSON contract is parsed.
  brief_lint.py --kiro-hook     Kiro CLI preToolUse hook mode (delegate tool):
                                Kiro's preToolUse wire contract is exit-code
                                based (0 allow; 2 block + stderr to the LLM; any
                                OTHER nonzero shows stderr as a warning and still
                                allows the tool). Warn-only therefore = findings
                                on stderr + exit 1. This mode never exits 2.
  brief_lint.py --self-test     embedded fixtures incl. synthetic Claude, Codex,
                                and Kiro hook payloads; exits nonzero on mismatch.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path

PREMISE = re.compile(
    r"(?i)\bthe (?:bug|defect|root cause|fix|problem|cause) is\b"
    r"|\ball (?:findings? |items? )?(?:are |were )?addressed\b"
    r"|\bis (?:now )?fixed\b"
    r"|\b\d+ passed\b[^\n]{0,40}\b0 fail(?:ed|ures)\b"
    r"|\btreat\b[^\n]{0,60}\bas given\b"
    r"|\bgiven data\b"
    r"|\bproposed (?:action|fix|remedy)\b"
)
LICENSE = re.compile(
    r"(?i)pressure-?test|argue the opposite|may be wrong|independently verify"
    r"|verify against the live|do not trust|refute|falsif"
    r"|(?:also )?search (?:for (?:problems|regressions?) )?elsewhere|prove (?:me|it) wrong"
)
OPTION_MENU = re.compile(
    r"(?i)\boption [A-D]\b|\bchoose (?:one|between|exactly)\b|\bexactly one of the following\b"
    r"|\bpick (?:one|an option)\b|\brecommend(?:ation)? for each of D\d\b"
)
MENU_OK = re.compile(r"(?i)user-specified options|operator-specified|open brief|OPEN brief|re-cut the problem")
LINE_ANCHOR = re.compile(r"\b[\w./-]+\.(?:rs|ts|tsx|py|go|js|mjs|c|cc|cpp|h|java|sql|toml)\:\d+\b")
GIVEN = re.compile(r"(?i)\btreat\b[^\n]{0,60}\bas given\b|\bgiven data\b|\bobserved facts\b[^\n]{0,40}\bas (?:given|established)\b")
# an actual artifact reference, not the mere WORD "probe" (the axiom-injection
# incident said "you cannot re-run those probes" — that is not a probe link):
PROBE_REF = re.compile(r"(?i)[\w./-]+\.(?:md|txt|log|json|jsonl|out|csv)\b|\$ |```|exit code|captured? (?:at|in|to)\b")


def lint(text: str, role: str = "review") -> list[tuple[str, str, str]]:
    """Return findings as (severity, rule, detail). severity in {VIOLATION, WARN}."""
    out: list[tuple[str, str, str]] = []
    m = PREMISE.search(text)
    if m and not LICENSE.search(text):
        out.append(("VIOLATION", "R1 premise-without-license",
                    f"embedded premise/claim ({m.group(0)!r}) with no falsification license — "
                    "add: 'The conclusion above is mine and may be wrong; argue the opposite case "
                    "first; independently verify; also search elsewhere.'"))
    m = OPTION_MENU.search(text)
    if m and not MENU_OK.search(text):
        out.append(("WARN", "R2 option-menu",
                    f"option menu ({m.group(0)!r}) without a user-specified-options marker or "
                    "open-brief language — default to an open brief unless the operator chose the options."))
    if role == "implement":
        anchors = LINE_ANCHOR.findall(text)
        if anchors:
            out.append(("WARN", "R3 line-number-anchors",
                        f"{len(anchors)} line-number edit anchors (e.g. {anchors[0]!r}) — anchor by "
                        "symbol/function + context snippet; line numbers drift as prior tasks land."))
    for m in GIVEN.finditer(text):
        lo, hi = max(0, m.start() - 200), min(len(text), m.end() + 200)
        if not PROBE_REF.search(text[lo:hi]):
            out.append(("VIOLATION", "R4 given-facts-no-probe",
                        f"facts declared given ({m.group(0)!r}) with no probe/command/output reference "
                        "nearby — link the probe that established them or label them assumptions."))
    return out


def render(findings, source: str) -> str:
    lines = [f"brief-lint: {len(findings)} finding(s) in {source}"]
    for sev, rule, detail in findings:
        lines.append(f"  [{sev}] {rule}: {detail}")
    return "\n".join(lines)


def hook_mode() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never block on malformed input
    if payload.get("tool_name") not in ("Task", "Agent"):
        return 0
    ti = payload.get("tool_input") or {}
    text = " ".join(str(ti.get(k, "")) for k in ("description", "prompt"))
    if not text.strip():
        return 0
    findings = lint(text, role="review")
    if findings:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": render(findings, "subagent prompt"),
        }}))
    return 0


# --- codex / kiro adapters -------------------------------------------------
# Agent-dispatch tool names across providers (payload tool_name, lowercased).
# The hooks.json / agent-config matcher already restricts which tools reach the
# hook; this set is defense-in-depth against matcher drift.
AGENTISH = {"task", "agent", "spawn_agent", "delegate", "subagent", "subagents"}


def _collect_strings(node, depth: int = 0) -> list[str]:
    """Bounded recursive harvest of string values (for undocumented shapes)."""
    if depth > 4:
        return []
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _collect_strings(v, depth + 1)]
    if isinstance(node, list):
        return [s for v in node for s in _collect_strings(v, depth + 1)]
    return []


def _agent_prompt_text(payload) -> str:
    """Prompt-bearing text from an agent-dispatch tool_input, provider-blind.

    claude Task/Agent: description+prompt. codex spawn_agent (v1/v2, verified
    against codex-rs multi_agents_spec.rs): message (+ items for v1 structured
    input). kiro delegate: shape undocumented -> harvest all strings.
    """
    if str(payload.get("tool_name", "")).lower() not in AGENTISH:
        return ""
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return ""
    parts = [str(ti[k]) for k in ("description", "prompt", "message", "task", "instructions")
             if isinstance(ti.get(k), str) and ti[k]]
    parts += _collect_strings(ti.get("items"))
    if not parts:  # unknown shape (e.g. kiro delegate): harvest everything
        parts = _collect_strings(ti)
    return " ".join(parts)


def codex_hook_mode() -> int:
    """Codex PreToolUse hook: warn-only. Never emits permissionDecision — this
    adapter cannot deny. Always exits 0. Empty stdout when clean."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never interfere on malformed input
    text = _agent_prompt_text(payload)
    if not text.strip():
        return 0
    findings = lint(text, role="review")
    if findings:
        body = render(findings, "subagent dispatch (codex spawn_agent)")[:4000]
        print(json.dumps({
            "systemMessage": f"brief-lint (warn-only): {len(findings)} finding(s) in the dispatch brief",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": body + "\n(warn-only brief-lint: the spawn proceeds "
                                            "regardless; fix the brief if the findings hold.)",
            },
        }))
    return 0


def kiro_hook_mode() -> int:
    """Kiro preToolUse hook: warn-only. Findings -> stderr + exit 1 (Kiro shows
    stderr as a warning for non-0/non-2 exits and still runs the tool). Clean,
    non-matching, or malformed input -> quiet exit 0. NEVER exits 2 (2 blocks)."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = _agent_prompt_text(payload)
    if not text.strip():
        return 0
    findings = lint(text, role="review")
    if not findings:
        return 0
    print(render(findings, "subagent dispatch (kiro delegate)")
          + "\n(warn-only brief-lint: dispatch proceeds regardless.)", file=sys.stderr)
    return 1


GOOD_OPEN_BRIEF = """This is deliberately an OPEN brief. You are given evidence, not a question with
options. If the investigation has mis-cut the problem, re-cut it. Proposed action (mine): a
mill-aware tolerance floor. Pressure-test this hard and independently verify against the live
checkout; also search elsewhere for regressions."""
BAD_ANCHORED_PANEL = """For each of D1-D6 deliver a clear recommendation. Choose exactly one of the
following options per decision. The root cause is the resolver gate; work within it."""
BAD_GIVEN_DATA = """The ADR's evidence table is first-hand observation. You cannot re-run those probes,
so treat the observed facts as given data. Review the reasoning built on them."""
BAD_IMPL_ANCHORS = """Modify crates/bridge-a2a-inbound/src/server.rs:3049 and bin/a2a-bridge/src/main.rs:6210.
The fix is to add the retry config. All findings are addressed in the plan; just implement task 3."""


def _run_hook(fn, stdin_text: str) -> tuple[int, str, str]:
    """Run a hook mode against a synthetic stdin payload; capture stdout+stderr."""
    old_stdin = sys.stdin
    out, err = io.StringIO(), io.StringIO()
    try:
        sys.stdin = io.StringIO(stdin_text)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn()
    finally:
        sys.stdin = old_stdin
    return rc, out.getvalue(), err.getvalue()


# Synthetic hook payloads (shapes per each platform's documented contract).
CLAUDE_PAYLOAD = {"hook_event_name": "PreToolUse", "session_id": "self-test",
                  "tool_name": "Task",
                  "tool_input": {"description": "review panel", "prompt": BAD_GIVEN_DATA}}
CODEX_PAYLOAD_V2 = {"hook_event_name": "PreToolUse", "session_id": "self-test",
                    "cwd": "/tmp", "model": "gpt-5.5", "tool_name": "spawn_agent",
                    "tool_use_id": "tu_1",
                    "tool_input": {"task_name": "review_panel", "message": BAD_ANCHORED_PANEL}}
CODEX_PAYLOAD_V1_ITEMS = {"hook_event_name": "PreToolUse", "session_id": "self-test",
                          "cwd": "/tmp", "tool_name": "spawn_agent", "tool_use_id": "tu_2",
                          "tool_input": {"items": [{"type": "text", "text": BAD_GIVEN_DATA}],
                                         "fork_context": False}}
CODEX_PAYLOAD_CLEAN = {"hook_event_name": "PreToolUse", "session_id": "self-test",
                       "cwd": "/tmp", "tool_name": "spawn_agent", "tool_use_id": "tu_3",
                       "tool_input": {"task_name": "open_brief", "message": GOOD_OPEN_BRIEF}}
CODEX_PAYLOAD_OTHER_TOOL = {"hook_event_name": "PreToolUse", "session_id": "self-test",
                            "cwd": "/tmp", "tool_name": "Bash", "tool_use_id": "tu_4",
                            "tool_input": {"command": "echo the root cause is the resolver gate"}}
KIRO_PAYLOAD = {"hook_event_name": "preToolUse", "cwd": "/tmp", "session_id": "self-test",
                "tool_name": "delegate",
                "tool_input": {"task": BAD_GIVEN_DATA, "agents": ["worker"]}}
KIRO_PAYLOAD_CLEAN = {"hook_event_name": "preToolUse", "cwd": "/tmp", "session_id": "self-test",
                      "tool_name": "delegate", "tool_input": {"task": GOOD_OPEN_BRIEF}}


def self_test() -> int:
    cases = [
        ("good open brief", GOOD_OPEN_BRIEF, "review", set()),
        ("anchored panel", BAD_ANCHORED_PANEL, "review", {"R1 premise-without-license", "R2 option-menu"}),
        ("given data", BAD_GIVEN_DATA, "review",
         {"R1 premise-without-license", "R4 given-facts-no-probe"}),
        ("impl anchors", BAD_IMPL_ANCHORS, "implement", {"R1 premise-without-license", "R3 line-number-anchors"}),
    ]
    failures = 0
    for name, text, role, expect in cases:
        got = {rule for _, rule, _ in lint(text, role)}
        status = "ok" if got == expect else "FAIL"
        if got != expect:
            failures += 1
        print(f"  {status}: {name} -> {sorted(got)} (expected {sorted(expect)})")

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        if not cond:
            failures += 1
        print(f"  {'ok' if cond else 'FAIL'}: {name}{(' — ' + detail) if (detail and not cond) else ''}")

    # Claude hook mode (synthetic Claude PreToolUse payload).
    rc, out, err = _run_hook(hook_mode, json.dumps(CLAUDE_PAYLOAD))
    j = json.loads(out) if out.strip() else {}
    check("claude hook dirty -> rc0, allow+reason with R1/R4",
          rc == 0 and err == ""
          and j.get("hookSpecificOutput", {}).get("permissionDecision") == "allow"
          and "R1" in j.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
          and "R4" in j["hookSpecificOutput"]["permissionDecisionReason"],
          f"rc={rc} out={out!r}")

    # Codex hook mode: dirty v2 payload -> JSON warn, no permissionDecision ever.
    rc, out, err = _run_hook(codex_hook_mode, json.dumps(CODEX_PAYLOAD_V2))
    j = json.loads(out) if out.strip() else {}
    hso = j.get("hookSpecificOutput", {})
    check("codex hook dirty(v2) -> rc0, valid JSON, additionalContext R1+R2",
          rc == 0 and err == "" and set(j) == {"systemMessage", "hookSpecificOutput"}
          and set(hso) == {"hookEventName", "additionalContext"}
          and hso.get("hookEventName") == "PreToolUse"
          and "R1" in hso.get("additionalContext", "") and "R2" in hso["additionalContext"],
          f"rc={rc} out={out!r}")
    check("codex hook never denies (no permissionDecision/deny in output)",
          "permissionDecision" not in out and '"deny"' not in out, out[:200])
    rc, out, err = _run_hook(codex_hook_mode, json.dumps(CODEX_PAYLOAD_V1_ITEMS))
    check("codex hook dirty(v1 items) -> R4 found in items text",
          rc == 0 and "R4" in out, f"rc={rc} out={out!r}")
    rc, out, err = _run_hook(codex_hook_mode, json.dumps(CODEX_PAYLOAD_CLEAN))
    check("codex hook clean -> rc0, EMPTY stdout", rc == 0 and out == "" and err == "",
          f"rc={rc} out={out!r}")
    rc, out, err = _run_hook(codex_hook_mode, json.dumps(CODEX_PAYLOAD_OTHER_TOOL))
    check("codex hook non-agent tool -> rc0, quiet", rc == 0 and out == "" and err == "",
          f"rc={rc} out={out!r}")
    rc, out, err = _run_hook(codex_hook_mode, "{not json")
    check("codex hook malformed -> rc0, quiet", rc == 0 and out == "" and err == "")

    # Kiro hook mode: warn channel is stderr + exit 1; never 2; stdout stays empty.
    rc, out, err = _run_hook(kiro_hook_mode, json.dumps(KIRO_PAYLOAD))
    check("kiro hook dirty -> rc1 (not 2), findings on stderr, stdout empty",
          rc == 1 and rc != 2 and out == "" and "R4" in err and "R1" in err,
          f"rc={rc} err={err!r}")
    rc, out, err = _run_hook(kiro_hook_mode, json.dumps(KIRO_PAYLOAD_CLEAN))
    check("kiro hook clean -> rc0, quiet", rc == 0 and out == "" and err == "",
          f"rc={rc} err={err!r}")
    rc, out, err = _run_hook(kiro_hook_mode, "{not json")
    check("kiro hook malformed -> rc0, quiet", rc == 0 and out == "" and err == "")

    print("self-test:", "PASS" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="dispatch-brief linter")
    ap.add_argument("file", nargs="?", help="brief file to lint")
    ap.add_argument("--role", choices=("review", "implement"), default="review")
    ap.add_argument("--strict", action="store_true", help="exit 1 on VIOLATIONs")
    ap.add_argument("--hook", action="store_true",
                    help="Claude Code PreToolUse hook mode (stdin JSON, always exit 0)")
    ap.add_argument("--codex-hook", action="store_true",
                    help="Codex CLI PreToolUse hook mode (warn-only additionalContext, always exit 0)")
    ap.add_argument("--kiro-hook", action="store_true",
                    help="Kiro CLI preToolUse hook mode (warn-only: findings->stderr+exit 1, never 2)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.hook:
        return hook_mode()
    if args.codex_hook:
        return codex_hook_mode()
    if args.kiro_hook:
        return kiro_hook_mode()
    if not args.file:
        ap.error("FILE required unless --hook/--codex-hook/--kiro-hook/--self-test")
    findings = lint(Path(args.file).read_text(encoding="utf-8", errors="replace"), args.role)
    if findings:
        print(render(findings, args.file))
        if args.strict and any(s == "VIOLATION" for s, _, _ in findings):
            return 1
    else:
        print(f"brief-lint: clean ({args.file})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
