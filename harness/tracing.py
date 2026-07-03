"""Best-effort call tracing. Never raises, never blocks a run.

opik is installed on eval machines but is NOT configured by default, so the
graceful path is a JSONL append into the results dir. We only attempt the opik
SDK when it is plausibly usable (an OPIK_API_KEY is present), and we import it
lazily inside a broad try/except so a missing/misconfigured opik can never slow
down or crash an eval. If neither opik nor a results_dir is available, tracing
is a silent no-op.
"""
from __future__ import annotations

import json
import os
import time

_opik_client = None
_opik_tried = False


def _maybe_opik():
    """Return an opik client if configured and importable, else None. Cached."""
    global _opik_client, _opik_tried
    if _opik_tried:
        return _opik_client
    _opik_tried = True
    if not os.environ.get("OPIK_API_KEY"):
        _opik_client = None
        return None
    try:  # lazy, guarded — must never raise into the caller
        import opik  # type: ignore

        _opik_client = opik.Opik()
    except Exception:
        _opik_client = None
    return _opik_client


def trace_call(kind: str, payload: dict, results_dir: str | None = None) -> None:
    """Record one traced event. Falls back to results_dir/trace.jsonl."""
    event = {"ts": time.time(), "kind": kind, "payload": payload}
    try:
        client = _maybe_opik()
        if client is not None:
            try:
                client.trace(name=kind, metadata={"payload": payload})
                return
            except Exception:
                pass  # fall through to JSONL
        if results_dir:
            path = os.path.join(results_dir, "trace.jsonl")
            os.makedirs(results_dir, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # Tracing must never break a run.
        return
