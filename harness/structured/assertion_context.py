"""Shared normalized samples and population descriptors for assertions."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from harness.structured.asserts import Population


def call_number(call: Mapping[str, Any], field: str) -> float:
    value = call.get(field)
    if value is None and field == "cost_usd":
        envelope = call.get("llm_envelope")
        value = envelope.get(field) if isinstance(envelope, Mapping) else None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"call {field} must be a finite nonnegative number")
    return float(value)


def assertion_sample(call: Mapping[str, Any]) -> dict[str, Any]:
    sample = dict(call)
    sample.setdefault("cost_usd", call_number(call, "cost_usd"))
    return sample


def assertion_context(
    calls: Sequence[Mapping[str, Any]], *, version: str, item_id: str
) -> tuple[
    list[dict[str, Any]],
    dict[str, tuple[list[dict[str, Any]], Population]],
] | None:
    all_samples = [assertion_sample(call) for call in calls]
    version_calls = [call for call in calls if call.get("version") == version]
    excluded = {
        str(call.get("item_id")) for call in version_calls if call.get("stage_error")
    }
    if item_id in excluded:
        return None
    eligible = [call for call in version_calls if call.get("item_id") not in excluded]
    item_calls = [call for call in eligible if call.get("item_id") == item_id]
    if not eligible or not item_calls:
        return None
    version_samples = [assertion_sample(call) for call in version_calls]
    item_samples = [assertion_sample(call) for call in item_calls]
    return item_samples, {
        "run": (
            all_samples,
            Population(
                "run",
                item_count=len({sample["item_id"] for sample in all_samples}),
                sample_count=len(all_samples),
            ),
        ),
        "version": (
            version_samples,
            Population(
                "version",
                item_count=len({sample["item_id"] for sample in version_samples}),
                sample_count=len(version_samples),
            ),
        ),
    }


__all__ = ["assertion_context", "assertion_sample", "call_number"]
