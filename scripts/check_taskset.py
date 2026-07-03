#!/usr/bin/env python3
"""Validate a taskset dir: manifest parses, every item has context/diff/truth,
seeded items carry 1-2 fully-populated defects, clean items carry rationale +
tempting_non_defects. Prints seeded/clean counts and base rate. See check_moves.py."""
import sys, pathlib, yaml

DEFECT_FIELDS = ["id", "defect_class", "location", "hunk_lines", "description",
                 "root_cause", "bad_behavior", "minimal_trigger",
                 "acceptable_match", "reject_if"]

def main(root):
    root = pathlib.Path(root)
    errors = []
    man_path = root / "manifest.yaml"
    if not man_path.is_file():
        sys.exit(f"FAIL: missing {man_path}")
    man = yaml.safe_load(man_path.read_text())
    items = man.get("items") if isinstance(man, dict) else None
    if not isinstance(items, list) or not items:
        sys.exit("FAIL: manifest 'items' list missing or empty")
    ids, seeded_n, clean_n = set(), 0, 0
    for it in items:
        iid = str(it.get("id"))
        if iid in ids:
            errors.append(f"duplicate id {iid!r}")
        ids.add(iid)
        d = root / "items" / iid
        ctx, dp, tp = d / "context.md", d / "diff.patch", d / "truth.yaml"
        for f in (ctx, dp, tp):
            if not f.is_file():
                errors.append(f"{iid}: missing {f.name}")
        if not tp.is_file():
            continue
        truth = yaml.safe_load(tp.read_text()) or {}
        seeded = bool(truth.get("seeded"))
        if seeded != bool(it.get("seeded")):
            errors.append(f"{iid}: manifest seeded={it.get('seeded')} != truth {truth.get('seeded')}")
        if ctx.is_file() and len(ctx.read_text().splitlines()) > 25:
            errors.append(f"{iid}: context.md > 25 lines")
        if dp.is_file():
            t = dp.read_text()
            if "--- " not in t or "+++ " not in t or "@@" not in t:
                errors.append(f"{iid}: diff.patch missing ---/+++/@@ markers")
        defects = truth.get("defects") or []
        # neutral_findings (OPTIONAL, seeded-only): true-but-out-of-scope
        # observations the judge treats as neither credit nor false finding.
        # Clean items stay strict — they may NOT carry any neutral_findings.
        neutral = truth.get("neutral_findings")
        if seeded:
            seeded_n += 1
            if not (1 <= len(defects) <= 2):
                errors.append(f"{iid}: seeded needs 1-2 defects, has {len(defects)}")
            did = set()
            for j, df in enumerate(defects):
                if not isinstance(df, dict):
                    errors.append(f"{iid} defect[{j}]: not a mapping"); continue
                for k in DEFECT_FIELDS:
                    if df.get(k) in (None, "", []):
                        errors.append(f"{iid} defect[{j}]: missing/empty '{k}'")
                if df.get("id") in did:
                    errors.append(f"{iid}: duplicate defect id {df.get('id')!r}")
                did.add(df.get("id"))
            if neutral is not None:
                if not isinstance(neutral, list) or not neutral:
                    errors.append(f"{iid}: neutral_findings must be a non-empty list when present")
                else:
                    for j, nf in enumerate(neutral):
                        if not isinstance(nf, str) or not nf.strip():
                            errors.append(f"{iid} neutral_findings[{j}]: must be a non-empty string")
        else:
            clean_n += 1
            if defects:
                errors.append(f"{iid}: clean item must have 0 defects, has {len(defects)}")
            if neutral is not None:
                errors.append(f"{iid}: clean item must not carry neutral_findings (seeded-only field)")
            if not (truth.get("clean_rationale") or "").strip():
                errors.append(f"{iid}: clean item missing clean_rationale")
            tnd = truth.get("tempting_non_defects")
            if not isinstance(tnd, list) or not tnd:
                errors.append(f"{iid}: clean item missing non-empty tempting_non_defects list")
    idir = root / "items"
    if idir.is_dir():
        orphan = {p.name for p in idir.iterdir() if p.is_dir()} - ids
        if orphan:
            errors.append(f"item dirs not in manifest: {sorted(orphan)}")
    if errors:
        print("\n".join(errors)); sys.exit(f"FAIL: {len(errors)} error(s)")
    total = seeded_n + clean_n
    rate = seeded_n / total if total else 0.0
    print(f"OK: {total} items - {seeded_n} seeded / {clean_n} clean, base rate {rate:.2f}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_taskset.py <taskset_dir>")
    main(sys.argv[1])
