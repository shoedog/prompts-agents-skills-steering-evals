# quant-platform — pacing retrospective + concurrent-agent coordination design

Date: 2026-07-17. Follow-up to item 2 (`[A1][F1]`) of
[`stocktrading-roadmap-2026-07-17.md`](stocktrading-roadmap-2026-07-17.md), plus the
owner's pacing question. Evidence base: read-only inspection of
`~/code/stockTrading` at branch `feat/layer6-a3-canonical-load` (HEAD `d7474d5`,
2026-07-13 05:25, 134 dirty/untracked files), the full git history across all
branches, the 138-session Codex transcript digest (2026-06-12 → 2026-07-17), the
A-3 plan/spec/ADR corpus, and the actual interlock code in the working tree
(`family_lock.rs`, `activate.rs`, `benchmark_authorization.rs`, migration 0003).
Nothing in quant-platform was modified.

---

# Part 1 — Pacing retrospective

## Verdict

**The slow pace is predominantly a process/tooling problem, not inherent domain
difficulty — weighted roughly 75/25.** The domain-hard part (ticker reuse,
restatement collisions, corporate-action identity) is real, and when the team was
actually executing it moved *fast*: the entire A-2 identity foundation landed in
one day, the A-3 spec/plan/implementation in two more. What consumed the calendar
was (a) a 28-day dead zone with zero commits and zero sessions, (b) measured
approval idle time of minutes-waiting-per-seconds-executing inside every active
session, and (c) coordination friction (an admitted handoff redo, a stalled
commit pipeline, build-dir contention). None of those three has "the data is
hard" as its fix.

## The calendar, decomposed

Total elapsed 06-13 → 07-17: **34 days**.

| Window | Days | What happened | Evidence |
|---|---|---|---|
| 06-13 → 07-10 | ~28 (82%) | **Nothing.** Zero commits on any branch (`git log --all`), zero Codex sessions after one isolated 06-13 design review. | Transcript digest timeline; git history |
| 07-10 → 07-11 | 1 | Vendor decision (Sharadar SFA, NDL $79/mo, decision-log addendum dated 2026-07-10). Then **20 commits on 07-11 alone**: full A-2 identity slice (migration 0002 → G12 SP500 gate → three code-review rounds closed), plus A-3/A-4/sleeves spec DRAFTs. | `risks-and-decisions.md` addenda; commit log |
| 07-11 → 07-13 05:25 | ~2 | A-3 adversarial spec/plan reviews (5+ rounds, design-duel synthesis) then ten implementation batches: control plane, policy sources, determinism-pin protection, visibility, gates G1–G7, CAS activation. Last commit on the branch. | Commit log 07-12/07-13 |
| 07-13 → 07-17 | ~4 | Real-data load campaign, entirely uncommitted: source cohorts r1–r4, revision burns 1–5, GP1/GP2, G12 backlog resolution, **18 new ADRs (0038–0055)**, 35 dirty doc paths, evidence artifacts. Revision 5 materialized 46,182,413 bars + 558,598 actions, WAL-converged, then was operator-interrupted nonterminal. | Working-tree `git status`; ADR files; plan-doc cursor |

Two observations fall straight out of the table:

1. **82% of elapsed time was the gap, and the gap was not data difficulty** — no
   data existed yet. The 06-12 platform analysis already named the vendor
   shortlist with prices ("Norgate ~$30–60/mo or Sharadar via NDL"); the $79
   commitment happened 28 days later, and work resumed the next day at very high
   velocity. **Confirmed cause (owner, 2026-07-17): Claude Fable access was
   pulled over a US-government-related issue and took a few weeks to get
   reinstated, compounded by the Sharadar purchase itself failing over mobile
   checkout until the owner completed it on desktop.** Neither cause is
   data-ingestion difficulty, and neither is a decision the owner delayed —
   both are external-tool-availability and purchase-flow friction. Recovering
   this lever going forward means a faster fallback when a primary agent's
   access is interrupted (not "decide faster") and trying an alternate
   purchase channel sooner when the first one silently fails.
2. **When work ran, throughput was near-ceiling.** A-2 (identity DDL through
   PIT resolution through three review rounds) in one day is not "slow pace";
   neither is spec→plan→ten implementation batches in two days.

