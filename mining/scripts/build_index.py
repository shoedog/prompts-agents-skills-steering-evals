#!/usr/bin/env python3
"""Streaming indexer for the two local transcript corpora:

  ~/.claude/projects/<encoded-project-dir>/<session-uuid>.jsonl
      Claude Code session transcripts (one JSON object per line).
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
      Codex CLI "rollout" transcripts (one JSON object per line, different schema).

Emits one JSON row per MAIN session to:
  mining/out/claude_index.jsonl
  mining/out/codex_index.jsonl

Never loads a whole file into memory -- both corpora are streamed line by line.

============================================================================
OBSERVED SCHEMA NOTES (derived from inspecting real files, not assumed)
============================================================================

Claude Code (~/.claude/projects/**/*.jsonl)
--------------------------------------------
Each project directory name is the session's launch `cwd` with '/' replaced
by '-' (e.g. "-Users-wesleyjinks-code-slicing" -> "/Users/wesleyjinks/code/
slicing"). This encoding is LOSSY: a literal '-' inside a real path component
(e.g. "prompts-skills-steering") is indistinguishable from a '/' separator.
Rather than guess, this script prefers the `cwd` field recorded on the
transcript's own lines (ground truth, present on almost every line) and only
falls back to naive dash-decoding of the directory name for the rare
sessions that never recorded a `cwd` (e.g. degenerate "bridge-session" stub
files, see below).

Two distinct sidechain/subagent mechanisms coexist in this corpus:

  1. Inline sidechains: lines within the main session .jsonl carry
     "isSidechain": true (the classic Task-tool subagent transcript,
     interleaved with the parent).
  2. Out-of-process subagents: a session directory
     ~/.claude/projects/<proj>/<session-uuid>/subagents/agent-*.jsonl
     (occasionally nested further under .../subagents/workflows/wf_*/
     agent-*.jsonl for multi-agent orchestration) holds ENTIRELY SEPARATE
     files for agents spawned via the Agent/Task tool. Every line in these
     files also carries "isSidechain": true. These are NOT top-level
     *.jsonl files directly under a project dir, so a naive `find -name
     "*.jsonl"` count (which is what the ~3,629 total in the task brief
     reflects) includes them, while this indexer treats them as sidechain
     material rolled into their parent session's row (sidechain_models,
     n_sidechain_lines) rather than as separate indexed sessions. See
     task-M1-report.md for the exact main-vs-subagent-file split observed
     and a note on the small number of "orphan" subagent dirs that have no
     matching top-level parent file (parent session file missing/renamed).

  There is also a "tool-results/" sibling directory (plain text blobs, not
  JSONL) used to store large tool outputs out of line; it is not indexed.

Top-level line `type` values observed: user, assistant, system, attachment,
queue-operation, file-history-snapshot, mode, last-prompt, permission-mode,
bridge-session, ai-title, pr-link. Only `user` and `assistant` carry a
`message` object ({role, content, model(assistant only), ...}).

`message.content` is either a plain string, or a list of typed blocks:
text, thinking, tool_use ({name, input}), tool_result ({content: str | list
of {type:text,...}}). Assistant turns with `message.model == "<synthetic>"`
are locally-injected placeholders (observed content: "API Error: ..." after
a dropped connection) -- excluded from the `models` turn tally but still
scanned for outcome signals (an API error IS an error).

Real vs. wrapper user turns: slash commands and command-line automation
inject user-role messages wrapping the real text in
<local-command-caveat>/<command-name>/<command-message>/<command-args>
tags (with "isMeta": true on the caveat line); mid-conversation system
nudges get appended as trailing <system-reminder>...</system-reminder>
inside an otherwise-real user turn. `first_user_text` strips these tags and
takes the first turn with real content left over.

Observed model id strings (from a ~900-file sample): claude-opus-4-8,
claude-sonnet-4-6, claude-sonnet-5, claude-fable-5, claude-haiku-4-5-*,
claude-opus-4-6, claude-opus-4-7 (rare), <synthetic>.

Codex (~/.codex/sessions/**/*.jsonl)
-------------------------------------
Top-level line `type` values: session_meta (once, has payload.cwd), event_msg,
response_item, turn_context, compacted.

  - turn_context.payload.model: the active model for the turn (also mirrored
    in payload.collaboration_mode.settings.model); observed to change only
    rarely mid-session. Tracked as "current model" while streaming and used
    to attribute subsequent assistant turns.
  - event_msg.payload.type == "user_message": real user turn text is in
    payload.message directly (no wrapper stripping needed -- the CLI's own
    <environment_context> injection shows up separately as a
    response_item/message with role="developer"/"user", not as a
    user_message event, so it's naturally excluded).
  - event_msg.payload.type == "agent_message": one assistant turn,
    payload.message is the text. Cross-checked against
    response_item/message role=="assistant" counts on a sample file -- they
    matched exactly (2131 == 2131), so agent_message is used as the single
    source of truth for assistant turns (simpler: text is inline, no block
    parsing needed).
  - response_item.payload.type in (function_call, custom_tool_call): tool
    calls; payload.name is the tool (exec_command, apply_patch, write_stdin,
    update_plan, ...). function_call_output / custom_tool_call_output carry
    the result text (scanned for outcome signals).
  - No sidechain/subagent concept observed in this corpus (single-agent CLI)
    -- sidechain fields are always empty/zero for codex rows.

Observed model id strings: gpt-5.5 (dominant), gpt-5.4, gpt-5.3-codex-spark,
gpt-5.3-codex, gpt-5.4-mini, and one stray "gpt-5-5" (dash instead of dot,
kept as-is/unnormalized).

Malformed lines: extremely rare in sampling (0 bad lines in ~20k sampled
lines across both corpora) but handled defensively per-file with a
try/except around json.loads; counted and skipped, never fatal.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CLAUDE_ROOT = HOME / ".claude" / "projects"
CODEX_ROOT = HOME / ".codex" / "sessions"

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "mining" / "out"

# ---------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------

WRAPPER_TAG_RE = re.compile(
    r"<(command-name|command-message|command-args|local-command-caveat"
    r"|system-reminder|environment_context)>.*?</\1>",
    re.DOTALL,
)

FRUSTRATION_RE = re.compile(r"no,|wrong|stop|not what", re.IGNORECASE)
TEST_WORD_RE = re.compile(r"test", re.IGNORECASE)
TEST_PASS_RE = re.compile(r"passed|PASS|✓")
GIT_COMMIT_MENTION_RE = re.compile(r"git commit", re.IGNORECASE)
GIT_COMMIT_BANNER_RE = re.compile(r"\[\S+ [0-9a-f]{7,40}\]")

ORCH_TOOL_NAMES = {
    "Agent", "Task", "TaskCreate", "TaskList", "TaskGet", "TaskUpdate",
    "TaskStop", "SendMessage", "TaskOutput",
}

# task_type keyword rules, checked in order; first bucket with >=1 hit wins.
# confidence = 'med' if >=2 keyword hits landed in the winning bucket, else 'low'.
KEYWORD_RULES = [
    # Checked before debug/refactor: review-rubric prompts frequently discuss
    # bugs/regressions/blockers as part of what to look for, which would
    # otherwise false-positive into the debug bucket (observed in sampling).
    ("review", [
        "code review", "review this", "review the", "review my",
        "reviewer of", "reviewers of", "independent review", "reviewing a",
        "diff review", "review a diff", "review the diff",
        "pr review", "pull request", "critique", "give feedback on",
        "second opinion", "blockers",
    ]),
    ("debug", [
        "debug", " bug ", "bugfix", "fix the bug", "failing test",
        "not working", "doesn't work", "broken", "crash", "traceback",
        "stack trace", "regression", "root cause", "why is this fail",
        "why does this fail", "flaky", "reproduce the",
    ]),
    ("plan_design", [
        "implementation plan", "write a plan", "design doc", "architecture",
        "rfc", "proposal for", "spec for", "write and execute the",
        "design the", "brainstorm",
    ]),
    ("refactor", [
        "refactor", "clean up", "simplify", "reorganize", "restructure",
        "extract a function", "dedupe", "deduplicate", "rename ",
    ]),
    ("infra_config", [
        "ci pipeline", "dockerfile", "docker-compose", "deploy",
        "deployment", "kubernetes", "k8s", "github actions", "ci/cd",
        "environment variable", "settings.json", "set up ci",
        "configure the", "terraform", "pyproject.toml", "gitignore",
    ]),
    ("writing_docs", [
        "write docs", "readme", "documentation for", "write a report",
        "write-up", "write up a", "changelog", "write the docs",
    ]),
    ("data_analysis", [
        "dataset", "csv", "sql query", "dataframe", "pandas", "plot the",
        "chart of", "cross-tab", "analyze the data", "analyze the results",
        "metrics for", "statistics on",
    ]),
    ("research_analysis", [
        "research ", "investigate", "compare ", "explain how",
        "understand how", "look into", "figure out why",
        "what is the best", "what's the best", "inspect the",
    ]),
    ("implement", [
        "implement", "add support for", "add a feature", "build a ",
        "create a new", "write code to", "add an endpoint", "new feature",
        "build the", "add a new",
    ]),
]


def truncate(text, n):
    if not text:
        return None
    text = text.strip()
    return text[:n]


def strip_wrappers(text):
    if not text:
        return ""
    return WRAPPER_TAG_RE.sub("", text).strip()


def classify_task_type(text, tool_counter):
    lower = (text or "").lower()
    total_tools = sum(tool_counter.values())
    orch_tools = sum(tool_counter.get(t, 0) for t in ORCH_TOOL_NAMES)
    if total_tools and orch_tools >= 3 and orch_tools / total_tools > 0.15:
        return "orchestration", "med"
    for task_type, keywords in KEYWORD_RULES:
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            return task_type, ("med" if hits >= 2 else "low")
    return "other", "low"


def iso_to_epoch_min(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() / 60.0
    except Exception:
        return None


class OutcomeAccumulator:
    __slots__ = ("error_hits", "commit_hits", "tests_passed", "n_lines")

    def __init__(self):
        self.error_hits = 0
        self.commit_hits = 0
        self.tests_passed = False
        self.n_lines = 0

    def scan(self, text):
        if not text:
            return
        self.error_hits += (
            text.count("Error") + text.count("Traceback") + text.count("FAILED")
        )
        self.commit_hits += len(GIT_COMMIT_MENTION_RE.findall(text))
        self.commit_hits += len(GIT_COMMIT_BANNER_RE.findall(text))
        if not self.tests_passed and TEST_WORD_RE.search(text) and TEST_PASS_RE.search(text):
            self.tests_passed = True

    def to_dict(self, frustration_count):
        density = round(self.error_hits * 100.0 / max(self.n_lines, 1), 3)
        return {
            "mentions_tests_passed": self.tests_passed,
            "n_commits": self.commit_hits,
            "n_errors": density,
            "user_frustration": frustration_count,
        }


# ---------------------------------------------------------------------------
# Claude Code parsing
# ---------------------------------------------------------------------------

def decode_project_dirname(dirname):
    if dirname.startswith("-"):
        return "/" + dirname[1:].replace("-", "/")
    return dirname.replace("-", "/")


def extract_first_real_user_text(content):
    """Return cleaned real-user text, or None if this is a pure wrapper turn."""
    if isinstance(content, str):
        cleaned = strip_wrappers(content)
        return cleaned or None
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                cleaned = strip_wrappers(block.get("text") or "")
                if cleaned:
                    return cleaned
        return None
    return None


def extract_assistant_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        joined = "\n".join(p for p in parts if p)
        return joined.strip()
    return ""


def extract_scan_texts(content):
    out = []
    if content is None:
        return out
    if isinstance(content, str):
        out.append(content)
        return out
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            bt = block.get("type")
            if bt == "text":
                out.append(block.get("text") or "")
            elif bt == "thinking":
                th = block.get("thinking")
                if th:
                    out.append(th)
            elif bt == "tool_result":
                c = block.get("content")
                if isinstance(c, str):
                    out.append(c)
                elif isinstance(c, list):
                    for sub in c:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            out.append(sub.get("text") or "")
            elif bt == "tool_use" and block.get("name") == "Bash":
                inp = block.get("input") or {}
                cmd = inp.get("command")
                if cmd:
                    out.append(cmd)
    return out


def find_claude_main_files(root):
    """Yield top-level session .jsonl files directly under each project dir
    (i.e. NOT the ones nested under <uuid>/subagents/...)."""
    if not root.exists():
        return
    for proj_dir in sorted(root.iterdir()):
        if not proj_dir.is_dir():
            continue
        for entry in sorted(proj_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".jsonl":
                yield entry


def stream_json_lines(path, fail_counter):
    """Yield parsed dicts from a jsonl file, counting failures in fail_counter (a
    single-element list used as a mutable int cell)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                fail_counter[0] += 1
                continue


