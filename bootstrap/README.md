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

Not covered — machine-local by design: `~/.claude/settings.json` permissions
and hooks, plugin installs (including the superpowers SessionStart guard, see
TRACKER), and auto-memory directories. The `validators/` and `artifacts/`
trees ride the repo itself and need no install step.
