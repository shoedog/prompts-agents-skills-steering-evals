"""Config loader/validation tests — validated against the real files on disk."""
import copy

import pytest
import yaml

from harness import config
from harness.config import REPO_ROOT, ConfigError

_BASE = {
    "id": "tmp-exp",
    "task_family": "review",
    "eval_shape": "ablation",
    "baseline_prompt": ["artifacts/baseline/review.md", "artifacts/baseline/output_format.md"],
    "varied_element": "composites/review-shape",
    "varied_element_form": "prompt",
    "taskset": "tasksets/smoke",
    "executor": {"model": "claude-haiku-4-5-20251001", "tier": "weak"},
    "judge": {
        "provider": "codex",
        "model": "gpt-5.5",
        "effort": "medium",
        "rubric": "harness/rubrics/review_judge.md",
        "schema": "harness/rubrics/review_judge.schema.json",
    },
    "token_budget": {"max_cost_usd": 10.0, "max_items": 5},
    "negative_control": False,
}


def _write(tmp_path, mutate=None):
    doc = copy.deepcopy(_BASE)
    if mutate:
        mutate(doc)
    p = tmp_path / "exp.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


# --------------------------------------------------------------------------- #
def test_real_configs_load():
    for name in (
        "experiments/smoke.yaml",
        "experiments/exp1-review-shape.yaml",
        "experiments/exp2-negative-control.yaml",
    ):
        cfg = config.load(name)
        assert cfg.varied_element_path().is_file()
        for p in cfg.baseline_paths():
            assert p.is_file()
        assert cfg.taskset_path().is_dir()
        assert cfg.rubric_path().is_file()
        assert cfg.schema_path().is_file()

    smoke = config.load("experiments/smoke.yaml")
    assert smoke.id == "smoke"
    assert smoke.token_budget.max_items == 5
    exp1 = config.load("experiments/exp1-review-shape.yaml")
    assert exp1.id == "exp1-review-shape"
    assert exp1.taskset == "tasksets/review-seeded"


def test_exp2_negative_control_config():
    cfg = config.load("experiments/exp2-negative-control.yaml")
    assert cfg.id == "exp2-negative-control"
    assert cfg.negative_control is True
    assert cfg.varied_element == "negative_control"
    assert cfg.varied_element_path() == (
        REPO_ROOT / "artifacts" / "negative_control" / "prompt.md"
    )
    assert cfg.varied_element_path().is_file()
    # same budget and taskset as exp1, per the mirrored-config requirement
    exp1 = config.load("experiments/exp1-review-shape.yaml")
    assert cfg.token_budget.max_cost_usd == exp1.token_budget.max_cost_usd
    assert cfg.token_budget.max_items == exp1.token_budget.max_items
    assert cfg.taskset == exp1.taskset
    assert cfg.baseline_prompt == exp1.baseline_prompt


def test_valid_tmp_config_loads(tmp_path):
    cfg = config.load(_write(tmp_path))
    assert cfg.id == "tmp-exp"
    assert cfg.executor.tier == "weak"
    assert cfg.results_dir() == REPO_ROOT / "results" / "tmp-exp" / "weak"


def test_varied_element_list_rejected(tmp_path):
    def mut(d):
        d["varied_element"] = ["composites/review-shape", "elements/goal-restatement"]
    with pytest.raises(ConfigError, match="one element per experiment"):
        config.load(_write(tmp_path, mut))


def test_varied_element_must_resolve_to_one_file(tmp_path):
    def mut(d):
        d["varied_element"] = "composites/does-not-exist"
    with pytest.raises(ConfigError):
        config.load(_write(tmp_path, mut))


def test_varied_element_form_missing_file(tmp_path):
    # composites/review-shape has a prompt.md but not a skill.md.
    def mut(d):
        d["varied_element_form"] = "skill"
    with pytest.raises(ConfigError):
        config.load(_write(tmp_path, mut))


@pytest.mark.parametrize("key", ["id", "eval_shape", "baseline_prompt", "varied_element",
                                 "varied_element_form", "taskset", "executor", "judge",
                                 "token_budget"])
def test_missing_required_key_raises(tmp_path, key):
    def mut(d):
        d.pop(key)
    with pytest.raises(ConfigError):
        config.load(_write(tmp_path, mut))


def test_missing_nested_key_raises(tmp_path):
    def mut(d):
        d["judge"].pop("schema")
    with pytest.raises(ConfigError):
        config.load(_write(tmp_path, mut))


def test_negative_control_defaults_false(tmp_path):
    def mut(d):
        d.pop("negative_control")
    cfg = config.load(_write(tmp_path, mut))
    assert cfg.negative_control is False


def test_bad_eval_shape_rejected(tmp_path):
    def mut(d):
        d["eval_shape"] = "bogus"
    with pytest.raises(ConfigError):
        config.load(_write(tmp_path, mut))


def test_load_taskset_reads_items_and_task_input():
    cfg = config.load("experiments/smoke.yaml")
    items = config.load_taskset(cfg)
    assert len(items) == 5  # max_items
    first = items[0]
    assert first["id"] == "sm-01"
    assert first["seeded"] is True
    assert "recent" in first["task_input"]      # from context.md
    assert "diff" in first["task_input"] or "@@" in first["task_input"]  # from diff.patch
    assert first["truth_path"].endswith("sm-01/truth.yaml")
