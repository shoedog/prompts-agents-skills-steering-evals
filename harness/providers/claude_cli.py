"""Provider wrapper around `claude -p` (the weak executor arm).

No raw Anthropic API key exists on eval-harness machines: the executor is
always driven through the `claude` CLI in non-interactive print mode. This
module shells out once per call and parses the CLI's `--output-format json`
result object.

Token accounting: `input_tokens` in the returned dict is the SUM of the CLI's
`usage.input_tokens`, `usage.cache_creation_input_tokens`, and
`usage.cache_read_input_tokens` — i.e. total tokens processed for the call,
not just cache-miss tokens. The fixed CLI/harness overhead (system prompt,
tool schemas, etc.) is constant across experiment arms, so token/cost DELTAS
between arms still isolate the effect of the artifact under test even though
the absolute totals include that constant overhead.
"""
import json
import subprocess
import time

from harness.providers.binpath import resolve_executable
from harness.providers.errors import ProviderError

DISALLOWED_TOOLS = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Glob,Grep,Read,Task"


def _stderr_tail(text: str, n: int = 4000) -> str:
    if not text:
        return ""
    return text[-n:]


def run_claude(prompt: str, model: str, cwd: str, timeout: int = 300) -> dict:
    """Run one `claude -p` turn and return its parsed result.

    Returns a dict with keys: output (str), input_tokens (int),
    output_tokens (int), cost_usd (float), duration_ms (int), raw (dict, the
    full parsed CLI JSON object).

    Raises ProviderError on timeout, nonzero exit, unparseable stdout, or a
    CLI-reported `is_error`. The error carries the tail of stderr.
    """
    argv = [
        resolve_executable("claude"),
        "-p",
        prompt,
        "--model",
        model,
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disallowedTools",
        DISALLOWED_TOOLS,
    ]

    # stdin=DEVNULL: without it the CLI waits 3s probing an inherited pipe
    # (promptfoo runs us with one) and logs a stderr warning. One retry on
    # nonzero exit: transient rc-1 blips under load cost a whole arm's
    # integrity otherwise (observed: rh-07/rh-14, exp-d7 treatment arm).
    proc = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as e:
            raise ProviderError(
                f"claude CLI timed out after {timeout}s",
                stderr_tail=_stderr_tail(getattr(e, "stderr", None)),
            ) from e
        except OSError as e:
            raise ProviderError(
                f"claude CLI failed to start: {e}",
            ) from e
        if proc.returncode == 0:
            break
        if attempt == 1:
            time.sleep(3)

    if proc.returncode != 0:
        raise ProviderError(
            f"claude CLI exited with code {proc.returncode} (after retry)",
            stderr_tail=_stderr_tail(proc.stderr),
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ProviderError(
            f"claude CLI stdout was not valid JSON: {e}",
            stderr_tail=_stderr_tail(proc.stderr),
        ) from e

    if not isinstance(data, dict):
        raise ProviderError(
            f"claude CLI stdout was valid JSON but not an object (got {type(data).__name__})",
            stderr_tail=_stderr_tail(proc.stderr),
        )

    if data.get("is_error"):
        raise ProviderError(
            "claude CLI reported is_error=true",
            stderr_tail=_stderr_tail(proc.stderr),
        )

    usage = data.get("usage", {})
    input_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )

    return {
        "output": data.get("result", ""),
        "input_tokens": input_tokens,
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": data.get("total_cost_usd", 0.0),
        "duration_ms": data.get("duration_ms", 0),
        "raw": data,
    }
