# Bootstrap — portable steering

`global-CLAUDE.md` is the canonical copy of the validated global steering
(installed as `~/.claude/CLAUDE.md`). On a new machine:

    git clone git@github.com:shoedog/prompts-agents-skills-steering-evals.git
    cd prompts-agents-skills-steering-evals/bootstrap
    ./install.sh

`./install.sh --check` diffs the installed copy against the repo copy and
exits nonzero on drift.

Sync rule: the repo copy is canonical. When steering changes (a promotion or
refinement), edit `bootstrap/global-CLAUDE.md`, commit, then run `install.sh`
on each machine. If `~/.claude/CLAUDE.md` was hot-edited directly, copy it
back here and commit in the same turn (durable-custody rule).

## Other carriers (Codex, Kiro)

On the personal machine, `~/.codex/AGENTS.md` and `~/.kiro/steering/ssot.md`
are exact mirrors of `global-CLAUDE.md` — sync them with a plain `cp` from
this file after any steering change (verified mirrors 2026-08-07; `.pre-v2`
backups sit alongside). The merge-not-overwrite guidance below is for the
WORK machine, where those files may carry work-specific content.

The steering content is tool-agnostic markdown; only the carrier file
differs. `install.sh` deliberately handles only the Claude carrier — the
others may already hold work-specific content, and an installer that
overwrites them is worse than a paste:

- **Codex**: merge the sections of `global-CLAUDE.md` into `~/.codex/AGENTS.md`
  (global) or the repo's `AGENTS.md` (per-project). Append under a
  `# Global steering` header; don't replace existing work content.
- **Kiro**: steering is per-project — drop a copy as
  `.kiro/steering/global-steering.md` in each repo that should carry it.

If the work machine's layout settles (e.g. a work AGENTS.md with a marked
steering section), a merge-aware installer can replace this manual step.
Long-term, the ssot-agents compiler (separate repo) is the real answer for
compiling one source of truth to Claude/Codex/Kiro carriers.

Not covered — machine-local by design: `~/.claude/settings.json` permissions
and hooks, plugin installs (including the superpowers SessionStart guard, see
TRACKER), and auto-memory directories. The `validators/` and `artifacts/`
trees ride the repo itself and need no install step.
