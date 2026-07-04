#!/usr/bin/env python3
"""Human-calibration gate for the blind judge (NOT a harness integrity check).

Reads a results dir's `spotcheck.yaml` (written by `report.render`, one row per
sampled judged item with an initially-empty `agree:` field). This never
auto-passes on judgment quality: it only reports what a human has recorded so
far.

  - No `agree:` fields filled in yet -> PROVISIONAL (human hasn't reviewed),
    exit 0 (a fresh run is expected to be provisional; this is not a failure).
  - An `items:` key that is PRESENT but EMPTY (`items: []` — e.g. a taskset
    with zero judged rows to sample) -> PROVISIONAL, exit 0: there is nothing
    to spot-check yet, which is not the same failure as a malformed/missing
    `items` key.
  - Some/all filled -> disagreement rate over the filled subset. >20%
    disagreement -> STOP-and-recalibrate, exit 1. Otherwise print the
    agreement rate, exit 0.

See check_moves.py / check_taskset.py for the sibling structural-validators.
"""
import pathlib
import sys

import yaml


def main(results_dir):
    path = pathlib.Path(results_dir) / "spotcheck.yaml"
    if not path.is_file():
        sys.exit(f"FAIL: spotcheck.yaml not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    items = data.get("items") if isinstance(data, dict) else None
    if items is None or not isinstance(items, list):
        sys.exit("FAIL: spotcheck.yaml has no 'items' list")
    if not items:
        # Present but empty is a legitimate shape (e.g. a run with zero
        # judged rows to sample) — not a malformed file. Nothing to
        # spot-check yet, so this is provisional, not a failure.
        print("PROVISIONAL: spotcheck.yaml has an empty 'items' list (nothing to spot-check yet)")
        return

    filled = [it for it in items if it.get("agree") is not None]
    if not filled:
        print("PROVISIONAL: human spot-check not yet recorded")
        return

    disagree = sum(1 for it in filled if not it.get("agree"))
    rate = disagree / len(filled)
    if rate > 0.20:
        print(
            f"STOP AND RECALIBRATE: {disagree}/{len(filled)} = {rate:.1%} of "
            f"spot-checked items disagree with the blind judge (>20% "
            f"threshold). Do not trust this run's judge grades until the "
            f"judge/rubric has been recalibrated."
        )
        sys.exit(1)

    agree = len(filled) - disagree
    print(
        f"OK: {agree}/{len(filled)} = {agree/len(filled):.1%} agreement with "
        f"the judge ({len(filled)}/{len(items)} sampled items reviewed so far)"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_spotcheck.py <results_dir>")
    main(sys.argv[1])
