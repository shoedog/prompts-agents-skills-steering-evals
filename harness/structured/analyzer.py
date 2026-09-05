"""Execution seam for Prism finding evaluation modes."""

from __future__ import annotations

import json
import os
import re
import subprocess
from functools import lru_cache
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote

from jsonschema import Draft202012Validator, validators

from harness.providers.binpath import resolve_executable
from harness.structured.asserts.analyzer_match import MatchResult, match_findings
from harness.structured.config import AnalyzerConfig, load_analyzer_config
from harness.structured.taskset import TaskItem, load_taskset


_FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")
_MODE_FLAGS = (("--resolution", "resolution"), ("--min-confidence", "min_confidence"))
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGETS_SCHEMA = _REPO_ROOT / "contracts/targets.schema.json"
_SARIF_SCHEMA = _REPO_ROOT / "harness/tests/fixtures/sarif-schema-2.1.0.json"


class AnalyzerExecutorError(RuntimeError):
    """Prism could not be probed or did not produce a usable document."""


@dataclass(frozen=True)
class AnalyzerMode:
    algorithm: str
    language: str
    resolution: str
    min_confidence: str

    @property
    def version(self) -> str:
        return "/".join(
            (self.algorithm, self.language, self.resolution, self.min_confidence)
        )


@dataclass(frozen=True)
class AnalyzerResult:
    version_record: dict[str, Any]
    stage_record: dict[str, Any] | None
    findings: tuple[dict[str, Any], ...]
    match: MatchResult | None
    strata: tuple[dict[str, Any], ...]


@lru_cache(maxsize=2)
def _validator(path: Path, *, declared_dialect: bool):
    try:
        schema = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalyzerExecutorError(f"cannot load analyzer schema {path}: {exc}") from exc
    validator_type = validators.validator_for(schema) if declared_dialect else Draft202012Validator
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


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise AnalyzerExecutorError(f"cannot execute analyzer {argv[0]!r}: {exc}") from exc


def probe_flags(binary: str) -> frozenset[str]:
    """Return long options advertised by a successful ``prism --help`` probe."""
    completed = _run([binary, "--help"])
    if completed.returncode != 0:
        raise AnalyzerExecutorError(
            f"analyzer help probe exited with code {completed.returncode}: "
            f"{completed.stderr[-1000:]}"
        )
    return frozenset(_FLAG.findall(f"{completed.stdout}\n{completed.stderr}"))


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
            raise AnalyzerExecutorError(f"invalid targets finding at index {index}") from exc
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


