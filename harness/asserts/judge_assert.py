"""promptfoo Python assert: normalize the findings block, then grade it blindly.

promptfoo calls `get_assert(output, context)` after the executor runs, with
`output` = the executor's full response and `context["vars"]` = the test vars.
This runs concurrently (promptfoo -j 4), so all writes are per-item files with
no shared appends.

The pipeline is deliberately defensive about what reaches the judge:

  1. Slice from the LAST `## FINDINGS` marker to end — that block is the only
     graded surface.
  2. Normalize deterministically: pull the `VERDICT: APPROVE|REJECT` line and the
     numbered findings (or `No findings.`) via regex and re-render them as a
     canonical block. ALL other prose is dropped, so no treatment's writing
     style can leak into the judge. An unparseable verdict => parse_ok=false, the
     item fails, and NO judge call is made.
  3. Compute adherence labels locally by scanning the WORKSPACE (text before
     `## FINDINGS`) for the literal section labels CHECKLIST / DISCONFIRM /
     VERIFY. These are instrumentation only and are never sent to the judge.
  4. Call the blind judge (retry handled inside `judge_review`); a hard failure
     marks judge_error=true so the item is excluded from pass metrics and the
     run exits nonzero.

The promptfoo python worker only puts THIS file's directory on sys.path, so we
prepend the repo root before importing the `harness` package.
"""
import json
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.judge import JudgeError, judge_review, load_truth  # noqa: E402

try:
    from harness.tracing import trace_call  # noqa: E402
except Exception:  # pragma: no cover
    def trace_call(kind, payload, results_dir=None):
        return None

_FINDINGS_MARKER = "## FINDINGS"
# A weak executor wraps/decorates the verdict line: `**VERDICT: REJECT**`,
# `## VERDICT: APPROVE`, `> VERDICT: REJECT`, leading whitespace, etc. It may
# ALSO wrap just the word (`VERDICT: **REJECT**`) rather than the whole line.
# Tolerate a run of markdown decoration / whitespace both before the literal
# `VERDICT:` token AND between the colon and the word, WITHOUT loosening what
# the judge sees — the re-render below is still canonical either way.
_VERDICT_RE = re.compile(
    r"^[\s*_#>~`]*VERDICT:\s*[*_~`]*\s*(APPROVE|REJECT)\b",
    re.IGNORECASE | re.MULTILINE,
)
# Findings arrive numbered `1.` / `1)` / `1:` or bulleted `-` / `*` / `+`. Bullets
# REQUIRE a following space so a bold marker (`**VERDICT...`) is never mistaken for
# a `*` bullet; numbered markers may abut their text (`1.foo`), as before.
_FINDING_RE = re.compile(
    r"^\s*(?:\d+[.):][ \t]*|[-*+][ \t]+)(.+?)\s*$",
    re.MULTILINE,
)
# A genuine, explicit empty finding list (any casing). Load-bearing: it is what
# distinguishes an explicit "No findings." from a silent extraction failure.
_NO_FINDINGS_RE = re.compile(r"\bno findings\b", re.IGNORECASE)
_LABEL_RES = {
    "checklist": re.compile(r"\bCHECKLIST\b"),
    "disconfirm": re.compile(r"\bDISCONFIRM\b"),
    "verify": re.compile(r"\bVERIFY\b"),
}


def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def _split_workspace_and_block(output: str):
    idx = output.rfind(_FINDINGS_MARKER)
    if idx == -1:
        return output, ""
    return output[:idx], output[idx:]


def _detect_adherence(workspace: str) -> dict:
    return {name: bool(rx.search(workspace)) for name, rx in _LABEL_RES.items()}


def normalize_block(block: str):
    """Return (normalized_text, parse_ok, verdict_flagged).

    parse_ok is False when the surface is unusable:
      - no VERDICT line can be extracted; OR
      - the verdict is REJECT but zero findings are extractable — a REJECT that
        lists nothing is a contradictory surface, so we refuse it rather than
        silently rendering "No findings." (which would flip it into a clean pass
        to the judge); OR
      - the verdict is APPROVE but there are neither extractable findings nor an
        explicit "No findings." line — an extraction failure, not a clean pass.

    A genuine "No findings." (any casing) IS recognized as an explicit empty
    finding list, distinct from that extraction failure.
    """
    vm = _VERDICT_RE.search(block)
    if not vm:
        return "", False, False
    verdict = vm.group(1).upper()
    verdict_flagged = verdict == "REJECT"

    raw_findings = [f for f in (m.group(1).strip() for m in _FINDING_RE.finditer(block)) if f]
    # A bulleted/numbered "No findings." (e.g. `- No findings.`) is prose, not a
    # finding — filter it out before deciding whether the list is genuinely
    # empty, so it can never be re-rendered as a spurious "1. No findings."
    findings = [f for f in raw_findings if not _NO_FINDINGS_RE.search(f)]
    if not findings:
        # No findings extracted. Legitimate only for an APPROVE that explicitly
        # says "No findings."; a REJECT here is contradictory, and an APPROVE
        # with no explicit empty marker is an extraction failure.
        if verdict_flagged or not _NO_FINDINGS_RE.search(block):
            return "", False, verdict_flagged

    lines = [_FINDINGS_MARKER, f"VERDICT: {verdict}"]
    if findings:
        for i, f in enumerate(findings, 1):
            lines.append(f"{i}. {f}")
    else:
        lines.append("No findings.")
    return "\n".join(lines) + "\n", True, verdict_flagged


