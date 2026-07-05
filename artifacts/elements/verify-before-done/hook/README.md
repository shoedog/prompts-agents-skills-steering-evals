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

Codex/OpenAI models: ENFORCEMENT TIER DEPLOYED (2026-07-04, corrected — codex
DOES have Stop hooks with block/continuation semantics). Port:
~/.codex/hooks/verify_gate_codex.sh + ~/.codex/hooks.json (repo copies here).
Differences from the claude version: stop_hook_active replaces the counter
loop-guard (one enforcement round per turn); cwd is the session dir; success
must be exit 0 with NO stdout (plain text is invalid for codex Stop).
Smoke-verified end-to-end: gpt-5.5 blocked once, then wrote a
fail-on-pre-change regression test + well-formed VERIFICATION.md.
TRUST: non-managed hooks must be trusted once via /hooks in interactive
codex (hash-pinned; re-trust after editing the script). Headless runs need
--dangerously-bypass-hook-trust until trusted. The a2a-bridge verify node
remains a second, structural enforcement layer.

Rollback: delete the verify_gate group from ~/.claude/settings.json.
