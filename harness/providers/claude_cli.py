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
import os
import subprocess
import time

from harness.providers.binpath import resolve_executable
from harness.providers.errors import ProviderError

DISALLOWED_TOOLS = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Glob,Grep,Read,Task,Skill"

# Executor children must NOT inherit the operator's user-global settings: the
# SessionStart hook there (moshi-hooks/superpowers) injects framework context
# that overrides terse instructions — observed destroying 3/7 fixed-token
# probes in the ssot dogfood corpus (2026-07-25, slice-D FAILURE-1). Skill is
# disallowed above as belt for the same incident.
#
# CAVEAT (falsified 2026-07-26, exp-w3a run 2 transcripts): `--settings` ADDS a
# settings source; it does not replace the user-global one — PostToolUse hooks
# from ~/.claude/settings.json were observed firing inside executor children.
# The real severs are (a) CLAUDE_INSTRUMENT_CHILD=1 in the child env, which the
# operator's guarded SessionStart hook keys on, and (b) `--tools ""` below,
# which removes the built-in tool surface entirely.
ISOLATED_SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isolated_settings.json")


def _stderr_tail(text: "str | None", n: int = 4000) -> str:
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
        "--settings",
        ISOLATED_SETTINGS,
        # No tools AT ALL: with --max-turns 1, ANY tool interaction (even a
        # denied one, even ToolSearch loading a deferred tool) ends the run as
        # max_turns_reached with no result -> CLI exit 1 with empty stderr.
        # Observed killing 2/28 executor calls in exp-w3a run 2 (2026-07-26):
        # sonnet-5 stochastically reached for ToolSearch/DesignSync on review
        # prompts. "" removes the whole built-in tool surface, so turn 1 always
        # ends in text. The disallowed list above stays as belt.
        "--tools",
        "",
    ]

    # stdin=DEVNULL: without it the CLI waits 3s probing an inherited pipe
    # (promptfoo runs us with one) and logs a stderr warning. One retry on
    # nonzero exit: transient rc-1 blips under load cost a whole arm's
    # integrity otherwise (observed: rh-07/rh-14, exp-d7 treatment arm).
    # CLAUDE_INSTRUMENT_CHILD keys the guard on the operator's SessionStart
    # hook — the one hook event --settings does NOT sever (see CAVEAT above).
    child_env = {**os.environ, "CLAUDE_INSTRUMENT_CHILD": "1"}
    proc = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL, env=child_env,
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
        # The CLI reports many failures (e.g. error_max_turns) as a JSON result
        # object on STDOUT with an empty stderr — carry a stdout tail in the
        # message or the error is a bare exit code (exp-w3a run 2, 2026-07-26).
        raise ProviderError(
            f"claude CLI exited with code {proc.returncode} (after retry);"
            f" stdout tail: {_stderr_tail(proc.stdout, 1500)!r}",
            stderr_tail=_stderr_tail(proc.stderr),
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ProviderError(
            f"claude CLI stdout was not valid JSON: {e};"
            f" stdout tail: {_stderr_tail(proc.stdout, 1500)!r}",
            stderr_tail=_stderr_tail(proc.stderr),
        ) from e

    if not isinstance(data, dict):
        raise ProviderError(
            f"claude CLI stdout was valid JSON but not an object (got {type(data).__name__})",
            stderr_tail=_stderr_tail(proc.stderr),
        )

    if data.get("is_error"):
        raise ProviderError(
            "claude CLI reported is_error=true;"
            f" result tail: {_stderr_tail(str(data.get('result', '')), 1500)!r}",
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
