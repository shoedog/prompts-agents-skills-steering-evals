"""Tests for the custom-agent (`agent.md`) deployment form.

Covers the four surfaces the agent form touches:
  * config enum: `varied_element_form` accepts `agent`, rejects unknown values;
  * composition: the agent frontmatter (name/description) is stripped, so the
    executor sees the body only — the same substance the other three forms give;
  * generation: a form=agent ablation config emits valid, re-parseable
    promptfoo YAML for both arms;
  * lint: `scripts/lint_artifacts.py` requires a present, within-budget
    `agent.md` (exercised against a throwaway fixture tree, never the real one).
"""
import copy
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness import config
from harness.config import ConfigError
from harness.gen_promptfoo import _strip_frontmatter, gen_promptfoo

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT / "scripts" / "lint_artifacts.py"

_BASE = {
    "id": "agent-tmp",
    "task_family": "review",
    "eval_shape": "ablation",
    "baseline_prompt": ["artifacts/baseline/review.md", "artifacts/baseline/output_format.md"],
    "varied_element": "composites/review-shape",
    "varied_element_form": "agent",
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


# --- config enum ----------------------------------------------------------- #
def test_enum_accepts_agent_form(tmp_path):
    cfg = config.load(_write(tmp_path))
    assert cfg.varied_element_form == "agent"
    # resolves to the real composite agent artifact on disk
    assert cfg.varied_element_path().name == "agent.md"
    assert cfg.varied_element_path().is_file()


def test_enum_rejects_unknown_form(tmp_path):
    def mut(d):
        d["varied_element_form"] = "bogus"
    with pytest.raises(ConfigError, match="varied_element_form must be one of") as exc:
        config.load(_write(tmp_path, mut))
    # the accepted set now advertises the agent form
    assert "agent" in str(exc.value)


# --- frontmatter stripping helper ------------------------------------------ #
def test_strip_frontmatter_removes_header_keeps_body():
    raw = "---\nname: review-shape\ndescription: route here.\n---\nBody line one.\nBody line two.\n"
    out = _strip_frontmatter(raw)
    assert out.startswith("Body line one.")
    assert "---" not in out
    assert "name:" not in out
    assert "description:" not in out


def test_strip_frontmatter_is_noop_without_header():
    plain = "# Heading\n\nBody text.\n"
    assert _strip_frontmatter(plain) == plain


# --- composition strips the agent header ----------------------------------- #
def test_agent_frontmatter_stripped_at_composition(tmp_path):
    cfg = config.load(_write(tmp_path))
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")
    ttxt = out["treatment"]["prompt"].read_text()

    # body substance from composites/review-shape/agent.md is present...
    assert "Review procedure, in order:" in ttxt
    assert "DISCONFIRM" in ttxt
    # ...but none of the deployment metadata survives composition.
    assert "---" not in ttxt
    assert "name: review-shape" not in ttxt
    assert "description:" not in ttxt

    # baseline arm carries the baseline artifact and no stray frontmatter.
    btxt = out["baseline"]["prompt"].read_text()
    assert "Review the code change below." in btxt
    assert "Review procedure, in order:" not in btxt
    assert "---" not in btxt


# --- generation: valid promptfoo YAML for a form=agent ablation ------------ #
def test_agent_form_generates_valid_promptfoo_yaml(tmp_path):
    cfg = config.load(_write(tmp_path))
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")

    for arm in ("baseline", "treatment"):
        doc = yaml.safe_load(out[arm]["yaml"].read_text())  # must re-parse
        assert doc["prompts"][0]["label"] == arm
        assert os.path.isfile(_strip_file(doc["prompts"][0]["id"]))
        prov = doc["providers"][0]
        assert os.path.isfile(_strip_file(prov["id"]))
        assert prov["config"]["arm"] == arm
        assert len(doc["tests"]) == 5
        a = doc["tests"][0]["assert"][0]
        assert a["type"] == "python"
        assert os.path.isfile(_strip_file(a["value"]))


# --- lint requires a present, within-budget agent.md ----------------------- #
def _build_lint_fixture(root: Path):
    """Minimal artifact tree + moves.yaml that the real lint accepts."""
    (root / "moves.yaml").write_text(
        yaml.safe_dump({"moves": [{"id": "foo", "classification": "element", "verdict": "keep"}]})
    )
    eld = root / "artifacts" / "elements" / "foo"
    eld.mkdir(parents=True)
    for form in ("prompt.md", "skill.md", "steering.md"):
        (eld / form).write_text("Small body for form.\n")
    (eld / "agent.md").write_text(
        "---\nname: foo\ndescription: Route here for foo.\n---\nSmall standing body.\n"
    )
    comp = root / "artifacts" / "composites" / "review-shape"
    comp.mkdir(parents=True)
    (comp / "prompt.md").write_text("Composite prompt body.\n")
    (comp / "agent.md").write_text(
        "---\nname: review-shape\ndescription: Route here.\n---\nComposite standing body.\n"
    )
    return eld, comp


def _run_lint(cwd: Path):
    return subprocess.run(
        [sys.executable, str(LINT_SCRIPT)],
        cwd=str(cwd), capture_output=True, text=True,
    )


def test_lint_passes_on_complete_fixture(tmp_path):
    _build_lint_fixture(tmp_path)
    res = _run_lint(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "OK" in res.stdout


def test_lint_fails_on_missing_agent_md(tmp_path):
    eld, _ = _build_lint_fixture(tmp_path)
    (eld / "agent.md").unlink()
    res = _run_lint(tmp_path)
    assert res.returncode != 0
    combined = res.stdout + res.stderr
    assert "agent.md" in combined
    assert "missing" in combined


def test_lint_fails_on_missing_composite_agent_md(tmp_path):
    _, comp = _build_lint_fixture(tmp_path)
    (comp / "agent.md").unlink()
    res = _run_lint(tmp_path)
    assert res.returncode != 0
    assert "composites/review-shape/agent.md" in (res.stdout + res.stderr)


def test_lint_fails_on_oversized_agent_md(tmp_path):
    eld, _ = _build_lint_fixture(tmp_path)
    # ~200 tokens, well over the 150 cap
    (eld / "agent.md").write_text(
        "---\nname: foo\ndescription: Route here.\n---\n" + ("word " * 200) + "\n"
    )
    res = _run_lint(tmp_path)
    assert res.returncode != 0
    combined = res.stdout + res.stderr
    assert "agent.md" in combined
    assert "> 150" in combined
