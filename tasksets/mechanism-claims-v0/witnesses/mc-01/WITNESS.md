# mc-01 — witness interpretation (VERIFIED-SEEDED)

`output.log`: the patch applies cleanly (`git apply --check` exit 0, `patch
--dry-run` exit 0) and the patched crate compiles (cargo build exit 0, step 3).
The minimal_trigger (step 4) pushes one `Entry` whose `market_bar` is 20
already-encoded protobuf bytes through the diff's `RunWriter::push` path and
reads the framed bytes back: the record payload is a 244-byte UTF-8 JSON object
(printed verbatim at log line 77), in which the 20 protobuf bytes render as the
JSON integer array `[10,18,8,...,66]` — 64 characters for 20 bytes, a 3.20x
blow-up, inside the 60–80-char range truth.yaml predicts. This is produced by
`encode_entry()`'s `serde_json::to_writer` call in the diff's own
`src/replay_spool.rs`, directly contradicting the doc hunk's "compact custom
binary codec … no JSON anywhere on the write path … protobuf bar bytes stored
raw" claims, which predict ~20 payload bytes plus framing. Seeded defect
mc-01-d1 is real and demonstrable exactly as described; only the framing
(magic, u32 BE length prefix, footer) is binary.
