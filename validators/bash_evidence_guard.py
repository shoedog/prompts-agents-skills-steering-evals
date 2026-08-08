#!/usr/bin/env python3
"""bash-evidence-guard — warn-only evidence-integrity validator.

Guards Bash commands against two panel-approved risks in the 2026-08-08
evidence-integrity review.  It is intentionally self-contained (standard
library only) so the same scanner and adapters work in Claude Code, Codex, and
Kiro hook processes under Python 3.9.

Rules (the cited incidents and panel decisions are normative):
  E1 truncated-test-output  WARN  A test runner feeds head, tail, grep -c/-q/-m,
                              or wc -l in one pipeline, losing test evidence.
                              [608a7a2a; 9aea8b01; 225b97db; sol W2-W7; opus]
  E2a false-PASS sentinel    WARN  set -e/errexit without pipefail, an executable
                              subshell/substitution/pipeline, then a later
                              echo/printf PASS/OK/SUCCESS-shaped sentinel.
                              [fb80415b:13598-13608; both lanes]
  E2b pipeline-status loss   WARN  A runner pipeline ends in a non-runner with
                              no pipefail or PIPESTATUS/pipestatus recovery.
                              [sol tee-status finding; both lanes]

This is deliberately a bounded scanner, not a shell parser: it blanks heredoc
bodies, splits top-level lists then pipelines, examines stages, and recurses no
more than twice into executable shell strings and substitutions.  That scope
is the v2 panel contract (SPEC.md sections 2-4), not an invitation to infer a
full shell grammar.

Modes:
  bash_evidence_guard.py --cmd COMMAND
  bash_evidence_guard.py --hook          Claude Code PreToolUse JSON on stdin
  bash_evidence_guard.py --codex-hook    Codex PreToolUse JSON on stdin
  bash_evidence_guard.py --kiro-hook     Kiro preToolUse JSON on stdin
  bash_evidence_guard.py --self-test     embedded core and adapter fixtures
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


MAX_RECURSION = 2
KIRO_SHELL_TOOLS = {
    "execute_bash", "executebash", "execute_cmd", "executecmd", "shell",
}
SENTINEL = re.compile(r"(?i)\b(?:pass|ok|success|passed|green)\b")
PIPEFAIL = re.compile(r"(?i)\bpipefail\b")
STATUS_RECOVERY = re.compile(r"(?i)(?:\$?\{?PIPESTATUS\b|\$?\{?pipestatus\b)")
ERREXIT = re.compile(r"(?i)(?:\bset\s+-[A-Za-z]*e[A-Za-z]*\b|\bset\s+-o\s+errexit\b)")


@dataclass(frozen=True)
class Finding:
    """One warn-only panel finding, with its shell subject and source line."""

    rule: str
    detail: str
    subject: str
    line: int


@dataclass(frozen=True)
class Evaluation:
    """Scanner result plus the loggable decision required by SPEC.md section 6."""

    findings: Tuple[Finding, ...]
    has_runner: bool
    escaped: bool

    @property
    def decision(self) -> str:
        if self.escaped:
            return "escape"
        if self.findings:
            return "warn"
        return "clean"

    @property
    def rule(self) -> Optional[str]:
        return self.findings[0].rule if self.findings and not self.escaped else None


@dataclass(frozen=True)
class Runner:
    """A recognized runner stage; ``runs`` is false for runner-specific probes."""

    recognized: bool
    runs: bool
    command_index: int


@dataclass(frozen=True)
class ListElement:
    """One bounded top-level list element and its retained shell separators."""

    text: str
    line: int
    preceding_separator: str
    following_separator: str


def _blank_heredoc_bodies(text: str) -> str:
    """Replace simple heredoc bodies with newlines before scanning (opus SMELL-A).

    The guard only needs the panel's bounded ``<<WORD`` / ``<<'WORD'`` shapes.
    Keeping newline count preserves useful source lines without treating body text
    as executable shell.
    """
    lines = text.splitlines(True)
    kept: List[str] = []
    index = 0
    marker_re = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|([A-Za-z_][A-Za-z0-9_]*))")
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        match = marker_re.search(line)
        if not match:
            index += 1
            continue
        marker = next(part for part in match.groups() if part is not None)
        index += 1
        while index < len(lines):
            body_line = lines[index]
            comparable = body_line.rstrip("\r\n")
            if comparable.lstrip("\t") == marker:
                kept.append(body_line)
                index += 1
                break
            kept.append("\n" if body_line.endswith("\n") else "")
            index += 1
    return "".join(kept)


def _strip_comments(text: str) -> Tuple[str, bool]:
    """Return executable text and whether its final real comment is evidence-ok."""
    out: List[str] = []
    comments: List[Tuple[int, int, str]] = []
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            out.append(char)
            if char == "\\" and quote == '"' and index + 1 < len(text):
                out.append(text[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            out.append(char)
            index += 1
            continue
        if char == "\\" and index + 1 < len(text):
            out.append(char)
            out.append(text[index + 1])
            index += 2
            continue
        previous = text[index - 1] if index else "\n"
        if char == "#" and (index == 0 or previous.isspace() or previous in ";|&()"):
            end = text.find("\n", index)
            if end < 0:
                end = len(text)
            comments.append((index, end, text[index:end]))
            out.append(" " * (end - index))
            index = end
            continue
        out.append(char)
        index += 1
    escaped = False
    if comments:
        start, end, comment = comments[-1]
        escaped = (not text[end:].strip()
                   and bool(re.match(r"#\s*evidence-ok:\s*\S", comment, re.IGNORECASE)))
    return "".join(out), escaped


def _split_top_level_list(text: str, base_line: int = 1) -> List[ListElement]:
    """Split on shell list separators while respecting bounded quote/subshell state."""
    pieces: List[ListElement] = []
    start = 0
    preceding = ""
    quote: Optional[str] = None
    backtick = False
    parens = 0
    index = 0

    def append_piece(end: int, following: str) -> None:
        piece = text[start:end].strip()
        if piece:
            line = base_line + text.count("\n", 0, start)
            pieces.append(ListElement(piece, line, preceding, following))

    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\" and quote == '"' and index + 1 < len(text):
                index += 2
                continue
            if char == "`" and quote == '"':
                backtick = not backtick
            elif char == quote and not backtick:
                quote = None
            index += 1
            continue
        if backtick:
            if char == "\\" and index + 1 < len(text):
                index += 2
                continue
            if char == "`":
                backtick = False
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "`":
            backtick = True
            index += 1
            continue
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == "$" and index + 1 < len(text) and text[index + 1] == "(":
            parens += 1
            index += 2
            continue
        if char == "(":
            parens += 1
            index += 1
            continue
        if char == ")" and parens:
            parens -= 1
            index += 1
            continue
        if parens == 0:
            if char == "\n" or char == ";":
                separator = char
                append_piece(index, separator)
                index += 1
                start = index
                preceding = separator
                continue
            if char == "&" and not ((index and text[index - 1] in ">|")
                                    or (index + 1 < len(text) and text[index + 1] == ">")):
                separator = "&&" if index + 1 < len(text) and text[index + 1] == "&" else "&"
                append_piece(index, separator)
                index += len(separator)
                start = index
                preceding = separator
                continue
            if char == "|" and index + 1 < len(text) and text[index + 1] == "|":
                separator = "||"
                append_piece(index, separator)
                index += 2
                start = index
                preceding = separator
                continue
        index += 1
    append_piece(len(text), "")
    return pieces


def _split_pipeline(text: str) -> List[str]:
    """Split one list element into stages; ``|&`` is a pipe and ``||`` is not."""
    stages: List[str] = []
    start = 0
    quote: Optional[str] = None
    backtick = False
    parens = 0
    index = 0

    def append_stage(end: int) -> None:
        stage = text[start:end].strip()
        if stage:
            stages.append(stage)

    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\" and quote == '"' and index + 1 < len(text):
                index += 2
                continue
            if char == "`" and quote == '"':
                backtick = not backtick
            elif char == quote and not backtick:
                quote = None
            index += 1
            continue
        if backtick:
            if char == "\\" and index + 1 < len(text):
                index += 2
                continue
            if char == "`":
                backtick = False
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if char == "`":
            backtick = True
            index += 1
            continue
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == "$" and index + 1 < len(text) and text[index + 1] == "(":
            parens += 1
            index += 2
            continue
        if char == "(":
            parens += 1
            index += 1
            continue
        if char == ")" and parens:
            parens -= 1
            index += 1
            continue
        if char == "|" and parens == 0 and not (index + 1 < len(text) and text[index + 1] == "|"):
            append_stage(index)
            index += 2 if index + 1 < len(text) and text[index + 1] == "&" else 1
            start = index
            continue
        index += 1
    append_stage(len(text))
    return stages


def _shell_words(stage: str) -> List[str]:
    """Small quote- and escape-aware word splitter for one pipeline stage."""
    words: List[str] = []
    index = 0
    while index < len(stage):
        while index < len(stage) and stage[index].isspace():
            index += 1
        if index >= len(stage):
            break
        word: List[str] = []
        quote: Optional[str] = None
        while index < len(stage):
            char = stage[index]
            if quote is not None:
                if char == "\\" and quote == '"' and index + 1 < len(stage):
                    word.append(stage[index + 1])
                    index += 2
                    continue
                if char == quote:
                    quote = None
                else:
                    word.append(char)
                index += 1
                continue
            if char in ("'", '"'):
                quote = char
                index += 1
                continue
            if char == "\\" and index + 1 < len(stage):
                word.append(stage[index + 1])
                index += 2
                continue
            if char.isspace():
                break
            word.append(char)
            index += 1
        words.append("".join(word))
        while index < len(stage) and stage[index].isspace():
            index += 1
    return words


def _basename(word: str) -> str:
    return os.path.basename(word).lower()


def _is_assignment(word: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word))


def _skip_option(words: Sequence[str], index: int) -> int:
    """Skip one common wrapper option, consuming its value when applicable."""
    option = words[index]
    if option in ("-C", "-c", "-n", "-p", "-u", "-w", "-e", "--env", "--workdir",
                  "--user", "--timeout", "--kill-after", "--replace"):
        return min(len(words), index + 2)
    return index + 1


def _executable_index(words: Sequence[str]) -> int:
    """Find a command word after bounded env/timeout/nice prefixes (sol W6)."""
    index = 0
    while index < len(words) and _is_assignment(words[index]):
        index += 1
    while index < len(words):
        command = _basename(words[index])
        if command == "env":
            index += 1
            while index < len(words):
                if _is_assignment(words[index]):
                    index += 1
                elif words[index].startswith("-"):
                    index = _skip_option(words, index)
                else:
                    break
            continue
        if command == "timeout":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index = _skip_option(words, index)
            if index < len(words):
                index += 1  # duration
            continue
        if command == "nice":
            index += 1
            while index < len(words) and words[index].startswith("-"):
                index = _skip_option(words, index)
            continue
        break
    return index


def _generic_nonrun(args: Sequence[str]) -> bool:
    return any(arg in ("--help", "-h", "--version", "-V", "--list", "--list-tests", "--dry-run")
               for arg in args)


def _runner_for_words(words: Sequence[str]) -> Runner:
    """Recognize the SPEC.md section 3 runner vocabulary at a stage boundary."""
    index = _executable_index(words)
    if index >= len(words):
        return Runner(False, False, index)
    command = _basename(words[index])
    args = list(words[index + 1:])

    def active(extra_nonrun: bool = False) -> Runner:
        return Runner(True, not (extra_nonrun or _generic_nonrun(args)), index)

    if command in ("pytest", "vitest", "jest", "gotestsum", "tox", "nox", "ctest", "phpunit",
                   "rspec", "verify-mutation-gates"):
        return active(command == "pytest" and any(a in ("--collect-only", "--co") for a in args)
                      or command == "ctest" and any(a in ("-N", "--show-only") for a in args)
                      or command == "jest" and "--listTests" in args)
    if command == "python" and len(args) >= 2 and args[0] == "-m" and args[1] in ("pytest", "unittest"):
        return active(any(a in ("--collect-only", "--co") for a in args[2:]))
    if command in ("uv", "poetry") and len(args) >= 2 and args[0] == "run" and args[1] == "pytest":
        return active(any(a in ("--collect-only", "--co") for a in args[2:]))
    if command == "cargo" and args[:1] == ["test"]:
        return active("--no-run" in args)
    if command == "cargo" and args[:2] == ["nextest", "run"]:
        return active()
    if command in ("npm", "pnpm", "yarn", "bun"):
        is_test = args[:1] in (["test"], ["t"]) or args[:2] == ["run", "test"]
        return active() if is_test else Runner(False, False, index)
    if command == "go" and args[:1] == ["test"]:
        return active()
    if command in ("mvn", "mvnw") and args[:1] in (["test"], ["verify"]):
        return active()
    if command in ("gradle", "gradlew") and args[:1] == ["test"]:
        return active()
    if command == "make":
        pos = 0
        while pos < len(args) and args[pos].startswith("-"):
            pos = _skip_option(args, pos)
        return active() if pos < len(args) and args[pos] in ("test", "check") else Runner(False, False, index)
    if command == "just" and args[:1] == ["test"]:
        return active()
    if command == "swift" and args[:1] == ["test"]:
        return active()
    if command == "dotnet" and args[:1] == ["test"]:
        return active()
    if command == "deno" and args[:1] == ["test"]:
        return active()
    if command == "flutter" and args[:1] == ["test"]:
        return active()
    if command == "bazel" and args[:1] == ["test"]:
        return active()
    if command == "rake" and args[:1] == ["test"]:
        return active()
    if command == "mix" and args[:1] == ["test"]:
        return active()
    return Runner(False, False, index)


def _destructive_filter(words: Sequence[str]) -> bool:
    """Whether a normalized downstream stage destroys the runner's evidence."""
    index = _executable_index(words)
    if index >= len(words):
        return False
    command = _basename(words[index])
    args = words[index + 1:]
    if command in ("head", "tail"):
        return True
    if command == "grep":
        return any(arg in ("-c", "-q", "-m") or arg.startswith("-m")
                   or arg.startswith("--max-count") for arg in args)
    if command == "wc":
        return any(arg == "-l" or (arg.startswith("-") and "l" in arg[1:]) for arg in args)
    return False


