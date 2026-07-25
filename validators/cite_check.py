#!/usr/bin/env python3
"""cite-check — file:line citation resolver (Wave 2 of the 2026-07-25 failure-mode plan).

Makes the cite-or-label rule enforceable: every `path/to/file.ext:NNN` citation in a
spec/brief/evidence doc must resolve against the checkout — file exists, line number
within range. Optionally verifies a nearby backtick-quoted snippet appears within
±5 lines of the cited line (whitespace-collapsed substring match).

Evidence basis: every mode-1 incident in the forensics was corrected by a <1-minute
read of the cited lines that happened AFTER the claim; stale/fabricated citations
are deterministic to catch. (~/Documents/agent-failure-modes-2026-07-25.md, B1.)

Usage:
  cite_check.py DOC [--repo ROOT] [--strict] [--quotes]
  cite_check.py --self-test

Exit: 0 clean or warn-only; 1 with --strict when any citation fails (or --self-test fails).
Notes: citations inside fenced code blocks are still checked (specs quote code with
citations); paths are resolved relative to --repo, then to the doc's own directory.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

CITE = re.compile(
    r"(?P<path>[A-Za-z0-9_][\w./-]*\.(?:rs|ts|tsx|js|mjs|py|go|c|cc|cpp|h|hpp|java|sql|toml|json|ya?ml|sh|md|proto))"
    r":(?P<line>\d{1,6})(?:-(?P<end>\d{1,6}))?"
)
QUOTE_NEAR = re.compile(r"`([^`\n]{4,120})`")


def check_doc(doc_path: Path, repo: Path, check_quotes: bool = False):
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    results = []  # (ok: bool, citation, detail)
    line_cache: dict[Path, list[str]] = {}

    def resolve(rel: str) -> Path | None:
        for base in (repo, doc_path.parent):
            p = (base / rel).resolve()
            if p.is_file():
                return p
        return None

    for m in CITE.finditer(text):
        rel, ln = m.group("path"), int(m.group("line"))
        end = int(m.group("end")) if m.group("end") else ln
        cite = f"{rel}:{m.group('line')}" + (f"-{m.group('end')}" if m.group("end") else "")
        p = resolve(rel)
        if p is None:
            results.append((False, cite, "file not found under repo or doc dir"))
            continue
        if p not in line_cache:
            line_cache[p] = p.read_text(encoding="utf-8", errors="replace").splitlines()
        n = len(line_cache[p])
        if ln > n or end > n:
            results.append((False, cite, f"line out of range (file has {n} lines)"))
            continue
        if check_quotes:
            # only AFTER the citation — a backward window picks up the previous
            # citation's quote and vacuously passes (caught by self-test)
            qm = QUOTE_NEAR.search(text[m.end():m.end() + 120])
            if qm:
                needle = " ".join(qm.group(1).split())
                window = " ".join(
                    " ".join(line_cache[p][max(0, ln - 1 - 5):min(n, end + 5)]).split())
                if needle and needle not in window:
                    results.append((False, cite, f"nearby quote {qm.group(1)!r} not found within ±5 lines"))
                    continue
        results.append((True, cite, "ok"))
    return results


def self_test() -> int:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "src").mkdir()
        (repo / "src" / "lib.rs").write_text("fn a() {}\nfn b() { panic!(\"boom\") }\nfn c() {}\n")
        doc = repo / "doc.md"
        doc.write_text(
            "Good cite src/lib.rs:2 with quote `panic!(\"boom\")` nearby.\n"
            "Out of range src/lib.rs:99 here.\n"
            "Missing file src/nope.rs:3 here.\n"
            "Bad quote src/lib.rs:1 says `does_not_exist()` supposedly.\n")
        res = check_doc(doc, repo, check_quotes=True)
        expected = [True, False, False, False]
        got = [ok for ok, _, _ in res]
        for (ok, cite, detail) in res:
            print(f"  {'ok  ' if ok else 'FAIL'} {cite}: {detail}")
        print("self-test:", "PASS" if got == expected else f"MISMATCH got={got} expected={expected}")
        return 0 if got == expected else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="file:line citation resolver")
    ap.add_argument("doc", nargs="?", help="document to check")
    ap.add_argument("--repo", default=".", help="checkout root citations resolve against")
    ap.add_argument("--quotes", action="store_true", help="also verify nearby backtick quotes")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any failed citation")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.doc:
        ap.error("DOC required unless --self-test")
    results = check_doc(Path(args.doc), Path(args.repo).resolve(), args.quotes)
    bad = [r for r in results if not r[0]]
    print(f"cite-check: {len(results)} citations, {len(bad)} unresolved in {args.doc}")
    for _, cite, detail in bad:
        print(f"  FAIL {cite}: {detail}")
    return 1 if (bad and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
