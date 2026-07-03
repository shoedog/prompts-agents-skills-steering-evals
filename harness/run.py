"""End-to-end experiment runner.

Pipeline: load config -> refuse to run over a stale/contaminated results dir ->
generate the two one-arm promptfoo configs -> run the BASELINE arm -> budget
gate (abort before spending the treatment arm if the baseline already implies
we would blow the cost cap) -> run the TREATMENT arm -> compute metrics ->
render report + spot-check. The process exits nonzero if the harness detects
it is broken (negative-control inversion), if any item hit a judge_error, or
if a results dir is stale/incomplete, so a wrapping CI/script can never treat
a compromised run as clean.

The executor and judge have no direct API keys — the only model transport is the
Python provider/assert shims, driven by promptfoo with PROMPTFOO_PYTHON pointing
at this interpreter. We pass --no-cache so arms never share cached completions.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
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


def _arm_ids_on_disk(results_dir, subdir, arm) -> set:
    """Task ids actually on disk for one arm under `subdir`, parsed back out of
    the `<arm>-<task_id>.json` filenames promptfoo/the assert write per item."""
    prefix = f"{arm}-"
    ids = set()
    for p in glob.glob(os.path.join(str(results_dir), subdir, f"{prefix}*.json")):
        name = os.path.basename(p)
        ids.add(name[len(prefix):-len(".json")])
    return ids


def _check_arm_integrity(results_dir, arm, expected_ids) -> bool:
    """True iff the arm produced EXACTLY the expected set of per-item task ids
    (from the taskset manifest) in BOTH calls/ and judge/ — not merely a count
    that is at-least `len(expected_ids)`.

    A pure count check cannot catch contamination: a leftover file from a
    stale/prior run plus a missing file for a current-run task id nets out to
    the SAME count as a clean run, so a count-only check would read a mixed
    (stale + fresh) results dir as clean. Diffing the actual id set against
    the manifest's expected ids catches both directions — ids the run never
    produced (a shortfall, e.g. promptfoo dying mid-run or an assert crash)
    and ids that shouldn't be there at all (contamination). judge/ is checked
    independently of calls/ for the same reason as before: calls/ can be
    complete while the assert crashes before writing its judge/ record for an
    item (an assert-crash shortfall). Warn loudly and let the caller mark the
    whole run integrity-failed."""
    expected = set(expected_ids)
    ok = True
    for subdir, label in (("calls", "call"), ("judge", "judge")):
        got = _arm_ids_on_disk(results_dir, subdir, arm)
        missing = expected - got
        unexpected = got - expected
        if missing or unexpected:
            parts = []
            if missing:
                parts.append(f"missing ids: {sorted(missing)}")
            if unexpected:
                parts.append(f"unexpected ids: {sorted(unexpected)}")
            print(
                f"[run] INTEGRITY FAILURE: arm '{arm}' produced {len(got)}/{len(expected)} "
                f"per-item {label} records and its task-id set does not match the "
                f"taskset manifest ({'; '.join(parts)}) — possible stale/contaminated "
                f"results dir or an incomplete run. The run is NOT clean.",
                file=sys.stderr, flush=True,
            )
            ok = False
    return ok


def _stale_result_files(results_dir) -> list:
    """Per-item calls/ and judge/ json files already sitting in `results_dir`
    before this run starts — leftovers from a previous run over this exact
    tier results dir."""
    out = []
    for subdir in ("calls", "judge"):
        out.extend(
            sorted(glob.glob(os.path.join(str(results_dir), subdir, "*.json")))
        )
    return out


def _check_stale_results_dir(results_dir, force: bool) -> bool:
    """Guard a tier results dir against silently mixing an old run's per-item
    records with a new one.

    metrics.py's calls/judge loaders glob ALL json files under calls/ and
    judge/ with no run-identity check, and `_check_arm_integrity` above only
    validates THIS run's expected ids are present — neither notices extra
    files left over from a prior run sharing the same tier dir (e.g. a
    manifest that later shrank, or a crashed run that was re-run without
    clearing first). So this guard runs BEFORE anything is generated: if
    calls/ or judge/ already contain files, it refuses outright unless
    `force` is set, and never deletes anything on its own initiative.

    Returns True if the caller may proceed (the dir was already clean, or
    `force` cleared it). Returns False (after printing a REFUSING message) if
    stale files exist and `force` was not requested.
    """
    stale = _stale_result_files(results_dir)
    if not stale:
        return True
    if not force:
        calls_dir = os.path.join(str(results_dir), "calls")
        judge_dir = os.path.join(str(results_dir), "judge")
        print(
            f"[run] REFUSING to run: {len(stale)} stale per-item result file(s) "
            f"already exist under {results_dir} (calls/ and/or judge/) from a "
            f"previous run over this exact tier results dir. Re-running here "
            f"would silently mix old and new records into the same metrics. "
            f"Delete {calls_dir} and {judge_dir} yourself and re-run, or pass "
            f"--force to clear them and proceed.",
            file=sys.stderr, flush=True,
        )
        return False
    print(
        f"[run] --force: clearing {len(stale)} stale per-item result file(s) "
        f"under {results_dir} (calls/, judge/) before this run.",
        flush=True,
    )
    for subdir in ("calls", "judge"):
        d = os.path.join(str(results_dir), subdir)
        if os.path.isdir(d):
            shutil.rmtree(d)
    return True


def run_experiment(config_path, force: bool = False) -> int:
    cfg = config_mod.load(config_path)
    results_dir = cfg.results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)

    if not _check_stale_results_dir(results_dir, force):
        return 4

    arms = gen_promptfoo(cfg, results_dir)
    expected_ids = [item["id"] for item in config_mod.load_taskset(cfg)]
    expected_items = len(expected_ids)
    print(f"[run] results dir: {results_dir}", flush=True)
    print(f"[run] expecting {expected_items} item(s) per arm", flush=True)
    integrity_ok = True

    # --- baseline arm ---
    _run_arm(cfg, arms["baseline"]["yaml"], results_dir / "promptfoo-baseline.json")
    integrity_ok = _check_arm_integrity(results_dir, "baseline", expected_ids) and integrity_ok

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
    integrity_ok = _check_arm_integrity(results_dir, "treatment", expected_ids) and integrity_ok

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
        print("[run] run marked INTEGRITY-FAILED: an arm's calls/ or judge/ task-id "
              "set does not match the taskset manifest (see warnings above).",
              file=sys.stderr, flush=True)
        exit_code = exit_code or 1
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harness.run",
        description="Run a prompt/skill/steering ablation experiment end-to-end.",
    )
    p.add_argument("experiment", help="path to an experiment config YAML (e.g. experiments/smoke.yaml)")
    p.add_argument(
        "--force",
        action="store_true",
        help=(
            "clear stale per-item calls/ and judge/ files already present in the "
            "tier results dir before running (without --force, a non-empty "
            "calls/ or judge/ dir makes the run refuse to start, to avoid "
            "silently mixing old and new records)."
        ),
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return run_experiment(args.experiment, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
