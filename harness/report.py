"""Render the experiment report + human spot-check materials.

Every report is PROVISIONAL until a human confirms a sample of the blind judge's
grades — the LLM judge is instrumentation, not ground truth. So the report leads
with a provisional banner and emits `spotcheck.md` (readable) + `spotcheck.yaml`
(one `agree:` slot per sampled item) for a human to fill before the result is
trusted.

Reporting choices that are load-bearing, not cosmetic:
  - logical tokens and USD are reported on SEPARATE delta rows (neither cleanly
    isolates the artifact under test).
  - when both arms floor (composite_floored), the composite pass-rate is marked
    inconclusive and the report leads with defect recall + verdict confusion.
  - results are never aggregated across tiers.
"""
from __future__ import annotations

import json
import os

import yaml

from harness.config import ExperimentConfig
from harness.judge import _render_ground_truth, load_truth
from harness.metrics import (
    adherence,
    confusion,
    delta,
    flags,
    judge_token_totals,
    load_rows,
    mcnemar_p,
    pass_rate,
    paired_flips,
    token_totals,
)

_SPOTCHECK_LIMIT = 20
_SPOTCHECK_PER_ARM = _SPOTCHECK_LIMIT // 2
# Within each arm, the spot-check sample is stratified seeded/clean (not just
# taken as the first N by task_id) so a run whose seeded items cluster at one
# end of the id space can't crowd clean items out of a human's calibration
# sample entirely. 7 + 3 = 10 = _SPOTCHECK_PER_ARM, so the total cap is
# unchanged at _SPOTCHECK_LIMIT.
_SPOTCHECK_SEEDED_QUOTA = 7
_SPOTCHECK_CLEAN_QUOTA = 3

_ESTIMAND = (
    "Estimand: the effect of the varied review-procedure element on review "
    "quality, CONDITIONAL on a shared binary output format. Workspace section "
    "labels (CHECKLIST/DISCONFIRM/VERIFY) are instrumentation, not the treatment."
)


def summarize(cfg: ExperimentConfig, results_dir) -> dict:
    calls, judges = load_rows(results_dir)

    b_pr = pass_rate(judges, "baseline")
    t_pr = pass_rate(judges, "treatment")
    b_tok = token_totals(calls, "baseline")
    t_tok = token_totals(calls, "treatment")
    tok_delta = delta(b_tok, t_tok)
    b_conf = confusion(judges, "baseline")
    t_conf = confusion(judges, "treatment")
    flips = paired_flips(judges)
    adh = adherence(judges)
    b_judge_tok = judge_token_totals(judges, "baseline")
    t_judge_tok = judge_token_totals(judges, "treatment")
    mcnemar_p_value = mcnemar_p(flips["only_baseline"], flips["only_treatment"])

    judge_errors = b_pr["judge_errors"] + t_pr["judge_errors"]
    parse_failures = sum(
        1 for r in judges if not r.get("judge_error") and not r.get("parse_ok")
    )
    logical_pct = tok_delta.get("logical_total", {}).get("pct")
    fl = flags(
        b_pr["rate"], t_pr["rate"], logical_pct, cfg.negative_control, judge_errors
    )

    return {
        "calls": calls,
        "judges": judges,
        "baseline_pass": b_pr,
        "treatment_pass": t_pr,
        "baseline_tokens": b_tok,
        "treatment_tokens": t_tok,
        "token_delta": tok_delta,
        "baseline_confusion": b_conf,
        "treatment_confusion": t_conf,
        "flips": flips,
        "mcnemar_p": mcnemar_p_value,
        "adherence": adh,
        "baseline_judge_tokens": b_judge_tok,
        "treatment_judge_tokens": t_judge_tok,
        "flags": fl,
        "judge_errors": judge_errors,
        "parse_failures": parse_failures,
    }


def _fmt_pct(x):
    return "n/a" if x is None else f"{x:+.1f}%"


def _pass_line(pr):
    lo, hi = pr["wilson_ci"]
    return f"{pr['k']}/{pr['n']} = {pr['rate']:.3f}  (95% CI {lo:.3f}–{hi:.3f})"


def _token_block(tok):
    return (
        f"fresh={tok['fresh_input']} cache_creation={tok['cache_creation']} "
        f"cache_read={tok['cache_read']} output={tok['output']} "
        f"logical_total={tok['logical_total']}"
    )


