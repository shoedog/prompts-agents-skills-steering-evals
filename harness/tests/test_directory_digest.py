from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.structured.taskset import TasksetError, sha256_directory


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests/fixtures/conformance/digest-001"


def test_directory_digest_matches_conformance_fixture():
    expected = json.loads((FIXTURE / "expected.json").read_text())
    assert sha256_directory(FIXTURE / "tree", ignore=expected["ignore"]) == expected["digest"]


def test_executable_bit_changes_digest(tmp_path):
    path = tmp_path / "run.sh"
    path.write_text("exit 0\n")
    regular = sha256_directory(tmp_path, ignore=[])
    path.chmod(0o755)
    assert sha256_directory(tmp_path, ignore=[]) != regular


def test_ignored_and_git_files_do_not_change_digest(tmp_path):
    (tmp_path / "kept.txt").write_text("kept\n")
    before = sha256_directory(tmp_path, ignore=["*.tmp"])
    (tmp_path / "ignored.tmp").write_text("ignored\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/config").write_text("ignored too\n")
    assert sha256_directory(tmp_path, ignore=["*.tmp"]) == before


def test_symlink_hashes_literal_target_without_following(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.write_text("one\n")
    os.symlink(str(outside), tmp_path / "link")
    before = sha256_directory(tmp_path, ignore=[])
    outside.write_text("two\n")
    assert sha256_directory(tmp_path, ignore=[]) == before
    (tmp_path / "link").unlink()
    os.symlink("different-target", tmp_path / "link")
    assert sha256_directory(tmp_path, ignore=[]) != before


def test_nfc_path_collision_is_rejected(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_text("one")
    second.write_text("two")

    class Entry:
        def __init__(self, name, path):
            self.name = name
            self.path = str(path)

        def stat(self, *, follow_symlinks):
            assert follow_symlinks is False
            return Path(self.path).stat()

    monkeypatch.setattr(
        "harness.structured.taskset.os.scandir",
        lambda directory: [
            Entry("\N{LATIN SMALL LETTER E WITH ACUTE}", first),
            Entry("e\N{COMBINING ACUTE ACCENT}", second),
        ],
    )
    with pytest.raises(TasksetError, match="normalize to the same path"):
        sha256_directory(tmp_path, ignore=[])


def test_socket_is_rejected(tmp_path, monkeypatch):
    class SocketEntry:
        name = "fixture.sock"
        path = str(tmp_path / name)

        def stat(self, *, follow_symlinks):
            assert follow_symlinks is False
            return SimpleNamespace(st_mode=stat.S_IFSOCK)

    monkeypatch.setattr(
        "harness.structured.taskset.os.scandir", lambda directory: [SocketEntry()]
    )
    with pytest.raises(TasksetError, match="unsupported file type"):
        sha256_directory(tmp_path, ignore=[])
