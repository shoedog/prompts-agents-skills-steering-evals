"""CI gate for the eval harness.

Two tiers, deliberately separated by cost:

  (a) Cheap structural checks (`test_moves_check`, `test_artifact_lint`,
      `test_taskset_check`) subprocess the three `scripts/check_*.py`
      validators. No model calls, no promptfoo. These always run.

  (b) `test_smoke_run` — the harness's first end-to-end contact with reality.
      It runs `python -m harness.run experiments/smoke.yaml` for real (5 items
      x 2 arms = 10 haiku executor calls + 10 codex judge calls; a few dollars,
      several minutes), then wraps the written artifacts in a deepeval
      `assert_test` against a custom BINARY `HarnessIntegrityMetric`. That
      metric makes NO model calls of its own — it gates only on the files the
      smoke run wrote having the shapes metrics.py/report.py require. It is
      NOT a judgment-quality check (that is the human spot-check's job, via
      `scripts/check_spotcheck.py` against `spotcheck.yaml`).

      Marked `@pytest.mark.live` AND skipped unless `RUN_LIVE=1`, so a plain
      `pytest ci` (no env var) collects it but reports it SKIPPED, never runs
      it, and never spends money.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

REPO_ROOT = Path(__file__).resolve().parents[1]
_ARMS = ("baseline", "treatment")
_RUN_LIVE = os.environ.get("RUN_LIVE") == "1"


def _run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# (a) Cheap structural checks — no model calls.
# --------------------------------------------------------------------------- #
def test_moves_check():
    proc = _run_script("scripts/check_moves.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_artifact_lint():
    proc = _run_script("scripts/lint_artifacts.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_taskset_check():
    tasksets_dir = REPO_ROOT / "tasksets"
    taskset_dirs = sorted(
        p for p in tasksets_dir.iterdir()
        if p.is_dir() and (p / "manifest.yaml").is_file()
    )
    assert taskset_dirs, f"no tasksets with a manifest.yaml found under {tasksets_dir}"
    for d in taskset_dirs:
        proc = _run_script("scripts/check_taskset.py", str(d))
        assert proc.returncode == 0, f"{d.name}: {proc.stdout + proc.stderr}"


# --------------------------------------------------------------------------- #
# (b) Live smoke run + deepeval integrity gate.
# --------------------------------------------------------------------------- #
def _load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def _integrity_failures(results_dir: Path, n_items: int) -> list[str]:
    """Every reason `results_dir` is NOT a clean, complete smoke run.

    Empty list == clean. This function makes no model calls; it only reads
    the artifacts the pipeline already wrote to disk."""
    results_dir = Path(results_dir)
    failures: list[str] = []

    for name in ("report.md", "metrics.json", "spotcheck.yaml"):
        if not (results_dir / name).is_file():
            failures.append(f"missing {name}")
    for arm in _ARMS:
        if not (results_dir / f"promptfoo-{arm}.json").is_file():
            failures.append(f"missing promptfoo-{arm}.json")

    # calls/: exactly n_items per arm, each with nonzero output_tokens and a
    # valid arm label.
    for arm in _ARMS:
        paths = sorted((results_dir / "calls").glob(f"{arm}-*.json"))
        if len(paths) != n_items:
            failures.append(
                f"calls/: expected {n_items} '{arm}-*.json' file(s), found {len(paths)}"
            )
        for p in paths:
            try:
                rec = _load_json(p)
            except (OSError, json.JSONDecodeError) as e:
                failures.append(f"calls/{p.name}: unparseable ({e})")
                continue
            if rec.get("arm") != arm:
                failures.append(f"calls/{p.name}: arm={rec.get('arm')!r}, expected {arm!r}")
            out_tok = rec.get("output_tokens")
            if not isinstance(out_tok, int) or isinstance(out_tok, bool) or out_tok <= 0:
                failures.append(
                    f"calls/{p.name}: output_tokens must be a positive int, got {out_tok!r}"
                )

    # judge/: exactly n_items per arm, each with a binary item_pass and
    # judge_error: false (a judge_error anywhere means the run is not clean).
    for arm in _ARMS:
        paths = sorted((results_dir / "judge").glob(f"{arm}-*.json"))
        if len(paths) != n_items:
            failures.append(
                f"judge/: expected {n_items} '{arm}-*.json' file(s), found {len(paths)}"
            )
        for p in paths:
            try:
                rec = _load_json(p)
            except (OSError, json.JSONDecodeError) as e:
                failures.append(f"judge/{p.name}: unparseable ({e})")
                continue
            if not isinstance(rec.get("item_pass"), bool):
                failures.append(
                    f"judge/{p.name}: item_pass must be bool, got {rec.get('item_pass')!r}"
                )
            if rec.get("judge_error") is not False:
                failures.append(
                    f"judge/{p.name}: judge_error={rec.get('judge_error')!r}, expected False"
                )

    # metrics.json: parses and carries every step-6 metric concept.
    #
    # NOTE (see task-7-report.md): the brief lists the step-6 CONCEPTS by
    # their metrics.py FUNCTION names (pass_rate, delta, token_totals,
    # confusion, base_rate, adherence, paired_flips, flags, judge_errors).
    # report.py (Task 6, reviewed) actually serializes these per-arm under
    # different top-level keys (baseline_pass/treatment_pass, token_delta,
    # baseline_tokens/treatment_tokens, baseline_confusion/
    # treatment_confusion with base_rate nested inside, flips, adherence,
    # flags, judge_errors) because a single arm's pass rate/tokens/confusion
    # is meaningless without knowing which arm it is. This checks the REAL
    # keys that carry each concept in the schema Task 6 shipped, rather than
    # renaming a reviewed, tested module to match the brief's shorthand.
    metrics_path = results_dir / "metrics.json"
    if metrics_path.is_file():
        try:
            m = _load_json(metrics_path)
        except (OSError, json.JSONDecodeError) as e:
            failures.append(f"metrics.json: unparseable ({e})")
            m = {}
        required_keys_by_concept = {
            "pass_rate": ("baseline_pass", "treatment_pass"),
            "delta": ("token_delta",),
            "token_totals": ("baseline_tokens", "treatment_tokens"),
            "confusion": ("baseline_confusion", "treatment_confusion"),
            "adherence": ("adherence",),
            "paired_flips": ("flips",),
            "flags": ("flags",),
            "judge_errors": ("judge_errors",),
        }
        for concept, keys in required_keys_by_concept.items():
            for key in keys:
                if key not in m:
                    failures.append(f"metrics.json: missing key '{key}' (covers '{concept}')")
        for conf_key in ("baseline_confusion", "treatment_confusion"):
            conf = m.get(conf_key)
            if isinstance(conf, dict) and "base_rate" not in conf:
                failures.append(f"metrics.json: {conf_key}.base_rate missing (covers 'base_rate')")

    # report.md: CONTENT-level checks, not just presence. A file that exists
    # but is missing the provisional framing or the estimand would silently
    # ship a report nobody would recognize as unvalidated.
    report_path = results_dir / "report.md"
    if report_path.is_file():
        report_text = report_path.read_text()
        if "PROVISIONAL" not in report_text:
            failures.append("report.md: missing the PROVISIONAL banner")
        if "Estimand:" not in report_text:
            failures.append("report.md: missing the estimand line")
        if "### Deltas" not in report_text:
            failures.append("report.md: missing a Deltas section")

    # spotcheck.yaml: CONTENT-level check — it must parse to a non-empty
    # 'items' list, and every sampled item must carry the three keys a human
    # (or check_spotcheck.py) needs to record + join a spot-check verdict.
    spotcheck_path = results_dir / "spotcheck.yaml"
    if spotcheck_path.is_file():
        try:
            spot = yaml.safe_load(spotcheck_path.read_text()) or {}
        except yaml.YAMLError as e:
            failures.append(f"spotcheck.yaml: unparseable ({e})")
            spot = {}
        spot_items = spot.get("items") if isinstance(spot, dict) else None
        if not isinstance(spot_items, list) or not spot_items:
            failures.append("spotcheck.yaml: 'items' list missing or empty")
        else:
            for it in spot_items:
                missing = [k for k in ("task_id", "arm", "agree") if not isinstance(it, dict) or k not in it]
                if missing:
                    failures.append(f"spotcheck.yaml: item missing key(s) {missing}: {it!r}")

    return failures


class HarnessIntegrityMetric(BaseMetric):
    """Binary artifact-integrity gate over one smoke results dir.

    Deliberately NOT an LLM-backed metric — `measure` makes no model calls,
    it only checks that the smoke run wrote every artifact the pipeline
    promises, with the shapes downstream consumers (metrics.py, report.py,
    the human spot-check) require. Threshold 1.0: any single missing/
    malformed artifact fails the whole metric, because a partially-written
    run is not a smaller clean run — it is a broken one (see
    harness/run.py's own `_check_arm_integrity`, which this mirrors at the
    CI-gate level).
    """

    def __init__(self, results_dir, n_items: int, threshold: float = 1.0):
        self.results_dir = Path(results_dir)
        self.n_items = n_items
        self.threshold = threshold
        self.score = None
        self.reason = None
        self.success = None

    def measure(self, test_case, *args, **kwargs) -> float:
        failures = _integrity_failures(self.results_dir, self.n_items)
        self.score = 0.0 if failures else 1.0
        self.reason = "clean smoke run" if not failures else "; ".join(failures)
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "HarnessIntegrityMetric"


@pytest.mark.live
@pytest.mark.skipif(
    not _RUN_LIVE,
    reason="live smoke run makes real haiku + codex API calls (~$2); set RUN_LIVE=1 to run",
)
def test_smoke_run():
    from harness import config as config_mod

    cfg = config_mod.load("experiments/smoke.yaml")
    results_dir = cfg.results_dir()
    n_items = len(config_mod.load_taskset(cfg))

    # Fresh run every time: stale files from a previous attempt (different
    # n_items, a crashed partial run) must never be able to satisfy the
    # integrity metric by accident.
    shutil.rmtree(results_dir, ignore_errors=True)

    proc = subprocess.run(
        [sys.executable, "-m", "harness.run", "experiments/smoke.yaml"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    assert proc.returncode == 0, (
        f"harness.run experiments/smoke.yaml exited {proc.returncode} "
        f"(harness_broken=2, judge_error/integrity-failed=1, budget-abort=3) "
        f"— see captured stdout/stderr above for the harness's own diagnostic."
    )

    test_case = LLMTestCase(
        input="harness.run experiments/smoke.yaml — artifact integrity check",
        actual_output=str(results_dir),
    )
    assert_test(test_case, [HarnessIntegrityMetric(results_dir, n_items)])
