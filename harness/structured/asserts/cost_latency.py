"""Per-call cost and sample-population p95 latency assertion."""
from __future__ import annotations

import math

from harness.structured.asserts import AssertConfigError, AssertResult, Population, register


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


@register("cost_latency")
def cost_latency_assert(
    *, output, raw, expected, item, cfg, samples=None, population: Population | None = None
) -> AssertResult:
    declared = cfg.get("population")
    if declared not in {"per_item", "run"}:
        raise AssertConfigError(
            f"cost_latency population must be 'per_item' or 'run'; got {declared!r}"
        )
    if population is None:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"population descriptor required for declared {declared!r} population",
        )
    if population.kind != declared:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"population mismatch: declared {declared!r}, got {population.kind!r}",
        )
    if not samples:
        return AssertResult("cost_latency", False, False, None, "cost_latency requires samples")
    if population.sample_count != len(samples):
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"population sample_count {population.sample_count} does not match {len(samples)} samples",
        )
    if population.kind == "per_item" and population.item_count != 1:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"per_item population must contain 1 item, got {population.item_count}",
        )
    invalid_identities = [
        index
        for index, sample in enumerate(samples)
        if not isinstance(sample.get("item_id"), str)
        or not sample["item_id"]
        or not isinstance(sample.get("version"), str)
        or not sample["version"]
    ]
    if invalid_identities:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            "population samples require nonempty item_id and version; "
            f"invalid indexes: {invalid_identities}",
        )
    versions = sorted({sample["version"] for sample in samples})
    if len(versions) != 1:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"population must contain exactly 1 version, got {versions}",
        )
    item_ids = {sample["item_id"] for sample in samples}
    if population.kind == "run" and len(item_ids) != population.item_count:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"run population item_count {population.item_count} does not match "
            f"{len(item_ids)} distinct item ids",
        )
    if population.kind == "per_item" and len(item_ids) != 1:
        return AssertResult(
            "cost_latency",
            False,
            False,
            None,
            f"per_item population must contain exactly 1 distinct item id, got {len(item_ids)}",
        )
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
