#!/usr/bin/env python3
"""Rescore an already-run experiment's executor outputs under the CURRENT truth
+ rubric + schema, WITHOUT re-running the (expensive) executor.

The executor evidence is fixed: every source `calls/<arm>-<task_id>.json` is
copied VERBATIM into the new results dir (costs/tokens identical by
construction). Only the JUDGE is re-run. For each source
`judge/<arm>-<task_id>.json`, we take its `normalized_block` — the EXACT graded
surface the blind judge saw the first time — and re-judge it LIVE against the
current ground truth (`truth_path` on the record, whose CONTENT may have
changed, e.g. new `neutral_findings`), rubric, and schema, using the same
`harness.judge.judge_review` retry-once semantics as the live assert. Item-pass
is recomputed with the UNCHANGED rule; seeded/adherence/verdict fields are
carried over from the source record (they do not depend on the truth edit).

Then metrics + report + spotcheck are written via the existing report module,
and the report carries a provenance note recording that the executor calls are
shared verbatim with the source run.

Usage:
    scripts/rejudge.py <source_results_dir> <experiment_config> <output_exp_id>

e.g.
    scripts/rejudge.py results/exp1-review-shape/weak \\
        experiments/exp1-review-shape.yaml exp1-review-shape-rescored
"""
import argparse
import dataclasses
import glob
import json
import os
import shutil
import sys

# Running this file directly puts only `scripts/` on sys.path, not the repo
# root — `harness` isn't importable otherwise (same gap as regen_report.py).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness import config as config_mod  # noqa: E402
from harness import report as report_mod  # noqa: E402
from harness.judge import JudgeError, judge_review, load_truth  # noqa: E402
from harness.tracing import trace_call  # noqa: E402

_NOTE = (
    "Rescore of exp1-review-shape executor outputs under neutral-findings "
    "scoring; executor calls shared verbatim with results/exp1-review-shape/."
)


def _recompute_item_pass(seeded, truth_defect_ids, found_ids,
                         false_findings, verdict_flagged) -> bool:
    """The item-pass rule, UNCHANGED (mirrors harness.asserts.judge_assert).

    Neutral matches never appear here: a neutral match is excluded from
    false_findings by the judge, so it can neither block nor grant a pass.
    """
    if seeded:
        all_found = bool(truth_defect_ids) and set(truth_defect_ids).issubset(found_ids)
        return all_found and false_findings == 0 and verdict_flagged
    return false_findings == 0 and not verdict_flagged


def _rejudge_one(src_record: dict, judge_cfg: dict, judge_scratch: str,
                 output_exp_id: str, out_dir: str | None = None) -> dict:
    """Re-judge one source judge record's normalized_block against current truth.

    Carries over the deterministic/executor-derived fields; re-derives the
    graded fields (defects/false_findings/neutral_matched) from a fresh LIVE
    judge call; recomputes item_pass with the unchanged rule.

    The written record is stamped with `output_exp_id` — the NEW rescore's own
    experiment id — not the source run's `exp_id`. The executor calls are
    shared verbatim with the source run, but this record lives under the
    OUTPUT results dir and must identify itself as belonging to that
    experiment, not the one it was rescored from (a stale source exp_id here
    would make metrics.json/report.md lie about which run produced this
    grade).

    A native per-call trace log is appended to `out_dir/trace.jsonl` (via
    `harness.tracing.trace_call`, same mechanism the live assert uses) for
    every row that actually reached a live judge call — i.e. everything
    except a carried-over source parse-failure, which never calls the judge
    either here or in the original run.
    """
    arm = src_record["arm"]
    task_id = src_record["task_id"]
    seeded = bool(src_record.get("seeded"))
    verdict_flagged = bool(src_record.get("verdict_flagged"))
    normalized = src_record.get("normalized_block") or ""

    # Current ground truth (content may have changed since the source run).
    truth = load_truth(src_record["truth_path"])
    truth_defect_ids = sorted({d["id"] for d in (truth.get("defects") or [])})

    base = {
        "exp_id": output_exp_id,
        "arm": arm,
        "task_id": task_id,
        "tier": src_record.get("tier"),
        "seeded": seeded,
        "adherence_labels": src_record.get("adherence_labels"),
        "truth_path": src_record["truth_path"],
        "truth_defect_ids": truth_defect_ids,
        "normalized_block": normalized,
    }

    # A source PARSE FAILURE never reached the judge — there is nothing to
    # re-judge. Carry it over as a parse-failure row (no judge call, no
    # trace), exactly as the live assert would produce it.
    if not src_record.get("parse_ok"):
        return dict(base, parse_ok=False, defects=[], false_findings=0,
                    neutral_matched=0, verdict_flagged=False, item_pass=False,
                    judge_error=False, judge_tokens=None, judge_cost_usd=None)

    try:
        judged = judge_review(normalized, truth, judge_cfg, cwd=judge_scratch)
    except JudgeError as e:
        print(f"  [rejudge] JUDGE ERROR on {arm}-{task_id}: {e}", file=sys.stderr, flush=True)
        record = dict(base, parse_ok=True, defects=[], false_findings=0,
                     neutral_matched=0, verdict_flagged=verdict_flagged,
                     item_pass=False, judge_error=True, judge_tokens=None,
                     judge_cost_usd=None)
        trace_call("rejudge_judge_error", {"task_id": task_id, "arm": arm, "error": str(e)},
                   results_dir=out_dir)
        return record

    defects = judged.get("defects", []) or []
    false_findings = int(judged.get("false_findings", 0) or 0)
    neutral_matched = int(judged.get("neutral_matched", 0) or 0)
    found_ids = {d.get("defect_id") for d in defects if d.get("found")}
    item_pass = _recompute_item_pass(
        seeded, truth_defect_ids, found_ids, false_findings, verdict_flagged
    )

    record = dict(base, parse_ok=True, defects=defects, false_findings=false_findings,
                 neutral_matched=neutral_matched, verdict_flagged=verdict_flagged,
                 item_pass=item_pass, judge_error=False,
                 judge_tokens=judged.get("judge_tokens"), judge_cost_usd=None)
    trace_call("rejudge_judge", record, results_dir=out_dir)
    return record


