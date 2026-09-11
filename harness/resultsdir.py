"""Results-dir contamination guards.

Extracted verbatim from `harness/run.py` (PR-2 of the eval-harness
generalization, see `specs/2026-09-04-eval-harness-generalization-spec.md`
§3 "Results-dir guards" and §12 row 2): these four functions are the only
part of the review-ablation runner that is genuinely generic across "arm"
(two-arm review ablation) and "version" (N-version structured/analyzer/
pipeline runs) result layouts — both share the same `<results_dir>/{calls,
judge}/<key>-<item_id>.json` naming convention and the same two failure
modes (a stale leftover file from a prior run sharing the dir; a run that
did not produce the full expected id set). `harness/structured/run.py`
imports this module directly; `harness/run.py` re-exports the same names
under their original private spelling so `harness/tests/test_run.py`
continues to import `_check_arm_integrity` / `_check_stale_results_dir`
from `harness.run` unmodified.

No behavior change from the pre-extraction code: bodies are moved
unchanged, only the module and the public (no leading underscore) names
are new.
"""
from __future__ import annotations

import glob
import os
import shutil
import sys
from pathlib import Path


def arm_ids_on_disk(results_dir, subdir, arm) -> set:
    """Task ids actually on disk for one arm under `subdir`, parsed back out of
    the `<arm>-<task_id>.json` filenames promptfoo/the assert write per item."""
    prefix = f"{arm}-"
    ids = set()
    for p in glob.glob(os.path.join(str(results_dir), subdir, f"{prefix}*.json")):
        name = os.path.basename(p)
        ids.add(name[len(prefix):-len(".json")])
    return ids


def check_arm_integrity(results_dir, arm, expected_ids) -> bool:
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
        got = arm_ids_on_disk(results_dir, subdir, arm)
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


def stale_result_files(results_dir) -> list:
    """Per-item calls/ and judge/ json files already sitting in `results_dir`
    before this run starts — leftovers from a previous run over this exact
    tier results dir."""
    out = []
    for subdir in ("calls", "judge"):
        out.extend(
            sorted(glob.glob(os.path.join(str(results_dir), subdir, "*.json")))
        )
    return out


def check_stale_results_dir(results_dir, force: bool) -> bool:
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
    stale = stale_result_files(results_dir)
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


_STRUCTURED_RESULT_DIRS = ("calls", "stages", "asserts", "inputs")
_STRUCTURED_RESULT_FILES = (
    "replay.jsonl",
    "trace.jsonl",
    "run.json",
    "metrics.json",
    "report.md",
)


def structured_stale_files(results_dir: Path) -> list[Path]:
    """Return existing artifacts owned by one structured-eval results tree."""
    results_dir = Path(results_dir)
    stale: list[Path] = []
    for name in _STRUCTURED_RESULT_DIRS:
        directory = results_dir / name
        if directory.is_symlink() or directory.is_file():
            stale.append(directory)
        elif directory.is_dir():
            stale.extend(
                path
                for path in directory.rglob("*")
                if path.is_file() or path.is_symlink()
            )
    for name in _STRUCTURED_RESULT_FILES:
        path = results_dir / name
        if path.exists() or path.is_symlink():
            stale.append(path)
    return sorted(stale)


def check_structured_stale_results_dir(results_dir: Path, force: bool) -> bool:
    """Refuse stale structured results, or remove only owned artifacts with force."""
    results_dir = Path(results_dir)
    stale = structured_stale_files(results_dir)
    if not stale:
        return True
    if not force:
        print(
            f"[structured] REFUSING to run: {len(stale)} stale result artifact(s) "
            f"already exist under {results_dir}. Re-run with --force to clear only "
            "the structured results layout.",
            file=sys.stderr,
            flush=True,
        )
        return False
    print(
        f"[structured] --force: clearing {len(stale)} stale result artifact(s) "
        f"under {results_dir}.",
        flush=True,
    )
    for path in reversed(stale):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    return True
