# mc-06 — witness interpretation (VERIFIED-CLEAN)

`output.log`: patch applies (exit 0 both tools), the patched crate compiles
(step 3, exit 0), and clippy reports nothing (step 3b, exit 0). The harness
(step 4) writes two `TargetEntry` records (20-byte and 40-byte protobuf bars)
and checks every claim in the diff's own `docs/target-spool-format.md` against
the produced bytes. Claim "framing is binary": the file starts with
`TARGET_REPLAY_RUN_V1\n` and each record carries a u32 BE length prefix that
exactly matches its body length (211 and 291). Claim "payload is serde_json,
protobuf bytes as a JSON integer array with ~3-4x blow-up": both payloads parse
as JSON, the `market_bar` arrays round-trip the exact input bytes, and the
measured blow-ups are 3.20x and 3.60x — inside the doc's stated ~3-4x. Claim
"record-count + SHA-256 footer over the framed stream": the footer is 8+32
bytes, count = 2, and a SHA-256 recomputed over exactly the length-framed
record stream equals the stored digest (`d036db0e…8048`, log lines 74-75);
RUN_MAGIC is not part of the framed stream, consistent with the wording.
Defect hunt found nothing disqualifying: the only quirks are the ones the
truth.yaml already treats as neutral/tempting (u32-length `expect` panic on a
>4 GiB record, shared verbatim with mc-01; `to_vec` vs `to_writer` style).
Every doc claim HOLDS; the clean label stands.
