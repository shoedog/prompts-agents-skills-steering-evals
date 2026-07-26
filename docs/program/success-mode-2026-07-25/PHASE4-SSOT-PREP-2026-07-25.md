# Phase 4 SSOT prep — portable always-on instructions (2026-07-25)

## What is ready (all uncommitted, in ~/code/ssot-agents)

- Carrier (source of truth): `instructions/always-on/INSTRUCTIONS.md` — a byte-identical copy (sha256 `5a0b4438…edbd3`, 956 bytes) of `~/.claude/CLAUDE.md` as of today: the `# Global steering` title plus the two validated rules (code review severity, exp-d7; debugging discipline, exp-3). It passes the strict content gate: LF-only, no frontmatter, no `@` imports, no HTML comments, no Kiro file refs, well under the 32 KiB ceiling.
- Driver: `tools/emit-instructions.mjs` — parses the carrier at USER scope, compiles it through `compileWorkflow.plan` (profile `agent-instructions-portable-v1`, catalog `capability-catalog/2026-07-21/r2`, lossPolicy `reject`; all three targets planned ready), and stages each planned file under `<stagingRoot>/<target>/<relativePath>`. It refuses to write outside the staging root and never touches the real global files.
- Staged outputs, each byte-identical to the carrier:
  - `out/staging/claude/.claude/CLAUDE.md`
  - `out/staging/codex/.codex/AGENTS.md`
  - `out/staging/kiro/.kiro/steering/ssot.md`

## Commands

- Stage (default root `out/staging`): `cd ~/code/ssot-agents && node --import tsx tools/emit-instructions.mjs [stagingRoot]`
- Drift check, read-only (exit 0 all SAME, 1 any DRIFT): `node --import tsx tools/emit-instructions.mjs --check`
- Real rollout later (manual and deliberate — the compiler plans, it never writes real scopes):
  1. Settle the open decisions below, edit the carrier if needed, re-stage, review `out/staging/`.
  2. `cp out/staging/claude/.claude/CLAUDE.md ~/.claude/CLAUDE.md`
  3. `cp out/staging/codex/.codex/AGENTS.md ~/.codex/AGENTS.md`
  4. `cp out/staging/kiro/.kiro/steering/ssot.md ~/.kiro/steering/ssot.md`
  5. `node --import tsx tools/emit-instructions.mjs --check` — expect three SAME.

## Constraint to keep in mind

The portable profile is byte-exact by design: every target receives the identical carrier bytes; only the destination paths differ. There is no per-target content shaping — no Kiro inclusion-mode frontmatter, no codex-only sections. One text everywhere, or it does not belong in this carrier.

## Drift inventory (from --check, 2026-07-25)

- claude: SAME — `~/.claude/CLAUDE.md` already matches the carrier; rollout is a no-op.
- codex: DRIFT — `~/.codex/AGENTS.md` (1491 bytes) carries a third rule, "Verify before done (instruction tier; enforcement lives in claude hooks / bridge verify node)", ahead of the two shared rules. Rolling out as-is would delete it from codex.
- kiro: DRIFT — `~/.kiro/steering/` is empty; no `ssot.md` exists. Rollout would create it (kiro currently gets no global steering at all).

## Open decisions (owner calls, not made here)

1. "Verify before done": promote it into the carrier (it then lands in claude and kiro too) or drop it from codex at rollout. Its own text says enforcement lives in hooks/bridge, so the instruction tier is advisory either way.
2. Accept identical steering everywhere, including kiro picking up the same text with no kiro-specific framing.
3. The carrier keeps the `# Global steering` H1 so claude is byte-SAME today and codex keeps its current document shape. A rules-only carrier (no H1) would put claude into DRIFT as well.

Nothing is committed and no real global file was modified during prep.
