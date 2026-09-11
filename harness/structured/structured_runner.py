"""Authenticated orchestration for structured LLM evaluation runs."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from harness.resultsdir import check_structured_stale_results_dir
from harness.structured.config import StructuredConfig
from harness.structured.promotion import PromotionVerdict
from harness.structured.replay import LoadedRun
from harness.structured.report import render
from harness.structured.results import ResultsWriter, canonical_json, confined_run_dir, write_json_atomic
from harness.structured.runner_call import _run_one
from harness.structured.runner_config import (
    _config_snapshot,
    _item_snapshot,
    _seed,
    _validate_asserts,
    _validate_versions,
)
from harness.structured.runner_finalize import (
    _shared_refs,
    _verify_final_tree,
    _write_assert_records,
)
from harness.structured.runner_types import (
    Clock,
    ExecutorFactory,
    RunResult,
    StaleRunError,
    _Completed,
    _Work,
    _timestamp_parts,
)
from harness.structured.snapshots import write_input_snapshots
from harness.structured.taskset import assemble_request


def _run_structured(
    cfg: StructuredConfig,
    *,
    executor_factory: ExecutorFactory,
    clock: Clock,
    force: bool,
    no_cache: bool,
    only: frozenset[str],
    taskset_loader: Callable[..., Any],
) -> RunResult:
    """Run one validated structured-task config into an authenticated result tree."""
    _validate_versions(cfg)
    _validate_asserts(cfg)
    taskset = taskset_loader(
        cfg.taskset,
        split=cfg.split,
        max_items=cfg.token_budget["max_items"],
    )
    by_id = {item.id: item for item in taskset.items}
    unknown = sorted(only - by_id.keys())
    if unknown:
        raise ValueError(f"unknown --only item: {unknown[0]}")
    items = tuple(by_id[item_id] for item_id in sorted(only or by_id.keys()))
    if not items:
        raise ValueError("structured run selected no items")
    versions = tuple(deepcopy(list(cfg.versions)))
    config = _config_snapshot(cfg, taskset.manifest["task"])
    item_snapshots = {item.id: _item_snapshot(item) for item in items}
    requests: dict[tuple[str, int], dict[str, Any]] = {}
    for item in items:
        for sample in range(cfg.samples_per_item):
            requests[(item.id, sample)] = {
                version["name"]: assemble_request(
                    item,
                    task_version=version["task_version"],
                    request_schema=cfg.request_schema,
                )
                for version in versions
            }

    started_at, compact = _timestamp_parts(clock.now())
    del started_at
    config_digest = hashlib.sha256(canonical_json(config) + b"\n").hexdigest()
    run_dir = confined_run_dir(cfg.root, cfg.id, f"{compact}-{config_digest[:8]}")
    if not check_structured_stale_results_dir(run_dir, force=force):
        raise StaleRunError(f"stale structured results: {run_dir}")
    writer = ResultsWriter(run_dir)
    write_input_snapshots(
        writer,
        config=config,
        manifest=taskset.manifest,
        items=item_snapshots,
        requests=requests,
    )
    executors = {version["name"]: executor_factory(version) for version in versions}
    shared_refs = _shared_refs(writer, items, versions)
    cache_root = cfg.root / ".cache" / "structured"

    completed: list[_Completed] = []
    with tempfile.TemporaryDirectory(prefix="structured-run-", dir=cfg.root) as temporary:
        temporary_root = Path(temporary)
        work_items: list[_Work] = []
        for version in versions:
            for item in items:
                for sample in range(cfg.samples_per_item):
                    request_file = (
                        temporary_root
                        / "requests"
                        / f"{version['name']}-{item.id}-s{sample}.json"
                    )
                    write_json_atomic(request_file, requests[(item.id, sample)][version["name"]])
                    work_items.append(
                        _Work(
                            version=version,
                            item=item,
                            sample=sample,
                            seed=_seed(cfg.seed, version["name"], item.id, sample),
                            request=requests[(item.id, sample)][version["name"]],
                            request_file=request_file,
                            input_sha256={
                                name: ref.sha256 for name, ref in sorted(item.inputs.items())
                            },
                            shared_ref=shared_refs.get((version["name"], item.id)),
                        )
                    )
        response_validator = Draft202012Validator(cfg.response_schema)
        max_cost = float(cfg.token_budget["max_cost_usd"])
        spent = 0.0
        budget_reached = False
        next_work = 0
        with ThreadPoolExecutor(max_workers=cfg.jobs) as pool:
            futures: dict[Future[_Completed], int] = {}

            def submit(work_index: int) -> None:
                work = work_items[work_index]
                future = pool.submit(
                    _run_one,
                    work,
                    executor=executors[work.version["name"]],
                    writer=writer,
                    clock=clock,
                    cache_root=cache_root,
                    no_cache=no_cache,
                    response_validator=response_validator,
                )
                futures[future] = work_index

            while next_work < len(work_items) and len(futures) < cfg.jobs:
                submit(next_work)
                next_work += 1

            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=futures.__getitem__):
                    futures.pop(future)
                    if future.cancelled():
                        continue
                    result = future.result()
                    completed.append(result)
                    if result.call["cache"] == "miss":
                        spent += float(result.call["llm_envelope"]["cost_usd"])
                if spent > 0.0 and spent >= max_cost:
                    budget_reached = True
                    for future in futures:
                        future.cancel()
                if not budget_reached:
                    while next_work < len(work_items) and len(futures) < cfg.jobs:
                        submit(next_work)
                        next_work += 1

        if budget_reached:
            raise RuntimeError(
                "token_budget.max_cost_usd reached after provider invocation: "
                f"reported ${spent:.6f} against ${max_cost:.6f}"
            )

    completed.sort(key=lambda value: value.key)
    calls = [value.call for value in completed]
    for value in completed:
        writer.append_event("replay", value.replay)
        writer.append_event("trace", value.trace)
    _write_assert_records(
        writer,
        calls=calls,
        items=item_snapshots,
        config=config,
        classes=tuple(taskset.classes),
    )
    loaded = LoadedRun.load(run_dir)
    render(loaded)
    _verify_final_tree(
        run_dir,
        loaded=loaded,
        versions=tuple(version["name"] for version in versions),
        items=tuple(item.id for item in items),
        samples=cfg.samples_per_item,
        shared_refs=shared_refs,
    )
    metrics = json.loads((run_dir / "metrics.json").read_bytes())
    promotion_value = next(iter(metrics["promotions"].values()), None)
    promotion = PromotionVerdict(**promotion_value) if promotion_value is not None else None
    return RunResult(
        run_dir=run_dir,
        metrics=metrics,
        promotion=promotion,
        stage_errors=sum(bool(call.get("stage_error")) for call in loaded.calls),
    )
