"""Evidence-line and rationale-term assertions."""
from __future__ import annotations

import re

from harness.structured.asserts import AssertResult, register


@register("evidence")
def evidence_assert(*, output, raw, expected, item, cfg, samples=None, population=None) -> AssertResult:
    output = output or {}
    rationale = output.get("rationale", "")
    patterns = expected.get("rationale_must_mention", [])
    missing_terms: list[str] = []
    invalid_terms: list[str] = []
    for pattern in patterns:
        try:
            matched = re.search(pattern, rationale) is not None
        except re.error:
            invalid_terms.append(pattern)
            continue
        if not matched:
            missing_terms.append(pattern)

    required_lines = set(expected.get("evidence_lines_subset", []))
    actual_lines = set(output.get("evidence_lines", []))
    rendered = item.get("rendered_slice")
    rendered_numbers = rendered.get("rendered_line_numbers") if isinstance(rendered, dict) else None
    valid_lines = (
        {line for line in rendered_numbers if isinstance(line, int) and not isinstance(line, bool)}
        if isinstance(rendered_numbers, list)
        else set()
    )
    stray_lines = sorted(actual_lines - valid_lines)
    missing_lines = sorted(required_lines - actual_lines)
    failures = []
    if missing_terms:
        failures.append(f"missing rationale terms: {missing_terms}")
    if invalid_terms:
        failures.append(f"invalid rationale regexes: {invalid_terms}")
    if stray_lines:
        failures.append(f"citations outside rendered slice: {stray_lines}")
    if missing_lines:
        failures.append(f"missing evidence lines: {missing_lines}")
    passed = not failures
    return AssertResult(
        "evidence",
        passed,
        False,
        float(passed),
        "evidence requirements met" if passed else "; ".join(failures),
    )
