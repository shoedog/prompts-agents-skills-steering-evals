"""Per-call cost and sample-population p95 latency assertion."""
from __future__ import annotations

import math

from harness.structured.asserts import AssertResult, register


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


@register("cost_latency")
def cost_latency_assert(*, output, raw, expected, item, cfg, samples=None) -> AssertResult:
    if not samples:
        return AssertResult("cost_latency", False, False, None, "cost_latency requires samples")
    failures = []
    max_cost = cfg.get("max_usd_per_call")
    if max_cost is not None:
        for sample in samples:
            cost = sample.get("cost_usd")
            if not isinstance(cost, (int, float)) or isinstance(cost, bool):
                failures.append("missing or invalid cost_usd")
            elif cost > max_cost:
                failures.append(f"cost_usd {cost:g} exceeds {max_cost:g}")

    max_p95 = cfg.get("max_p95_ms")
    if max_p95 is not None:
        durations = [sample.get("duration_ms") for sample in samples]
        if any(
            not isinstance(duration, (int, float)) or isinstance(duration, bool)
            for duration in durations
        ):
            failures.append("missing or invalid duration_ms")
        else:
            p95 = _p95(durations)
            if p95 > max_p95:
                failures.append(f"p95 duration_ms {p95:g} exceeds {max_p95:g}")
    passed = not failures
    return AssertResult(
        "cost_latency",
        passed,
        False,
        None,
        "cost and latency within limits" if passed else "; ".join(failures),
    )
