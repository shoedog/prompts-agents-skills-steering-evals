# cleanup-2 retroactive review — 2026-08-07

Reviewer: Claude (Fable, main loop) — owner-directed 2026-08-07; independent of
the author (codex wrote the fixes). Target: a2a-bridge `625183e2` (+ fixup
`eb79133`), 2,418-line diff, 14 files. Closes the disclosed judgment call
"cleanup-2 merged without its re-review round."

## Verdict: ACCEPT — 0 WRONG, 3 SMELL

Full workspace suite at the fixup tree (`a2a-bridge-operator-main` @ eb79133):
**2,699 passed, 0 failed** (73 result sections, `cargo test --workspace`).

All four brief groups delivered and tested: smoke defect pair with root-cause
+ alternatives-ruled-out in the commit message (MAJOR-1 remediation present);
per-gate reached/not-reached verify reporting with lock-sync as its own class;
--input hard error on the local path with an honest WARNING degradation on
--serve (remote graph not inspectable); Task P MINOR batch complete
(shared append_attestation_contract_to_last_part, generate_turn_id
propagation through all three call families, spool I/O tests, field-count
pin producer+parser consistent at 8/6, MCP-args-through-wrapper test,
connect-time incapable diagnostics, §4.3/§17.16 doc notes, three-marker
case). The §18-7 Off-mode noop path matches the ratified wording, with a
counting-store test discriminating the production Noop path from a
mint-and-discard bundle.

Verified and dissolved during review: the `{{input}}` guard's literal
`contains` matches the renderer exactly (template.rs is exact-token,
whitespace variants are never substituted); NotReached rows (ok=false) leak
into no consumer outside verify.rs's own renderers.

## SMELL findings (risks, no demonstrated incorrect behavior)

1. **`is_lock_sync_failure` substring heuristic** (verify.rs). Any reached
   gate whose failure output happens to contain `--locked` plus one of
   {cargo.lock, lock file, lockfile, needs to be updated} is classified
   LockSync and the verdict line renames it "lock-sync before <gate>" — a
   genuine test failure mentioning those strings (e.g. a test asserting on
   lockfile messages) would be mislabeled. Risk condition, not witnessed.
   Tightening: match the canonical full cargo phrase.

2. **`safe_error_category` no longer static-only** (smoke.rs). It now
   forwards `error.to_string()` into smoke-artifact `causes` for
   ConfigInvalid/ConfigMismatch/ConfigReseedRequired/InvalidRequest. The
   function previously guaranteed static strings into an artifact family that
   is redaction-conscious elsewhere; a ConfigX reason that ever embeds a
   config VALUE (cf. DelegationConfig.auth) would leak it. No current reason
   constructor demonstrated to do so. Ask: audit ConfigX reason constructors
   or route causes through the redaction path.

3. **Env-var race window in the new argv test** (main.rs,
   acp_program_argv_wraps_unsandboxed_codex...). Its `static ENV_LOCK` is
   declared inside the test fn, so it serializes nothing: sibling
   acp_program_argv tests (e.g. the no-wrapper "no -c for Acp" case) read
   `A2A_BRIDGE_CODEX_ACP_PATH` through the same production path and can
   observe the mutated value under parallel `cargo test` — a flake window,
   test-only. Fix: hoist the lock to module scope and take it in every test
   touching that env var.

## What was verified / not verified

Verified: full diff read (all 14 files); renderer/guard consistency checked
against template.rs; NotReached consumer sweep; field-count pin cross-checked
producer (wrapper test, inner len 8) vs parser (expected_fields 8/6); full
workspace suite run at the fixup tree (2,699/0). Not verified: mutation-gate
re-execution (none re-run); failing-first property taken on inspection —
API-coupled tests cannot compile pre-change, and the behavioral ones
(message preservation, reached/not-reached, counted noop store) assert
content the pre-change code did not produce.

None of the three SMELLs blocks retroactive acceptance; all three are
candidates for a future bridge cleanup batch.
