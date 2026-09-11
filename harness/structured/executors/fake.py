"""Content-addressed in-process executor fake for structured runner tests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Mapping

from .base import ExecutionRequest, ExecutionResult, LlmRunEnvelope


def _canonical_request_sha256(path: Path) -> str:
    value = json.loads(path.read_text())
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class FakeExecutor:
    """Return exact configured envelopes selected by canonical request hash."""

    def __init__(self, envelopes: Mapping[str, LlmRunEnvelope]) -> None:
        self._envelopes = {key: deepcopy(value) for key, value in envelopes.items()}
        self._requests: list[ExecutionRequest] = []

    @property
    def requests(self) -> tuple[ExecutionRequest, ...]:
        return tuple(self._requests)

    def run(self, request: ExecutionRequest) -> ExecutionResult:
        self._requests.append(request)
        key = _canonical_request_sha256(request.request_file)
        envelope = deepcopy(self._envelopes[key])
        raw_stdout = json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
        return ExecutionResult(envelope=envelope, raw_stdout=raw_stdout, returncode=0)
