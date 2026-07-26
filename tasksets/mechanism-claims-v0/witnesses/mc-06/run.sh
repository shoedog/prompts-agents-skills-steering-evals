#!/usr/bin/env bash
# mc-06 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Clean twin of mc-01. Re-runnable: materializes shim base files, applies
# items/mc-06/diff.patch, builds, and EXECUTES every mechanism claim the format
# doc makes, plus an unintended-defect sweep (footer/digest recompute, JSON
# round-trip, clippy).
#
# SHIMS: Cargo.toml wrapper crate; src/lib.rs module decl; src/bin/trigger.rs
# harness; base docs/target-spool-format.md stub ("TBD."). src/target_spool.rs
# comes ONLY from diff.patch.
#
# CLAIMS under test (doc hunk in this diff): (1) framing is binary (RUN_MAGIC,
# u32 BE length prefixes, count+SHA-256 footer over the framed stream);
# (2) record payload is serde_json, protobuf bar bytes as a JSON integer array
# with ~3-4x blow-up. Item is labeled CLEAN: every claim must HOLD.
# FALSIFIER: any claim measurably false, or a real defect beyond the
# truth.yaml tempting_non_defects.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-06}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-06 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: $(cargo --version); $(git --version); patch: $(patch --version 2>&1 | head -1)"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize shim base files ---"
mkdir -p src docs src/bin
cat > Cargo.toml <<'SHIM_EOF'
[package]
name = "mc06"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "=1.0.228", features = ["derive"] }
serde_json = "=1.0.150"
sha2 = "=0.10.9"
SHIM_EOF
cat > src/lib.rs <<'SHIM_EOF'
pub mod target_spool;
SHIM_EOF
cat > docs/target-spool-format.md <<'SHIM_EOF'
# Target spool format

TBD.
SHIM_EOF
cat > src/bin/trigger.rs <<'SHIM_EOF'
//! Claim-verification harness for mc-06 (clean item): write two TargetEntry
//! records and check every docs/target-spool-format.md claim against the bytes.
use mc06::target_spool::{TargetEntry, TargetRunWriter, RUN_MAGIC};
use sha2::{Digest, Sha256};

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn main() -> std::io::Result<()> {
    let bar1: Vec<u8> = vec![
        0x0a, 0x12, 0x08, 0x9b, 0xc4, 0x03, 0x11, 0x71, 0x3d, 0x0a, 0xd7, 0xa3, 0x70, 0x45,
        0x40, 0x19, 0x00, 0x00, 0xf8, 0x42,
    ];
    let bar2: Vec<u8> = (0..40u8).map(|i| i.wrapping_mul(97).wrapping_add(13)).collect();
    let e1 = TargetEntry {
        market_bar: bar1.clone(),
        source_ordinal: 1,
        close_token: "C-2026-07-24".to_string(),
        raw_row_sha256: "e3".repeat(32),
    };
    let e2 = TargetEntry {
        market_bar: bar2.clone(),
        source_ordinal: 2,
        close_token: "C-2026-07-25".to_string(),
        raw_row_sha256: "5c".repeat(32),
    };
    let mut sink: Vec<u8> = Vec::new();
    {
        let mut w = TargetRunWriter::create(&mut sink)?;
        w.push(&e1)?;
        w.push(&e2)?;
        w.finish()?;
    }
    println!("total run bytes written: {}", sink.len());

    // CLAIM 1: binary framing -- RUN_MAGIC then u32 BE length-framed records.
    assert!(sink.starts_with(RUN_MAGIC));
    println!("claim 1 (binary framing): RUN_MAGIC prefix {:?} present: true", String::from_utf8_lossy(RUN_MAGIC).trim_end());
    let mut off = RUN_MAGIC.len();
    let mut framed: Vec<u8> = Vec::new(); // bytes the footer digest is documented to cover
    let mut bodies: Vec<Vec<u8>> = Vec::new();
    for rec in 0..2usize {
        let len = u32::from_be_bytes(sink[off..off + 4].try_into().unwrap()) as usize;
        framed.extend_from_slice(&sink[off..off + 4]);
        let body = sink[off + 4..off + 4 + len].to_vec();
        framed.extend_from_slice(&body);
        println!("  record {}: u32 BE length prefix = {len}, body = {} bytes, prefix==body-len: {}", rec + 1, body.len(), len == body.len());
        bodies.push(body);
        off += 4 + len;
    }

    // CLAIM 2: payload is serde_json; protobuf bar bytes as JSON integer array, ~3-4x blow-up.
    for (i, (body, bar)) in bodies.iter().zip([&bar1, &bar2]).enumerate() {
        let v: serde_json::Value = serde_json::from_slice(body).expect("record payload parses as JSON");
        let arr = v["market_bar"].as_array().expect("market_bar is a JSON integer array");
        let decoded: Vec<u8> = arr.iter().map(|x| x.as_u64().unwrap() as u8).collect();
        assert_eq!(&decoded, bar, "JSON integer array round-trips the exact bar bytes");
        let arr_txt = serde_json::to_string(&v["market_bar"]).unwrap();
        let factor = arr_txt.len() as f64 / bar.len() as f64;
        println!(
            "claim 2 (serde_json payload): record {} parses as JSON; market_bar {} bytes -> {} chars = {:.2}x blow-up (doc: ~3-4x)",
            i + 1, bar.len(), arr_txt.len(), factor
        );
        assert!((2.5..=4.5).contains(&factor), "blow-up factor consistent with the doc's ~3-4x");
    }

    // CLAIM 3: footer = record count + SHA-256 computed over the framed stream.
    let footer = &sink[off..];
    println!("claim 3 (footer): trailing bytes after records = {} (expect 8 count + 32 digest)", footer.len());
    assert_eq!(footer.len(), 8 + 32);
    let count = u64::from_be_bytes(footer[0..8].try_into().unwrap());
    let stored = &footer[8..40];
    let recomputed = Sha256::digest(&framed);
    println!("  record count field = {count} (records written: 2, match: {})", count == 2);
    println!("  stored sha256      = {}", hex(stored));
    println!("  recomputed sha256 over the framed record stream (len prefixes + payloads) = {}", hex(&recomputed));
    assert_eq!(stored, recomputed.as_slice(), "footer digest covers exactly the framed stream");
    assert_eq!(count, 2);

    println!();
    println!("VERDICT: all doc claims HOLD against the implementing code -- binary framing,");
    println!("serde_json payload with the stated ~3-4x bar-byte blow-up, count+SHA-256 footer");
    println!("over the framed stream. Doc and code agree (clean item).");
    Ok(())
}
SHIM_EOF
echo "base files:"
find . -type f -not -path './.git/*' | sort

echo
echo "--- step 2: git apply --check ---"
git apply --check "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2b: patch -p1 --dry-run (cross-check) ---"
patch -p1 --dry-run -i "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2c: apply for real (git apply) ---"
git apply "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "post-apply tree:"
find . -type f -not -path './.git/*' -not -path './target/*' | sort

echo
echo "--- step 3: cargo build (compile check) ---"
cargo build --bins 2>&1
echo "exit=$?"

echo
echo "--- step 3b: unintended-defect sweep: cargo clippy (advisory, not -D) ---"
cargo clippy --quiet 2>&1
echo "exit=$?"

echo
echo "--- step 4: claim-verification run ---"
./target/debug/trigger 2>&1
echo "exit=$?"
