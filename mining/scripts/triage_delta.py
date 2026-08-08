#!/usr/bin/env python3
"""Daily triage delta: accumulate nomination evidence, append only what's new.

Reads mining/out/{failure,success}_nominations.md (regenerated daily by the
detectors), keys every evidence row by (source, class, session, line), stores
first-seen rows durably in triage_evidence.jsonl, and appends a dated section
to triage-inbox.md containing ONLY new evidence — grouped by signature class,
with tallies for prioritization. A class nominated yesterday that gains
evidence today is the SAME nomination: new rows attach under it and the
running tally rises. Old inbox sections are never rewritten, so owner
checkmarks persist. Cron: 07:10, after both detectors.
"""
import json
import re
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"
SOURCES = {
    "failure": OUT / "failure_nominations.md",
    "success": OUT / "success_nominations.md",
}
STORE = OUT / "triage_evidence.jsonl"
INBOX = OUT / "triage-inbox.md"

SECTION_RE = re.compile(r"^## (\S+) — (\d+) (?:total|rows)")
ROW_RE = re.compile(r"^- \[[ x]\] (\S+) `([^`]+)` L(\d+)")


def parse(source, path):
    rows, cls, detector_total = [], None, {}
    if not path.exists():
        return rows, detector_total
    for line in path.read_text().splitlines():
        m = SECTION_RE.match(line)
        if m:
            cls = m.group(1)
            detector_total[cls] = int(m.group(2))
            continue
        m = ROW_RE.match(line)
        if m and cls:
            ts, session, lno = m.groups()
            rows.append({
                "key": f"{source}|{cls}|{session}|L{lno}",
                "source": source, "class": cls, "ts": ts,
                "session": session, "line": int(lno), "row": line,
            })
    return rows, detector_total


def main():
    today = date.today().isoformat()
    seen, store_rows = set(), []
    if STORE.exists():
        for raw in STORE.read_text().splitlines():
            r = json.loads(raw)
            seen.add(r["key"])
            store_rows.append(r)

    new, detector_totals = [], {}
    for source, path in SOURCES.items():
        rows, totals = parse(source, path)
        for cls, n in totals.items():
            detector_totals[(source, cls)] = n
        new.extend(r for r in rows if r["key"] not in seen)

    if not new:
        print(f"triage_delta: {today} no new evidence")
        return

    for r in new:
        r["first_seen"] = today
    with STORE.open("a") as f:
        for r in new:
            f.write(json.dumps(r) + "\n")
    store_rows.extend(new)

    # Per-class store stats (all-time surfaced evidence).
    stats = {}
    for r in store_rows:
        k = (r["source"], r["class"])
        s = stats.setdefault(k, {"n": 0, "sessions": set(), "first": r["first_seen"]})
        s["n"] += 1
        s["sessions"].add(r["session"])
        s["first"] = min(s["first"], r["first_seen"])

    by_class = {}
    for r in new:
        by_class.setdefault((r["source"], r["class"]), []).append(r)
    ordered = sorted(by_class.items(), key=lambda kv: -len(kv[1]))

    lines = [f"# {today} — triage delta: +{len(new)} new evidence rows "
             f"across {len(by_class)} nominations", ""]
    for (source, cls), rows in ordered:
        s = stats[(source, cls)]
        det = detector_totals.get((source, cls))
        det_note = f"; detector reports {det} total today" if det is not None else ""
        prior = s["n"] - len(rows)
        lines.append(
            f"## [{source}] {cls} — +{len(rows)} new · {s['n']} in store across "
            f"{len(s['sessions'])} sessions · first seen {s['first']}{det_note}")
        lines.extend(r["row"] for r in sorted(rows, key=lambda r: r["ts"], reverse=True))
        if prior:
            lines.append(f"  (prior evidence: {prior} rows under earlier dates in this "
                         f"inbox / triage_evidence.jsonl; full stream: {source}_signatures.jsonl)")
        lines.append("")

    header = "" if INBOX.exists() else (
        "# Triage inbox — append-only daily deltas\n\n"
        "New evidence only; a class recurring across days is one nomination\n"
        "accumulating evidence — tallies in each day's headers are the priority\n"
        "signal. Check rows off as triaged; old sections are never rewritten.\n\n")
    with INBOX.open("a") as f:
        f.write(header + "\n".join(lines) + "\n")
    print(f"triage_delta: {today} +{len(new)} rows in {len(by_class)} classes -> {INBOX.name}")


if __name__ == "__main__":
    main()
