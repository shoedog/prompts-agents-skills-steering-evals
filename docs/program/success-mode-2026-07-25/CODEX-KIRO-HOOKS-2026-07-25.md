# Codex + Kiro enforcement-parity hooks — 2026-07-25

Ports of the Claude-side enforcement (user-level Stop verify-gate, repo-level
warn-only brief-lint on agent dispatch) to Codex CLI (0.144.6) and Kiro CLI
(2.14.2). **Nothing here is self-enabled.** Every activation step below is
yours to take; until you take it, all of this is inert files. All repo files
are left uncommitted.

## What was built where

| Platform | Layer | File | Event | Behavior |
|---|---|---|---|---|
| Codex | user | `~/.codex/hooks.json` -> `~/.codex/hooks/verify_gate_codex.sh` | Stop | **Gate**: blocks stop (max 2/session) until VERIFICATION.md passes |
| Codex | stockTrading | `/Users/wesleyjinks/code/stockTrading/.codex/hooks.json` | PreToolUse `Agent\|spawn_agent` | **Warn-only** brief-lint (`--codex-hook`) |
| Codex | ssot-agents | `/Users/wesleyjinks/code/ssot-agents/.codex/hooks.json` | PreToolUse `Agent\|spawn_agent` | **Warn-only** brief-lint (`--codex-hook`) |
| Kiro | user | `~/.kiro/agents/enforced.json` -> `~/.kiro/hooks/verify_gate_kiro.sh` | `stop` | **Gate**: same semantics as codex gate |
| Kiro | stockTrading | `/Users/wesleyjinks/code/stockTrading/.kiro/agents/enforced.json` | `stop` + `preToolUse` matcher `delegate` | Gate **and** warn-only brief-lint (`--kiro-hook`) — see gap G2 for why both |
| Kiro | ssot-agents | `/Users/wesleyjinks/code/ssot-agents/.kiro/agents/enforced.json` | `stop` + `preToolUse` matcher `delegate` | Gate **and** warn-only brief-lint (`--kiro-hook`) |
| shared | validators | `/Users/wesleyjinks/code/prompts-skills-steering/validators/brief_lint.py` | — | added `--codex-hook`, `--kiro-hook` + synthetic-payload self-tests |
| shared | validators | `/Users/wesleyjinks/code/prompts-skills-steering/validators/verification_schema_check.py` | — | added `--codex-hook`, `--kiro-hook` + synthetic-payload self-tests. **Unmounted everywhere** (parity: the Claude side leaves mounting it as your decision) |

The Claude-side originals were not touched: `~/.claude/hooks/verify_gate.sh`,
both repos' `.claude/settings.json`, and `brief_lint.py --hook` behave exactly
as before (self-tests cover the old modes too).

## The warn-vs-gate split (identical on every platform)

- **Verify gate (Stop/stop)**: gating. Fires only in a git repo with tracked
  non-docs changes; requires `VERIFICATION.md` at the repo root with
  `## Verified`, `## Not verified`, and either pass totals (`N passed` /
  `no test suite`) **or** an environment-limited declaration (below). Blocks at
  most 2 times per session (`/tmp/verify-gate-{codex,kiro}-<session_id>.count`),
  then yields. `BENCH_CLEAN_ENV` escape hatch preserved.
