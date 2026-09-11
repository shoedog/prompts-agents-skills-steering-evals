from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_NAMES = (
    "targets.schema.json",
    "observations.schema.json",
    "classify_error_handling.schema.json",
    "llm_run_envelope.schema.json",
    "taskset_v2.schema.json",
)
CLASSES = [
    "correct",
    "swallowed_fatal",
    "retried_non_retryable",
    "no_retry_on_transient",
    "partial_as_success",
    "resource_leak_on_error",
    "missing_timeout",
    "unbounded_retry",
    "unclear",
]


def _write_json(path: Path, value: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def minimal_target(index: int = 1) -> dict[str, Any]:
    return {
        "id": f"{index:064x}",
        "site": {"file": f"svc/client_{index}.py", "line": 10 + index, "symbol": "fetch"},
        "kind": "external_call",
        "category": "missing_error_handling",
        "expected": {"property": "error_handled"},
        "source_algorithm": "absence",
        "confidence": "exact",
        "tier": "asserted",
        "severity": "warning",
        "description": f"fixture target {index}",
        "parse_quality": "clean",
    }


def minimal_slice(index: int = 1) -> dict[str, Any]:
    line = 10 + index
    return {
        "text": f"{line}: return client.fetch()\n",
        "file": f"svc/client_{index}.py",
        "function": "fetch_data",
        "lines": [line, line],
        "language": "python",
    }


def minimal_observation(index: int = 1) -> dict[str, Any]:
    target = minimal_target(index)
    return {
        "target_id": target["id"],
        "site": target["site"],
        "reached": True,
        "fault": {
            "catalog_id": f"http.fixture_{index}",
            "kind": "http",
            "name": "TimeoutError",
            "retryable": True,
            "fatal": False,
        },
        "observed": {
            "outcome": "propagated",
            "duration_ms": index,
            "test": {"id": f"test_fixture_{index}", "status": "passed"},
        },
        "log_excerpt": f"fixture log {index}",
    }


def build_v2_taskset(root: Path, *, items: list[dict[str, Any]]) -> Path:
    contracts = root / "contracts"
    contracts.mkdir(parents=True, exist_ok=True)
    for name in CONTRACT_NAMES:
        shutil.copy2(REPO_ROOT / "contracts" / name, contracts / name)

    taskset = root / "tasksets" / "structured" / "classify_error_handling"
    (taskset / "items").mkdir(parents=True, exist_ok=True)
    manifest_items: list[dict[str, Any]] = []
    counts = {"dev": 0, "test": 0}
    for index, spec in enumerate(items, 1):
        item_id = spec.get("id", f"eh-py-{index:04d}")
        split = spec.get("split", "dev")
        label = spec.get("label", CLASSES[(index - 1) % len(CLASSES)])
        target = spec.get("target", minimal_target(index))
        slice_value = spec.get("slice", minimal_slice(index))
        observation = spec.get("observation", minimal_observation(index))
        input_dir = taskset / "inputs" / item_id
        refs = {}
        for name, value in (
            ("target", target),
            ("slice", slice_value),
            ("observation", observation),
        ):
            path = input_dir / f"{name}.json"
            digest = _write_json(path, value)
            refs[name] = {"path": path.relative_to(taskset).as_posix(), "sha256": digest}
        refs["dependency_semantics"] = {
            "source": "catalog",
            "text": f"fixture dependency semantics {index}",
        }
        item = {
            "id": item_id,
            "task": "classify_error_handling",
            "defect_class": f"error_handling.{label}",
            "language": "python",
            "source": "synthetic",
            "split": split,
            "contamination_risk": "low",
            "inputs": refs,
            "expected": {
                "label": label,
                "confidence_min": 0.5,
                "rationale_must_mention": ["fixture"],
                "evidence_lines_subset": [10 + index],
            },
            "labels": {"primary": {"by": "fixture", "at": "2026-09-04"}},
        }
        item.update(spec.get("item_updates", {}))
        (taskset / "items" / f"{item_id}.yaml").write_text(yaml.safe_dump(item, sort_keys=False))
        manifest_items.append(
            {"id": item_id, "split": split, "contamination_risk": "low"}
        )
        counts[split] += 1

    manifest = {
        "taskset": "classify_error_handling",
        "schema_version": 2,
        "task": "classify_error_handling",
        "request_schema": "contracts/classify_error_handling.schema.json#/$defs/request",
        "response_schema": "contracts/classify_error_handling.schema.json#/$defs/response",
        "labeling_guide": "LABELING.md",
        "class_field": "class",
        "classes": CLASSES,
        "splits": {
            "dev": {"items": counts["dev"], "min_per_class": 0},
            "test": {"items": counts["test"], "min_per_class": 0, "consulted": 0},
        },
        "items": manifest_items,
    }
    (taskset / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (taskset / "LABELING.md").write_text("# Fixture labels\n")
    return taskset


@pytest.fixture
def fixture_taskset(tmp_path: Path) -> Path:
    return build_v2_taskset(tmp_path, items=[{}])


@pytest.fixture
def taskset_case(tmp_path: Path):
    def build(mutation: str) -> tuple[Path, Path]:
        items = [{"id": "eh-py-0001", "split": "dev", "label": "correct"}]
        if mutation == "cross_split_duplicate":
            items.append({"id": "eh-py-0002", "split": "test", "label": "correct"})
        root = build_v2_taskset(tmp_path / mutation, items=items)
        repo_root = root.parents[2]

        if mutation == "bad_hash":
            (root / "inputs/eh-py-0001/target.json").write_text("mutated\n")
        elif mutation == "cross_split_duplicate":
            first = yaml.safe_load((root / "items/eh-py-0001.yaml").read_text())
            second_path = root / "items/eh-py-0002.yaml"
            second = yaml.safe_load(second_path.read_text())
            second["inputs"] = first["inputs"]
            second_path.write_text(yaml.safe_dump(second, sort_keys=False))
        elif mutation == "class_floor":
            path = root / "manifest.yaml"
            manifest = yaml.safe_load(path.read_text())
            manifest["splits"]["dev"]["min_per_class"] = 1
            path.write_text(yaml.safe_dump(manifest, sort_keys=False))
        elif mutation == "finding_spacing":
            path = root / "items/eh-py-0001.yaml"
            item = yaml.safe_load(path.read_text())
            item["expected"]["findings"] = [
                {"category": "x", "file": "a.py", "line": 10, "tier": "asserted"},
                {"category": "y", "file": "a.py", "line": 14, "tier": "candidate"},
            ]
            path.write_text(yaml.safe_dump(item, sort_keys=False))
        elif mutation == "orphan_item":
            shutil.copy2(root / "items/eh-py-0001.yaml", root / "items/orphan.yaml")
        elif mutation == "id_collision":
            (repo_root / "experiments/structured").mkdir(parents=True)
            (repo_root / "experiments/legacy.yaml").write_text("id: shared-id\n")
            (repo_root / "experiments/structured/new.yaml").write_text(
                "kind: structured_task\nid: shared-id\n"
            )
        return root, repo_root

    return build
