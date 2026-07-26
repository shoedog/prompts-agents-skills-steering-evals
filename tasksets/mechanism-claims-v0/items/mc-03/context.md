# backfill CLI: canonical-data subcommands + session handoff doc

A hand-rolled argument loop parses global flags, then dispatches on the
subcommand name. `next_value` pulls a flag's value from the arg iterator.
Subcommands: `load-canonical` (loads a candidate revision from frozen
inputs), `adjudicate-canonical` (adjudicates a loaded candidate),
`audit-canonical` (read-only replay/audit of a failed candidate).

Contract:
- Flags that only make sense for some subcommands must be rejected for the
  others at parse time, with an error naming the accepting subcommands.
- `docs/RESUME-g4c.md` is the session handoff: its "Next step (runnable
  now)" section must be executable exactly as written — the next session
  starts by running it.
- The diff adds the `--spinoff-binding` flag, its acceptance rule, the
  `audit-canonical` dispatch arm, and the handoff's next-step section.
