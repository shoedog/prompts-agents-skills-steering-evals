"""Shared response normalization for structured-task and pipeline calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from jsonschema.protocols import Validator


@dataclass(frozen=True)
class NormalizedResponse:
    output: dict[str, Any] | None
    raw: str
    final_document_valid: bool
    sentinel_kind: str


def normalize_response(
    envelope: Mapping[str, Any], response_validator: Validator
) -> NormalizedResponse:
    response = envelope.get("response")
    output = dict(response) if isinstance(response, Mapping) else None
    final_document_valid = output is not None and not list(
        response_validator.iter_errors(output)
    )
    label = output.get("class") if output is not None else None
    if envelope.get("final_sentinel") is True:
        sentinel_kind = "transport" if label == "provider_error" else "schema"
    else:
        sentinel_kind = "none"
    raw = (
        json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if output is not None
        else ""
    )
    return NormalizedResponse(output, raw, final_document_valid, sentinel_kind)


__all__ = ["NormalizedResponse", "normalize_response"]
