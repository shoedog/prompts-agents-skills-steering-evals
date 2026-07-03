#!/usr/bin/env python3
"""Regenerate spotcheck.md + spotcheck.yaml from a results dir's EXISTING
judge/ records — no model call, no re-run of the experiment.

Useful whenever `harness/report.py`'s spot-check sampling logic changes (e.g.
the arm-stratification fix that replaced the naive `graded[:20]` sample,
which put every sampled item in whichever arm sorts first alphabetically) and
already-run results need their spot-check materials regenerated to match,
without re-running the underlying (expensive, model-calling) experiment.

Only touches spotcheck.md / spotcheck.yaml. metrics.json and report.md (the
experiment's actual numeric results) are read-only here and never rewritten.
"""
import argparse
import os
import sys

# Running this file directly (`python scripts/regen_spotcheck.py`) puts only
# `scripts/` on sys.path, not the repo root — `harness` isn't importable
# otherwise (same gap documented in harness/providers/promptfoo_claude.py).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.metrics import load_rows  # noqa: E402
from harness.report import render_spotcheck  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        help="e.g. results/exp1-review-shape/weak (must contain a judge/ dir)",
    )
    args = parser.parse_args()

    _, judges = load_rows(args.results_dir)

    spot_md, spot_rows = render_spotcheck(judges)

    import yaml  # local import: keep this script's only non-stdlib dep scoped

    with open(os.path.join(args.results_dir, "spotcheck.md"), "w") as f:
        f.write(spot_md)
    with open(os.path.join(args.results_dir, "spotcheck.yaml"), "w") as f:
        yaml.safe_dump({"items": spot_rows}, f, sort_keys=False, allow_unicode=True)

    counts = {}
    for r in spot_rows:
        counts[r["arm"]] = counts.get(r["arm"], 0) + 1
    counts_str = " ".join(f"{arm}={n}" for arm, n in sorted(counts.items()))
    print(
        f"OK: regenerated {args.results_dir}/spotcheck.{{md,yaml}} — "
        f"{len(spot_rows)} rows ({counts_str})"
    )


if __name__ == "__main__":
    main()
