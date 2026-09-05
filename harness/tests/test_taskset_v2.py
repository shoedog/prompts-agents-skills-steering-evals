from __future__ import annotations

import json

import pytest
import yaml

from harness.tests.structured_support import build_v2_taskset, fixture_taskset
from harness.structured.taskset import (
    TasksetError,
    assemble_request,
    load_taskset,
    resolve_schema_ref,
    sha256_directory,
    sha256_file,
)


def test_load_taskset_rejects_a_mutated_pinned_input(fixture_taskset):
    target = fixture_taskset / "inputs" / "eh-py-0001" / "target.json"
    target.write_text(target.read_text() + "\n")
    with pytest.raises(TasksetError, match="sha256 mismatch.*target.json"):
        load_taskset(fixture_taskset, split="dev", max_items=10)


def test_hash_check_precedes_json_parsing(fixture_taskset):
    target = fixture_taskset / "inputs" / "eh-py-0001" / "target.json"
    target.write_text("not json")
    with pytest.raises(TasksetError, match="sha256 mismatch"):
        load_taskset(fixture_taskset, split="dev", max_items=10)


def test_assemble_request_injects_version_and_validates_schema(fixture_taskset):
    taskset = load_taskset(fixture_taskset, split="dev", max_items=10)
    item = taskset.items[0]
    request = assemble_request(
        item,
        task_version="2026-09-04.1",
        request_schema=taskset.request_schema,
    )
    assert request["task"] == "classify_error_handling"
    assert request["task_version"] == "2026-09-04.1"
    target_path = fixture_taskset / "inputs" / "eh-py-0001" / "target.json"
    assert request["target"] == json.loads(target_path.read_text())
    assert request["observation"]["log_excerpt"] == "fixture log 1"
    assert request["dependency_semantics"]["source"] == "catalog"


def test_load_validates_target_contract(fixture_taskset):
    target_path = fixture_taskset / "inputs/eh-py-0001/target.json"
    target_path.write_text("{}\n")
    item_path = fixture_taskset / "items/eh-py-0001.yaml"
    import yaml

    item = yaml.safe_load(item_path.read_text())
    item["inputs"]["target"]["sha256"] = sha256_file(target_path)
    item_path.write_text(yaml.safe_dump(item, sort_keys=False))
    with pytest.raises(TasksetError, match="target.*schema"):
        load_taskset(fixture_taskset, split="dev", max_items=10)


def test_schema_ref_cannot_escape_root(tmp_path):
    with pytest.raises(TasksetError, match="escapes repo root"):
        resolve_schema_ref(tmp_path, "../outside.json#/$defs/request")


def test_load_rejects_unknown_split_and_nonpositive_limit(fixture_taskset):
    with pytest.raises(TasksetError, match="unknown split"):
        load_taskset(fixture_taskset, split="holdout", max_items=10)
    with pytest.raises(TasksetError, match="max_items"):
        load_taskset(fixture_taskset, split="dev", max_items=0)


def test_load_rejects_manifest_count_drift(fixture_taskset):
    path = fixture_taskset / "manifest.yaml"
    manifest = yaml.safe_load(path.read_text())
    manifest["splits"]["dev"]["items"] = 2
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    with pytest.raises(TasksetError, match="manifest split dev count"):
        load_taskset(fixture_taskset, split="dev", max_items=10)


def test_load_rejects_labeling_guide_escape(fixture_taskset):
    path = fixture_taskset / "manifest.yaml"
    manifest = yaml.safe_load(path.read_text())
    manifest["labeling_guide"] = "../../outside.md"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    with pytest.raises(TasksetError, match="labeling_guide path escapes taskset root"):
        load_taskset(fixture_taskset, split="dev", max_items=10)


def test_analyzer_directory_and_plain_diff_are_hashed(tmp_path):
    root = build_v2_taskset(tmp_path, items=[{}])
    repo = root / "inputs/px-py-0001/repo"
    repo.mkdir(parents=True)
    (repo / "fixture.py").write_text("value = 1\n")
    diff = root / "inputs/px-py-0001/change.patch"
    diff.write_text("--- a/fixture.py\n+++ b/fixture.py\n")
    item = {
        "id": "px-py-0001",
        "task": "prism_analyzer",
        "language": "python",
        "algorithm": "absence",
        "source": "fixture",
        "split": "dev",
        "contamination_risk": "low",
        "ignore": ["*.tmp"],
        "inputs": {
            "repo": {
                "path": "inputs/px-py-0001/repo",
                "sha256": sha256_directory(repo, ignore=["*.tmp"]),
            },
            "diff": {
                "path": "inputs/px-py-0001/change.patch",
                "sha256": sha256_file(diff),
            },
        },
        "expected": {"findings": [], "negative_findings": [], "max_findings": 6},
    }
    (root / "items/eh-py-0001.yaml").unlink()
    (root / "items/px-py-0001.yaml").write_text(yaml.safe_dump(item, sort_keys=False))
    manifest = {
        "taskset": "prism_fixtures",
        "schema_version": 2,
        "task": "prism_analyzer",
        "labeling_guide": "LABELING.md",
        "splits": {
            "dev": {"items": 1, "min_per_class": 0},
            "test": {"items": 0, "min_per_class": 0, "consulted": 0},
        },
        "items": [{"id": "px-py-0001", "split": "dev", "contamination_risk": "low"}],
    }
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    loaded = load_taskset(root, split="dev", max_items=10)
    assert set(loaded.items[0].inputs) == {"repo", "diff"}
    assert loaded.items[0].input_values == {}
    (repo / "fixture.py").write_text("value = 2\n")
    with pytest.raises(TasksetError, match="sha256 mismatch.*repo"):
        load_taskset(root, split="dev", max_items=10)
