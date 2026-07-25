#!/usr/bin/env python3
"""Failure-signature detector over the two local transcript corpora (Wave 0 of
the 2026-07-25 failure-mode mitigation plan; see ~/Documents/
agent-failure-modes-2026-07-25.md §4-E1/§7).

Purpose: turn the one-off forensic analysis into a standing, re-runnable
detector that emits labeled incident streams (for TRACKER nominations) and a
baseline report (so later mitigation waves are measurable against today's
rates).

Reads (streaming, never whole-file):
  ~/.claude/projects/<proj>/<session>.jsonl   (main sessions, via build_index.find_claude_main_files)
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl

Emits:
  mining/out/failure_signatures.jsonl  -- one row per incident:
      {corpus, detector, bucket, path, session, line_no, ts, model, cwd,
       sidechain, snippet}
  mining/out/failure_baseline.md       -- counts, July-2026 daily series,
      recurrence-after-admission metric, loop/fork session lists, and a
      known-incident validation table.

Detectors (high-precision by design; fuzzy ideas like "mechanism claim
without citation" are deliberately EXCLUDED from v1 -- a noisy metric is
worse than none):

  Claude + Codex assistant text:
    admission_{strong,weak}      self-admitted errors ("I was wrong", "my
                                 mistake", "this one is on me", "I over-claimed";
                                 weak: "I assumed", "you're right").
  Claude real user turns / Codex user_message events:
    user_correction_{strong,weak}  the user calling out a failure ("you didn't",
                                 "did you actually read", "I told you"; weak:
                                 "wrong", "again", "assum*", "too specific").
  Claude Bash tool_use:
    pipe_truncated_test          test-ish command piped through tail/head --
                                 the exact `| tail -8` evidence-destruction
                                 signature (608a7a2a L2692).
    pipe_truncated_check         looser: any check/verify/campaign command
                                 piped through tail/head.
  Claude assistant lines:
    synthetic_error              message.model == "<synthetic>" (API-error
                                 placeholder turns).
  Claude session-level:
    lineage_dupe                 a session file whose FIRST content-line uuid
                                 appears inside another session file -- i.e. a
                                 post-compact/resume fork that copied its
                                 parent's history and double-counts in naive
                                 mining (e.g. 9aea8b01 duplicating 608a7a2a).
                                 NOTE: first-uuid EQUALITY does not work (forks
                                 begin mid-lineage), copied lines carry the
                                 fork's OWN sessionId, and a dangling first
                                 parentUuid marks every chained session, not
                                 just dupes -- containment of the child's first
                                 uuid in the parent is the discriminating
                                 signal (verified on the 9aea8b01/608a7a2a
                                 pair, 2026-07-25).
  Codex event stream:
    null_final_zero_output       task_complete with empty last_agent_message
                                 and NO prior assistant text (spawn death;
                                 2026-07-10 sol x codex-acp x CLI 0.133.0
                                 cluster).
    null_final_after_output      task_complete with empty last_agent_message
                                 after real output (context-capacity death;
                                 the 17.6M-token r2f review loss).
    apply_patch_failed           "apply_patch verification failed" in a tool
                                 output; sessions with >=3 are patch loops
                                 (line-number-anchored prompt drift).
    phantom_tool_fallback        worker narrating that advertised prism/lsp
                                 nav tools are not actually mounted.

Validation ground truth (known incidents from the 2026-07-25 forensics; the
baseline report asserts each is found -- if one goes missing after a schema
change, the detector regressed, not the corpus):
  admission            fb80415b-...jsonl ("over-claimed"), 608a7a2a-...jsonl
  pipe_truncated_*     608a7a2a-...jsonl (`| tail -8` on test campaigns)
  null_final_*         rollout-2026-07-20T17-49-14-*.jsonl (r2f capacity),
                       rollout-2026-07-10T09-23-38-*.jsonl (PONG spawn death)
  apply_patch_failed   rollout-2026-07-06T20-58-03-*.jsonl (7 in-session)

Usage:
  python3 mining/scripts/detect_failure_signatures.py            # full corpora
  python3 mining/scripts/detect_failure_signatures.py --since 2026-07-01
  (--since filters codex files by path date and claude files by mtime; rows
   always carry their own ts, so the baseline slices July regardless.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_index import CLAUDE_ROOT, CODEX_ROOT, find_claude_main_files, stream_json_lines  # noqa: E402

OUT_DIR = HERE.parent / "out"
HOME = Path.home()

# ---------------------------------------------------------------- patterns

ADMISSION_STRONG = re.compile(
    r"(?i)\bmy (?:mistake|error|fault)\b"
    r"|\bI was wrong\b|\bI'?m wrong\b|\bI got (?:this|that|it) wrong\b"
    r"|\bth(?:is|at) one(?:'s| is) on me\b|\bthat'?s on me\b"
    r"|\bI over-?(?:claimed|stated|reached)\b"
    r"|\bI mis(?:read|understood|interpreted)\b"
    r"|\bI should (?:have|'ve)\b"
)
ADMISSION_WEAK = re.compile(
    r"(?i)\byou'?re (?:absolutely |completely |quite )?right\b|\byou are right\b|\bI assumed\b"
)
CORRECTION_STRONG = re.compile(
    r"(?i)\byou (?:didn'?t|did not|never|keep)\b"
    r"|\bdid you (?:actually |even )?(?:read|check|run|trace|look|verify)\b"
    r"|\bI (?:said|told you|asked)\b"
    r"|\bnot what I (?:asked|said|meant)\b"
    r"|\bwhy (?:did|didn'?t|are|would) you\b"
    r"|\bre-?read\b|\bactually read\b|\btrace through\b"
)
CORRECTION_WEAK = re.compile(
    r"(?i)\bwrong\b|\bagain\b|\bassum\w+|\bgeneraliz\w+|\btoo (?:specific|narrow|broad)\b"
)
TEST_CMD = re.compile(
    r"(?i)\b(?:pytest|cargo (?:nextest|test)|npm (?:test|run test\S*)|pnpm test|yarn test"
    r"|vitest|jest|go test|mvn test|make (?:test|check)|verify-mutation-gates)\b"
)
CHECK_CMD = re.compile(r"(?i)\b(?:test|check|verify|campaign|suite)\b")
PIPE_TRUNC = re.compile(r"\|\s*(?:tail|head)\b")
PHANTOM_TOOL_NEAR = re.compile(
    r"(?i)(?:\bprism\b|\blsp\b)(?:(?!\.).){0,160}?"
    r"(?:not (?:exposed|available|mounted|present)|unavailable|falling back|no prism|"
    r"aren'?t available|are not available|do(?:es)? not (?:expose|appear)|isn'?t (?:exposed|available))"
    r"|(?:not (?:exposed|available)|falling back)(?:(?!\.).){0,120}?(?:\bprism\b|\blsp\b)"
)
CLAUDE_WRAPPER = ("<local-command-caveat>", "<command-name>")
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)

KNOWN_INCIDENTS = [
    # (label, detector prefix, session substring)
    ("Opus5 over-claim admissions (stockTrading)", "admission", "fb80415b"),
    ("Opus4.8 admissions incl. tail-8 mea culpa (ssot marathon)", "admission", "608a7a2a"),
    ("tail-8 evidence destruction (ssot marathon)", "pipe_truncated", "608a7a2a"),
    ("r2f 17.6M-token capacity null-final", "null_final", "rollout-2026-07-20T17-49-14"),
    ("sol x acp 0.133.0 PONG spawn death", "null_final", "rollout-2026-07-10T09-23-38"),
    ("apply_patch loop (line-anchored prompts)", "apply_patch_failed", "rollout-2026-07-06T20-58-03"),
    ("post-compact fork 9aea8b01 <- 608a7a2a (ssot marathon)", "lineage_dupe", "9aea8b01"),
]


def snippet_around(text: str, m: re.Match, width: int = 80) -> str:
    lo = max(0, m.start() - width)
    hi = min(len(text), m.end() + width)
    return " ".join(text[lo:hi].split())[:220]


def content_text(message: dict, want_types=("text",)) -> str:
    """Concatenate text-ish blocks of a claude message.content (str or list)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") in want_types:
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
    return "\n".join(parts)


