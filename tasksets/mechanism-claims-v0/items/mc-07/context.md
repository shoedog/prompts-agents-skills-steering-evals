# backfill CLI: archive subcommands + session handoff doc

A hand-rolled argument loop parses global flags, then dispatches on the
subcommand name. `next_value` pulls a flag's value from the arg iterator.
Subcommands: `verify-archive` (read-only archive verification),
`load-canonical` (loads a candidate revision), `adjudicate-canonical`
(adjudicates a loaded candidate).

Contract:
- Flags that only make sense for some subcommands must be rejected for the
  others at parse time, with an error naming the accepting subcommands.
- `docs/RESUME-archive.md` is the session handoff: its "Next step
  (runnable now)" section must be executable exactly as written — the next
  session starts by running it.
- The diff adds `--rebuild-index` and `--emit-report`, their acceptance
  rules, and the handoff's next-step section.
