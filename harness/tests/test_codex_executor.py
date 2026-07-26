"""Multi-family executor tiers (workstream D): config plumbing for
`executor.provider`/`usd_per_mtok`/`effort`, the same-family-judge
self-preference guard, the `promptfoo_codex.py` provider shim's per-call
record schema, and `gen_promptfoo.py`'s provider-id selection.

All tests here mock `harness.providers.promptfoo_codex.run_codex` — no live
`codex` process is ever spawned by pytest. Live smoke calls are run manually
outside pytest (see task-D-report.md).

The claude-provider regression test below compares gen_promptfoo's output for
experiments/smoke.yaml against a golden fixture captured from the SAME config
BEFORE this workstream added codex provider support (results_dir/prompt-path
placeholders normalized to "<RDIR>" so the comparison is stable across
`tmp_path` runs) — proof the claude path stayed byte-identical.
"""
import copy
import json
from unittest.mock import patch

import pytest
import yaml

from harness import config
from harness.config import ConfigError
from harness.gen_promptfoo import gen_promptfoo
from harness.providers.errors import ProviderError
from harness.providers.promptfoo_codex import call_api

_BASE = {
    "id": "codex-tmp",
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


# --------------------------------------------------------------------------- #
# config.py: executor.provider / usd_per_mtok / effort defaults + overrides
# --------------------------------------------------------------------------- #
def test_executor_provider_defaults_to_claude(tmp_path):
    cfg = config.load(_write(tmp_path))
    assert cfg.executor.provider == "claude"


def test_executor_usd_per_mtok_defaults_to_none(tmp_path):
    cfg = config.load(_write(tmp_path))
    assert cfg.executor.usd_per_mtok is None


def test_executor_effort_defaults_to_medium(tmp_path):
    cfg = config.load(_write(tmp_path))
    assert cfg.executor.effort == "medium"


def test_executor_provider_codex_accepted(tmp_path):
    def mut(d):
        d["executor"]["provider"] = "codex"
        d["executor"]["model"] = "gpt-5.5"
        d["judge"]["provider"] = "claude"  # different family: guard doesn't apply
    cfg = config.load(_write(tmp_path, mut))
    assert cfg.executor.provider == "codex"


def test_executor_provider_invalid_rejected(tmp_path):
    def mut(d):
        d["executor"]["provider"] = "gemini"
    with pytest.raises(ConfigError, match="executor.provider"):
        config.load(_write(tmp_path, mut))


def test_executor_usd_per_mtok_override(tmp_path):
    def mut(d):
        d["executor"]["usd_per_mtok"] = 3.5
    cfg = config.load(_write(tmp_path, mut))
    assert cfg.executor.usd_per_mtok == 3.5


def test_executor_effort_override(tmp_path):
    def mut(d):
        d["executor"]["effort"] = "low"
    cfg = config.load(_write(tmp_path, mut))
    assert cfg.executor.effort == "low"


def test_existing_configs_still_load_unchanged():
    # All real configs predate `provider`/`usd_per_mtok`/`effort` and
    # `allow_same_family_judge` — they must load with the documented defaults,
    # not fail or silently change shape.
    for name in (
        "experiments/smoke.yaml",
        "experiments/exp1-review-shape.yaml",
        "experiments/exp2-negative-control.yaml",
    ):
        cfg = config.load(name)
        assert cfg.executor.provider == "claude"
        assert cfg.executor.usd_per_mtok is None
        assert cfg.executor.effort == "medium"
        assert cfg.allow_same_family_judge is False


# --------------------------------------------------------------------------- #
# config.py: same-family-judge self-preference guard
# --------------------------------------------------------------------------- #
def test_same_family_judge_raises_without_override(tmp_path):
    def mut(d):
        d["executor"]["provider"] = "codex"
        d["executor"]["model"] = "gpt-5.5"
        # d["judge"]["provider"] is already "codex" in _BASE
    with pytest.raises(ConfigError, match="allow_same_family_judge"):
        config.load(_write(tmp_path, mut))


def test_same_family_judge_error_names_reason_and_override(tmp_path):
    def mut(d):
        d["executor"]["provider"] = "codex"
        d["executor"]["model"] = "gpt-5.5"
    with pytest.raises(ConfigError) as exc_info:
        config.load(_write(tmp_path, mut))
    msg = str(exc_info.value)
    assert "self-preference" in msg
    assert "allow_same_family_judge" in msg
    assert "codex" in msg


def test_same_family_judge_override_flag_allows(tmp_path):
    def mut(d):
        d["executor"]["provider"] = "codex"
        d["executor"]["model"] = "gpt-5.5"
        d["allow_same_family_judge"] = True
    cfg = config.load(_write(tmp_path, mut))
    assert cfg.executor.provider == "codex"
    assert cfg.judge.provider == "codex"
    assert cfg.allow_same_family_judge is True


def test_different_family_never_triggers_guard(tmp_path):
    # default shape: claude executor, codex judge (today's only real
    # combination) — must never require the override.
    cfg = config.load(_write(tmp_path))
    assert cfg.executor.provider == "claude"
    assert cfg.judge.provider == "codex"
    assert cfg.allow_same_family_judge is False


# --------------------------------------------------------------------------- #
# promptfoo_codex.py: call_api per-call record schema
# --------------------------------------------------------------------------- #
def _options(results_dir, **extra_config):
    cfg = {
        "model": "gpt-5.5",
        "tier": "weak",
        "arm": "baseline",
        "exp_id": "smoke",
        "results_dir": str(results_dir),
    }
    cfg.update(extra_config)
    return {"config": cfg}


def _context(task_id="sm-01"):
    return {"vars": {"task_id": task_id}}


_MANDATORY_RECORD_KEYS = (
    "exp_id", "arm", "task_id", "tier", "model",
    "fresh_input_tokens", "cache_creation_tokens", "cache_read_tokens",
    "output_tokens", "input_tokens_logical", "cost_usd", "duration_ms",
)


def test_record_schema_without_usd_per_mtok(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 1234}
        result = call_api("prompt text", _options(tmp_path), _context())

    assert result["output"] == "OK"
    assert result["tokenUsage"] == {"total": 1234}
    assert result["cost"] == 0.0

    record_path = tmp_path / "calls" / "baseline-sm-01.json"
    assert record_path.is_file()
    record = json.loads(record_path.read_text())

    for key in _MANDATORY_RECORD_KEYS:
        assert key in record, f"missing mandatory key {key!r}"

    assert record["fresh_input_tokens"] is None
    assert record["cache_creation_tokens"] is None
    assert record["cache_read_tokens"] is None
    assert record["output_tokens"] is None
    assert record["input_tokens_logical"] is None
    assert record["cost_usd"] is None  # no usd_per_mtok configured: unpriced, not free
    assert record["tokens_used"] == 1234
    assert record["tokens_only"] is True
    assert record["exp_id"] == "smoke"
    assert record["arm"] == "baseline"
    assert record["task_id"] == "sm-01"
    assert record["tier"] == "weak"
    assert record["model"] == "gpt-5.5"
    assert isinstance(record["duration_ms"], int)


def test_record_schema_with_usd_per_mtok(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 2_000_000}
        result = call_api(
            "prompt text", _options(tmp_path, usd_per_mtok=3.0), _context()
        )

    record = json.loads((tmp_path / "calls" / "baseline-sm-01.json").read_text())
    assert record["cost_usd"] == pytest.approx(6.0)  # 2,000,000 / 1e6 * 3.0
    assert record["tokens_only"] is True
    assert result["cost"] == pytest.approx(6.0)


def test_tokens_used_none_yields_null_cost_and_empty_token_usage(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": None}
        result = call_api(
            "prompt text", _options(tmp_path, usd_per_mtok=3.0), _context()
        )

    record = json.loads((tmp_path / "calls" / "baseline-sm-01.json").read_text())
    assert record["tokens_used"] is None
    assert record["cost_usd"] is None  # can't price an unknown token count
    assert result["tokenUsage"] == {}
    assert result["cost"] == 0.0


def test_model_and_effort_passed_through_to_run_codex(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 10}
        call_api(
            "prompt text",
            _options(tmp_path, model="gpt-4o-mini", effort="low"),
            _context(),
        )

    _, kwargs = mock_run.call_args
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["effort"] == "low"


def test_effort_defaults_to_medium_when_not_configured(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 10}
        call_api("prompt text", _options(tmp_path), _context())

    _, kwargs = mock_run.call_args
    assert kwargs["effort"] == "medium"


def test_sandbox_is_per_call_fresh_and_read_only_via_run_codex(tmp_path):
    sandbox = tmp_path / "sandbox" / "baseline-sm-01"
    sandbox.mkdir(parents=True)
    (sandbox / "stale.txt").write_text("leftover from a previous item")

    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 10}
        call_api("prompt text", _options(tmp_path), _context())

    # fresh: the stale file from a previous call must be gone
    assert not (sandbox / "stale.txt").exists()
    assert sandbox.is_dir()
    # per-(arm, task): the sandbox cwd handed to run_codex is this exact dir
    # (run_codex itself applies `--sandbox read-only` — nothing to mock here).
    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == str(sandbox)


def test_sandbox_path_is_scoped_by_arm_and_task_id(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.return_value = {"output": "OK", "tokens_used": 10}
        call_api(
            "prompt text",
            _options(tmp_path, arm="treatment"),
            _context(task_id="sm-02"),
        )

    expected_sandbox = tmp_path / "sandbox" / "treatment-sm-02"
    assert expected_sandbox.is_dir()
    assert (tmp_path / "calls" / "treatment-sm-02.json").is_file()


def test_provider_error_returns_error_dict_and_writes_no_record(tmp_path):
    with patch("harness.providers.promptfoo_codex.run_codex") as mock_run:
        mock_run.side_effect = ProviderError("boom", stderr_tail="stderr detail")
        result = call_api("prompt text", _options(tmp_path), _context())

    assert "error" in result
    assert "boom" in result["error"]
    assert "stderr detail" in result["error"]
    # a failed item writes no calls/ record — same contract as promptfoo_claude.py
    assert not (tmp_path / "calls" / "baseline-sm-01.json").exists()


# --------------------------------------------------------------------------- #
# gen_promptfoo.py: codex provider id selection + effort/usd_per_mtok threading
# --------------------------------------------------------------------------- #
def test_gen_emits_codex_provider_id_and_config(tmp_path):
    def mut(d):
        d["executor"] = {
            "model": "gpt-5.5", "tier": "weak", "provider": "codex",
            "effort": "low", "usd_per_mtok": 3.0,
        }
        d["allow_same_family_judge"] = True  # judge stays "codex" in _BASE
    cfg = config.load(_write(tmp_path, mut))
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")

    for arm in ("baseline", "treatment"):
        doc = yaml.safe_load(out[arm]["yaml"].read_text())
        prov = doc["providers"][0]
        assert prov["id"].endswith("harness/providers/promptfoo_codex.py")
        assert prov["config"]["model"] == "gpt-5.5"
        assert prov["config"]["effort"] == "low"
        assert prov["config"]["usd_per_mtok"] == 3.0
        assert prov["config"]["arm"] == arm


def test_gen_codex_provider_config_default_effort_and_unset_usd_per_mtok(tmp_path):
    def mut(d):
        d["executor"] = {"model": "gpt-5.5", "tier": "weak", "provider": "codex"}
        d["allow_same_family_judge"] = True
    cfg = config.load(_write(tmp_path, mut))
    out = gen_promptfoo(cfg, results_dir=tmp_path / "results")

    doc = yaml.safe_load(out["baseline"]["yaml"].read_text())
    prov_config = doc["providers"][0]["config"]
    assert prov_config["effort"] == "medium"
    assert prov_config["usd_per_mtok"] is None


# --------------------------------------------------------------------------- #
# gen_promptfoo.py: claude-provider regression (byte-identical claude path)
# --------------------------------------------------------------------------- #
# Golden fixtures captured from `gen_promptfoo(config.load("experiments/
# smoke.yaml"))` BEFORE this workstream touched gen_promptfoo.py, with the
# results_dir-derived absolute paths (results_dir itself, and the prompt
# file's path) normalized to the placeholder "<RDIR>" so the comparison is
# independent of pytest's per-run `tmp_path`. Every other field — including
# the provider shim's own absolute repo path, which does not depend on
# tmp_path — is compared verbatim.
_GOLDEN_BASELINE = json.loads(r'{"description":"smoke baseline (weak)","prompts":[{"id":"file://<RDIR>/prompts/baseline.txt","label":"baseline"}],"providers":[{"id":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/providers/promptfoo_claude.py","config":{"model":"claude-haiku-4-5-20251001","tier":"weak","arm":"baseline","exp_id":"smoke","results_dir":"<RDIR>"}}],"tests":[{"vars":{"task_id":"sm-01","seeded":true,"arm":"baseline","task_input":"# recent.last_n\n\n`last_n(items, n)` returns the last `n` items of a list, in order.\n\nContract:\n- Return the final `n` elements of `items` (or all of them if `items` has\n  fewer than `n`).\n- `n >= 0`.\n\n\n--- a/recent.py\n+++ b/recent.py\n@@ -1,5 +1,9 @@\n+def last_n(items, n):\n+    return items[-n - 1:]\n+\n+\n def first_n(items, n):\n     return items[:n]\n \n \n def middle(items):\n     return items[len(items) // 2]\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-01/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-02","seeded":true,"arm":"baseline","task_input":"# cart.add_item\n\n`add_item(item, basket)` appends `item` to a shopping basket and returns it.\n\nContract:\n- Append `item` to `basket` and return the basket.\n- If the caller omits `basket`, the function starts a NEW empty basket for\n  that call; two separate calls that both omit `basket` must not share items.\n\n\n--- a/cart.py\n+++ b/cart.py\n@@ -1,5 +1,9 @@\n+def add_item(item, basket=[]):\n+    basket.append(item)\n+    return basket\n+\n+\n def total(basket):\n     return sum(i.price for i in basket)\n \n \n def is_empty(basket):\n     return not basket\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-02/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-03","seeded":true,"arm":"baseline","task_input":"# eligibility.is_eligible\n\n`is_eligible(age, has_consent)` gates access to a feature.\n\nContract:\n- A user is eligible if they are an adult (`age >= 18`) OR a guardian has\n  provided consent (`has_consent` is True).\n- Otherwise they are not eligible.\n\n\n--- a/eligibility.py\n+++ b/eligibility.py\n@@ -1,4 +1,8 @@\n+def is_eligible(age, has_consent):\n+    # Adults, or minors with guardian consent.\n+    return age >= 18 and has_consent\n+\n+\n MIN_AGE = 18\n MAX_AGE = 120\n \n \n def clamp_age(a):\n     return max(MIN_AGE, min(a, MAX_AGE))\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-03/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-04","seeded":false,"arm":"baseline","task_input":"# merge.merge\n\n`merge(base, extra=None)` returns a new dict combining `base` and `extra`.\n\nContract:\n- Return a NEW dict; never mutate `base` or `extra`.\n- `extra` overrides keys in `base`.\n- If `extra` is omitted, return a copy of `base`.\n\n\n--- a/merge.py\n+++ b/merge.py\n@@ -1,4 +1,11 @@\n+def merge(base, extra=None):\n+    if extra is None:\n+        extra = {}\n+    result = dict(base)\n+    result.update(extra)\n+    return result\n+\n+\n DEFAULTS = {\"timeout\": 30}\n \n \n def with_defaults(cfg):\n     return merge(DEFAULTS, cfg)\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-04/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-05","seeded":false,"arm":"baseline","task_input":"# batching_ok.batches\n\n`batches(items, size)` splits `items` into consecutive non-overlapping lists\nof length `size` (last may be shorter), covering each element once.\n\nContract:\n- batches([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]].\n- Every element appears exactly once, in order. `size >= 1`.\n\n\n--- a/batching_ok.py\n+++ b/batching_ok.py\n@@ -1,4 +1,9 @@\n+def batches(items, size):\n+    out = []\n+    for i in range(0, len(items), size):\n+        out.append(items[i:i + size])\n+    return out\n+\n \n def flatten(chunks):\n     return [x for c in chunks for x in c]\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-05/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]}]}')

_GOLDEN_TREATMENT = json.loads(r'{"description":"smoke treatment (weak)","prompts":[{"id":"file://<RDIR>/prompts/treatment.txt","label":"treatment"}],"providers":[{"id":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/providers/promptfoo_claude.py","config":{"model":"claude-haiku-4-5-20251001","tier":"weak","arm":"treatment","exp_id":"smoke","results_dir":"<RDIR>"}}],"tests":[{"vars":{"task_id":"sm-01","seeded":true,"arm":"treatment","task_input":"# recent.last_n\n\n`last_n(items, n)` returns the last `n` items of a list, in order.\n\nContract:\n- Return the final `n` elements of `items` (or all of them if `items` has\n  fewer than `n`).\n- `n >= 0`.\n\n\n--- a/recent.py\n+++ b/recent.py\n@@ -1,5 +1,9 @@\n+def last_n(items, n):\n+    return items[-n - 1:]\n+\n+\n def first_n(items, n):\n     return items[:n]\n \n \n def middle(items):\n     return items[len(items) // 2]\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-01/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-02","seeded":true,"arm":"treatment","task_input":"# cart.add_item\n\n`add_item(item, basket)` appends `item` to a shopping basket and returns it.\n\nContract:\n- Append `item` to `basket` and return the basket.\n- If the caller omits `basket`, the function starts a NEW empty basket for\n  that call; two separate calls that both omit `basket` must not share items.\n\n\n--- a/cart.py\n+++ b/cart.py\n@@ -1,5 +1,9 @@\n+def add_item(item, basket=[]):\n+    basket.append(item)\n+    return basket\n+\n+\n def total(basket):\n     return sum(i.price for i in basket)\n \n \n def is_empty(basket):\n     return not basket\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-02/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-03","seeded":true,"arm":"treatment","task_input":"# eligibility.is_eligible\n\n`is_eligible(age, has_consent)` gates access to a feature.\n\nContract:\n- A user is eligible if they are an adult (`age >= 18`) OR a guardian has\n  provided consent (`has_consent` is True).\n- Otherwise they are not eligible.\n\n\n--- a/eligibility.py\n+++ b/eligibility.py\n@@ -1,4 +1,8 @@\n+def is_eligible(age, has_consent):\n+    # Adults, or minors with guardian consent.\n+    return age >= 18 and has_consent\n+\n+\n MIN_AGE = 18\n MAX_AGE = 120\n \n \n def clamp_age(a):\n     return max(MIN_AGE, min(a, MAX_AGE))\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-03/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-04","seeded":false,"arm":"treatment","task_input":"# merge.merge\n\n`merge(base, extra=None)` returns a new dict combining `base` and `extra`.\n\nContract:\n- Return a NEW dict; never mutate `base` or `extra`.\n- `extra` overrides keys in `base`.\n- If `extra` is omitted, return a copy of `base`.\n\n\n--- a/merge.py\n+++ b/merge.py\n@@ -1,4 +1,11 @@\n+def merge(base, extra=None):\n+    if extra is None:\n+        extra = {}\n+    result = dict(base)\n+    result.update(extra)\n+    return result\n+\n+\n DEFAULTS = {\"timeout\": 30}\n \n \n def with_defaults(cfg):\n     return merge(DEFAULTS, cfg)\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-04/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]},{"vars":{"task_id":"sm-05","seeded":false,"arm":"treatment","task_input":"# batching_ok.batches\n\n`batches(items, size)` splits `items` into consecutive non-overlapping lists\nof length `size` (last may be shorter), covering each element once.\n\nContract:\n- batches([1,2,3,4,5], 2) -> [[1,2],[3,4],[5]].\n- Every element appears exactly once, in order. `size >= 1`.\n\n\n--- a/batching_ok.py\n+++ b/batching_ok.py\n@@ -1,4 +1,9 @@\n+def batches(items, size):\n+    out = []\n+    for i in range(0, len(items), size):\n+        out.append(items[i:i + size])\n+    return out\n+\n \n def flatten(chunks):\n     return [x for c in chunks for x in c]\n","truth_path":"/Users/wesleyjinks/code/prompts-skills-steering/tasksets/smoke/items/sm-05/truth.yaml","results_dir":"<RDIR>","exp_id":"smoke","tier":"weak","judge_json":"{\"provider\": \"codex\", \"model\": \"gpt-5.5\", \"effort\": \"medium\", \"rubric\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.md\", \"schema\": \"/Users/wesleyjinks/code/prompts-skills-steering/harness/rubrics/review_judge.schema.json\"}"},"assert":[{"type":"python","value":"file:///Users/wesleyjinks/code/prompts-skills-steering/harness/asserts/judge_assert.py"}]}]}')


def _normalize(doc, rdir):
    """Replace the tmp_path-derived results_dir/prompt-path substrings with a
    stable placeholder so the comparison doesn't depend on pytest's per-run
    tmp_path. Round-trips through JSON text so the replacement reaches every
    nested string, not just the top-level results_dir field."""
    text = json.dumps(doc)
    text = text.replace(str(rdir), "<RDIR>")
    return json.loads(text)


def test_claude_provider_yaml_unchanged_regression(tmp_path):
    cfg = config.load("experiments/smoke.yaml")
    rdir = tmp_path / "results"
    out = gen_promptfoo(cfg, results_dir=rdir)

    for arm, golden in (("baseline", _GOLDEN_BASELINE), ("treatment", _GOLDEN_TREATMENT)):
        doc = yaml.safe_load(out[arm]["yaml"].read_text())
        got = _normalize(doc, rdir)
        assert got == golden, f"{arm} arm's generated YAML changed for a claude-provider config"
