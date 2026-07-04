"""promptfoo Python provider shim for a codex-family executor tier.

Mirrors `promptfoo_claude.py`'s contract exactly: promptfoo imports this file
and calls `call_api(prompt, options, context)`, where `options["config"]` is
the provider config from the generated YAML and `context["vars"]` holds the
test vars. The prompt arrives already rendered (nunjucks `{{task_input}}`
filled in).

This shim exists so the harness can run OpenAI/local models — via the `codex`
CLI, the ONLY model transport available on eval machines for that family — as
an EXECUTOR tier, not just as the blind judge. That enables cross-family
comparisons (e.g. weak-claude vs. weak-codex) and the expertise-reversal
failure signature the owner wants to study. `run_codex` already runs the
child under `--sandbox read-only`; this shim additionally gives each call its
own fresh, per-(arm, task) sandbox cwd so no state leaks between items, the
same isolation `promptfoo_claude.py` provides for the claude family.

Token accounting differs from the claude shim: codex-cli only ever reports a
single best-effort `tokens_used` total (parsed from its stderr/stdout "tokens
used" line) — there is no fresh/cache-creation/cache-read/output breakdown to
report, unlike claude's `usage` block. The per-call JSON record keeps every
mandatory key the claude shim writes (so `metrics.py`'s glob-and-sum code path
is unchanged), but the breakdown fields are null and a `tokens_only: true`
marker flags the record as such for report annotation. `cost_usd` is derived
from `tokens_used` and the provider's configured `usd_per_mtok` rate when one
is set; None (not 0.0) when no rate is configured, so "unpriced" is never
confused with "free". `metrics.token_totals` already coerces a None
token/cost field to 0 via `c.get(key, 0) or 0`, so these nulls do not break
aggregation — verified by reading that function, not assumed.

The promptfoo python worker only puts THIS file's directory on sys.path, so we
prepend the repo root before importing the `harness` package (same fix
`promptfoo_claude.py` needed).
"""
import json
import os
import shutil
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from harness.providers.codex_cli import run_codex  # noqa: E402
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

    effort = config.get("effort", "medium")
    usd_per_mtok = config.get("usd_per_mtok")

    sandbox = os.path.join(results_dir, "sandbox", f"{arm}-{task_id}")
    shutil.rmtree(sandbox, ignore_errors=True)
    os.makedirs(sandbox, exist_ok=True)

    start = time.monotonic()
    try:
        out = run_codex(prompt, model=model, effort=effort, cwd=sandbox, timeout=300)
    except ProviderError as e:
        # Surface as a promptfoo provider error; the item's assert never runs
        # and the missing calls/judge files mark this item absent downstream.
        return {"error": f"codex executor failed: {e} :: {getattr(e, 'stderr_tail', '')}"}
    duration_ms = int((time.monotonic() - start) * 1000)

    tokens_used = out.get("tokens_used")
    if tokens_used is not None:
        tokens_used = int(tokens_used)
    cost = (
        (tokens_used / 1e6 * usd_per_mtok)
        if (tokens_used is not None and usd_per_mtok is not None)
        else None
    )

    record = {
        "exp_id": exp_id,
        "arm": arm,
        "task_id": task_id,
        "tier": tier,
        "model": model,
        # codex-cli reports one token total, not a fresh/cache/output
        # breakdown — these stay null rather than a fabricated split.
        "fresh_input_tokens": None,
        "cache_creation_tokens": None,
        "cache_read_tokens": None,
        "output_tokens": None,
        "input_tokens_logical": None,
        "cost_usd": cost,
        "duration_ms": duration_ms,
        "tokens_used": tokens_used,
        "tokens_only": True,
    }

    calls_dir = os.path.join(results_dir, "calls")
    os.makedirs(calls_dir, exist_ok=True)
    with open(os.path.join(calls_dir, f"{arm}-{task_id}.json"), "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    trace_call("executor", record, results_dir=results_dir)

    # promptfoo's own TokenUsage schema fields are all optional numbers with no
    # `.nullable()` — sending JSON null through the python-worker bridge would
    # fail validation, so we omit unknown fields entirely rather than send
    # null, and never send total=None.
    token_usage = {"total": tokens_used} if tokens_used is not None else {}

    return {
        "output": out["output"],
        "tokenUsage": token_usage,
        "cost": cost if cost is not None else 0.0,
    }
