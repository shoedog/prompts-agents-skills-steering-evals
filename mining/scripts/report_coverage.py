#!/usr/bin/env python3
"""Reads the claude/codex session indexes built by build_index.py and writes
mining/out/coverage.md: cross-tabs and Fable-5-specific coverage numbers used
to (a) find matched Fable-vs-other sessions per task type/project, (b) find
sessions with strong outcome signals for benchmark extraction, and (c)
answer "which task types lack Fable coverage".

primary_model for a session = the model with the most MAIN-session assistant
turns in that row's `models` dict (ties broken lexically by model id for
determinism). Sessions with an empty `models` dict (no real-model assistant
turns at all -- e.g. degenerate stub sessions, or sessions where every
assistant turn was a "<synthetic>" error placeholder) have no primary_model
and are reported separately rather than silently dropped.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "mining" / "out"

FABLE_MODEL = "claude-fable-5"

TASK_TYPES = [
    "implement", "debug", "review", "plan_design", "research_analysis",
    "refactor", "infra_config", "writing_docs", "data_analysis",
    "orchestration", "eval_harness", "probe_check", "other",
]


def primary_model(row):
    models = row.get("models") or {}
    if not models:
        return None
    return max(models.items(), key=lambda kv: (kv[1], kv[0]))[0]


def load_rows(path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def fmt_table(headers, rows):
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def main():
    claude_rows = load_rows(OUT_DIR / "claude_index.jsonl")
    codex_rows = load_rows(OUT_DIR / "codex_index.jsonl")
    all_rows = claude_rows + codex_rows

    for r in all_rows:
        r["_primary_model"] = primary_model(r)

    no_model_rows = [r for r in all_rows if r["_primary_model"] is None]
    modeled_rows = [r for r in all_rows if r["_primary_model"] is not None]

    # --- task_type x primary_model: session counts + total assistant turns ---
    models_seen = sorted({r["_primary_model"] for r in modeled_rows})
    count_tab = defaultdict(lambda: defaultdict(int))
    turns_tab = defaultdict(lambda: defaultdict(int))
    for r in modeled_rows:
        tt = r.get("task_type", "other")
        m = r["_primary_model"]
        count_tab[tt][m] += 1
        turns_tab[tt][m] += r.get("n_assistant_turns", 0)

    count_rows = []
    turns_rows = []
    for tt in TASK_TYPES:
        count_rows.append([tt] + [count_tab[tt].get(m, 0) for m in models_seen] + [sum(count_tab[tt].values())])
        turns_rows.append([tt] + [turns_tab[tt].get(m, 0) for m in models_seen] + [sum(turns_tab[tt].values())])
    count_rows.append(["TOTAL"] + [sum(count_tab[tt].get(m, 0) for tt in TASK_TYPES) for m in models_seen] + [len(modeled_rows)])
    turns_rows.append(["TOTAL"] + [sum(turns_tab[tt].get(m, 0) for tt in TASK_TYPES) for m in models_seen] + [sum(sum(v.values()) for v in turns_tab.values())])

    count_table_md = fmt_table(["task_type"] + models_seen + ["total"], count_rows)
    turns_table_md = fmt_table(["task_type"] + models_seen + ["total"], turns_rows)

    # --- project x primary_model, top 30 projects by session count ---
    project_counts = Counter(r.get("project", "unknown") for r in modeled_rows)
    top_projects = [p for p, _ in project_counts.most_common(30)]
    proj_tab = defaultdict(lambda: defaultdict(int))
    for r in modeled_rows:
        p = r.get("project", "unknown")
        if p in top_projects:
            proj_tab[p][r["_primary_model"]] += 1
    proj_rows = []
    for p in top_projects:
        proj_rows.append([p] + [proj_tab[p].get(m, 0) for m in models_seen] + [sum(proj_tab[p].values())])
    proj_table_md = fmt_table(["project"] + models_seen + ["total"], proj_rows)

    # --- Fable-specific: per task_type, fable vs each other model ---
    other_models = [m for m in models_seen if m != FABLE_MODEL]
    fable_rows = []
    for tt in TASK_TYPES:
        fable_sessions = [r for r in modeled_rows if r.get("task_type") == tt and r["_primary_model"] == FABLE_MODEL]
        fable_n = len(fable_sessions)
        fable_mean_turns = round(sum(r.get("n_assistant_turns", 0) for r in fable_sessions) / fable_n, 1) if fable_n else 0
        row = [tt, fable_n, fable_mean_turns]
        for m in other_models:
            sessions = [r for r in modeled_rows if r.get("task_type") == tt and r["_primary_model"] == m]
            n = len(sessions)
            mean_turns = round(sum(r.get("n_assistant_turns", 0) for r in sessions) / n, 1) if n else 0
            row.append(f"{n} (mean turns {mean_turns})")
        fable_rows.append(row)
    fable_table_md = fmt_table(["task_type", "fable_n", "fable_mean_turns"] + [f"{m}_n (mean_turns)" for m in other_models], fable_rows)

    # Coverage gap callout: task types with zero or near-zero Fable sessions
    fable_by_tt = Counter(r.get("task_type") for r in modeled_rows if r["_primary_model"] == FABLE_MODEL)
    all_by_tt = Counter(r.get("task_type") for r in modeled_rows)
    gap_rows = []
    for tt in TASK_TYPES:
        fn = fable_by_tt.get(tt, 0)
        an = all_by_tt.get(tt, 0)
        pct = round(100.0 * fn / an, 1) if an else 0.0
        gap_rows.append([tt, fn, an, f"{pct}%"])
    gap_rows.sort(key=lambda r: r[3])
    gap_table_md = fmt_table(["task_type", "fable_sessions", "total_sessions", "fable_share"], gap_rows)

    # --- date ranges per model (recency) ---
    date_range_rows = []
    for m in models_seen:
        sessions = [r for r in modeled_rows if r["_primary_model"] == m]
        starts = sorted(r.get("start_ts") for r in sessions if r.get("start_ts"))
        ends = sorted(r.get("end_ts") for r in sessions if r.get("end_ts"))
        date_range_rows.append([
            m, len(sessions),
            starts[0] if starts else "n/a",
            ends[-1] if ends else "n/a",
        ])
    date_range_rows.sort(key=lambda r: r[3], reverse=True)
    date_range_md = fmt_table(["model", "n_sessions", "earliest_start", "latest_end"], date_range_rows)

    # --- sessions with strong outcome signals per task_type ---
    def is_strong_outcome(r):
        sig = r.get("outcome_signals", {})
        return bool(sig.get("mentions_tests_passed")) or sig.get("n_commits", 0) > 0

    strong_rows = []
    for tt in TASK_TYPES:
        sessions = [r for r in modeled_rows if r.get("task_type") == tt]
        strong = [r for r in sessions if is_strong_outcome(r)]
        fable_strong = [r for r in strong if r["_primary_model"] == FABLE_MODEL]
        strong_rows.append([tt, len(sessions), len(strong), len(fable_strong)])
    strong_table_md = fmt_table(["task_type", "n_sessions", "n_with_strong_outcome_signal", "of_which_fable"], strong_rows)

    # --- headline totals ---
    claude_model_turns = Counter()
    claude_sidechain_turns = Counter()
    for r in claude_rows:
        for m, c in (r.get("models") or {}).items():
            claude_model_turns[m] += c
        for m, c in (r.get("sidechain_models") or {}).items():
            claude_sidechain_turns[m] += c

    codex_model_turns = Counter()
    for r in codex_rows:
        for m, c in (r.get("models") or {}).items():
            codex_model_turns[m] += c

    combined_turns = Counter()
    for m, c in claude_model_turns.items():
        combined_turns[m] += c
    for m, c in claude_sidechain_turns.items():
        combined_turns[m] += c

    turn_totals_md = fmt_table(
        ["model", "main_session_turns", "sidechain_turns", "main+sidechain"],
        [
            [m, claude_model_turns.get(m, 0), claude_sidechain_turns.get(m, 0),
             claude_model_turns.get(m, 0) + claude_sidechain_turns.get(m, 0)]
            for m in sorted(set(claude_model_turns) | set(claude_sidechain_turns), key=lambda m: -(claude_model_turns.get(m, 0) + claude_sidechain_turns.get(m, 0)))
        ],
    )

    codex_turn_totals_md = fmt_table(
        ["model", "main_session_turns"],
        [[m, c] for m, c in codex_model_turns.most_common()],
    )

    # --- parse-failure / no-model-row summary ---
    total_parse_failures_claude = sum(r.get("parse_failures", 0) for r in claude_rows)
    total_parse_failures_codex = sum(r.get("parse_failures", 0) for r in codex_rows)

    md = f"""# Transcript Corpus Coverage Report

