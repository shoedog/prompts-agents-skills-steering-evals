from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from harness.structured.config import load_config
from harness.structured.executors import ExecutionResult, ExecutorError
from harness.structured.replay import LoadedRun
from harness.structured.report import summarize
from harness.structured.results import canonical_json
from harness.structured.runner import RunResult, run_structured
from harness.structured.taskset import sha256_file
from harness.tests.structured_support import build_v2_taskset


@dataclass
class FixedClock:
    timestamp: str

    def now(self) -> str:
        return self.timestamp

    def monotonic(self) -> float:
        return 0.0


class FixtureExecutor:
    def __init__(
        self,
        version: dict,
        *,
        promotable: bool = True,
        child_exit: int | None = None,
        child_exit_sample: int | None = None,
        prompt_token: str = "",
    ) -> None:
        self.version = version
        self.promotable = promotable
        self.child_exit = child_exit
        self.child_exit_sample = child_exit_sample
        self.prompt_token = prompt_token
        self.calls = 0

    def cache_identity(self, request) -> tuple[str, str]:
        body = json.loads(request.request_file.read_text())
        prompt = hashlib.sha256(canonical_json(body) + self.prompt_token.encode()).hexdigest()
        return "fake-provider 1.0", prompt

    def run(self, request):
        self.calls += 1
        assert request.scratch_dir.is_dir()
        if self.child_exit is not None and (
            self.child_exit_sample is None or request.sample == self.child_exit_sample
        ):
            raise ExecutorError(self.child_exit, stderr_tail="fixture child failure")
        body = json.loads(request.request_file.read_text())
        label = "correct"
        if not self.promotable and self.version["name"] != "baseline":
            label = "unclear"
        response = {
            "class": label,
            "confidence": 0.8,
            "rationale": "fixture TimeoutError propagated",
            "evidence_lines": [11],
        }
        request_hash = hashlib.sha256(canonical_json(body) + self.prompt_token.encode()).hexdigest()
        identity = canonical_json(
            {
                "version": self.version["name"],
                "item": body["target"]["id"],
                "sample": request.sample,
                "seed": request.seed,
            }
        )
        invocation = hashlib.md5(identity, usedforsecurity=False).hexdigest()
        envelope = {
            "schema_version": "1",
            "invocation_id": (
                f"{invocation[:8]}-{invocation[8:12]}-{invocation[12:16]}-"
                f"{invocation[16:20]}-{invocation[20:]}"
            ),
            "task": request.task,
            "task_version": request.task_version,
            "provider": "fake",
            "model": request.model,
            "provider_version": "fake-provider 1.0",
            "prompt_sha256": request_hash,
            "escalation_state": "first_valid",
            "first_tier_valid": True,
            "first_tier_sentinel": False,
            "final_sentinel": False,
            "cache_hit": False,
            "usage": {
                "input_tokens": 12,
                "output_tokens": 7,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "cost_usd": 0.001,
            "response": response,
            "log_path": "logs/fake.jsonl",
        }
        return ExecutionResult(
            envelope=envelope,
            raw_stdout=json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
            returncode=0,
        )


def _write_config(
    root: Path,
    *,
    experiment_id: str = "st-fixture",
    split: str = "dev",
    samples: int = 1,
    candidates: int = 0,
) -> Path:
    versions = [
        {
            "name": "v1" if candidates == 0 else "baseline",
            "task_version": "2026-09-04.1",
            "provider": {"kind": "stub", "model": "fake-model"},
        }
    ]
    versions.extend(
        {
            "name": f"candidate-{number}",
            "task_version": f"2026-09-04.{number + 1}",
            "provider": {"kind": "stub", "model": "fake-model"},
        }
        for number in range(1, candidates + 1)
    )
    raw = {
        "kind": "structured_task",
        "id": experiment_id,
        "task": "classify_error_handling",
        "request_schema": "contracts/classify_error_handling.schema.json#/$defs/request",
        "response_schema": "contracts/classify_error_handling.schema.json#/$defs/response",
        "taskset": "tasksets/structured/classify_error_handling",
        "split": split,
        "versions": versions,
        "baseline_version": versions[0]["name"],
        "samples_per_item": samples,
        "seed": 20260904,
        "jobs": 3,
        "asserts": [
            {"type": "schema", "hard": True},
            {"type": "label", "mode": "exact", "field": "class"},
            {"type": "evidence"},
        ],
        "stats": {"bootstrap_resamples": 20, "seed": 20260904},
        "token_budget": {"max_cost_usd": 1.0, "max_items": 1},
    }
    path = root / "experiments/structured/fixture.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path


def relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def replay_cache_values(root: Path) -> list[str]:
    rows = [json.loads(line) for line in (root / "replay.jsonl").read_text().splitlines()]
    return [row["cache"] for row in rows if row["stage"] == "classify"]


def metrics_bytes(root: Path) -> bytes:
    return (root / "metrics.json").read_bytes()


@pytest.fixture
def run_smoke(tmp_path: Path, monkeypatch):
    build_v2_taskset(
        tmp_path,
        items=[{"id": "eh-py-0001", "label": "correct"}],
    )
    call_number = 0

    def run(
        *,
        samples=1,
        no_cache=False,
        shared_stage=None,
        child_exit=None,
        child_exit_sample=None,
        prompt_token="",
        cache_identity=True,
        execution_counts=None,
        return_result=False,
    ):
        nonlocal call_number
        config_path = _write_config(tmp_path, samples=samples)
        cfg = load_config(config_path, root=tmp_path)
        if shared_stage is not None:
            import harness.structured.runner as runner_module

            real_load = runner_module.load_taskset

            def load_with_shared(*args, **kwargs):
                loaded = real_load(*args, **kwargs)
                item = loaded.items[0]
                amended = replace(
                    item,
                    raw={
                        **item.raw,
                        "stages": {
                            shared_stage: {"pin": "from_item", "shared": True}
                        },
                    },
                    input_values={**item.input_values, shared_stage: item.input_values["target"]},
                )
                return replace(loaded, items=(amended,))

            monkeypatch.setattr(runner_module, "load_taskset", load_with_shared)
        executors = []

        def factory(version):
            executor = FixtureExecutor(
                version,
                child_exit=child_exit,
                child_exit_sample=child_exit_sample,
                prompt_token=prompt_token,
            )
            executors.append(executor)
            if cache_identity:
                return executor

            class ExecutorWithoutCacheIdentity:
                def run(self, request):
                    return executor.run(request)

            return ExecutorWithoutCacheIdentity()

        clock = FixedClock("2026-09-04T18:40:11Z")
        call_number += 1
        result = run_structured(
            cfg,
            executor_factory=factory,
            clock=clock,
            force=call_number > 1,
            no_cache=no_cache,
            only=frozenset(),
        )
        if execution_counts is not None:
            execution_counts.extend(executor.calls for executor in executors)
        assert isinstance(result, RunResult)
        captured = tmp_path / "captures" / str(call_number)
        shutil.copytree(result.run_dir, captured)
        return result if return_result else captured

    return run


def test_structured_smoke_writes_exact_tree(run_smoke):
    run_dir = run_smoke(samples=1)
    assert relative_files(run_dir) == {
        "calls/v1-eh-py-0001-0.json",
        "stages/v1-eh-py-0001-s0-classify.json",
        "asserts/v1-eh-py-0001-0.json",
        "inputs/config.json",
        "inputs/manifest.json",
        "inputs/items/eh-py-0001.json",
        "inputs/requests/eh-py-0001-s0.json",
        "inputs/index.json",
        "run.json",
        "replay.jsonl",
        "trace.jsonl",
        "metrics.json",
        "report.md",
    }


def test_second_run_hits_cache_and_no_cache_bypasses_reads(run_smoke):
    first = run_smoke(samples=1)
    second = run_smoke(samples=1)
    third = run_smoke(samples=1, no_cache=True)
    assert replay_cache_values(first) == ["miss"]
    assert replay_cache_values(second) == ["hit"]
    assert replay_cache_values(third) == ["miss"]
    assert metrics_bytes(first) == metrics_bytes(second) == metrics_bytes(third)


def test_executor_without_cache_identity_always_executes_and_leaves_no_cache_record(
    run_smoke,
):
    execution_counts = []
    first = run_smoke(cache_identity=False, execution_counts=execution_counts)
    second = run_smoke(cache_identity=False, execution_counts=execution_counts)

    assert execution_counts == [1, 1]
    assert replay_cache_values(first) == ["miss"]
    assert replay_cache_values(second) == ["miss"]
    assert not list((first.parents[1] / ".cache/structured").glob("*.json"))


def test_prompt_identity_change_cannot_reuse_a_stale_cache_entry(run_smoke):
    first = run_smoke(prompt_token="one")
    changed = run_smoke(prompt_token="two")
    restored = run_smoke(prompt_token="one")
    assert replay_cache_values(first) == ["miss"]
    assert replay_cache_values(changed) == ["miss"]
    assert replay_cache_values(restored) == ["hit"]


def test_three_samples_preserve_three_classify_stage_records(run_smoke):
    run_dir = run_smoke(samples=3)
    paths = sorted((run_dir / "stages").glob("*.json"))
    assert [path.name for path in paths] == [
        "v1-eh-py-0001-s0-classify.json",
        "v1-eh-py-0001-s1-classify.json",
        "v1-eh-py-0001-s2-classify.json",
    ]
    rows = [json.loads(path.read_text()) for path in paths]
    assert [(row["item_id"], row["sample"], row["stage"]) for row in rows] == [
        ("eh-py-0001", 0, "classify"),
        ("eh-py-0001", 1, "classify"),
        ("eh-py-0001", 2, "classify"),
    ]
    replay = [json.loads(line) for line in (run_dir / "replay.jsonl").read_text().splitlines()]
    assert [row["sample"] for row in replay] == [0, 1, 2]


def test_shared_stage_is_written_once_and_each_sample_carries_its_ref(run_smoke):
    run_dir = run_smoke(samples=3, shared_stage="targets")
    shared = run_dir / "stages/v1-eh-py-0001-targets.json"
    assert shared.is_file()
    rows = [json.loads(line) for line in (run_dir / "replay.jsonl").read_text().splitlines()]
    refs = [row["stage_ref"] for row in rows if row["stage"] == "classify"]
    assert refs == [
        {"path": "stages/v1-eh-py-0001-targets.json", "sha256": sha256_file(shared)}
    ] * 3


def test_stage_error_is_recorded_and_excluded_from_scoring(run_smoke):
    result = run_smoke(child_exit=3, return_result=True)
    run_dir = result.run_dir
    call = json.loads((run_dir / "calls/v1-eh-py-0001-0.json").read_text())
    stage = json.loads((run_dir / "stages/v1-eh-py-0001-s0-classify.json").read_text())
    assert call["stage_error"] == "classify"
    assert stage["status"] == "error"
    assert result.stage_errors == 1
    assert result.metrics["versions"]["v1"]["classification"]["n"] == 0
    assert result.promotion is None
    with pytest.raises(FrozenInstanceError):
        result.stage_errors = 0


def test_one_failed_sample_excludes_the_whole_item_from_version_reductions(run_smoke):
    result = run_smoke(
        samples=2,
        child_exit=3,
        child_exit_sample=0,
        return_result=True,
    )
    version = result.metrics["versions"]["v1"]
    full_summary = summarize(LoadedRun.load(result.run_dir))

    assert result.stage_errors == 1
    assert version["stage_errors"]["item_ids"] == ["eh-py-0001"]
    assert version["classification"]["n"] == 0
    assert version["calibration"]["n"] == 0
    assert version["kappa_vs_human"] == 0.0
    assert full_summary["scored_rows"]["v1"] == []
    assert result.metrics["recomputed_assert_records"] == 0
    assert full_summary["worst_rows"] == []


@pytest.fixture
def config_factory(tmp_path: Path):
    def build(*, split="dev", candidates=0, experiment_id="st-cli"):
        build_v2_taskset(
            tmp_path,
            items=[{"id": "eh-py-0001", "split": split, "label": "correct"}],
        )
        path = _write_config(
            tmp_path,
            experiment_id=experiment_id,
            split=split,
            candidates=candidates,
        )
        return SimpleNamespace(
            path=path,
            root=tmp_path,
            results_parent=tmp_path / "results",
        )

    return build


@pytest.fixture
def test_config(config_factory):
    return config_factory(split="test", experiment_id="st-test")


@pytest.fixture
def dev_config(config_factory):
    return config_factory(candidates=1, experiment_id="st-dev")


@pytest.fixture
def plain_config(config_factory):
    return config_factory(experiment_id="st-child")


@pytest.fixture
def structured_cli(monkeypatch):
    import harness.structured.run as run_module

    def invoke(config, *, promotable=True, child_exit=None, extra=()):
        monkeypatch.setattr(run_module, "_CLOCK", FixedClock("2026-09-04T18:40:11Z"))
        monkeypatch.setattr(
            run_module,
            "_EXECUTOR_FACTORY",
            lambda version: FixtureExecutor(
                version, promotable=promotable, child_exit=child_exit
            ),
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            returncode = run_module.main([str(config.path), *extra])
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    return invoke


def test_test_split_without_allow_test_exits_five_before_writes(structured_cli, test_config):
    proc = structured_cli(test_config)
    assert proc.returncode == 5
    assert not test_config.results_parent.exists()


@pytest.fixture
def seed_stale_run(monkeypatch):
    def seed(tmp_path):
        build_v2_taskset(tmp_path, items=[{"id": "eh-py-0001", "label": "correct"}])
        config = SimpleNamespace(
            path=_write_config(tmp_path, experiment_id="st-stale"),
            root=tmp_path,
            results_parent=tmp_path / "results",
        )
        cfg = replace(load_config(config.path, root=tmp_path), jobs=4)
        result = run_structured(
            cfg,
            executor_factory=lambda version: FixtureExecutor(version),
            clock=FixedClock("2026-09-04T18:40:11Z"),
            force=False,
            no_cache=False,
            only=frozenset(),
        )
        call = next((result.run_dir / "calls").glob("*.json"))
        return SimpleNamespace(config=config, call=call, original_bytes=call.read_bytes())

    return seed


def test_stale_refusal_returns_four_without_deleting(structured_cli, seed_stale_run, tmp_path):
    stale = seed_stale_run(tmp_path)
    proc = structured_cli(stale.config)
    assert proc.returncode == 4
    assert stale.call.read_bytes() == stale.original_bytes


@pytest.mark.parametrize("promotable", [True, False])
def test_promotion_verdict_prints_and_exits_zero(structured_cli, dev_config, promotable):
    proc = structured_cli(dev_config, promotable=promotable)
    expected = "PROMOTABLE" if promotable else "NOT PROMOTABLE"
    assert proc.returncode == 0
    assert expected in proc.stdout


@pytest.mark.parametrize("child_exit", range(1, 7))
def test_child_exit_one_through_six_records_stage_error_and_cli_exits_zero(
    structured_cli, plain_config, child_exit
):
    proc = structured_cli(plain_config, child_exit=child_exit)
    assert proc.returncode == 0
    call = next((plain_config.results_parent / "st-child").glob("*/calls/*.json"))
    assert json.loads(call.read_text())["stage_error_detail"]["child_returncode"] == child_exit


def test_parser_has_exact_defaults_repeatable_only_and_argparse_exit_two():
    from harness.structured.run import build_parser

    parser = build_parser()
    args = parser.parse_args(["experiment.yaml", "--only", "one", "--only", "two"])
    assert (args.split, args.allow_test, args.jobs, args.force, args.no_cache) == (
        None,
        False,
        4,
        False,
        False,
    )
    assert args.only == ["one", "two"]
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["experiment.yaml", "--split", "holdout"])
    assert caught.value.code == 2


def test_only_rejects_unknown_item_before_executor_creation(tmp_path):
    build_v2_taskset(tmp_path, items=[{"id": "eh-py-0001", "label": "correct"}])
    cfg = load_config(_write_config(tmp_path), root=tmp_path)
    created = False

    def factory(_version):
        nonlocal created
        created = True
        return FixtureExecutor(_version)

    with pytest.raises(ValueError, match="unknown --only item"):
        run_structured(
            cfg,
            executor_factory=factory,
            clock=FixedClock("2026-09-04T18:40:11Z"),
            force=False,
            no_cache=False,
            only=frozenset({"absent"}),
        )
    assert created is False
    assert not (tmp_path / "results").exists()