def _is_discard_sink(path: str) -> bool:
    return (not path or path == "-" or path.startswith("&") or path == "/dev/null"
            or path.startswith("/dev/fd/") or path.startswith("<(") or path.startswith(">("))


def _has_capture_path(words: Sequence[str]) -> bool:
    """Recognize a stdout capture path on the runner's own stage (sol W4)."""
    index = 0
    while index < len(words):
        word = words[index]
        match = re.match(r"^(?:1)?(>>|>)(.*)$", word)
        if match:
            target = match.group(2)
            if not target and index + 1 < len(words):
                target = words[index + 1]
                index += 1
            if not _is_discard_sink(target):
                return True
        index += 1
    return False


def _tee_captures(words: Sequence[str]) -> bool:
    """``tee FILE`` is an E1 allowance only as the first downstream consumer."""
    index = _executable_index(words)
    if index >= len(words) or _basename(words[index]) != "tee":
        return False
    args = list(words[index + 1:])
    pos = 0
    while pos < len(args) and args[pos].startswith("-"):
        pos += 1
    return pos < len(args) and not _is_discard_sink(args[pos])


def _matching_paren(text: str, start: int) -> int:
    """Find the close for a ``$(`` body, honoring quotes and nested parens."""
    depth = 1
    quote: Optional[str] = None
    index = start
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\" and quote == '"' and index + 1 < len(text):
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "\\" and index + 1 < len(text):
            index += 2
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _matching_backtick(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] == "`":
            return index
        index += 1
    return -1


