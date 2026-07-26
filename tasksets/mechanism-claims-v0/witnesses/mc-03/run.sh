#!/usr/bin/env bash
# mc-03 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Re-runnable: materializes a shim base src/main.rs (CliError, next_value,
# Opts, subcommand stubs, run() pre-image whose lines the diff context
# requires) + base docs/RESUME-g4c.md, applies items/mc-03/diff.patch, builds
# the `backfill` binary, then runs the RESUME doc's own "Next step (runnable
# now)" command EXTRACTED FROM THE PATCHED DOC.
#
# SHIMS: Cargo.toml; base main.rs support code (subcommand stubs print their
# args; the two-arg load/adjudicate signatures live in the base, matching the
# post-state call sites -- the base pre-image itself is not required to
# compile, only the patched tree is); base RESUME doc through its
# "## Next step (runnable now)" header. The parse loop, accept-list guard,
# dispatch arms, and doc next-step all come ONLY from diff.patch.
#
# HYPOTHESIS under test (truth.yaml mc-03-d1): the documented command
# `backfill audit-canonical --spinoff-binding out/rev9-bindings.json` is
# REJECTED at parse time by the accept-list guard the same diff adds
# (audit-canonical not in the matches! list). FALSIFIER: the command exits 0
# and audit_canonical runs.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-03}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-03 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
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

fn load_canonical(opts: &Opts, spinoff_binding: Option<&Path>) -> Result<(), CliError> {
    println!(
        "load_canonical: dry_run={} spinoff_binding={:?}",
        opts.dry_run, spinoff_binding
    );
    Ok(())
}

fn adjudicate_canonical(opts: &Opts, spinoff_binding: Option<&Path>) -> Result<(), CliError> {
    println!(
        "adjudicate_canonical: dry_run={} spinoff_binding={:?}",
        opts.dry_run, spinoff_binding
    );
    Ok(())
}

fn audit_canonical(opts: &Opts) -> Result<(), CliError> {
    println!("audit_canonical: dry_run={}", opts.dry_run);
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
cat > docs/RESUME-g4c.md <<'SHIM_EOF'
# RESUME — g4c canonical backfill

## State
Rev 9 failed with 1.13M incomplete rows; its spinoff-ratio bindings were
regenerated this session and written to `out/rev9-bindings.json`.

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
echo "--- step 4: minimal_trigger -- run the RESUME doc's documented next step verbatim ---"
mkdir -p out
printf '{}\n' > out/rev9-bindings.json   # the file the doc references exists
DOC_CMD="$(grep -E '^    backfill ' docs/RESUME-g4c.md | sed -E 's/^    //')"
echo "command documented in docs/RESUME-g4c.md 'Next step (runnable now)': $DOC_CMD"
echo "expectation (seeded hypothesis): parse-time Config error naming the accept-list; falsifier: exit 0"
# shellcheck disable=SC2086
./target/debug/${DOC_CMD} 2>&1
echo "exit=$?"

echo
echo "--- step 5: controls (rule out 'flag does not exist' and 'audit is broken per se') ---"
echo "[control A] backfill load-canonical --spinoff-binding out/rev9-bindings.json (accept-listed; expect exit 0)"
./target/debug/backfill load-canonical --spinoff-binding out/rev9-bindings.json 2>&1
echo "exit=$?"
echo "[control B] backfill adjudicate-canonical --spinoff-binding out/rev9-bindings.json (accept-listed; expect exit 0)"
./target/debug/backfill adjudicate-canonical --spinoff-binding out/rev9-bindings.json 2>&1
echo "exit=$?"
echo "[control C] backfill audit-canonical  (without the flag; expect exit 0)"
./target/debug/backfill audit-canonical 2>&1
echo "exit=$?"