def roll_up_subagent_dir(session_dir, sidechain_models, fail_counter):
    """Fold every line of every *.jsonl under <session_dir>/subagents/**
    (arbitrary nesting, e.g. subagents/workflows/wf_x/agent-*.jsonl) into
    sidechain_models / a line count. Returns n_lines rolled up."""
    subagents_dir = session_dir / "subagents"
    if not subagents_dir.exists():
        return 0
    n_lines = 0
    for sub_path in subagents_dir.rglob("*.jsonl"):
        for d in stream_json_lines(sub_path, fail_counter):
            n_lines += 1
            msg = d.get("message")
            if isinstance(msg, dict) and d.get("type") == "assistant":
                model = msg.get("model")
                if model and model != "<synthetic>":
                    sidechain_models[model] += 1
    return n_lines


def process_claude_session(path, orphan_tracker=None):
    fail_counter = [0]
    first_cwd = None
    start_ts = None
    end_ts = None
    models_main = Counter()
    inline_sidechain_models = Counter()
    n_user_turns = 0
    n_assistant_turns = 0
    tool_counter = Counter()
    first_user_text = None
    last_assistant_text = None
    inline_sidechain_lines = 0
    frustration_count = 0
    acc = OutcomeAccumulator()

    n_lines = 0
    for d in stream_json_lines(path, fail_counter):
        n_lines += 1
        acc.n_lines += 1

        if first_cwd is None:
            c = d.get("cwd")
            if c:
                first_cwd = c

        ts = d.get("timestamp")
        if ts:
            if start_ts is None or ts < start_ts:
                start_ts = ts
            if end_ts is None or ts > end_ts:
                end_ts = ts

        is_sidechain = bool(d.get("isSidechain"))
        dtype = d.get("type")
        msg = d.get("message")
        msg = msg if isinstance(msg, dict) else None

        if is_sidechain:
            inline_sidechain_lines += 1
            if dtype == "assistant" and msg:
                model = msg.get("model")
                if model and model != "<synthetic>":
                    inline_sidechain_models[model] += 1
            continue  # sidechain content does not count toward main stats

        if msg is None:
            continue

        role = msg.get("role")
        content = msg.get("content")

        if dtype == "user" and role == "user":
            is_meta = bool(d.get("isMeta"))
            if not is_meta:
                n_user_turns += 1
                real_text = extract_first_real_user_text(content)
                if real_text:
                    if first_user_text is None:
                        first_user_text = real_text
                    if FRUSTRATION_RE.search(real_text):
                        frustration_count += 1
            for t in extract_scan_texts(content):
                acc.scan(t)

        elif dtype == "assistant":
            n_assistant_turns += 1
            model = msg.get("model")
            if model and model != "<synthetic>":
                models_main[model] += 1
            text = extract_assistant_text(content)
            if text:
                last_assistant_text = text
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_counter[block.get("name") or "?"] += 1
            for t in extract_scan_texts(content):
                acc.scan(t)

    # Roll up out-of-process subagent files living in the sibling
    # <session-uuid>/ directory next to this main file.
    session_dir = path.parent / path.stem
    n_external_sidechain_lines = 0
    if session_dir.exists() and session_dir.is_dir():
        n_external_sidechain_lines = roll_up_subagent_dir(
            session_dir, inline_sidechain_models, fail_counter
        )

    project = first_cwd or decode_project_dirname(path.parent.name)

    if start_ts is None:
        # Degenerate sessions (e.g. "bridge-session" stub with no message
        # lines at all) carry no timestamp; fall back to file mtime so
        # duration_min is at least defined (0).
        mtime_iso = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        start_ts = end_ts = mtime_iso

    start_min = iso_to_epoch_min(start_ts)
    end_min = iso_to_epoch_min(end_ts)
    duration_min = round(end_min - start_min, 2) if (start_min is not None and end_min is not None) else None

    task_type, confidence = classify_task_type(first_user_text, tool_counter)

    row = {
        "path": str(path),
        "project": project,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_min": duration_min,
        "models": dict(models_main),
        "sidechain_models": dict(inline_sidechain_models),
        "n_user_turns": n_user_turns,
        "n_assistant_turns": n_assistant_turns,
        "n_sidechain_lines": inline_sidechain_lines + n_external_sidechain_lines,
        "tool_histogram": dict(tool_counter.most_common(10)),
        "total_bytes": path.stat().st_size,
        "first_user_text": truncate(first_user_text, 600),
        "last_assistant_text": truncate(last_assistant_text, 400),
        "outcome_signals": acc.to_dict(frustration_count),
        "task_type": task_type,
        "task_type_confidence": confidence,
        "n_lines": n_lines,
        "parse_failures": fail_counter[0],
        "source": "claude",
    }
    return row, fail_counter[0]


