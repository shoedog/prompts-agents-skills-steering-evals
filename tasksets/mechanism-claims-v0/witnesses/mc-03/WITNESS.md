# mc-03 — witness interpretation (VERIFIED-SEEDED)

`output.log`: patch applies (git apply --check and patch --dry-run exit 0; the
`patch` offset note against the reconstructed base is expected) and the patched
`backfill` binary compiles (step 3, exit 0). The minimal_trigger (step 4)
extracts the "Next step (runnable now)" command from the patched
`docs/RESUME-g4c.md` itself — `backfill audit-canonical --spinoff-binding
out/rev9-bindings.json` — and runs it with the referenced bindings file
present: it exits 2 at parse time with `error: config error: --spinoff-binding
is accepted only by load-canonical and adjudicate-canonical` (log line 30),
emitted by the accept-list guard the same diff adds
(`!matches!(cmd.as_str(), "load-canonical" | "adjudicate-canonical")`), which
excludes `audit-canonical`. Controls (step 5) rule out the alternative causes:
the flag IS accepted by both accept-listed subcommands (exit 0 with
`spinoff_binding=Some(...)`), and `audit-canonical` without the flag runs fine
(exit 0) — so the failure is exactly the guard-vs-doc contradiction, and the
handoff's "runnable now" step is not runnable as written. Seeded defect
mc-03-d1 is real and demonstrable exactly as described.