def _substitution_bodies(text: str) -> List[str]:
    """Extract executable ``$(...)`` and backtick bodies, including in double quotes."""
    bodies: List[str] = []
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if char == "\\" and quote != "'" and index + 1 < len(text):
            index += 2
            continue
        if char in ("'", '"') and quote is None:
            quote = char
            index += 1
            continue
        if char == '"' and quote == '"':
            quote = None
            index += 1
            continue
        if char == "$" and index + 1 < len(text) and text[index + 1] == "(":
            end = _matching_paren(text, index + 2)
            if end >= 0:
                bodies.append(text[index + 2:end])
                index = end + 1
                continue
        if char == "`" and quote != "'":
            end = _matching_backtick(text, index + 1)
            if end >= 0:
                bodies.append(text[index + 1:end])
                index = end + 1
                continue
        index += 1
    return bodies


def _wrapper_bodies(stage: str, words: Sequence[str]) -> List[str]:
    """Extract executable string arguments from the panel's bounded wrappers."""
    index = _executable_index(words)
    if index >= len(words):
        return []
    command = _basename(words[index])
    args = list(words[index + 1:])
    if command in ("bash", "sh", "zsh", "dash"):
        for pos, arg in enumerate(args):
            if arg == "-c" or (arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]):
                return [args[pos + 1]] if pos + 1 < len(args) else []
    if command == "ssh":
        pos = 0
        while pos < len(args) and args[pos].startswith("-"):
            pos = _skip_option(args, pos)
        return [" ".join(args[pos + 1:])] if pos + 1 < len(args) else []
    if command == "docker" and args[:1] == ["exec"]:
        pos = 1
        while pos < len(args) and args[pos].startswith("-"):
            pos = _skip_option(args, pos)
        return [" ".join(args[pos + 1:])] if pos + 1 < len(args) else []
    if command == "xargs":
        pos = 0
        while pos < len(args) and args[pos].startswith("-"):
            pos = _skip_option(args, pos)
        return [" ".join(args[pos:])] if pos < len(args) else []
    if command in ("env", "timeout", "nice"):
        next_index = _executable_index(words)
        if next_index > index and next_index < len(words):
            return [" ".join(words[next_index:])]
    return []