# ---------------------------------------------------------------------------
# Codex parsing
# ---------------------------------------------------------------------------

def extract_codex_output_text(payload):
    """function_call_output / custom_tool_call_output -> best-effort text."""
    for key in ("output", "content"):
        v = payload.get(key)
        if isinstance(v, str):
            return v
    return ""


def process_codex_session(path):
    fail_counter = [0]
    first_cwd = None
    start_ts = None
    end_ts = None
    models_main = Counter()
    n_user_turns = 0
    n_assistant_turns = 0
    tool_counter = Counter()
    first_user_text = None
    last_assistant_text = None
    frustration_count = 0
    acc = OutcomeAccumulator()
    current_model = None

    n_lines = 0
    for d in stream_json_lines(path, fail_counter):
        n_lines += 1
        acc.n_lines += 1

        ts = d.get("timestamp")
        if ts:
            if start_ts is None or ts < start_ts:
                start_ts = ts
            if end_ts is None or ts > end_ts:
                end_ts = ts

        dtype = d.get("type")
        payload = d.get("payload")
        payload = payload if isinstance(payload, dict) else {}

        if dtype == "session_meta":
            c = payload.get("cwd")
            if c and first_cwd is None:
                first_cwd = c
            continue

        if dtype == "turn_context":
            m = payload.get("model")
            if m:
                current_model = m
            c = payload.get("cwd")
            if c and first_cwd is None:
                first_cwd = c
            continue

        if dtype == "event_msg":
            ptype = payload.get("type")
            if ptype == "user_message":
                n_user_turns += 1
                text = strip_wrappers(payload.get("message") or "") or (payload.get("message") or "").strip()
                if text:
                    if first_user_text is None:
                        first_user_text = text
                    if FRUSTRATION_RE.search(text):
                        frustration_count += 1
                    acc.scan(text)
            elif ptype == "agent_message":
                n_assistant_turns += 1
                if current_model:
                    models_main[current_model] += 1
                text = (payload.get("message") or "").strip()
                if text:
                    last_assistant_text = text
                    acc.scan(text)
            continue

        if dtype == "response_item":
            ptype = payload.get("type")
            if ptype in ("function_call", "custom_tool_call"):
                tool_counter[payload.get("name") or "?"] += 1
            elif ptype == "web_search_call":
                tool_counter["web_search"] += 1
            elif ptype in ("function_call_output", "custom_tool_call_output"):
                acc.scan(extract_codex_output_text(payload))
            continue

        # compacted / other: ignore for stats, already covered by timestamp scan

    project = first_cwd or "unknown"

    if start_ts is None:
        mtime_iso = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        start_ts = end_ts = mtime_iso

    start_min = iso_to_epoch_min(start_ts)
    end_min = iso_to_epoch_min(end_ts)
    duration_min = round(end_min - start_min, 2) if (start_min is not None and end_min is not None) else None

    task_type, confidence = classify_task_type(first_user_text, tool_counter)

    row = {
        "path": str(path),
        "project": project,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_min": duration_min,
        "models": dict(models_main),
        "sidechain_models": {},
        "n_user_turns": n_user_turns,
        "n_assistant_turns": n_assistant_turns,
        "n_sidechain_lines": 0,
        "tool_histogram": dict(tool_counter.most_common(10)),
        "total_bytes": path.stat().st_size,
        "first_user_text": truncate(first_user_text, 600),
        "last_assistant_text": truncate(last_assistant_text, 400),
        "outcome_signals": acc.to_dict(frustration_count),
        "task_type": task_type,
        "task_type_confidence": confidence,
        "n_lines": n_lines,
        "parse_failures": fail_counter[0],
        "source": "codex",
    }
    return row, fail_counter[0]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

