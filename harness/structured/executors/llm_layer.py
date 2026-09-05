"""Subprocess consumer for the normative ``llm-layer run --json`` envelope."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator

from harness.providers.binpath import resolve_executable

from .base import (
    EnvelopeContractError,
    EnvelopeEchoError,
    EnvelopeStdoutError,
    ExecutionRequest,
    ExecutionResult,
    ExecutorError,
    LlmRunEnvelope,
)


_TAIL_LENGTH = 4000
_DEFAULT_SCHEMA = Path(__file__).resolve().parents[3] / "contracts" / "llm_run_envelope.schema.json"


def _tail(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return (value or "")[-_TAIL_LENGTH:]


def _json_path(parts) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value}")


class LlmLayerExecutor:
    def __init__(
        self,
        binary: str | Path | None = None,
        timeout_seconds: int = 300,
        schema_path: Path = _DEFAULT_SCHEMA,
    ) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema)

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        executable = str(self.binary) if self.binary is not None else resolve_executable("llm-layer")
        argv = [
            executable,
            "run",
            "--task",
            request.task,
            "--task-version",
            request.task_version,
            "--request-file",
            str(request.request_file),
            "--model",
            request.model,
            "--seed",
            str(request.seed),
            "--json",
        ]
        try:
            proc = subprocess.run(
                argv,
                cwd=request.scratch_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ExecutorError(
                -1,
                _tail(error.stdout),
                _tail(error.stderr),
                f"llm-layer timed out after {self.timeout_seconds}s",
            ) from error
        except OSError as error:
            raise ExecutorError(-1, message=f"llm-layer failed to start: {error}") from error

        stdout_tail = _tail(proc.stdout)
        stderr_tail = _tail(proc.stderr)
        if proc.returncode != 0:
            raise ExecutorError(proc.returncode, stdout_tail, stderr_tail)

        envelope_object = self._decode_stdout(proc.stdout, stdout_tail, stderr_tail)
        errors = sorted(
            self._validator.iter_errors(envelope_object),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            error = errors[0]
            raise EnvelopeContractError(
                _json_path(error.path),
                str(error.validator),
                error.message,
                stdout_tail,
                stderr_tail,
            )

        for field, expected in (
            ("task", request.task),
            ("task_version", request.task_version),
            ("model", request.model),
        ):
            actual = envelope_object[field]
            if actual != expected:
                raise EnvelopeEchoError(
                    field,
                    expected,
                    actual,
                    stdout_tail,
                    stderr_tail,
                )

        envelope = cast(LlmRunEnvelope, envelope_object)
        return ExecutionResult(envelope=envelope, raw_stdout=proc.stdout, returncode=proc.returncode)

    @staticmethod
    def _decode_stdout(stdout: str, stdout_tail: str, stderr_tail: str) -> dict:
        if not stdout.endswith("\n") or stdout.endswith("\n\n"):
            raise EnvelopeStdoutError(
                "llm-layer stdout must end with exactly one newline",
                stdout_tail,
                stderr_tail,
            )
        serialized = stdout[:-1]
        try:
            value, end = json.JSONDecoder(parse_constant=_reject_json_constant).raw_decode(
                serialized
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise EnvelopeStdoutError(
                f"llm-layer stdout was not one JSON object: {error}",
                stdout_tail,
                stderr_tail,
            ) from error
        if end != len(serialized):
            raise EnvelopeStdoutError(
                "llm-layer stdout contained data after the JSON object",
                stdout_tail,
                stderr_tail,
            )
        if not isinstance(value, dict):
            raise EnvelopeStdoutError(
                f"llm-layer stdout JSON must be an object, got {type(value).__name__}",
                stdout_tail,
                stderr_tail,
            )
        return value
