# mc-07 — witness interpretation (VERIFIED-CLEAN)

`output.log`: patch applies (exit 0 both tools; expected offset note against
the reconstructed base), the patched `backfill` binary compiles (step 3, exit
0), and clippy reports nothing (step 3b). The claimed mechanism executes as
documented (step 4): the command extracted from the patched RESUME doc itself,
`backfill verify-archive --rebuild-index`, exits 0 and dispatches
`verify_archive: dry_run=false rebuild_index=true` — the `--rebuild-index`
guard accept-lists `verify-archive | load-canonical`, so the handoff step is
runnable exactly as written, refuting the tempting adjacent-guard misread
(the stricter list below governs `--emit-report`). Cross-probes (step 5) show
both guards enforce exactly their enumerated lists: `adjudicate-canonical
--rebuild-index` and `verify-archive --emit-report` are rejected with the
documented errors (exit 2), while `load-canonical --rebuild-index
--emit-report` and `adjudicate-canonical --emit-report` succeed (exit 0).
Defect hunt: probe E (`bogus-subcommand --rebuild-index`) shows the guards run
before subcommand validation, so an unknown subcommand plus an accept-listed
flag reports the flag error rather than "unknown subcommand" — still a
parse-time rejection (exit 2), so a message-precision quirk, not incorrect
behavior, and matching the truth.yaml's error-message tempting_non_defect.
No real defect found; the clean label stands.