# --------------------------------------------------------------------------- #
# Automatic honesty caveats
#
# These are computed straight from metrics already present in the summary
# dict `s` (never stored back onto `s`, so `metrics.json` — built directly
# from `s` in `render()` — cannot gain new keys or drift; only the rendered
# report gains lines). Every future experiment gets them for free because
# they fire off the same generic confusion/pass_rate shapes every experiment
# already produces.
# --------------------------------------------------------------------------- #
def _recall_ceiling_caveats(b_conf: dict, t_conf: dict) -> list[str]:
    """One caveat line per arm whose defect-level recall is at ceiling (1.000).

    An arm already at 1.000 recall cannot be observed to improve further on
    this task set, so any comparison built on top of that arm — recall
    deltas, and partly the pass-rate delta too, since verdict correctness is
    entangled with recall — is uninterpretable. Fires per arm (not just
    baseline) so it also catches the case where both arms floor the task
    set's difficulty simultaneously.
    """
    out = []
    for name, other, conf in (
        ("Baseline", "treatment", b_conf),
        ("Treatment", "baseline", t_conf),
    ):
        dr = conf.get("defect_recall", {}) or {}
        if dr.get("total") and dr.get("rate") == 1.0:
            out.append(
                f"{name} defect recall is at ceiling (1.000): the {other} "
                "structurally cannot improve recall on this task set; recall "
                "deltas are uninterpretable and pass-rate deltas partly "
                "preordained. A harder task set is required to detect a "
                "recall improvement."
            )
    return out


def _ci_overlap(b_pr: dict, t_pr: dict) -> bool:
    """Whether the two arms' Wilson 95% CIs (already computed in metrics) overlap."""
    b_lo, b_hi = b_pr["wilson_ci"]
    t_lo, t_hi = t_pr["wilson_ci"]
    return b_lo <= t_hi and t_lo <= b_hi


def _noise_caveat(b_pr: dict, t_pr: dict, only_baseline: int, only_treatment: int) -> str | None:
    """Caveat when EITHER noise screen fires: the arms' pass-rate CIs overlap,
    OR the exact McNemar test on the paired discordant flips (only_baseline vs
    only_treatment) is not significant (p > 0.05). Both screens are reported
    whenever either fires, and the wording stays honest when they disagree —
    it never claims agreement it doesn't have.
    """
    ci_overlap = _ci_overlap(b_pr, t_pr)
    p = mcnemar_p(only_baseline, only_treatment)
    p_flags_noise = p > 0.05
    if not (ci_overlap or p_flags_noise):
        return None
    b_n, t_n = b_pr["n"], t_pr["n"]
    n_str = str(b_n) if b_n == t_n else f"{b_n}/{t_n}"
    mcnemar_str = (
        f"McNemar exact p={p:.2f} on {only_baseline} vs {only_treatment} "
        "discordant pairs"
    )
    if ci_overlap and p_flags_noise:
        detail = f"overlapping 95% CIs and {mcnemar_str}"
    elif ci_overlap:
        detail = (
            f"overlapping 95% CIs, though {mcnemar_str} alone would not flag noise"
        )
    else:
        detail = f"{mcnemar_str}, though the 95% CIs do not overlap"
    return (
        f"Arm pass rates are not statistically distinguishable at n={n_str} "
        f"({detail}); treat the pass-rate delta as noise, not effect."
    )


def _collect_caveats(s: dict) -> list[str]:
    """Ordered list of automatic honesty caveats for this summary."""
    out = list(
        _recall_ceiling_caveats(s["baseline_confusion"], s["treatment_confusion"])
    )
    noise = _noise_caveat(
        s["baseline_pass"], s["treatment_pass"],
        s["flips"]["only_baseline"], s["flips"]["only_treatment"],
    )
    if noise:
        out.append(noise)
    return out


