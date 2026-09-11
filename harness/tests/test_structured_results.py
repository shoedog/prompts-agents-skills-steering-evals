from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import PurePosixPath
from unittest.mock import patch

import pytest

from harness.resultsdir import (
    check_structured_stale_results_dir,
    structured_stale_files,
)
from harness.structured.results import (
    ResultCollisionError,
    ResultsWriter,
    canonical_json,
    confined_run_dir,
    write_json_atomic,
)


def test_canonical_json_is_sorted_compact_utf8_without_a_newline():
    assert canonical_json({"z": 1, "message": "café", "a": [True, None]}) == (
        b'{"a":[true,null],"message":"caf\xc3\xa9","z":1}'
    )


def test_atomic_write_replaces_with_canonical_json_and_one_newline(tmp_path):
    path = tmp_path / "calls" / "v1-item-0.json"
    write_json_atomic(path, {"z": 1, "a": 2})
    assert path.read_bytes() == b'{"a":2,"z":1}\n'

    write_json_atomic(path, {"state": "replacement"})
    assert path.read_bytes() == b'{"state":"replacement"}\n'


def test_failed_atomic_write_preserves_previous_record(tmp_path, monkeypatch):
    path = tmp_path / "calls" / "v1-item-0.json"
    write_json_atomic(path, {"state": "old"})

    def fail_json(_value):
        raise TypeError("not serializable")

    monkeypatch.setattr("harness.structured.results.canonical_json", fail_json)
    with pytest.raises(TypeError, match="not serializable"):
        write_json_atomic(path, {"state": object()})
    assert json.loads(path.read_text()) == {"state": "old"}


@pytest.mark.parametrize(
    "relative_path",
    [
        PurePosixPath("/absolute.json"),
        PurePosixPath("../escaped.json"),
        PurePosixPath("nested/../../escaped.json"),
        PurePosixPath(""),
    ],
)
def test_writer_rejects_invalid_relative_artifact_paths(tmp_path, relative_path):
    writer = ResultsWriter(tmp_path / "run")
    with pytest.raises(ValueError, match="relative artifact path"):
        writer.write_json(relative_path, {"bad": True})


def test_writer_rejects_a_symlink_destination_outside_run_root(tmp_path):
    root = tmp_path / "run"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    writer = ResultsWriter(root)

    with pytest.raises(ValueError, match="outside results root"):
        writer.write_json(PurePosixPath("linked/escaped.json"), {"bad": True})
    assert not (outside / "escaped.json").exists()


def test_run_directory_rejects_experiment_symlink_outside_results(tmp_path):
    results = tmp_path / "results"
    outside = tmp_path / "outside"
    results.mkdir()
    outside.mkdir()
    (results / "st-linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes results"):
        confined_run_dir(tmp_path, "st-linked", "run-1")


def test_write_json_returns_destination_and_write_once_preserves_collision_bytes(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    relative = PurePosixPath("calls/v1-item-0.json")
    destination = writer.write_json(relative, {"state": "first"})
    assert destination == writer.root / relative

    before = destination.read_bytes()
    with pytest.raises(ResultCollisionError, match="calls/v1-item-0.json"):
        writer.write_json_once(relative, {"state": "second"})
    assert destination.read_bytes() == before


def test_sample_stage_path_is_unique_and_a_second_write_is_an_error(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    ref = writer.write_stage(
        version="v1",
        item_id="item",
        stage="classify",
        sample=2,
        shared=False,
        value={"sample": 2},
    )
    assert ref.path == "stages/v1-item-s2-classify.json"
    assert ref.sha256 == hashlib.sha256((writer.root / ref.path).read_bytes()).hexdigest()
    with pytest.raises(FrozenInstanceError):
        ref.path = "changed.json"
    with pytest.raises(ResultCollisionError, match="stages/v1-item-s2-classify.json"):
        writer.write_stage(
            version="v1",
            item_id="item",
            stage="classify",
            sample=2,
            shared=False,
            value={"sample": 2},
        )


def test_shared_stage_is_written_once_without_a_sample_component(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    ref = writer.write_stage(
        version="v1",
        item_id="item",
        stage="targets",
        sample=None,
        shared=True,
        value={"targets": []},
    )
    assert ref.path == "stages/v1-item-targets.json"
    assert ref.sha256 == hashlib.sha256((writer.root / ref.path).read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "shared,sample",
    [
        (False, None),
        (True, 0),
    ],
)
def test_stage_sample_rules_are_enforced(tmp_path, shared, sample):
    writer = ResultsWriter(tmp_path / "run")
    with pytest.raises(ValueError, match="sample"):
        writer.write_stage(
            version="v1",
            item_id="item",
            stage="classify",
            sample=sample,
            shared=shared,
            value={},
        )


def test_stage_path_components_cannot_change_the_results_layout(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    for field, value in (
        ("version", "../v1"),
        ("item_id", "nested/item"),
        ("stage", ""),
    ):
        arguments = {"version": "v1", "item_id": "item", "stage": "classify"}
        arguments[field] = value
        with pytest.raises(ValueError, match=field):
            writer.write_stage(
                **arguments,
                sample=0,
                shared=False,
                value={},
            )


def test_locked_jsonl_keeps_every_concurrent_event(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda number: writer.append_event("replay", {"n": number}), range(40)))
    rows = [json.loads(line) for line in (writer.root / "replay.jsonl").read_text().splitlines()]
    assert sorted(row["n"] for row in rows) == list(range(40))


def test_trace_event_has_one_local_owner_and_forwards_without_a_results_dir(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    row = {"item_id": "item", "stage": "classify"}

    with patch("harness.structured.results.trace_call") as trace_call:
        writer.append_event("replay", row)
        writer.append_event("trace", row)

    assert (writer.root / "replay.jsonl").read_bytes() == canonical_json(row) + b"\n"
    assert (writer.root / "trace.jsonl").read_bytes() == canonical_json(row) + b"\n"
    trace_call.assert_called_once_with("structured", row, results_dir=None)


def test_append_event_rejects_an_unknown_stream(tmp_path):
    writer = ResultsWriter(tmp_path / "run")
    with pytest.raises(ValueError, match="event name"):
        writer.append_event("other", {})


def test_stale_refusal_does_not_delete_existing_bytes(tmp_path):
    path = tmp_path / "calls" / "v1-item-0.json"
    write_json_atomic(path, {"state": "old"})
    before = path.read_bytes()
    assert check_structured_stale_results_dir(tmp_path, force=False) is False
    assert path.read_bytes() == before


def test_structured_stale_scan_and_force_are_limited_to_the_results_layout(tmp_path):
    relative_paths = [
        "calls/v1-item-0.json",
        "stages/v1-item-s0-classify.json",
        "asserts/v1-item-0.json",
        "inputs/config.json",
        "inputs/items/item.json",
        "replay.jsonl",
        "trace.jsonl",
        "run.json",
        "metrics.json",
        "report.md",
    ]
    expected = []
    for relative in relative_paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
        expected.append(path)
    unrelated = tmp_path / "notes.txt"
    unrelated.write_text("preserve me")

    assert structured_stale_files(tmp_path) == sorted(expected)
    assert check_structured_stale_results_dir(tmp_path, force=True) is True
    assert all(not path.exists() for path in expected)
    assert unrelated.read_text() == "preserve me"
    assert structured_stale_files(tmp_path) == []
    assert check_structured_stale_results_dir(tmp_path, force=False) is True
