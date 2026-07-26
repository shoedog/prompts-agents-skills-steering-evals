# Operator-fix protocol (S5 draft — operational doc, catalog: agent-success-modes-2026-07-25.md)

Scope: an implement run ends at its attempt bound (or REJECT) with findings that are CLOSED
and ENUMERABLE (see S1: each finding names input/state + incorrect result + bounded fix).
Open-class findings do NOT enter this protocol — they escalate to spec/design.

## Rules

1. **Fix on the agent's artifact, never a fresh start.** The clone keeps the agent's commit
   untouched; operator fixes land as SEPARATE commits on top (exception: pipeline convention
   requires amend — then the review input must say exactly what was amended and why).
2. **Provenance tiers, named per commit:** `agent` / `operator` / `debug-agent`. No
   laundering: a fix authored during adjudication is `operator` even if trivial.
3. **Four host gates with durable evidence before any review:** fmt, clippy, build, test —
   each gate's full output to its own log ending in an `EXIT <code>` line, plus a STATUS
   file, under `w2-tasks/<task>-verify/`. The wrapper must propagate the real exit code
   (`ov=$?; ...; exit $ov` — the echo-tail swallowing the code is a documented lapse).
4. **Review input discloses provenance and directs scrutiny:** list every post-hoc commit,
   its author tier, and the instruction "scrutinize the post-hoc fixes hardest." Include
   `## Acceptance Criteria` (task-spec validator requires it — re-learned twice).
5. **Scoped review, not ceremony:** targeted fixes get implement-review-light scoped to the
   fix diff; full two-reviewer only when the fix touches the deliverable core.
6. **Merge mechanics:** `git fetch <clone> <branch>` + `cherry-pick -n FETCH_HEAD` +
   `commit -C FETCH_HEAD --reset-author` per commit, agent's then operator's, preserving the
   commit split. Rebuild the pipeline binary after merge. Retain the clone (provenance)
   until the owner's reap policy says otherwise.
7. **Cap discipline applies here too (S8):** declare how many fix rounds before starting
   (default: ONE targeted fix round; a second only if the review's new findings are again
   closed+enumerable AND smaller). Reviewer findings that grow or shift class ⇒ stop, park,
   escalate.

## Review-input template block

```
## Provenance
- <sha1> — agent (original artifact, untouched)
- <sha2> — operator: <one-line what/why>          [tier: operator]
- <sha3> — debug-agent + operator: <what/why>      [tier: debug-agent]
Reviewers: scrutinize the post-hoc commits hardest; the original commit already
survived <verify state / prior review state>.
```

Evidence base: 6/6 targeted fixes merged clean 2026-07-25 (W2a, W2d, W2a-2, W2c,
cleanup-1); every review engaged the disclosed fixes specifically; the one spec-authorship
error (W2b v2 addendum) was caught BECAUSE authorship was disclosed.