def render_report_md(cfg: ExperimentConfig, s: dict, note: str | None = None) -> str:
    L = []
    L.append("# Experiment report — PROVISIONAL")
    L.append("")
    L.append(
        "> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, "
        "then run `scripts/check_spotcheck.py`."
    )
    L.append("")
    if note:
        L.append(f"> NOTE — {note}")
        L.append("")
    L.append(_ESTIMAND)
    L.append("")

    caveats = _collect_caveats(s)
    if caveats:
        L.append("## Caveats")
        L.append("")
        for c in caveats:
            L.append(f"- {c}")
        L.append("")

    fl = s["flags"]
    if fl["harness_broken"]:
        L.append("## ⛔ HARNESS BROKEN")
        L.append(
            "Negative control, yet treatment beat baseline. This run measures "
            "noise; do not interpret the effect."
        )
        L.append("")
    if fl["composite_floored"]:
        L.append("## ⚠ COMPOSITE FLOORED — composite metric INCONCLUSIVE")
        L.append(
            "Both arms floored below 0.15 item-pass. Lead with defect-level "
            "recall and verdict confusion below, not the composite pass rate."
        )
        L.append("")
    if fl["cost_adjusted_verdict"]:
        L.append("## ⚠ COST-ADJUSTED VERDICT")
        L.append(
            "Treatment wins on pass rate but spends >20% more logical tokens — "
            "discount the win accordingly."
        )
        L.append("")

    config_block = _render_configuration_block(cfg)
    per_arm_block = _render_per_arm_block(s)
    judge_tokens_block = _render_judge_tokens_block(s)
    deltas_block = _render_deltas_block(s)
    confusion_block = _render_confusion_block(s)
    flips_block = _render_flips_block(s)
    adherence_block = _render_adherence_block(s)
    flags_block = _render_flags_block(s)
    footer_block = ["---", "_Not aggregated across tiers._", ""]

    L += config_block
    if fl["composite_floored"]:
        # COMPOSITE FLOORED: the composite pass rate is inconclusive, so the
        # report physically leads with defect recall + verdict confusion
        # (the confusion-matrix section carries both) BEFORE the pass-rate
        # table, not just the banner above — a reader skimming top-to-bottom
        # sees the trustworthy numbers first. Only the confusion block moves;
        # per-arm/judge-tokens/deltas stay grouped together either way.
        L += confusion_block
        L += per_arm_block
        L += judge_tokens_block
        L += deltas_block
    else:
        L += per_arm_block
        L += judge_tokens_block
        L += deltas_block
        L += confusion_block
    L += flips_block
    L += adherence_block
    L += flags_block
    L += footer_block
    return "\n".join(L)


def _render_configuration_block(cfg: ExperimentConfig) -> list[str]:
    L = ["## Configuration", ""]
    L.append(f"- id: `{cfg.id}`  task_family: `{cfg.task_family}`  eval_shape: `{cfg.eval_shape}`")
    L.append(f"- executor: `{cfg.executor.model}` (tier `{cfg.executor.tier}`)")
    L.append(f"- baseline_prompt: {cfg.baseline_prompt}")
    L.append(
        f"- varied element: `{cfg.varied_element}` (form `{cfg.varied_element_form}`) "
        f"-> `{cfg.varied_element_path().name}`"
    )
    L.append(f"- taskset: `{cfg.taskset}`  negative_control: `{cfg.negative_control}`")
    L.append(f"- judge: `{cfg.judge.provider}/{cfg.judge.model}` effort `{cfg.judge.effort}`")
    L.append("")
    return L


def _render_per_arm_block(s: dict) -> list[str]:
    L = ["## Per-arm results", ""]
    L.append("| arm | n | pass | tokens | cost USD |")
    L.append("|---|---|---|---|---|")
    for arm, pr, tok in (
        ("baseline", s["baseline_pass"], s["baseline_tokens"]),
        ("treatment", s["treatment_pass"], s["treatment_tokens"]),
    ):
        L.append(
            f"| {arm} | {pr['n']} | {_pass_line(pr)} | {_token_block(tok)} | "
            f"{tok['cost_usd']:.4f} |"
        )
    L.append("")
    return L


def _render_judge_tokens_block(s: dict) -> list[str]:
    L = ["## Judge-side tokens", ""]
    for arm, jt in (
        ("baseline", s["baseline_judge_tokens"]),
        ("treatment", s["treatment_judge_tokens"]),
    ):
        cost_total = jt.get("judge_cost_usd_total")
        cost_str = f"  cost_usd≈{cost_total:.4f}" if cost_total is not None else ""
        L.append(
            f"- {arm}: judge_tokens={jt['judge_tokens_total']} "
            f"(missing={jt['judge_tokens_missing']}){cost_str}"
        )
    L.append("")
    return L


