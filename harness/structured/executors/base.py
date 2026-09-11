"""Stable execution seam shared by structured-eval stage executors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from typing_extensions import TypedDict


class LlmUsage(TypedDict, closed=True):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


class LlmRunEnvelope(TypedDict, closed=True):
    schema_version: Literal["1"]
    invocation_id: str
    task: str
    task_version: str
    provider: str
    model: str
    provider_version: str
    prompt_sha256: str
    escalation_state: str
    first_tier_valid: bool | None
    first_tier_sentinel: bool | None
    final_sentinel: bool
    cache_hit: bool
    usage: LlmUsage
    cost_usd: float
    response: dict[str, Any]
    log_path: str


@dataclass(frozen=True)
class ExecutionRequest:
    task: str
    task_version: str
    request_file: Path
    model: str
    seed: int
    sample: int
    scratch_dir: Path


@dataclass(frozen=True)
class ExecutionResult:
    envelope: LlmRunEnvelope
    raw_stdout: str
    returncode: int


class Executor(Protocol):
    def run(self, request: ExecutionRequest) -> ExecutionResult: ...


class ExecutorError(Exception):
    """The child could not produce a successful envelope."""

    def __init__(
        self,
        returncode: int,
        stdout_tail: str = "",
        stderr_tail: str = "",
        message: str | None = None,
    ) -> None:
        self.returncode = returncode
        self.stdout_tail = stdout_tail
        self.stderr_tail = stderr_tail
        super().__init__(message or f"llm-layer exited with code {returncode}")


class _EnvelopeError(Exception):
    def __init__(self, message: str, stdout_tail: str = "", stderr_tail: str = "") -> None:
        self.stdout_tail = stdout_tail
        self.stderr_tail = stderr_tail
        super().__init__(message)


class EnvelopeContractError(_EnvelopeError):
    """A decoded object did not satisfy the vendored producer contract."""

    def __init__(
        self,
        json_path: str,
        validator: str,
        message: str,
        stdout_tail: str = "",
        stderr_tail: str = "",
    ) -> None:
        self.json_path = json_path
        self.validator = validator
        self.message = message
        super().__init__(
            f"envelope contract violation at {json_path} ({validator}): {message}",
            stdout_tail,
            stderr_tail,
        )


class EnvelopeStdoutError(_EnvelopeError):
    """Stdout was not exactly one JSON object followed by one newline."""


class EnvelopeEchoError(_EnvelopeError):
    """A validated envelope did not echo the submitted request identity."""

    def __init__(
        self,
        field: str,
        expected: object,
        actual: object,
        stdout_tail: str = "",
        stderr_tail: str = "",
    ) -> None:
        self.field = field
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"envelope echo mismatch for {field}: expected {expected!r}, got {actual!r}",
            stdout_tail,
            stderr_tail,
        )
