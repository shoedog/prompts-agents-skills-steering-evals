# Codex-specific operation notes (this machine)

## Sandbox boundaries — request escalation UP FRONT, never try-fail-retry
The following are known blocked inside the sandbox on this machine. Do not
attempt them in-sandbox first; request escalation immediately with a one-line
justification, or route the step to the controller. After ONE sandbox denial
of a command class, treat the whole class as blocked for the rest of the
session — the try-fail-rerun-outside double run wastes a round every time.

- Network egress in workspace-write (default off): installs, `cargo update`
  fetching new crates, `curl`/`wget`, `git fetch/pull/push`.
- `.git` writes in sandboxed workspaces: commits fail (sandbox protects
  .git) — leave committing to the controller and say so in the hand-off.
- `npx tsx` is IPC-blocked — use `node --import tsx` instead (never spend a
  round discovering this again).
- Launching browsers (Chromium/Playwright) — route browser work to the
  controller's Claude subagents.
- Writes outside the workspace roots (including /tmp paths not under the
  granted writable roots).

## Approved commands
~/.codex/rules/default.rules pre-approves the read-only and verify chains
(git status/diff/log/show, ls/rg/grep/find/cat/head/tail/wc/nl, cargo
fmt/check/clippy/test/build, npx tsc, node --import tsx --test) and forces a
prompt on git push/fetch/pull. If a routine safe command still prompts,
propose adding a prefix_rule instead of working around it.

## Patch discipline
Before apply_patch, re-read the exact target region in the same turn; never
compose a patch from remembered content. After any failed apply_patch, the
next action is reading the file (nl -ba), not a retry.