def _render_deltas_block(s: dict) -> list[str]:
    td = s["token_delta"]
    L = ["### Deltas (treatment − baseline), reported separately", ""]
    lt = td.get("logical_total", {})
    ot = td.get("output", {})
    fi = td.get("fresh_input", {})
    cu = td.get("cost_usd", {})
    L.append(f"- logical tokens: {lt.get('abs', 'n/a')} ({_fmt_pct(lt.get('pct'))})")
    L.append(f"- output tokens: {ot.get('abs', 'n/a')} ({_fmt_pct(ot.get('pct'))})")
    L.append(f"- fresh input tokens: {fi.get('abs', 'n/a')} ({_fmt_pct(fi.get('pct'))})")
    L.append(f"- cost USD: {cu.get('abs', 'n/a'):+.4f} ({_fmt_pct(cu.get('pct'))})"
             if isinstance(cu.get("abs"), (int, float)) else "- cost USD: n/a")
    L.append("")
    return L


def _render_confusion_block(s: dict) -> list[str]:
    L = ["## Confusion matrix (verdict) + base rate", ""]
    L.append("| arm | TP | FP | TN | FN | base rate | defect recall | false findings | neutral matched |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for arm, c in (("baseline", s["baseline_confusion"]), ("treatment", s["treatment_confusion"])):
        dr = c["defect_recall"]
        L.append(
            f"| {arm} | {c['tp']} | {c['fp']} | {c['tn']} | {c['fn']} | "
            f"{c['base_rate']:.3f} | {dr['found']}/{dr['total']} = {dr['rate']:.3f} | "
            f"{c['false_findings_total']} | {c.get('neutral_matched_total', 0)} |"
        )
    L.append("")
    L.append(
        "- judge_id_mismatches (judge-returned defect ids not in ground truth; "
        "excluded from recall): "
        f"baseline={s['baseline_confusion']['defect_recall']['judge_id_mismatches']} "
        f"treatment={s['treatment_confusion']['defect_recall']['judge_id_mismatches']}"
    )
    L.append("")
    return L


def _render_flips_block(s: dict) -> list[str]:
    fp = s["flips"]
    L = ["## Paired flip table (joined on task_id)", ""]
    L.append(
        f"- both_pass: {fp['both_pass']}  both_fail: {fp['both_fail']}  "
        f"only_baseline: {fp['only_baseline']}  only_treatment: {fp['only_treatment']}"
    )
    L.append(f"- McNemar exact p-value (two-sided, on the discordant pairs): {s['mcnemar_p']:.3f}")
    L.append("")
    return L


def _render_adherence_block(s: dict) -> list[str]:
    L = ["## Treatment-arm adherence (per directive)", ""]
    for k, v in s["adherence"].items():
        L.append(f"- `{k}`: {v:.3f}")
    L.append("")
    return L


def _render_flags_block(s: dict) -> list[str]:
    fl = s["flags"]
    L = ["## Flags", ""]
    L.append(f"- cost_adjusted_verdict: {fl['cost_adjusted_verdict']}")
    L.append(f"- harness_broken: {fl['harness_broken']}")
    L.append(f"- composite_floored: {fl['composite_floored']}")
    L.append(f"- judge_errors: {fl['judge_errors']}")
    L.append(f"- parse failures (unparseable findings block): {s['parse_failures']}")
    L.append("")
    return L


def _sample_items(judges):
    """Up to _SPOTCHECK_LIMIT judged items, stratified across arms AND, within
    each arm, across seeded/clean.

    Naively taking `graded[:_SPOTCHECK_LIMIT]` off a `judge/*.json` glob sorts
    alphabetically by filename, and `"baseline-*"` sorts before
    `"treatment-*"` — with >=_SPOTCHECK_LIMIT baseline items the treatment arm
    is silently excluded from the human-calibration sample entirely (this is
    exactly what happened on the 40-record exp1 run: 20/20 sampled rows were
    baseline, 0 were treatment). A per-arm cap alone still leaves a second,
    subtler gap: sorting purely by task_id can crowd one seeded/clean split
    out of a small sample if that split's ids happen to cluster past the cap.

    So within each arm: split graded (parse_ok, not judge_error) rows into
    seeded and clean, sort each split by task_id (deterministic — no
    randomness, no Date-based seed), take up to _SPOTCHECK_SEEDED_QUOTA
    seeded + _SPOTCHECK_CLEAN_QUOTA clean (7 + 3 = _SPOTCHECK_PER_ARM),
    combine and re-sort that arm's selection by task_id. Arms are then
    interleaved round-robin (baseline, treatment, baseline, treatment, ...)
    exactly as before, so a human skimming spotcheck.md always sees both arms
    represented, alternating, in a stable order run to run.
    """
    graded = [r for r in judges if r.get("parse_ok") and not r.get("judge_error")]

    by_arm: dict = {}
    for r in graded:
        by_arm.setdefault(r.get("arm"), []).append(r)

    # Deterministic arm order (alphabetical: "baseline" before "treatment"),
    # tolerant of a stray None/missing arm without crashing the sort.
    arms = sorted(by_arm.keys(), key=lambda a: (a is None, a))

    lanes = []
    for arm in arms:
        rows = by_arm[arm]
        seeded_rows = sorted(
            (r for r in rows if r.get("seeded")), key=lambda r: r.get("task_id") or ""
        )
        clean_rows = sorted(
            (r for r in rows if not r.get("seeded")), key=lambda r: r.get("task_id") or ""
        )
        lane = seeded_rows[:_SPOTCHECK_SEEDED_QUOTA] + clean_rows[:_SPOTCHECK_CLEAN_QUOTA]
        lane.sort(key=lambda r: r.get("task_id") or "")
        lanes.append(lane)

    out = []
    for i in range(_SPOTCHECK_PER_ARM):
        for lane in lanes:
            if i < len(lane):
                out.append(lane[i])
    return out[:_SPOTCHECK_LIMIT]


def render_spotcheck(judges) -> tuple[str, list[dict]]:
    md = ["# Judge spot-check (human review)", ""]
    yaml_rows = []
    for r in _sample_items(judges):
        truth = load_truth(r["truth_path"]) if r.get("truth_path") else {}
        gt = _render_ground_truth(truth)
        verdict = "REJECT (flagged)" if r.get("verdict_flagged") else "APPROVE"
        found = [d["defect_id"] for d in (r.get("defects") or []) if d.get("found")]
        md.append(f"## {r['arm']} — {r['task_id']} (seeded={r.get('seeded')})")
        md.append("")
        md.append("**Normalized findings block:**")
        md.append("```")
        md.append((r.get("normalized_block") or "").rstrip())
        md.append("```")
        md.append("**Ground truth:**")
        md.append("```")
        md.append(gt)
        md.append("```")
        md.append(
            f"**Judge:** verdict={verdict}  found={found}  "
            f"false_findings={r.get('false_findings')}  item_pass={r.get('item_pass')}"
        )
        md.append("")
        yaml_rows.append(
            {
                "task_id": r["task_id"],
                "arm": r["arm"],
                "seeded": r.get("seeded"),
                "verdict_flagged": r.get("verdict_flagged"),
                "found": found,
                "false_findings": r.get("false_findings"),
                "item_pass": r.get("item_pass"),
                "agree": None,
            }
        )
    return "\n".join(md), yaml_rows


def render(cfg: ExperimentConfig, results_dir, note: str | None = None) -> dict:
    """Compute metrics and write report.md, spotcheck.md, spotcheck.yaml.

    `note`, if given, is rendered as a provenance blockquote near the top of
    report.md (e.g. a rescore's "executor calls shared verbatim with ..." note).

    Returns the summary dict (so run.py can read flags/judge_errors)."""
    results_dir = str(results_dir)
    s = summarize(cfg, results_dir)

    report_md = render_report_md(cfg, s, note=note)
    with open(os.path.join(results_dir, "report.md"), "w") as f:
        f.write(report_md)

    # metrics.json: the machine-readable reduction (drop the bulky raw row lists).
    # This is where judge_id_mismatches and the other reduced metrics are surfaced.
    metrics_json = {k: v for k, v in s.items() if k not in ("calls", "judges")}
    with open(os.path.join(results_dir, "metrics.json"), "w") as f:
        json.dump(metrics_json, f, ensure_ascii=False, indent=2)

    spot_md, spot_rows = render_spotcheck(s["judges"])
    with open(os.path.join(results_dir, "spotcheck.md"), "w") as f:
        f.write(spot_md)
    with open(os.path.join(results_dir, "spotcheck.yaml"), "w") as f:
        yaml.safe_dump({"items": spot_rows}, f, sort_keys=False, allow_unicode=True)

    return s
