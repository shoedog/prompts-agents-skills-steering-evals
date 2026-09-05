"""Content identity for structured evaluation stage cache entries."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from harness.structured.results import canonical_json


def cache_key(
    stage_type: str,
    provider_version: str,
    model: str,
    task_version: str,
    prompt_sha256: str,
    seed: int,
    sample: int,
    input_sha256: Mapping[str, str],
) -> str:
    identity = {
        "stage_type": stage_type,
        "provider_version": provider_version,
        "model": model,
        "task_version": task_version,
        "prompt_sha256": prompt_sha256,
        "seed": seed,
        "sample": sample,
        "input_sha256": dict(sorted(input_sha256.items())),
    }
    return hashlib.sha256(canonical_json(identity)).hexdigest()
