# quant-platform improvement roadmap — 2026-07-17

> Companion to the official phased plan (`docs/60-plan/timeline.md`, ~3 years, Phases 0–4).
> This is a **risk-closure overlay** on that plan, not a replacement: it sequences the gaps
> found in a deep read-only audit (18 findings, tagged `[A1]`…`[F3]` below; `[NEW]` = added
> in this pass). The official plan says what to build; this says what to close, and when.

## Current state

The platform is in **Phase 1 (walking skeleton), paper-trading only — no live capital, and
this roadmap does not imply readiness for any.** Merged: P1 data plane, P2 order-path spine
(real Alpaca paper fill), P3 backtest spine, P4a feature compute-parity, plus deepening
layers through P10 (live Polygon WS 1m ingest) and P11 (live decision loop — third host of
the sealed artifact, default-disarmed behind a TTL'd Postgres arm). Determinism digests,
leakage audit, fail-closed pre-trade risk (4 of 8 controls), and the continuous-ops
operating-day ledger all exist. **Right now** the repo sits mid-flight on
`feat/layer6-a3-canonical-load` (~134 dirty/untracked files, a concurrent agent actively
editing): canonical revision 5 is materialized and WAL-converged but operator-interrupted,
the plan-doc live cursor forbids allocating revision 6 or flipping the serving pointer, and
first production activation (Task 20) is blocked — treat all branch details here as a
snapshot, not a stable baseline.

The audit's core framing, which this roadmap adopts: **determinism is not validity.** The
platform is excellent at reproducing its own results; the thin spots are proving those
results are *right* (no look-ahead on the shared read path) and that backtest-green
transfers to the live path (audits currently run only in backtest). That, plus fail-closed
risk depth, is the center of gravity below.

---

## Short-term (next 2–4 weeks) — cheap, high-leverage, live risks

Ordered by leverage. Items 1–3 are the "do these even if nothing else" set.

1. **Reconcile `platform-analysis-2026-06-12.md` into authoritative tracking.** `[F3]`
   The doc says its findings "should land in `risks-and-decisions.md` as ADRs"; a grep
   confirms zero references were ever promoted. Several of the sharpest known risks
   (live-path blindness, missing post-trade reconciliation, no DR cron, no walk-forward)
   are recorded nowhere authoritative. One editing session: promote each P1–P5 finding to
   an ADR or an explicit "declined, because" entry. Cheapest item on this list; unblocks
   honest go/no-go reasoning later.

2. **Mechanical interlock for the activation state machine + concurrent agents.** `[A1][F1]`
   The revision-5 exact-resume rules live in a prose plan cursor; the advisory family lock
   serializes runtime activations but nothing stops a second agent's code edit, operator
   command, or partial merge from violating the frozen-evidence invariants. Add: (a) a DB
   constraint or guard table encoding the live cursor ("no revision 6, no failure-mark, no
   pointer flip until cleared"), checked by the operator CLI itself; (b) a short
   concurrent-agent protocol section in `agent-collaboration.md` covering shared *stateful*
   artifacts (loader, pointer, frozen snapshots, in-flight branches) — the current doc has
   conventions for humans and none for agents. Do the DB guard after the A-3 branch
   settles; write the protocol doc now.

3. **Close the ABSENT-selection foot-gun.** `[A3]` `resolve_pg`'s `Absent` branch returns
   the live-active pointer without consulting `market_data_serving_verification`, so any
   non-pinning consumer can read a gated-but-unverified revision in the window between the
   flip commit and the verification insert — and can never replay the result. Make the
   serving side refuse (or explicitly warn-and-tag) ABSENT resolution to an unverified
   revision, and deprecate the legacy `historical_dataset: None` replay path in favor of
   the `FrozenDatasetSelection` pin the backtest engine already uses.

4. **Fix the 08-risk.md self-contradiction.** `[E1]` The header claims "eight controls
   committed" while the status table shows four live. Cheap doc fix now; prevents a future
   go-live decision from being made against the wrong belief. (Building the controls
   themselves is the long-term gate, below.)

5. **Decide `as_of` call-pattern policy for corporate actions.** `[B1]` Every `GetBars`
   caller today passes `as_of == window_end` (documented in
   `layer-3-deferred-follow-ups.md`), which back-adjusts bars earlier than an in-window
   ex-date — an earlier decision's price embeds a later action. Short-term: write the ADR
   choosing the fix (per-decision-instant `as_of` vs adjusted-at-decision-time series) and
   add a leakage-audit case that would catch it. Implementation is medium-term.

## Medium-term (1–3 months) — structural, while still paper-only

6. **Run the backtest safety audits on the live decision path.** `[C1]` Contracts are
   shared between backtest and live; the *audits* (leakage, determinism, survivorship /
   leaver handling) run only in the backtest host. Wire the leakage audit and a
   determinism/parity spot-check into `live-decision-runtime`'s session cycle, and — since
   the machinery already exists — fold them into the continuous-ops operating-day
   six-criterion health gate so every earned "real day" also certifies the live path.
   `[NEW]` (the health-gate fold-in; the gap itself is C1).

7. **Move the determinism gate into CI.** `[C2]` Reproducibility is a stated release
   blocker but the real-data acceptance tests are `#[ignore]`, run locally by convention
   (VERIFICATION.md shows the sandbox already forced a host-stack rerun once). A scheduled
   CI job with QuestDB service containers running the five pinned digests, required on
   merge to main, converts the invariant from discipline to mechanism.

8. **Close the corporate-action look-ahead vectors.** `[B1][B2]` Implement the ADR from
   item 5, and add the knowledge-time dimension for actions (`received_at` watermark +
   supersession-aware reads, already spec'd in `layer-3-deferred-follow-ups.md`) so vendor
   restatements stop being retroactively "known" at ex-date. Reframe B2 in tracking as a
   PIT look-ahead vector, not a feature gap.

9. **Content-verify the cross-store barrier; cover the prune race.** `[A2]` The WAL
   visibility barrier is count-based (revision 3 failed it with 1,666 unapplied
   transactions — the mechanism works, but counts can match while bytes differ). Add a
   sampled content digest to flip-readiness, make "covered date, no bar" a loud error
   rather than a silent empty result, and add a guard for ADR-0055 partition-pruning
   racing a reader pinned to the pruned revision.

10. **Treat the two parity seams as versioned artifacts.** `[C3][B3]` The
    `signal.forecast.v1` two-producer parity test and the three-way as-of-join parity test
    are each the *sole* guard on a central invariant. Enumerate their case coverage in a
    reviewed doc, extend to the known nasty edges (tie-breaking, boundary inclusivity,
    market-closed days), and require an ADR note when either changes.

11. **De-brittle the canonical-load conservation gate; implement retention.** `[D1][D2]`
    The exact-count conservation law fails closed (good) but means every future vendor
    re-snapshot whose composition shifts by one row halts activation pending a
    hand-authored disposition ADR — this does not scale to routine re-snapshots. Design a
    categorized-disposition mechanism (known classes auto-annotate, only novel classes
    block). Implement the deferred retention sweep before the 12-revision headroom wall is
    reached by accretion, and recalibrate the capacity charge the environment already
    falsified (revision 4's free space *increased*).

## Long-term (3–6+ months) — pre-live-trading gate

**This roadmap does not recommend live trading and nothing above implies readiness.** The
items here are framed as **"must close before considering live"** — a mechanical go/no-go
checklist, not a schedule. The official plan's Phase 1B/2 exits (30/60 green paper days)
are necessary but not sufficient; these are the additional gates.

12. **Complete the pre-trade control set.** `[E1]` Build the four deferred controls that
    are safety-critical for a solo-operator system — max position size, liquidity/%ADV
    cap, price band, sector exposure — plus short-borrow when shorting exists. Without the
    ADV cap and price band, a strategy bug can size into an illiquid name or chase a bad
    print with only notional/leverage as backstops.

13. **Harden fail-closed semantics beyond "unreachable".** `[E2]` Define and centrally
    enforce deny-on-timeout/deny-on-error (a reachable-but-hung risk service must deny,
    not stall), and make limit-set activation atomic so no order is evaluated against a
    torn old/new limit mix.

14. **Implement the broker-scope kill switch.** `[E3]` `EngageKillSwitch(scope=broker)`
    returns `unimplemented`; the last-resort control when the platform *itself* misbehaves
    must act at the venue, not through the possibly-broken order path.

15. **Live observability + DR, implemented not designed.** `[F2]` Replace `nohup cargo
    run` + flat files with supervised processes; OTel/metrics/alert delivery on the live
    path; persistent logs; the nightly backup cron that the DR doc assumes; a rehearsed
    restore that validates the claimed 6-hour RTO; an operator-unavailability runbook
    (who/what flattens the book if the operator is unreachable).

16. **Post-trade controls and reconciliation.** `[F3][NEW]` Automated broker-vs-
    portfolio-state position reconciliation after every session (a Phase-1B exit
    requirement nothing yet implements), plus daily-loss and drawdown auto-halt so the
    kill switch has a machine trigger, not only a human one.

17. **Fill/cost model realism + strategy validity.** `[C4]` Replace the fixed 5 bps
    placeholder with spread + impact + latency models calibrated against accumulated
    paper-fill divergence data (the sim-vs-paper harness already exists), fix the
    sizing-vs-fill notional mismatch, and correct `05-backtesting.md`'s claim that this is
    done. Gate live on the platform-analysis strategy-validity items: multi-year
    survivorship-free evaluation, walk-forward with embargo/purge, benchmark-relative
    metrics.

18. **Convert the go/no-go rubric from prose to a checklist ADR** referencing items 12–17
    with per-item evidence links, signed off in `risks-and-decisions.md`. `[NEW]` The
    rubric currently exists only in the advisory analysis; the decision to move real money
    should be the most-tracked decision in the repo.

---

## About this document

Produced 2026-07-17 by a two-pass external review: an Opus deep read-only audit of
quant-platform (18-finding edge-case/failure-mode synthesis; source of the `[A1]`–`[F3]`
tags — full text in [`stocktrading-opus-synthesis-2026-07-17.md`](stocktrading-opus-synthesis-2026-07-17.md))
followed by this roadmap-authoring pass, which independently verified the key claims
against README, VERIFICATION.md, the phase-1/timeline plan docs, `agent-collaboration.md`,
`risks-and-decisions.md`, and `platform-analysis-2026-06-12.md`. It lives in
`prompts-skills-steering`, **outside quant-platform's own docs** — and per finding `[F3]`,
this repo has a demonstrated pattern of advisory analyses never being folded into
authoritative tracking. **This document is exposed to exactly that failure mode.** Once
the `feat/layer6-a3-canonical-load` branch settles, the owner should decide, item by item,
what gets promoted into quant-platform's `risks-and-decisions.md` / ADR log (or explicitly
declined there) — rather than letting this become the next orphaned analysis.