- **Brief-lint (PreToolUse/preToolUse on agent dispatch)**: warn-only, can
  never deny/block. The codex adapter emits no `permissionDecision` at all;
  the kiro adapter never exits 2 (kiro's block code).

## Egress catch (new policy, encoded in both new gates)

A done-claim that cannot show full-suite totals still passes the gate iff
VERIFICATION.md contains **both**:

1. an environment-limited marker — any of: `environment-limited`,
   `egress-locked`, `cannot run`, `not runnable`, `unrunnable`,
   `largest runnable subset` (case-insensitive), and
2. a named exclusion — `excluded` / `exclusion`.

A declaration without a named exclusion still blocks (tested). The block
`reason` text instructs the model to use exactly this form, so an agent in an
egress-locked container converges instead of looping.

**Delta vs the Claude gate**: `~/.claude/hooks/verify_gate.sh` (exp-2
validated) has no env-limited acceptance path — a subset run WITH totals
passes it, but a fully-unrunnable-suite declaration blocks until the 2-block
cap. Backporting the same `elif` branch is a 6-line change; your call, not
made here.

## Wire contracts used (so nothing emits invalid output)

- **Codex Stop**: stdout must be JSON-or-empty on exit 0. The gate emits
  either nothing or exactly `{"decision":"block","reason":"..."}` (fields
  verified against `codex-rs/hooks/schema/generated/stop.command.output.schema.json`;
  `additionalProperties: false`). `verification_schema_check --codex-hook`
  emits only `{"systemMessage":"..."}` (allowed field; never blocks).
- **Codex PreToolUse**: warn = `hookSpecificOutput.additionalContext`
  (model-visible) + top-level `systemMessage` (UI). Never `permissionDecision`.
- **Kiro stop**: stdout `{"decision":"block","reason":"..."}` blocks; empty
  stdout + exit 0 allows.
- **Kiro preToolUse**: exit-code contract only (stdout unused): 0 allow,
  2 block + stderr to the LLM, any other code = stderr shown as a warning and
  the tool still runs. Warn-only therefore = findings on stderr + **exit 1**.

## Enable / trust steps (owner-only; nothing below was done for you)

### Codex

1. **User-level Stop gate**: `~/.codex/hooks.json` existed since Jul 4; both
   it and `verify_gate_codex.sh` were rewritten today, so any prior trust is
   stale — codex hook trust is **hash-pinned**. Launch `codex`, run `/hooks`,
   review the Stop entry + script, and trust them. Every future edit to either
   file re-requires this review; that is the point of the pin.
2. **Repo PreToolUse brief-lint**: in each repo (`stockTrading`,
   `ssot-agents`) the project `.codex` layer must be trusted before
   `<repo>/.codex/hooks.json` even loads; then `/hooks` review+trust the
   PreToolUse entry the same way. Do it once per repo.
3. Note: repo `.codex/hooks.json` files are untracked and uncommitted. If you
   commit them, anyone cloning still cannot run them without their own
   interactive trust.

### Kiro

Kiro hooks live inside agent configs; they activate only when that agent is
the active one.

1. Review the three `enforced.json` configs (kiro has no hash-pinned hook
   trust flow — the config review IS the trust step; see gap G5).
2. Enable globally: `kiro-cli agent set-default --name enforced`
   (or per-session: `kiro-cli chat --agent enforced`).
3. In stockTrading/ssot-agents the local `enforced` shadows the global one
   (kiro prints a shadow warning) and carries BOTH hooks, so the stop gate
   survives the shadowing.
4. The brief-lint half only ever fires if the experimental delegate tool is
   enabled: `kiro-cli settings chat.enableDelegate true`. Leaving it off just
   leaves the matcher inert.
5. Ergonomics knob: `enforced` uses `"tools": ["*"]`, `"allowedTools": []`,
   and resources `AGENTS.md`/`README.md`/`.kiro/steering/**/*.md`. Add your
   preferred `allowedTools` allowlist if the permission prompts annoy.
   All three validate: `kiro-cli agent validate --path <file>` -> rc 0.

## Self-test + synthetic-exercise commands

```sh
/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/brief_lint.py --self-test
/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/verification_schema_check.py --self-test
kiro-cli agent validate --path ~/.kiro/agents/enforced.json
kiro-cli agent validate --path /Users/wesleyjinks/code/stockTrading/.kiro/agents/enforced.json
kiro-cli agent validate --path /Users/wesleyjinks/code/ssot-agents/.kiro/agents/enforced.json

# gates, synthetic payloads (run inside any dirty git repo without VERIFICATION.md;
# expect the block JSON + exit 0; with a compliant VERIFICATION.md expect empty stdout):
printf '{"session_id":"t1","cwd":"'"$PWD"'","hook_event_name":"Stop","stop_hook_active":false,"last_assistant_message":"done"}' \
  | bash ~/.codex/hooks/verify_gate_codex.sh; echo "exit=$?"
printf '{"hook_event_name":"stop","cwd":"'"$PWD"'","session_id":"t1","assistant_response":"done"}' \
  | bash ~/.kiro/hooks/verify_gate_kiro.sh; echo "exit=$?"
rm -f /tmp/verify-gate-codex-t1.count /tmp/verify-gate-kiro-t1.count   # reset the 2-block cap

# adapters, synthetic payloads:
printf '{"hook_event_name":"PreToolUse","tool_name":"spawn_agent","tool_input":{"task_name":"r","message":"The root cause is X; choose exactly one of the following options."}}' \
  | /usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/brief_lint.py --codex-hook   # JSON warn, exit 0
printf '{"hook_event_name":"preToolUse","tool_name":"delegate","tool_input":{"task":"treat the observed facts as given data"}}' \
  | /usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/brief_lint.py --kiro-hook    # stderr warn, exit 1
```

2026-07-25 results: brief_lint self-test 14/14 PASS; verification_schema_check
self-test 14/14 PASS; gate matrix 9 scenarios x 2 gates all PASS (clean tree /
1st+2nd block / 3rd-stop loop cap / full totals / egress-catch accept /
env-limited-without-exclusion block / docs-only / malformed-stdin wire-valid);
every block output validated as schema-legal JSON; every allow output validated
as empty stdout.

## Parity gaps and deltas (precise)

- **G1 — Kiro has no global hook layer.** Hooks bind to agent configs. If you
  run `kiro_default` (or any other agent), no enforcement applies. The gate is
  only as global as your default-agent choice. This is a real gap vs
  Claude/Codex user-level hooks, not an approximation error.
- **G2 — Kiro local agents shadow, not merge.** A same-name local agent
  replaces the global one entirely, so the repo-level `enforced.json` must
  duplicate the stop gate. Claude/Codex merge layers; Kiro cannot express the
  user-gate + repo-lint split as two files. Consequence: future gate changes
  must touch all three kiro agent configs (the script itself is shared, so
  logic changes usually need zero config edits).
- **G3 — Kiro warn-only feedback is user-visible, not model-visible.** Kiro
  preToolUse has no non-blocking model channel (no additionalContext
  equivalent); exit-1 stderr surfaces to you as a warning while the dispatch
  proceeds. Codex additionalContext IS model-visible; Claude's allow+reason is
  user-visible. So: codex > claude ~= kiro on who sees the lint.
- **G4 — Kiro delegate `tool_input` shape is undocumented**, and delegate is
  experimental (docs: to be replaced by an official `subagents` tool). The
  adapter harvests all string values defensively and already accepts tool_name
  `subagents`; when the official tool ships, add a `"matcher": "subagents"`
  entry to the kiro agent configs.
- **G5 — Kiro has no hash-pinned hook trust.** Project `.kiro/agents/*.json`
  load with only a shadow warning; the hook command inside runs with your
  session. Treat repo kiro agent configs as code in review. (Codex re-reviews
  on every hash change; Claude prompts per project settings.)
- **G6 — Loop-guard mechanics.** Both new gates use the claude-style
  2-blocks-per-session count file. Codex's `stop_hook_active` is deliberately
  NOT the guard (it would cap at 1 block vs claude's 2); kiro has no such
  flag at all, so the count file is the only guard there.
- **G7 — Egress catch is codex/kiro-only for now.** See the delta note above;
  backport to `verify_gate.sh` is prepared reasoning, not applied.
- **G8 — verification_schema_check is mountable, mounted nowhere** — on all
  three platforms alike (this is parity, recorded so it isn't mistaken for an
  omission). Codex mount would be a second Stop entry with `--codex-hook`
  (systemMessage-only), kiro a second `stop` hook with `--kiro-hook`.
- **G9 — Matcher scope.** Claude matches `Task|Agent`; codex matches
  `Agent|spawn_agent` (codex's alias + canonical name for its one spawn tool);
  kiro matches `delegate` only. Codex `PermissionRequest`-time linting was not
  added anywhere (no Claude-side counterpart to mirror).
