"""gen_promptfoo tests — generate both arms' YAML and re-parse; no promptfoo run."""
import copy
import os

import pytest
import yaml

from harness import config
from harness.config import ConfigError
from harness.gen_promptfoo import gen_promptfoo

_BASE = {
    "id": "gp-tmp",
    "task_family": "review",
    "eval_shape": "ablation",
    "baseline_prompt": ["artifacts/baseline/review.md", "artifacts/baseline/output_format.md"],
    "varied_element": "composites/review-shape",
    "varied_element_form": "prompt",
    "taskset": "tasksets/smoke",
    "executor": {"model": "claude-haiku-4-5-20251001", "tier": "weak"},
    "judge": {
        "provider": "codex", "model": "gpt-5.5", "effort": "medium",
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


def _strip_file(ref):
    assert ref.startswith("file://")
    return ref[len("file://"):]


def test_generates_valid_yaml_for_both_arms(tmp_path):
    cfg = config.load("experiments/smoke.yaml")
    rdir = tmp_path / "results"
    out = gen_promptfoo(cfg, results_dir=rdir)

    for arm in ("baseline", "treatment"):
        ypath = out[arm]["yaml"]
        assert ypath.is_file()
        doc = yaml.safe_load(ypath.read_text())  # must re-parse

        # prompt block references an existing file, labeled by arm
        assert doc["prompts"][0]["label"] == arm
        prompt_file = _strip_file(doc["prompts"][0]["id"])
        assert os.path.isfile(prompt_file)
        assert out[arm]["prompt"].is_file()

        # provider block: our shim + arm hard-coded into config
        prov = doc["providers"][0]
        assert os.path.isfile(_strip_file(prov["id"]))
        assert prov["config"]["arm"] == arm
        assert prov["config"]["exp_id"] == "smoke"
        assert prov["config"]["model"] == cfg.executor.model

        # one test per item, each with a python assert referencing our file
        assert len(doc["tests"]) == 5
        t0 = doc["tests"][0]
        assert t0["vars"]["arm"] == arm
        assert t0["vars"]["exp_id"] == "smoke"
        assert "task_input" in t0["vars"]
        assert t0["vars"]["truth_path"].endswith("truth.yaml")
        a = t0["assert"][0]
        assert a["type"] == "python"
        assert os.path.isfile(_strip_file(a["value"]))


def test_prompt_composition_differs_between_arms(tmp_path):
    cfg = config.load("experiments/smoke.yaml")
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")
    btxt = out["baseline"]["prompt"].read_text()
    ttxt = out["treatment"]["prompt"].read_text()

    assert "{{task_input}}" in btxt
    assert "{{task_input}}" in ttxt
    # baseline artifacts are present in both
    assert "Review the code change below." in btxt
    assert "Review the code change below." in ttxt
    # the varied element only appears in the treatment arm
    assert "Review procedure" in ttxt
    assert "Review procedure" not in btxt


def test_unfilled_slot_guard_rejects_templated_element(tmp_path):
    # goal-restatement/prompt.md carries `<...>` template slots.
    def mut(d):
        d["varied_element"] = "elements/goal-restatement"
    cfg = config.load(_write(tmp_path, mut))
    with pytest.raises(ConfigError, match="per-task instantiation"):
        gen_promptfoo(cfg, results_dir=tmp_path / "results")


def test_concrete_composite_passes_guard(tmp_path):
    # the exp1 composite is fully concrete: no ConfigError.
    cfg = config.load("experiments/exp1-review-shape.yaml")
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")
    assert out["treatment"]["prompt"].is_file()


def test_negative_control_comment_stripped_from_composed_prompt(tmp_path):
    # The negative-control artifact's quarantine warning is an HTML comment
    # (`<!-- NEGATIVE CONTROL ... -->`). It must never reach the composed
    # treatment prompt an executor sees — the narrative body must, and does.
    cfg = config.load("experiments/exp2-negative-control.yaml")
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")
    ttxt = out["treatment"]["prompt"].read_text()

    # the narrative content is present...
    assert "Repository Overview" in ttxt
    assert "layered architecture" in ttxt
    # ...but no raw HTML comment markers survive composition...
    assert "<!--" not in ttxt
    assert "-->" not in ttxt
    # ...and no phrasing that would tell the executor it's in a control arm.
    assert "negative control" not in ttxt.lower()

    # baseline prompt is untouched by the same guarantee (no comments there
    # to begin with, but the strip must be a no-op, not a corruption).
    btxt = out["baseline"]["prompt"].read_text()
    assert "Review the code change below." in btxt
    assert "<!--" not in btxt


def test_html_comment_stripped_from_baseline_and_element_parts(tmp_path):
    # Direct unit test of the stripping helper itself, independent of which
    # experiment config is used — proves the fix is generic (applies to any
    # composed part), not special-cased to the negative-control artifact.
    from harness.gen_promptfoo import _strip_html_comments

    raw = "<!-- warning: do not leak this -->\n\n# Heading\n\nBody text.\n"
    stripped = _strip_html_comments(raw)
    assert "<!--" not in stripped
    assert "warning" not in stripped
    assert stripped.startswith("# Heading")

    # a no-op on text with no comments at all
    plain = "# Heading\n\nBody text.\n"
    assert _strip_html_comments(plain) == plain
