from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_llm_run_envelope_contract_is_pinned_and_valid():
    path = REPO_ROOT / "contracts/llm_run_envelope.schema.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "1219f167faa80fb65d128f4258c5525904aaa9d7d1c2cec25b587b4861f917c8"
    )
    Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_all_vendored_contracts_are_valid_draft_2020_12():
    for name in (
        "targets.schema.json",
        "observations.schema.json",
        "classify_error_handling.schema.json",
        "taskset_v2.schema.json",
    ):
        Draft202012Validator.check_schema(json.loads((REPO_ROOT / "contracts" / name).read_text()))