def _compound_kinds(text: str) -> "set":
    """Kinds of real compound structure in a list element (not quoted data):
    "group" = subshell/substitution/backticks (set -e may not propagate the
    failure — the fb80415b mechanism, INDEPENDENT of pipefail); "pipe" = a
    top-level pipeline (safe under pipefail, unsafe without it)."""
    kinds: set = set()
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote is not None:
            if char == "\\" and quote == '"' and index + 1 < len(text):
                index += 2
                continue
            if char == quote:
                quote = None
            elif char == "$" and quote == '"' and index + 1 < len(text) and text[index + 1] == "(":
                kinds.add("group")
            elif char == "`" and quote == '"':
                kinds.add("group")
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "\\" and index + 1 < len(text):
            index += 2
            continue
        elif char == "(" or char == "`" or (char == "$" and index + 1 < len(text) and text[index + 1] == "("):
            kinds.add("group")
        elif char == "|" and not (index + 1 < len(text) and text[index + 1] == "|"):
            kinds.add("pipe")
        index += 1
    return kinds


def _sentinel_element(element: str) -> bool:
    stages = _split_pipeline(element)
    if not stages:
        return False
    words = _shell_words(stages[-1])
    index = _executable_index(words)
    return bool(index < len(words) and _basename(words[index]) in ("echo", "printf")
                and SENTINEL.search(" ".join(words[index + 1:])))


