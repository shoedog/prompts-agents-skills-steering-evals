from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from harness.structured.config import load_config
from harness.structured.executors import FakeExecutor
from harness.structured.runner import run_structured
from harness.tests.test_structured_runner import FixedClock, relative_files


FIXTURE = Path(__file__).parent / "fixtures/conformance/structured-smoke-001"
CONTRACTS = (
    "classify_error_handling.schema.json",
    "llm_run_envelope.schema.json",
    "observations.schema.json",
    "targets.schema.json",
    "taskset_v2.schema.json",
)


def _run_fixture(destination: Path) -> Path:
    request = FIXTURE / "request"
    shutil.copytree(request / "taskset", destination / "taskset")
    (destination / "experiments").mkdir(parents=True)
    shutil.copy2(request / "config.yaml", destination / "experiments/config.yaml")
    (destination / "contracts").mkdir()
    repo_contracts = Path(__file__).resolve().parents[2] / "contracts"
    for name in CONTRACTS:
        shutil.copy2(repo_contracts / name, destination / "contracts" / name)
    cfg = load_config(destination / "experiments/config.yaml", root=destination)
    task_request = {
        "task": "classify_error_handling",
        "task_version": "2026-09-04.1",
        "target": json.loads((destination / "taskset/inputs/eh-py-0001/target.json").read_text()),
        "slice": json.loads((destination / "taskset/inputs/eh-py-0001/slice.json").read_text()),
        "fault": json.loads(
            (destination / "taskset/inputs/eh-py-0001/observation.json").read_text()
        )["fault"],
        "observation": {
            **json.loads(
                (destination / "taskset/inputs/eh-py-0001/observation.json").read_text()
            )["observed"],
            "log_excerpt": "TimeoutError propagated to the test boundary",
        },
        "dependency_semantics": {
            "source": "catalog",
            "text": "Timeouts are retryable, but propagation is valid when no retry policy is declared.",
        },
    }
    envelope = json.loads((request / "success.json").read_text())
    executor = FakeExecutor({canonical_request_sha256_value(task_request): envelope})
    result = run_structured(
        cfg,
        executor_factory=lambda _version: executor,
        clock=FixedClock("2026-09-04T18:40:11Z"),
        force=False,
        no_cache=False,
        only=frozenset(),
    )
    return result.run_dir


def canonical_request_sha256_value(value: dict) -> str:
    pathless = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(pathless).hexdigest()


def test_structured_request_to_tree_is_byte_pinned_and_repeatable(tmp_path):
    first = _run_fixture(tmp_path / "first")
    second = _run_fixture(tmp_path / "second")
    expected = FIXTURE / "expected"
    assert relative_files(first) == relative_files(second) == relative_files(expected)
    for relative in sorted(relative_files(expected)):
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
        assert (first / relative).read_bytes() == (expected / relative).read_bytes()


def test_conformance_run_header_authenticates_the_exact_input_index(tmp_path):
    run_dir = _run_fixture(tmp_path / "run")
    actual = hashlib.sha256((run_dir / "inputs/index.json").read_bytes()).hexdigest()
    recorded = json.loads((run_dir / "run.json").read_bytes())["inputs_index_sha256"]
    assert actual == recorded