## Inside the active days: what was inherent, what wasn't

**Inherent and handled well (the ~25%).** The hard identity cases genuinely
required primary-source research: RSII (Reckson vs RSI Holdings, transition date
still unresolved), GNCI/GCOR/GCRX (Gencor vs General Nutrition), CDG (hypothesis
stated, then falsified next session), INFQ/CCCXU (two permaticker classes),
SOND (GP1 indexed only `current_ticker` — a real reuse-driven matching bug),
TDACU (validator scoped globally instead of by-date). The adversarial gate
process was built to catch exactly this class and did, repeatedly: cross-vendor
duplicate actions, inverted date intervals, non-positive permatickers, blank
tickers, forged GP1 test bindings. The G12 SP500 backlog is the flagship case:
59,667 rows → 1,971 distinct pairs → 1,007 resolved, and the remaining 964 were
root-caused to a resolution-logic bug (PIT trading-symbol resolution applied to
a canonical/restated-symbol feed) instead of being papered over with 964 manual
mappings. Five burned revisions for one frozen source run — including revision 1
lost to a digest type-confusion (ADR-0052) — is the immutable-attempt design
working as specified, not thrash. This is expected difficulty, discovered by
process, resolved with evidence. It cost days, and those days were well spent.

**Not inherent (the ~75%):**