class Rows:
    def __init__(self):
        self.rows: list[dict] = []
        self.counts: Counter = Counter()

    def add(self, corpus, detector, bucket, path, line_no, ts, model, cwd, sidechain, snip):
        self.rows.append({
            "corpus": corpus, "detector": detector, "bucket": bucket,
            "path": str(path).replace(str(HOME), "~"), "session": Path(path).stem,
            "line_no": line_no, "ts": ts, "model": model, "cwd": cwd,
            "sidechain": sidechain, "snippet": snip,
        })
        self.counts[f"{corpus}.{detector}.{bucket}"] += 1


# ---------------------------------------------------------------- claude

def first_content_uuid(path) -> str | None:
    """uuid of the first non-sidechain user/assistant line (early-exit read)."""
    fails = [0]
    for obj in stream_json_lines(path, fails):
        if obj.get("type") in ("user", "assistant") and not obj.get("isSidechain") \
                and isinstance(obj.get("uuid"), str):
            return obj["uuid"]
    return None


def scan_claude(rows: Rows, since_mtime: float | None, limit=None):
    fails = [0]
    admissions_per_session: Counter = Counter()
    files = list(find_claude_main_files(CLAUDE_ROOT))
    if limit:
        files = files[:limit]
    files = [p for p in files
             if since_mtime is None or p.stat().st_mtime >= since_mtime]

    # pre-pass: each file's first content-line uuid; membership of that uuid
    # inside ANOTHER file marks the owner as a copied-lineage fork of it.
    firsts: dict[str, Path] = {}
    for path in files:
        u = first_content_uuid(path)
        if u:
            firsts[u] = path
    fork_pairs: set[tuple[str, str]] = set()  # (child_name, parent_name)

    n_scanned = 0
    for path in files:
        n_scanned += 1
        cwd = None
        model = None
        for line_no, obj in enumerate(stream_json_lines(path, fails), 1):
            uid = obj.get("uuid")
            if isinstance(uid, str) and uid in firsts and firsts[uid] != path \
                    and obj.get("type") in ("user", "assistant") and not obj.get("isSidechain"):
                child = firsts[uid]
                if (child.name, path.name) not in fork_pairs:
                    fork_pairs.add((child.name, path.name))
                    rows.add("claude", "lineage_dupe", "lineage_dupe", child, 1,
                             obj.get("timestamp"), None, path.parent.name, False,
                             f"first content line of {child.name} found at line {line_no} "
                             f"of {path.name} -- copied lineage (post-compact fork/resume)")
            if cwd is None and isinstance(obj.get("cwd"), str):
                cwd = obj["cwd"]
            ltype = obj.get("type")
            if ltype not in ("user", "assistant"):
                continue
            msg = obj.get("message") or {}
            ts = obj.get("timestamp")
            sidechain = bool(obj.get("isSidechain"))

            if ltype == "assistant":
                m_model = msg.get("model")
                if m_model == "<synthetic>":
                    text = content_text(msg)
                    rows.add("claude", "synthetic_error", "synthetic_error", path, line_no,
                             ts, m_model, cwd, sidechain, " ".join(text.split())[:220])
                    continue
                if m_model:
                    model = m_model
                text = content_text(msg)
                if text:
                    m = ADMISSION_STRONG.search(text)
                    if m:
                        rows.add("claude", "admission", "strong", path, line_no, ts, model,
                                 cwd, sidechain, snippet_around(text, m))
                        if not sidechain:
                            admissions_per_session[path.stem] += 1
                    else:
                        m = ADMISSION_WEAK.search(text)
                        if m:
                            rows.add("claude", "admission", "weak", path, line_no, ts, model,
                                     cwd, sidechain, snippet_around(text, m))
                content = msg.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use" \
                                and block.get("name") == "Bash":
                            cmd = (block.get("input") or {}).get("command") or ""
                            if isinstance(cmd, str) and PIPE_TRUNC.search(cmd):
                                if TEST_CMD.search(cmd):
                                    rows.add("claude", "pipe_truncated_test", "test", path,
                                             line_no, ts, model, cwd, sidechain,
                                             " ".join(cmd.split())[:220])
                                elif CHECK_CMD.search(cmd):
                                    rows.add("claude", "pipe_truncated_check", "check", path,
                                             line_no, ts, model, cwd, sidechain,
                                             " ".join(cmd.split())[:220])
            else:  # user
                if obj.get("isMeta") or sidechain:
                    continue  # sidechain "user" turns are orchestrator/tool plumbing, not the human
                text = content_text(msg)
                if not text or any(w in text for w in CLAUDE_WRAPPER):
                    continue
                text = SYSTEM_REMINDER.sub("", text)
                if not text.strip():
                    continue
                m = CORRECTION_STRONG.search(text)
                if m:
                    rows.add("claude", "user_correction", "strong", path, line_no, ts, model,
                             cwd, sidechain, snippet_around(text, m))
                else:
                    m = CORRECTION_WEAK.search(text)
                    if m:
                        rows.add("claude", "user_correction", "weak", path, line_no, ts, model,
                                 cwd, sidechain, snippet_around(text, m))
    fork_groups = sorted(fork_pairs)
    return n_scanned, fails[0], admissions_per_session, fork_groups


