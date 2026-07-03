#!/usr/bin/env python3
"""Regenerate report.md from a results dir's EXISTING calls/ + judge/ records
and its experiment config — no model calls, no re-run of the experiment, no
change to the computed metrics.

Companion to scripts/regen_spotcheck.py (which regenerates spotcheck.md/yaml
only, from judge/ records). This script regenerates report.md only: whenever
harness/report.py's RENDERING changes (e.g. the automatic honesty caveats —
recall-ceiling, CI-overlap — and the extra output/fresh-input delta rows),
every already-run, committed report needs those lines without re-running the
underlying (expensive, model-calling) experiment.

It reuses harness.report.summarize() (itself built entirely on
harness.metrics' pure functions) to recompute the summary dict straight from
calls/ + judge/, then harness.report.render_report_md() to render the new
report text — so the underlying numbers cannot drift from a hand-rolled
recomputation. Before writing, it asserts the recomputed reduced metrics
(the same dict harness.report.render() would serialize to metrics.json) are
value-identical to the results dir's EXISTING committed metrics.json; a
mismatch aborts without writing anything, on the theory that a metrics
change means something upstream is wrong, not just a report-wording change.

metrics.json and spotcheck.{md,yaml} are read-only here and never rewritten.
"""
import argparse
import json
import os
import sys

# Running this file directly (`python scripts/regen_report.py`) puts only
# `scripts/` on sys.path, not the repo root — `harness` isn't importable
# otherwise (same gap documented in scripts/regen_spotcheck.py).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness import config as config_mod  # noqa: E402
from harness.report import render_report_md, summarize  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        help="e.g. results/exp1-review-shape/weak (must contain calls/ + judge/)",
    )
    parser.add_argument(
        "experiment_config",
        help="e.g. experiments/exp1-review-shape.yaml (the config the run used)",
    )
    args = parser.parse_args()

    cfg = config_mod.load(args.experiment_config)
    s = summarize(cfg, args.results_dir)

    # Same reduction harness.report.render() performs before serializing
    # metrics.json — recomputed here purely to VERIFY against the committed
    # file, never to overwrite it. Round-tripped through JSON (dump then
    # load) before comparing: several values here are tuples in memory
    # (e.g. wilson_ci) but lists once read back from committed JSON, and a
    # bare `!=` would flag that harmless type difference as a metrics drift.
    recomputed_metrics = {k: v for k, v in s.items() if k not in ("calls", "judges")}
    recomputed_metrics = json.loads(json.dumps(recomputed_metrics, ensure_ascii=False))

    metrics_path = os.path.join(args.results_dir, "metrics.json")
    if os.path.isfile(metrics_path):
        with open(metrics_path) as f:
            committed_metrics = json.load(f)
        if committed_metrics != recomputed_metrics:
            print(
                f"ABORT: recomputed metrics differ from {metrics_path} — this "
                "is not a report-only rendering change; refusing to write "
                "report.md. Diff the two and investigate before regenerating.",
                file=sys.stderr,
            )
            return 1
    else:
        print(
            f"WARNING: no existing {metrics_path} to verify against "
            "(nothing to compare recomputed metrics to).",
            file=sys.stderr,
        )

    report_md = render_report_md(cfg, s)
    with open(os.path.join(args.results_dir, "report.md"), "w") as f:
        f.write(report_md)

    print(
        f"OK: regenerated {args.results_dir}/report.md "
        f"(metrics verified byte-identical to {metrics_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
