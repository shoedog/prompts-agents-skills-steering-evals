---
task-type: implement
---
# Cleanup-2: smoke-subcommand defect pair, verify-report truthfulness, --input silent drop, Task P MINOR batch

## Description

Four closed defect groups, one batch (fix-vs-redispatch rule: all enumerable).

1. SMOKE SUBCOMMAND PAIR (root-cause first, from W2d acceptance): (a) `smoke` fails
   container-agent model-override config at prompt_start; (b) smoke.config classifier
   collapses 4 ConfigX error variants AND discards the underlying message (evidence-
   destroying classification — the class is in the failure taxonomy; carry the full
   message).
2. VERIFY-REPORT TRUTHFULNESS (Task P process finding): the hand-off's "verify: FAIL at
   <gate>" must distinguish "gate X failed" from "nothing after gate X ever ran" — emit
   per-gate reached/not-reached/exit status, and surface lock-sync failures (`--locked`
   pre-compile death) as their own class, not as the first gate's failure. Three review
   rounds examined a commit whose gates all died pre-compile without knowing it.
3. RUN-WORKFLOW --input SILENT DROP: warn loudly (or fail) when --input is supplied but
   no node prompt contains `{{input}}` — witnessed twice (mine-sol/mine-luna round 1
   returned "missing INPUT" from a green-looking run).
4. TASK P MINOR BATCH (review rounds 3 + fix-round SMELLs, all file:line'd in
   w2b-taskP-run.log tail + w2b-taskP-fix-review-verdict.md): incapable-backend
   diagnostics at connect; generate_turn_id().expect() → propagate; spool I/O failure
   tests; MCP-args-through-wrapper unsandboxed test; duplicated
   append_attestation_contract_to_last_part helper → shared module; session_id §4.3 spec
   note; inner `dev.b2a.attested_prefix` field-count guard; three-marker test case +
   process_prefix_bytes pin in the split test; strip_reserved_meta scope note. (The
   terminal_status race + spawn_blocking spool are TASK F's, not here.)

## Acceptance Criteria

Each group: failing-first test where the defect is testable (esp. 1b message
preservation, 2 reached/not-reached, 3 warning); hermetic verify green; existing tests
untouched in intent; smoke pair root-cause documented in the commit message before the
fix (debugging discipline: alternatives named and ruled out).

## Non-goals

Task F scope; watchdog feature (separate task); any default behavior change beyond the
named fixes.

## Commit Message

bridge: cleanup-2 — smoke defect pair with root-cause, truthful per-gate verify reporting, --input consumption warning, Task P MINOR batch