Generated from `mining/out/claude_index.jsonl` ({len(claude_rows)} rows) and
`mining/out/codex_index.jsonl` ({len(codex_rows)} rows).

`primary_model` = model with the most MAIN-session assistant turns per row's
`models` dict (ties broken lexically). {len(no_model_rows)} of {len(all_rows)}
total sessions have no primary_model (no real-model assistant turn at all --
degenerate/empty sessions or 100% "<synthetic>" error-placeholder turns) and
are excluded from the cross-tabs below but counted here for transparency.

Parse failures (malformed lines, skipped): {total_parse_failures_claude} (claude), {total_parse_failures_codex} (codex).

## Claude model turn totals (main vs. sidechain)

{turn_totals_md}

## Codex model turn totals

{codex_turn_totals_md}

## task_type x primary_model -- session counts

{count_table_md}

## task_type x primary_model -- total assistant turns

{turns_table_md}

## project x primary_model -- top 30 projects by session count

{proj_table_md}

## Fable-5 coverage per task_type (vs. every other primary_model)

{fable_table_md}

## Coverage gap ranking (lowest Fable share first) -- answers "which task types lack Fable coverage"

{gap_table_md}

## Model date ranges (recency)

{date_range_md}

## Sessions with strong outcome signals (tests-passed mention or >=1 commit) per task_type

{strong_table_md}
"""

    out_path = OUT_DIR / "coverage.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"wrote {out_path} ({len(md)} bytes)")
    print(f"claude rows: {len(claude_rows)}, codex rows: {len(codex_rows)}, no-primary-model rows: {len(no_model_rows)}")


if __name__ == "__main__":
    main()
