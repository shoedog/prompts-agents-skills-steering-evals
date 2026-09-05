"""Calibration and categorical agreement reducers for structured runs."""

from __future__ import annotations

import math
from typing import Any, Sequence

from harness.structured.metrics import INVALID_PREDICTION, ScoredSample


def _brier_inputs(row: ScoredSample) -> tuple[float, float, bool]:
    forced_penalty = (
        not row.schema_valid_for_eval
        or row.final_sentinel
        or row.sentinel_kind != "none"
        or row.prediction == INVALID_PREDICTION
    )
    if forced_penalty:
        return 0.0, 1.0, True
    confidence = row.brier_confidence
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(confidence)
        or not 0.0 <= confidence <= 1.0
    ):
        raise ValueError(
            f"sample {row.item_id!r} brier_confidence must be a finite number in [0, 1]"
        )
    return float(confidence), float(row.brier_correct), False


def brier(rows: Sequence[ScoredSample]) -> dict[str, Any]:
    """Score every row and return a ten-bin reliability table."""
    bin_values: list[list[tuple[float, float]]] = [[] for _ in range(10)]
    losses: list[float] = []
    maximum_penalty = 0
    for row in rows:
        confidence, outcome, forced = _brier_inputs(row)
        loss = (confidence - outcome) ** 2
        if forced:
            maximum_penalty += 1
        losses.append(loss)
        index = 9 if confidence == 1.0 else int(confidence * 10)
        bin_values[index].append((confidence, outcome))

    bins = []
    for index, values in enumerate(bin_values):
        count = len(values)
        bins.append(
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "n": count,
                "mean_confidence": (
                    math.fsum(confidence for confidence, _ in values) / count
                    if count
                    else None
                ),
                "accuracy": (
                    math.fsum(outcome for _, outcome in values) / count if count else None
                ),
            }
        )
    return {
        "score": math.fsum(losses) / len(losses) if losses else 0.0,
        "n": len(rows),
        "maximum_penalty": maximum_penalty,
        "bins": bins,
    }


def cohen_kappa(
    expected: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> float:
    """Cohen's kappa over declared truth labels plus observed prediction sentinels."""
    if len(expected) != len(predicted):
        raise ValueError("cohen_kappa requires equal-length expected and predicted sequences")
    declared = tuple(labels)
    if len(set(declared)) != len(declared):
        raise ValueError("labels must not contain duplicates")
    if any(not isinstance(label, str) or not label for label in declared):
        raise ValueError("labels must contain nonempty strings")
    declared_set = set(declared)
    for label in expected:
        if label not in declared_set:
            raise ValueError(f"expected label {label!r} is not declared")
    if any(not isinstance(label, str) or not label for label in predicted):
        raise ValueError("predicted labels must contain nonempty strings")
    if not expected:
        return 0.0

    categories = (*declared, *(label for label in dict.fromkeys(predicted) if label not in declared_set))
    total = len(expected)
    observed = sum(left == right for left, right in zip(expected, predicted, strict=True)) / total
    expected_agreement = sum(
        expected.count(label) * predicted.count(label) for label in categories
    ) / (total * total)
    if expected_agreement == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected_agreement) / (1.0 - expected_agreement)
