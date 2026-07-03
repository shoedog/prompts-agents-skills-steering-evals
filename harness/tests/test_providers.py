"""Tests for the CLI-wrapping model providers.

All tests here mock subprocess.run — no live `claude` or `codex` process is
ever spawned by pytest. Live smoke calls are run manually outside pytest
(see task-4-report.md).
"""
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from harness.providers.claude_cli import run_claude
from harness.providers.codex_cli import run_codex
from harness.providers.errors import ProviderError

# The real shape of `claude -p ... --output-format json` stdout.
CANNED_CLAUDE_JSON = {
    "type": "result",
    "result": "OK",
    "total_cost_usd": 0.019,
    "usage": {
        "input_tokens": 9,
        "cache_creation_input_tokens": 8269,
        "cache_read_input_tokens": 17209,
        "output_tokens": 210,
    },
    "duration_ms": 3759,
}


def _completed(stdout="", stderr="", returncode=0):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


class TestRunClaude:
    def test_parses_canned_result(self):
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.return_value = _completed(stdout=json.dumps(CANNED_CLAUDE_JSON))
            result = run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp")

        assert result["output"] == "OK"
        # input_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
        assert result["input_tokens"] == 9 + 8269 + 17209
        assert result["output_tokens"] == 210
        assert result["cost_usd"] == 0.019
        assert result["duration_ms"] == 3759
        assert result["raw"] == CANNED_CLAUDE_JSON

    def test_argv_contains_required_flags(self):
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.return_value = _completed(stdout=json.dumps(CANNED_CLAUDE_JSON))
            run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp")

        argv = mock_run.call_args.args[0]
        assert "--output-format" in argv
        assert argv[argv.index("--output-format") + 1] == "json"
        assert "--disallowedTools" in argv
        assert "--max-turns" in argv
        assert "--strict-mcp-config" in argv
        assert "--mcp-config" in argv

    def test_timeout_raises_provider_error(self):
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["claude"], timeout=300)
            with pytest.raises(ProviderError):
                run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp", timeout=300)

    def test_is_error_raises_provider_error_with_stderr_tail(self):
        payload = dict(CANNED_CLAUDE_JSON, is_error=True)
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.return_value = _completed(
                stdout=json.dumps(payload), stderr="some failure detail"
            )
            with pytest.raises(ProviderError) as exc_info:
                run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp")
        assert "some failure detail" in exc_info.value.stderr_tail

    def test_nonzero_returncode_raises_provider_error(self):
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.return_value = _completed(
                stdout="", stderr="boom", returncode=1
            )
            with pytest.raises(ProviderError) as exc_info:
                run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp")
        assert "boom" in exc_info.value.stderr_tail

    def test_unparseable_json_raises_provider_error(self):
        with patch("harness.providers.claude_cli.subprocess.run") as mock_run:
            mock_run.return_value = _completed(stdout="not json", stderr="")
            with pytest.raises(ProviderError):
                run_claude("hi", "claude-haiku-4-5-20251001", cwd="/tmp")


class TestRunCodex:
    def _mock_run_writing_output_file(self, stdout_extra="", stderr="", returncode=0,
                                       last_message="OK"):
        def side_effect(argv, **kwargs):
            out_path = argv[argv.index("-o") + 1]
            with open(out_path, "w") as f:
                f.write(last_message)
            return _completed(stdout=stdout_extra, stderr=stderr, returncode=returncode)
        return side_effect

    def test_parses_output_and_tokens_used(self):
        stdout = (
            "codex\nOK\ntokens used\n7,004\n"
        )
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(stdout_extra=stdout)
            result = run_codex("Reply with exactly: OK")

        assert result["output"] == "OK"
        assert result["tokens_used"] == 7004

    def test_tokens_used_absent_is_none(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(stdout_extra="codex\nOK\n")
            result = run_codex("Reply with exactly: OK")

        assert result["output"] == "OK"
        assert result["tokens_used"] is None

    def test_argv_contains_required_flags(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(stdout_extra="tokens used\n1\n")
            run_codex("hi", model="gpt-5.5", effort="medium")

        argv = mock_run.call_args.args[0]
        assert argv[0] == "codex"
        assert argv[1] == "exec"
        assert "--sandbox" in argv
        assert argv[argv.index("--sandbox") + 1] == "read-only"
        assert "--model" in argv
        assert argv[argv.index("--model") + 1] == "gpt-5.5"
        assert "-c" in argv
        assert argv[argv.index("-c") + 1] == 'model_reasoning_effort="medium"'
        assert "-o" in argv
        assert argv[-1] == "-"

    def test_schema_path_included_when_given(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(stdout_extra="tokens used\n1\n")
            run_codex("hi", schema_path="/tmp/schema.json")

        argv = mock_run.call_args.args[0]
        assert "--output-schema" in argv
        assert argv[argv.index("--output-schema") + 1] == "/tmp/schema.json"

    def test_schema_path_omitted_when_not_given(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(stdout_extra="tokens used\n1\n")
            run_codex("hi")

        argv = mock_run.call_args.args[0]
        assert "--output-schema" not in argv

    def test_timeout_raises_provider_error(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["codex"], timeout=300)
            with pytest.raises(ProviderError):
                run_codex("hi", timeout=300)

    def test_nonzero_returncode_raises_provider_error(self):
        with patch("harness.providers.codex_cli.subprocess.run") as mock_run:
            mock_run.side_effect = self._mock_run_writing_output_file(
                stderr="codex boom", returncode=1
            )
            with pytest.raises(ProviderError) as exc_info:
                run_codex("hi")
        assert "codex boom" in exc_info.value.stderr_tail
