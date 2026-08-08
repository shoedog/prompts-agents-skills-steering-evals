#!/usr/bin/env python3
"""One-shot (idempotent) scrub of triage_evidence.jsonl for evidence the
fixed detectors would no longer emit (2026-08-08 precision batch; weekly
triage sign-off items 2+3).

Marks rows -- never deletes them, so their keys keep suppressing
resurfacing in triage_delta.py -- with an `excluded` field that
triage_delta's tallies skip:

  excluded: "sandbox-corpus"  row's cwd lies under this repo's results/
                              dir (eval-harness sandbox transcripts, the
                              177-row exp-w3a contamination).
  excluded: "lineage-dupe"    row cites a post-compaction fork file and a
                              row with the same (source, class, ts) exists
                              for the fork's parent session (the same event
                              counted twice); `dupe_of` names the parent
                              row's key. Fork pairs come from the failure
                              detector's lineage_dupe rows.

Usage:
  python3 mining/scripts/triage_store_scrub.py            # real store
  (test hook: scrub(store_path, signatures_path) marks and rewrites)

Runs under /usr/bin/python3 (3.9) -- keep 3.9-compatible.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"
STORE = OUT / "triage_evidence.jsonl"
SIGNATURES = OUT / "failure_signatures.jsonl"

REPO_RESULTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "results") + "/"
FORK_SNIPPET = re.compile(r"first content line of (\S+\.jsonl) found at line \d+ of (\S+\.jsonl)")


def fork_pairs(signatures_path: Path) -> "list[tuple[str, str]]":
    """(child_stem, parent_stem) pairs from the detector's lineage_dupe rows."""
    pairs = []
    if not signatures_path.exists():
        return pairs
    with open(signatures_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("detector") != "lineage_dupe":
                continue
            m = FORK_SNIPPET.search(r.get("snippet") or "")
            if m:
                child, parent = m.group(1), m.group(2)
                pairs.append((child[:-6], parent[:-6]))  # strip .jsonl
    return pairs


def scrub(store_path: Path, signatures_path: Path) -> int:
    """Mark contaminated / duplicated store rows; returns rows newly marked."""
    rows = []
    with open(store_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # parent lookup for lineage marking: (source, class, ts, session24) present?
    by_event = {}
    for r in rows:
        by_event[(r["source"], r["class"], r["ts"], r["session"])] = r

    child_to_parent = {c[:24]: p[:24] for c, p in fork_pairs(signatures_path)}

    n_marked = 0
    for r in rows:
        if r.get("excluded"):
            continue
        if REPO_RESULTS_DIR in r.get("row", ""):
            r["excluded"] = "sandbox-corpus"
            n_marked += 1
            continue
        parent24 = child_to_parent.get(r["session"])
        if parent24:
            parent_row = by_event.get((r["source"], r["class"], r["ts"], parent24))
            if parent_row is not None:
                r["excluded"] = "lineage-dupe"
                r["dupe_of"] = parent_row["key"]
                n_marked += 1

    tmp = store_path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(store_path)
    return n_marked


def main():
    n = scrub(STORE, SIGNATURES)
    total = sum(1 for _ in open(STORE, encoding="utf-8"))
    marked = sum(1 for line in open(STORE, encoding="utf-8")
                 if json.loads(line).get("excluded"))
    print(f"triage_store_scrub: {n} rows newly marked; {marked}/{total} total excluded "
          f"({STORE.name})")


if __name__ == "__main__":
    main()
