"""Validation and projection of Prism analyzer documents."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote

from jsonschema import Draft202012Validator, validators


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGETS_SCHEMA = _REPO_ROOT / "contracts/targets.schema.json"
_SARIF_SCHEMA = _REPO_ROOT / "harness/tests/fixtures/sarif-schema-2.1.0.json"


class AnalyzerExecutorError(RuntimeError):
    """Prism could not be probed or did not produce a usable document."""


@lru_cache(maxsize=2)
def _validator(path: Path, *, declared_dialect: bool):
    try:
        schema = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalyzerExecutorError(f"cannot load analyzer schema {path}: {exc}") from exc
    validator_type = (
        validators.validator_for(schema) if declared_dialect else Draft202012Validator
    )
    try:
        validator_type.check_schema(schema)
    except Exception as exc:
        raise AnalyzerExecutorError(f"invalid analyzer schema {path}: {exc}") from exc
    return validator_type(schema)


def _validate_document(document: Mapping[str, Any]) -> str:
    if document.get("schema_version") == "1.0":
        label = "targets"
        validator = _validator(_TARGETS_SCHEMA, declared_dialect=False)
        contract = "targets-1.0"
    elif document.get("version") == "2.1.0":
        label = "SARIF"
        validator = _validator(_SARIF_SCHEMA, declared_dialect=True)
        contract = "sarif-2.1.0"
    else:
        raise AnalyzerExecutorError("unknown analyzer output contract")
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: ([str(part) for part in error.absolute_path], error.message),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        raise AnalyzerExecutorError(
            f"{label} schema validation failed at {location}: {first.message}"
        )
    return contract


def _targets_findings(document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    targets = document.get("targets")
    if not isinstance(targets, list):
        raise AnalyzerExecutorError("targets document has no targets array")
    projected = []
    for index, target in enumerate(targets):
        try:
            site = target["site"]
            projected.append(
                {
                    "category": target["category"],
                    "file": site["file"],
                    "line": site["line"],
                    "tier": target["tier"],
                }
            )
        except (KeyError, TypeError) as exc:
            raise AnalyzerExecutorError(
                f"invalid targets finding at index {index}"
            ) from exc
    return tuple(projected)


def _sarif_findings(document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    runs = document.get("runs")
    if not isinstance(runs, list):
        raise AnalyzerExecutorError("SARIF document has no runs array")
    projected = []
    for run_index, run in enumerate(runs):
        results = run.get("results", []) if isinstance(run, Mapping) else None
        if not isinstance(results, list):
            raise AnalyzerExecutorError(f"SARIF run {run_index} has no results array")
        for result_index, result in enumerate(results):
            try:
                properties = result["properties"]
                physical = result["locations"][0]["physicalLocation"]
                region = physical.get("region", {})
                projected.append(
                    {
                        "category": properties["category"],
                        "file": unquote(physical["artifactLocation"]["uri"]),
                        "line": region.get("startLine", 0),
                        "tier": properties["tier"],
                    }
                )
            except (IndexError, KeyError, TypeError) as exc:
                raise AnalyzerExecutorError(
                    f"invalid SARIF finding at run {run_index} result {result_index}"
                ) from exc
    return tuple(projected)


def findings_from_document(
    document: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Project Prism targets v1 or SARIF 2.1 into the matching shape."""
    contract = _validate_document(document)
    if contract == "targets-1.0":
        return _targets_findings(document)
    return _sarif_findings(document)


def _document_resolution(document: Mapping[str, Any]) -> str:
    if document.get("schema_version") == "1.0":
        producer = document.get("producer")
        value = (
            producer.get("resolution_mode") if isinstance(producer, Mapping) else None
        )
    else:
        runs = document.get("runs")
        first = runs[0] if isinstance(runs, list) and runs else None
        properties = first.get("properties") if isinstance(first, Mapping) else None
        value = (
            properties.get("resolution_mode")
            if isinstance(properties, Mapping)
            else None
        )
    if not isinstance(value, str) or not value:
        raise AnalyzerExecutorError("analyzer output omits resolution mode")
    return value


__all__ = ["AnalyzerExecutorError", "findings_from_document"]
