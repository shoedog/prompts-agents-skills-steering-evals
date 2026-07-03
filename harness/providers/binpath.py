"""Resolve a CLI executable defensively against `npx`/npm PATH pollution.

`run.py` launches promptfoo via `npx promptfoo eval`. `npx` (and, more
generally, any npm-invoked process) prepends `<dir>/node_modules/.bin` for
`<dir>` and every one of its ancestors onto `PATH` for the whole process tree
it spawns — including the Python provider/assert workers our shims run in,
since they inherit PATH from that same tree.

promptfoo (0.121.17) lists `@openai/codex-sdk` and
`@anthropic-ai/claude-agent-sdk` as OPTIONAL dependencies. `@openai/codex-sdk`
pulls in `@openai/codex`, which declares a `bin: {"codex": "bin/codex.js"}` —
so `npm install` symlinks `node_modules/.bin/codex` to that JS wrapper. Under
`npx`'s augmented PATH, a bare `subprocess.run(["codex", ...])` resolves to
THIS local npm wrapper before it ever reaches the real Homebrew/system `codex`
CLI on `/opt/homebrew/bin` — and the wrapper's own vendored native binary
(`node_modules/@openai/codex-darwin-arm64/vendor/.../codex/`) was an empty
directory in this environment (an incompletely-installed optional
dependency), so every judge call failed with `spawn ... ENOENT`, a Node-level
error with nothing indicating it came from the wrong `codex` in the first
place.

`resolve_executable` reproduces PATH's search order but skips any entry that
lives under a `node_modules` directory, so both the judge (`codex`) and the
executor (`claude`) always resolve to the real system CLI regardless of what
promptfoo's own npm dependency tree happens to vendor under this project's
`node_modules/`.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_executable(name: str) -> str:
    """First PATH match for `name` that is NOT under any `node_modules` dir.

    Falls back to the bare `name` (unresolved) if every PATH match is
    shadowed or none exists, so subprocess's own FileNotFoundError still
    surfaces a clear error exactly as it would have before this existed.
    """
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        if "node_modules" in Path(entry).parts:
            continue
        candidate = os.path.join(entry, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return name