- **Approval idle time — the single dominant in-session sink.** The agent's own
  instrumentation: *"~724 seconds awaiting approval, then ~10 seconds
  executing… ~1,670 seconds awaiting approval, then ~0.4 seconds executing.
  Narrow persistent approvals… would eliminate most idle time."* That is
  98–99% idle in the instrumented probes. The owner raised it at least three
  times ("could it be because i have to grant approval for each command and let
  it sit there?" / "well there are a lot of commands to approve") and it was
  still recurring on 07-17. This is a settings change, not an engineering
  project — Part 2C below.
- **The 07-13 handoff redo.** Verbatim: *"I should have been more clear to have
  you run it instead of resuming claude… I'd like you to takeover."* An
  orchestration-clarity miss, admitted as such; every subsequent session replays
  that seed conversation.
- **The commit pipeline stalled for four days.** The a2a-bridge protocol has
  agents stage changes and write `.git/A2A_COMMIT_MSG` for the bridge to commit;
  `.git/A2A_TASK.md` in the tree is stale at Jul 13 05:08 and one session opened
  blocked because the task file was simply absent. Result: 18 ADRs, the decision
  log, evidence artifacts, and the interlock code itself exist only as dirty
  working-tree state — four days of decisions one bad `git` command away from
  loss, and unreviewable as diffs.
- **Environment contention as recurring manual labor:** "Blocking waiting for
  file lock on artifact directory," persistent shared-Cargo-target stalls (the
  A2A task file itself says "use a fresh CARGO_TARGET_DIR if the shared one
  stalls" — a per-incident workaround for a policy-shaped problem), and ≥10
  near-verbatim disk-reclamation requests across 07-13→07-17.

## What changed since `platform-analysis-2026-06-12.md`

Closed or materially advanced:

- **P1 first half (real history) — the big one.** Sharadar purchased (07-10);
  A-1 acquisition crate, A-2 permaticker/PIT identity ledger, and A-3 canonical
  load are built; revision 5 has the full ~1998→present SEP-all + SFP-SPY
  materialized (46.18M bars, 558.6k actions) awaiting exact resume + activation.
  The analysis asked for survivorship-free multi-year data; it now physically
  exists behind a fail-closed control plane the analysis never asked for
  (pointer-flip serving, immutable revisions, Ed25519 N-of-N activation
  authorization) — scope growth, but scope that matches the repo's stated
  invariants.
- **P5 partially:** G12 SP500 identity resolution is green for r4; A-4 PIT
  universe is spec'd (review round 3) but not built.
- Strategy-expansion sleeves (the analysis's §7) have a reviewed DRAFT spec.

Still open, unchanged since 06-12: walk-forward harness and benchmark-relative
metrics (P1 second half), automated loss halts (P2), broker reconciliation (P3),
live observability/DR/key rotation (P4), tax modeling, and — per roadmap item 1 —
**the analysis itself has still never been promoted into
`risks-and-decisions.md`: a grep today finds zero references**, while 21 new
ADRs (0035–0055) landed for A-3 alone. The decision-log discipline is alive and
excellent *for the work in flight*; the advisory-analysis intake path remains
broken.

## What better planning would actually have changed

1. Vendor commitment in the same week as the analysis → the whole arc shifts
   ~4 weeks left. Largest single lever — but per the confirmed cause above,
   not a decision-latency fix: a fallback path for when the primary agent
   (Fable) loses access, and trying desktop checkout as soon as mobile
   checkout stalled instead of after weeks blocked on it.
2. A pre-approved command allowlist from day one of the campaign → recovers the
   dominant share of in-session wall clock (Part 2C).
3. Worktree/target-dir isolation and a mandatory commit cadence from the 07-13
   handoff onward → eliminates the contention labor and the four-day
   uncommitted-state exposure (Part 2B).
4. The adversarial review rounds and the burned-revision retries should **not**
   be planned away — they are the mechanism that caught the forged GP1 bindings,
   the 964-mapping mistake, and the digest type-confusion. Budget for them.

---

# Part 2 — Coordination design: mechanical interlock + concurrent-agent protocol

## What already exists (do not rebuild)

The working tree already mechanizes more than the roadmap item assumed. Any
implementation should slot into this, not duplicate it:

- **Migration `0003_market_data_control_plane.sql`:** immutable
  family/version/coverage/gate/failure/verification/event relations with
  `BEFORE UPDATE OR DELETE` rejection triggers; gate↔failure mutual-exclusion
  triggers that take an xact advisory lock on `(family,revision)`; one mutable
  pointer row, CAS-updated only.
- **`canonical/family_lock.rs`:** detached-session Postgres advisory lock
  (`pg_try_advisory_lock(hashtextextended('quant-platform/a3/canonical-family-lock/v1' + family))`)
  held across the loader protocol; xact-scoped variant for activation.
- **`canonical/activate.rs`:** CAS flip requiring locked pointer read, gate
  attestation present, no failure attestation, expected-active-revision match.
- **`canonical/benchmark_authorization.rs`:** Task-20 activation requires N-of-N
  detached Ed25519 signatures from reviewer keys compiled into the exact clean
  CI-tested build.
- **ADR-0052** (prose + loader code): exact-resume rules — an unattested newest
  revision resumes exactly; a gated newest revision verifies exactly; either
  blocks successor allocation for the same source run; retry allocates
  `MAX(revision)+1` only when every predecessor is failure-attested.

## The actual residual gap

The live execution cursor — *"the next live boundary is an exact revision-5
resume… revision 6 must not be allocated… every production activation step
remains blocked"* — lives only in a **prose section of an uncommitted plan
document** (`docs/superpowers/plans/2026-07-12-slice-a3-canonical-load.md`,
lines 13–28). Concretely exploitable failure modes today:

1. **The failure-attestation hole.** Nothing stops any agent or psql session
   from inserting a failure attestation for revision 5 (the triggers only
   enforce gate/failure mutual exclusion, not *authorization to declare
   failure*). The moment that row exists, ADR-0052 **legally unblocks
   allocation of revision 6** — silently forfeiting the durably materialized
   46.18M-bar revision the cursor says must be resumed. An agent that
   reasonably concludes "operator interrupt ⇒ failed attempt" does the wrong
   thing through entirely legitimate code paths.
2. **ADR-0052's history rules are application-code-only.** A second binary
   version, a different agent's reimplementation, or manual SQL can insert
   version rows the ADR forbids; the DB accepts anything trigger-consistent.
3. **The cursor prose is mutable by any agent** editing the plan doc, and is
   currently not even committed.
4. **No concurrent-agent protocol at all** in `agent-collaboration.md` — it
   covers humans (branching, PR style, pre-flight checks) and says nothing
   about two agents sharing a working tree, a build cache, a dev-stack DB, or
   the activation state machine. The incidents already on record: missing
   `.git/A2A_TASK.md` blocking a session; artifact-directory file-lock waits;
   shared Cargo target contention; four days of uncommitted shared state.

## 2A — The mechanical interlock: an execution-cursor guard table

Move the plan-doc cursor into the control plane it describes. One new table in
the next `market-data-query` migration, plus three constraint triggers on
existing tables. All checks fail closed (absent/corrupt cursor row ⇒ reject),
matching the repo's stated posture.

```sql
CREATE TABLE reference.market_data_execution_cursor (
  family      TEXT PRIMARY KEY
              REFERENCES reference.market_data_family(family),
  mode        TEXT NOT NULL CHECK (mode IN ('resume-only','open','frozen')),
  resume_revision            BIGINT,           -- exact revision that may be resumed
  allow_failure_attestation  BOOLEAN NOT NULL DEFAULT false,
  allow_pointer_flip         BOOLEAN NOT NULL DEFAULT false,
  reason      TEXT NOT NULL,                   -- human-readable, mirrors old prose
  set_by      TEXT NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((mode = 'resume-only') = (resume_revision IS NOT NULL))
);

-- Append-only audit of every cursor change (same immutability triggers as the
-- other control-plane relations).
CREATE TABLE reference.market_data_execution_cursor_event ( … old/new/reason/set_by/at … );
```

Seeded for the current state:
`('sharadar-historical','resume-only', 5, false, false, 'r5 WAL-converged, operator-interrupted; exact G1–G7 resume only; Task-20 evidence outstanding', 'operator')`.

**Trigger 1 — revision allocation guard** (`BEFORE INSERT ON
reference.market_data_version`): read the family's cursor row `FOR SHARE`;
reject when the row is absent, `mode = 'frozen'`, or `mode = 'resume-only'`
(resuming revision 5 inserts no version row, so resume is unaffected; allocating
revision 6 is impossible until the operator flips the cursor to `open`).
Additionally encode ADR-0052 rule 2 mechanically, independent of loader code:
reject when any earlier revision for the same `(family, source_run_id)` lacks a
failure attestation, and reject when any predecessor is gate-attested (at most
one live candidate per source run — currently only enforced in `load.rs`).

**Trigger 2 — failure-attestation guard** (`BEFORE INSERT` on the failure
table, after the existing mutual-exclusion trigger): when the cursor is
`resume-only` and `NOT allow_failure_attestation`, reject with an error naming
the cursor (`EXECUTION_CURSOR_FORBIDS_FAILURE_MARK: sharadar-historical is
resume-only on revision 5; operator must set allow_failure_attestation`). This
closes hole 1: declaring the resumable revision dead becomes an explicit
operator act, not an agent inference.

**Trigger 3 — pointer-flip guard** (`BEFORE UPDATE ON
reference.market_data_serving_pointer`): reject when `NOT allow_pointer_flip`.
Belt-and-suspenders under the existing CAS + Ed25519 authorization: the
signature machinery proves *who authorized*; the cursor encodes *whether the
state machine is at a flip boundary at all*. Default `false` matches today's
"Task 20 blocked" reality.

**Cursor mutation discipline.** Cursor `UPDATE` goes through one operator CLI
verb (`historical-backfill cursor set …`) that takes the family advisory lock,
writes the audit event, and sets a session GUC
(`SET LOCAL quant.operator_intent = 'cursor-change'`) that the cursor table's
`BEFORE UPDATE` trigger requires. This is deliberately **advisory-strength, not
cryptographic**: any SQL client could set the GUC, but the threat model here is
a confused or over-eager agent taking a legitimate-looking path — the same
model as the existing family lock. The truly dangerous transition (pointer
flip) already has, and keeps, the Ed25519 gate.

**The prose cursor becomes generated output.** Replace the plan-doc section
with `historical-backfill cursor show --markdown` output (or a one-line pointer
to it). One source of truth; the doc can never silently disagree with the DB.
The loader and operator CLI print the cursor at startup and refuse verbs the
cursor forbids *before* touching data, so agents get the constraint as an
immediate, named error instead of prose they may not have read.

Sequencing (matches roadmap item 2's guidance): the migration + triggers land
**after the A-3 branch settles** (it owns these tables); the protocol doc below
lands now.

## 2B — Concurrent-agent coordination protocol

A new `## Concurrent agents` section in
`docs/00-foundations/agent-collaboration.md`, plus one small runtime mechanism.
Modeled on the proven ssot-agents ↔ a2a-bridge coordination pattern (written
contract, explicit ownership, neither party mutating the other's surface) but
lighter, because this is single-repo/multi-agent: the *contract* is a committed
doc section; the *runtime claims* live in Postgres, which every working agent
already reaches, cannot merge-conflict, and survives session restarts.

**1. Shared-stateful-artifact ownership matrix** (committed table in the doc —
the "don't touch X, it's being worked" class becomes a lookup, not tribal
knowledge):

| Artifact | Sole mutation channel | Lock/guard |
|---|---|---|
| Serving pointer | `activate` CLI CAS | family advisory lock + cursor trigger 3 + Ed25519 |
| Execution cursor | operator `cursor set` | advisory lock + GUC trigger + audit event |
| Canonical revisions (Postgres control rows + QuestDB partitions) | loader under family lock | immutability triggers + cursor triggers 1–2 |
| Frozen source snapshots / identity bindings (MinIO raw-lake) | loader, content-addressed, write-once | never overwritten; byte/digest verification on read-back |
| Evidence dir (`docs/superpowers/evidence/a3/`) | append-only by the producing session | claim (below) |
| Working tree / in-flight branch | exactly one implementing agent per worktree | claim + worktree policy (below) |
| Plan/spec/ADR docs | implementing agent for its slice; reviewers propose via review files, never edit in place | claim |
| Shared dev-stack DBs (Postgres/QuestDB containers) | schema owner per existing schema-per-service rule | read-only role for everyone else (2C) |
| Cargo target dirs | per-agent, never shared | env policy (below) |

**2. Claims table + CLI.** `reference.agent_claims (claim_id, scope TEXT,
agent TEXT, task_ref TEXT, claimed_at, heartbeat_at, released_at NULL)` with
verbs `claim / heartbeat / release / list` on the operator CLI (or a 30-line
`tools/agent-claim.sh` over psql). Rules: claim before mutating any artifact in
the matrix; scopes are coarse path/artifact prefixes (`worktree:main`,
`evidence:a3`, `db:reference.market_data_*`); a claim with a heartbeat older
than 60 min is stale and may be taken over only with an operator ack recorded
in the takeover row. Orchestrators (a2a-bridge workflows) claim on behalf of
the subagents they spawn.

**3. Task-file lifecycle fix (the missing-`A2A_TASK.md` incident).** `.git/` is
exactly the wrong home for the *authoritative* task statement: invisible to
history, lost on re-clone, absent when a session starts cold. Keep
`.git/A2A_TASK.md` / `.git/A2A_COMMIT_MSG` as the bridge's *mechanical mailbox*,
but require the authoritative task text to be a committed file under
`docs/superpowers/tasks/<date>-<slug>.md` that the mailbox copy names; a session
that finds the mailbox empty reads the newest unclaimed committed task instead
of blocking. Status transitions (QUEUED → CLAIMED → DONE, with the closing
commit SHA) are appended to the task file, so recovery from any session death is
a file read.

**4. Commit-checkpoint rule (the four-uncommitted-days incident).** The plan
already mandates "every task boundary is a compiling, green commit"; the
protocol adds the enforcement side: **no agent may start a new task batch while
a prior batch sits uncommitted in its worktree**, and the orchestrator's
end-of-batch step is stage → write `A2A_COMMIT_MSG` → verify the bridge
committed (or commit directly when running with commit rights) — a batch is not
DONE until its SHA exists. Evidence artifacts and ADRs count as batch output;
18 ADRs must never again live only as untracked files.

**5. Build/workspace isolation policy (the contention incidents).** One agent
per worktree, period; reviewers and secondary agents get read-only checkouts or
`git worktree` copies (the repo already does this ad hoc:
`/private/tmp/stockTrading-a3-capacity`). Every agent exports
`CARGO_TARGET_DIR=~/.cache/quant-target/<agent-name>` via a shared
`tools/agent-env.sh` sourced at session start — this replaces the "fresh
CARGO_TARGET_DIR if the shared one stalls" workaround with a default. Add
`tools/reclaim-space.sh` (sweep stale target dirs + dead worktrees, print
before/after) so the ≥10 manual reclamation requests become one approved
command; artifact-directory writes go under the producing agent's claim, which
serializes the writers that were previously colliding on file locks.

## 2C — Approval/permission policy

The evidence is unambiguous (724s/10s, 1670s/0.4s, unresolved after three
owner complaints), and the interlock above is what makes a broad allowlist
*safe*: pre-approval shifts the safety boundary from "a human reads every
command" to "the DB refuses every forbidden state transition" — which the
control plane now enforces better than a tired human skimming his hundredth
prompt of the night. The two must ship together; an allowlist without the
cursor triggers genuinely would be a new safety gap for the failure-attestation
hole above.

**Pre-approve (persistent, per-project — Codex approval policy /
`.claude/settings.json` allowlist, and the same list handed to the a2a-bridge
approval-assessment agent so the third-process-in-the-loop stops re-deciding
trivia):**

- Read-only filesystem/repo: `ls`, `cat`, `head`, `tail`, `wc`, `grep`/`rg`,
  `find`, `git status/log/diff/show/branch/worktree list` (no mutating git).
- The scoped verification loop, exactly as the plan names it:
  `cargo check --workspace`, `cargo test -p <pkg> …` (including
  `-- --ignored --test-threads=1` forms), `cargo clippy -p <pkg> --all-targets
  -- -D warnings`, `cargo fmt --all -- --check`, `uv run pytest|ruff|mypy`.
  These dominate the TDD red/fix/green loops that the transcripts show
  repeating across sessions; they mutate only per-agent target dirs.
- Read-only DB probes **via a dedicated role**: create `quant_agent_ro` with
  `SELECT`-only on the `reference` schema (and other service schemas as
  needed); agents' diagnostic psql runs as that role, so arbitrary SELECTs are
  blanket-approvable because writes are impossible at the DB, not at the
  prompt. Caveat to state in the doc: QuestDB OSS has no role separation — its
  HTTP `/exec` can run DDL — so QuestDB queries stay behind a thin read-only
  wrapper script (allowlisted) or remain approval-gated.
- Claim/heartbeat/cursor-`show` verbs, `tools/agent-env.sh`,
  `tools/reclaim-space.sh`.

**Keep human-approved (each now *double-gated* — the prompt and the
interlock):** any mutating git outside the bridge flow; `rm`/deletion outside
the reclaim script; network/vendor fetches (they can move the frozen source
boundary — ADR-0052's rejected alternative — and cost money); DB writes as any
role other than `quant_agent_ro`; loader burn/resume, `cursor set`, and
activation verbs (also gated by advisory lock, cursor triggers, and Ed25519
respectively — approval fatigue on these few high-stakes prompts drops to near
zero once the hundreds of read/test prompts stop arriving).

**Expected effect:** in the two instrumented probes, ≥98% of wall clock was
approval idle; the allowlisted classes cover essentially all of the repeated
commands the transcripts show. Even a conservative estimate returns the
majority of active-session wall time — the largest single pacing lever that is
purely configuration.

## Implementation order and acceptance

1. **Now (docs-only, no repo-state risk):** the `Concurrent agents` section in
   `agent-collaboration.md` (matrix, claims rules, task-file lifecycle,
   commit-checkpoint rule, workspace policy, approval policy) + the allowlist
   config + `quant_agent_ro`. Acceptance: a cold agent session can state, from
   the doc alone, whether it may touch each of the nine artifact classes and
   which commands need no approval.
2. **After the A-3 branch settles (owns the tables):** cursor
   migration + triggers 1–3 + audit table + CLI verbs + generated cursor doc.
   Acceptance tests (mirror the repo's existing DB-test conventions): revision
   insert rejected under `resume-only`; failure attestation for revision 5
   rejected until the operator flips the flag (and the audit row exists);
   pointer UPDATE rejected with `allow_pointer_flip=false`; same-source-run
   allocation rejected while a predecessor is unattested or gated; absent
   cursor row rejects everything.
3. **Then:** claims table + agent-env/reclaim scripts; bridge task-mailbox
   fallback to committed task files.
4. Record the whole package as an ADR (it changes documented operational
   convention), and — per roadmap item 1 — promote it through
   `risks-and-decisions.md`, not another orphaned advisory doc.
