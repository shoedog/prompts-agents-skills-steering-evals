from __future__ import annotations

import json

import pytest

from harness.structured.asserts import AssertResult, get, register, run_asserts
from harness.structured.asserts.consistency import consistency_assert
from harness.structured.asserts.cost_latency import cost_latency_assert
from harness.structured.asserts.evidence import evidence_assert
from harness.structured.asserts.label import label_assert
from harness.structured.asserts.schema import schema_assert


@pytest.fixture
def cfg():
    return {
        "response_schema": {
            "type": "object",
            "required": ["class", "confidence", "rationale"],
            "additionalProperties": False,
            "properties": {
                "class": {"enum": ["correct", "swallowed_fatal", "unclear"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
                "evidence_lines": {"type": "array", "items": {"type": "integer"}},
            },
        },
        "classes": ["correct", "unclear", "swallowed_fatal"],
        "samples_per_item": 3,
    }


@pytest.fixture
def item():
    class FixtureItem:
        expected = {
            "label": "swallowed_fatal",
            "rationale_must_mention": ["HTTPError", "None"],
            "evidence_lines_subset": [118, 119, 121],
        }
        raw = {"id": "eh-py-0042"}

    return FixtureItem()


def _valid_output():
    return {
        "class": "swallowed_fatal",
        "confidence": 0.8,
        "rationale": "HTTPError returned None",
        "evidence_lines": [118, 119, 121],
    }


def test_registry_rejects_duplicate_and_unknown_names():
    with pytest.raises(KeyError, match="unknown assert type 'missing'"):
        get("missing")
    with pytest.raises(KeyError, match="duplicate assert type 'schema'"):
        register("schema")(
            lambda **kwargs: AssertResult("schema", True, True, 1.0, "valid")
        )


@pytest.mark.parametrize(
    "raw, detail",
    [
        ("not json", "output is not JSON"),
        ('{"class":"not-a-class","confidence":0.5,"rationale":"x"}', "schema error"),
        ('{"class":"correct","confidence":1.4,"rationale":"x"}', "schema error"),
    ],
)
def test_schema_assert_keeps_invalid_outputs_as_hard_failures(cfg, item, raw, detail):
    output = None if raw == "not json" else json.loads(raw)
    result = schema_assert(
        output=output,
        raw=raw,
        expected=item.expected,
        item=item.raw,
        cfg=cfg,
        samples=None,
    )
    assert (result.passed, result.hard, result.score) == (False, True, 0.0)
    assert detail in result.detail


def test_schema_assert_accepts_selected_schema(cfg, item):
    output = _valid_output()
    result = schema_assert(
        output=output,
        raw=json.dumps(output),
        expected=item.expected,
        item=item.raw,
        cfg=cfg,
        samples=None,
    )
    assert result == AssertResult("schema", True, True, 1.0, "valid")


def test_schema_assert_resolves_checked_path_and_pointer(tmp_path, cfg, item):
    path = tmp_path / "response.schema.json"
    path.write_text(json.dumps({"$defs": {"response": cfg["response_schema"]}}))
    output = _valid_output()
    result = schema_assert(
        output=output,
        raw=json.dumps(output),
        expected=item.expected,
        item=item.raw,
        cfg={
            "response_schema_path": path,
            "response_schema_pointer": "$defs/response",
        },
        samples=None,
    )
    assert result == AssertResult("schema", True, True, 1.0, "valid")


def test_label_exact_and_ordinal_distance(cfg, item):
    exact = label_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "mode": "exact", "field": "class"},
        samples=None,
    )
    near = label_assert(
        output={**_valid_output(), "class": "unclear"},
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "mode": "ordinal", "field": "class", "tolerance": 1},
        samples=None,
    )
    far = label_assert(
        output={**_valid_output(), "class": "correct"},
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "mode": "ordinal", "field": "class", "tolerance": 1},
        samples=None,
    )
    assert (exact.passed, near.passed, far.passed) == (True, True, False)
    assert "ordinal distance 2 exceeds tolerance 1" in far.detail


