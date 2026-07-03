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
    load_rows,
    pass_rate,
    paired_flips,
    token_totals,
)

_SPOTCHECK_LIMIT = 20

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
        "adherence": adh,
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


def render_report_md(cfg: ExperimentConfig, s: dict) -> str:
    L = []
    L.append("# Experiment report — PROVISIONAL")
    L.append("")
    L.append(
        "> PROVISIONAL — pending human judge spot-check. Fill `spotcheck.yaml`, "
        "then run `scripts/check_spotcheck.py`."
    )
    L.append("")
    L.append(_ESTIMAND)
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

    L.append("## Configuration")
    L.append("")
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

    L.append("## Per-arm results")
    L.append("")
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

    td = s["token_delta"]
    L.append("### Deltas (treatment − baseline), reported separately")
    L.append("")
    lt = td.get("logical_total", {})
    cu = td.get("cost_usd", {})
    L.append(f"- logical tokens: {lt.get('abs', 'n/a')} ({_fmt_pct(lt.get('pct'))})")
    L.append(f"- cost USD: {cu.get('abs', 'n/a'):+.4f} ({_fmt_pct(cu.get('pct'))})"
             if isinstance(cu.get("abs"), (int, float)) else "- cost USD: n/a")
    L.append("")

    L.append("## Confusion matrix (verdict) + base rate")
    L.append("")
    L.append("| arm | TP | FP | TN | FN | base rate | defect recall | false findings |")
    L.append("|---|---|---|---|---|---|---|---|")
    for arm, c in (("baseline", s["baseline_confusion"]), ("treatment", s["treatment_confusion"])):
        dr = c["defect_recall"]
        L.append(
            f"| {arm} | {c['tp']} | {c['fp']} | {c['tn']} | {c['fn']} | "
            f"{c['base_rate']:.3f} | {dr['found']}/{dr['total']} = {dr['rate']:.3f} | "
            f"{c['false_findings_total']} |"
        )
    L.append("")
    L.append(
        "- judge_id_mismatches (judge-returned defect ids not in ground truth; "
        "excluded from recall): "
        f"baseline={s['baseline_confusion']['defect_recall']['judge_id_mismatches']} "
        f"treatment={s['treatment_confusion']['defect_recall']['judge_id_mismatches']}"
    )
    L.append("")

    fp = s["flips"]
    L.append("## Paired flip table (joined on task_id)")
    L.append("")
    L.append(
        f"- both_pass: {fp['both_pass']}  both_fail: {fp['both_fail']}  "
        f"only_baseline: {fp['only_baseline']}  only_treatment: {fp['only_treatment']}"
    )
    L.append("")

    L.append("## Treatment-arm adherence (per directive)")
    L.append("")
    for k, v in s["adherence"].items():
        L.append(f"- `{k}`: {v:.3f}")
    L.append("")

    L.append("## Flags")
    L.append("")
    L.append(f"- cost_adjusted_verdict: {fl['cost_adjusted_verdict']}")
    L.append(f"- harness_broken: {fl['harness_broken']}")
    L.append(f"- composite_floored: {fl['composite_floored']}")
    L.append(f"- judge_errors: {fl['judge_errors']}")
    L.append(f"- parse failures (unparseable findings block): {s['parse_failures']}")
    L.append("")

    L.append("---")
    L.append("_Not aggregated across tiers._")
    L.append("")
    return "\n".join(L)


def _sample_items(judges):
    """Up to _SPOTCHECK_LIMIT judged items (parse_ok, not judge_error)."""
    graded = [r for r in judges if r.get("parse_ok") and not r.get("judge_error")]
    return graded[:_SPOTCHECK_LIMIT]


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


def render(cfg: ExperimentConfig, results_dir) -> dict:
    """Compute metrics and write report.md, spotcheck.md, spotcheck.yaml.

    Returns the summary dict (so run.py can read flags/judge_errors)."""
    results_dir = str(results_dir)
    s = summarize(cfg, results_dir)

    report_md = render_report_md(cfg, s)
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
