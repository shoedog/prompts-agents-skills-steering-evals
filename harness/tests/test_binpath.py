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

from harness.providers.binpath import resolve_executable


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


def test_only_node_modules_entries_present_falls_back_to_bare_name(tmp_path, monkeypatch):
    shadow_dir = tmp_path / "project" / "node_modules" / ".bin"
    shadow_dir.mkdir(parents=True)
    _make_executable(shadow_dir / "codex")

    monkeypatch.setenv("PATH", str(shadow_dir))

    assert resolve_executable("codex") == "codex"


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
