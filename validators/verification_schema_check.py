#!/usr/bin/env python3
"""verification-schema-check — VERIFICATION.md evidence-integrity validator
(Wave 2 of the 2026-07-25 failure-mode plan).

Extends the exp-2 Stop-gate's structural checks with evidence-integrity checks.
NOT wired into the live verify_gate.sh yet — the gate is exp-2-validated as-is;
wiring this in (warn-only first) is an owner decision. Run standalone, from CI,
add one line to the gate when ready, or mount warn-only as a Claude Code Stop
hook via --hook (prepared patch: ~/Documents/PHASE5-STOPHOOK-PREP-2026-07-25.md).

Checks (evidence: the `| tail -8` incident — pass/fail claimed off evidence the
pipe destroyed; the controller fix-claim with no post-edit rerun):
  S1 structure      "## Verified" and "## Not verified" sections exist (gate parity).
  S2 linked totals  every test-total claim ("N passed", "N/N", "0 failed") has a
                    capture reference (a *.log/*.txt/*.json/*.out path or the words
                    "exit code") within the same paragraph -> VIOLATION otherwise.
  S3 provenance     the doc distinguishes re-ran-this-turn from supplied evidence
                    (any of "re-ran", "reran", "this turn", "supplied") -> WARN if absent.
  S4 tier marker    if the doc claims an APPROVE/verdict without test evidence,
                    it must say STATIC-ONLY -> WARN otherwise.

Usage:
  verification_schema_check.py [PATH ...]   (file or repo dir; default: ./VERIFICATION.md)
  verification_schema_check.py --strict     exit 1 on VIOLATIONs
  verification_schema_check.py --hook       Claude Stop hook mode: reads the hook JSON on
                                            stdin, checks VERIFICATION.md files that exist
                                            under the payload cwd (bounded: git-tracked at
                                            any depth + depth-<=2 glob skipping dot dirs,
                                            capped at HOOK_MAX_FILES), prints findings to
                                            stderr, ALWAYS exits 0 (warn-only — never
                                            blocks the stop). Quiet when clean; a missing
                                            VERIFICATION.md is NOT flagged (no S0).
  verification_schema_check.py --codex-hook Codex Stop hook mode. Codex Stop stdout MUST
                                            be JSON-or-empty on exit 0 (plain text is
                                            invalid wire format), so findings go out as
                                            {"systemMessage": ...} — a UI warning that
                                            never blocks the stop. Never emits "decision";
                                            always exits 0. Same bounded discovery as
                                            --hook. NOT wired anywhere by default (parity
                                            with the Claude side: mounting is an owner
                                            decision).
  verification_schema_check.py --kiro-hook  Kiro stop hook mode. Kiro's wire contract is
                                            exit-code based for warnings (non-0/non-2 exit
                                            shows stderr as a warning and still allows the
                                            stop; stdout JSON {"decision":"block"} would
                                            block). Warn-only therefore = findings on
                                            stderr + exit 1; clean = quiet exit 0. Never
                                            emits {"decision": ...}; never exits 2.
  verification_schema_check.py --self-test  embedded fixtures incl. synthetic Claude,
                                            Codex, and Kiro stop payloads; exits nonzero
                                            on any mismatch.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TOTAL = re.compile(r"(?i)\b\d+\s*(?:/\s*\d+\s*)?(?:tests? )?pass(?:ed)?\b|\b0 fail(?:ed|ures)\b")
CAPTURE = re.compile(r"(?i)[\w./-]+\.(?:log|txt|json|jsonl|out)\b|exit code|exit status|--locked")
PROVENANCE = re.compile(r"(?i)\bre-?ran\b|\bthis turn\b|\bsupplied\b")
VERDICTISH = re.compile(r"(?i)\bAPPROVE\b|\bverdict\b")
TESTISH = re.compile(r"(?i)\btests?\b|\bsuite\b|pass(?:ed)?")
STATIC = re.compile(r"STATIC-ONLY")


def check_text(text: str):
    findings = []
    if "## Verified" not in text or "## Not verified" not in text:
        findings.append(("VIOLATION", "S1 structure", "missing '## Verified' and/or '## Not verified' section"))
    for para in re.split(r"\n\s*\n", text):
        m = TOTAL.search(para)
        if m and not CAPTURE.search(para):
            findings.append(("VIOLATION", "S2 linked-totals",
                             f"test-total claim ({m.group(0)!r}) with no capture file / exit-code reference in its paragraph"))
    if not PROVENANCE.search(text):
        findings.append(("WARN", "S3 provenance", "no re-ran-this-turn vs supplied distinction anywhere in the doc"))
    if VERDICTISH.search(text) and not TESTISH.search(text) and not STATIC.search(text):
        findings.append(("WARN", "S4 tier-marker", "verdict claimed without test evidence and without STATIC-ONLY marker"))
    return findings


def check_path(p: Path):
    f = p / "VERIFICATION.md" if p.is_dir() else p
    if not f.is_file():
        return f, [("VIOLATION", "S0 missing", "VERIFICATION.md not found")]
    return f, check_text(f.read_text(encoding="utf-8", errors="replace"))


def render(findings, source: str) -> str:
    lines = [f"verification-schema-check: {len(findings)} finding(s) in {source}"]
    for sev, rule, detail in findings:
        lines.append(f"  [{sev}] {rule}: {detail}")
    return "\n".join(lines)


HOOK_MAX_FILES = 20  # hard cap on files checked per stop


def find_verification_files(root: Path) -> list[Path]:
    """Bounded discovery for --hook: git-tracked VERIFICATION.md at any depth
    (index read only — no tree walk; git pathspec '*' crosses '/') UNIONED with a
    depth-<=2 glob skipping dot dirs. The glob leg matters: both target repos keep
    /VERIFICATION.md in .git/info/exclude, so ls-files --others --exclude-standard
    would miss the very file this hook exists to check; it also covers non-git
    dirs. Never an unbounded scan; capped at HOOK_MAX_FILES."""
    hits: set[Path] = set()
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--",
             "VERIFICATION.md", "*/VERIFICATION.md"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            hits.update(root / rel for rel in r.stdout.split("\0") if rel)
    except Exception:
        pass  # no git / not a repo — the shallow glob below still applies
    for pat in ("VERIFICATION.md", "*/VERIFICATION.md", "*/*/VERIFICATION.md"):
        for p in root.glob(pat):
            if not any(part.startswith(".") for part in p.relative_to(root).parts):
                hits.add(p)
    return sorted(p for p in hits if p.is_file())[:HOOK_MAX_FILES]


def _hook_reports(stdin) -> list[str]:
    """Shared payload-cwd discovery for the hook modes. Returns rendered
    findings per flagged file; [] on clean, malformed input, or any error."""
    try:
        payload = json.load(stdin)
    except Exception:
        return []  # never block on malformed input
    reports: list[str] = []
    try:
        cwd = payload.get("cwd") or ""
        root = Path(cwd)
        if not cwd or not root.is_dir():
            return []
        for f in find_verification_files(root):
            findings = check_text(f.read_text(encoding="utf-8", errors="replace"))
            if findings:
                reports.append(render(findings, str(f.relative_to(root))))
    except Exception:
        return []  # warn-only: an internal error must never block the stop
    return reports


def hook_mode() -> int:
    for report in _hook_reports(sys.stdin):
        print(report, file=sys.stderr)
    return 0


def codex_hook_mode() -> int:
    """Codex Stop: warn via {"systemMessage": ...} JSON on stdout (the only
    valid non-empty stdout shape); never "decision"; always exit 0."""
    reports = _hook_reports(sys.stdin)
    if reports:
        msg = ("verification-schema-check (warn-only): " + " | ".join(reports))[:4000]
        print(json.dumps({"systemMessage": msg}))
    return 0


def kiro_hook_mode() -> int:
    """Kiro stop: warn via stderr + exit 1 (never 2; never a decision JSON)."""
    reports = _hook_reports(sys.stdin)
    if not reports:
        return 0
    for report in reports:
        print(report, file=sys.stderr)
    print("(warn-only verification-schema-check: the stop proceeds regardless.)", file=sys.stderr)
    return 1


GOOD = """# Verification
## Verified
Full suite re-ran this turn: 1314 passed, 0 failed (capture: target/test-run.log, exit code 0).
## Not verified
Live-stack soak — supplied from the prior session, not re-ran.
"""
BAD = """# Verification
All good: 200 passed.
Verdict: APPROVE.
"""
BAD_STATIC = """# Verification
Reviewed the diff line by line; no defects identified. Verdict: APPROVE.
"""


STOP_PAYLOAD = {"hook_event_name": "Stop", "session_id": "self-test", "stop_hook_active": False}
# Codex Stop payload (per codex hooks docs: common fields + stop_hook_active
# + last_assistant_message; transcript_path is explicitly not a stable interface).
CODEX_STOP_PAYLOAD = {"hook_event_name": "Stop", "session_id": "self-test",
                      "transcript_path": None, "model": "gpt-5.5", "turn_id": "t1",
                      "stop_hook_active": False,
                      "last_assistant_message": "Done. All checks pass."}
# Kiro stop payload (per kiro cli hooks docs).
KIRO_STOP_PAYLOAD = {"hook_event_name": "stop", "session_id": "self-test",
                     "assistant_response": "Done. All checks pass."}


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


def self_test() -> int:
    ok = True
    g = check_text(GOOD)
    print(f"  good fixture -> {len(g)} findings (expected 0): {'ok' if not g else 'FAIL ' + str(g)}")
    ok &= not g
    b = {rule for _, rule, _ in check_text(BAD)}
    expect = {"S1 structure", "S2 linked-totals", "S3 provenance"}
    print(f"  bad fixture  -> {sorted(b)} (expected {sorted(expect)}): {'ok' if b == expect else 'FAIL'}")
    ok &= b == expect
    s = {rule for _, rule, _ in check_text(BAD_STATIC)}
    expect_s = {"S1 structure", "S3 provenance", "S4 tier-marker"}
    print(f"  static-verdict fixture -> {sorted(s)} (expected {sorted(expect_s)}): {'ok' if s == expect_s else 'FAIL'}")
    ok &= s == expect_s
    with tempfile.TemporaryDirectory() as td:
        _, res = check_path(Path(td))
        print(f"  missing file -> {res[0][1]}: {'ok' if res[0][1] == 'S0 missing' else 'FAIL'}")
        ok &= res[0][1] == "S0 missing"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(GOOD, encoding="utf-8")
        rc, out, err = _run_hook(hook_mode, json.dumps({**STOP_PAYLOAD, "cwd": td}))
        h = rc == 0 and err == "" and out == ""
        print(f"  hook clean payload -> rc={rc}, {len(err)} stderr bytes (expected rc=0, quiet): "
              f"{'ok' if h else 'FAIL ' + repr(err)}")
        ok &= h
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(BAD, encoding="utf-8")
        (Path(td) / "svc").mkdir()
        (Path(td) / "svc" / "VERIFICATION.md").write_text(BAD_STATIC, encoding="utf-8")
        rc, out, err = _run_hook(hook_mode, json.dumps({**STOP_PAYLOAD, "cwd": td}))
        h = (rc == 0 and out == "" and "S2 linked-totals" in err and "S4 tier-marker" in err
             and err.count("finding(s)") == 2)
        print(f"  hook dirty payload -> rc={rc}, 2 files flagged on stderr: "
              f"{'ok' if h else 'FAIL ' + repr(err)}")
        ok &= h
    with tempfile.TemporaryDirectory() as td:
        rc, out, err = _run_hook(hook_mode, json.dumps({**STOP_PAYLOAD, "cwd": td}))
        h = rc == 0 and err == "" and out == ""
        print(f"  hook empty dir -> rc={rc}, quiet (no S0 in hook mode): {'ok' if h else 'FAIL ' + repr(err)}")
        ok &= h
    rc, out, err = _run_hook(hook_mode, "{not json")
    h = rc == 0 and err == "" and out == ""
    print(f"  hook malformed payload -> rc={rc}, quiet: {'ok' if h else 'FAIL'}")
    ok &= h

    # Codex Stop mode: stdout must be JSON-or-empty; only "systemMessage"; never "decision".
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(BAD, encoding="utf-8")
        rc, out, err = _run_hook(codex_hook_mode, json.dumps({**CODEX_STOP_PAYLOAD, "cwd": td}))
        try:
            j = json.loads(out)
        except Exception:
            j = None
        h = (rc == 0 and err == "" and isinstance(j, dict) and set(j) == {"systemMessage"}
             and "S2 linked-totals" in j["systemMessage"] and "decision" not in out)
        print(f"  codex hook dirty -> rc={rc}, stdout is systemMessage-only JSON, no decision: "
              f"{'ok' if h else 'FAIL ' + repr(out)}")
        ok &= h
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(GOOD, encoding="utf-8")
        rc, out, err = _run_hook(codex_hook_mode, json.dumps({**CODEX_STOP_PAYLOAD, "cwd": td}))
        h = rc == 0 and out == "" and err == ""
        print(f"  codex hook clean -> rc={rc}, EMPTY stdout (valid codex Stop wire): "
              f"{'ok' if h else 'FAIL ' + repr(out)}")
        ok &= h
    rc, out, err = _run_hook(codex_hook_mode, "{not json")
    h = rc == 0 and out == "" and err == ""
    print(f"  codex hook malformed -> rc={rc}, quiet: {'ok' if h else 'FAIL'}")
    ok &= h

    # Kiro stop mode: warn = stderr + exit 1 (never 2); stdout always empty.
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(BAD, encoding="utf-8")
        rc, out, err = _run_hook(kiro_hook_mode, json.dumps({**KIRO_STOP_PAYLOAD, "cwd": td}))
        h = rc == 1 and rc != 2 and out == "" and "S2 linked-totals" in err
        print(f"  kiro hook dirty -> rc={rc} (not 2), findings on stderr, stdout empty: "
              f"{'ok' if h else 'FAIL ' + repr((rc, out, err))}")
        ok &= h
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "VERIFICATION.md").write_text(GOOD, encoding="utf-8")
        rc, out, err = _run_hook(kiro_hook_mode, json.dumps({**KIRO_STOP_PAYLOAD, "cwd": td}))
        h = rc == 0 and out == "" and err == ""
        print(f"  kiro hook clean -> rc={rc}, quiet: {'ok' if h else 'FAIL ' + repr(err)}")
        ok &= h
    rc, out, err = _run_hook(kiro_hook_mode, "{not json")
    h = rc == 0 and out == "" and err == ""
    print(f"  kiro hook malformed -> rc={rc}, quiet: {'ok' if h else 'FAIL'}")
    ok &= h

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="VERIFICATION.md evidence-integrity checks")
    ap.add_argument("paths", nargs="*", default=["."], help="VERIFICATION.md files or repo dirs")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--hook", action="store_true",
                    help="Claude Stop hook mode (stdin JSON, findings->stderr, always exit 0)")
    ap.add_argument("--codex-hook", action="store_true",
                    help="Codex Stop hook mode (findings->systemMessage JSON on stdout, always exit 0)")
    ap.add_argument("--kiro-hook", action="store_true",
                    help="Kiro stop hook mode (findings->stderr+exit 1, never 2, never blocks)")
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
    worst = 0
    for raw in (args.paths or ["."]):
        f, findings = check_path(Path(raw))
        print(f"{f}: {len(findings)} finding(s)")
        for sev, rule, detail in findings:
            print(f"  [{sev}] {rule}: {detail}")
            if sev == "VIOLATION":
                worst = 1
    return worst if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