# ---------------------------------------------------------------- codex

def _codex_output_text(payload: dict) -> str:
    out = payload.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, dict):
        c = out.get("content")
        return c if isinstance(c, str) else json.dumps(out)[:2000]
    return ""


def scan_codex(rows: Rows, since_date: str | None, limit=None):
    fails = [0]
    patch_fail_per_session: Counter = Counter()
    files = sorted(CODEX_ROOT.rglob("*.jsonl"))
    if limit:
        files = files[:limit]
    n_scanned = 0
    for path in files:
        if since_date is not None:
            # path .../sessions/YYYY/MM/DD/rollout-*.jsonl
            try:
                y, mo, d = path.parts[-4], path.parts[-3], path.parts[-2]
                if f"{y}-{mo}-{d}" < since_date:
                    continue
            except Exception:
                pass
        n_scanned += 1
        cwd = None
        model = None
        had_output = False
        last_total_tokens = None
        for line_no, obj in enumerate(stream_json_lines(path, fails), 1):
            ts = obj.get("timestamp")
            ltype = obj.get("type")
            payload = obj.get("payload") or {}
            if ltype == "session_meta":
                c = payload.get("cwd")
                if isinstance(c, str):
                    cwd = c
                continue
            if ltype == "turn_context":
                m = payload.get("model")
                if isinstance(m, str):
                    model = m
                continue
            if ltype == "event_msg":
                ptype = payload.get("type")
                if ptype == "token_count":
                    info = payload.get("info") or {}
                    tu = info.get("total_token_usage") or {}
                    t = tu.get("total_tokens")
                    if isinstance(t, int):
                        last_total_tokens = t
                elif ptype == "agent_message":
                    text = payload.get("message")
                    if isinstance(text, str) and text.strip():
                        had_output = True
                        m = ADMISSION_STRONG.search(text)
                        if m:
                            rows.add("codex", "admission", "strong", path, line_no, ts, model,
                                     cwd, False, snippet_around(text, m))
                        m = PHANTOM_TOOL_NEAR.search(text)
                        if m:
                            rows.add("codex", "phantom_tool_fallback", "phantom", path, line_no,
                                     ts, model, cwd, False, snippet_around(text, m))
                elif ptype == "user_message":
                    text = payload.get("message")
                    if isinstance(text, str):
                        m = CORRECTION_STRONG.search(text)
                        if m:
                            rows.add("codex", "user_correction", "strong", path, line_no, ts,
                                     model, cwd, False, snippet_around(text, m))
                elif ptype == "task_complete":
                    lam = payload.get("last_agent_message")
                    if lam is None or (isinstance(lam, str) and not lam.strip()):
                        bucket = "after_output" if had_output else "zero_output"
                        snip = f"task_complete with empty last_agent_message; had_output={had_output}"
                        if last_total_tokens is not None:
                            snip += f"; last_total_tokens={last_total_tokens}"
                        rows.add("codex", "null_final", bucket, path, line_no, ts, model,
                                 cwd, False, snip)
                continue
            if ltype == "response_item":
                ptype = payload.get("type")
                if ptype in ("function_call_output", "custom_tool_call_output"):
                    out_text = _codex_output_text(payload)
                    if "apply_patch verification failed" in out_text:
                        rows.add("codex", "apply_patch_failed", "failed", path, line_no, ts,
                                 model, cwd, False, " ".join(out_text.split())[:220])
                        patch_fail_per_session[path.name] += 1
                elif ptype == "message" and payload.get("role") == "assistant":
                    # belt-and-braces alongside agent_message (indexer found them 1:1)
                    for block in payload.get("content") or []:
                        if isinstance(block, dict) and isinstance(block.get("text"), str):
                            had_output = had_output or bool(block["text"].strip())
    return n_scanned, fails[0], patch_fail_per_session


