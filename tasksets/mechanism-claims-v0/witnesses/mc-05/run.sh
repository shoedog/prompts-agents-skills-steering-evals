#!/usr/bin/env bash
# mc-05 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Re-runnable: applies items/mc-05/diff.patch (new file ci/run-suite.sh) into a
# minimal cargo crate that passes fmt+clippy and has EXACTLY ONE failing test,
# then runs the CI gate script and compares its exit status against the test
# runner's own.
#
# SHIMS: Cargo.toml + src/lib.rs fixture crate (one passing test, one seeded
# failing test), normalized once with `cargo fmt` during prep so the fmt/clippy
# steps of the script pass and the ONLY failing check is the test suite.
# ci/run-suite.sh comes ONLY from diff.patch and is run via `bash` (the patch
# carries no exec bit).
#
# HYPOTHESIS under test (truth.yaml mc-05-d1): the header comment claims "the
# script's exit status is the test runner's own exit code", but the suite runs
# as `cargo test --workspace 2>&1 | tail -40` under plain `set -eu` (no
# pipefail), so the pipeline's status is tail's (0) and the script exits 0
# while cargo test exits 101. FALSIFIER: the script exits nonzero.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-05}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-05 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: $(cargo --version); $(cargo fmt --version); $(cargo clippy --version); bash $BASH_VERSION"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize fixture crate (fmt/clippy-clean, one seeded failing test) ---"
cat > Cargo.toml <<'SHIM_EOF'
[package]
name = "ci-demo"
version = "0.1.0"
edition = "2021"
SHIM_EOF
mkdir -p src
cat > src/lib.rs <<'SHIM_EOF'
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    #[test]
    fn addition_works() {
        assert_eq!(super::add(2, 2), 4);
    }

    #[test]
    fn seeded_failure() {
        assert_eq!(super::add(2, 2), 5);
    }
}
SHIM_EOF
cargo fmt 2>&1   # normalize fixture formatting (shim prep)
echo "fixture files:"
find . -type f -not -path './.git/*' -not -path './target/*' | sort

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
echo "--- step 3: bash -n parse check of the diff's script ---"
bash -n ci/run-suite.sh 2>&1
echo "exit=$?"

echo
echo "--- step 4: pre-checks -- prove fmt and clippy pass, so the ONLY failing check is the suite ---"
echo "[pre-check] cargo fmt --check (expect 0)"
cargo fmt --check 2>&1
echo "exit=$?"
echo "[pre-check] cargo clippy --workspace --quiet -- -D warnings (expect 0)"
cargo clippy --workspace --quiet -- -D warnings 2>&1
echo "exit=$?"

echo
echo "--- step 5: probe A -- the test runner's OWN exit code (no pipe) ---"
echo "expectation: nonzero (one seeded failing test)"
cargo test --workspace 2>&1
echo "cargo test exit=$?"

echo
echo "--- step 6: probe B -- the CI gate script (THE minimal_trigger) ---"
echo "header comment claims: \"the script's exit status is the test runner's own"
echo "exit code, so the CI step fails exactly when the suite fails\""
echo "expectation (seeded hypothesis): script exits 0 despite the failing suite; falsifier: nonzero"
bash ci/run-suite.sh 2>&1
echo "run-suite.sh exit=$?"

echo
echo "--- step 7: probe C -- fmt/clippy failures are NOT swallowed (truth.yaml reject_if support) ---"
echo "copy the crate, break formatting, rerun the script; expectation: nonzero exit at the fmt step"
mkdir -p "$BUILD_DIR/badfmt"
cp -R Cargo.toml src ci "$BUILD_DIR/badfmt/"
printf 'pub fn ugly( x:i32 )->i32{ x }\n' >> "$BUILD_DIR/badfmt/src/lib.rs"
( cd "$BUILD_DIR/badfmt" && bash ci/run-suite.sh 2>&1 )
echo "badfmt run-suite.sh exit=$?"
