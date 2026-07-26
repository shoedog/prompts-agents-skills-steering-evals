#!/usr/bin/env python3
"""SUCCESS-signature detector over the two local transcript corpora -- the
dual of detect_failure_signatures.py, for the owner-approved success-mode
program (operationalize what WORKS, not just what fails).

Purpose: turn "what went right" from anecdote into a standing, re-runnable
detector that emits labeled incident streams (for TRACKER success-mode
nominations) and a baseline report, so practices worth operationalizing can
be found, counted, and promoted into artifacts (steering lines, hooks,
skills, workflow nodes).

Reads (streaming, never whole-file):
  ~/.claude/projects/<proj>/<session>.jsonl   (main sessions, via build_index.find_claude_main_files)
  ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl

Emits:
  mining/out/success_signatures.jsonl  -- one row per incident (same schema
      as failure_signatures.jsonl):
      {corpus, detector, bucket, path, session, line_no, ts, model, cwd,
       sidechain, snippet}
  mining/out/success_baseline.md       -- counts, known-incident validation
      table, checkpoint-cadence session list, July-2026 daily series, notes.
  mining/out/success_nominations.md    -- strong-signal triage checklist,
      most recent first, one row per session per detector, capped.

Within a detector, buckets are tried strongest-first and the first match wins
per message (failure-side admission strong/weak parity); the July daily
series uses strong buckets only.

Philosophy (copied from the failure side): HIGH-PRECISION v1 -- a noisy
metric is worse than none. Strong buckets headline; anything fuzzy is
excluded or clearly bucketed weak. These are triage MARKERS, not verdicts.

One honest caveat, load-bearing for triage: a success marker in an
ORCHESTRATOR session often NARRATES a subagent's act rather than enacting it
(e.g. a subagent's "ADJUDICATED FALSE" arrives inside a tool_result -- which
this detector deliberately does NOT scan, tool_results being other-agent
content -- and the orchestrator then narrates it in its own prose as
"1 refuted"). Triage reads snippets in context before promoting anything.

Detectors (assistant text in both corpora unless stated):

  attribution_control   base-control-before-blame ENACTED: "base <sha> fails
                        identically", "base-control", "attribution control",
                        "latent since", "reproduced at base/main/HEAD~".
                        prose_weak: "not a ... regression", "pre-existing
                        bug/failure" (claim-shaped; may lack the control run).
  refutation_accepted   a claim tested against evidence and overturned, the
                        overturning ACCEPTED into the record: "refuted",
                        "adjudicated false", "disproved", "overturned my/the",
                        "attribution corrected". Negation-guarded ("no label
                        refutations" does NOT count).
  cap_honored           convergence cap declared/honored -- churn stopped by
                        policy, not exhaustion: "round N is the cap",
                        "convergence cap/contract", "held for owner", "parked
                        at the cap". prose_weak: "stop(ped) retrying",
                        "escalate to spec/design/owner" (also common in
                        ordinary retry-logic code talk). Claude corpus ALSO
                        scans assistant-authored Edit/Write content (bucket
                        authored_doc): cap declarations canonically live in
                        coordination docs (HANDOFF files), where writing the
                        cap IS the enactment.
  provenance_disclosed  post-hoc/operator authorship disclosed to reviewers
                        rather than laundered: "operator-authored",
                        "provenance-tier/-disclosed", "disclosed degradation",
                        "scrutinize the post-hoc", "spec-authorship error".
                        prose_weak: "provenance mark*" (also ordinary
                        data-lineage engineering talk; sampled collisions in
                        slicing/ssot design sessions).
  expect_falsify_probe  prediction-before-probe debugging discipline:
                        requires "falsif*" AND one of hypothes/probe/expect/
                        predict within +-400 chars of it in the same message
                        (co-occurrence keeps this precise). Sampling shows the
                        codex hits are GENUINE enactments but saturated: the
                        owner's exp-3 debugging steering makes this routine in
                        stockTrading/ssot-agents gpt-5.5 sessions, so its row
                        count measures steering ADOPTION, not incidents --
                        read the baseline's sessions column.
  checkpoint_cadence    SESSION-LEVEL, claude corpus only: count of
                        Edit/Write/MultiEdit tool_use blocks whose
                        input.file_path matches /HANDOFF|CHECKPOINT/i; ONE
                        row per session with >=3 such edits, count in the
                        snippet (sidechain edits included -- the file edit is
                        real either way).

NOTE on self-matching: several pattern literals below are written with
character classes ("held[ ]for[ ]owner") so that THIS FILE's own source --
which enters the claude corpus as Write/Edit tool_use content whenever a
session edits it -- can never match its own patterns via the authored_doc
scan. Prose that QUOTES these phrases (reports about this very program) can
still match; that is exactly the narration case triage is taught to skip.

Validation ground truth (all from session 782c0297-efe4-408f-9b1a-
07346a6a6c30, the 2026-07-25 failure->success-mode program session, in
~/.claude/projects/-Users-wesleyjinks/). SELF-REFERENTIAL caveat: that
session is the very session that NAMED these patterns -- it both enacts and
narrates them, so it over-represents every detector; it is a detector
regression check, not a typicality claim. Verified against the raw file
2026-07-25 before writing the detector:
  attribution_control  "base `e8ed61f` fails identically" (3 assistant text
                       hits) and "latent since `e159915`" (1) -- both prose.
  refutation_accepted  assistant prose "one refuted"/"1 refuted" (the
                       literal "ADJUDICATED FALSE" lives in a subagent
                       tool_result, which is deliberately not scanned; the
                       orchestrator's own narration is the prose hit).
  cap_honored          "ROUND 3 IS THE CAP" and "HELD FOR OWNER" live in
                       Edit new_string (HANDOFF doc) => authored_doc bucket;
                       "convergence cap/contract"/"parked at the cap" also
                       appear in plain prose.
  provenance_disclosed "operator-authored" (prose, 1), "disclosed
                       degradation" (prose, 1).
  checkpoint_cadence   42 Edit/Write calls on ~/Documents/HANDOFF-2026-07-25-
                       failure-mode-program.md -- qualifies at >=3.

Usage:
  python3 mining/scripts/detect_success_signatures.py            # full corpora
  python3 mining/scripts/detect_success_signatures.py --since 2026-06-01
  (--since filters codex files by path date and claude files by mtime; rows
   always carry their own ts, so the baseline slices July regardless.)

Exits 1 with a WARNING on stderr if any known incident goes undetected
(detector regression, not corpus change).
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

ATTRIB_STRONG = re.compile(
    r"(?i)\bbase[- ]control\b"
    r"|\battribution[- ]control\b"
    r"|\bbase\b[^\n]{0,40}?\bfails? identically\b"
    r"|\bfails? (?:the same|identically) (?:at|on|in|against) (?:base\b|main\b|HEAD~\d*)"
    r"|\blatent[ ]since\b"
    r"|\breproduce[sd]? (?:at|on) (?:base\b|main\b|HEAD~)"
)
ATTRIB_WEAK = re.compile(
    r"(?i)\bnot a (?:[\w-]{1,24} )?regression\b(?!\s+test)"
    r"|\bpre[- ]existing (?:failure|bug|breakage|defect)\b"
)
REFUT = re.compile(
    r"(?i)\brefut(?:ed|es|ation|ations)\b"
    r"|\badjudicated (?:false|true)\b"
    r"|\bdisprov(?:ed|en)\b"
    r"|\bover-?turn(?:ed|s)? (?:my|the|that|this)\b"
    r"|\battribution[ ]corrected\b"
)
# "no label refutations" / "without refutation" / "could not refute" /
# "neither confirms nor refutes" are the OPPOSITE event; a small
# preceding-context guard keeps them out (tuned on sampled false positives).
REFUT_NEG_GUARD = re.compile(
    r"(?i)(?:\b(?:no|zero|not|without|never|cannot|neither|nor)\b|n[o']t\b)[\w\s,'-]{0,20}$"
)
CAP_STRONG = re.compile(
    r"(?i)\bround \d+ is the cap\b"
    r"|\bconvergence (?:cap|contract)\b"
    r"|\bheld[ ]for[ ]owner\b"
    r"|\bparked at (?:the )?(?:convergence )?cap\b"
)
CAP_WEAK = re.compile(
    r"(?i)\bstop(?:ped)? retrying\b"
    r"|\bescalat\w{0,3} to (?:spec\b|design\b|the owner\b|owner\b)"
)
PROV = re.compile(
    r"(?i)\boperator[- ]authored\b"
    r"|\bprovenance[- ](?:tier\w*|disclos\w+)\b"
    r"|\bdisclosed[- ]degradation\b"
    r"|\bscrutinize (?:the )?post[- ]hoc\b"
    r"|\bauthorship (?:named|disclosed)\b"
    r"|\bspec[- ]authorship error\b"
)
# "provenance-marked commit" IS authorship disclosure, but "provenance
# markers/marks" is also ordinary DATA-lineage engineering talk (observed in
# slicing/ssot-agents design sessions) -- polysemous, so bucketed weak.
PROV_WEAK = re.compile(r"(?i)\bprovenance[- ]mark\w+")
FALSIF = re.compile(r"(?i)falsif")
FALSIF_NEAR = re.compile(r"(?i)hypothes|probe|expect|predict")
FALSIF_WINDOW = 400
HANDOFF_PATH = re.compile(r"(?i)HANDOFF|CHECKPOINT")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit")

KNOWN_INCIDENTS = [
    # (label, detector prefix, session substring, snippet regex or None)
    ("base-control enacted: 'base e8ed61f fails identically' (program session)",
     "attribution_control", "782c0297", re.compile(r"(?i)fails? identically")),
    ("attribution 'latent since e159915' (program session)",
     "attribution_control", "782c0297", re.compile(r"(?i)latent[ ]since")),
    ("refutation accepted into record ('1 refuted'; ADJUDICATED FALSE narrated)",
     "refutation_accepted", "782c0297", None),
    ("cap declared: 'ROUND 3 IS THE CAP' (HANDOFF authored_doc)",
     "cap_honored", "782c0297", re.compile(r"(?i)round \d+ is the cap")),
    ("cap honored: 'held for owner' (HANDOFF authored_doc)",
     "cap_honored", "782c0297", re.compile(r"(?i)held[ ]for[ ]owner")),
    ("provenance disclosed: 'operator-authored'",
     "provenance_disclosed", "782c0297", re.compile(r"(?i)operator[- ]authored")),
    ("provenance: 'disclosed degradation'",
     "provenance_disclosed", "782c0297", re.compile(r"(?i)disclosed[- ]degradation")),
    ("checkpoint cadence >=3 HANDOFF edits (42 observed 2026-07-25)",
     "checkpoint_cadence", "782c0297", None),
]

# Per detector, buckets tried in order; first bucket that matches wins for a
# given message (strong-else-weak, same semantics as the failure side's
# admission strong/weak). Applied to assistant prose in BOTH corpora.
PROSE_DETECTORS = [
    ("attribution_control", [(ATTRIB_STRONG, "prose"), (ATTRIB_WEAK, "prose_weak")]),
    ("refutation_accepted", [(REFUT, "prose")]),
    ("cap_honored", [(CAP_STRONG, "prose"), (CAP_WEAK, "prose_weak")]),
    ("provenance_disclosed", [(PROV, "prose"), (PROV_WEAK, "prose_weak")]),
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


def refut_match(text: str) -> re.Match | None:
    """First REFUT match whose preceding ~26 chars are not a negation."""
    for m in REFUT.finditer(text):
        if not REFUT_NEG_GUARD.search(text[max(0, m.start() - 26):m.start()]):
            return m
    return None


def falsify_match(text: str) -> re.Match | None:
    """First 'falsif*' with hypothes/probe/expect/predict within the window."""
    for m in FALSIF.finditer(text):
        lo = max(0, m.start() - FALSIF_WINDOW)
        hi = min(len(text), m.end() + FALSIF_WINDOW)
        if FALSIF_NEAR.search(text[lo:hi]):
            return m
    return None


class Rows:
    def __init__(self):
        self.rows: list[dict] = []
        self.counts: Counter = Counter()
        self.key_sessions: dict[str, set] = {}

    def add(self, corpus, detector, bucket, path, line_no, ts, model, cwd, sidechain, snip):
        session = Path(path).stem
        self.rows.append({
            "corpus": corpus, "detector": detector, "bucket": bucket,
            "path": str(path).replace(str(HOME), "~"), "session": session,
            "line_no": line_no, "ts": ts, "model": model, "cwd": cwd,
            "sidechain": sidechain, "snippet": snip,
        })
        key = f"{corpus}.{detector}.{bucket}"
        self.counts[key] += 1
        self.key_sessions.setdefault(key, set()).add(session)


def scan_prose(rows: Rows, corpus, text, path, line_no, ts, model, cwd, sidechain):
    """Apply every prose detector to one assistant message text: at most one
    row per detector per message, strongest bucket wins (failure-side parity)."""
    if not text:
        return
    for detector, buckets in PROSE_DETECTORS:
        for pat, bucket in buckets:
            m = pat.search(text)
            if m and detector == "refutation_accepted":
                m = refut_match(text)
            if m:
                rows.add(corpus, detector, bucket, path, line_no, ts, model,
                         cwd, sidechain, snippet_around(text, m))
                break
    m = falsify_match(text)
    if m:
        rows.add(corpus, "expect_falsify_probe", "prose", path, line_no, ts,
                 model, cwd, sidechain, snippet_around(text, m))


def authored_texts(block: dict):
    """Assistant-authored document content from an Edit/Write/MultiEdit
    tool_use block (the content the assistant is writing, NOT tool results)."""
    inp = block.get("input") or {}
    name = block.get("name")
    if name == "Write":
        v = inp.get("content")
        if isinstance(v, str):
            yield v
    elif name == "Edit":
        v = inp.get("new_string")
        if isinstance(v, str):
            yield v
    elif name == "MultiEdit":
        for e in inp.get("edits") or []:
            if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                yield e["new_string"]


# ---------------------------------------------------------------- claude

def scan_claude(rows: Rows, since_mtime: float | None, limit=None):
    fails = [0]
    checkpoint_edits: Counter = Counter()          # session stem -> n edits
    checkpoint_meta: dict[str, dict] = {}          # session stem -> row context
    files = list(find_claude_main_files(CLAUDE_ROOT))
    if limit:
        files = files[:limit]
    files = [p for p in files
             if since_mtime is None or p.stat().st_mtime >= since_mtime]

    n_scanned = 0
    for path in files:
        n_scanned += 1
        cwd = None
        model = None
        for line_no, obj in enumerate(stream_json_lines(path, fails), 1):
            if cwd is None and isinstance(obj.get("cwd"), str):
                cwd = obj["cwd"]
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message") or {}
            ts = obj.get("timestamp")
            sidechain = bool(obj.get("isSidechain"))
            m_model = msg.get("model")
            if m_model == "<synthetic>":
                continue
            if m_model:
                model = m_model

            scan_prose(rows, "claude", content_text(msg), path, line_no, ts,
                       model, cwd, sidechain)

            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                if block.get("name") not in EDIT_TOOLS:
                    continue
                # checkpoint_cadence: session-level edit counter
                fp = (block.get("input") or {}).get("file_path")
                if isinstance(fp, str) and HANDOFF_PATH.search(fp):
                    stem = path.stem
                    checkpoint_edits[stem] += 1
                    meta = checkpoint_meta.setdefault(stem, {
                        "path": path, "first_line": line_no, "cwd": cwd,
                        "paths": set(),
                    })
                    meta["last_ts"] = ts
                    meta["model"] = model or meta.get("model")
                    meta["cwd"] = meta.get("cwd") or cwd
                    meta["paths"].add(fp.replace(str(HOME), "~"))
                # cap_honored over assistant-authored doc content
                for text in authored_texts(block):
                    m = CAP_STRONG.search(text)
                    if m:
                        rows.add("claude", "cap_honored", "authored_doc", path,
                                 line_no, ts, model, cwd, sidechain,
                                 snippet_around(text, m))

    for stem, n in checkpoint_edits.items():
        if n < 3:
            continue
        meta = checkpoint_meta[stem]
        paths = sorted(meta["paths"])
        shown = ", ".join(paths[:2]) + (f" (+{len(paths)-2} more)" if len(paths) > 2 else "")
        rows.add("claude", "checkpoint_cadence", "session", meta["path"],
                 meta["first_line"], meta.get("last_ts"), meta.get("model"),
                 meta["cwd"], False,
                 f"{n} Edit/Write tool_use calls on HANDOFF/CHECKPOINT paths: {shown}"[:220])
    qualifying = {s: n for s, n in checkpoint_edits.items() if n >= 3}
    return n_scanned, fails[0], qualifying, checkpoint_meta


# ---------------------------------------------------------------- codex

def scan_codex(rows: Rows, since_date: str | None, limit=None):
    fails = [0]
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
        for line_no, obj in enumerate(stream_json_lines(path, fails), 1):
            ts = obj.get("timestamp")
            ltype = obj.get("type")
            payload = obj.get("payload") or {}
            if ltype == "session_meta":
                c = payload.get("cwd")
                if isinstance(c, str):
                    cwd = c
            elif ltype == "turn_context":
                m = payload.get("model")
                if isinstance(m, str):
                    model = m
            elif ltype == "event_msg" and payload.get("type") == "agent_message":
                text = payload.get("message")
                if isinstance(text, str) and text.strip():
                    scan_prose(rows, "codex", text, path, line_no, ts, model, cwd, False)
    return n_scanned, fails[0]


# ---------------------------------------------------------------- report

STRONG_BUCKETS = ("prose", "authored_doc", "session")


def month_series(rows: Rows, corpus: str, detector: str, month="2026-07",
                 buckets=STRONG_BUCKETS):
    days: Counter = Counter()
    for r in rows.rows:
        if r["corpus"] == corpus and r["detector"] == detector \
                and r["bucket"] in buckets \
                and r["ts"] and r["ts"].startswith(month):
            days[r["ts"][:10]] += 1
    return dict(sorted(days.items()))


def main():
    ap = argparse.ArgumentParser(description="Success-signature detector (success-mode program)")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; filter codex by path date, claude by mtime")
    ap.add_argument("--limit", type=int, default=None, help="debug: only N files per corpus")
    args = ap.parse_args()

    since_mtime = None
    if args.since:
        since_mtime = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()

    rows = Rows()
    c_files, c_bad, checkpoint_sessions, checkpoint_meta = scan_claude(rows, since_mtime, args.limit)
    x_files, x_bad = scan_codex(rows, args.since, args.limit)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sig_path = OUT_DIR / "success_signatures.jsonl"
    with open(sig_path, "w", encoding="utf-8") as f:
        for r in rows.rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # known-incident validation
    validations = []
    for label, det_prefix, session_sub, snip_re in KNOWN_INCIDENTS:
        hit = any(r for r in rows.rows
                  if r["detector"].startswith(det_prefix) and session_sub in r["session"]
                  and (snip_re is None or snip_re.search(r["snippet"])))
        validations.append((label, det_prefix, session_sub, hit))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Success-signature baseline",
        "",
        f"Generated {now} by `mining/scripts/detect_success_signatures.py`"
        f"{' --since ' + args.since if args.since else ''}. "
        f"Scanned {c_files} claude main sessions ({c_bad} bad lines), "
        f"{x_files} codex rollouts ({x_bad} bad lines). "
        f"{len(rows.rows)} incident rows -> `mining/out/success_signatures.jsonl`.",
        "",
        "Dual of `failure_baseline.md`: these are markers of practices that WORKED",
        "(controls run before blame, refutations accepted, caps honored, provenance",
        "disclosed, prediction-first probes, checkpoint discipline), mined so they can",
        "be operationalized -- not victory laps.",
        "",
        "## Counts by detector",
        "",
        "(rows = matched messages; sessions = distinct sessions containing one.",
        "When steering makes a practice routine, rows measure compliance volume --",
        "read the sessions column for spread.)",
        "",
        "| detector | rows | sessions |",
        "|---|---|---|",
    ]
    for key, n in sorted(rows.counts.items()):
        lines.append(f"| {key} | {n} | {len(rows.key_sessions.get(key, ()))} |")

    lines += [
        "",
        "## Known-incident validation (2026-07-25 program-session ground truth)",
        "",
        "| incident | detector | session | found |",
        "|---|---|---|---|",
    ]
    for label, det, sub, hit in validations:
        lines.append(f"| {label} | {det} | {sub} | {'YES' if hit else '**MISSING**'} |")
    lines += [
        "",
        "SELF-REFERENTIAL caveat: session 782c0297 is the 2026-07-25 program session",
        "that NAMED these patterns -- it both enacts and narrates them, so it",
        "over-represents every detector. The table is a detector regression check",
        "(exit 1 if a row goes MISSING), not evidence the practices are widespread.",
    ]

    lines += [
        "",
        "## Checkpoint-cadence sessions (>=3 Edit/Write calls on HANDOFF/CHECKPOINT paths)",
        "",
        f"{len(checkpoint_sessions)} sessions. Top 15:",
        "",
    ]
    for s, n in sorted(checkpoint_sessions.items(), key=lambda kv: -kv[1])[:15]:
        cwd = (checkpoint_meta.get(s) or {}).get("cwd") or "?"
        lines.append(f"- {s}: {n} edits ({cwd})")
    if not checkpoint_sessions:
        lines.append("- none")

    lines += ["", "## July 2026 daily series (key detectors, strong buckets only)", ""]
    for corpus, det in [("claude", "attribution_control"), ("claude", "refutation_accepted"),
                        ("claude", "cap_honored"), ("claude", "provenance_disclosed"),
                        ("claude", "expect_falsify_probe"), ("claude", "checkpoint_cadence"),
                        ("codex", "attribution_control"), ("codex", "refutation_accepted"),
                        ("codex", "cap_honored"), ("codex", "provenance_disclosed"),
                        ("codex", "expect_falsify_probe")]:
        series = month_series(rows, corpus, det)
        if series:
            pts = ", ".join(f"{d[8:]}:{n}" for d, n in series.items())
            lines.append(f"- **{corpus}.{det}** (day:count): {pts}")

    lines += [
        "",
        "## Notes",
        "",
        "- These are success MARKERS for triage, not verdicts; snippets carry the context.",
        "- ADOPTION vs DISCOVERY: `codex.expect_falsify_probe` is dominated by",
        "  stockTrading/ssot-agents gpt-5.5 sessions enacting the owner's exp-3",
        "  expect/falsify debugging steering in nearly every message (verified by",
        "  sampling: genuine enactments, not regex noise). At that saturation the row",
        "  count measures steering ADOPTION, not notable incidents -- read its",
        "  sessions column, and note the nominations queue dedupes to one row per",
        "  session.",
        "- NARRATION caveat: an orchestrator session often narrates a SUBAGENT's act",
        "  rather than enacting it (subagent reports arrive as tool_results, which are",
        "  deliberately not scanned; the orchestrator's own prose narration is what",
        "  matches). Read the snippet in context before promoting.",
        "- `prose_weak` buckets (not-a-regression / pre-existing claims without a shown",
        "  control; stop-retrying / escalate-to phrasing that also occurs in ordinary",
        "  retry-logic code talk) are deliberately noisy; headline rates use strong",
        "  buckets only.",
        "- `authored_doc` (cap_honored only) scans assistant-authored Edit/Write content:",
        "  cap declarations canonically live in coordination docs (HANDOFF files).",
        "  Repeated edits of the same doc re-count the same declaration -- treat as",
        "  presence, not intensity.",
        "- checkpoint_cadence is one row per qualifying session (>=3 HANDOFF/CHECKPOINT",
        "  edits), count in the snippet; sidechain edits included.",
        "- Ground truth is self-referential (see validation section); later program",
        "  sessions that DISCUSS these patterns will also self-hit. Triage skips",
        "  narration/quotation; the detector does not try to.",
    ]
    (OUT_DIR / "success_baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # standing triage queue: strong-signal incidents, most recent first, capped.
    nl = [
        "# Success-signature triage queue",
        "",
        f"Generated {now} by `mining/scripts/detect_success_signatures.py`. Strong-signal",
        "incidents only, most recent first. Triage: read the snippet in context; if it",
        "marks a REPEATABLE practice worth operationalizing, promote it to TRACKER.md's",
        "success-mode section as a candidate artifact (steering line, hook, skill,",
        "workflow node); if it is mere narration/quotation (an orchestrator retelling a",
        "subagent's act, a report about this program, a pasted pattern list), skip.",
        "These are markers, not verdicts. Each section shows at most ONE row per",
        "session (the most recent) so steering-saturated sessions can't flood the",
        "queue; the full per-message stream is in success_signatures.jsonl.",
        "",
    ]
    for corpus, det, buckets, cap in [
        ("claude", "attribution_control", ("prose",), 15),
        ("claude", "refutation_accepted", ("prose",), 15),
        ("claude", "cap_honored", ("prose", "authored_doc"), 15),
        ("claude", "provenance_disclosed", ("prose",), 15),
        ("claude", "expect_falsify_probe", ("prose",), 15),
        ("claude", "checkpoint_cadence", None, 15),
        ("codex", "attribution_control", ("prose",), 10),
        ("codex", "refutation_accepted", ("prose",), 10),
        ("codex", "cap_honored", ("prose",), 10),
        ("codex", "provenance_disclosed", ("prose",), 10),
        ("codex", "expect_falsify_probe", ("prose",), 10),
    ]:
        rs = [r for r in rows.rows
              if r["corpus"] == corpus and r["detector"] == det
              and (buckets is None or r["bucket"] in buckets)]
        rs.sort(key=lambda r: r["ts"] or "", reverse=True)
        n_all = len(rs)
        seen_sessions: set[str] = set()
        deduped = []
        for r in rs:
            if r["session"] in seen_sessions:
                continue
            seen_sessions.add(r["session"])
            deduped.append(r)
        rs = deduped
        nl.append(f"## {corpus}.{det} — {n_all} rows in {len(rs)} sessions, "
                  f"showing {min(cap, len(rs))}")
        nl.append("")
        for r in rs[:cap]:
            ts = (r["ts"] or "?")[:16]
            nl.append(f"- [ ] {ts} `{r['session'][:24]}` L{r['line_no']} [{r['bucket']}] "
                      f"({r['model'] or '?'} @ {r['cwd'] or '?'}): {r['snippet'][:160]}")
        nl.append("")
    (OUT_DIR / "success_nominations.md").write_text("\n".join(nl) + "\n", encoding="utf-8")
    print(f"wrote {sig_path} ({len(rows.rows)} rows), success_baseline.md, success_nominations.md")
    missing = [v for v in validations if not v[3]]
    if missing:
        print(f"WARNING: {len(missing)} known incidents NOT detected: {[m[0] for m in missing]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
