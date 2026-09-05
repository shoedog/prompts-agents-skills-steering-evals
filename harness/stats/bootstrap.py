"""Deterministic, standard-library paired bootstrap statistics."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from typing import Any


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return a linearly interpolated percentile of a nonempty population."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if (
        not isinstance(quantile, (int, float))
        or isinstance(quantile, bool)
        or not math.isfinite(quantile)
        or not 0.0 <= quantile <= 1.0
    ):
        raise ValueError("quantile must be a finite number in [0, 1]")

    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def mean_outcome(rows: Sequence[dict[str, Any]]) -> float:
    """Return the arithmetic mean of the rows' numeric ``outcome`` values."""
    return sum(row["outcome"] for row in rows) / len(rows)


def _stable_float(value: float) -> float:
    """Remove subtraction noise so numeric JSON goldens remain literal."""
    return round(float(value), 15)


def paired_delta_ci(
    items_a: Mapping[str, dict],
    items_b: Mapping[str, dict],
    statistic: Callable[[Sequence[dict]], float],
    *,
    resamples: int,
    seed: int,
    alpha: float = 0.05,
) -> dict[str, float | int]:
    """Percentile CI for ``statistic(B) - statistic(A)`` under paired resampling."""
    if set(items_a) != set(items_b):
        raise ValueError("paired bootstrap requires identical item-id sets")
    if not items_a:
        raise ValueError("paired bootstrap requires at least one paired item")
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    if (
        not isinstance(alpha, (int, float))
        or isinstance(alpha, bool)
        or not math.isfinite(alpha)
        or not 0.0 < alpha < 1.0
    ):
        raise ValueError("alpha must be a finite number in (0, 1)")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")

    keys = sorted(items_a)
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(resamples):
        draw = [keys[rng.randrange(len(keys))] for _ in keys]
        deltas.append(
            statistic([items_b[item_id] for item_id in draw])
            - statistic([items_a[item_id] for item_id in draw])
        )

    return {
        "delta": _stable_float(
            statistic([items_b[item_id] for item_id in keys])
            - statistic([items_a[item_id] for item_id in keys])
        ),
        "lo": _stable_float(percentile(deltas, alpha / 2)),
        "hi": _stable_float(percentile(deltas, 1 - alpha / 2)),
        "resamples": resamples,
        "seed": seed,
        "alpha": alpha,
    }
