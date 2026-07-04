"""Provider wrapper around `codex exec` (the blind binary judge, a different
model family than the executor).

The prompt is piped in on stdin; the final agent message is written by the
CLI to a `-o` scratch file rather than parsed off stdout, since stdout only
carries the last message text while the full transcript (and the `tokens
used` line) is emitted on stderr. This module tolerates either stream for
`tokens used` in case that routing changes between codex-cli versions.

Judge blinding is only a prompt-level contract unless it also holds at the
process level: `run_codex` therefore never lets the child inherit the
caller's cwd (the repo root at eval-run time, which contains the results/
and tasksets/ ground-truth files). See the `cwd` parameter below.
"""
import os
import re
import shutil
import subprocess
import tempfile

from harness.providers.binpath import resolve_executable
from harness.providers.errors import ProviderError

_TOKENS_USED_RE = re.compile(r"tokens used\s*\n\s*([0-9,]+)", re.IGNORECASE)

# `effort` is interpolated, unescaped, straight into a TOML value literal
# (`model_reasoning_effort="{effort}"` below, passed via `-c`). A value
# containing a `"` (or a newline) could close that string early and inject
# additional `-c` config keys into the codex CLI invocation. Rather than
# denylist just `"`/newline, allowlist to lowercase letters only — every
# real effort value (low/medium/high, ...) matches this, and it closes the
# injection vector categorically rather than one escape sequence at a time.
_EFFORT_RE = re.compile(r"[a-z]+")


def _stderr_tail(text: str, n: int = 4000) -> str:
    if not text:
        return ""
    return text[-n:]


def _parse_tokens_used(*streams: str) -> int | None:
    for stream in streams:
        if not stream:
            continue
        m = _TOKENS_USED_RE.search(stream)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def run_codex(
    prompt: str,
    schema_path: str | None = None,
    model: str = "gpt-5.5",
    effort: str = "medium",
    timeout: int = 300,
    cwd: str | None = None,
) -> dict:
    """Run one `codex exec` turn (read-only sandbox) and return its result.

    `cwd` is where the `codex exec` child process is launched — NEVER the
    caller's own cwd (repo root at eval-run time) by default, since that
    would let the "blind" judge process read repo/results/truth files off
    the filesystem even though it never sees them in its prompt. If `cwd` is
    omitted, a fresh empty directory is created for this call alone and
    removed again in `finally`. If `cwd` IS given (e.g. judge.py passing a
    `results_dir/judge_scratch` path it manages across calls), it is created
    if missing and left in place afterward — this function only cleans up
    a scratch directory it created itself.

    Returns a dict with keys: output (str, the final agent message read back
    from the `-o` scratch file) and tokens_used (int | None, parsed from the
    `tokens used` line in the CLI's output if present).

    Raises ProviderError on timeout or nonzero exit. The error carries the
    tail of stderr.
    """
    if not _EFFORT_RE.fullmatch(effort):
        raise ProviderError(
            f"invalid effort value {effort!r}: must match {_EFFORT_RE.pattern} "
            "(it is interpolated unescaped into a TOML config value)"
        )

    fd, out_path = tempfile.mkstemp(suffix=".codex-output.txt")
    os.close(fd)

    owns_scratch_dir = cwd is None
    scratch_dir = (
        tempfile.mkdtemp(prefix="codex-judge-scratch-") if owns_scratch_dir else cwd
    )
    if not owns_scratch_dir:
        os.makedirs(scratch_dir, exist_ok=True)

    try:
        argv = [
            resolve_executable("codex"),
            "exec",
            "--sandbox",
            "read-only",
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-o",
            out_path,
        ]
        if schema_path:
            argv += ["--output-schema", schema_path]
        argv.append("-")

        try:
            proc = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=scratch_dir,
            )
        except subprocess.TimeoutExpired as e:
            raise ProviderError(
                f"codex CLI timed out after {timeout}s",
                stderr_tail=_stderr_tail(getattr(e, "stderr", None)),
            ) from e
        except OSError as e:
            raise ProviderError(
                f"codex CLI failed to start: {e}",
            ) from e

        if proc.returncode != 0:
            raise ProviderError(
                f"codex CLI exited with code {proc.returncode}",
                stderr_tail=_stderr_tail(proc.stderr),
            )

        try:
            with open(out_path, "r") as f:
                output = f.read()
        except OSError as e:
            raise ProviderError(
                f"codex CLI did not write an output file: {e}",
                stderr_tail=_stderr_tail(proc.stderr),
            ) from e

        tokens_used = _parse_tokens_used(proc.stderr, proc.stdout)

        return {"output": output, "tokens_used": tokens_used}
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
        if owns_scratch_dir:
            shutil.rmtree(scratch_dir, ignore_errors=True)