# ---------------------------------------------------------------- report

def month_series(rows: Rows, corpus: str, detector: str, month="2026-07"):
    days: Counter = Counter()
    for r in rows.rows:
        if r["corpus"] == corpus and r["detector"] == detector and r["ts"] and r["ts"].startswith(month):
            days[r["ts"][:10]] += 1
    return dict(sorted(days.items()))


def main():
    ap = argparse.ArgumentParser(description="Failure-signature detector (Wave 0)")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; filter codex by path date, claude by mtime")
    ap.add_argument("--limit", type=int, default=None, help="debug: only N files per corpus")
    args = ap.parse_args()

    since_mtime = None
    if args.since:
        since_mtime = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()

    rows = Rows()
    c_files, c_bad, admissions_per_session, fork_groups = scan_claude(rows, since_mtime, args.limit)
    x_files, x_bad, patch_fails = scan_codex(rows, args.since, args.limit)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sig_path = OUT_DIR / "failure_signatures.jsonl"
    with open(sig_path, "w", encoding="utf-8") as f:
        for r in rows.rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    recurrence = {s: n for s, n in admissions_per_session.items() if n >= 2}
    loops = {s: n for s, n in patch_fails.items() if n >= 3}

    # known-incident validation
    validations = []
    for label, det_prefix, session_sub in KNOWN_INCIDENTS:
        hit = any(r for r in rows.rows
                  if r["detector"].startswith(det_prefix) and session_sub in r["session"])
        validations.append((label, det_prefix, session_sub, hit))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Failure-signature baseline",
        "",
        f"Generated {now} by `mining/scripts/detect_failure_signatures.py`"
        f"{' --since ' + args.since if args.since else ''}. "
        f"Scanned {c_files} claude main sessions ({c_bad} bad lines), "
        f"{x_files} codex rollouts ({x_bad} bad lines). "
        f"{len(rows.rows)} incident rows -> `mining/out/failure_signatures.jsonl`.",
        "",
        "## Counts by detector",
        "",
        "| detector | count |",
        "|---|---|",
    ]
    for key, n in sorted(rows.counts.items()):
        lines.append(f"| {key} | {n} |")

    lines += [
        "",
        "## Known-incident validation (forensics 2026-07-25 ground truth)",
        "",
        "| incident | detector | session | found |",
        "|---|---|---|---|",
    ]
    for label, det, sub, hit in validations:
        lines.append(f"| {label} | {det} | {sub} | {'YES' if hit else '**MISSING**'} |")

    lines += [
        "",
        "## Recurrence-after-admission (sessions with >=2 strong main-thread admissions)",
        "",
        f"{len(recurrence)} sessions. Top 10:",
        "",
    ]
    for s, n in sorted(recurrence.items(), key=lambda kv: -kv[1])[:10]:
        lines.append(f"- {s}: {n} strong admissions")

    lines += ["", "## apply_patch loop sessions (>=3 failures)", ""]
    for s, n in sorted(loops.items(), key=lambda kv: -kv[1])[:15]:
        lines.append(f"- {s}: {n} failures")
    if not loops:
        lines.append("- none")

    lines += ["", "## Copied-lineage sessions (fork begins inside parent; dedupe before rate math)", ""]
    for child, parent in fork_groups[:20]:
        lines.append(f"- {child} forked from {parent}")
    if not fork_groups:
        lines.append("- none")

    lines += ["", "## July 2026 daily series (key detectors)", ""]
    for corpus, det in [("claude", "admission"), ("claude", "user_correction"),
                        ("claude", "pipe_truncated_test"), ("claude", "pipe_truncated_check"),
                        ("codex", "null_final"), ("codex", "apply_patch_failed"),
                        ("codex", "phantom_tool_fallback")]:
        series = month_series(rows, corpus, det)
        if series:
            pts = ", ".join(f"{d[8:]}:{n}" for d, n in series.items())
            lines.append(f"- **{corpus}.{det}** (day:count): {pts}")

    lines += [
        "",
        "## Notes",
        "",
        "- `admission`/`user_correction` are incident MARKERS for triage, not verdicts; "
        "snippets carry the context.",
        "- Weak buckets are deliberately noisy; headline rates should use strong buckets only.",
        "- `<synthetic>` rows are API-error turns (session-health signal, not a model failure).",
        "- Wave-1+ mitigation effects should be read against the strong-bucket July rates above.",
    ]
    (OUT_DIR / "failure_baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # standing triage queue: strong-signal incidents, most recent first, capped.
    nl = [
        "# Failure-signature triage queue",
        "",
        f"Generated {now} by `mining/scripts/detect_failure_signatures.py`. Strong-signal",
        "incidents only, most recent first. Triage: read the snippet in context; if it marks a",
        "real steering/enforcement gap, promote it to TRACKER.md as an experiment or wave item;",
        "if benign (quotation, template artifact), skip. These are markers, not verdicts.",
        "",
    ]
    for corpus, det, buckets, cap in [
        ("claude", "admission", ("strong",), 15),
        ("claude", "user_correction", ("strong",), 15),
        ("codex", "null_final", None, 15),
        ("codex", "apply_patch_failed", None, 10),
        ("codex", "phantom_tool_fallback", None, 10),
        ("claude", "pipe_truncated_test", None, 10),
        ("claude", "lineage_dupe", None, 10),
    ]:
        rs = [r for r in rows.rows
              if r["corpus"] == corpus and r["detector"] == det
              and (buckets is None or r["bucket"] in buckets)]
        rs.sort(key=lambda r: r["ts"] or "", reverse=True)
        nl.append(f"## {corpus}.{det} — {len(rs)} total, showing {min(cap, len(rs))}")
        nl.append("")
        for r in rs[:cap]:
            ts = (r["ts"] or "?")[:16]
            nl.append(f"- [ ] {ts} `{r['session'][:24]}` L{r['line_no']} "
                      f"({r['model'] or '?'} @ {r['cwd'] or '?'}): {r['snippet'][:160]}")
        nl.append("")
    (OUT_DIR / "failure_nominations.md").write_text("\n".join(nl) + "\n", encoding="utf-8")
    print(f"wrote {sig_path} ({len(rows.rows)} rows), failure_baseline.md, failure_nominations.md")
    missing = [v for v in validations if not v[3]]
    if missing:
        print(f"WARNING: {len(missing)} known incidents NOT detected: {[m[0] for m in missing]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
