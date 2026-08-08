# bash_evidence_guard — live mounts (personal machine, 2026-08-08)

All mounts are machine-local (settings files are not repo-carried; this doc
is their durable record). Every edit was ADDITIVE with a `.pre-guard` backup
alongside the file. Warn-only everywhere per SPEC.md §6; deny flips, if
ever, land per-project only.

PORTABILITY: every snippet embeds THIS machine's clone path
(`/Users/wesleyjinks/code/prompts-skills-steering`). On the work machine or
a colleague's checkout, substitute the local clone path. Kiro additionally
requires the `enforced` agent to be the active agent
(`kiro-cli agent set-default --name enforced`), and repo-level
`.kiro/agents/enforced.json` files shadow the global one — the fragment
must ride each of them (stockTrading and ssot-agents carry it tracked).

## claude — `~/.claude/settings.json` (user-global)

Appended to `hooks.PreToolUse` (existing moshi-hooks entry preserved
byte-identical):

```json
{ "matcher": "Bash",
  "hooks": [{ "type": "command",
    "command": "/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/bash_evidence_guard.py --hook",
    "timeout": 10, "statusMessage": "bash-evidence-guard: checking shell command" }] }
```

Note: a hook deny (not used in v1) would override `permissions.allow`
entries; the user-global mount stays warn permanently (SPEC §6).

## codex — `~/.codex/hooks.json` (global)

New `PreToolUse` group beside the existing Stop verifier; matcher `^Bash$`
covers legacy shell and unified exec_command (sol-verified, 0.146):

```json
{ "matcher": "^Bash$",
  "hooks": [{ "type": "command",
    "command": "/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/bash_evidence_guard.py --codex-hook",
    "timeout": 10, "statusMessage": "bash-evidence-guard: checking shell command" }] }
```

## kiro — `hooks.preToolUse` in the `enforced` agent config

Mounted in all three places (repo-level agent configs SHADOW the global
one): `~/.kiro/agents/enforced.json`,
`/Users/wesleyjinks/code/stockTrading/.kiro/agents/enforced.json`,
`/Users/wesleyjinks/code/ssot-agents/.kiro/agents/enforced.json`.
`kiro-cli agent validate` exit 0 (lenient — a live fire is the real proof).

```json
{ "matcher": "execute_bash|executeBash|execute_cmd|executeCmd|shell",
  "command": "/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/bash_evidence_guard.py --kiro-hook",
  "timeout_ms": 10000 }
```

Kiro caveats (SPEC §5): hooks fire only when the `enforced` agent is
active; kiro warn (exit 1) is user-visible only — the model never sees it;
hooks do not fire inside kiro native subagents. Work machine: apply the
same fragment during the bootstrap/README.md merge.

## Observation channel

Fire log: `~/.claude/logs/bash-evidence-guard.jsonl` — one row per
runner-bearing command: `{ts, carrier, cwd, command, rule, decision}` with
decisions warn/deny/clean/escape; `clean` rows are the denominator. Weekly
triage reads FP rate + fires÷runner-invocations before any flip discussion
(declared cap: flip review no earlier than after 2 weekly reports).
Escape hatch: append `# evidence-ok: <why>` — allowed and logged.
