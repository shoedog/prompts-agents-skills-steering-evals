#!/usr/bin/env python
"""Fable-5 reference-run harness.

Produces the "what does Fable-5 actually do on this exact real task" baseline
for the benchmark tasks nominated in `mining/out/nominations.md`, before
cheaper models get graded against it. Fable-5 leaves the owner's plan
2026-07-07 — this harness is the only way to capture that baseline first.

## Reference framing (read this before trusting a run)

The reference condition is **Fable-5 running in a fresh local clone of the
task's source repo, checked out at the pinned pre-task git tag, with the
owner's normal Claude environment still active**. That means tracked repo
scaffold (CLAUDE.md, `.claude/`, `.claude-plugin/`, AGENTS.md, whatever the
repo actually tracked at that ref) plus the owner's global SessionStart hooks.
Those global hooks are intentional: this benchmark asks what Fable does as the
owner really uses it, not under an isolated synthetic config. Each run's
`summary.json` records this as `scaffold.global_hooks_present`.

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
      above). AGENTS.md-only repos get an untracked CLAUDE.md shim, excluded
      as a harness artifact and hashed before/after the run.
  (c) [skipped under --dry-run] run Fable headlessly in the workspace:
      `claude -p <replay_preface + task_prompt> --model claude-fable-5 --output-format json
      --dangerously-skip-permissions`, cwd = the workspace, a generous
      timeout (`--timeout-min`, default 75) and NO turn cap. The parsed CLI
      JSON (usage/cost/duration/result) is written to `run.json`.
  (d) capture `git diff` + `git status --short` to `changes.diff`, then run
      the task's `success_evidence` commands in the workspace and capture
      their output to `evidence.txt`. Under `--dry-run` these commands run
      against the UNTOUCHED pre-task tree — failures there are EXPECTED (the
      evidence commands assert the post-task state; the delta between their
      pre-state and post-state failure/pass IS the task).
  (e) locate the Claude Code session transcript by the CLI JSON `session_id`,
      verify the first JSONL line's `sessionId`, wait for size/mtime
      stability, and copy it to `transcript.jsonl`.
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
import hashlib
import json
import os
import re
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
REPLAY_PREFACE_TEMPLATE = (
    "Replay note: you are working in {ws} (an isolated clone). Treat this directory as the "
    "repository root; ignore any absolute paths or branch names mentioned below — the task "
    "content is otherwise unchanged."
)
CARGO_PASSED_RE = re.compile(r"\btest result:.*?\b(\d+)\s+passed\b")
PYTEST_PASSED_RE = re.compile(r"(?:^|[=\s])(\d+)\s+passed(?:\b|[,=\s])")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    try:
        git(["clone", "--local", source_repo, str(ws_dir)])
    except RuntimeError as e:
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
        print(
            f"[bench] git clone --local failed ({e}); retrying with --no-hardlinks",
            file=sys.stderr, flush=True,
        )
        git(["clone", "--no-hardlinks", source_repo, str(ws_dir)])
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
    shim = {
        "present": False,
        "sha256_at_write": None,
    }
    if has_agents_md and not (has_claude_md or has_dot_claude):
        # Equalize priming with the original codex session: codex auto-injects
        # AGENTS.md; Claude Code auto-loads CLAUDE.md. Copy (untracked, clone-only)
        # so the Fable reference gets the same repo scaffold the source run had.
        shim_path = ws_dir / "CLAUDE.md"
        shutil.copyfile(ws_dir / "AGENTS.md", shim_path)
        exclude_path = ws_dir / ".git" / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        exclude_text = exclude_path.read_text() if exclude_path.exists() else ""
        if "CLAUDE.md" not in exclude_text.splitlines():
            with open(exclude_path, "a") as f:
                if exclude_text and not exclude_text.endswith("\n"):
                    f.write("\n")
                f.write("CLAUDE.md\n")
        agents_md_shimmed = True
        shim = {
            "present": True,
            "sha256_at_write": sha256_file(shim_path),
        }
        print(
            "[bench] NOTE: AGENTS.md-only scaffold — copied AGENTS.md -> CLAUDE.md "
            "in the clone to equalize priming with the original codex session "
            "and excluded it as a harness artifact.",
            flush=True,
        )
    return {
        "tracked_scaffold_paths": scaffold_tracked,
        "missing_on_disk_after_checkout": missing_on_disk,
        "has_CLAUDE_md": has_claude_md,
        "has_dot_claude_dir": has_dot_claude,
        "has_AGENTS_md": has_agents_md,
        "agents_md_shimmed": agents_md_shimmed,
        # Global SessionStart hook injection is the intended owner-reference condition.
        "global_hooks_present": True,
        "shim": shim,
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


def inject_tree(src_dir: Path, ws_dir: Path) -> dict:
    """Copy a treatment tree (e.g. .claude/ hook config) into the workspace and
    exclude every injected path from git (same mechanism as the CLAUDE.md
    shim) so evidence/status capture stays clean."""
    injected = []
    for p in sorted(src_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src_dir)
        dst = ws_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
        dst.chmod(p.stat().st_mode)
        injected.append(str(rel))
    exclude = ws_dir / ".git" / "info" / "exclude"
    with open(exclude, "a") as f:
        for rel in injected:
            f.write(f"/{rel}\n")
    print(f"[bench] injected {len(injected)} treatment file(s) from {src_dir}", flush=True)
    return {"from": str(src_dir), "files": injected}


def run_codex_impl(task_prompt: str, effort: str, ws_dir: Path, timeout_sec: int) -> dict:
    """Run one headless `codex exec` turn in `ws_dir` (workspace-write sandbox)
    and return a run_record shaped like run_fable()'s, so the summary code
    downstream works unchanged. Cost is not reported by the codex CLI (plan
    billing); tokens_used is parsed best-effort from its output."""
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise RuntimeError("codex CLI not found on PATH")
    out_file = ws_dir / ".codex-final-message.md"
    argv = [
        codex_bin, "exec",
        "--sandbox", "workspace-write",
        "-c", f'model_reasoning_effort="{effort}"',
        "-o", str(out_file), "-",
    ]
    started_at = utcnow_iso()
    t0 = time.time()
    timed_out = False
    proc = subprocess.Popen(
        argv, cwd=str(ws_dir), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(input=task_prompt, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        print(f"[bench] codex invocation exceeded {timeout_sec}s — killing process group",
              file=sys.stderr, flush=True)
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        stdout, stderr = proc.communicate(timeout=15)
    duration_ms = int((time.time() - t0) * 1000)
    tokens_used = None
    m = re.search(r"tokens used[:\s]+([\d,]+)", stdout + "\n" + stderr, re.IGNORECASE)
    if m:
        tokens_used = int(m.group(1).replace(",", ""))
    final_text = out_file.read_text() if out_file.exists() else None
    if out_file.exists():
        out_file.unlink()  # keep the workspace clean for status/diff capture
    cli_result = {
        "subtype": "success" if proc.returncode == 0 and not timed_out else "error",
        "is_error": proc.returncode != 0 or timed_out,
        "num_turns": None,
        "usage": {"tokens_used": tokens_used},
        "total_cost_usd": None,
        "result": final_text,
        "session_id": None,  # codex rollouts are matched by cwd+mtime downstream
        "duration_ms": duration_ms,
    }
    return {
        "harness": {
            "executor": "codex", "effort": effort, "cwd": str(ws_dir),
            "argv": argv, "started_at": started_at,
            "returncode": proc.returncode, "timed_out": timed_out,
            "timeout_sec": timeout_sec,
            "stderr_tail": (stderr or "")[-4000:],
        },
        "cli_result": cli_result,
    }


def find_codex_rollout(ws_dir: Path, since_ts: float):
    """Find the codex rollout JSONL whose session_meta cwd == ws_dir, written
    after since_ts. Returns (path|None, note)."""
    root = Path.home() / ".codex" / "sessions"
    candidates = []
    for p in root.rglob("rollout-*.jsonl"):
        try:
            if p.stat().st_mtime < since_ts - 5:
                continue
            with open(p) as f:
                head = f.readline()
            meta = json.loads(head)
            cwd = (meta.get("payload") or {}).get("cwd") or ""
            if cwd == str(ws_dir):
                candidates.append(p)
        except (OSError, json.JSONDecodeError):
            continue
    if not candidates:
        return None, f"no codex rollout with cwd={ws_dir} newer than since_ts"
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return newest, f"matched codex rollout by cwd ({len(candidates)} candidate(s))"


def build_replay_preface(ws_dir: Path) -> str:
    return REPLAY_PREFACE_TEMPLATE.format(ws=str(ws_dir))


# --------------------------------------------------------------------------
# success_evidence execution
# --------------------------------------------------------------------------

def count_passed_tests(stdout: str, stderr: str) -> int:
    total = 0
    for line in (stdout + "\n" + stderr).splitlines():
        cargo_match = CARGO_PASSED_RE.search(line)
        if cargo_match:
            total += int(cargo_match.group(1))
            continue
        pytest_match = PYTEST_PASSED_RE.search(line)
        if pytest_match:
            total += int(pytest_match.group(1))
    return total


def annotate_evidence_min_tests(result: dict, full_stdout: str = None, full_stderr: str = None) -> dict:
    # Count from the FULL streams when provided — the stored *_tail fields are
    # truncated to 8000 chars, which undercounts large cargo suites (a 2494-test
    # slicing run counted as 216 from the tail alone; observed on REF-03).
    expect_min_tests = result.get("expect_min_tests")
    if expect_min_tests is None:
        return result
    matched_tests = count_passed_tests(
        full_stdout if full_stdout is not None else result.get("stdout_tail", ""),
        full_stderr if full_stderr is not None else result.get("stderr_tail", ""),
    )
    result["matched_tests"] = matched_tests
    result["min_tests_satisfied"] = matched_tests >= expect_min_tests
    if not result["min_tests_satisfied"]:
        result["min_tests_failure"] = (
            f"matched {matched_tests} passed test(s), expected at least {expect_min_tests}"
        )
    return result


def evidence_entry_passed(result: dict) -> bool:
    if result.get("error") or result.get("timed_out"):
        return False
    if result.get("returncode") != 0:
        return False
    if result.get("expect_min_tests") is not None and not result.get("min_tests_satisfied", False):
        return False
    return True


def run_evidence(commands: list, ws_dir: Path, timeout_sec: int) -> list:
    results = []
    for item in commands:
        cmd = item["cmd"] if isinstance(item, dict) else item
        desc = item.get("desc", "") if isinstance(item, dict) else ""
        expect_min_tests = item.get("expect_min_tests") if isinstance(item, dict) else None
        print(f"[bench] evidence: {cmd}", flush=True)
        t0 = time.time()
        try:
            argv = shlex.split(cmd)
            proc = subprocess.run(
                argv, cwd=str(ws_dir), capture_output=True, text=True, timeout=timeout_sec,
            )
            results.append(annotate_evidence_min_tests({
                "cmd": cmd, "desc": desc,
                "expect_min_tests": expect_min_tests,
                "returncode": proc.returncode, "timed_out": False,
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": proc.stdout[-8000:],
                "stderr_tail": proc.stderr[-8000:],
            }, full_stdout=proc.stdout, full_stderr=proc.stderr))
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else ""
            err = e.stderr if isinstance(e.stderr, str) else ""
            results.append(annotate_evidence_min_tests({
                "cmd": cmd, "desc": desc,
                "expect_min_tests": expect_min_tests,
                "returncode": None, "timed_out": True,
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": out[-8000:], "stderr_tail": err[-8000:],
            }))
        except FileNotFoundError as e:
            results.append(annotate_evidence_min_tests({
                "cmd": cmd, "desc": desc,
                "expect_min_tests": expect_min_tests,
                "returncode": None, "timed_out": False, "error": f"executable not found: {e}",
                "wall_sec": round(time.time() - t0, 3),
                "stdout_tail": "", "stderr_tail": "",
            }))
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
        if r.get("expect_min_tests") is not None:
            lines.append(
                f"  # expect_min_tests={r['expect_min_tests']} "
                f"matched_tests={r.get('matched_tests', 0)} "
                f"min_tests_satisfied={r.get('min_tests_satisfied', False)}"
            )
        if r.get("min_tests_failure"):
            lines.append(f"  MIN-TESTS FAILED: {r['min_tests_failure']}")
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
    all_pass = all(evidence_entry_passed(r) for r in evidence_results)
    if dry_run:
        # Pre-task state passing the post-task evidence would be a red flag
        # (the tests should not exist / should fail yet) — surface it as such.
        return "pass (SUSPICIOUS for a dry-run pre-state — see evidence.txt)" if all_pass else "fail (expected pre-implementation)"
    return "pass" if all_pass else "fail"


# --------------------------------------------------------------------------
# transcript location
# --------------------------------------------------------------------------

def encoded_claude_project_dir(ws_dir: Path) -> str:
    return str(ws_dir).replace("/", "-")


def wait_for_stable_file(path: Path, checks: int = 2, interval_sec: int = 3) -> bool:
    stable = 0
    previous = None
    while stable < checks:
        try:
            st = path.stat()
        except OSError:
            return False
        current = (st.st_size, st.st_mtime_ns)
        if current == previous:
            stable += 1
        else:
            stable = 0
            previous = current
        if stable < checks:
            time.sleep(interval_sec)
    return True


def first_line_session_id(path: Path) -> str | None:
    try:
        with open(path) as f:
            first = f.readline()
    except OSError:
        return None
    if not first:
        return None
    try:
        obj = json.loads(first)
    except json.JSONDecodeError:
        return None
    return obj.get("sessionId")


def find_transcript_by_cwd(ws_dir: Path, since_ts: float) -> Path | None:
    """Diagnostic fallback: newest ~/.claude/projects/*/*.jsonl whose recorded
    `cwd` matches `ws_dir`, restricted to files modified at/after `since_ts`.
    Live copying is keyed by session_id; this heuristic is logged only when
    the exact session path is missing/invalid."""
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


def find_transcript_by_session(ws_dir: Path, session_id: str, since_ts: float) -> tuple[Path | None, str | None]:
    projects_dir = Path.home() / ".claude" / "projects"
    transcript = projects_dir / encoded_claude_project_dir(ws_dir) / f"{session_id}.jsonl"
    if not transcript.is_file():
        fallback = find_transcript_by_cwd(ws_dir, since_ts)
        return None, f"expected {transcript}; cwd fallback candidate={fallback}"
    observed_session_id = first_line_session_id(transcript)
    if observed_session_id != session_id:
        fallback = find_transcript_by_cwd(ws_dir, since_ts)
        return (
            None,
            f"expected first-line sessionId={session_id}, got {observed_session_id!r} "
            f"at {transcript}; cwd fallback candidate={fallback}",
        )
    if not wait_for_stable_file(transcript):
        fallback = find_transcript_by_cwd(ws_dir, since_ts)
        return None, f"transcript did not stabilize at {transcript}; cwd fallback candidate={fallback}"
    return transcript, None


# --------------------------------------------------------------------------
# run classification and source-repo guard
# --------------------------------------------------------------------------

def source_repo_status(source_repo: str) -> dict:
    proc = git(["-C", source_repo, "status", "--porcelain"], check=False)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def render_source_repo_guard(source_repo: str, before: dict, after: dict) -> str:
    return "\n".join([
        f"# source_repo: {source_repo}",
        "# before: git -C <source_repo> status --porcelain",
        before.get("stdout", ""),
        f"# before_returncode: {before.get('returncode')}",
        before.get("stderr", ""),
        "# after: git -C <source_repo> status --porcelain",
        after.get("stdout", ""),
        f"# after_returncode: {after.get('returncode')}",
        after.get("stderr", ""),
    ]).rstrip() + "\n"


def source_repo_touched(before: dict, after: dict) -> bool:
    return (
        before.get("returncode") != after.get("returncode")
        or before.get("stdout") != after.get("stdout")
        or before.get("stderr") != after.get("stderr")
    )


def classify_run(run_record: dict, transcript_missing: bool) -> str:
    harness = run_record.get("harness", {})
    cli_result = run_record.get("cli_result") or {}
    if harness.get("timed_out"):
        return "timeout"
    if run_record.get("parse_error"):
        return "parse_error"
    if harness.get("returncode") not in (0, None):
        return "nonzero_exit"
    if cli_result.get("is_error") or cli_result.get("subtype") in {"api_error", "error"}:
        return "api_error"
    if transcript_missing:
        return "transcript_missing"
    return "ok"


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

    source_before = source_repo_status(task["source_repo"])

    try:
        clone_and_checkout(task["source_repo"], task["pre_tag"], ws_dir)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"[bench] {task_id}: FAILED during clone/checkout: {e}", file=sys.stderr, flush=True)
        (out_dir / "summary.json").write_text(json.dumps(
            {"id": task_id, "error": f"clone/checkout failed: {e}"}, indent=2))
        return 5

    scaffold = check_scaffold(ws_dir, task["pre_tag"])
    if args.inject_dir:
        scaffold["injected"] = inject_tree(args.inject_dir, ws_dir)
    replay_preface = build_replay_preface(ws_dir)
    replay_prompt = f"{replay_preface}\n\n{task['task_prompt']}"

    since_ts = time.time()
    if args.dry_run:
        run_record = {
            "dry_run": True,
            "replay_preface": replay_preface,
            "harness": {
                "task_id": task_id, "model": args.model, "cwd": str(ws_dir),
                "timeout_sec": args.timeout_min * 60,
            },
            "cli_result": None,
            "note": "Fable invocation SKIPPED (--dry-run). This stub documents what would have run; steps (d)/(e)/(f) still ran against the untouched pre-task workspace.",
        }
    elif args.executor == "codex":
        run_record = run_codex_impl(replay_prompt, args.codex_effort, ws_dir, args.timeout_min * 60)
        run_record["replay_preface"] = replay_preface
    else:
        run_record = run_fable(replay_prompt, args.model, ws_dir, args.timeout_min * 60)
        run_record["replay_preface"] = replay_preface

    (out_dir / "run.json").write_text(json.dumps(run_record, indent=2, default=str))

    source_after = source_repo_status(task["source_repo"])
    (out_dir / "source_repo_guard.txt").write_text(
        render_source_repo_guard(task["source_repo"], source_before, source_after)
    )

    shim_info = dict(scaffold.get("shim", {}))
    shim_after_hash = sha256_file(ws_dir / "CLAUDE.md") if shim_info.get("present") else None
    shim_info["sha256_after_run"] = shim_after_hash
    shim_info["changed"] = (
        bool(shim_info.get("present"))
        and shim_info.get("sha256_at_write") != shim_after_hash
    )
    scaffold["shim"] = shim_info

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
    transcript_missing = False
    transcript_lookup_note = None
    if not args.dry_run:
        if args.executor == "codex":
            found, transcript_lookup_note = find_codex_rollout(ws_dir, since_ts)
        else:
            session_id = (run_record.get("cli_result") or {}).get("session_id")
            if session_id:
                found, transcript_lookup_note = find_transcript_by_session(ws_dir, session_id, since_ts)
            else:
                found = None
                transcript_lookup_note = "cli_result.session_id was absent"
        if found:
            transcript_path = out_dir / "transcript.jsonl"
            shutil.copy2(found, transcript_path)
            print(f"[bench] transcript: {found} -> {transcript_path}", flush=True)
        else:
            transcript_missing = True
            print(
                f"[bench] ERROR: no verified session transcript found for cwd={ws_dir}; "
                f"{transcript_lookup_note}",
                file=sys.stderr, flush=True,
            )

    guess = tests_passed_guess(evidence_results, args.dry_run)
    cli_result = (run_record.get("cli_result") or {})
    harness = run_record.get("harness", {})
    run_status = classify_run(run_record, transcript_missing)
    summary = {
        "id": task_id,
        "ws": str(ws_dir),
        "dry_run": args.dry_run,
        "model": args.model,
        "replay_preface": replay_preface,
        "run_status": run_status,
        "subtype": cli_result.get("subtype"),
        "api_error_status": cli_result.get("api_error_status"),
        "returncode": harness.get("returncode"),
        "session_id": cli_result.get("session_id"),
        "duration_ms": cli_result.get("duration_ms"),
        "num_turns": cli_result.get("num_turns"),
        "usage": cli_result.get("usage"),
        "total_cost_usd": cli_result.get("total_cost_usd"),
        "stop_reason": cli_result.get("stop_reason"),
        "is_error": cli_result.get("is_error"),
        "result_text": cli_result.get("result"),
        "timed_out": harness.get("timed_out", False),
        "parse_error": run_record.get("parse_error"),
        "terminal_reason": cli_result.get("terminal_reason"),
        "tests_passed_guess": guess,
        "evidence_summary": [
            {
                "cmd": r["cmd"],
                "returncode": r.get("returncode"),
                "timed_out": r.get("timed_out"),
                "expect_min_tests": r.get("expect_min_tests"),
                "matched_tests": r.get("matched_tests"),
                "min_tests_satisfied": r.get("min_tests_satisfied"),
            }
            for r in evidence_results
        ],
        "scaffold": scaffold,
        "shim": {
            "present": shim_info.get("present", False),
            "changed": shim_info.get("changed", False),
            "sha256_at_write": shim_info.get("sha256_at_write"),
            "sha256_after_run": shim_info.get("sha256_after_run"),
        },
        "source_repo_touched": source_repo_touched(source_before, source_after),
        "transcript_lookup_note": transcript_lookup_note,
        "transcript_path": str(transcript_path) if transcript_path else None,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print(
        f"[bench] {task_id}: dry_run={args.dry_run} tests_passed_guess={guess!r} "
        f"cost=${summary['total_cost_usd']} out={out_dir}",
        flush=True,
    )
    if run_status == "transcript_missing":
        return 7
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
        "--executor", choices=["claude", "codex"], default="claude",
        help="CLI executor. 'codex' runs `codex exec` (workspace-write sandbox, "
             "gpt-5.5); --model is ignored, --codex-effort applies.",
    )
    p.add_argument(
        "--codex-effort", default="high",
        help="model_reasoning_effort for --executor codex (default: high).",
    )
    p.add_argument(
        "--inject-dir", type=Path, default=None,
        help="copy this tree into each workspace after clone (git-excluded), "
             "e.g. a .claude/ hook-config treatment.",
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
