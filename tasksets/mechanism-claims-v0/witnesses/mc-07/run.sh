#!/usr/bin/env bash
# mc-07 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Clean twin of mc-03. Re-runnable: shim base src/main.rs + base
# docs/RESUME-archive.md, apply items/mc-07/diff.patch, build `backfill`, run
# the RESUME doc's "Next step (runnable now)" command extracted from the
# patched doc, plus cross-probes of both accept-list guards.
#
# SHIMS: Cargo.toml; base main.rs support code (stubs print their args; the
# post-state signatures verify_archive(&Opts,bool),
# load_canonical(&Opts,bool,Option<&Path>), adjudicate_canonical(&Opts,
# Option<&Path>) live in the base). Parse loop, both guards, dispatch arms,
# doc next-step come ONLY from diff.patch.
#
# CLAIM under test (item labeled CLEAN): the documented command
# `backfill verify-archive --rebuild-index` is runnable exactly as written --
# the --rebuild-index guard accept-lists verify-archive; the stricter-looking
# guard below it governs a DIFFERENT flag (--emit-report). Expect exit 0 with
# verify_archive(rebuild_index=true). FALSIFIER: a parse-time Config error.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-07}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-07 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
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
name = "backfill"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "backfill"
path = "src/main.rs"
SHIM_EOF
cat > src/main.rs <<'SHIM_EOF'
//! backfill CLI -- BASE file (reconstruction). Subcommand impls are stubs that
//! print their arguments; the parse/dispatch code is what the diff modifies.

use std::env;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

#[derive(Debug)]
pub enum CliError {
    Config(String),
}

impl std::fmt::Display for CliError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CliError::Config(msg) => write!(f, "config error: {msg}"),
        }
    }
}

pub struct Opts {
    pub dry_run: bool,
}

fn next_value(args: &mut env::Args, flag: &str) -> Result<String, CliError> {
    args.next().ok_or_else(|| CliError::Config(format!("{flag} requires a value")))
}

fn verify_archive(opts: &Opts, rebuild_index: bool) -> Result<(), CliError> {
    println!(
        "verify_archive: dry_run={} rebuild_index={}",
        opts.dry_run, rebuild_index
    );
    Ok(())
}

fn load_canonical(opts: &Opts, rebuild_index: bool, emit_report: Option<&Path>) -> Result<(), CliError> {
    println!(
        "load_canonical: dry_run={} rebuild_index={} emit_report={:?}",
        opts.dry_run, rebuild_index, emit_report
    );
    Ok(())
}

fn adjudicate_canonical(opts: &Opts, emit_report: Option<&Path>) -> Result<(), CliError> {
    println!(
        "adjudicate_canonical: dry_run={} emit_report={:?}",
        opts.dry_run, emit_report
    );
    Ok(())
}

fn run(cmd: String, mut args: env::Args) -> Result<(), CliError> {
    let mut dry_run = false;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--dry-run" => dry_run = true,
            other => return Err(CliError::Config(format!("unknown flag {other}"))),
        }
    }
    let opts = Opts { dry_run };
    match cmd.as_str() {
        "verify-archive" => verify_archive(&opts),
        "load-canonical" => load_canonical(&opts),
        "adjudicate-canonical" => adjudicate_canonical(&opts),
        other => Err(CliError::Config(format!("unknown subcommand {other}"))),
    }
}

fn main() -> ExitCode {
    let mut args = env::args();
    let _bin = args.next();
    let Some(cmd) = args.next() else {
        eprintln!("usage: backfill <subcommand> [flags]");
        return ExitCode::from(2);
    };
    match run(cmd, args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::from(2)
        }
    }
}
SHIM_EOF
cat > docs/RESUME-archive.md <<'SHIM_EOF'
# RESUME — archive maintenance

## State
The July archive sweep left 214 orphaned index entries; the walker now
knows how to rebuild the index in place.

## Next step (runnable now)
SHIM_EOF
echo "base files:"
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
echo "--- step 3: cargo build (compile check of the patched tree) ---"
cargo build 2>&1
echo "exit=$?"

echo
echo "--- step 3b: unintended-defect sweep: cargo clippy (advisory, not -D) ---"
cargo clippy --quiet 2>&1
echo "exit=$?"

echo
echo "--- step 4: run the RESUME doc's documented next step verbatim ---"
DOC_CMD="$(grep -E '^    backfill ' docs/RESUME-archive.md | sed -E 's/^    //')"
echo "command documented in docs/RESUME-archive.md 'Next step (runnable now)': $DOC_CMD"
echo "expectation (clean hypothesis): exit 0, verify_archive rebuild_index=true; falsifier: Config error"
# shellcheck disable=SC2086
./target/debug/${DOC_CMD} 2>&1
echo "exit=$?"

echo
echo "--- step 5: cross-probes of both guards (documented acceptance rules) ---"
echo "[probe A] backfill adjudicate-canonical --rebuild-index  (NOT accept-listed; expect Config error)"
./target/debug/backfill adjudicate-canonical --rebuild-index 2>&1
echo "exit=$?"
echo "[probe B] backfill verify-archive --emit-report out/report.json  (NOT accept-listed for --emit-report; expect Config error)"
./target/debug/backfill verify-archive --emit-report out/report.json 2>&1
echo "exit=$?"
echo "[probe C] backfill load-canonical --rebuild-index --emit-report out/report.json  (both accept-listed; expect exit 0)"
./target/debug/backfill load-canonical --rebuild-index --emit-report out/report.json 2>&1
echo "exit=$?"
echo "[probe D] backfill adjudicate-canonical --emit-report out/report.json  (accept-listed; expect exit 0)"
./target/debug/backfill adjudicate-canonical --emit-report out/report.json 2>&1
echo "exit=$?"
echo "[probe E] backfill bogus-subcommand --rebuild-index  (defect hunt: guard runs before dispatch, so the"
echo "          flag error is reported instead of 'unknown subcommand' -- an error either way; expect exit 2)"
./target/debug/backfill bogus-subcommand --rebuild-index 2>&1
echo "exit=$?"
