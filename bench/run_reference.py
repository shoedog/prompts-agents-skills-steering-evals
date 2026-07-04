#!/usr/bin/env python
"""Fable-5 reference-run harness.

Produces the "what does Fable-5 actually do on this exact real task" baseline
for the benchmark tasks nominated in `mining/out/nominations.md`, before
cheaper models get graded against it. Fable-5 leaves the owner's plan
2026-07-07 — this harness is the only way to capture that baseline first.

## Reference framing (read this before trusting a run)

The reference condition is **Fable-5 running in a fresh local clone of the
task's source repo, checked out at the pinned pre-task git tag, with
whatever repo scaffold already existed there** — CLAUDE.md, `.claude/`,
`.claude-plugin/`, AGENTS.md, whatever the repo actually tracked at that ref.
This harness injects NOTHING beyond that: no synthetic system prompt, no
extra CLAUDE.md, no MCP config. `git clone --local` + `git checkout <tag>`
naturally preserves every tracked file, so "the reference" is just Fable
plus the owner's real scaffold, exactly as it stood at the pre-task commit.

**Known asymmetry — read before comparing against the original session:**
Claude Code auto-discovers and loads `CLAUDE.md` / `.claude/` on startup, but
it does **not** auto-load `AGENTS.md`. The original nominated sessions ran
under `codex`, which auto-injects a repo's `AGENTS.md` as a synthetic first
user message before the real task prompt (verified directly in the source
transcripts during task-spec authoring). Several source repos (e.g.
`a2a-bridge`) carry an AGENTS.md-only scaffold with no CLAUDE.md/.claude/ at
all. For those tasks, this harness's Fable run gets systematically *less*
repo-specific priming than the original codex session received — not a bug
in this harness, just a real difference between the two CLIs' auto-context
behavior. Each run's `summary.json` records a `scaffold` block (which of
CLAUDE.md/.claude//AGENTS.md were tracked at the pinned ref and actually
landed on disk after checkout) so this is auditable per task rather than
silently assumed away.

## Per-task pipeline

For each task id in `--tasks`:
  (a) clone the task's `source_repo` (`git clone --local`) into a fresh
      workspace under `--workspace-root`, check out `pre_tag`, then
      `git remote remove origin` (no accidental push target exists).
  (b) verify + record which of CLAUDE.md/.claude//AGENTS.md were tracked at
      that ref and actually present on disk post-checkout (see framing
      above).
  (c) [skipped under --dry-run] run Fable headlessly in the workspace:
      `claude -p <task_prompt> --model claude-fable-5 --output-format json
      --dangerously-skip-permissions`, cwd = the workspace, a generous
      timeout (`--timeout-min`, default 75) and NO turn cap. The parsed CLI
      JSON (usage/cost/duration/result) is written to `run.json`.
  (d) capture `git diff` + `git status --short` to `changes.diff`, then run
      the task's `success_evidence` commands in the workspace and capture
      their output to `evidence.txt`. Under `--dry-run` these commands run
      against the UNTOUCHED pre-task tree — failures there are EXPECTED (the
      evidence commands assert the post-task state; the delta between their
      pre-state and post-state failure/pass IS the task).
  (e) locate the Claude Code session transcript this run created under
      `~/.claude/projects/` (the newest *.jsonl whose recorded `cwd` matches
      the workspace path) and copy it to `transcript.jsonl`.
  (f) write `summary.json`: id, workspace path, duration, usage tokens,
      total_cost_usd, a mechanical tests_passed guess (derived from the
      success_evidence exit codes), and the transcript path.

## Idempotence

A task refuses to run if `bench/out/<ID>/` already exists, unless `--force`
is given (which deletes and re-creates it). The workspace clone itself is
always wiped and re-cloned fresh on every invocation regardless of
`--force` — only the *output* directory is idempotence-guarded.

## Wave support

`--tasks IMPL-03,IMPL-04` runs both sequentially within this one process.
Parallelize across waves by launching two separate invocations (with
disjoint `--tasks` lists) rather than asking this script to fork internally.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.providers.binpath import resolve_executable  # noqa: E402

DEFAULT_TASKS_DIR = REPO_ROOT / "bench" / "tasks"
DEFAULT_OUT_DIR = REPO_ROOT / "bench" / "out"
DEFAULT_WORKSPACE_ROOT = Path("/private/tmp/fable-bench-ws")
DEFAULT_MODEL = "claude-fable-5"
DEFAULT_TIMEOUT_MIN = 75
DEFAULT_EVIDENCE_TIMEOUT_MIN = 25
DEFAULT_GIT_TIMEOUT_SEC = 300

REQUIRED_TASK_FIELDS = ("id", "source_repo", "pre_tag", "task_prompt", "success_evidence")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# task spec loading
# --------------------------------------------------------------------------

def load_task(tasks_dir: Path, task_id: str) -> dict:
    path = tasks_dir / f"{task_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"[bench] no task spec at {path}")
    with open(path) as f:
        task = yaml.safe_load(f)
    missing = [field for field in REQUIRED_TASK_FIELDS if field not in task]
    if missing:
        raise SystemExit(f"[bench] {path} missing required field(s): {missing}")
    if task["id"] != task_id:
        raise SystemExit(f"[bench] {path}: id field {task['id']!r} != filename {task_id!r}")
    return task


def discover_task_ids(tasks_dir: Path) -> list:
    return sorted(p.stem for p in tasks_dir.glob("*.yaml"))


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------

def git(args, check=True, timeout=DEFAULT_GIT_TIMEOUT_SEC):
    proc = subprocess.run(
        ["git"] + args, capture_output=True, text=True, timeout=timeout
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    return proc


def clone_and_checkout(source_repo: str, pre_tag: str, ws_dir: Path) -> None:
    if not Path(source_repo).exists():
        raise RuntimeError(f"source_repo does not exist: {source_repo}")
    if ws_dir.exists():
        print(f"[bench] removing existing workspace {ws_dir}", flush=True)
        shutil.rmtree(ws_dir)
    ws_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"[bench] git clone --local {source_repo} {ws_dir}", flush=True)
    git(["clone", "--local", source_repo, str(ws_dir)])
    print(f"[bench] git -C {ws_dir} checkout {pre_tag}", flush=True)
    git(["-C", str(ws_dir), "checkout", pre_tag])
    print(f"[bench] git -C {ws_dir} remote remove origin", flush=True)
    git(["-C", str(ws_dir), "remote", "remove", "origin"])


def check_scaffold(ws_dir: Path, pre_tag: str) -> dict:
    """Verify which of CLAUDE.md/.claude//.claude-plugin//AGENTS.md were
    tracked at `pre_tag` and confirm they actually landed on disk after
    checkout (a mismatch would indicate a broken clone/checkout, e.g. a
    sparse-checkout misconfiguration). See the module docstring's "Known
    asymmetry" section for why AGENTS.md-only repos matter here."""
    tracked = git(["-C", str(ws_dir), "ls-tree", "-r", "--name-only", pre_tag]).stdout.splitlines()
    scaffold_prefixes = (".claude/", ".claude-plugin/")
    scaffold_exact = ("CLAUDE.md", "AGENTS.md", ".claude", ".claude-plugin")
    scaffold_tracked = sorted(
        {p for p in tracked if p in scaffold_exact or p.startswith(scaffold_prefixes)}
    )
    missing_on_disk = [p for p in scaffold_tracked if not (ws_dir / p).exists()]
    has_claude_md = "CLAUDE.md" in scaffold_tracked
    has_dot_claude = any(p == ".claude" or p.startswith(".claude/") for p in scaffold_tracked)
    has_agents_md = "AGENTS.md" in scaffold_tracked

    if missing_on_disk:
        print(
            f"[bench] WARNING: scaffold path(s) tracked at {pre_tag} but MISSING on "
            f"disk after checkout (broken clone?): {missing_on_disk}",
            file=sys.stderr, flush=True,
        )
    agents_md_shimmed = False
    if has_agents_md and not (has_claude_md or has_dot_claude):
        # Equalize priming with the original codex session: codex auto-injects
        # AGENTS.md; Claude Code auto-loads CLAUDE.md. Copy (untracked, clone-only)
        # so the Fable reference gets the same repo scaffold the source run had.
        shutil.copyfile(ws_dir / "AGENTS.md", ws_dir / "CLAUDE.md")
        agents_md_shimmed = True
        print(
            "[bench] NOTE: AGENTS.md-only scaffold — copied AGENTS.md -> CLAUDE.md "
            "in the clone to equalize priming with the original codex session.",
            flush=True,
        )
    return {
        "tracked_scaffold_paths": scaffold_tracked,
        "missing_on_disk_after_checkout": missing_on_disk,
        "has_CLAUDE_md": has_claude_md,
        "has_dot_claude_dir": has_dot_claude,
        "has_AGENTS_md": has_agents_md,
        "agents_md_shimmed": agents_md_shimmed,
    }


