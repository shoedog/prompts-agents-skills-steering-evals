#!/usr/bin/env bash
# mc-01 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Re-runnable: materializes shim base files into BUILD_DIR (default mktemp),
# applies items/mc-01/diff.patch (git apply + patch cross-check), builds with
# cargo, and runs the truth.yaml minimal_trigger.
#
# SHIMS (do not touch the seeded mechanism): Cargo.toml wrapper crate;
# src/lib.rs module decl; src/bin/trigger.rs harness; base docs/spool-format.md
# stub ("TBD." -- the patch's own pre-image). src/replay_spool.rs comes ONLY
# from diff.patch.
#
# HYPOTHESIS under test (truth.yaml mc-01-d1): doc claims custom binary codec /
# no JSON on the write path / protobuf bytes stored raw; encode_entry() actually
# serializes via serde_json, so 20 protobuf bytes render as a ~60-80 char JSON
# integer array. FALSIFIER: the framed payload is not JSON / the bar bytes are
# stored raw.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-01}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-01 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: $(cargo --version); $(git --version); patch: $(patch --version 2>&1 | head -1)"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize shim base files ---"
mkdir -p src docs
cat > Cargo.toml <<'SHIM_EOF'
[package]
name = "mc01"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "=1.0.228", features = ["derive"] }
serde_json = "=1.0.150"
sha2 = "=0.10.9"
SHIM_EOF
cat > src/lib.rs <<'SHIM_EOF'
pub mod replay_spool;
SHIM_EOF
cat > docs/spool-format.md <<'SHIM_EOF'
# Replay spool format

TBD.
SHIM_EOF
mkdir -p src/bin
cat > src/bin/trigger.rs <<'SHIM_EOF'
//! minimal_trigger harness for mc-01 (truth.yaml mc-01-d1):
//! push() one Entry whose market_bar is 20 protobuf bytes; compare the doc's
//! size/encoding prediction against the actual framed record.
use mc01::replay_spool::{Entry, RunWriter, RUN_MAGIC};

fn main() -> std::io::Result<()> {
    // 20 bytes of already-encoded protobuf (MarketBar-like framing bytes).
    let market_bar: Vec<u8> = vec![
        0x0a, 0x12, 0x08, 0x9b, 0xc4, 0x03, 0x11, 0x71, 0x3d, 0x0a, 0xd7, 0xa3, 0x70, 0x45,
        0x40, 0x19, 0x00, 0x00, 0xf8, 0x42,
    ];
    assert_eq!(market_bar.len(), 20);
    let entry = Entry {
        market_bar: market_bar.clone(),
        source_ordinal: 7,
        close_token: "C-2026-07-24".to_string(),
        closeadj_token: "CA-2026-07-24".to_string(),
        raw_row_sha256: "a".repeat(64),
    };
    let mut sink: Vec<u8> = Vec::new();
    {
        let mut w = RunWriter::create(&mut sink)?;
        w.push(&entry)?;
        w.finish()?;
    }
    println!("total run bytes written        : {}", sink.len());
    println!("RUN_MAGIC prefix present       : {}", sink.starts_with(RUN_MAGIC));
    let after_magic = &sink[RUN_MAGIC.len()..];
    let len = u32::from_be_bytes(after_magic[0..4].try_into().unwrap()) as usize;
    println!("u32 BE length prefix (framing) : {len}");
    let body = &after_magic[4..4 + len];
    println!();
    println!("DOC CLAIM (docs/spool-format.md hunk in this diff):");
    println!("  'Record payloads use our compact custom binary codec; there is no JSON");
    println!("   anywhere on the write path. Protobuf bar bytes are stored raw' ->");
    println!("  predicted record ~= 20 raw bar bytes + tokens/ordinal + framing.");
    println!();
    let body_str =
        String::from_utf8(body.to_vec()).expect("payload is valid UTF-8 (JSON), not binary");
    println!("ACTUAL framed record payload ({len} bytes) is UTF-8 JSON text:");
    println!("{body_str}");
    let v: serde_json::Value = serde_json::from_slice(body).expect("payload parses as JSON");
    let arr = v
        .get("market_bar")
        .and_then(|m| m.as_array())
        .expect("market_bar is a JSON array of numbers");
    assert_eq!(arr.len(), 20);
    let arr_txt = serde_json::to_string(&v["market_bar"]).unwrap();
    println!();
    println!("market_bar (20 raw protobuf bytes) rendered as a JSON integer array:");
    println!(
        "  {} => {} characters for 20 bytes = {:.2}x blow-up",
        arr_txt,
        arr_txt.len(),
        arr_txt.len() as f64 / 20.0
    );
    assert!(
        body.starts_with(b"{"),
        "payload starts with '{{' -- JSON object, not a binary codec"
    );
    assert!(
        (55..=90).contains(&arr_txt.len()),
        "JSON array text for the 20 bar bytes is in the predicted ~60-80 char range (got {})",
        arr_txt.len()
    );
    println!();
    println!("VERDICT: the payload encoder is serde_json (encode_entry -> serde_json::to_writer,");
    println!("src/replay_spool.rs); the market_bar protobuf bytes are NOT stored raw. The doc's");
    println!("'compact custom binary codec / no JSON anywhere on the write path' claim is FALSE.");
    Ok(())
}
SHIM_EOF
echo "base files:"
find . -type f -not -path './.git/*' | sort

echo
echo "--- step 2: git apply --check (header/structure validation) ---"
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
echo "--- step 4: minimal_trigger run ---"
./target/debug/trigger 2>&1
echo "exit=$?"
