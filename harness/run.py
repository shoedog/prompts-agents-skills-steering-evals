"""End-to-end experiment runner.

Pipeline: load config -> generate the two one-arm promptfoo configs -> run the
BASELINE arm -> budget gate (abort before spending the treatment arm if the
baseline already implies we would blow the cost cap) -> run the TREATMENT arm ->
compute metrics -> render report + spot-check. The process exits nonzero if the
harness detects it is broken (negative-control inversion) or if any item hit a
judge_error, so a wrapping CI/script can never treat a compromised run as clean.

The executor and judge have no direct API keys — the only model transport is the
Python provider/assert shims, driven by promptfoo with PROMPTFOO_PYTHON pointing
at this interpreter. We pass --no-cache so arms never share cached completions.
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

from harness import config as config_mod
from harness import metrics as metrics_mod
from harness import report as report_mod
from harness.gen_promptfoo import gen_promptfoo


def _promptfoo_env() -> dict:
    env = dict(os.environ)
    env["PROMPTFOO_PYTHON"] = sys.executable
    env.setdefault("PROMPTFOO_DISABLE_TELEMETRY", "1")
    env.setdefault("PROMPTFOO_DISABLE_UPDATE", "1")
    return env


def _run_arm(cfg, yaml_path, json_path) -> int:
    argv = [
        "npx", "promptfoo", "eval",
        "-c", str(yaml_path),
        "--output", str(json_path),
        "--no-cache",
        "-j", "4",
    ]
    print(f"[run] {' '.join(argv)}", flush=True)
    proc = subprocess.run(argv, cwd=str(cfg.root), env=_promptfoo_env(), check=False)
    # promptfoo exits 100 when any test fails its assert — that is EXPECTED here
    # (a failed review item is a legitimate outcome), so we do not treat a
    # nonzero code as fatal; downstream we rely on the per-item calls/judge files.
    return proc.returncode


def _arm_cost(results_dir, arm) -> float:
    # Route through metrics._load_json_glob (not a bare json.load loop) so a
    # truncated/unparseable calls/ file surfaces as the same named
    # IntegrityError metrics.load_rows raises, instead of crashing the budget
    # gate on the first bad file with a plain JSONDecodeError.
    rows = metrics_mod._load_json_glob(
        os.path.join(str(results_dir), "calls", f"{arm}-*.json")
    )
    return sum(float(r.get("cost_usd", 0.0) or 0.0) for r in rows)


def _count_arm_files(results_dir, subdir, arm) -> int:
    """Number of per-item JSON records written for one arm under `subdir`."""
    return len(glob.glob(os.path.join(str(results_dir), subdir, f"{arm}-*.json")))


def _count_arm_calls(results_dir, arm) -> int:
    """Number of per-item call records promptfoo wrote for one arm."""
    return _count_arm_files(results_dir, "calls", arm)


def _count_arm_judges(results_dir, arm) -> int:
    """Number of per-item judge records the assert wrote for one arm."""
    return _count_arm_files(results_dir, "judge", arm)


def _check_arm_integrity(results_dir, arm, expected_items) -> bool:
    """True iff the arm produced at least `expected_items` call records AND
    at least `expected_items` judge records.

    A silent shortfall (e.g. promptfoo dying mid-run, an n=0 arm) would
    otherwise read as a clean, smaller run — checked via calls/. But calls/ can
    also be complete while the assert crashes before writing its judge/ record
    for an item (an assert-crash shortfall), which would ALSO read as a clean,
    smaller-n run if only calls/ were counted. So judge/ is checked
    independently against the same expected_items. Warn loudly and let the
    caller mark the whole run integrity-failed."""
    ok = True
    got_calls = _count_arm_calls(results_dir, arm)
    if got_calls < expected_items:
        print(
            f"[run] INTEGRITY FAILURE: arm '{arm}' produced {got_calls}/{expected_items} "
            f"per-item call records — promptfoo did not complete every item. "
            f"The run is NOT clean.",
            file=sys.stderr, flush=True,
        )
        ok = False
    got_judges = _count_arm_judges(results_dir, arm)
    if got_judges < expected_items:
        print(
            f"[run] INTEGRITY FAILURE: arm '{arm}' produced {got_judges}/{expected_items} "
            f"per-item judge records — the assert did not run to completion for "
            f"every item (possible assert crash). The run is NOT clean.",
            file=sys.stderr, flush=True,
        )
        ok = False
    return ok


def run_experiment(config_path) -> int:
    cfg = config_mod.load(config_path)
    results_dir = cfg.results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)

    arms = gen_promptfoo(cfg, results_dir)
    expected_items = len(config_mod.load_taskset(cfg))
    print(f"[run] results dir: {results_dir}", flush=True)
    print(f"[run] expecting {expected_items} item(s) per arm", flush=True)
    integrity_ok = True

    # --- baseline arm ---
    _run_arm(cfg, arms["baseline"]["yaml"], results_dir / "promptfoo-baseline.json")
    integrity_ok = _check_arm_integrity(results_dir, "baseline", expected_items) and integrity_ok

    baseline_cost = _arm_cost(results_dir, "baseline")
    projected = baseline_cost * 2
    print(f"[run] baseline arm cost ${baseline_cost:.4f}; projected 2-arm ${projected:.4f} "
          f"(cap ${cfg.token_budget.max_cost_usd:.2f})", flush=True)
    if projected > cfg.token_budget.max_cost_usd:
        print(
            f"[run] ABORT: projected two-arm cost ${projected:.4f} exceeds "
            f"max_cost_usd ${cfg.token_budget.max_cost_usd:.2f}; not running treatment arm.",
            file=sys.stderr, flush=True,
        )
        return 3

    # --- treatment arm ---
    _run_arm(cfg, arms["treatment"]["yaml"], results_dir / "promptfoo-treatment.json")
    integrity_ok = _check_arm_integrity(results_dir, "treatment", expected_items) and integrity_ok

    # --- metrics + report ---
    summary = report_mod.render(cfg, results_dir)
    print(f"[run] report written to {results_dir/'report.md'}", flush=True)

    fl = summary["flags"]
    exit_code = 0
    if fl["harness_broken"]:
        print("[run] HARNESS BROKEN: negative control inverted.", file=sys.stderr, flush=True)
        exit_code = 2
    if summary["judge_errors"]:
        print(f"[run] {summary['judge_errors']} judge_error(s) — run is not clean.",
              file=sys.stderr, flush=True)
        exit_code = exit_code or 1
    if not integrity_ok:
        print("[run] run marked INTEGRITY-FAILED: an arm is missing per-item call "
              "records (see warnings above).", file=sys.stderr, flush=True)
        exit_code = exit_code or 1
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harness.run",
        description="Run a prompt/skill/steering ablation experiment end-to-end.",
    )
    p.add_argument("experiment", help="path to an experiment config YAML (e.g. experiments/smoke.yaml)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return run_experiment(args.experiment)


if __name__ == "__main__":
    raise SystemExit(main())
