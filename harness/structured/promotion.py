"""Pure promotion decision for paired structured-evaluation metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromotionVerdict:
    promotable: bool
    reason: str
    evidence: Mapping[str, Any] | None = None


def _number(value: object, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _interval(ci: Mapping[str, float], field: str) -> tuple[float, float]:
    if not isinstance(ci, Mapping):
        raise ValueError(f"{field} must be a mapping")
    lo = _number(ci.get("lo"), f"{field}.lo")
    hi = _number(ci.get("hi"), f"{field}.hi")
    if lo > hi:
        raise ValueError(f"{field}.lo must be less than or equal to {field}.hi")
    return lo, hi


def promotion_verdict(
    *,
    macro_f1_ci: Mapping[str, float],
    schema_validity: float,
    recall_cis: Mapping[str, Mapping[str, float]],
    evidence: Mapping[str, Any] | None = None,
) -> PromotionVerdict:
    """Apply the macro-F1, schema-validity, and per-class recall promotion gates."""
    macro_lo, _ = _interval(macro_f1_ci, "macro_f1_ci")
    validity = _number(schema_validity, "schema_validity")
    if not 0.0 <= validity <= 1.0:
        raise ValueError("schema_validity must be in [0, 1]")
    if not isinstance(recall_cis, Mapping):
        raise ValueError("recall_cis must be a mapping")
    recall_upper = {
        label: _interval(ci, f"recall_cis[{label!r}]")[1]
        for label, ci in recall_cis.items()
    }

    if macro_lo < 0.0:
        return PromotionVerdict(
            False,
            f"NOT PROMOTABLE: macro_f1_ci.lo={macro_lo:g} is below 0",
            evidence,
        )
    if validity < 0.99:
        return PromotionVerdict(
            False,
            f"NOT PROMOTABLE: schema_validity={validity:g} is below 0.99",
            evidence,
        )
    for label in sorted(recall_upper):
        upper = recall_upper[label]
        if upper < 0.0:
            return PromotionVerdict(
                False,
                f"NOT PROMOTABLE: recall_ci.hi[{label}]={upper:g} is below 0",
                evidence,
            )
    return PromotionVerdict(
        True,
        "PROMOTABLE: macro_f1_ci.lo>=0, schema_validity>=0.99, "
        "and every recall_ci.hi>=0",
        evidence,
    )
