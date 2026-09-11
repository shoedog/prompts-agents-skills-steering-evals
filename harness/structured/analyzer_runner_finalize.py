"""Final identity checks for analyzer result trees."""

from __future__ import annotations

from typing import Any

from harness.structured.runner_types import IntegrityError


def verify_analyzer_records(loaded: Any, pairs: tuple[tuple[Any, Any], ...]) -> None:
    expected = {(mode.version, item.id, 0) for mode, item in pairs}
    for records, label in (
        (loaded.calls, "calls"),
        (loaded.stages, "stages"),
        (loaded.asserts, "asserts"),
    ):
        actual = {
            (record.get("version"), record.get("item_id"), record.get("sample"))
            for record in records
        }
        if actual != expected:
            raise IntegrityError(
                f"analyzer {label} identity mismatch: missing={sorted(expected - actual)}, "
                f"extra={sorted(actual - expected)}"
            )


__all__ = ["verify_analyzer_records"]
