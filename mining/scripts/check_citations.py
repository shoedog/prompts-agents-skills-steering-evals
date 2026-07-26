#!/usr/bin/env python3
"""check_citations — mechanical citation gate for mining/trial reports (S11 formalization).

Born from the 2026-07-26 S11 reader→reasoner trial evaluation: 14 sampled citations showed
ZERO fabrication but 3 spliced-fragment "quotes", 1 line drift, 1 sibling-file
transposition. This tool runs the same check mechanically so reports are gated BEFORE a
reasoner spends judgment on them — failures bounce back to the miner.

Citation convention checked (the mining-report style):
    `<path>:<line>` — "<verbatim quote>"
    `<path>:<line>` — "<quote>"
  where <path> is absolute or ~-prefixed and <quote> is ≤~25 words. Curly quotes, em
  dashes, and unicode are normalized on both sides. Lines like `shortId:line` without a
  resolvable path are reported UNRESOLVED (informational), never failed.

Grades per citation:
  VALID        quote found at the cited line (normalized substring)
  DRIFT(+/-n)  quote found in the same file within --drift lines (default 40)
  ELSEWHERE    quote found in the file but outside the drift window
  SPLICE?      quote NOT contiguous, but its first ~6 words ARE at the cited line
               (the dominant trial defect: stitched fragments presented as one quote)
  NOT-FOUND    neither the quote nor its 6-word prefix appears in the file  ← gating
  NO-FILE      cited file does not exist                                    ← gating
  UNRESOLVED   path could not be resolved (shortId style) — informational

Exit: 0 if no gating grades (NOT-FOUND / NO-FILE); 1 otherwise. --strict also gates on
SPLICE?. --self-test builds fixtures in a temp dir and asserts every grade fires.

Usage:
  check_citations.py REPORT.md [REPORT2.md ...] [--drift 40] [--strict]
  check_citations.py --self-test
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

CITE = re.compile(
    r"`(?P<path>[~/][^`\n]+?|[\w.-]+\.jsonl):(?P<line>\d+)(?:-\d+)?`"  # abs/~ path, or bare *.jsonl
    r"[^\S\n]*(?:—|-|--)[^\S\n]*"                              # separator dash
    r"[\"“](?P<quote>[^\"”\n]{8,400}?)[\"”]",                  # quoted span
)

CORPUS_ROOTS = [Path.home() / ".claude/projects", Path.home() / ".codex/sessions"]
_BASENAME_CACHE: dict[str, Path | None] = {}


def resolve_basename(name: str) -> Path | None:
    """Resolve a bare transcript filename against the known corpus roots (first match)."""
    if name in _BASENAME_CACHE:
        return _BASENAME_CACHE[name]
    found: Path | None = None
    for root in CORPUS_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob(name):
            found = p
            break
        if found:
            break
    _BASENAME_CACHE[name] = found
    return found


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    for a, b in [("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("—", "-"), ("…", "...")]:
        s = s.replace(a, b)
    # markdown emphasis/code markers are presentation, not content — transcripts keep
    # them, quotes routinely drop them (S11 trial: a bolded sentence graded SPLICE
    # against its own verbatim source)
    s = s.replace("**", "").replace("*", "").replace("__", "").replace("`", "")
    return " ".join(s.split()).lower()


def grade(path: Path, lineno: int, quote: str, drift: int) -> tuple[str, str]:
    """Return (grade, detail)."""
    if not path.is_file():
        return "NO-FILE", str(path)
    nq = norm(quote)
    prefix = norm(" ".join(quote.split()[:6]))
    at_line = None
    full_hits: list[int] = []
    prefix_hits: list[int] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            nl = norm(line)
            if nq in nl:
                full_hits.append(i)
                if len(full_hits) > 8:
                    break
            elif prefix and prefix in nl:
                prefix_hits.append(i)
            if i == lineno:
                at_line = nl
    if at_line is not None and nq in at_line:
        return "VALID", ""
    if full_hits:
        nearest = min(full_hits, key=lambda h: abs(h - lineno))
        d = nearest - lineno
        if abs(d) <= drift:
            return f"DRIFT({d:+d})", f"found at {nearest}"
        return "ELSEWHERE", f"found at {full_hits[:3]}"
    if lineno in prefix_hits or (at_line is not None and prefix and prefix in at_line):
        return "SPLICE?", "6-word prefix at cited line; full span not contiguous"
    if prefix_hits:
        return "SPLICE?", f"6-word prefix at {prefix_hits[:3]}, not at cited line"
    return "NOT-FOUND", "neither quote nor 6-word prefix in file"


def check_report(report: Path, drift: int) -> tuple[list[tuple[str, str, str]], int]:
    text = report.read_text(encoding="utf-8", errors="replace")
    rows: list[tuple[str, str, str]] = []
    unresolved = 0
    for m in CITE.finditer(text):
        raw = m.group("path")
        lineno = int(m.group("line"))
        quote = m.group("quote")
        if raw.startswith("~") or raw.startswith("/"):
            path = Path(os.path.expanduser(raw))
        else:
            resolved = resolve_basename(raw)
            if resolved is None:
                unresolved += 1
                rows.append(("NO-FILE", f"{raw}:{lineno}", "bare filename not found under corpus roots"))
                continue
            path = resolved
        g, detail = grade(path, lineno, quote, drift)
        rows.append((g, f"{raw}:{lineno}", detail if detail else quote[:50]))
    return rows, unresolved


def self_test() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as td:
        corpus = Path(td) / "corpus.jsonl"
        lines = ["padding %d\n" % i for i in range(1, 61)]
        lines[9] = "the exact verbatim sentence lives here on line ten\n"
        lines[49] = "a drifted sentence that moved to line fifty\n"
        lines[29] = "prefix words are here but the rest is absent\n"
        corpus.write_text("".join(lines))
        report = Path(td) / "report.md"
        report.write_text(
            f'- `{corpus}:10` — "the exact verbatim sentence lives here on line ten"\n'
            f'- `{corpus}:45` — "a drifted sentence that moved to line fifty"\n'
            f'- `{corpus}:30` — "prefix words are here but the tail was stitched from elsewhere"\n'
            f'- `{corpus}:5` — "this sentence appears nowhere in the corpus file at all"\n'
            f'- `{td}/missing.jsonl:3` — "quote against a file that does not even exist"\n'
        )
        rows, _ = check_report(report, drift=40)
        got = [g for g, _, _ in rows]
        expect_prefixes = ["VALID", "DRIFT(", "SPLICE?", "NOT-FOUND", "NO-FILE"]
        for e, g in zip(expect_prefixes, got):
            match = g.startswith(e)
            print(f"  {e:<10} -> {g}: {'ok' if match else 'FAIL'}")
            ok &= match
        ok &= len(got) == 5
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="mechanical citation gate for mining reports")
    ap.add_argument("reports", nargs="*")
    ap.add_argument("--drift", type=int, default=40)
    ap.add_argument("--strict", action="store_true", help="also gate on SPLICE?")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.reports:
        print("no reports given (see --help)", file=sys.stderr)
        return 2
    gate = 0
    for r in args.reports:
        rows, unresolved = check_report(Path(r).expanduser(), args.drift)
        counts: dict[str, int] = {}
        print(f"{r}: {len(rows)} resolvable citation(s), {unresolved} unresolved")
        for g, where, detail in rows:
            key = g.split("(")[0]
            counts[key] = counts.get(key, 0) + 1
            if g != "VALID":
                print(f"  [{g}] {where}  {detail}")
            if g in ("NOT-FOUND", "NO-FILE") or (args.strict and g.startswith("SPLICE")):
                gate = 1
        print("  summary:", ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())) or "none")
    return gate


if __name__ == "__main__":
    sys.exit(main())
