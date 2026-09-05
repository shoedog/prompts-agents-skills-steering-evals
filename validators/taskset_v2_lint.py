#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.structured.taskset import TasksetError, assemble_request, load_taskset


def _yaml_object(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise TasksetError(f"expected one YAML object: {path}")
    return value


def _experiment_ids(repo_root: Path, pattern: str) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(repo_root.glob(pattern)):
        try:
            value = _yaml_object(path)
        except (OSError, yaml.YAMLError, TasksetError):
            continue
        if isinstance(value.get("id"), str):
            found[value["id"]] = path
    return found


def _input_hash_set(item: dict[str, Any]) -> frozenset[str]:
    hashes = []
    inputs = item.get("inputs", {})
    if isinstance(inputs, dict):
        for value in inputs.values():
            if isinstance(value, dict) and isinstance(value.get("sha256"), str):
                hashes.append(value["sha256"])
    stages = item.get("stages", {})
    if isinstance(stages, dict):
        for value in stages.values():
            if isinstance(value, dict) and isinstance(value.get("sha256"), str):
                hashes.append(value["sha256"])
    return frozenset(hashes)


def _histograms(manifest: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = {}
    for split in manifest.get("splits", {}):
        result[split] = Counter(
            item.get("expected", {}).get("label")
            for item in items
            if item.get("split") == split and isinstance(item.get("expected"), dict)
        )
    return result


def lint_taskset(root: Path, *, repo_root: Path) -> list[str]:
    root = Path(root).resolve()
    repo_root = Path(repo_root).resolve()
    errors: list[str] = []
    try:
        manifest = _yaml_object(root / "manifest.yaml")
    except (OSError, yaml.YAMLError, TasksetError) as exc:
        return [f"manifest error: {exc}"]
    item_paths = sorted((root / "items").glob("*.yaml"))
    items: list[dict[str, Any]] = []
    for path in item_paths:
        try:
            items.append(_yaml_object(path))
        except (OSError, yaml.YAMLError, TasksetError) as exc:
            errors.append(f"item parse error {path.name}: {exc}")

    manifest_ids = {
        value.get("id") for value in manifest.get("items", []) if isinstance(value, dict)
    }
    file_ids = {item.get("id") for item in items}
    filenames = {path.stem for path in item_paths}
    if manifest_ids != file_ids or file_ids != filenames:
        errors.append(
            "manifest/items file mismatch: "
            f"manifest={sorted(str(v) for v in manifest_ids)} "
            f"items={sorted(str(v) for v in file_ids)} files={sorted(filenames)}"
        )

    for split in ("dev", "test"):
        summaries = [
            value for value in manifest.get("items", [])
            if isinstance(value, dict) and value.get("split") == split
        ]
        if not summaries:
            continue
        try:
            taskset = load_taskset(root, split=split, max_items=len(summaries))
            if manifest.get("task") == "classify_error_handling":
                for item in taskset.items:
                    assemble_request(
                        item, task_version="lint", request_schema=taskset.request_schema
                    )
        except TasksetError as exc:
            errors.append(str(exc))

    by_split: dict[str, list[tuple[str, frozenset[str]]]] = {"dev": [], "test": []}
    for item in items:
        split = item.get("split")
        if split in by_split:
            by_split[split].append((str(item.get("id")), _input_hash_set(item)))
    for dev_id, dev_hashes in by_split["dev"]:
        for test_id, test_hashes in by_split["test"]:
            if dev_hashes and dev_hashes == test_hashes:
                errors.append(
                    f"duplicate input hash set across dev/test: {dev_id} and {test_id}"
                )
            if manifest.get("task") == "prism_analyzer":
                dev_item = next(item for item in items if item.get("id") == dev_id)
                test_item = next(item for item in items if item.get("id") == test_id)
                dev_repo = dev_item.get("inputs", {}).get("repo", {}).get("sha256")
                test_repo = test_item.get("inputs", {}).get("repo", {}).get("sha256")
                if dev_repo and dev_repo == test_repo:
                    errors.append(f"duplicate repo hash across dev/test: {dev_id} and {test_id}")

    histograms = _histograms(manifest, items)
    classes = manifest.get("classes", [])
    for split, policy in manifest.get("splits", {}).items():
        if not isinstance(policy, dict):
            errors.append(f"split policy must be an object: {split}")
            continue
        actual_items = sum(1 for item in items if item.get("split") == split)
        if policy.get("items") != actual_items:
            errors.append(
                f"split {split} item count mismatch: manifest={policy.get('items')} actual={actual_items}"
            )
        floor = policy.get("min_per_class", 0)
        if not isinstance(floor, int) or isinstance(floor, bool) or floor < 0:
            errors.append(f"split {split} min_per_class must be a nonnegative integer")
            continue
        for label in classes:
            count = histograms.get(split, Counter()).get(label, 0)
            if count < floor:
                errors.append(
                    f"split {split} class {label} count {count} below min_per_class {floor}"
                )

    line_tolerance = manifest.get("line_tolerance", 3)
    distance = 2 * line_tolerance if isinstance(line_tolerance, int) else 6
    for item in items:
        findings = item.get("expected", {}).get("findings", [])
        if not isinstance(findings, list):
            continue
        for left_index, left in enumerate(findings):
            if not isinstance(left, dict):
                continue
            for right in findings[left_index + 1 :]:
                if not isinstance(right, dict):
                    continue
                if left.get("file") != right.get("file"):
                    continue
                if isinstance(left.get("line"), int) and isinstance(right.get("line"), int):
                    if abs(left["line"] - right["line"]) <= distance:
                        errors.append(
                            f"expected findings in {left['file']} are within {distance} lines: "
                            f"{left['line']} and {right['line']}"
                        )

    legacy = _experiment_ids(repo_root, "experiments/*.yaml")
    structured = _experiment_ids(repo_root, "experiments/structured/*.yaml")
    for experiment_id in sorted(legacy.keys() & structured.keys()):
        errors.append(
            f"experiment id collision: {experiment_id} in "
            f"{legacy[experiment_id]} and {structured[experiment_id]}"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate one taskset-v2 directory")
    parser.add_argument("taskset", type=Path)
    args = parser.parse_args(argv)
    root = args.taskset.resolve()
    errors = lint_taskset(root, repo_root=REPO_ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    manifest = _yaml_object(root / "manifest.yaml")
    items = [_yaml_object(path) for path in sorted((root / "items").glob("*.yaml"))]
    for split, histogram in sorted(_histograms(manifest, items).items()):
        rendered = ", ".join(f"{label}={histogram.get(label, 0)}" for label in manifest["classes"])
        print(f"{split}: {rendered}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
