from __future__ import annotations

import hashlib
import json

import pytest

from harness.structured.cache import cache_key


BASE = {
    "stage_type": "llm",
    "provider_version": "llm-layer 0.3.1",
    "model": "fake-model",
    "task_version": "2026-09-04.1",
    "prompt_sha256": "a" * 64,
    "seed": 20260904,
    "sample": 2,
    "input_sha256": {"target": "b" * 64, "observation": "c" * 64},
}


def test_cache_key_is_sha256_of_the_exact_canonical_identity():
    identity = {
        "stage_type": "llm",
        "provider_version": "llm-layer 0.3.1",
        "model": "fake-model",
        "task_version": "2026-09-04.1",
        "prompt_sha256": "a" * 64,
        "seed": 20260904,
        "sample": 2,
        "input_sha256": {"observation": "c" * 64, "target": "b" * 64},
    }
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert cache_key(**BASE) == hashlib.sha256(encoded).hexdigest()


def test_cache_key_is_independent_of_input_mapping_order():
    reordered = dict(BASE)
    reordered["input_sha256"] = {
        "observation": "c" * 64,
        "target": "b" * 64,
    }
    assert cache_key(**BASE) == cache_key(**reordered)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("stage_type", "prism"),
        ("provider_version", "llm-layer 0.3.2"),
        ("model", "other-model"),
        ("task_version", "2026-09-05.1"),
        ("prompt_sha256", "d" * 64),
        ("seed", 20260905),
        ("sample", 3),
        ("input_sha256", {"target": "b" * 64, "observation": "e" * 64}),
    ],
)
def test_every_cache_identity_field_changes_the_key(field, replacement):
    changed = dict(BASE)
    changed[field] = replacement
    assert cache_key(**changed) != cache_key(**BASE)
