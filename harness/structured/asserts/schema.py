"""Hard schema assert for structured responses."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from harness.structured.asserts import AssertResult, register


def _selected_schema(cfg: dict[str, Any]) -> dict[str, Any]:
    selected = cfg.get("response_schema")
    if isinstance(selected, dict):
        return selected

    with Path(cfg["response_schema_path"]).open() as source:
        document = json.load(source)
    schema = document
    pointer = cfg.get("response_schema_pointer")
    for part in pointer.split("/") if pointer else []:
        schema = schema[part]
    if schema is not document and isinstance(schema, dict):
        schema = dict(schema)
        if "$defs" in document and "$defs" not in schema:
            schema["$defs"] = document["$defs"]
        if "$schema" in document and "$schema" not in schema:
            schema["$schema"] = document["$schema"]
    return schema


@register("schema")
def schema_assert(*, output, raw, expected, item, cfg, samples=None, population=None) -> AssertResult:
    if output is None:
        return AssertResult("schema", False, True, 0.0, f"output is not JSON: {raw[:160]!r}")
    errors = sorted(
        Draft202012Validator(_selected_schema(cfg)).iter_errors(output),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "<root>"
        return AssertResult(
            "schema",
            False,
            True,
            0.0,
            f"{len(errors)} schema error(s); first at {location}: {first.message}",
        )
    return AssertResult("schema", True, True, 1.0, "valid")