SESSION_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def count_orphan_subagent_dirs(root):
    """Diagnostic only: how many <session-uuid>/ directories (subagents
    and/or tool-results) have no matching top-level <uuid>.jsonl parent file
    (parent session missing/renamed). Project dirs also contain a sibling
    "memory/" directory (persistent agent-memory notes, unrelated to
    sessions) which is explicitly excluded by requiring the entry name to
    look like a session uuid."""
    total_dirs = 0
    orphans = 0
    orphan_lines = 0
    if not root.exists():
        return 0, 0, 0
    for proj_dir in root.iterdir():
        if not proj_dir.is_dir():
            continue
        for entry in proj_dir.iterdir():
            if entry.is_dir() and SESSION_UUID_RE.match(entry.name):
                total_dirs += 1
                main_file = entry.with_suffix(".jsonl")
                if not main_file.exists():
                    orphans += 1
                    subagents_dir = entry / "subagents"
                    if subagents_dir.exists():
                        for sub_path in subagents_dir.rglob("*.jsonl"):
                            try:
                                with open(sub_path, "r", errors="replace") as f:
                                    orphan_lines += sum(1 for _ in f)
                            except Exception:
                                pass
    return total_dirs, orphans, orphan_lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="Only process N files per corpus (debug)")
    ap.add_argument("--skip-claude", action="store_true")
    ap.add_argument("--skip-codex", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    stats = {}

    if not args.skip_claude:
        claude_files = list(find_claude_main_files(CLAUDE_ROOT))
        if args.limit:
            claude_files = claude_files[: args.limit]
        n_rows = 0
        n_fail_lines = 0
        n_file_errors = 0
        out_path = OUT_DIR / "claude_index.jsonl"
        with open(out_path, "w", encoding="utf-8") as out:
            for i, path in enumerate(claude_files):
                try:
                    row, fails = process_claude_session(path)
                except Exception as e:
                    n_file_errors += 1
                    print(f"[claude] FILE ERROR {path}: {e}", file=sys.stderr)
                    continue
                n_fail_lines += fails
                out.write(json.dumps(row) + "\n")
                n_rows += 1
                if (i + 1) % 500 == 0:
                    print(f"[claude] {i + 1}/{len(claude_files)} files...", file=sys.stderr)

        total_dirs, orphans, orphan_lines = count_orphan_subagent_dirs(CLAUDE_ROOT)
        stats["claude"] = {
            "main_files_found": len(claude_files),
            "rows_written": n_rows,
            "parse_fail_lines": n_fail_lines,
            "file_errors": n_file_errors,
            "session_subagent_dirs_total": total_dirs,
            "orphan_subagent_dirs (no parent main file)": orphans,
            "orphan_subagent_dir_lines": orphan_lines,
        }
        print(f"[claude] done: {n_rows} rows -> {out_path}", file=sys.stderr)

    if not args.skip_codex:
        codex_files = sorted(CODEX_ROOT.rglob("*.jsonl"))
        if args.limit:
            codex_files = codex_files[: args.limit]
        n_rows = 0
        n_fail_lines = 0
        n_file_errors = 0
        out_path = OUT_DIR / "codex_index.jsonl"
        with open(out_path, "w", encoding="utf-8") as out:
            for i, path in enumerate(codex_files):
                try:
                    row, fails = process_codex_session(path)
                except Exception as e:
                    n_file_errors += 1
                    print(f"[codex] FILE ERROR {path}: {e}", file=sys.stderr)
                    continue
                n_fail_lines += fails
                out.write(json.dumps(row) + "\n")
                n_rows += 1
                if (i + 1) % 500 == 0:
                    print(f"[codex] {i + 1}/{len(codex_files)} files...", file=sys.stderr)

        stats["codex"] = {
            "files_found": len(codex_files),
            "rows_written": n_rows,
            "parse_fail_lines": n_fail_lines,
            "file_errors": n_file_errors,
        }
        print(f"[codex] done: {n_rows} rows -> {out_path}", file=sys.stderr)

    stats["elapsed_sec"] = round(time.time() - t0, 1)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
