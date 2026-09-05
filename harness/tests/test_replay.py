from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from harness.structured.replay import LoadedRun, ReplayInputError, replay
from harness.structured.results import canonical_json, write_json_atomic
from harness.structured.taskset import sha256_file
from harness.tests.test_structured_report import make_frozen_structured_run


def artifact_hashes(root: Path, *, names: Sequence[str]) -> dict[str, str]:
    return {name: sha256_file(root / name) for name in names}


@pytest.fixture
def frozen_structured_run(tmp_path: Path) -> LoadedRun:
    run = make_frozen_structured_run(tmp_path)
    from harness.structured.report import render

    render(run)
    return run


def _rewrite_index(run: LoadedRun, index: dict) -> None:
    index_path = run.path / "inputs/index.json"
    index_path.write_bytes(canonical_json(index))
    header = json.loads((run.path / "run.json").read_bytes())
    header["inputs_index_sha256"] = sha256_file(index_path)
    write_json_atomic(run.path / "run.json", header)


def test_snapshot_index_has_exact_digest_pair_and_closed_versioned_requests(
    frozen_structured_run,
):
    index_path = frozen_structured_run.path / "inputs/index.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    header = json.loads((frozen_structured_run.path / "run.json").read_bytes())
    assert index_bytes == canonical_json(index)
    assert not index_bytes.endswith(b"\n")
    assert header == {
        "inputs_index_path": "inputs/index.json",
        "inputs_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
    }
    assert index["entries"] == sorted(index["entries"], key=lambda row: row["path"])
    assert "inputs/index.json" not in {row["path"] for row in index["entries"]}
    request = json.loads(
        (frozen_structured_run.path / "inputs/requests/eh-py-0001-s0.json").read_bytes()
    )
    assert set(request) == {"item_id", "sample", "versions"}
    assert list(request["versions"]) == ["baseline", "candidate", "candidate-alt"]


def test_replay_uses_no_executor_and_reproduces_reductions(frozen_structured_run):
    before = artifact_hashes(frozen_structured_run.path, names=("metrics.json", "report.md"))
    result = replay(frozen_structured_run.path)
    assert result.executor_calls == 0
    assert result.metrics == json.loads((frozen_structured_run.path / "metrics.json").read_bytes())
    assert artifact_hashes(
        frozen_structured_run.path, names=("metrics.json", "report.md")
    ) == before


def test_replay_refuses_a_mutated_snapshot_before_loading_results(
    frozen_structured_run, monkeypatch
):
    item = frozen_structured_run.path / "inputs/items/eh-py-0001.json"
    item.write_bytes(item.read_bytes() + b"\n")
    loaded_results = False

    def forbidden_results_load(*_args, **_kwargs):
        nonlocal loaded_results
        loaded_results = True
        raise AssertionError("results loaded before input hashes")

    monkeypatch.setattr("harness.structured.replay.load_result_records", forbidden_results_load)
    with pytest.raises(ReplayInputError, match="sha256 mismatch.*eh-py-0001.json"):
        replay(frozen_structured_run.path)
    assert loaded_results is False


def test_replay_refuses_item_and_index_tamper_before_loading_results(
    frozen_structured_run, monkeypatch
):
    item = frozen_structured_run.path / "inputs/items/eh-py-0001.json"
    value = json.loads(item.read_bytes())
    assert value["expected"]["label"] == "correct"
    value["expected"]["label"] = "swallowed_fatal"
    item.write_bytes(canonical_json(value))

    index_path = frozen_structured_run.path / "inputs/index.json"
    index = json.loads(index_path.read_bytes())
    entry = next(row for row in index["entries"] if row["path"] == "inputs/items/eh-py-0001.json")
    entry["sha256"] = sha256_file(item)
    index_path.write_bytes(canonical_json(index))
    run = json.loads((frozen_structured_run.path / "run.json").read_bytes())
    assert sha256_file(index_path) != run["inputs_index_sha256"]

    loaded_results = False

    def forbidden_results_load(*_args, **_kwargs):
        nonlocal loaded_results
        loaded_results = True
        raise AssertionError("results loaded before index authentication")

    monkeypatch.setattr("harness.structured.replay.load_result_records", forbidden_results_load)
    with pytest.raises(ReplayInputError, match="inputs_index_sha256 mismatch"):
        replay(frozen_structured_run.path)
    assert loaded_results is False


