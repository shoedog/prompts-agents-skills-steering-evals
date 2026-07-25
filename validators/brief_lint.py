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
  brief_lint.py --hook          PreToolUse hook mode: reads the hook JSON on stdin,
                                lints Task/Agent tool_input prompt text, ALWAYS
                                exits 0 (warn-only feedback via permissionDecision
                                "allow" + reason). Never blocks a spawn.
  brief_lint.py --self-test     embedded fixtures; exits nonzero on any mismatch.
"""
from __future__ import annotations

import argparse
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
    print("self-test:", "PASS" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="dispatch-brief linter")
    ap.add_argument("file", nargs="?", help="brief file to lint")
    ap.add_argument("--role", choices=("review", "implement"), default="review")
    ap.add_argument("--strict", action="store_true", help="exit 1 on VIOLATIONs")
    ap.add_argument("--hook", action="store_true", help="PreToolUse hook mode (stdin JSON, always exit 0)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.hook:
        return hook_mode()
    if not args.file:
        ap.error("FILE required unless --hook/--self-test")
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
