#!/usr/bin/env bash
# mc-08 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25;
# re-run after the 2026-07-25 curation fix to compact_runs -- see step 4b).
# Clean twin of mc-02: same base shim (SpoolDir + merge_sorted + fsync_file +
# scratch meter), same driver, but items/mc-08/diff.patch -- whose doc comments
# DISCLOSE the ~2x seal-time high-water instead of denying it.
#
# CLAIMS under test (doc comments in this diff), item labeled CLEAN:
#  (a) compact_runs(): per-group delete-after-durable-merge "bounds
#      INTERMEDIATE merge scratch to roughly one merge group above the live
#      data size"  -> measured compact peak must be ~dataset + one group;
#  (b) seal(): "every remaining run is merged into the sealed output BEFORE
#      any input is deleted ... plan for ~2x scratch high-water at seal time"
#      -> measured seal peak must be ~2.0x dataset, and fsync of sealed.run
#      must see all inputs still present (merge/fsync-before-delete);
#  (c) crash-safety: fsync before every remove (never delete the only durable
#      copy) -> [fsync] instrumentation lines must show inputs present.
#  (d) error-path defect hunt (curation fix 2026-07-25): the v0 code drained
#      self.runs BEFORE the fallible merge/fsync/remove calls, so a failed
#      merge orphaned the drained group from tracking and a later seal()
#      silently omitted its records -- a real unintended defect (two blind
#      probes found it) that falsified this item's clean label. Step 4b
#      injects the same mid-compaction fault against the REPAIRED code: it
#      must show 0 runs dropped from tracking, 0 dangling entries, and a
#      quota-lifted retry seal() emitting every input record.
# FALSIFIER: any measured number contradicting the doc, or a real defect.
#
# Extra cross-check: the executable code added by mc-02 and mc-08 must be
# IDENTICAL once doc comments are stripped (the pair discriminates on prose
# alone); this run applies both patches to twin base trees and diffs them.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-08}"
ITEM_DIR_MC02="${ITEM_DIR_MC02:-$SCRIPT_DIR/../../items/mc-02}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-08 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: $(cargo --version); $(git --version); patch: $(patch --version 2>&1 | head -1)"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize shim base files (identical to the mc-02 witness base) ---"
mkdir -p src src/bin
BASE_SRC="$SCRIPT_DIR/../mc-02/run.sh"
# Extract the two shim files verbatim from the mc-02 runner so the twins share
# one base by construction.
awk '/^cat > src\/replay_spool.rs <<.SHIM_EOF.$/{f=1;next} f&&/^SHIM_EOF$/{exit} f{print}' "$BASE_SRC" > src/replay_spool.rs
awk '/^cat > src\/bin\/driver.rs <<.SHIM_EOF.$/{f=1;next} f&&/^SHIM_EOF$/{exit} f{print}' "$BASE_SRC" > src/bin/driver.rs
sed -i '' 's/^use mc02::/use mc08::/' src/bin/driver.rs
cat > Cargo.toml <<'SHIM_EOF'
[package]
name = "mc08"
version = "0.1.0"
edition = "2021"

[lib]
name = "mc08"
path = "src/replay_spool.rs"
SHIM_EOF
echo "base files (replay_spool.rs $(wc -l < src/replay_spool.rs | tr -d ' ') lines, driver.rs $(wc -l < src/bin/driver.rs | tr -d ' ') lines):"
find . -type f -not -path './.git/*' | sort

echo
echo "--- step 2: git apply --check ---"
git apply --check "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2b: patch -p1 --dry-run (cross-check; offset vs. reconstructed base is expected) ---"
patch -p1 --dry-run -i "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2c: apply for real (git apply) ---"
git apply "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"

echo
echo "--- step 3: cargo build (compile check) ---"
cargo build --bins 2>&1
echo "exit=$?"

echo
echo "--- step 3b: unintended-defect sweep: cargo clippy (advisory, not -D) ---"
cargo clippy --quiet 2>&1
echo "exit=$?"

echo
echo "--- step 4: measurement run (claims a/b/c) ---"
echo "Doc claims: intermediate peak ~ dataset + one merge group; seal peak ~2x"
echo "dataset (all remaining runs + full sealed output simultaneously); fsync"
echo "of every merged/sealed output happens while its inputs still exist."
./target/debug/driver measure "$BUILD_DIR/scratch-measure" 2>&1
echo "exit=$?"

echo
echo "--- step 4b: fault-injection witness for the compact_runs error path (curation fix 2026-07-25) ---"
echo "Claim (d): with a 1.0x-dataset quota failing the first compaction merge"
echo "mid-compaction, the repaired code must keep self.runs consistent -- no run"
echo "dropped from tracking, no dangling entry -- and a quota-lifted retry seal()"
echo "must emit every input record. (Control arm showing the pre-fix silent data"
echo "loss under this same fault: witnesses/mc-02/, step 6.)"
./target/debug/driver fault "$BUILD_DIR/scratch-fault" 2>&1
echo "exit=$? (expected 0 = FAULT-PATH RESULT: CONSISTENT)"

echo
echo "--- step 5: pair cross-check -- mc-02 vs mc-08 executable code identical modulo prose ---"
mkdir -p "$BUILD_DIR/pair/a" "$BUILD_DIR/pair/b"
awk '/^cat > src\/replay_spool.rs <<.SHIM_EOF.$/{f=1;next} f&&/^SHIM_EOF$/{exit} f{print}' "$BASE_SRC" > "$BUILD_DIR/pair/a/replay_spool.rs"
cp "$BUILD_DIR/pair/a/replay_spool.rs" "$BUILD_DIR/pair/b/replay_spool.rs"
mkdir -p "$BUILD_DIR/pair/a/src" "$BUILD_DIR/pair/b/src"
mv "$BUILD_DIR/pair/a/replay_spool.rs" "$BUILD_DIR/pair/a/src/replay_spool.rs"
mv "$BUILD_DIR/pair/b/replay_spool.rs" "$BUILD_DIR/pair/b/src/replay_spool.rs"
# each patch also touches a second file; create its pre-image where needed
printf '# Changelog\n\n' > "$BUILD_DIR/pair/a/CHANGELOG.md"
(cd "$BUILD_DIR/pair/a" && patch -p1 -i "$ITEM_DIR_MC02/diff.patch" 2>&1; echo "mc-02 apply exit=$?")
(cd "$BUILD_DIR/pair/b" && patch -p1 -i "$ITEM_DIR/diff.patch" 2>&1; echo "mc-08 apply exit=$?")
strip_prose() { grep -v -E '^[[:space:]]*///' "$1" | grep -v -E '^[[:space:]]*$'; }
strip_prose "$BUILD_DIR/pair/a/src/replay_spool.rs" > "$BUILD_DIR/pair/a.code"
strip_prose "$BUILD_DIR/pair/b/src/replay_spool.rs" > "$BUILD_DIR/pair/b.code"
if diff -u "$BUILD_DIR/pair/a.code" "$BUILD_DIR/pair/b.code"; then
  echo "PAIR CHECK: executable code identical after stripping /// doc comments and blanks"
else
  echo "PAIR CHECK: CODE DIFFERS (see diff above)"
fi
