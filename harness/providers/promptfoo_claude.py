"""promptfoo Python provider shim for the weak Claude executor arm.

promptfoo drives this via its Python provider protocol: it imports this file
and calls `call_api(prompt, options, context)`, where `options["config"]` is the
provider config from the generated YAML and `context["vars"]` holds the test
vars. The prompt arrives already rendered (nunjucks `{{task_input}}` filled in).

There is no direct model API on eval machines — the ONLY model transport is this
shim shelling out through `run_claude` (the `claude -p` CLI wrapper). Each call
runs in a fresh, per-(arm, task) sandbox cwd so no state leaks between items.

Every call writes results_dir/calls/<arm>-<task_id>.json with the full token
breakdown (fresh / cache-creation / cache-read / output) plus cost and duration,
which the metrics layer later globs. The value returned to promptfoo carries the
logical input-token total (fresh + both cache buckets) so promptfoo's own token
accounting stays consistent with ours.

The promptfoo python worker only puts THIS file's directory on sys.path, so we
prepend the repo root before importing the `harness` package.
"""
import json
import os
import shutil
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.providers.claude_cli import run_claude  # noqa: E402
from harness.providers.errors import ProviderError  # noqa: E402

try:  # tracing is best-effort and must never break a run
    from harness.tracing import trace_call  # noqa: E402
except Exception:  # pragma: no cover
    def trace_call(kind, payload, results_dir=None):
        return None


def call_api(prompt, options, context):
    config = (options or {}).get("config", {}) or {}
    variables = (context or {}).get("vars", {}) or {}

    arm = config["arm"]
    exp_id = config["exp_id"]
    tier = config["tier"]
    model = config["model"]
    results_dir = config["results_dir"]
    task_id = variables["task_id"]

    sandbox = os.path.join(results_dir, "sandbox", f"{arm}-{task_id}")
    shutil.rmtree(sandbox, ignore_errors=True)
    os.makedirs(sandbox, exist_ok=True)

    try:
        out = run_claude(prompt, model=model, cwd=sandbox, timeout=300)
    except ProviderError as e:
        # Surface as a promptfoo provider error; the item's assert never runs
        # and the missing calls/judge files mark this item absent downstream.
        return {"error": f"claude executor failed: {e} :: {getattr(e, 'stderr_tail', '')}"}

    usage = out.get("raw", {}).get("usage", {}) or {}
    fresh = int(usage.get("input_tokens", 0) or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    output_tokens = int(out.get("output_tokens", 0) or 0)
    logical_in = fresh + cache_creation + cache_read
    cost = float(out.get("cost_usd", 0.0) or 0.0)
    duration_ms = int(out.get("duration_ms", 0) or 0)

    record = {
        "exp_id": exp_id,
        "arm": arm,
        "task_id": task_id,
        "tier": tier,
        "model": model,
        "fresh_input_tokens": fresh,
        "cache_creation_tokens": cache_creation,
        "cache_read_tokens": cache_read,
        "output_tokens": output_tokens,
        "input_tokens_logical": logical_in,
        "cost_usd": cost,
        "duration_ms": duration_ms,
    }

    calls_dir = os.path.join(results_dir, "calls")
    os.makedirs(calls_dir, exist_ok=True)
    with open(os.path.join(calls_dir, f"{arm}-{task_id}.json"), "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    trace_call("executor", record, results_dir=results_dir)

    return {
        "output": out["output"],
        "tokenUsage": {
            "prompt": logical_in,
            "completion": output_tokens,
            "total": logical_in + output_tokens,
        },
        "cost": cost,
    }