# --------------------------------------------------------------------------
# headless Fable invocation
# --------------------------------------------------------------------------

def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_fable(task_prompt: str, model: str, ws_dir: Path, timeout_sec: int) -> dict:
    """Run one headless Fable turn in `ws_dir`. NO --max-turns cap — the
    real task may need an arbitrary number of tool-use turns; only a wall
    clock timeout bounds it. Returns a dict with `harness` (invocation
    metadata) and `cli_result` (the parsed --output-format json object, or
    None if the process timed out / produced unparseable stdout)."""
    claude_bin = resolve_executable("claude")
    argv = [
        claude_bin, "-p", task_prompt,
        "--model", model,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    started_at = utcnow_iso()
    t0 = time.time()
    proc = subprocess.Popen(
        argv, cwd=str(ws_dir),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        print(
            f"[bench] Fable invocation exceeded {timeout_sec}s — killing process group",
            file=sys.stderr, flush=True,
        )
        _kill_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
    wall_sec = time.time() - t0
    ended_at = utcnow_iso()

    cli_result = None
    parse_error = None
    if stdout:
        try:
            cli_result = json.loads(stdout)
        except json.JSONDecodeError as e:
            parse_error = str(e)

    return {
        "harness": {
            "argv_redacted": [
                claude_bin, "-p", "<task_prompt omitted here — see the task yaml>",
                "--model", model, "--output-format", "json",
                "--dangerously-skip-permissions",
            ],
            "cwd": str(ws_dir),
            "model": model,
            "timeout_sec": timeout_sec,
            "started_at": started_at,
            "ended_at": ended_at,
            "wall_sec": round(wall_sec, 3),
            "timed_out": timed_out,
            "returncode": proc.returncode,
        },
        "cli_result": cli_result,
        "stdout_tail": None if cli_result is not None else stdout[-20000:],
        "stderr_tail": stderr[-20000:] if stderr else "",
        "parse_error": parse_error,
    }


# --------------------------------------------------------------------------
# success_evidence execution
# --------------------------------------------------------------------------

def run_evidence(commands: list, ws_dir: Path, timeout_sec: int) -> list:
    results = []
    for item in commands:
        cmd = item["cmd"] if isinstance(item, dict) else item
        desc = item.get("desc", "") if isinstance(item, dict) else ""
        print(f"[bench] evidence: {cmd}", flush=True)
        t0 = time.time()
        try:
            argv = shlex.split(cmd)
            proc = subprocess.run(
                argv, cwd=str(ws_dir), capture_output=True, text=True, timeout=timeout_sec,
            )
            results.append({
                "cmd": cmd, "desc": desc,
                "returncode": proc.returncode, "timed_out": False,
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": proc.stdout[-8000:],
                "stderr_tail": proc.stderr[-8000:],
            })
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            err = e.stderr if isinstance(e.stderr, str) else ""
            results.append({
                "cmd": cmd, "desc": desc,
                "returncode": None, "timed_out": True,
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": out[-8000:], "stderr_tail": err[-8000:],
            })
        except FileNotFoundError as e:
            results.append({
                "cmd": cmd, "desc": desc,
                "returncode": None, "timed_out": False, "error": f"executable not found: {e}",
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": "", "stderr_tail": "",
            })
    return results


def render_evidence_txt(results: list, dry_run: bool) -> str:
    header = (
        "PRE-STATE evidence (--dry-run: the workspace is UNTOUCHED at the pre-task "
        "tag; failures below are EXPECTED and define the delta the real task must "
        "close, not a harness bug)"
        if dry_run else
        "POST-RUN evidence (workspace after the Fable session)"
    )
    lines = [header, "=" * len(header)]
    for r in results:
        lines.append("")
        lines.append(f"$ {r['cmd']}")
        if r.get("desc"):
            lines.append(f"  # {r['desc']}")
        if r.get("error"):
            lines.append(f"  ERROR: {r['error']}")
            continue
        status = "TIMED OUT" if r["timed_out"] else f"exit {r['returncode']}"
        lines.append(f"  [{status}, {r['wall_sec']}s]")
        if r["stdout_tail"].strip():
            lines.append("  --- stdout (tail) ---")
            lines.extend("  " + line for line in r["stdout_tail"].splitlines()[-80:])
        if r["stderr_tail"].strip():
            lines.append("  --- stderr (tail) ---")
            lines.extend("  " + line for line in r["stderr_tail"].splitlines()[-80:])
    return "\n".join(lines) + "\n"


def tests_passed_guess(evidence_results: list, dry_run: bool) -> str:
    if not evidence_results:
        return "unknown (task has no success_evidence commands)"
    if any(r.get("error") for r in evidence_results):
        return "fail (an evidence command could not even run)"
    if any(r["timed_out"] for r in evidence_results):
        return "fail (an evidence command timed out)"
    all_pass = all(r["returncode"] == 0 for r in evidence_results)
    if dry_run:
        # Pre-task state passing the post-task evidence would be a red flag
        # (the tests should not exist / should fail yet) — surface it as such.
        return "pass (SUSPICIOUS for a dry-run pre-state — see evidence.txt)" if all_pass else "fail (expected pre-implementation)"
    return "pass" if all_pass else "fail"


# --------------------------------------------------------------------------
# transcript location
# --------------------------------------------------------------------------

def find_transcript(ws_dir: Path, since_ts: float) -> Path | None:
    """Newest ~/.claude/projects/*/*.jsonl whose recorded `cwd` matches
    `ws_dir`, restricted to files modified at/after `since_ts` (a small
    buffer before the Fable invocation started) so this does not have to
    read the full content of all ~200 historical project transcripts."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.is_dir():
        return None
    needle = f'"cwd":"{ws_dir}"'.encode()
    candidates = []
    for p in projects_dir.glob("*/*.jsonl"):
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime < since_ts - 5:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if needle in data:
            candidates.append((st.st_mtime, p))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


# --------------------------------------------------------------------------
# per-task pipeline
# --------------------------------------------------------------------------

def run_task(task_id: str, args: argparse.Namespace) -> int:
    task = load_task(args.tasks_dir, task_id)
    out_dir = args.out_dir / task_id

    if out_dir.exists():
        if not args.force:
            print(
                f"[bench] REFUSING: {out_dir} already exists (a previous run's "
                f"output). Pass --force to overwrite.",
                file=sys.stderr, flush=True,
            )
            return 4
        print(f"[bench] --force: removing existing {out_dir}", flush=True)
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    ws_dir = args.workspace_root / task_id
    print(f"\n[bench] === {task_id} === ws={ws_dir} dry_run={args.dry_run} model={args.model}",
          flush=True)

    try:
        clone_and_checkout(task["source_repo"], task["pre_tag"], ws_dir)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"[bench] {task_id}: FAILED during clone/checkout: {e}", file=sys.stderr, flush=True)
        (out_dir / "summary.json").write_text(json.dumps(
            {"id": task_id, "error": f"clone/checkout failed: {e}"}, indent=2))
        return 5

    scaffold = check_scaffold(ws_dir, task["pre_tag"])

    since_ts = time.time()
    if args.dry_run:
        run_record = {
            "dry_run": True,
            "harness": {
                "task_id": task_id, "model": args.model, "cwd": str(ws_dir),
                "timeout_sec": args.timeout_min * 60,
            },
            "cli_result": None,
            "note": "Fable invocation SKIPPED (--dry-run). This stub documents what would have run; steps (d)/(e)/(f) still ran against the untouched pre-task workspace.",
        }
    else:
        run_record = run_fable(task["task_prompt"], args.model, ws_dir, args.timeout_min * 60)

    (out_dir / "run.json").write_text(json.dumps(run_record, indent=2, default=str))

    diff_proc = git(["-C", str(ws_dir), "diff"], check=False)
    status_proc = git(["-C", str(ws_dir), "status", "--short"], check=False)
    changes_text = (
        f"# git -C {ws_dir} status --short\n{status_proc.stdout}\n"
        f"# git -C {ws_dir} diff\n{diff_proc.stdout}\n"
    )
    (out_dir / "changes.diff").write_text(changes_text)

    evidence_results = run_evidence(
        task["success_evidence"], ws_dir, args.evidence_timeout_min * 60
    )
    (out_dir / "evidence.txt").write_text(render_evidence_txt(evidence_results, args.dry_run))

    transcript_path = None
    if not args.dry_run:
        found = find_transcript(ws_dir, since_ts)
        if found:
            transcript_path = out_dir / "transcript.jsonl"
            shutil.copy2(found, transcript_path)
            print(f"[bench] transcript: {found} -> {transcript_path}", flush=True)
        else:
            print(
                f"[bench] WARNING: no session transcript found under ~/.claude/projects "
                f"matching cwd={ws_dir}",
                file=sys.stderr, flush=True,
            )

    guess = tests_passed_guess(evidence_results, args.dry_run)
    cli_result = (run_record.get("cli_result") or {})
    summary = {
        "id": task_id,
        "ws": str(ws_dir),
        "dry_run": args.dry_run,
        "model": args.model,
        "duration_ms": cli_result.get("duration_ms"),
        "num_turns": cli_result.get("num_turns"),
        "usage": cli_result.get("usage"),
        "total_cost_usd": cli_result.get("total_cost_usd"),
        "stop_reason": cli_result.get("stop_reason"),
        "is_error": cli_result.get("is_error"),
        "result_text": cli_result.get("result"),
        "timed_out": run_record.get("harness", {}).get("timed_out", False),
        "tests_passed_guess": guess,
        "evidence_summary": [
            {"cmd": r["cmd"], "returncode": r.get("returncode"), "timed_out": r.get("timed_out")}
            for r in evidence_results
        ],
        "scaffold": scaffold,
        "transcript_path": str(transcript_path) if transcript_path else None,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(
        f"[bench] {task_id}: dry_run={args.dry_run} tests_passed_guess={guess!r} "
        f"cost=${summary['total_cost_usd']} out={out_dir}",
        flush=True,
    )
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bench.run_reference",
        description=__doc__.split("\n\n", 1)[0],
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--tasks", required=True,
        help="comma-separated task ids (e.g. IMPL-03,IMPL-04), or the literal "
             "word 'all' to run every *.yaml in --tasks-dir.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="do everything except invoke Fable (step c): clone+checkout, scaffold "
             "check, diff/status capture, and run success_evidence against the "
             "UNTOUCHED pre-task tree (pre-state evidence — failures expected).",
    )
    p.add_argument(
        "--force", action="store_true",
        help="overwrite an existing bench/out/<ID>/ instead of refusing to run.",
    )
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"model passed to `claude --model` (default: {DEFAULT_MODEL}). Override "
             f"for testing the harness itself with a cheaper model; the real "
             f"reference wave must use {DEFAULT_MODEL}.",
    )
    p.add_argument(
        "--timeout-min", type=float, default=DEFAULT_TIMEOUT_MIN,
        help=f"wall-clock timeout in minutes for the headless Fable invocation "
             f"(default: {DEFAULT_TIMEOUT_MIN}). No --max-turns cap is ever passed.",
    )
    p.add_argument(
        "--evidence-timeout-min", type=float, default=DEFAULT_EVIDENCE_TIMEOUT_MIN,
        help=f"per-command timeout in minutes for success_evidence commands "
             f"(default: {DEFAULT_EVIDENCE_TIMEOUT_MIN}; cargo workspace builds can "
             f"be slow).",
    )
    p.add_argument(
        "--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT,
        help=f"parent dir for per-task clone workspaces (default: {DEFAULT_WORKSPACE_ROOT}). "
             f"Each task gets <workspace-root>/<ID>, wiped and re-cloned fresh every run.",
    )
    p.add_argument(
        "--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR,
        help=f"directory of <ID>.yaml task specs (default: {DEFAULT_TASKS_DIR}).",
    )
    p.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help=f"directory to write bench/out/<ID>/ into (default: {DEFAULT_OUT_DIR}).",
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.tasks.strip().lower() == "all":
        task_ids = discover_task_ids(args.tasks_dir)
    else:
        task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]

    if not task_ids:
        print("[bench] no task ids given", file=sys.stderr, flush=True)
        return 2

    print(f"[bench] running {len(task_ids)} task(s): {task_ids}", flush=True)
    worst = 0
    failed = []
    for task_id in task_ids:
        # A crash on one task (bad yaml, a git/subprocess surprise, an
        # unhandled exception in evidence/transcript handling, ...) must not
        # take down the rest of a multi-task wave — log it, mark this task
        # failed, and move on to the next id.
        try:
            code = run_task(task_id, args)
        except Exception:
            import traceback
            traceback.print_exc()
            print(f"[bench] {task_id}: CRASHED (see traceback above)", file=sys.stderr, flush=True)
            code = 6
        if code != 0:
            failed.append(task_id)
        worst = max(worst, code)
    if failed:
        print(f"[bench] {len(failed)}/{len(task_ids)} task(s) did not complete cleanly: {failed}",
              file=sys.stderr, flush=True)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
