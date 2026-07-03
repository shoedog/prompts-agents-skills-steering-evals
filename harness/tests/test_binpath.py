"""Tests for resolve_executable's node_modules/.bin shadow avoidance.

See harness/providers/binpath.py's module docstring for the concrete failure
this guards against: `npx promptfoo eval` prepends this project's
`node_modules/.bin` onto PATH for its whole process tree (including our
Python provider/assert shims), and promptfoo's own optional dependencies
(`@openai/codex-sdk`, `@anthropic-ai/claude-agent-sdk`) can populate
`node_modules/.bin/<name>` with a same-named npm package binary that shadows
the real system CLI. All tests here build a fake PATH out of tmp_path dirs —
no real subprocess, no real PATH is touched or relied upon.
"""
import os
import stat

import pytest

from harness.providers.binpath import BinaryResolutionError, resolve_executable
from harness.providers.errors import ProviderError


def _make_executable(path):
    path.write_text("#!/bin/sh\necho hi\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_skips_node_modules_bin_entry_and_finds_real_one(tmp_path, monkeypatch):
    shadow_dir = tmp_path / "project" / "node_modules" / ".bin"
    shadow_dir.mkdir(parents=True)
    _make_executable(shadow_dir / "codex")

    real_dir = tmp_path / "opt" / "homebrew" / "bin"
    real_dir.mkdir(parents=True)
    _make_executable(real_dir / "codex")

    # node_modules/.bin listed FIRST, exactly as npx prepends it.
    monkeypatch.setenv("PATH", os.pathsep.join([str(shadow_dir), str(real_dir)]))

    resolved = resolve_executable("codex")
    assert resolved == str(real_dir / "codex")


def test_only_node_modules_entries_present_raises_binary_resolution_error(tmp_path, monkeypatch):
    # This is the exact incident binpath.py exists to prevent: if every match
    # is a node_modules shadow, a bare-name return would let subprocess's own
    # PATH search re-resolve to the same broken shim. Must raise instead.
    shadow_dir = tmp_path / "project" / "node_modules" / ".bin"
    shadow_dir.mkdir(parents=True)
    shadow_path = shadow_dir / "codex"
    _make_executable(shadow_path)

    monkeypatch.setenv("PATH", str(shadow_dir))

    with pytest.raises(BinaryResolutionError) as exc_info:
        resolve_executable("codex")

    # BinaryResolutionError must be a ProviderError so it flows through the
    # existing except ProviderError handlers in judge.py / promptfoo_claude.py
    # instead of crashing the whole run.
    assert isinstance(exc_info.value, ProviderError)
    assert str(shadow_path) in str(exc_info.value)
    assert "codex" in str(exc_info.value)


def test_multiple_shadowed_node_modules_matches_all_listed_in_error(tmp_path, monkeypatch):
    shadow_dir_1 = tmp_path / "a" / "node_modules" / ".bin"
    shadow_dir_1.mkdir(parents=True)
    _make_executable(shadow_dir_1 / "codex")

    shadow_dir_2 = tmp_path / "a" / "b" / "node_modules" / ".bin"
    shadow_dir_2.mkdir(parents=True)
    _make_executable(shadow_dir_2 / "codex")

    monkeypatch.setenv("PATH", os.pathsep.join([str(shadow_dir_1), str(shadow_dir_2)]))

    with pytest.raises(BinaryResolutionError) as exc_info:
        resolve_executable("codex")

    message = str(exc_info.value)
    assert str(shadow_dir_1 / "codex") in message
    assert str(shadow_dir_2 / "codex") in message


def test_no_path_entries_falls_back_to_bare_name(monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert resolve_executable("codex") == "codex"


def test_nested_node_modules_ancestor_also_skipped(tmp_path, monkeypatch):
    # npm prepends node_modules/.bin for EVERY ancestor directory, not just
    # the immediate project root.
    shadow_dir = tmp_path / "a" / "b" / "node_modules" / ".bin"
    shadow_dir.mkdir(parents=True)
    _make_executable(shadow_dir / "claude")

    real_dir = tmp_path / "usr" / "local" / "bin"
    real_dir.mkdir(parents=True)
    _make_executable(real_dir / "claude")

    monkeypatch.setenv("PATH", os.pathsep.join([str(shadow_dir), str(real_dir)]))
    assert resolve_executable("claude") == str(real_dir / "claude")


def test_non_executable_match_is_skipped(tmp_path, monkeypatch):
    non_exec_dir = tmp_path / "bin1"
    non_exec_dir.mkdir()
    (non_exec_dir / "codex").write_text("not executable")  # no exec bit

    real_dir = tmp_path / "bin2"
    real_dir.mkdir()
    _make_executable(real_dir / "codex")

    monkeypatch.setenv("PATH", os.pathsep.join([str(non_exec_dir), str(real_dir)]))
    assert resolve_executable("codex") == str(real_dir / "codex")
