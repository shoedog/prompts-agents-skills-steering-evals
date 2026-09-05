"""Exact and ordinal label assertions."""
from __future__ import annotations

from harness.structured.asserts import AssertResult, register


@register("label")
def label_assert(*, output, raw, expected, item, cfg, samples=None) -> AssertResult:
    field = cfg.get("field", "class")
    actual = output.get(field) if output is not None else None
    wanted = expected.get("label")
    mode = cfg.get("mode", "exact")
    if mode == "exact":
        passed = actual == wanted
        detail = "exact label match" if passed else f"expected {wanted!r}, got {actual!r}"
        return AssertResult("label", passed, False, float(passed), detail)

    if mode != "ordinal":
        return AssertResult("label", False, False, 0.0, f"unknown label mode {mode!r}")
    order = cfg.get("class_order", cfg.get("classes", []))
    missing = [value for value in (actual, wanted) if value not in order]
    if missing:
        return AssertResult(
            "label", False, False, 0.0, f"label {missing[0]!r} not in declared class order"
        )
    tolerance = cfg.get("tolerance", 0)
    distance = abs(order.index(actual) - order.index(wanted))
    passed = distance <= tolerance
    detail = (
        f"ordinal distance {distance} within tolerance {tolerance}"
        if passed
        else f"ordinal distance {distance} exceeds tolerance {tolerance}"
    )
    return AssertResult("label", passed, False, float(passed), detail)
