# Phase 5 prep: verification-schema-check Stop hook (PREPARED, NOT ENABLED) — 2026-07-25

Owner decision flagged in TRACKER. To enable warn-only checking at session stop in
stockTrading and ssot-agents, add this `"Stop"` key to the existing `"hooks"` object in each
repo's `.claude/settings.json` (both verified 2026-07-25 to have only the `PreToolUse`
brief-lint entry):

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "/usr/bin/python3 /Users/wesleyjinks/code/prompts-skills-steering/validators/verification_schema_check.py --hook || true",
        "timeout": 15,
        "statusMessage": "verification-schema-check (warn-only)"
      }
    ]
  }
]
```

Update (2026-07-25, later): the validator now HAS a `--hook` mode, mirroring brief_lint's
hook contract. It reads the Stop payload JSON on stdin, takes the repo from the payload
`cwd`, checks the VERIFICATION.md files that exist under it (bounded: git-tracked at any
depth via one `git ls-files` index read, plus a depth-<=2 glob that skips dot dirs; capped
at 20 files), prints findings concisely to stderr, and ALWAYS exits 0 — including on
malformed payloads, missing/invalid cwd, and internal errors (all self-tested). Quiet when
clean: zero output when there is nothing to say. Positional/`--strict` CLI behavior is
unchanged (diffed byte-identical against pre-change captures).

Warn-only twice over — why `|| true` stays: the script exits 0 by construction in `--hook`
mode, but the residual failure class is AROUND the script, not in it. Verified 2026-07-25:
`/usr/bin/python3` exits **2** if the validator file is ever moved/renamed ("can't open
file"), and argparse exits **2** on a mistyped flag in this command line. Exit 2 is the one
code that BLOCKS a Stop hook and feeds stderr to Claude — the exact thing this patch must
never do. `|| true` converts that whole class to exit 0 while stderr still passes through
untouched, at zero cost. Full output, no truncating pipes.

Caveats before enabling (updated after the `--hook` build; old caveats 1-3 resolved):
1. RESOLVED — timing. Measured read-only with real Stop payloads (`{"cwd": "<repo>",
   "hook_event_name": "Stop", ...}` on stdin), 3 runs each, 2026-07-25: stockTrading
   (855 tracked files) 0.03-0.05s wall; ssot-agents (557 tracked files) 0.03s wall.
   Three orders of magnitude under the 15s timeout.
2. RESOLVED — quiet when clean (self-tested). BUT: as of today BOTH repos' root
   VERIFICATION.md has live findings (stockTrading: 3x S2 unlinked totals + S3 no
   provenance; ssot-agents: S2 + S3). Enabling now prints those warnings at every stop
   until the docs are fixed — fix or knowingly accept them first, or the always-on warn
   trains people to ignore it.
3. RESOLVED — `--hook` exists; the "tighter integration" option (only files the session
   touched, via the transcript path) remains unbuilt and is a prompts-skills-steering
   change if ever wanted.
4. Both repos keep `/VERIFICATION.md` in `.git/info/exclude` (checked: `.git/info/exclude:7`
   in each). Discovery was built for that: `git ls-files --others --exclude-standard` would
   MISS the very file this hook exists to check; the depth-<=2 glob leg catches it.
5. Hook mode checks only files that EXIST — there is no S0-missing finding in `--hook`
   (unlike positional mode). This hook does not enforce that a VERIFICATION.md gets
   written at all; that enforcement stays with the exp-2 Stop-gate.
6. Findings go to stderr with exit 0: non-blocking hook output (transcript/verbose view),
   never a stop-block or a prominent banner. If more prominence is ever wanted, printing to
   stdout is a one-line validator change — decide that after living with warn-only.
7. `--self-test` now covers hook mode (synthetic Stop payloads: clean, dirty, empty dir,
   malformed); passes 2026-07-25 on `/usr/bin/python3` (3.9.6, the interpreter pinned
   above). Rerun it the day you enable.
