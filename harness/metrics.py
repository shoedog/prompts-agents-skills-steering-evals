"""Custom metrics over one experiment's per-item call + judge rows.

All functions operate on rows loaded from a SINGLE results dir (one experiment,
one tier). Aggregating across tiers is meaningless here — a weak-tier pass rate
and a strong-tier pass rate answer different questions — so every row-consuming
function asserts single-tier input and raises TierMixError otherwise.

Two accounting axes are reported SEPARATELY and never collapsed into one number:
  - logical tokens (fresh + cache-creation + cache-read): cache warming is
    arm-order dependent, so this is descriptive, not a clean isolation of the
    artifact's cost.
  - USD cost: does not isolate the artifact either (it blends model pricing and
    cache behavior).

Judge failures (`judge_error: true`) are excluded from pass/confusion metrics
but surfaced explicitly via a `judge_errors` count so a run can never quietly
launder harness breakage into a result.
"""
from __future__ import annotations

import glob
import json
import math
import os

Z_95 = 1.959963984540054  # 97.5th percentile of the standard normal


class TierMixError(Exception):
    """Raised when metric input rows carry more than one tier."""


class IntegrityError(Exception):
    """Raised when one or more per-item result JSON files cannot be parsed.

    Collected across the whole glob and raised once (with every offending path)
    so a single truncated file cannot masquerade as a clean, smaller run."""


def _assert_single_tier(rows):
    tiers = {r["tier"] for r in rows if isinstance(r, dict) and r.get("tier") is not None}
    if len(tiers) > 1:
        raise TierMixError(f"rows span multiple tiers: {sorted(tiers)}")


def load_rows(results_dir):
    """Load (calls, judges) row lists from a results dir's calls/ and judge/."""
    calls = _load_json_glob(os.path.join(results_dir, "calls", "*.json"))
    judges = _load_json_glob(os.path.join(results_dir, "judge", "*.json"))
    return calls, judges


def _load_json_glob(pattern):
    rows = []
    bad = []
    for p in sorted(glob.glob(pattern)):
        try:
            with open(p) as f:
                rows.append(json.load(f))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            bad.append(f"{p}: {e}")
    if bad:
        raise IntegrityError(
            "unparseable per-item result file(s):\n  " + "\n  ".join(bad)
        )
    return rows


# --------------------------------------------------------------------------- #
# Pass rate + Wilson interval
# --------------------------------------------------------------------------- #
def wilson_ci(k, n, z=Z_95):
    """Wilson score 95% CI for k successes out of n. Returns (low, high)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def pass_rate(rows, arm):
    """Item pass rate for one arm. Excludes judge_error rows from k/n and reports
    the excluded count as `judge_errors`."""
    _assert_single_tier(rows)
    arm_rows = [r for r in rows if r.get("arm") == arm]
    judge_errors = sum(1 for r in arm_rows if r.get("judge_error"))
    scored = [r for r in arm_rows if not r.get("judge_error")]
    n = len(scored)
    k = sum(1 for r in scored if r.get("item_pass"))
    rate = (k / n) if n else 0.0
    return {
        "k": k,
        "n": n,
        "rate": rate,
        "wilson_ci": wilson_ci(k, n),
        "judge_errors": judge_errors,
    }


# --------------------------------------------------------------------------- #
# Token / cost accounting
# --------------------------------------------------------------------------- #
_TOKEN_FIELDS = (
    ("fresh_input", "fresh_input_tokens"),
    ("cache_creation", "cache_creation_tokens"),
    ("cache_read", "cache_read_tokens"),
    ("output", "output_tokens"),
    ("logical_total", "input_tokens_logical"),
)


def token_totals(calls, arm):
    """Sum the token breakdown + USD for one arm's call rows."""
    _assert_single_tier(calls)
    arm_rows = [c for c in calls if c.get("arm") == arm]
    totals = {name: 0 for name, _ in _TOKEN_FIELDS}
    totals["cost_usd"] = 0.0
    for c in arm_rows:
        for name, key in _TOKEN_FIELDS:
            totals[name] += int(c.get(key, 0) or 0)
        totals["cost_usd"] += float(c.get("cost_usd", 0.0) or 0.0)
    return totals


def delta(baseline: dict, treatment: dict) -> dict:
    """Per-key {abs, pct} difference (treatment - baseline) over shared numerics."""
    out = {}
    for key, b in baseline.items():
        if not isinstance(b, (int, float)) or isinstance(b, bool):
            continue
        if key not in treatment:
            continue
        t = treatment[key]
        out[key] = {
            "abs": t - b,
            "pct": ((t - b) / b * 100.0) if b else None,
        }
    return out


