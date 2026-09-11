"""One-to-one matching for labeled analyzer findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from harness.structured.asserts import AssertResult, register


@dataclass(frozen=True)
class MatchResult:
    tp: int
    fp: int
    fn: int
    surplus_fp: int
    negative_hits: int
    matches: tuple[dict[str, Any], ...]


def _same_site(left: dict, right: dict, tolerance: int) -> bool:
    return (
        left.get("category") == right.get("category")
        and left.get("file") == right.get("file")
        and isinstance(left.get("line"), int)
        and not isinstance(left.get("line"), bool)
        and isinstance(right.get("line"), int)
        and not isinstance(right.get("line"), bool)
        and abs(left["line"] - right["line"]) <= tolerance
    )


def match_findings(
    expected: Sequence[dict],
    emitted: Sequence[dict],
    *,
    line_tolerance: int,
    negative_findings: Sequence[dict],
    max_findings: int,
) -> MatchResult:
    """Greedily assign compatible findings in ascending line-distance order."""
    if (
        not isinstance(line_tolerance, int)
        or isinstance(line_tolerance, bool)
        or line_tolerance < 0
    ):
        raise ValueError("line_tolerance must be a nonnegative integer")
    if not isinstance(max_findings, int) or isinstance(max_findings, bool) or max_findings < 0:
        raise ValueError("max_findings must be a nonnegative integer")

    candidates = sorted(
        (
            (abs(want["line"] - got["line"]), expected_index, emitted_index)
            for expected_index, want in enumerate(expected)
            for emitted_index, got in enumerate(emitted)
            if _same_site(want, got, line_tolerance)
        ),
        key=lambda edge: edge,
    )
    assigned_expected: set[int] = set()
    assigned_emitted: set[int] = set()
    matches: list[dict[str, Any]] = []
    for _, expected_index, emitted_index in candidates:
        if expected_index in assigned_expected or emitted_index in assigned_emitted:
            continue
        assigned_expected.add(expected_index)
        assigned_emitted.add(emitted_index)
        delta = emitted[emitted_index]["line"] - expected[expected_index]["line"]
        matches.append(
            {
                "expected_index": expected_index,
                "emitted_index": emitted_index,
                "matched_by": "exact_line" if delta == 0 else f"tolerance({delta:+d})",
            }
        )

    unmatched_emitted = [
        index for index in range(len(emitted)) if index not in assigned_emitted
    ]
    negative_hits = sum(
        any(_same_site(emitted[index], negative, line_tolerance) for negative in negative_findings)
        for index in unmatched_emitted
    )
    surplus_fp = max(0, len(emitted) - max_findings)
    return MatchResult(
        tp=len(matches),
        fp=len(unmatched_emitted) + surplus_fp,
        fn=len(expected) - len(matches),
        surplus_fp=surplus_fp,
        negative_hits=negative_hits,
        matches=tuple(matches),
    )


@register("analyzer_match")
def analyzer_match_assert(
    *, output, raw, expected, item, cfg, samples=None, population=None
) -> AssertResult:
    """Registry adapter for normalized analyzer outputs."""
    emitted = output.get("findings") if isinstance(output, dict) else None
    if not isinstance(emitted, list) or not all(isinstance(value, dict) for value in emitted):
        return AssertResult(
            "analyzer_match", False, False, 0.0, f"output has no findings array: {raw[:160]!r}"
        )
    match_cfg = cfg.get("match", {})
    tolerance = match_cfg.get("line_tolerance", cfg.get("line_tolerance", 3))
    result = match_findings(
        expected.get("findings", []),
        emitted,
        line_tolerance=tolerance,
        negative_findings=expected.get("negative_findings", []),
        max_findings=expected.get("max_findings", 0),
    )
    denominator = 2 * result.tp + result.fp + result.fn
    score = 1.0 if denominator == 0 else 2 * result.tp / denominator
    passed = result.fp == 0 and result.fn == 0
    detail = (
        f"tp={result.tp} fp={result.fp} fn={result.fn} "
        f"negative_hits={result.negative_hits} surplus_fp={result.surplus_fp}"
    )
    return AssertResult("analyzer_match", passed, False, score, detail)


__all__ = ["MatchResult", "analyzer_match_assert", "match_findings"]
