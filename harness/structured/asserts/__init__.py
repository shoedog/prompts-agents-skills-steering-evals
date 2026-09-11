"""Assert registry for the structured / analyzer / pipeline execution path.

Nothing here is imported by harness/asserts/judge_assert.py, harness/run.py or
harness/gen_promptfoo.py; the review-ablation path keeps its single hard-wired
assert and is unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class AssertConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AssertResult:
    name: str
    passed: bool
    hard: bool
    score: float | None
    detail: str


@dataclass(frozen=True)
class Population:
    kind: str
    item_count: int
    sample_count: int

    def __post_init__(self) -> None:
        if self.kind not in {"run", "version"}:
            raise ValueError(f"unknown population kind {self.kind!r}")
        for field in ("item_count", "sample_count"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"population {field} must be a positive integer")


class Assert(Protocol):
    def __call__(
        self,
        *,
        output: dict[str, Any] | None,
        raw: str,
        expected: dict[str, Any],
        item: dict[str, Any],
        cfg: dict[str, Any],
        samples: list[dict[str, Any]] | None,
        population: Population | None = None,
    ) -> AssertResult: ...


_REGISTRY: dict[str, Assert] = {}


def register(name: str) -> Callable[[Assert], Assert]:
    def _wrap(fn: Assert) -> Assert:
        if name in _REGISTRY:
            raise KeyError(f"duplicate assert type {name!r}")
        _REGISTRY[name] = fn
        return fn

    return _wrap


def get(name: str) -> Assert:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown assert type {name!r}; known: {sorted(_REGISTRY)}") from None


def run_asserts(
    *,
    output: dict[str, Any] | None,
    raw: str,
    expected: dict[str, Any],
    item: dict[str, Any],
    cfg: dict[str, Any],
    samples: list[dict[str, Any]] | None,
    populations: dict[str, tuple[list[dict[str, Any]], Population]] | None = None,
) -> list[AssertResult]:
    """Run configured asserts; Task 8 supplies full populations as `(samples, descriptor)`."""
    results: list[AssertResult] = []
    hard_failure = False
    for entry in cfg.get("asserts", []):
        name = entry["type"]
        assertion = get(name)
        declared_population = entry.get("population") if name == "cost_latency" else None
        if name == "cost_latency" and declared_population not in {"run", "version"}:
            raise AssertConfigError(
                "cost_latency population must be 'run' or 'version'; "
                f"got {declared_population!r}"
            )
        if hard_failure:
            results.append(
                AssertResult(name, False, False, None, "not_applicable: hard schema failure")
            )
            continue
        assertion_cfg = {**cfg, **entry}
        assertion_samples = samples
        population = None
        if populations is not None and declared_population in populations:
            assertion_samples, population = populations[declared_population]
        result = assertion(
            output=output,
            raw=raw,
            expected=expected,
            item=item,
            cfg=assertion_cfg,
            samples=assertion_samples,
            population=population,
        )
        results.append(result)
        hard_failure = not result.passed and result.hard
    return results


# Import registered asserts only after the registry primitives exist.
from harness.structured.asserts import analyzer_match as _analyzer_match  # noqa: E402,F401
from harness.structured.asserts import consistency as _consistency  # noqa: E402,F401
from harness.structured.asserts import cost_latency as _cost_latency  # noqa: E402,F401
from harness.structured.asserts import evidence as _evidence  # noqa: E402,F401
from harness.structured.asserts import label as _label  # noqa: E402,F401
from harness.structured.asserts import schema as _schema  # noqa: E402,F401
