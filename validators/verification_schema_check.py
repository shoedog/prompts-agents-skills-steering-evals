#!/usr/bin/env python3
"""verification-schema-check — VERIFICATION.md evidence-integrity validator
(Wave 2 of the 2026-07-25 failure-mode plan).

Extends the exp-2 Stop-gate's structural checks with evidence-integrity checks.
NOT wired into the live verify_gate.sh yet — the gate is exp-2-validated as-is;
wiring this in (warn-only first) is an owner decision. Run standalone, from CI,
or add one line to the gate when ready.

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
  verification_schema_check.py --self-test
"""
from __future__ import annotations

import argparse
import re
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
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="VERIFICATION.md evidence-integrity checks")
    ap.add_argument("paths", nargs="*", default=["."], help="VERIFICATION.md files or repo dirs")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
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
