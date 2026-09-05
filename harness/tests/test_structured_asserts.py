from __future__ import annotations

import json

import pytest

from harness.structured.asserts import (
    AssertConfigError,
    AssertResult,
    Population,
    get,
    register,
    run_asserts,
)
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
        raw = {
            "id": "eh-py-0042",
            "rendered_slice": {
                "text": "118: try request\n119: except HTTPError\n121: return None\n",
                "rendered_line_numbers": [118, 119, 121],
            },
        }

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


def test_evidence_rejects_citations_outside_rendered_slice(cfg, item):
    output = {
        **_valid_output(),
        "evidence_lines": [11, 999],
    }
    expected = {**item.expected, "evidence_lines_subset": [11]}
    rendered_item = {
        **item.raw,
        "rendered_slice": {
            "text": "11: return client.fetch()\n",
            "rendered_line_numbers": [11],
        },
    }
    result = evidence_assert(
        output=output,
        raw=json.dumps(output),
        expected=expected,
        item=rendered_item,
        cfg=cfg,
        samples=None,
    )
    assert result.passed is False
    assert "citations outside rendered slice: [999]" in result.detail


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
        {
            "item_id": "item-a",
            "version": "v1",
            "cost_usd": 0.01,
            "duration_ms": duration,
        }
        for duration in [10, 20, 30, 40, 50]
    ]
    passing = cost_latency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "population": "per_item", "max_usd_per_call": 0.01, "max_p95_ms": 50},
        samples=samples, population=Population("per_item", 1, 5),
    )
    samples[2]["cost_usd"] = 0.02
    failing = cost_latency_assert(
        output=_valid_output(), raw="", expected=item.expected, item=item.raw,
        cfg={**cfg, "population": "per_item", "max_usd_per_call": 0.01, "max_p95_ms": 45},
        samples=samples, population=Population("per_item", 1, 5),
    )
    assert passing.passed is True
    assert failing.passed is False
    assert "cost_usd 0.02 exceeds 0.01" in failing.detail
    assert "p95 duration_ms 50 exceeds 45" in failing.detail


def test_run_population_requires_descriptor_instead_of_using_fast_item_samples(cfg, item):
    result = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "run", "max_p95_ms": 100},
        samples=[{"cost_usd": 0.001, "duration_ms": 10}],
    )
    assert result.passed is False
    assert result.detail == "population descriptor required for declared 'run' population"


def test_run_population_rejects_per_item_descriptor_and_includes_slow_call(cfg, item):
    fast = [{"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 10}]
    wrong_population = Population(kind="per_item", item_count=1, sample_count=1)
    mismatch = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "run", "max_p95_ms": 100},
        samples=fast,
        population=wrong_population,
    )
    assert mismatch.passed is False
    assert mismatch.detail == "population mismatch: declared 'run', got 'per_item'"

    run_samples = [
        *fast,
        {"item_id": "item-b", "version": "v1", "cost_usd": 0.001, "duration_ms": 1_000},
    ]
    run_population = Population(kind="run", item_count=2, sample_count=2)
    result = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "run", "max_p95_ms": 100},
        samples=run_samples,
        population=run_population,
    )
    assert result.passed is False
    assert "p95 duration_ms 1000 exceeds 100" in result.detail


def test_run_asserts_selects_declared_run_population(cfg, item):
    per_item_samples = [
        {"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 10}
    ]
    run_samples = [
        *per_item_samples,
        {"item_id": "item-b", "version": "v1", "cost_usd": 0.001, "duration_ms": 1_000},
    ]
    results = run_asserts(
        output=_valid_output(),
        raw=json.dumps(_valid_output()),
        expected=item.expected,
        item=item.raw,
        cfg={
            **cfg,
            "asserts": [
                {"type": "cost_latency", "population": "run", "max_p95_ms": 100}
            ],
        },
        samples=per_item_samples,
        populations={
            "run": (
                run_samples,
                Population(kind="run", item_count=2, sample_count=2),
            )
        },
    )
    assert results[0].passed is False
    assert "p95 duration_ms 1000 exceeds 100" in results[0].detail


def test_run_population_rejects_two_samples_from_one_item(cfg, item):
    samples = [
        {"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 10},
        {"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 20},
    ]
    result = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "run", "max_p95_ms": 100},
        samples=samples,
        population=Population("run", item_count=2, sample_count=2),
    )
    assert result.passed is False
    assert result.detail == "run population item_count 2 does not match 1 distinct item ids"


def test_run_population_computes_with_two_distinct_items(cfg, item):
    samples = [
        {"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 10},
        {"item_id": "item-b", "version": "v1", "cost_usd": 0.001, "duration_ms": 20},
    ]
    result = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "run", "max_p95_ms": 100},
        samples=samples,
        population=Population("run", item_count=2, sample_count=2),
    )
    assert result.passed is True


@pytest.mark.parametrize(
    "samples, detail",
    [
        (
            [{"item_id": "item-a", "cost_usd": 0.001, "duration_ms": 10}],
            "require nonempty item_id and version",
        ),
        (
            [
                {"item_id": "item-a", "version": "v1", "cost_usd": 0.001, "duration_ms": 10},
                {"item_id": "item-a", "version": "v2", "cost_usd": 0.001, "duration_ms": 20},
            ],
            "must contain exactly 1 version",
        ),
    ],
)
def test_population_rejects_missing_identity_and_mixed_versions(cfg, item, samples, detail):
    result = cost_latency_assert(
        output=_valid_output(),
        raw="",
        expected=item.expected,
        item=item.raw,
        cfg={**cfg, "population": "per_item", "max_p95_ms": 100},
        samples=samples,
        population=Population("per_item", item_count=1, sample_count=len(samples)),
    )
    assert result.passed is False
    assert detail in result.detail


def test_cost_latency_requires_declared_population(cfg, item):
    with pytest.raises(AssertConfigError, match="population must be 'per_item' or 'run'"):
        cost_latency_assert(
            output=_valid_output(),
            raw="",
            expected=item.expected,
            item=item.raw,
            cfg={**cfg, "max_p95_ms": 100},
            samples=[{"cost_usd": 0.001, "duration_ms": 10}],
            population=Population("per_item", 1, 1),
        )


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
