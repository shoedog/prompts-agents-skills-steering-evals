from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
import yaml

from harness.structured.config import ConfigError, load_config
from harness.tests.structured_support import build_v2_taskset


def _config(root, **updates):
    build_v2_taskset(root, items=[{}])
    raw = {
        "kind": "structured_task",
        "id": "st-fixture",
        "task": "classify_error_handling",
        "request_schema": "contracts/classify_error_handling.schema.json#/$defs/request",
        "response_schema": "contracts/classify_error_handling.schema.json#/$defs/response",
        "taskset": "tasksets/structured/classify_error_handling",
        "split": "dev",
        "versions": [
            {
                "name": "v1",
                "task_version": "2026-09-04.1",
                "provider": {"kind": "stub", "model": "fixture"},
            }
        ],
        "baseline_version": "v1",
        "samples_per_item": 1,
        "seed": 20260904,
        "asserts": [{"type": "schema", "hard": True}],
        "stats": {"bootstrap_resamples": 20, "seed": 20260904},
        "token_budget": {"max_cost_usd": 0, "max_items": 10},
    }
    raw.update(updates)
    path = root / "experiments/structured/test.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path


def test_load_structured_config_resolves_paths_and_is_frozen(tmp_path):
    cfg = load_config(_config(tmp_path), root=tmp_path)
    assert cfg.id == "st-fixture"
    assert cfg.taskset == tmp_path / "tasksets/structured/classify_error_handling"
    assert cfg.request_schema["type"] == "object"
    with pytest.raises(FrozenInstanceError):
        cfg.id = "changed"


@pytest.mark.parametrize(
    "updates, message",
    [
        ({"kind": "review_ablation"}, "unknown structured kind"),
        ({"id": "bad-prefix"}, "id must start with st-"),
        ({"versions": [{"name": "v1"}, {"name": "v1"}]}, "duplicate version"),
        ({"baseline_version": "missing"}, "baseline_version"),
        ({"samples_per_item": 0}, "samples_per_item"),
        ({"stats": {"bootstrap_resamples": 0, "seed": 1}}, "bootstrap_resamples"),
        ({"token_budget": {"max_items": 0}}, "max_items"),
        ({"jobs": 0}, "jobs"),
        ({"split": "holdout"}, "split"),
    ],
)
def test_config_rejects_invalid_values(tmp_path, updates, message):
    with pytest.raises(ConfigError, match=message):
        load_config(_config(tmp_path, **updates), root=tmp_path)


def test_config_rejects_path_escape(tmp_path):
    with pytest.raises(ConfigError, match="escapes repo root"):
        load_config(_config(tmp_path, taskset="../elsewhere"), root=tmp_path)
