"""Provider wrapper around `codex exec` (the blind binary judge, a different
model family than the executor).

The prompt is piped in on stdin; the final agent message is written by the
CLI to a `-o` scratch file rather than parsed off stdout, since stdout only
carries the last message text while the full transcript (and the `tokens
used` line) is emitted on stderr. This module tolerates either stream for
`tokens used` in case that routing changes between codex-cli versions.
"""
import os
import re
import subprocess
import tempfile

from harness.providers.binpath import resolve_executable
from harness.providers.errors import ProviderError

_TOKENS_USED_RE = re.compile(r"tokens used\s*\n\s*([0-9,]+)", re.IGNORECASE)


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
) -> dict:
    """Run one `codex exec` turn (read-only sandbox) and return its result.

    Returns a dict with keys: output (str, the final agent message read back
    from the `-o` scratch file) and tokens_used (int | None, parsed from the
    `tokens used` line in the CLI's output if present).

    Raises ProviderError on timeout or nonzero exit. The error carries the
    tail of stderr.
    """
    fd, out_path = tempfile.mkstemp(suffix=".codex-output.txt")
    os.close(fd)
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