def findings_from_document(document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Project Prism targets v1 or SARIF 2.1 into the matching shape."""
    contract = _validate_document(document)
    if contract == "targets-1.0":
        return _targets_findings(document)
    return _sarif_findings(document)


def _document_resolution(document: Mapping[str, Any]) -> str:
    if document.get("schema_version") == "1.0":
        producer = document.get("producer")
        value = producer.get("resolution_mode") if isinstance(producer, Mapping) else None
    else:
        runs = document.get("runs")
        first = runs[0] if isinstance(runs, list) and runs else None
        properties = first.get("properties") if isinstance(first, Mapping) else None
        value = properties.get("resolution_mode") if isinstance(properties, Mapping) else None
    if not isinstance(value, str) or not value:
        raise AnalyzerExecutorError("analyzer output omits resolution mode")
    return value


def _version_record(mode: AnalyzerMode) -> dict[str, Any]:
    return {
        "version": mode.version,
        "algorithm": mode.algorithm,
        "language": mode.language,
        "resolution": mode.resolution,
        "min_confidence": mode.min_confidence,
    }


def _strata(
    mode: AnalyzerMode,
    expected: tuple[dict, ...],
    emitted: tuple[dict, ...],
    matched: MatchResult,
) -> tuple[dict[str, Any], ...]:
    pairs = {
        (match["expected_index"], match["emitted_index"]) for match in matched.matches
    }
    rows = []
    for tier in ("asserted", "candidate"):
        expected_indexes = {
            index for index, finding in enumerate(expected) if finding.get("tier", "asserted") == tier
        }
        emitted_indexes = {
            index for index, finding in enumerate(emitted) if finding.get("tier", "asserted") == tier
        }
        same_tier = {
            (expected_index, emitted_index)
            for expected_index, emitted_index in pairs
            if expected_index in expected_indexes and emitted_index in emitted_indexes
        }
        rows.append(
            {
                "language": mode.language,
                "tier": tier,
                "resolution": mode.resolution,
                "tp": len(same_tier),
                "fp": len(emitted_indexes) - len(same_tier),
                "fn": len(expected_indexes) - len(same_tier),
            }
        )
    return tuple(rows)


def run_analyzer_item(
    item: TaskItem,
    mode: AnalyzerMode,
    *,
    line_tolerance: int,
    binary: str | None = None,
    flags: frozenset[str] | None = None,
) -> AnalyzerResult:
    """Execute one analyzer mode for one labeled fixture and match its findings."""
    executable = binary or resolve_executable("prism")
    available = probe_flags(executable) if flags is None else flags
    version_record = _version_record(mode)
    for flag, _ in _MODE_FLAGS:
        if flag not in available:
            skipped = {**version_record, "skipped": f"flag_unavailable({flag})"}
            return AnalyzerResult(skipped, None, (), None, ())

    repo = item.inputs.get("repo")
    diff = item.inputs.get("diff")
    if repo is None or diff is None:
        raise AnalyzerExecutorError(f"analyzer item {item.id} requires repo and diff inputs")
    argv = [
        executable,
        "--repo",
        str(repo.path),
        "--algorithm",
        mode.algorithm,
        "--diff",
        str(diff.path),
        "--format",
        "sarif",
        "--resolution",
        mode.resolution,
        "--min-confidence",
        mode.min_confidence,
    ]
    completed = _run(argv)
    if completed.returncode != 0:
        raise AnalyzerExecutorError(
            f"analyzer exited with code {completed.returncode}: {completed.stderr[-1000:]}"
        )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AnalyzerExecutorError(f"analyzer stdout is not JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise AnalyzerExecutorError("analyzer stdout must contain one JSON object")
    emitted = findings_from_document(document)
    observed_resolution = _document_resolution(document)
    if observed_resolution != mode.resolution:
        raise AnalyzerExecutorError(
            "analyzer resolution mismatch: "
            f"requested {mode.resolution!r}, got {observed_resolution!r}"
        )
    expected = tuple(item.expected["findings"])
    matched = match_findings(
        expected,
        emitted,
        line_tolerance=line_tolerance,
        negative_findings=item.expected["negative_findings"],
        max_findings=item.expected["max_findings"],
    )
    strata = _strata(mode, expected, emitted, matched)
    stage_record = {
        "stage": "analyzer",
        "version": mode.version,
        "item_id": item.id,
        "argv": argv,
        "output_contract": (
            "targets-1.0" if document.get("schema_version") == "1.0" else "sarif-2.1.0"
        ),
        "output": document,
        "findings": list(emitted),
        "match": asdict(matched),
        "strata": list(strata),
    }
    return AnalyzerResult(version_record, stage_record, emitted, matched, strata)


def run_analyzer_config(
    cfg: AnalyzerConfig, *, binary: str | None = None
) -> tuple[AnalyzerResult, ...]:
    """Run all language-applicable item/mode pairs after one help probe."""
    executable = binary
    if executable is None and cfg.prism_bin is not None:
        executable = os.environ.get(cfg.prism_bin.removeprefix("env:"))
    executable = executable or resolve_executable("prism")
    flags = probe_flags(executable)
    taskset = load_taskset(
        cfg.taskset, split=cfg.split, max_items=cfg.token_budget["max_items"]
    )
    return tuple(
        run_analyzer_item(
            item,
            mode,
            binary=executable,
            flags=flags,
            line_tolerance=cfg.line_tolerance,
        )
        for mode in cfg.modes
        for item in taskset.items
        if item.raw.get("language") == mode.language
    )


__all__ = [
    "AnalyzerExecutorError",
    "AnalyzerMode",
    "AnalyzerResult",
    "findings_from_document",
    "load_analyzer_config",
    "probe_flags",
    "run_analyzer_config",
    "run_analyzer_item",
]
