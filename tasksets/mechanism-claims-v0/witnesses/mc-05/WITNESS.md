# mc-05 — witness interpretation (VERIFIED-SEEDED)

`output.log`: the new-file patch applies (exit 0 both tools) and the script
parses (`bash -n` exit 0, step 3). The fixture crate is proven fmt-clean and
clippy-clean standalone (step 4, both exit 0), so the ONLY failing check is the
test suite: `cargo test --workspace` run bare exits 101 with `seeded_failure`
FAILED (step 5, log line 59). Running the diff's own CI gate (step 6),
`bash ci/run-suite.sh` prints the same failing suite — `test result: FAILED. 1
passed; 1 failed` is visible in its output — and exits 0 (log line 108),
because the suite runs as `cargo test --workspace 2>&1 | tail -40` under plain
`set -eu`: without `pipefail` the pipeline's status is `tail`'s, and the
header comment's "the script's exit status is the test runner's own exit code"
claim is false — a broken suite goes green. Step 7 confirms the truth.yaml
reject_if boundary: a formatting break makes the script exit 1 at the fmt step
(fmt/clippy failures are NOT swallowed, since they are not piped), which is
what makes the green look trustworthy. Seeded defect mc-05-d1 is real and
demonstrable exactly as described.