def _e2a_finding(text: str, elements: Sequence[ListElement]) -> Optional[Finding]:
    """Find the fb80415b set-e/subshell/later-sentinel incident shape (E2a).

    pipefail gates ONLY the pipeline branch: a subshell/substitution failure
    is invisible to pipefail, and the real incident ran under
    `set -euo pipefail` (spec v2.1 correction)."""
    if not ERREXIT.search(text):
        return None
    first_errexit = next((i for i, element in enumerate(elements) if ERREXIT.search(element.text)), None)
    if first_errexit is None:
        return None
    pipefail = bool(PIPEFAIL.search(text))
    compound = next((i for i, element in enumerate(elements)
                     if i >= first_errexit
                     and ("group" in _compound_kinds(element.text)
                          or (not pipefail and "pipe" in _compound_kinds(element.text)))), None)
    if compound is None:
        return None
    for element in elements[compound + 1:]:
        if _sentinel_element(element.text):
            return Finding(
                "E2a",
                "The PASS/OK sentinel is not explicitly gated on the earlier compound step's status; "
                "gate it with `status=$?; [ $status -eq 0 ] && printf '...PASS...'` (and exit on failure).",
                element.text,
                element.line,
            )
    return None


def _scan_text(text: str, depth: int = 0, base_line: int = 1) -> Tuple[List[Finding], bool]:
    """Run the bounded list/pipeline scanner; recursion never exceeds two levels."""
    prepared = _blank_heredoc_bodies(text)
    executable, _ = _strip_comments(prepared)
    elements = _split_top_level_list(executable, base_line)
    findings: List[Finding] = []
    has_runner = False
    e2a = _e2a_finding(executable, elements)
    if e2a is not None:
        findings.append(e2a)
    status_preserved = bool(PIPEFAIL.search(executable) or STATUS_RECOVERY.search(executable))

    for element in elements:
        stages = _split_pipeline(element.text)
        words_by_stage = [_shell_words(stage) for stage in stages]
        runners = [_runner_for_words(words) for words in words_by_stage]
        for runner in runners:
            has_runner = has_runner or runner.recognized
        for runner_index, runner in enumerate(runners):
            if not runner.runs:
                continue
            destructive = any(_destructive_filter(words_by_stage[pos])
                              for pos in range(runner_index + 1, len(stages)))
            captures = _has_capture_path(words_by_stage[runner_index])
            first_consumer_captures = (runner_index + 1 < len(stages)
                                       and _tee_captures(words_by_stage[runner_index + 1]))
            e1_fired = destructive and not (captures or first_consumer_captures)
            subject = " | ".join(stages)
            if e1_fired:
                corrected = stages[runner_index].strip() + " >full.log 2>&1"
                findings.append(Finding(
                    "E1",
                    "This runner's output is truncated by a downstream filter; capture it first with `"
                    + corrected + "` and inspect the capture after the runner exits.",
                    subject,
                    element.line,
                ))
            final_is_runner = bool(runners and runners[-1].runs)
            if len(stages) > runner_index + 1 and not final_is_runner and not status_preserved and not e1_fired:
                findings.append(Finding(
                    "E2b",
                    "The pipeline returns its last stage's status, not this runner's; run `set -o pipefail; "
                    + subject + "` (or check `${PIPESTATUS[0]}`) before claiming the result.",
                    subject,
                    element.line,
                ))
        if depth < MAX_RECURSION:
            for stage, words in zip(stages, words_by_stage):
                bodies = _substitution_bodies(stage) + _wrapper_bodies(stage, words)
                for body in bodies:
                    nested, nested_runner = _scan_text(body, depth + 1, element.line)
                    findings.extend(nested)
                    has_runner = has_runner or nested_runner
    return findings, has_runner


