"""Experiment config: dataclass, loader, validation, and taskset loading.

An experiment config declares a single ablation: one baseline prompt (a list of
artifact files concatenated in order) and exactly ONE varied element that is
composed into the treatment arm. The loader validates every referenced path
against the real files on disk so a misconfigured experiment fails fast, before
any model call is spent.

Path resolution is anchored at the repo root (the parent of the `harness`
package) so configs can use repo-relative paths regardless of the working
directory the harness is invoked from.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

_EVAL_SHAPES = {"ablation", "adherence", "triggering"}
_FORMS = {"prompt", "skill", "steering", "agent"}
_EXECUTOR_PROVIDERS = {"claude", "codex"}


class ConfigError(Exception):
    """Raised when an experiment config is malformed or references missing files."""


@dataclass
class ExecutorCfg:
    model: str
    tier: str
    # Multi-family executor tiers (workstream D): which CLI wrapper/provider
    # shim drives this executor. Defaults to "claude" so every config written
    # before this field existed loads with identical behavior.
    provider: str = "claude"
    # Reasoning effort passed straight through to `run_codex` for a codex-family
    # executor. Unused (but harmless) when provider == "claude".
    effort: str = "medium"
    # Optional USD-per-million-tokens rate used to derive cost_usd for a
    # codex-family executor, which only reports a single tokens_used count (no
    # separate input/output breakdown, hence no per-field pricing). None means
    # "unpriced" — cost_usd stays null rather than silently reporting 0.0.
    usd_per_mtok: float | None = None


@dataclass
class JudgeCfg:
    provider: str
    model: str
    effort: str
    rubric: str
    schema: str


@dataclass
class TokenBudget:
    max_cost_usd: float
    max_items: int


@dataclass
class ExperimentConfig:
    id: str
    task_family: str
    eval_shape: str
    baseline_prompt: list[str]
    varied_element: str
    varied_element_form: str
    taskset: str
    executor: ExecutorCfg
    judge: JudgeCfg
    token_budget: TokenBudget
    negative_control: bool = False
    # Self-preference guard override (see _validate_same_family_judge below).
    # Only meaningful when executor.provider == judge.provider == "codex".
    allow_same_family_judge: bool = False
    root: Path = field(default=REPO_ROOT)

    # ---- resolved paths (all absolute) --------------------------------------
    def baseline_paths(self) -> list[Path]:
        return [self.root / p for p in self.baseline_prompt]

    def varied_element_path(self) -> Path:
        return (
            self.root
            / "artifacts"
            / self.varied_element
            / f"{self.varied_element_form}.md"
        )

    def taskset_path(self) -> Path:
        return self.root / self.taskset

    def rubric_path(self) -> Path:
        return self.root / self.judge.rubric

    def schema_path(self) -> Path:
        return self.root / self.judge.schema

    def results_dir(self) -> Path:
        return self.root / "results" / self.id / self.executor.tier

    def judge_json(self) -> str:
        """JSON blob handed to the judge assert via a promptfoo test var."""
        return json.dumps(
            {
                "provider": self.judge.provider,
                "model": self.judge.model,
                "effort": self.judge.effort,
                "rubric": str(self.rubric_path()),
                "schema": str(self.schema_path()),
            }
        )


def _require(d: dict, key: str, where: str):
    if key not in d:
        raise ConfigError(f"missing required key '{key}' in {where}")
    return d[key]


def load(path, root: Path | None = None) -> ExperimentConfig:
    """Load and validate an experiment config YAML file."""
    root = Path(root) if root is not None else REPO_ROOT
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ConfigError(f"config must be a mapping, got {type(raw).__name__}")

    where = str(path)

    exp_id = _require(raw, "id", where)
    task_family = _require(raw, "task_family", where)
    eval_shape = _require(raw, "eval_shape", where)
    if eval_shape not in _EVAL_SHAPES:
        raise ConfigError(
            f"eval_shape must be one of {sorted(_EVAL_SHAPES)}, got {eval_shape!r}"
        )

    baseline_prompt = _require(raw, "baseline_prompt", where)
    if not isinstance(baseline_prompt, list) or not baseline_prompt:
        raise ConfigError("baseline_prompt must be a non-empty list of artifact paths")

    varied_element = _require(raw, "varied_element", where)
    if isinstance(varied_element, list):
        raise ConfigError("one element per experiment")
    if not isinstance(varied_element, str):
        raise ConfigError("varied_element must be a single string")

    varied_element_form = _require(raw, "varied_element_form", where)
    if varied_element_form not in _FORMS:
        raise ConfigError(
            f"varied_element_form must be one of {sorted(_FORMS)}, got {varied_element_form!r}"
        )

    taskset = _require(raw, "taskset", where)

    executor_raw = _require(raw, "executor", where)
    if not isinstance(executor_raw, dict):
        raise ConfigError("executor must be a mapping")
    executor_provider = executor_raw.get("provider", "claude")
    if executor_provider not in _EXECUTOR_PROVIDERS:
        raise ConfigError(
            f"executor.provider must be one of {sorted(_EXECUTOR_PROVIDERS)}, "
            f"got {executor_provider!r}"
        )
    usd_per_mtok_raw = executor_raw.get("usd_per_mtok")
    usd_per_mtok = float(usd_per_mtok_raw) if usd_per_mtok_raw is not None else None
    executor = ExecutorCfg(
        model=_require(executor_raw, "model", "executor"),
        tier=_require(executor_raw, "tier", "executor"),
        provider=executor_provider,
        effort=str(executor_raw.get("effort", "medium")),
        usd_per_mtok=usd_per_mtok,
    )

    judge_raw = _require(raw, "judge", where)
    if not isinstance(judge_raw, dict):
        raise ConfigError("judge must be a mapping")
    judge = JudgeCfg(
        provider=_require(judge_raw, "provider", "judge"),
        model=_require(judge_raw, "model", "judge"),
        effort=_require(judge_raw, "effort", "judge"),
        rubric=_require(judge_raw, "rubric", "judge"),
        schema=_require(judge_raw, "schema", "judge"),
    )

    budget_raw = _require(raw, "token_budget", where)
    if not isinstance(budget_raw, dict):
        raise ConfigError("token_budget must be a mapping")
    token_budget = TokenBudget(
        max_cost_usd=float(_require(budget_raw, "max_cost_usd", "token_budget")),
        max_items=int(_require(budget_raw, "max_items", "token_budget")),
    )

    negative_control = bool(raw.get("negative_control", False))
    allow_same_family_judge = bool(raw.get("allow_same_family_judge", False))

    _validate_same_family_judge(executor, judge, allow_same_family_judge)

    cfg = ExperimentConfig(
        id=exp_id,
        task_family=task_family,
        eval_shape=eval_shape,
        baseline_prompt=list(baseline_prompt),
        varied_element=varied_element,
        varied_element_form=varied_element_form,
        taskset=taskset,
        executor=executor,
        judge=judge,
        token_budget=token_budget,
        negative_control=negative_control,
        allow_same_family_judge=allow_same_family_judge,
        root=root,
    )

    _validate_paths(cfg)
    return cfg


def _validate_same_family_judge(executor: ExecutorCfg, judge: JudgeCfg, allow: bool):
    """Self-preference guard: a codex-family judge scoring a codex-family
    executor can systematically favor its own family's outputs, which would
    quietly bias exactly the cross-family comparisons multi-family tiers exist
    to make trustworthy. Refuse same-family (executor.provider == judge.provider
    == "codex") unless the config explicitly opts in via
    `allow_same_family_judge: true`."""
    if executor.provider == "codex" and judge.provider == "codex" and not allow:
        raise ConfigError(
            "executor.provider and judge.provider are both 'codex' — a "
            "same-family judge risks self-preference bias (the judge favoring "
            "outputs from its own model family), undermining the point of a "
            "cross-family comparison. Set allow_same_family_judge: true in the "
            "config to override if this is intentional."
        )


def _validate_paths(cfg: ExperimentConfig):
    for p in cfg.baseline_paths():
        if not p.is_file():
            raise ConfigError(f"baseline_prompt artifact not found: {p}")

    vp = cfg.varied_element_path()
    if not vp.is_file():
        raise ConfigError(
            f"varied_element must resolve to exactly one existing artifact file; "
            f"not found: {vp}"
        )

    if not cfg.taskset_path().is_dir():
        raise ConfigError(f"taskset directory not found: {cfg.taskset_path()}")
    if not (cfg.taskset_path() / "manifest.yaml").is_file():
        raise ConfigError(f"taskset manifest not found: {cfg.taskset_path()/'manifest.yaml'}")

    if not cfg.rubric_path().is_file():
        raise ConfigError(f"judge rubric not found: {cfg.rubric_path()}")
    if not cfg.schema_path().is_file():
        raise ConfigError(f"judge schema not found: {cfg.schema_path()}")


def load_taskset(cfg: ExperimentConfig) -> list[dict]:
    """Load up to `token_budget.max_items` items for this experiment's taskset.

    Each returned dict has: id, seeded, task_input (context.md + "\\n\\n" +
    diff.patch), truth_path (absolute). Ordered by the manifest.
    """
    manifest_path = cfg.taskset_path() / "manifest.yaml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    items = manifest.get("items", []) or []
    max_items = cfg.token_budget.max_items
    out = []
    for entry in items[:max_items]:
        item_id = entry["id"]
        seeded = bool(entry.get("seeded", False))
        item_dir = cfg.taskset_path() / "items" / item_id
        context = (item_dir / "context.md").read_text()
        diff = (item_dir / "diff.patch").read_text()
        task_input = context + "\n\n" + diff
        out.append(
            {
                "id": item_id,
                "seeded": seeded,
                "task_input": task_input,
                "truth_path": str(item_dir / "truth.yaml"),
            }
        )
    return out
