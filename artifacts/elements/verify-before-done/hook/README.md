# verify-before-done Stop-gate hook (deployed 2026-07-04)

Validated in exp-2 (docs/exp-2-verify-hook.md): tests-stronger 12/12 vs
unaided Fable on implement tasks; 100% adherence vs 4/6 for the prompt form.

Deployment: USER-LEVEL — applies to every repo, no per-repo install.
- script: ~/.claude/hooks/verify_gate.sh (this dir holds the repo copy)
- registered in ~/.claude/settings.json under hooks.Stop (second group,
  synchronous, alongside the async moshi-hooks entry)

Safety rails for global use: no-ops outside git repos, on clean trees, on
untracked-only changes, and on docs-only changes; VERIFICATION.md is
auto-added to .git/info/exclude; loop guard = 2 blocks per session
(/tmp/verify-gate-<session_id>.count); "no test suite" is an accepted total
for repos without tests.

Codex/OpenAI models: no native Stop-hook equivalent — they get the
instruction tier via ~/.codex/AGENTS.md (weak form, measured 4/6 adherence)
or STRUCTURAL enforcement when dispatched through a2a-bridge's implement
flow (its verify node runs the build/test gates).

Rollback: delete the verify_gate group from ~/.claude/settings.json.
