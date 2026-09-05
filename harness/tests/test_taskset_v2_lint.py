from __future__ import annotations

import pytest

from harness.tests.structured_support import build_v2_taskset, taskset_case
from validators.taskset_v2_lint import lint_taskset


def test_lint_accepts_valid_taskset(tmp_path):
    root = build_v2_taskset(tmp_path, items=[{}])
    assert lint_taskset(root, repo_root=tmp_path) == []


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("bad_hash", "sha256 mismatch"),
        ("cross_split_duplicate", "duplicate input hash set across dev/test"),
        ("class_floor", "below min_per_class"),
        ("finding_spacing", "within 6 lines"),
        ("orphan_item", "manifest/items file mismatch"),
        ("id_collision", "experiment id collision"),
    ],
)
def test_lint_rejects_each_integrity_class(taskset_case, mutation, message):
    root, repo_root = taskset_case(mutation)
    assert any(message in error for error in lint_taskset(root, repo_root=repo_root))