def analyze_command(command: str) -> List[Finding]:
    """Return E1/E2 findings for a command without logging or hook side effects."""
    findings, _ = _scan_text(command)
    _, escaped = _strip_comments(command)
    return [] if escaped else findings


def evaluate_command(command: str) -> Evaluation:
    """Evaluate one hook command, retaining the clean/escape log denominator."""
    findings, has_runner = _scan_text(command)
    _, escaped = _strip_comments(command)
    return Evaluation(tuple() if escaped else tuple(findings), has_runner, escaped)


def render(findings: Sequence[Finding], source: str = "command") -> str:
    """Render actionable, warn-only feedback for humans and model-visible adapters."""
    lines = ["bash-evidence-guard: {0} finding(s) in {1}".format(len(findings), source)]
    for finding in findings:
        lines.append("  [WARN] {0} (line {1}): {2}".format(
            finding.rule, finding.line, finding.detail))
    return "\n".join(lines)


def append_fire_log(command: str, evaluation: Evaluation, carrier: str, cwd: str) -> None:
    """Append the section-6 JSONL receipt; all filesystem failures are non-fatal."""
    if not evaluation.has_runner:
        return
    path = os.environ.get("BASH_EVIDENCE_GUARD_LOG")
    if not path:
        path = os.path.expanduser("~/.claude/logs/bash-evidence-guard.jsonl")
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "carrier": carrier,
        "cwd": cwd,
        "command": command,
        "rule": evaluation.rule,
        "decision": evaluation.decision,
    }
    try:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass  # A diagnostic receipt must never break a user's hook invocation.


