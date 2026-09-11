from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from harness.structured.results import canonical_json
from harness.structured.trends import append_trend


def test_trends_append_without_rewriting_existing_line(tmp_path):
    path = tmp_path / "classify_error_handling.jsonl"
    append_trend(path, {"run_id": "one", "promotable": False})
    first = path.read_bytes()
    append_trend(path, {"run_id": "two", "promotable": True})
    assert path.read_bytes().startswith(first)
    assert [json.loads(line)["run_id"] for line in path.read_text().splitlines()] == [
        "one",
        "two",
    ]
    assert first == canonical_json({"run_id": "one", "promotable": False}) + b"\n"


def test_trends_file_lock_preserves_concurrent_canonical_rows(tmp_path):
    path = tmp_path / "trends" / "classify_error_handling.jsonl"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda number: append_trend(path, {"n": number}), range(30)))
    rows = path.read_bytes().splitlines()
    assert len(rows) == 30
    assert sorted(json.loads(row)["n"] for row in rows) == list(range(30))
    assert all(canonical_json(json.loads(row)) == row for row in rows)
