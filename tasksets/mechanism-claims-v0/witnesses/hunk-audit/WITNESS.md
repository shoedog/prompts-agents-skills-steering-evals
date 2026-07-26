# Hunk-header arithmetic audit — witness

`audit.py` parses all 8 `items/mc-*/diff.patch` files and, for each of the 12
hunks, recounts the body lines by prefix and checks the declared `@@ -a,b +c,d @@`
counts against them (old = context+deletions, new = context+additions), checks
cross-hunk start offsets (new_start − old_start must equal the cumulative
add−del delta of prior hunks in the same file, with the `-0,0` new-file
convention), and rejects invalid body prefixes, stray inter-hunk lines, CRLF,
and missing final newlines. Result in `output.log`: all 12 hunks OK, `HUNK-AUDIT
RESULT: PASS`, exit 0. Independent cross-checks: `git apply --check` exited 0
for all 8 patches and `patch -p1 --dry-run` exited 0 for all 8 (see step 2 /
2b of each item's `witnesses/mc-*/output.log`) — both tools verify header
counts against hunk bodies as part of applying. One cosmetic (non-arithmetic)
note: mc-02's CHANGELOG.md hunk ends with a trailing `+` blank line at EOF,
which `git apply` reports as a whitespace warning ("new blank line at EOF",
mc-02 output.log step 2c) while still applying cleanly. Start-line positions
relative to a base tree are not auditable for mc-02/mc-03/mc-07/mc-08 because
the taskset ships no base files; the audit therefore establishes internal
consistency, and application was demonstrated against reconstructed bases
(with the expected benign offsets reported by `patch`).
