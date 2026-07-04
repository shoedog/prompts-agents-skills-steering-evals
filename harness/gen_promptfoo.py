"""Generate the two one-arm promptfoo configs (baseline + treatment).

Each experiment produces TWO separate promptfoo eval configs, one per arm, with
the arm label hard-coded into the prompt file, the provider config, and every
test's vars. This keeps the arms fully isolated: promptfoo never sees both
prompts in one eval, so there is no chance of cache-warming or ordering leakage
between arms within a single promptfoo run.

Prompt composition:
  baseline  = <baseline artifacts joined by \\n\\n> + "\\n\\n{{task_input}}"
  treatment = <baseline artifacts> + "\\n\\n" + <varied element artifact>
              + "\\n\\n{{task_input}}"

`{{task_input}}` is a nunjucks placeholder promptfoo fills per test from the
item's vars.

Unfilled-slot guard: some element artifacts are deliberately templated (they
carry `<...>` slots that require per-task instantiation and must never reach an
executor raw). We check the VARIED-ELEMENT artifact text for such slots and
refuse to build the treatment arm if any remain. The guard is scoped to the
element text specifically — the baseline output-format artifact legitimately
contains `<file>`/`<line>` placeholders that describe the required output shape,
and those must not trip the guard.

Comment stripping: artifact source files may carry HTML comments as authoring
metadata (e.g. the negative-control artifact's quarantine warning header,
`<!-- NEGATIVE CONTROL ... -->`). Comments are for humans editing the artifact
tree, never for the executor — they are stripped from every composed part
(baseline AND element) before the prompt is assembled, so an executor can never
see them, let alone infer which arm/experiment it is in from their contents.
This is a no-op for every artifact that doesn't use HTML comments (currently
everything except the negative control).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from harness.config import ConfigError, ExperimentConfig, load_taskset

ARMS = ("baseline", "treatment")

_PROVIDER_SHIM = Path(__file__).resolve().parent / "providers" / "promptfoo_claude.py"
_JUDGE_ASSERT = Path(__file__).resolve().parent / "asserts" / "judge_assert.py"

# A template slot: an angle-bracket placeholder holding lowercase prose / an
# ellipsis (e.g. `<approach 1>`, `<the decision>`, `<...>`). This deliberately
# does NOT match the baseline output-format placeholders like `<file>` /
# `<line>` — those are single lowercase words, but they live in the baseline
# artifact, not the varied element, and we only scan the varied element here.
_SLOT_RE = re.compile(r"<[^<>\n]*(?:\.\.\.|\s)[^<>\n]*>|<\.\.\.>")

# HTML comments (including multi-line). Stripped from every composed part —
# see module docstring.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# YAML frontmatter block at the very start of a file: `---\n ... \n---\n`. The
# `agent` deployment form carries a frontmatter header (`name:` / `description:`)
# that is delegation metadata for routing to the agent, NOT prompt content. When
# an agent-form element is composed into a treatment prompt, this header must be
# stripped so the executor sees only the body — the same substance the other
# three forms contribute. No other form has frontmatter, so this is a no-op there.
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _check_no_unfilled_slots(text: str, source: str):
    if _SLOT_RE.search(text):
        raise ConfigError(
            "task-specific element requires per-task instantiation — not supported yet"
            f" (unfilled template slot in {source})"
        )


def _strip_html_comments(text: str) -> str:
    """Remove HTML comments and any leading blank line(s) they leave behind."""
    return _HTML_COMMENT_RE.sub("", text).lstrip("\n")


def _strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block (`--- ... ---`) if present.

    Used for the `agent` deployment form, whose `name:`/`description:` header is
    routing metadata, not prompt content. A no-op on any text with no leading
    frontmatter block.
    """
    return _FRONTMATTER_RE.sub("", text, count=1).lstrip("\n")


def _compose_prompt(cfg: ExperimentConfig, arm: str) -> str:
    parts = [_strip_html_comments(p.read_text()).rstrip("\n") for p in cfg.baseline_paths()]
    if arm == "treatment":
        # Strip comments BEFORE the unfilled-slot scan: comment text is
        # authoring metadata (never reaches the executor either way), so an
        # angle-bracket-ish phrase inside a comment (e.g. prose punctuation in
        # a quarantine warning) must not false-positive the slot guard, which
        # is only meant to catch template slots in the actual prompt content.
        element = _strip_html_comments(cfg.varied_element_path().read_text())
        if cfg.varied_element_form == "agent":
            # The agent form's frontmatter (name/description) is delegation
            # metadata, not prompt content — strip it before the slot scan and
            # composition so the executor sees only the body.
            element = _strip_frontmatter(element)
        _check_no_unfilled_slots(element, str(cfg.varied_element_path()))
        parts.append(element.rstrip("\n"))
    body = "\n\n".join(parts)
    return body + "\n\n{{task_input}}\n"


def _yaml_for_arm(cfg: ExperimentConfig, arm: str, results_dir: Path,
                  prompt_path: Path, items: list[dict]) -> dict:
    provider_config = {
        "model": cfg.executor.model,
        "tier": cfg.executor.tier,
        "arm": arm,
        "exp_id": cfg.id,
        "results_dir": str(results_dir),
    }
    tests = []
    for item in items:
        tests.append(
            {
                "vars": {
                    "task_id": item["id"],
                    "seeded": item["seeded"],
                    "arm": arm,
                    "task_input": item["task_input"],
                    "truth_path": item["truth_path"],
                    "results_dir": str(results_dir),
                    "exp_id": cfg.id,
                    "tier": cfg.executor.tier,
                    "judge_json": cfg.judge_json(),
                },
                "assert": [
                    {"type": "python", "value": f"file://{_JUDGE_ASSERT}"}
                ],
            }
        )
    return {
        "description": f"{cfg.id} {arm} ({cfg.executor.tier})",
        "prompts": [{"id": f"file://{prompt_path}", "label": arm}],
        "providers": [
            {
                "id": f"file://{_PROVIDER_SHIM}",
                "config": provider_config,
            }
        ],
        "tests": tests,
    }


def gen_promptfoo(cfg: ExperimentConfig, results_dir: Path | None = None) -> dict:
    """Compose prompt files and emit both arms' promptfoo YAML configs.

    Returns {arm: {"yaml": <path>, "prompt": <path>}} for each arm.
    Raises ConfigError if the treatment element has an unfilled template slot.
    """
    results_dir = Path(results_dir) if results_dir is not None else cfg.results_dir()
    prompts_dir = results_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "calls").mkdir(parents=True, exist_ok=True)
    (results_dir / "judge").mkdir(parents=True, exist_ok=True)

    items = load_taskset(cfg)

    out = {}
    for arm in ARMS:
        prompt_text = _compose_prompt(cfg, arm)
        prompt_path = prompts_dir / f"{arm}.txt"
        prompt_path.write_text(prompt_text)

        doc = _yaml_for_arm(cfg, arm, results_dir, prompt_path, items)
        yaml_path = results_dir / f"promptfoo-{arm}.yaml"
        with open(yaml_path, "w") as f:
            yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=4096)

        out[arm] = {"yaml": yaml_path, "prompt": prompt_path}
    return out
