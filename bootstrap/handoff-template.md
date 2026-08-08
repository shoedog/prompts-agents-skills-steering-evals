<!-- HANDOFF TEMPLATE — copy, fill top to bottom, delete no heading.

WHEN TO WRITE (the rule this template exists for): write/refresh the handoff at every
stable point — after a commit or push, before any long-running or irreversible step,
before compaction, when a lane changes owner, and any time you are about to go idle.
Do NOT save it for exit. Motivating failure: a session was ASKED for a handoff, went
idle without writing one, and the successor reconstructed it from a 15,348-line
transcript. A handoff at 60% fidelity beats one that was never written. Overwrite the
same file each refresh — living document, not a farewell note.

FILL RULES (exact aliases of dispatch-brief-contract §3 — one vocabulary, not two):
[MEASURED] = RE-RAN THIS TURN: name the command AND attach or point to its output.
[INHERITED] = SUPPLIED, NOT RE-VERIFIED: name the source. A load-bearing statement
with no probe and no named source is tagged [ASSUMPTION] — never silently inherited.
[UNKNOWN] is truthful when the observing capability is unavailable: name the missing
capability; an UNKNOWN gating fact stays OPEN. If a section is empty write "None." —
an empty section is indistinguishable from an unfinished one.

NOT THIS DOCUMENT'S JOB: committing/pushing/backing up artifacts (global steering,
durable custody) and running the refutation pass (dispatch-brief-contract §2c). §0 and
§7 carry only their VERDICTS — do not restate either rule here.

STABLE ANCHORS (a validator checks these; keep the exact strings): the eight
numbered section headings, the Truth-ordering and Provenance header lines, the
MEASURED/INHERITED/ASSUMPTION/UNKNOWN tags, and the section-7 verdict line. The
checker MUST strip HTML comments, require each anchor once in its expected region
and the headings in order, and reject surviving <metavariable> placeholders —
otherwise this very comment would satisfy a naive substring check. -->

# Handoff — <lane; what a successor is picking up>

**Written:** <ISO timestamp> · **By:** <session id / agent name> · **Provider:** <claude | codex | kiro | other>
**Workspace:** <repo> · <branch> · **Measured state:** `[MEASURED]` HEAD <sha> · Tree <CLEAN|DIRTY> · Probe <command> · Output <capture path or inline>
**Predecessor:** <session id | "none — first in lane" | "unknown — <capability checked>">
**Truth ordering:** measured live state > explicit owner/contract authority within its scope > this handoff for current operational state > earlier handoffs and non-authoritative summaries. A conflict between tiers stays OPEN in §0 — never resolved by document class alone.
**Provenance:** <written live by the worker | reconstructed from transcript by <who/how> | folded from N sources>. `[MEASURED]` claims were probed by this writer; `[INHERITED]` claims were not.

## 0. Gating facts — settle these before starting anything below
<!-- ONLY facts that make a later step unsafe or wrong to begin. Answer each; "None." is an answer.
Mark each OPEN or RESOLVED <how, when> — amend in place on refresh, don't rewrite history. -->

**(a) Lane ownership** — another session/agent alive in this lane? who owns it? `[MEASURED|INHERITED|UNKNOWN]` <probe, source, or missing capability> — **OPEN | RESOLVED <how, when>**
**(b) Custody exposure** — unpushed commits, uncommitted work, single-copy/untracked artifacts: `[MEASURED|INHERITED|UNKNOWN]` <counts, sizes, paths> — **OPEN | RESOLVED <how, when>**
**(c) In flight / irreversible** — running process, held lock, half-applied migration: `[MEASURED|INHERITED|UNKNOWN]` … — **OPEN | RESOLVED <how, when>**
**(d) Authorization granted but not exercised** — the standing instruction a successor may not re-derive: <verbatim quote>

## 1. Resume order
<!-- Numbered, exact, executable. Step 1 must be startable with no further reading: commands, paths,
expected duration. If a step is blocked, name what blocks it. -->
1. …
2. …

**STOP conditions:** <what halts work rather than gets worked around>

## 2. State ledger
<!-- One row per unit of work. State ∈ done | next | blocked | pending | parked.
Evidence must point at something re-readable (file, commit, log path) — never the word "verified". -->

| Item | State | Evidence / correction |
|---|---|---|
| … | … | `[MEASURED]` … |

## 3. Corrections to standing documents and memory
<!-- Every place that now asserts something false, and the correction. This is what stops a successor
trusting stale docs. Say whether you already corrected it; if not, this table IS a work item. -->

| Location | Stale or false assertion | Correction |
|---|---|---|
| … | … | `[MEASURED]` … |

## 4. Open work

| # | Work | State | Exact next action | Blocked by | Identifiers |
|---:|---|---|---|---|---|
| … | … | … | … | … | … |

## 5. Invariants and traps — do not do these
<!-- Prohibitions a successor could plausibly violate in the first hour, each with WHY in half a line.
Traps you personally hit go here, not in prose. -->
- Never … — because …
- <trap observed this session> → <what to do instead>

## 6. Identifiers
<!-- Verbatim and copy-pasteable: shas, paths, ports, container/volume names, session ids, run labels.
A successor should never have to re-derive one of these. -->

| Item | Verbatim |
|---|---|
| … | `…` |

## 7. Refutation verdict and owner questions

**§2c verdict:** <SURVIVED | REFUTED — corrected in place | NOT RUN — why | NOT APPLICABLE — no claim-bearing content> · claim: "<the one claim the most downstream work depends on>" · pass: <INDEPENDENT | SELF-PASS (NOT INDEPENDENT)> · evidence tier: <TEST-BACKED | STATIC-ONLY> · record: <path or session label of the refutation pass>
<!-- Verdict only; the procedure is dispatch-brief-contract §2c. NOT RUN is acceptable at an interim
checkpoint and a defect at a lane handover WHEN §2c IS IN SCOPE; out-of-scope handovers say NOT APPLICABLE. -->

**Questions the owner owes an answer to:** <numbered, each blocking or near-blocking; "None." if none>
