"""Blind binary judge: grades a normalized findings block against ground truth.

The judge is a different model family than the executor (codex, via the
`run_codex` CLI wrapper) and is deliberately blind: it sees ONLY the rubric, the
rendered ground truth, and the normalized findings block. It never sees the
executor's reasoning, the executor's raw prompt, or the arm label — nothing that
could let a treatment's style bias the grade.

Ground truth is rendered with each defect's `acceptable_match` / `reject_if`
guidance (and, for clean items, the `clean_rationale` and `tempting_non_defects`)
so the judge can apply the same matching bar a human grader would.

JSON is obtained under `--output-schema`; we still parse and re-validate the
required keys and retry once on a malformed response before giving up (which the
caller records as a harness-level judge_error, not an executor failure).
"""
from __future__ import annotations

import json

import yaml

from harness.providers.codex_cli import run_codex
from harness.providers.errors import ProviderError

_JUDGE_TIMEOUT = 200  # >= 180s; codex judge calls take 30-90s and run at -j 4
_REQUIRED_KEYS = {"parse_ok", "defects", "false_findings", "neutral_matched",
                  "verdict_flagged"}


class JudgeError(Exception):
    """Raised when the judge cannot produce a valid grade after a retry."""


def _render_ground_truth(truth: dict) -> str:
    defects = truth.get("defects") or []
    lines: list[str] = []
    if defects:
        lines.append("This item is SEEDED. Ground-truth defects:")
        for d in defects:
            lines.append(f"- id: {d.get('id')}")
            if d.get("description"):
                lines.append(f"  description: {d['description']}")
            if d.get("acceptable_match"):
                lines.append(f"  acceptable_match: {d['acceptable_match']}")
            if d.get("reject_if"):
                lines.append(f"  reject_if: {d['reject_if']}")
        # neutral_findings render ONLY on seeded items (clean items never carry
        # them). A finding matching one is neither credited nor counted false.
        neutral = truth.get("neutral_findings") or []
        if neutral:
            lines.append(
                "neutral_findings (true-but-out-of-scope; a finding matching one "
                "of these is NEITHER credited as a defect NOR a false finding — "
                "count it in neutral_matched):"
            )
            for nf in neutral:
                lines.append(f"- {nf}")
    else:
        lines.append("This item is CLEAN. There are NO ground-truth defects.")
        if truth.get("clean_rationale"):
            lines.append(f"clean_rationale: {truth['clean_rationale']}")
        tempting = truth.get("tempting_non_defects") or []
        if tempting:
            lines.append("tempting_non_defects (a finding matching one of these is a false finding):")
            for t in tempting:
                lines.append(f"- {t}")
    return "\n".join(lines)


def build_judge_prompt(findings_block: str, truth: dict, rubric_text: str) -> str:
    return (
        rubric_text.rstrip()
        + "\n\nGROUND TRUTH:\n"
        + _render_ground_truth(truth)
        + "\n\nFINDINGS BLOCK:\n"
        + findings_block.strip()
        + "\n"
    )


def load_truth(truth_path: str) -> dict:
    with open(truth_path) as f:
        return yaml.safe_load(f) or {}


def _parse_and_validate(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("judge output was JSON but not an object")
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"judge output missing keys: {sorted(missing)}")
    defects = data.get("defects")
    if not isinstance(defects, list):
        raise ValueError("judge 'defects' must be a list")
    # Every defect entry must carry a string defect_id and a bool found. A
    # malformed entry raises here, which judge_review treats like any other bad
    # response (retry once, then JudgeError) so the caller writes a judge_error
    # row — never a silent drop or a downstream KeyError.
    for i, d in enumerate(defects):
        if not isinstance(d, dict):
            raise ValueError(f"judge 'defects'[{i}] is not an object")
        if not isinstance(d.get("defect_id"), str):
            raise ValueError(f"judge 'defects'[{i}] missing string 'defect_id'")
        if not isinstance(d.get("found"), bool):
            raise ValueError(f"judge 'defects'[{i}] missing bool 'found'")
    # neutral_matched (findings matching a neutral_findings entry — neither
    # credited nor counted false) must be a non-bool integer, mirroring the
    # false_findings contract; a malformed value fails like any other bad
    # response (retry once, then JudgeError).
    if not isinstance(data.get("neutral_matched"), int) or isinstance(
        data.get("neutral_matched"), bool
    ):
        raise ValueError("judge 'neutral_matched' must be an integer")
    return data


def judge_review(findings_block: str, truth: dict, judge_cfg: dict,
                 cwd: str | None = None) -> dict:
    """Grade `findings_block` against `truth`. Returns the validated judge dict.

    `judge_cfg` keys: model, effort, rubric (path), schema (path).
    `cwd`, if given, is forwarded to `run_codex` as the judge process's
    working directory (e.g. a `results_dir/judge_scratch` the caller owns) —
    isolating the blind judge from the caller's own cwd (repo root), which
    could otherwise be read even though it is never in the judge's prompt.
    Omitting `cwd` still isolates: `run_codex` defaults to a fresh empty
    scratch dir it creates and cleans up itself.
    Retries once on a malformed/failed response; raises JudgeError on a second
    failure.
    """
    with open(judge_cfg["rubric"]) as f:
        rubric_text = f.read()

    prompt = build_judge_prompt(findings_block, truth, rubric_text)

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            result = run_codex(
                prompt,
                schema_path=judge_cfg.get("schema"),
                model=judge_cfg.get("model", "gpt-5.5"),
                effort=judge_cfg.get("effort", "medium"),
                timeout=_JUDGE_TIMEOUT,
                cwd=cwd,
            )
            data = _parse_and_validate(result["output"])
            # tokens_used is parsed best-effort by run_codex from the codex
            # CLI's stderr/stdout (outside the validated JSON body) — thread
            # it onto the returned dict as judge_tokens (null if the CLI
            # output didn't carry a parseable "tokens used" line) so callers
            # can attribute judge-side cost per item, same as the executor's
            # token accounting.
            data["judge_tokens"] = result.get("tokens_used")
            return data
        except (json.JSONDecodeError, ValueError, ProviderError) as e:
            last_err = e
            continue
    tail = getattr(last_err, "stderr_tail", "") or ""
    detail = f" :: stderr: {tail}" if tail else ""
    raise JudgeError(f"judge failed after retry: {last_err}{detail}")
