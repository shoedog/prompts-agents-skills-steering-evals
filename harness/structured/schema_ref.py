from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchemaRefError(ValueError):
    pass


def _inside(root: Path, path: Path) -> bool:
    return root == path or root in path.parents


def resolve_schema_ref(root: Path, ref: str) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    raw_path, marker, pointer = ref.partition("#")
    if not raw_path:
        raise SchemaRefError(f"schema reference has no path: {ref}")
    path = (root / raw_path).resolve()
    if not _inside(root, path):
        raise SchemaRefError(f"schema path escapes repo root: {ref}")
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaRefError(f"cannot load schema {ref}: {exc}") from exc
    if not isinstance(document, dict):
        raise SchemaRefError(f"schema must contain one JSON object: {ref}")
    selected: Any = document
    if marker:
        if pointer and not pointer.startswith("/"):
            raise SchemaRefError(f"invalid JSON pointer in schema reference: {ref}")
        try:
            for part in pointer.removeprefix("/").split("/") if pointer else ():
                selected = selected[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError) as exc:
            raise SchemaRefError(f"schema pointer not found: {ref}") from exc
    if not isinstance(selected, dict):
        raise SchemaRefError(f"schema reference does not select an object: {ref}")
    return document, selected
