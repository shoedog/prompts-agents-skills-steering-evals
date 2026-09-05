from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
HELP_COMMANDS = {
    "python -m harness.run --help",
    "python -m harness.structured.run --help",
    "python -m harness.structured.replay --help",
}


def _documented_help_commands() -> set[str]:
    return set(re.findall(r"^python -m harness(?:\.structured)?\.[a-z]+ --help$", README.read_text(), re.M))


def test_documented_help_commands_exit_zero_without_model_calls():
    commands = _documented_help_commands()
    assert commands == HELP_COMMANDS
    for command in sorted(commands):
        argv = command.split()
        proc = subprocess.run(
            [sys.executable, *argv[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "usage:" in proc.stdout.lower()


def test_readme_carries_required_truth_and_named_evidence():
    text = README.read_text()
    required = (
        "Python 3.12",
        "taskset v2",
        "inputs/index.json",
        "PROMOTABLE",
        "--allow-test",
        "synthetic",
        "human-vs-human",
        "audited deployment identity",
        "directory-digest-v1",
        "structured-smoke-001",
        "test_generation_leg_matches_golden",
        "test_directory_digest_matches_conformance_fixture",
        "test_snapshot_index_has_exact_digest_pair_and_closed_versioned_requests",
        "test_each_promotion_condition_can_veto",
        "test_test_split_without_allow_test_exits_five_before_writes",
        "test_claude_provider_yaml_unchanged_regression",
        "test_scrub_marks_sandbox_and_lineage_rows",
        "test_scrub_is_idempotent",
        "test_scrub_without_matching_parent_leaves_row_alone",
    )
    for claim in required:
        assert claim in text