def test_index_digest_is_checked_before_index_json_is_parsed(frozen_structured_run):
    index_path = frozen_structured_run.path / "inputs/index.json"
    index_path.write_bytes(b"{not-json")
    with pytest.raises(ReplayInputError, match="inputs_index_sha256 mismatch"):
        replay(frozen_structured_run.path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda header: header.update({"tampered": True}),
            "run.json unknown key: tampered",
        ),
        (
            lambda header: header.pop("inputs_index_path"),
            "run.json missing key: inputs_index_path",
        ),
        (
            lambda header: header.update({"inputs_index_path": 1}),
            "run.json key inputs_index_path must be a string",
        ),
    ],
)
def test_replay_requires_a_closed_typed_header_before_reading_index(
    frozen_structured_run, monkeypatch, mutate, message
):
    header_path = frozen_structured_run.path / "run.json"
    header = json.loads(header_path.read_bytes())
    mutate(header)
    write_json_atomic(header_path, header)
    replay_module = __import__("harness.structured.replay", fromlist=["_read"])
    real_read = replay_module._read
    index_read = False

    def guarded_read(path, label):
        nonlocal index_read
        if label == "inputs/index.json":
            index_read = True
            raise AssertionError("index read before run.json header validation")
        return real_read(path, label)

    monkeypatch.setattr(replay_module, "_read", guarded_read)
    with pytest.raises(ReplayInputError) as caught:
        replay(frozen_structured_run.path)
    assert str(caught.value) == message
    assert index_read is False


@pytest.mark.parametrize("value", [None, "ABC", "a" * 63, "A" * 64])
def test_replay_requires_lowercase_sha256_header(frozen_structured_run, value):
    header_path = frozen_structured_run.path / "run.json"
    header = json.loads(header_path.read_bytes())
    if value is None:
        header.pop("inputs_index_sha256")
    else:
        header["inputs_index_sha256"] = value
    write_json_atomic(header_path, header)
    with pytest.raises(ReplayInputError, match="inputs_index_sha256"):
        replay(frozen_structured_run.path)


def test_replay_rejects_noncanonical_index_after_authentication(frozen_structured_run):
    index_path = frozen_structured_run.path / "inputs/index.json"
    index = json.loads(index_path.read_bytes())
    index_path.write_bytes(json.dumps(index, indent=2).encode() + b"\n")
    header = json.loads((frozen_structured_run.path / "run.json").read_bytes())
    header["inputs_index_sha256"] = sha256_file(index_path)
    write_json_atomic(frozen_structured_run.path / "run.json", header)
    with pytest.raises(ReplayInputError, match="index is not canonical JSON"):
        replay(frozen_structured_run.path)


def test_replay_rejects_missing_request_even_when_index_is_self_consistent(
    frozen_structured_run,
):
    relative = "inputs/requests/eh-py-0002-s0.json"
    (frozen_structured_run.path / relative).unlink()
    index = json.loads((frozen_structured_run.path / "inputs/index.json").read_bytes())
    index["entries"] = [row for row in index["entries"] if row["path"] != relative]
    _rewrite_index(frozen_structured_run, index)
    with pytest.raises(ReplayInputError, match="missing request snapshot.*eh-py-0002-s0"):
        replay(frozen_structured_run.path)


def test_replay_rejects_unlisted_input(frozen_structured_run):
    (frozen_structured_run.path / "inputs/unlisted.json").write_text("{}")
    with pytest.raises(ReplayInputError, match="unlisted input.*inputs/unlisted.json"):
        replay(frozen_structured_run.path)


@pytest.mark.parametrize("unsafe", ["inputs/../run.json", "/inputs/config.json"])
def test_replay_rejects_unsafe_path_before_hashing_snapshots(
    frozen_structured_run, unsafe
):
    index = json.loads((frozen_structured_run.path / "inputs/index.json").read_bytes())
    index["entries"][0]["path"] = unsafe
    index["entries"] = sorted(index["entries"], key=lambda row: row["path"])
    _rewrite_index(frozen_structured_run, index)
    with pytest.raises(ReplayInputError, match="unsafe input path"):
        replay(frozen_structured_run.path)


def test_replay_rejects_duplicate_index_path(frozen_structured_run):
    index = json.loads((frozen_structured_run.path / "inputs/index.json").read_bytes())
    index["entries"].append(dict(index["entries"][0]))
    _rewrite_index(frozen_structured_run, index)
    with pytest.raises(ReplayInputError, match="duplicate input path"):
        replay(frozen_structured_run.path)


def test_replay_rejects_a_missing_indexed_file(frozen_structured_run):
    path = frozen_structured_run.path / "inputs/items/eh-py-0001.json"
    path.unlink()
    with pytest.raises(ReplayInputError, match="missing input snapshot.*eh-py-0001.json"):
        replay(frozen_structured_run.path)
