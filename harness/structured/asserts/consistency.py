"""Repeated-sample modal-label consistency assertion."""
from __future__ import annotations

from collections import Counter

from harness.structured.asserts import AssertResult, register


@register("consistency")
def consistency_assert(
    *, output, raw, expected, item, cfg, samples=None, population=None
) -> AssertResult:
    if cfg.get("samples_per_item", 0) <= 1:
        return AssertResult(
            "consistency", False, False, None, "consistency requires samples_per_item > 1"
        )
    if not samples:
        return AssertResult("consistency", False, False, None, "consistency requires samples")
    field = cfg.get("field", "class")
    labels = []
    for sample in samples:
        sample_output = sample.get("output", sample)
        labels.append(sample_output.get(field, "__invalid__"))
    modal_count = max(Counter(labels).values())
    share = modal_count / len(labels)
    threshold = cfg.get("threshold", 1.0)
    passed = share >= threshold
    detail = (
        f"modal-label share {share:.6g} meets threshold {threshold:.6g}"
        if passed
        else f"modal-label share {share:.6g} below threshold {threshold:.6g}"
    )
    return AssertResult("consistency", passed, False, share, detail)
