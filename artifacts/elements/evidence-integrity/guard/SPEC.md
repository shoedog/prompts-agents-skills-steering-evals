# bash_evidence_guard — spec v2 (panel-folded, 2026-08-08)

Weekly-triage sign-off items 4 (truncated-test-output, E1) and 5
(false-PASS / status-loss, E2), owner-approved 2026-08-08. One validator,
three carriers (claude, codex, kiro), following `validators/brief_lint.py`'s
tri-platform shape — with the wire-contract corrections below (both of
brief_lint's warn paths turned out to be defective or stale; see §7).

Panel provenance: spec v1 reviewed by three lanes 2026-08-08 —
codex/sol xhigh (`mining/out/guard-review/sol-review.md`), opus5
(kiro/claude lane, transcript-archived), claude-code-guide (docs lane).
Every rule and contract below carries its lane attribution. v1's core
design was rejected by both review lanes (whole-string matching); v2's
stage-aware core is the panel's joint requirement.

## 1. Motivating incidents (unchanged from v1)

- `608a7a2a…jsonl:3364` — 15-campaign runner `| tail -8`: PASS/FAIL lines
  destroyed, pipeline exit = tail's. (E1)
- `9aea8b01…jsonl:289` — "captured the last 40 lines, never saw the
  reviewer's verdict". (E1)
- `225b97db…jsonl:4499` — `cargo test -p historical-backfill 2>&1 | tail -25`
  as the independent suite verification. (E1)
- `fb80415b…jsonl:13598-13608` — `set -euo pipefail` script; `( cd …;
  shasum … )` subshell failed; later `forensic_capture=PASS` sentinel
  printed anyway (zsh/eval context). (E2 — note: NO pipe involved; v1's
  pipe-shaped E2 pattern did not match this incident. Both lanes caught it.)

## 2. Core algorithm — bounded stage-aware scanner (REQUIRED; both lanes)

Whole-string trigger∧allowance matching is rejected: allowances anywhere in
the command suppressed real violations elsewhere (opus WRONG-1: a
`--collect-only` on line 1 suppressed a genuine `pytest | tail` on line 2),
and pipes belonging to other list elements false-positived (sol W3 / opus
WRONG-2: `make test && git log --oneline | head -20` must NOT fire).

Scanner (still not a full parser — bounded, auditable):
1. Blank heredoc bodies (`<<-?'?WORD'?` … `^WORD$`) before anything else
   (opus SMELL-A).
2. Split into top-level LIST elements at `;`, `&`, `&&`, `||`, newline —
   quote-, escape-, `$()`/backtick-, and `()`-depth-aware. Record each
   element's following/preceding separators (for `|| true` shapes if ever
   revisited — currently dropped, §4).
3. Split each element into PIPELINE stages at `|` and `|&` (sol W6 / opus
   WRONG-4; `||` is NOT a pipe). `|&` implies 2>&1.
4. Per stage: normalize an absolute-path or `env VAR=…`-prefixed command
   word to its basename (sol W6). Detect redirects (`>`, `>>`, target
   token), quoted spans, substitutions.
5. RECURSE (depth ≤ 2) into executable string arguments instead of
   stripping them (sol W2 / opus WRONG-5 — `bash -lc "pytest -q | tail -5"`
   must fire): shell wrappers `bash|sh|zsh|dash [-l] -c`, `ssh HOST "cmd"`,
   `docker exec … CMD`, `xargs`, `timeout`, `env`, `nice`, plus `$( … )`
   and backtick bodies. Quoted spans that are NOT such arguments stay
   data (the corpus-proven `grep -rn "cargo test" | head` non-fire holds).
   Design note (opus): the mining detector optimizes for false-positive
   freedom; this guard optimizes for false-negative freedom — sharing
   `strip_quoted` verbatim conflates the two loss functions.

## 3. Rule E1 — truncated-test-output (item 4)

FIRE when, within ONE pipeline: a runner stage is followed by a
destructive filter stage, and no allowance applies TO THAT PIPELINE.

Runners (v1 set + panel additions; sol W7, opus runner-gap table):
`pytest` (incl. `python -m pytest`, `uv run pytest`, `poetry run pytest`),
`python -m unittest`, `cargo test`, `cargo nextest run` (NOT bare
`cargo nextest` — `cargo nextest list` false-positived, sol W7),
`npm|pnpm|yarn|bun [run] test`, `npm t`, `vitest`, `jest`, `go test`,
`gotestsum`, `mvn test|verify`, `./mvnw test`, `gradle|./gradlew test`,
`make [-flags] [-C dir] test|check`, `just test`, `tox`, `nox`, `ctest`,
`swift test`, `dotnet test`, `deno test`, `flutter test`, `bazel test`,
`rspec`, `rake test`, `phpunit`, `mix test`, `verify-mutation-gates`.

