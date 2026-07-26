# Fresh-model probe report (promotion checklist box 3) — 2026-07-25

Protocol: one fresh Claude Sonnet agent per item, contamination-free (each saw ONLY a composed
prompt file mirroring the harness assembly: baseline review.md + output_format.md +
wrong-vs-smell steering + context.md + diff.patch, HTML comments stripped, per
gen_promptfoo.py `_compose_prompt` / config.py task_input; single Read call, no repo access,
no truth exposure). mc-02/mc-08 were probed twice: pre- and post- the 2026-07-25 curation fix
(see VERIFICATION.md "Curation fix"). Raw probe outputs:
`~/Documents/w2-tasks/probe-results-mechanism-claims-v0.md`.

## Results

| item | label | probe verdict | findable / survivable |
|------|-------|--------------|-----------------------|
| mc-01 | seeded | REJECT | ✓ found seed (serde_json vs custom-binary doc; implementing lines cited) |
| mc-02 (repaired) | seeded | REJECT | ✓ found seed clean (CHANGELOG 2x-gone vs seal(); numeric trace; error-path residue correctly SMELL-tagged) |
| mc-03 | seeded | REJECT | ✓ found seed (RESUME runnable-now vs accept-list guard; guard lines cited) |
| mc-04 | seeded | REJECT | ✓ found seed (preserved-verbatim doc vs fold/resolve code; both mechanisms, i/o pairs) |
| mc-05 | seeded | REJECT | ✓ found seed (no-pipefail tail exit-code + output-discard; both aspects) |
| mc-06 | clean | APPROVE | ✓ survived (SMELLs only, one already neutral-listed) |
| mc-07 | clean | APPROVE | ✓ survived (only the known guard-order message quirk, SMELL) |
| mc-08 (repaired) | clean | REJECT | ✗ see below |

Seeded findability: **5/5**, every one with the bar-required implementing-line citations under
BASELINE framing (no cite-or-label treatment needed to find them — the experiment measures rate
and citation discipline, and headroom exists on both).

## mc-08: fails survivability — owner decision required

Pre-fix, mc-08's rejection was CORRECT (a real data-loss defect in the shared reconstruction
code — since repaired and fault-injection-witnessed; VERIFICATION.md). Post-fix, a fresh probe
STILL rejects, but now on judgment-call severity inflation, not on any demonstrable
contract/data defect:

- seal()/compact_runs partial `remove_file` failure → untracked scratch leak (no data loss;
  sealed/merged already fsynced). mc-02's re-probe tagged the identical code SMELL; mc-08's
  probe tagged it WRONG.
- "one merge group above live data" doc phrase: the probe's own arithmetic confirms the literal
  bound HOLDS (peak = live + group); it rejected it as "materially misleading" because a FIFO
  group can approach dataset size. Strict wrong-vs-smell discipline files that as SMELL.

Implication: post-repair mc-08 sits at the APPROVE/REJECT boundary for defensible fresh
reviews. As a clean twin meant to discriminate on prose truthfulness alone, that boundary
position corrupts its signal: the judge would penalize severity-strict-but-REJECT reviews.
Sonnet severity-tag variance on identical code (SMELL vs WRONG across the twin probes) is
itself a finding about the wrong-vs-smell steering's binding power — relevant to the program.

Options (owner call; NOT applied):
1. Harden the shared error paths (best-effort cleanup that keeps tracking on failure; specify
   merge_sorted-on-empty) in BOTH twins. Touches mc-02-d1's citation surface (the post-merge
   remove_file loop is named in its bars) → bar-aware edit, owner territory.
2. Re-score clean items on findings-vs-bars rather than raw verdict (rubric/judge change).
3. Drop/replace mc-08 (7-item set, base rate 0.71 vs designed 0.62).

## Checklist consequence

Box 3 is NOT ticked. Earned for mc-01..mc-07 (7/8); mc-08 fails pending the decision above.
Box 4 (bar sign-off) untouched. exp-w3a remains un-run per its header gate (execution-verified
AND owner bar sign-off); everything else is run-ready — configs, taskset, witnesses, this
report.

## Resolution (2026-07-25, owner decision)

mc-08 DROPPED from v0 (option 3): 7 items, base rate 0.714, documented in manifest + exp
configs. Hardened replacement twin queued for v1. Remaining gate for running exp-w3a: owner
sign-off on the acceptable_match/reject_if citation bars (checklist box 4).

## Instrument rule (2026-07-25, owner-approved)

Any probe whose expected output is a fixed token MUST (1) run its claude CLI child with
the isolated settings file (`harness/providers/isolated_settings.json` via `--settings`) —
the operator's SessionStart hooks inject framework context that overrides terse
instructions (3/7 probes destroyed in the ssot dogfood corpus) — and (2) assert the token:
a prose reply classifies as INSTRUMENT_CONTAMINATED, never as product signal
(probe-admissibility: a malformed probe yields no evidence about the hypothesis).
Harnesses additionally export CLAUDE_INSTRUMENT_CHILD=1 so the settings-level guard
no-ops the hook for every descendant.
