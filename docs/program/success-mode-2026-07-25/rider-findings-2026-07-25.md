# Wave S0 qualitative rider — novel success patterns (2026-07-25)

Source: detector-build agent's qualitative pass over the 5 highest-strong-signal sessions
excluding the program's own (782c0297, a600bea5). Detector: mining/scripts/
detect_success_signatures.py (8/8 known-incident validation; 14,150 rows; 2,619 claude
sessions + 3,748 codex rollouts). These are NOMINATIONS pending curation into the catalog
(~/Documents/agent-success-modes-2026-07-25.md).

## f14884e6 (claude, ~/code/slicing, Jun 16-27; 22 refutations + 5 cap + 62-edit checkpoint cadence)

1. **Verify-first premise measurement** (L40707): before implementing a handed-off
   initiative, traced and measured its premise, found it already built/false, stopped and
   reported instead of building. Distinct from impossibility-argument-first (measures
   whether the problem EXISTS, not whether the task is impossible). Repeatable as a
   handoff-intake gate.
2. **Refutation propagated to durable memory** (L40863): "The MEMORY.md line still carries
   the now-refuted claim… I must correct it inline so a future session isn't misled" —
   plus negative A/B results recorded ("editing superpowers refuted (inert)",
   L57056/57222). Recurs in fb80415b (decision log records tested-and-refuted hypothesis).
   Repeatable: refutations must chase the refuted claim into every durable store.

## fb80415b (claude, ~/code/stockTrading, Jul 25-26)

3. **Independent recomputation of peer findings before acceptance** (L2344): "Fable found a
   real one, and I verified the arithmetic independently. Committed." Symmetric
   peer-refutation duel (assistant falsifies Fable's hypothesis L1552; Fable refutes
   assistant's L2344), evidence docs committed to a repo evidence dir.
4. **Claim quarantine after a burned claim** (L2042, L5932): "I want to confirm the second
   before claiming it"; "won't claim exhaustiveness again without an independent
   enumeration shown, since that claim was falsified once" — per-claim-class probation.
   Repeatable as a steering line.

## 608a7a2a (claude, ~/code, Jul 21-22 — the failure-forensics marathon, success side)

5. **Graded adjudication scorecard with self-error accounting** (L965, L1120): findings
   dispositioned CONFIRMED/PARTIAL/REFUTED ("no finding fully refuted, 4 of 7 PARTIAL with
   real overstatements — folding Sol's corrections verbatim would have introduced errors");
   orchestrator tallies its own record ("three of those four WRONGs are defects I
   introduced in the fold; one of my two pushbacks was overturned"). Extends two-lens
   accounting (S9) from lenses to disposition accuracy.
6. **Gate-vacuity audit** (L2980): "Does every gate falsify what it's supposed to?" —
   checking gates CAN fail; the complement of S10 (S10: gates must accept honest degraded
   paths; this: gates must be able to reject). Also: HEAD-unchanged verification after a
   nominally read-only agent (L965).

## f57999e7 (claude, ~/code/stockTrading, Jul 22-24)

7. **Evidence-probing reviewer blockers before compliance** (L5999-6057): Sol's "rev-9
   state is gone" blocker probed against the live DB with a stated falsification
   condition, refuted with counts, stale-source cause named (Sol reasoned from a
   superseded handoff). Skepticism runs upward too — reviewer claims get the same
   evidence bar as implementor claims.
8. **Audits dispatched to refute one's own oversell** (L7542): "it refuted my 'no new
   correctness surface' oversell — which is exactly what the audit was for."

## rollout-2026-07-10T21-03-55 (codex gpt-5.5 bridge orchestrator, ~/, Jul 10-25; only session with 4 strong detectors)

9. **Attribution/liveness tradecraft cluster**:
   - Precedent lookup for accepted controls (L122421): repo history consulted for the known
     separating control of an artifact class ("full dev debuginfo can exceed the 256 MiB
     evidence cap; the accepted separating control is CARGO_PROFILE_DEV_DEBUG=0") instead
     of re-deriving.
   - Named separator per attribution step (L122472-122496): every step names the
     discriminating experiment ("base control is 25/0, so both failures are candidate
     regressions"; serial-vs-parallel separator isolating a real concurrency defect).
   - Declared liveness patience window (L123499): "18 minutes… still within the normal
     long-review range, so I'm not treating it as stuck… let its event stream finish
     rather than restart or duplicate the billable turn" — a stated normal-duration prior
     before declaring a worker dead; the enacted dual of kill-and-retry/null-final churn.
   - Dischargeable objections (L123191): "will not merge unless this is removed, bounded
     and charged, or otherwise disproved with exact retention semantics" — the objection
     states its own discharge conditions.

## Detector measurement finding (baseline, not a nomination)

codex.expect_falsify_probe = 13,836 rows across 299 sessions (12,153 in stockTrading) —
the exp-3 expect/falsify discipline at ADOPTION saturation in codex workers. The detector
measures steering adoption there, not incidents; sessions-column + nomination dedupe keep
the queue usable. Claude-side: 64 rows / 20 sessions. Codex has ZERO strong cap_honored
prose — cap vocabulary is claude-orchestrator-side only.
