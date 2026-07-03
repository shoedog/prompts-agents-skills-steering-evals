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

If EVERY PATH match for a name is a `node_modules` shadow (i.e. some
npm-installed same-named binary exists, but no real system install does),
returning the bare name would be a trap: the caller's own `subprocess.run`
does its own PATH search and would just re-resolve to that identical shadow,
silently reproducing the exact judge_error incident this module exists to
prevent. So that case raises `BinaryResolutionError` instead — see
`resolve_executable`'s docstring for the three-way behavior.
"""
from __future__ import annotations

import os
from pathlib import Path

from harness.providers.errors import ProviderError


class BinaryResolutionError(ProviderError):
    """Every PATH match for a name is an npm `node_modules` shadow.

    Raised instead of returning the bare name, because the bare name is not a
    safe fallback here: `subprocess.run` would perform its own PATH search
    and re-resolve to the very same shadow binary this function exists to
    skip, reproducing the incident silently rather than failing loudly.
    Carries the list of shadowed paths (via the exception message) so a human
    can tell at a glance this is a missing-real-install problem, not a code
    bug.
    """


def resolve_executable(name: str) -> str:
    """First PATH match for `name` that is NOT under any `node_modules` dir.

    Three outcomes:
      - A real (non-shadowed) match exists: returns its absolute path.
      - No match exists anywhere on PATH (not even a shadow): returns the
        bare `name` unresolved, so subprocess's own FileNotFoundError still
        surfaces a clear error exactly as it would have before this existed.
      - One or more matches exist, but EVERY one is a `node_modules` shadow:
        raises `BinaryResolutionError` rather than returning the bare name —
        see that class's docstring for why the bare-name fallback is unsafe
        in this specific case.
    """
    shadowed = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = os.path.join(entry, name)
        under_node_modules = "node_modules" in Path(entry).parts
        if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
            continue
        if under_node_modules:
            shadowed.append(candidate)
            continue
        return candidate
    if shadowed:
        raise BinaryResolutionError(
            f"every PATH match for {name!r} is an npm node_modules shadow "
            f"with no real install found on PATH: {shadowed}. Install the "
            f"real `{name}` CLI (e.g. via Homebrew or your system package "
            f"manager) so it resolves from outside any node_modules "
            f"directory."
        )
    return name