def _payload_command(payload: object, allowed_tools: Sequence[str], casefold: bool = False) -> Tuple[str, str]:
    """Validate a synthetic/live hook payload's tool name and string command field."""
    if not isinstance(payload, dict):
        return "", ""
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str):
        return "", ""
    candidate = tool_name.lower() if casefold else tool_name
    allowed = {name.lower() for name in allowed_tools} if casefold else set(allowed_tools)
    if candidate not in allowed:
        return "", ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        return "", ""
    cwd = payload.get("cwd")
    return tool_input["command"], cwd if isinstance(cwd, str) else os.getcwd()


def _warn_json(evaluation: Evaluation, carrier: str) -> str:
    """Build the C1/C2-safe Claude/Codex warn shape: no permission decision."""
    body = render(evaluation.findings, "Bash command")
    return json.dumps({
        "systemMessage": "bash-evidence-guard (warn-only): {0} evidence-integrity finding(s)".format(
            len(evaluation.findings)),
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": body + "\n(warn-only: the command still follows the normal permission path; "
            "apply the corrected command above if the finding holds.)",
        },
    })


def hook_mode() -> int:
    """Claude PreToolUse adapter (SPEC §5 C1-C3): exact Bash, warn JSON, exit 0."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command, cwd = _payload_command(payload, ("Bash",))
    if not command:
        return 0
    evaluation = evaluate_command(command)
    append_fire_log(command, evaluation, "claude", cwd)
    if evaluation.findings:
        print(_warn_json(evaluation, "claude"))
    return 0


def codex_hook_mode() -> int:
    """Codex PreToolUse adapter (sol W1): exact Bash/tool_input.command, warn-only."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command, cwd = _payload_command(payload, ("Bash",))
    if not command:
        return 0
    evaluation = evaluate_command(command)
    append_fire_log(command, evaluation, "codex", cwd)
    if evaluation.findings:
        print(_warn_json(evaluation, "codex"))
    return 0


def kiro_hook_mode(deny: bool = False) -> int:
    """Kiro preToolUse adapter: warning stderr+1; a later deny policy is stderr+2.

    v1 calls this with ``deny=False``.  The optional branch encodes the verified
    §5 wire contract for a future tracked project deny without changing v1's
    warn-only rollout.
    """
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command, cwd = _payload_command(payload, tuple(KIRO_SHELL_TOOLS), casefold=True)
    if not command:
        return 0
    evaluation = evaluate_command(command)
    append_fire_log(command, evaluation, "kiro", cwd)
    if not evaluation.findings:
        return 0
    suffix = "(deny policy: command blocked; use the corrected command above.)" if deny else (
        "(warn-only: Kiro shows this to the user; the command proceeds.)")
    print(render(evaluation.findings, "Bash command") + "\n" + suffix, file=sys.stderr)
    return 2 if deny else 1


def _run_hook(fn, stdin_text: str, *args, **kwargs) -> Tuple[int, str, str]:
    """Run an adapter against synthetic stdin, matching brief_lint's self-test shape."""
    old_stdin = sys.stdin
    out, err = io.StringIO(), io.StringIO()
    try:
        sys.stdin = io.StringIO(stdin_text)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn(*args, **kwargs)
    finally:
        sys.stdin = old_stdin
    return rc, out.getvalue(), err.getvalue()