def test_label_ordinal_rejects_value_absent_from_class_order(cfg, item):
    result = label_assert(
        output={**_valid_output(), "class": "not-declared"},
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "mode": "ordinal", "field": "class", "tolerance": 1},
        samples=None,
    )
    assert result.passed is False
    assert "not in declared class order" in result.detail


def test_evidence_requires_all_minimum_lines_and_rationale_terms(cfg, item):
    output = {
        "class": "swallowed_fatal",
        "confidence": 0.8,
        "rationale": "HTTPError returned None",
        "evidence_lines": [118, 121],
    }
    result = evidence_assert(
        output=output,
        raw=json.dumps(output),
        expected=item.expected,
        item=item.raw,
        cfg=cfg,
        samples=None,
    )
    assert result.passed is False
    assert "missing evidence lines: [119]" in result.detail


def test_evidence_regex_is_case_sensitive_and_all_terms_are_required(cfg, item):
    output = {**_valid_output(), "rationale": "httperror returned a value"}
    result = evidence_assert(
        output=output,
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg=cfg,
        samples=None,
    )
    assert result.passed is False
    assert "missing rationale terms: ['HTTPError', 'None']" in result.detail


def test_consistency_uses_modal_label_share_and_threshold(cfg, item):
    samples = [
        {"output": {"class": "correct"}},
        {"output": {"class": "correct"}},
        {"output": {"class": "unclear"}},
    ]
    passing = consistency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "threshold": 2 / 3}, samples=samples,
    )
    failing = consistency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "threshold": 0.67}, samples=samples,
    )
    assert (passing.passed, passing.score) == (True, pytest.approx(2 / 3))
    assert failing.passed is False


def test_consistency_requires_multiple_samples(cfg, item):
    result = consistency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "samples_per_item": 1, "threshold": 0.5},
        samples=[{"output": _valid_output()}],
    )
    assert result.passed is False
    assert result.score is None
    assert "requires samples_per_item > 1" in result.detail


def test_cost_latency_checks_each_call_cost_and_p95_latency(cfg, item):
    samples = [
        {"cost_usd": 0.01, "duration_ms": duration}
        for duration in [10, 20, 30, 40, 50]
    ]
    passing = cost_latency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "max_usd_per_call": 0.01, "max_p95_ms": 50}, samples=samples,
    )
    samples[2]["cost_usd"] = 0.02
    failing = cost_latency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "max_usd_per_call": 0.01, "max_p95_ms": 45}, samples=samples,
    )
    assert passing.passed is True
    assert failing.passed is False
    assert "cost_usd 0.02 exceeds 0.01" in failing.detail
    assert "p95 duration_ms 50 exceeds 45" in failing.detail


def test_run_asserts_marks_semantics_not_applicable_after_schema_failure(cfg, item):
    results = run_asserts(
        output=None,
        raw="not json",
        expected=item.expected,
        item=item.raw,
        cfg={
            **cfg,
            "asserts": [
                {"type": "schema", "hard": True},
                {"type": "label", "mode": "exact", "field": "class"},
                {"type": "evidence"},
            ],
        },
        samples=None,
    )
    assert results[0].passed is False and results[0].hard is True
    assert [(result.name, result.passed, result.score, result.detail) for result in results[1:]] == [
        ("label", False, None, "not_applicable: hard schema failure"),
        ("evidence", False, None, "not_applicable: hard schema failure"),
    ]


def test_run_asserts_dispatches_configured_asserts(cfg, item):
    output = _valid_output()
    results = run_asserts(
        output=output,
        raw=json.dumps(output),
        expected=item.expected,
        item=item.raw,
        cfg={
            **cfg,
            "asserts": [
                {"type": "schema", "hard": True},
                {"type": "label", "mode": "exact", "field": "class"},
                {"type": "evidence"},
            ],
        },
        samples=None,
    )
    assert [result.name for result in results] == ["schema", "label", "evidence"]
    assert all(result.passed for result in results)