# --------------------------------------------------------------------------- #
# Confusion matrix (item-level verdict + defect-level recall)
# --------------------------------------------------------------------------- #
def confusion(rows, arm):
    """Item-level TP/FP/TN/FN + base rate, defect-level recall, false findings.

    Item level (verdict): TP = seeded & flagged; FN = seeded & !flagged;
    FP = clean & flagged; TN = clean & !flagged. Excludes judge_error rows.
    """
    _assert_single_tier(rows)
    arm_rows = [r for r in rows if r.get("arm") == arm and not r.get("judge_error")]
    tp = fp = tn = fn = 0
    found = total = false_findings = 0
    judge_id_mismatches = 0
    for r in arm_rows:
        seeded = r.get("seeded")
        flagged = r.get("verdict_flagged")
        if seeded and flagged:
            tp += 1
        elif seeded and not flagged:
            fn += 1
        elif not seeded and flagged:
            fp += 1
        else:
            tn += 1
        if seeded:
            # Recall is anchored to GROUND TRUTH, not the judge's own id list:
            #   denominator = seeded defects from truth
            #   numerator   = truth ids the judge marked found
            # A judge-returned id NOT in truth is a hallucinated id — it can never
            # inflate recall; it is tallied separately as a mismatch.
            truth_ids = set(r.get("truth_defect_ids") or [])
            defects = r.get("defects") or []
            judge_found = {d.get("defect_id") for d in defects if d.get("found")}
            judge_ids = {d.get("defect_id") for d in defects if d.get("defect_id") is not None}
            total += len(truth_ids)
            found += len(truth_ids & judge_found)
            judge_id_mismatches += len(judge_ids - truth_ids)
        false_findings += int(r.get("false_findings", 0) or 0)
    n = len(arm_rows)
    positives = tp + fn
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "n": n,
        "base_rate": (positives / n) if n else 0.0,
        "defect_recall": {
            "found": found,
            "total": total,
            "rate": (found / total) if total else 0.0,
            "judge_id_mismatches": judge_id_mismatches,
        },
        "false_findings_total": false_findings,
    }


# --------------------------------------------------------------------------- #
# Paired flip table
# --------------------------------------------------------------------------- #
def paired_flips(rows):
    """Join baseline/treatment judge rows on task_id and classify the 2x2 flips.

    Task ids with a judge_error in either arm, or missing from an arm, are
    excluded (a flip needs a clean result in both arms)."""
    _assert_single_tier(rows)
    by_task: dict = {}
    for r in rows:
        arm = r.get("arm")
        if arm not in ("baseline", "treatment"):
            continue
        by_task.setdefault(r["task_id"], {})[arm] = r

    both_pass = both_fail = only_baseline = only_treatment = 0
    for task_id, arms in by_task.items():
        b = arms.get("baseline")
        t = arms.get("treatment")
        if b is None or t is None:
            continue
        if b.get("judge_error") or t.get("judge_error"):
            continue
        bp = bool(b.get("item_pass"))
        tp = bool(t.get("item_pass"))
        if bp and tp:
            both_pass += 1
        elif not bp and not tp:
            both_fail += 1
        elif bp and not tp:
            only_baseline += 1
        else:
            only_treatment += 1
    return {
        "both_pass": both_pass,
        "both_fail": both_fail,
        "only_baseline": only_baseline,
        "only_treatment": only_treatment,
    }


# --------------------------------------------------------------------------- #
# Adherence (treatment-arm directive compliance)
# --------------------------------------------------------------------------- #
_DIRECTIVES = (
    ("review-shape.checklist", "checklist"),
    ("review-shape.disconfirm", "disconfirm"),
    ("review-shape.verify", "verify"),
)


def adherence(rows):
    """Treatment-arm per-directive compliance rates + an all-three rate.

    Keyed by directive id so downstream adherence-battery experiments can cross
    compliance against outcome."""
    _assert_single_tier(rows)
    arm_rows = [
        r for r in rows
        if r.get("arm") == "treatment" and isinstance(r.get("adherence_labels"), dict)
    ]
    n = len(arm_rows)
    out = {}
    for directive_id, label_key in _DIRECTIVES:
        hits = sum(1 for r in arm_rows if r["adherence_labels"].get(label_key))
        out[directive_id] = (hits / n) if n else 0.0
    all_three = sum(
        1 for r in arm_rows
        if all(r["adherence_labels"].get(k) for _, k in _DIRECTIVES)
    )
    out["review-shape.all_three"] = (all_three / n) if n else 0.0
    return out


# --------------------------------------------------------------------------- #
# Triggering metrics (shape (c) support)
# --------------------------------------------------------------------------- #
def triggering_metrics(rows):
    """Precision/recall/confusion + base rate from {should_trigger, did_trigger}
    rows. Never reports bare accuracy — base rate is what makes accuracy a trap."""
    _assert_single_tier(rows)
    tp = fp = tn = fn = 0
    for r in rows:
        should = bool(r.get("should_trigger"))
        did = bool(r.get("did_trigger"))
        if should and did:
            tp += 1
        elif not should and did:
            fp += 1
        elif should and not did:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    base_rate = ((tp + fn) / n) if n else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "n": n,
        "precision": precision,
        "recall": recall,
        "base_rate": base_rate,
    }


# --------------------------------------------------------------------------- #
# Flags
# --------------------------------------------------------------------------- #
def flags(baseline_rate, treatment_rate, logical_token_delta_pct,
          negative_control, judge_errors):
    """Interpretation flags computed from already-reduced scalars.

    - cost_adjusted_verdict: treatment wins on pass rate AND costs >20% more
      logical tokens (a win you should discount).
    - harness_broken: this is a negative control yet treatment still beat
      baseline (the harness is measuring noise).
    - composite_floored: BOTH arms floor below 0.15 item-pass, so the composite
      metric is uninformative and the report must lead with defect recall +
      verdict confusion instead.
    """
    win = treatment_rate > baseline_rate
    token_bloat = (logical_token_delta_pct is not None) and (logical_token_delta_pct > 20.0)
    return {
        "cost_adjusted_verdict": bool(win and token_bloat),
        "harness_broken": bool(negative_control and win),
        "composite_floored": bool(baseline_rate < 0.15 and treatment_rate < 0.15),
        "judge_errors": int(judge_errors),
    }
