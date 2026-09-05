"""Exact-key paired binary flip tables for structured evaluation rows."""

from __future__ import annotations

from collections.abc import Sequence


def _index(rows: Sequence[dict], key: str, side: str) -> dict[object, dict]:
    indexed: dict[object, dict] = {}
    for row in rows:
        item_id = row[key]
        if item_id in indexed:
            raise ValueError(f"duplicate {side} {key} {item_id!r}")
        indexed[item_id] = row
    return indexed


def flips(
    rows_a: Sequence[dict],
    rows_b: Sequence[dict],
    key: str = "item_id",
    passed: str = "item_pass",
) -> dict[str, int]:
    """Count exact-key binary outcomes present and stage-error-free on both sides."""
    baseline = _index(rows_a, key, "baseline")
    candidate = _index(rows_b, key, "candidate")
    counts = {
        "both_pass": 0,
        "both_fail": 0,
        "only_baseline": 0,
        "only_treatment": 0,
    }
    for item_id in baseline.keys() & candidate.keys():
        row_a = baseline[item_id]
        row_b = candidate[item_id]
        if row_a.get("stage_error") or row_b.get("stage_error"):
            continue
        passed_a = bool(row_a.get(passed))
        passed_b = bool(row_b.get(passed))
        if passed_a and passed_b:
            counts["both_pass"] += 1
        elif not passed_a and not passed_b:
            counts["both_fail"] += 1
        elif passed_a:
            counts["only_baseline"] += 1
        else:
            counts["only_treatment"] += 1
    return counts
