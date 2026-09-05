"""Pure reducers for structured classification runs."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from harness.metrics import wilson_ci
from harness.structured.metrics_cost import _required_mapping, cost_latency


INVALID_PREDICTION = "__invalid__"
SENTINEL_KINDS = {"none", "schema", "transport"}


@dataclass(frozen=True)
class ScoredSample:
    item_id: str
    truth: str
    first_tier_valid: bool | None
    first_tier_sentinel: bool | None
    final_sentinel: bool
    escalation_state: str
    sentinel_kind: str
    schema_valid_for_eval: bool
    repaired: bool
    prediction: str | None
    brier_confidence: float | None
    brier_correct: bool


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _confidence(value: object, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{field} must be a finite number in [0, 1]")
    return float(value)


def normalize_sample(
    call: Mapping[str, Any], *, final_document_valid: bool
) -> ScoredSample:
    """Apply the EVAL-3 truth table to one complete structured call record."""
    if not isinstance(final_document_valid, bool):
        raise ValueError("final_document_valid must be boolean")
    envelope = _required_mapping(call.get("llm_envelope", call), "llm_envelope")
    expected = _required_mapping(call.get("expected"), "expected")

    item_id = _required_string(call.get("item_id"), "item_id")
    truth = _required_string(expected.get("label"), "expected.label")
    escalation_state = _required_string(
        envelope.get("escalation_state"), "llm_envelope.escalation_state"
    )
    sentinel_kind = call.get("sentinel_kind", envelope.get("sentinel_kind"))
    if sentinel_kind not in SENTINEL_KINDS:
        raise ValueError(
            f"sentinel_kind must be one of {sorted(SENTINEL_KINDS)}, got {sentinel_kind!r}"
        )

    first_tier_valid = envelope.get("first_tier_valid")
    first_tier_sentinel = envelope.get("first_tier_sentinel")
    final_sentinel = envelope.get("final_sentinel")
    if first_tier_valid is not None and not isinstance(first_tier_valid, bool):
        raise ValueError("llm_envelope.first_tier_valid must be boolean or null")
    if first_tier_sentinel is not None and not isinstance(first_tier_sentinel, bool):
        raise ValueError("llm_envelope.first_tier_sentinel must be boolean or null")
    if not isinstance(final_sentinel, bool):
        raise ValueError("llm_envelope.final_sentinel must be boolean")

    schema_valid_for_eval = final_document_valid and sentinel_kind != "transport"
    repaired = first_tier_valid is False
    forced_penalty = not schema_valid_for_eval or sentinel_kind != "none"
    if not schema_valid_for_eval:
        prediction = INVALID_PREDICTION
        brier_confidence = 0.0
        brier_correct = False
    else:
        response = _required_mapping(envelope.get("response"), "llm_envelope.response")
        prediction = _required_string(response.get("class"), "llm_envelope.response.class")
        if forced_penalty:
            brier_confidence = 0.0
            brier_correct = False
        else:
            brier_confidence = _confidence(
                response.get("confidence"), "llm_envelope.response.confidence"
            )
            brier_correct = prediction == truth

    return ScoredSample(
        item_id=item_id,
        truth=truth,
        first_tier_valid=first_tier_valid,
        first_tier_sentinel=first_tier_sentinel,
        final_sentinel=final_sentinel,
        escalation_state=escalation_state,
        sentinel_kind=sentinel_kind,
        schema_valid_for_eval=schema_valid_for_eval,
        repaired=repaired,
        prediction=prediction,
        brier_confidence=brier_confidence,
        brier_correct=brier_correct,
    )


def _rate(count: int, total: int, *, interval: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "k": count,
        "n": total,
        "rate": count / total if total else 0.0,
    }
    if interval:
        result["wilson_ci"] = wilson_ci(count, total)
    return result


def classification_metrics(
    rows: Sequence[ScoredSample], classes: Sequence[str]
) -> dict[str, Any]:
    """Compute metrics, using known first-tier rows for both first-tier rates.

    The first-tier-valid and repaired rates are ``None`` when no row has a
    boolean ``first_tier_valid`` value. Invalid final rows remain in the other
    classification and validity populations.
    """
    declared = tuple(classes)
    if len(set(declared)) != len(declared):
        raise ValueError("classes must not contain duplicates")
    if any(not isinstance(label, str) or not label for label in declared):
        raise ValueError("classes must contain nonempty strings")

    declared_set = set(declared)
    predictions = []
    normalized_predictions: list[str] = []
    for row in rows:
        if row.truth not in declared_set:
            raise ValueError(f"truth label {row.truth!r} is not declared")
        prediction = (
            row.prediction
            if row.schema_valid_for_eval and row.prediction is not None
            else INVALID_PREDICTION
        )
        normalized_predictions.append(prediction)
        if prediction not in predictions and prediction not in declared_set:
            predictions.append(prediction)

    columns = (*declared, INVALID_PREDICTION)
    extra_columns = tuple(
        prediction for prediction in predictions if prediction != INVALID_PREDICTION
    )
    confusion = {
        truth: {predicted: 0 for predicted in (*columns, *extra_columns)}
        for truth in declared
    }
    for row, prediction in zip(rows, normalized_predictions, strict=True):
        confusion[row.truth][prediction] += 1

    per_class: dict[str, dict[str, int | float]] = {}
    for label in declared:
        tp = sum(
            1
            for row, prediction in zip(rows, normalized_predictions, strict=True)
            if row.truth == label and prediction == label
        )
        fp = sum(
            1
            for row, prediction in zip(rows, normalized_predictions, strict=True)
            if row.truth != label and prediction == label
        )
        fn = sum(
            1
            for row, prediction in zip(rows, normalized_predictions, strict=True)
            if row.truth == label and prediction != label
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    total = len(rows)
    first_valid = sum(row.first_tier_valid is True for row in rows)
    first_known = sum(isinstance(row.first_tier_valid, bool) for row in rows)
    first_unknown = sum(row.first_tier_valid is None for row in rows)
    schema_valid = sum(row.schema_valid_for_eval for row in rows)
    repaired = sum(row.first_tier_valid is False for row in rows)
    return {
        "n": total,
        "confusion": confusion,
        "per_class": per_class,
        "macro_f1": (
            sum(float(values["f1"]) for values in per_class.values()) / len(declared)
            if declared
            else 0.0
        ),
        "first_tier_valid_n": first_valid,
        "first_tier_known_n": first_known,
        "first_tier_unknown_n": first_unknown,
        "repaired_n": repaired,
        "first_tier_valid": {
            "k": first_valid,
            "n": first_known,
            "rate": first_valid / first_known if first_known else None,
            "wilson_ci": wilson_ci(first_valid, first_known) if first_known else None,
        },
        "schema_valid_for_eval": _rate(schema_valid, total, interval=True),
        "repaired": {
            "count": repaired,
            "n": first_known,
            "rate": repaired / first_known if first_known else None,
        },
    }


def brier(rows: Sequence[ScoredSample]) -> dict[str, Any]:
    """Compatibility export; implementation lives in calibration.py."""
    from harness.structured.calibration import brier as _brier

    return _brier(rows)


def cohen_kappa(
    expected: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> float:
    """Compatibility export; implementation lives in calibration.py."""
    from harness.structured.calibration import cohen_kappa as _cohen_kappa

    return _cohen_kappa(expected, predicted, labels)
