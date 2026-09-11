"""Cost and latency reduction for structured calls."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _required_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return value


def _percentile(ordered: Sequence[float], quantile: float) -> float:
    if not ordered:
        raise ValueError("percentile requires at least one value")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _call_number(call: Mapping[str, Any], field: str) -> float:
    value = call.get(field)
    if value is None and field == "cost_usd":
        envelope = call.get("llm_envelope")
        if isinstance(envelope, Mapping):
            value = envelope.get(field)
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"call {field} must be a finite nonnegative number")
    return float(value)


def cost_latency(calls: Sequence[dict]) -> dict[str, int | float | None]:
    """Reduce unique invocations from the complete caller-owned population.

    Cost comes from each call or its LLM envelope. Latency remains the
    caller-measured top-level ``duration_ms`` call-record field; it is never
    read from the envelope. A retry is counted when it has a new invocation ID.
    """
    invocation_ids: set[str] = set()
    for call in calls:
        envelope = _required_mapping(call.get("llm_envelope"), "llm_envelope")
        invocation_id = envelope.get("invocation_id")
        if not isinstance(invocation_id, str):
            raise ValueError("llm_envelope.invocation_id must be a string")
        if invocation_id in invocation_ids:
            raise ValueError(
                f"duplicate invocation_id in supplied population: {invocation_id!r}"
            )
        invocation_ids.add(invocation_id)

    costs = [_call_number(call, "cost_usd") for call in calls]
    durations = sorted(_call_number(call, "duration_ms") for call in calls)
    return {
        "calls": len(calls),
        "cost_usd": math.fsum(costs),
        "p50_ms": _percentile(durations, 0.50) if durations else None,
        "p95_ms": _percentile(durations, 0.95) if durations else None,
    }


__all__ = ["cost_latency"]