Destructive filters (basename-normalized, same pipeline, downstream of
runner): `head`, `tail`, `grep -c`, `grep -q`, `grep -m N` (sol table),
`wc -l` (opus; drains everything, keeps a count). DEFERRED as an open
class, do not ship in v1: `sed -n`, `awk NR<=`, bare `grep PATTERN`
(usually preserves the totals line — opus).

Allowances — scoped to the RUNNER'S OWN STAGE/PIPELINE only (sol W4, opus
WRONG-1/3):
- non-run forms on the runner stage, runner-specific: `cargo test
  --no-run`, `cargo nextest list`, pytest `--collect-only|--co`, ctest
  `-N|--show-only`, jest `--listTests`, generic `--help|-h|--version|-V|
  --list|--list-tests|--dry-run` on the runner stage;
- the runner stage redirects stdout to a file: `> path`/`>> path` where
  path is not `/dev/null`, `/dev/fd/*`, or `-` (call it a "capture path",
  never "durable" — syntax can't prove durability, sol W4);
- `tee FILE` as the FIRST consumer of the runner's output, before any
  destructive filter, FILE not a discard sink (opus WRONG-3:
  `npm test | tail -40 | tee f` preserves only the surviving 40 lines —
  MUST fire; `cargo test | tee /dev/null | tail -25` MUST fire, sol W4).

An E1 capture allowance NEVER suppresses E2 evaluation (both lanes:
`cargo test >full.log 2>&1 | tail -25` → E1 quiet, E2 status note).

## 4. Rule E2 — false-PASS / status-loss (item 5) — ONE rule + one note

Panel verdict: v1's three patterns were one incident-mismatched pattern
and two unevidenced ones. Consolidated (opus "E2 should be one rule";
sol W5 + S1-S3):

- **E2a (the incident rule):** `set -e`/`errexit` present AND a command
  runs inside a subshell/`$( … )`/backticks — OR inside a pipeline with
  `pipefail` absent — AND a later list element emits a PASS/OK/SUCCESS-
  shaped sentinel (`PASS`, `OK`, `SUCCESS`, `passed`, `green` inside an
  echo/printf). The `pipefail`-absent condition gates ONLY the pipeline
  branch: pipefail is irrelevant to the subshell mechanism, and the real
  incident ran under `set -euo pipefail` (v2.1 correction — the v2 wording
  required pipefail-absence globally and thereby missed its own motivating
  incident; caught by the build lane's fixture note). Message: the
  sentinel is not gated on the step's status; under eval/dialect contexts
  `set -e` may not stop the script — gate the sentinel on an explicit
  status check. Traces to `fb80415b:13598-13608`.
- **E2b (status note):** a runner pipeline whose final stage is not the
  runner (piped into ANYTHING, incl. `tee`), without `pipefail` /
  `PIPESTATUS` / `pipestatus` recovery → note "the pipeline's exit status
  is the last stage's, not the runner's" (sol's tee-status finding;
  empirically `false | tee f` exits 0). Suppressed when E1 already fired
  on the same pipeline (one message per pipeline).
- **DROPPED:** `$?`-captured-then-/dev/null (both lanes: imprecise, no
  incident trace; sol showed textually-identical commands with opposite
  status outcomes). `runner || true` / `; true` (opus: standard
  inspect-the-log idiom, zero incident trace — steering prose at most).

E2 is permanently warn-only. State the carrier asymmetry honestly: after
the C1/C2 fixes claude's warn is model-visible; kiro's warn is USER-visible
only (kiro has no model-visible non-blocking channel — opus §1.4).

## 5. Wire contracts (panel-verified; supersede brief_lint's docstrings)

### claude `--hook` (verified against shipped 2.1.225 binary — opus C1-C3)
- WARN: `{"systemMessage": …, "hookSpecificOutput": {"hookEventName":
  "PreToolUse", "additionalContext": "<findings + exact corrected
  command>"}}` — NO `permissionDecision` field AT ALL. Rationale:
  `allow`+reason is (a) invisible to the model and (b) AUTO-APPROVES the
  command, bypassing the normal permission prompt — a safety regression
  (`pytest -q | tail -5 && rm -rf ~/scratch` would skip its prompt).
  Never use `defer` (print-mode only).
- DENY (later, project-scoped): `permissionDecision: "deny"` +
  `permissionDecisionReason` (model-visible on the deny path).
- Timing honesty: additionalContext reaches the model NEXT request (beside
  the tool result) — warn never saves the wasted run; only deny does.
- Matcher `"Bash"` is EXACT match (binary-verified); does not catch
  BashOutput/KillShell. Keep tool_name self-check anyway.
- Merge semantics: user+project hooks all run; deny > defer > ask > allow;
  async hooks can't decide. Purely additive mount next to moshi-hooks.

### codex `--codex-hook` (verified vs installed 0.146.0 + release docs — sol §W1)
- tool_name is `Bash` (both legacy shell and unified exec_command);
  command in `tool_input.command` (STRING). Matcher: `^Bash$` (regex).
- WARN: `systemMessage` + `hookSpecificOutput.additionalContext`. NEVER a
  bare `permissionDecision: "allow"` — on codex that is the input-rewrite
  path and errors without `updatedInput`.
- DENY: supported (brief_lint's "codex cannot deny" is STALE — sol
  verified the deny branch in the installed binary):
  `permissionDecision: "deny"` + non-empty reason. Do not use
  `continue: false`.
- execpolicy is CONFIRMED not a carrier: `bash -lc 'cargo test | tail'`
  matches zero prefix rules (sol ran 8 empirical cases).

### kiro `--kiro-hook` (verified via binary strings + live `kiro-cli agent
validate` probes + docs — opus §1)
- Agent-config key: `hooks.preToolUse` (object form, snake_case fields;
  closed trigger enum). Matcher is a typed String, regex-on-tool-name per
  docs; anchoring UNVERIFIED → ship alternation
  `execute_bash|executeBash|execute_cmd|executeCmd|shell` PLUS in-script
  self-filter on those names (case-insensitive). Command field: `command`.
- Exit contract: 0 allow; 2 block + stderr TO THE MODEL (kiro's only
  model-visible channel); other nonzero = user-facing warning, tool runs.
- Consequences: kiro warn is a note to the human, not the model; kiro
  contributes NO evidence to the warn→deny gate. `kiro-cli agent validate`
  is lenient (unknown keys pass; bad entries silently dropped at load) —
  only a live fire proves a mount.
- Coverage limits (documented, not solved here): hooks bind to the ACTIVE
  agent config (`enforced` must be selected); repo-level agent configs
  SHADOW the global one (guard must ride each repo's config); hooks do not
  fire inside kiro native subagents.
- OPEN (5-min smoke before relying on it): whether preToolUse stdout is
  injected as model context like UserPromptSubmit's is.

## 6. Fire log, escape hatch, rollout (opus WRONG-7, SMELL-D; sol §6)

- EVERY evaluated command containing a runner stage appends one JSONL row:
  `{ts, carrier, cwd, command, rule: "E1"|"E2a"|"E2b"|null,
  decision: "warn"|"deny"|"clean"|"escape"}` to
  `~/.claude/logs/bash-evidence-guard.jsonl` (env
  `BASH_EVIDENCE_GUARD_LOG` overrides; log failures never break the hook).
  `clean` rows are the denominator that makes "zero warns" interpretable
  (warn-worked vs pattern-evaded vs nobody-ran-tests).
- Escape hatch: a literal `# evidence-ok: <why>` trailing comment → allow,
  log decision "escape". A deny with no one-step out invites
  pattern-mutation evasion.
- Rollout: ALL carriers warn-only in v1. User-global claude mount stays
  warn PERMANENTLY (blast radius: every repo, incl. ones where `make
  check | head` is legitimate). Deny flips, if any, land per-project in
  tracked `.claude/settings.json` files, and only for repos whose runner
  vocabulary the fixtures cover. Flip review: after 2 weekly reports, using
  fire-log FP rate + denominator — declared now per convergence
  discipline. Kiro: excluded from gate evidence (warn inaudible); owner
  may choose direct deny with logging instead.

## 7. brief_lint.py fixes riding this pass (both lanes; live mounts affected)

1. `hook_mode()` (claude): same C1+C2 defect — swap
   `permissionDecision: "allow"` + reason for additionalContext-only warn.
2. Codex docstring + self-test: "cannot deny" claim is stale (0.146
   supports deny); warn-only remains the chosen policy, restate as policy.

## 8. Deliverables

- `validators/bash_evidence_guard.py` — self-contained (no repo imports;
  /usr/bin/python3 3.9-compatible), stage-aware core, E1+E2, four modes
  (`--hook`, `--codex-hook`, `--kiro-hook`, `--cmd`), `--self-test` with
  embedded wire-contract fixtures, fire-log + escape hatch.
- `mining/tests/test_bash_evidence_guard.py` — pytest suite carrying the
  FULL panel fixture matrix (every concrete command in both review files,
  as positive or anti-finding), plus the three adapter contracts against
  synthetic payloads.
- Mount snippets + this spec in `artifacts/elements/evidence-integrity/`
  (mounts are ADDITIVE edits preserving existing entries verbatim —
  the moshi-hooks temp-path strings must survive byte-identical).
- brief_lint.py C1/C2/stale-docstring fix + its self-test update.
