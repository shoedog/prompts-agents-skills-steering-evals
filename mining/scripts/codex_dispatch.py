#!/usr/bin/env python3
"""codex_dispatch: run `codex exec` and never let a dead run pass as "no
findings" (weekly-triage sign-off item 1, owner-approved 2026-08-08; corrects
the queued Wave-2 blind auto-respawn design).

Motivating incidents:
  rollout-2026-08-05T19-31 L11983 -- OAuth refresh death after 5.2h:
    task_complete{last_agent_message: null, error.codex_error_info:
    "unauthorized"}. A blind respawn would have re-burned the run.
  rollout-2026-07-24T01-54 L11-12 -- credit exhaustion: task_complete with NO
    error field; the signal is the preceding token_count event's
    rate_limits.credits.has_credits == false.

Behavior:
  1. Preflight: `codex login status` must succeed before anything launches;
     refusal is an infrastructure failure (exit 97), not a quiet skip.
  2. Run `codex exec <args after -->` with this process's stdin as the
     prompt (read once, replayed on retry); stdout+stderr append to --log.
  3. Classify the run from its rollout file (located via the "session id:"
     banner in the log):
       ok               non-empty last_agent_message         -> exit 0
       auth             empty + error unauthorized/token     -> exit 97, NO retry
       credit           empty + no error + has_credits false -> exit 97, NO retry
       error            empty + any other error object       -> exit 97, NO retry
       empty-no-error   empty final, no error                -> retry once iff
                        --retry-once, else exit 98
       no-completion / spawn-death                            -> same as above
  4. Every non-ok round appends a crash record (kind, session, rollout path,
     duration_ms, last_total_tokens, error message, argv) to --crash-log and
     alerts the operator on stderr (+ best-effort macOS notification).

Env overrides (used by tests; defaults are the real surfaces):
  CODEX_DISPATCH_BIN            codex binary (default: codex on PATH)
  CODEX_DISPATCH_SESSIONS_ROOT  rollout root (default: ~/.codex/sessions)
  CODEX_DISPATCH_NO_NOTIFY=1    suppress the macOS notification

Runs under /usr/bin/python3 (3.9) in cron -- keep 3.9-compatible.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"
DEFAULT_CRASH_LOG = OUT / "dispatch_crashes.jsonl"

SESSION_ID_RE = re.compile(r"^session id: ([0-9a-f-]{36})\s*$", re.MULTILINE)
AUTH_MSG = re.compile(r"(?i)access token|refresh token|log ?out and sign in|unauthorized")

EXIT_INFRASTRUCTURE = 97
EXIT_FAILED_ROUND = 98


def _codex_bin() -> str:
    return os.environ.get("CODEX_DISPATCH_BIN", "codex")


def _sessions_root() -> Path:
    return Path(os.environ.get("CODEX_DISPATCH_SESSIONS_ROOT",
                               str(Path.home() / ".codex" / "sessions")))


def parse_session_id(log_text: str):
    m = SESSION_ID_RE.search(log_text)
    return m.group(1) if m else None


def find_rollout(session_id: str, root: Path):
    hits = sorted(root.glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
    return hits[-1] if hits else None


def read_terminal_events(rollout_path: Path) -> dict:
    """Stream the rollout; keep the last task_complete, the last token_count's
    credit flag and total, and whether any non-empty agent message appeared."""
    t = {"task_complete": None, "has_credits": None,
         "last_total_tokens": None, "had_output": False}
    with open(rollout_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") != "event_msg":
                continue
            p = obj.get("payload") or {}
            ptype = p.get("type")
            if ptype == "token_count":
                info = p.get("info") or {}
                total = (info.get("total_token_usage") or {}).get("total_tokens")
                if isinstance(total, int):
                    t["last_total_tokens"] = total
                credits = (p.get("rate_limits") or {}).get("credits") or {}
                if isinstance(credits.get("has_credits"), bool):
                    t["has_credits"] = credits["has_credits"]
            elif ptype == "agent_message":
                msg = p.get("message")
                if isinstance(msg, str) and msg.strip():
                    t["had_output"] = True
            elif ptype == "task_complete":
                t["task_complete"] = p
    return t


def classify(terminal) -> dict:
    """Verdict for one run. infrastructure => operator problem, never respawn;
    retryable => one fresh-session respawn is safe and possibly useful."""
    def v(kind, retryable=False, infrastructure=False, detail=None):
        return {"kind": kind, "retryable": retryable,
                "infrastructure": infrastructure, "detail": detail}

    if terminal is None:
        return v("spawn-death", retryable=True,
                 detail="codex exited before printing a session id")
    tc = terminal.get("task_complete")
    if tc is None:
        return v("no-completion", retryable=True,
                 detail="rollout ended without a task_complete event")
    lam = tc.get("last_agent_message")
    if isinstance(lam, str) and lam.strip():
        return v("ok")
    error = tc.get("error")
    if isinstance(error, dict):
        msg = str(error.get("message") or "")
        if error.get("codex_error_info") == "unauthorized" or AUTH_MSG.search(msg):
            return v("auth", infrastructure=True, detail=msg)
        return v("error", infrastructure=True, detail=msg)
    if terminal.get("has_credits") is False:
        return v("credit", infrastructure=True,
                 detail="rate_limits.credits.has_credits false at completion")
    return v("empty-no-error", retryable=True,
             detail="task_complete with empty last_agent_message and no error")


def alert(message: str, infrastructure: bool = True):
    label = "INFRASTRUCTURE FAILURE" if infrastructure else "FAILED ROUND"
    print(f"CODEX-DISPATCH {label}: {message}", file=sys.stderr)
    if os.environ.get("CODEX_DISPATCH_NO_NOTIFY") == "1":
        return
    try:  # best-effort; cron has no GUI guarantees
        subprocess.run(
            ["osascript", "-e",
             'display notification "%s" with title "codex dispatch"'
             % message.replace('"', "'")[:180]],
            capture_output=True, timeout=5)
    except Exception:
        pass


def write_crash_record(crash_log: Path, record: dict):
    crash_log.parent.mkdir(parents=True, exist_ok=True)
    with open(crash_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_codex(args, prompt_bytes: bytes, log_path: Path) -> int:
    with open(log_path, "ab") as log:
        proc = subprocess.run([_codex_bin(), "exec", *args],
                              input=prompt_bytes, stdout=log, stderr=log)
    return proc.returncode


def dispatch_round(args, prompt_bytes, log_path, attempt: int):
    """One codex run. Returns (verdict, context-for-crash-record, codex_rc)."""
    mark = log_path.stat().st_size if log_path.exists() else 0
    rc = run_codex(args, prompt_bytes, log_path)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")[mark:]
    session_id = parse_session_id(log_text)
    rollout = find_rollout(session_id, _sessions_root()) if session_id else None
    terminal = read_terminal_events(rollout) if rollout else None
    verdict = classify(terminal)
    tc = (terminal or {}).get("task_complete") or {}
    ctx = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attempt": attempt,
        "session_id": session_id,
        "rollout": str(rollout) if rollout else None,
        "duration_ms": tc.get("duration_ms"),
        "last_total_tokens": (terminal or {}).get("last_total_tokens"),
        "codex_exit": rc,
    }
    return verdict, ctx, rc


def main() -> int:
    ap = argparse.ArgumentParser(
        description="codex exec wrapper: classify null-final deaths instead of "
                    "passing them off as 'no findings'")
    ap.add_argument("--log", required=True, help="append codex stdout+stderr here")
    ap.add_argument("--crash-log", default=str(DEFAULT_CRASH_LOG))
    ap.add_argument("--label", default=None, help="dispatch name for crash records")
    ap.add_argument("--retry-once", action="store_true",
                    help="respawn once in a fresh session on a retryable empty round")
    ap.add_argument("--no-preflight", action="store_true")
    ap.add_argument("codex_args", nargs=argparse.REMAINDER,
                    help="-- then arguments for `codex exec`")
    ns = ap.parse_args()
    codex_args = ns.codex_args
    if codex_args and codex_args[0] == "--":
        codex_args = codex_args[1:]
    log_path = Path(ns.log)
    crash_log = Path(ns.crash_log)

    def record(verdict, ctx):
        rec = dict(ctx)
        rec.update({"kind": verdict["kind"], "detail": verdict["detail"],
                    "label": ns.label, "codex_args": codex_args})
        write_crash_record(crash_log, rec)
        return rec

    if not ns.no_preflight:
        try:
            pf = subprocess.run([_codex_bin(), "login", "status"],
                                capture_output=True, text=True, timeout=30)
            pf_ok, pf_detail = pf.returncode == 0, (pf.stdout + pf.stderr).strip()
        except Exception as e:
            pf_ok, pf_detail = False, f"login status probe failed: {e}"
        if not pf_ok:
            verdict = {"kind": "preflight-auth", "retryable": False,
                       "infrastructure": True, "detail": pf_detail}
            record(verdict, {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "attempt": 0, "session_id": None, "rollout": None,
                             "duration_ms": None, "last_total_tokens": None,
                             "codex_exit": None})
            alert(f"[{ns.label or 'codex'}] refusing to dispatch: {pf_detail}")
            return EXIT_INFRASTRUCTURE

    prompt_bytes = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") \
        else sys.stdin.read().encode()

    attempts = 2 if ns.retry_once else 1
    verdict = {"kind": "not-run", "retryable": False, "infrastructure": False,
               "detail": None}
    for attempt in range(1, attempts + 1):
        verdict, ctx, rc = dispatch_round(codex_args, prompt_bytes, log_path, attempt)
        if verdict["kind"] == "ok":
            return rc
        record(verdict, ctx)
        if verdict["infrastructure"]:
            alert(f"[{ns.label or 'codex'}] {verdict['kind']}: {verdict['detail']} "
                  f"(session {ctx['session_id']}, {ctx['duration_ms']}ms, "
                  f"{ctx['last_total_tokens']} tokens) -- NOT respawning")
            return EXIT_INFRASTRUCTURE
        if attempt < attempts and verdict["retryable"]:
            print(f"codex_dispatch: {verdict['kind']} on attempt {attempt}; "
                  f"respawning once in a fresh session", file=sys.stderr)
            continue
        break
    alert(f"[{ns.label or 'codex'}] {verdict['kind']} after {attempts} attempt(s): "
          f"{verdict['detail']} -- empty result is NOT 'no findings'",
          infrastructure=False)
    return EXIT_FAILED_ROUND


if __name__ == "__main__":
    sys.exit(main())