def self_test() -> int:
    """Exercise representative panel fixtures and all three corrected wire contracts."""
    cases = [
        ("tail E1", "cargo test 2>&1 | tail -25", ["E1"]),
        ("capture E2b", "cargo test >full.log 2>&1 | tail -25", ["E2b"]),
        ("stage association", "make test && git log --oneline | head -20", []),
        ("shell wrapper", 'bash -lc "pytest -q | tail -5"', ["E1"]),
        ("set-e sentinel", "set -eu\n( false )\nprintf 'PASS\\n'", ["E2a"]),
    ]
    failures = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        if not condition:
            failures += 1
        print("  {0}: {1}{2}".format("ok" if condition else "FAIL", name,
                                      " — " + detail if detail and not condition else ""))

    for name, command, expected in cases:
        got = [finding.rule for finding in analyze_command(command)]
        check(name, got == expected, "got={0!r} expected={1!r}".format(got, expected))

    payload = json.dumps({"tool_name": "Bash", "cwd": "/tmp", "tool_input": {
        "command": "pytest -q | tail -5"}})
    rc, out, err = _run_hook(hook_mode, payload)
    check("claude warn has additionalContext and no permissionDecision",
          rc == 0 and err == "" and "additionalContext" in out and "permissionDecision" not in out,
          "rc={0} out={1!r}".format(rc, out))
    rc, out, err = _run_hook(codex_hook_mode, payload)
    check("codex warn has additionalContext and no permissionDecision",
          rc == 0 and err == "" and "additionalContext" in out and "permissionDecision" not in out,
          "rc={0} out={1!r}".format(rc, out))
    kiro_payload = json.dumps({"tool_name": "execute_bash", "cwd": "/tmp", "tool_input": {
        "command": "pytest -q | tail -5"}})
    rc, out, err = _run_hook(kiro_hook_mode, kiro_payload)
    check("kiro warn is stderr plus exit 1", rc == 1 and out == "" and "E1" in err,
          "rc={0} err={1!r}".format(rc, err))
    rc, out, err = _run_hook(kiro_hook_mode, kiro_payload, deny=True)
    check("kiro deny wire is stderr plus exit 2", rc == 2 and out == "" and "E1" in err,
          "rc={0} err={1!r}".format(rc, err))
    for name, adapter in (("claude", hook_mode), ("codex", codex_hook_mode), ("kiro", kiro_hook_mode)):
        rc, out, err = _run_hook(adapter, "{not json")
        check(name + " malformed stdin is quiet", rc == 0 and out == "" and err == "",
              "rc={0} out={1!r} err={2!r}".format(rc, out, err))
    print("self-test:", "PASS" if failures == 0 else "{0} FAILURES".format(failures))
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="warn-only Bash test-evidence guard")
    parser.add_argument("--cmd", metavar="COMMAND", help="scan one command string")
    parser.add_argument("--hook", action="store_true", help="Claude Code PreToolUse hook mode")
    parser.add_argument("--codex-hook", action="store_true", help="Codex PreToolUse hook mode")
    parser.add_argument("--kiro-hook", action="store_true", help="Kiro preToolUse hook mode")
    parser.add_argument("--self-test", action="store_true", help="run embedded fixtures")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.hook:
        return hook_mode()
    if args.codex_hook:
        return codex_hook_mode()
    if args.kiro_hook:
        return kiro_hook_mode()
    if args.cmd is None:
        parser.error("--cmd COMMAND required unless --hook/--codex-hook/--kiro-hook/--self-test")
    evaluation = evaluate_command(args.cmd)
    append_fire_log(args.cmd, evaluation, "cmd", os.getcwd())
    if evaluation.findings:
        print(render(evaluation.findings))
    elif evaluation.escaped:
        print("bash-evidence-guard: escape accepted (logged)")
    else:
        print("bash-evidence-guard: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