def _write_record(results_dir: str, arm: str, task_id: str, record: dict):
    judge_dir = os.path.join(results_dir, "judge")
    os.makedirs(judge_dir, exist_ok=True)
    with open(os.path.join(judge_dir, f"{arm}-{task_id}.json"), "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def get_assert(output, context):
    variables = (context or {}).get("vars", {}) or {}
    task_id = variables["task_id"]
    arm = variables["arm"]
    exp_id = variables["exp_id"]
    tier = variables["tier"]
    seeded = _coerce_bool(variables.get("seeded"))
    truth_path = variables["truth_path"]
    results_dir = variables["results_dir"]
    judge_cfg = json.loads(variables["judge_json"])

    workspace, block = _split_workspace_and_block(output or "")
    adherence_labels = _detect_adherence(workspace)
    normalized, parse_ok, verdict_flagged = normalize_block(block)

    # Ground truth is the recall anchor: the record carries the seeded defect ids
    # so metrics can score recall against truth (not against the judge's own,
    # possibly-hallucinated, id list). Loaded up front so even a parse-failure row
    # records what SHOULD have been found.
    truth = load_truth(truth_path)
    truth_defect_ids = {d["id"] for d in (truth.get("defects") or [])}

    base_record = {
        "exp_id": exp_id,
        "arm": arm,
        "task_id": task_id,
        "tier": tier,
        "seeded": seeded,
        "adherence_labels": adherence_labels,
        "truth_path": truth_path,
        "truth_defect_ids": sorted(truth_defect_ids),
        "normalized_block": normalized,
    }

    # (2) unparseable verdict -> item fails, no judge call.
    if not parse_ok:
        record = dict(
            base_record,
            parse_ok=False,
            defects=[],
            false_findings=0,
            verdict_flagged=False,
            item_pass=False,
            judge_error=False,
        )
        _write_record(results_dir, arm, task_id, record)
        return {"pass": False, "score": 0.0, "reason": "unparseable findings block"}

    # (4) blind judge. cwd is pinned to a scratch dir under this experiment's
    # results_dir (never this worker's own cwd / repo root) so the "blind"
    # judge process cannot read repo/results/truth files at the process
    # level even though it never sees them in its prompt.
    judge_scratch = os.path.join(results_dir, "judge_scratch")
    try:
        judged = judge_review(normalized, truth, judge_cfg, cwd=judge_scratch)
    except JudgeError as e:
        record = dict(
            base_record,
            parse_ok=True,
            defects=[],
            false_findings=0,
            verdict_flagged=verdict_flagged,
            item_pass=False,
            judge_error=True,
        )
        _write_record(results_dir, arm, task_id, record)
        trace_call("judge_error", {"task_id": task_id, "arm": arm, "error": str(e)},
                   results_dir=results_dir)
        return {"pass": False, "score": 0.0, "reason": f"judge_error: {e}"}

    defects = judged.get("defects", []) or []
    false_findings = int(judged.get("false_findings", 0) or 0)
    # judge.py validates each entry has a string defect_id + bool found before we
    # get here; `.get` is belt-and-suspenders so a slipped-through entry can never
    # KeyError this row into a crash.
    found_ids = {d.get("defect_id") for d in defects if d.get("found")}

    if seeded:
        all_found = bool(truth_defect_ids) and truth_defect_ids.issubset(found_ids)
        item_pass = all_found and false_findings == 0 and verdict_flagged
    else:
        item_pass = false_findings == 0 and not verdict_flagged

    record = dict(
        base_record,
        parse_ok=True,
        defects=defects,
        false_findings=false_findings,
        verdict_flagged=verdict_flagged,
        item_pass=item_pass,
        judge_error=False,
    )
    _write_record(results_dir, arm, task_id, record)
    trace_call("judge", record, results_dir=results_dir)

    reason = (
        f"item_pass={item_pass} seeded={seeded} verdict_flagged={verdict_flagged} "
        f"false_findings={false_findings} found={sorted(found_ids)}"
    )
    return {"pass": item_pass, "score": 1.0 if item_pass else 0.0, "reason": reason}
