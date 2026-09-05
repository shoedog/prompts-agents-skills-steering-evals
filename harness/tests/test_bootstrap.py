"""Paired bootstrap tests over a hand-checkable twenty-item fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.stats.bootstrap import mean_outcome, paired_delta_ci, percentile


FIXTURE = Path(__file__).parent / "fixtures/stats/paired-20.json"


def test_paired_bootstrap_matches_numeric_golden():
    fixture = json.loads(FIXTURE.read_text())
    result = paired_delta_ci(
        fixture["baseline"],
        fixture["candidate"],
        mean_outcome,
        resamples=2000,
        seed=20260904,
    )
    assert result == fixture["expected"]
    assert (
        paired_delta_ci(
            fixture["baseline"],
            fixture["candidate"],
            mean_outcome,
            resamples=2000,
            seed=7,
        )
        != result
    )


def test_percentile_uses_linear_interpolation():
    assert percentile([0.0, 10.0], 0.25) == 2.5


@pytest.mark.parametrize("quantile", [-0.1, 1.1, float("nan"), True])
def test_percentile_rejects_invalid_quantiles(quantile):
    with pytest.raises(ValueError, match="quantile"):
        percentile([0.0], quantile)


def test_percentile_rejects_empty_population():
    with pytest.raises(ValueError, match="at least one value"):
        percentile([], 0.5)


def test_paired_bootstrap_reuses_one_draw_for_both_versions():
    baseline = {"a": {"outcome": 0.0}, "b": {"outcome": 1.0}}
    candidate = {"a": {"outcome": 0.25}, "b": {"outcome": 1.25}}

    result = paired_delta_ci(
        baseline,
        candidate,
        mean_outcome,
        resamples=25,
        seed=11,
    )

    assert result["delta"] == 0.25
    assert result["lo"] == 0.25
    assert result["hi"] == 0.25


def test_paired_bootstrap_rejects_unpaired_or_empty_items():
    with pytest.raises(ValueError, match="identical item-id sets"):
        paired_delta_ci(
            {"a": {"outcome": 1}},
            {"b": {"outcome": 1}},
            mean_outcome,
            resamples=1,
            seed=1,
        )
    with pytest.raises(ValueError, match="at least one paired item"):
        paired_delta_ci({}, {}, mean_outcome, resamples=1, seed=1)


@pytest.mark.parametrize(
    "resamples, seed, alpha, reason",
    [
        (0, 1, 0.05, "resamples"),
        (-1, 1, 0.05, "resamples"),
        (True, 1, 0.05, "resamples"),
        (1.5, 1, 0.05, "resamples"),
        (1, 1, 0.0, "alpha"),
        (1, 1, 1.0, "alpha"),
        (1, 1, float("nan"), "alpha"),
        (1, 1, True, "alpha"),
        (1, True, 0.05, "seed"),
        (1, 1.5, 0.05, "seed"),
    ],
)
def test_paired_bootstrap_rejects_invalid_sampling_parameters(
    resamples, seed, alpha, reason
):
    rows = {"a": {"outcome": 1}}
    with pytest.raises(ValueError, match=reason):
        paired_delta_ci(
            rows,
            rows,
            mean_outcome,
            resamples=resamples,
            seed=seed,
            alpha=alpha,
        )