def _clear_derived(dirpath: str):
    """Clear calls/ and judge/ under a NEW rescore output dir so a re-run starts
    fresh (the whole dir is derived output owned by this script)."""
    for sub in ("calls", "judge"):
        d = os.path.join(dirpath, sub)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source_results_dir",
                        help="e.g. results/exp1-review-shape/weak (source calls/ + judge/)")
    parser.add_argument("experiment_config",
                        help="e.g. experiments/exp1-review-shape.yaml")
    parser.add_argument("output_exp_id",
                        help="new experiment id, e.g. exp1-review-shape-rescored")
    args = parser.parse_args(argv)

    src = args.source_results_dir
    src_calls = sorted(glob.glob(os.path.join(src, "calls", "*.json")))
    src_judges = sorted(glob.glob(os.path.join(src, "judge", "*.json")))
    if not src_judges:
        print(f"ABORT: no judge records under {src}/judge/", file=sys.stderr)
        return 2

    cfg = config_mod.load(args.experiment_config)
    # Re-badge the config with the new id so results_dir() and the report's
    # Configuration echo point at the rescored experiment.
    cfg = dataclasses.replace(cfg, id=args.output_exp_id)
    out_dir = str(cfg.results_dir())
    os.makedirs(out_dir, exist_ok=True)
    _clear_derived(out_dir)
    print(f"[rejudge] source: {src}", flush=True)
    print(f"[rejudge] output: {out_dir}", flush=True)

    # 1) Copy executor calls VERBATIM (costs/tokens identical by construction).
    for p in src_calls:
        shutil.copy2(p, os.path.join(out_dir, "calls", os.path.basename(p)))
    print(f"[rejudge] copied {len(src_calls)} executor call record(s) verbatim", flush=True)

    # 2) Re-judge each normalized_block LIVE against current truth/rubric/schema.
    judge_cfg = {
        "provider": cfg.judge.provider,
        "model": cfg.judge.model,
        "effort": cfg.judge.effort,
        "rubric": str(cfg.rubric_path()),
        "schema": str(cfg.schema_path()),
    }
    judge_scratch = os.path.join(out_dir, "judge_scratch")
    os.makedirs(judge_scratch, exist_ok=True)

    judge_errors = 0
    total = len(src_judges)
    for i, p in enumerate(src_judges, 1):
        with open(p) as f:
            src_record = json.load(f)
        name = os.path.basename(p)
        print(f"[rejudge] ({i}/{total}) judging {name} ...", flush=True)
        new_record = _rejudge_one(src_record, judge_cfg, judge_scratch,
                                  args.output_exp_id, out_dir=out_dir)
        if new_record.get("judge_error"):
            judge_errors += 1
        with open(os.path.join(out_dir, "judge", name), "w") as f:
            json.dump(new_record, f, ensure_ascii=False, indent=2)

    # 3) metrics + report + spotcheck via the existing module (report carries
    #    the provenance note).
    report_mod.render(cfg, out_dir, note=_NOTE)
    print(f"[rejudge] report written to {os.path.join(out_dir, 'report.md')}", flush=True)

    if judge_errors:
        print(
            f"[rejudge] FAIL: {judge_errors} judge_error(s) after retry — the "
            "rescore is NOT clean. Fix the failing judge call(s) and re-run the "
            "rescore fresh.",
            file=sys.stderr, flush=True,
        )
        return 1

    print(f"[rejudge] OK: rescored {total} item(s), 0 judge errors.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
