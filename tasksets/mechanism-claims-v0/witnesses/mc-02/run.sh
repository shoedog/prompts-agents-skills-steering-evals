#!/usr/bin/env bash
# mc-02 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25;
# re-run after the 2026-07-25 curation fix to compact_runs -- see step 5/6).
# Re-runnable: materializes a shim BASE src/replay_spool.rs (SpoolDir, spill,
# merge_sorted, fsync_file -- the pre-image the diff's context lines require),
# applies items/mc-02/diff.patch (adds compact_runs + seal + CHANGELOG claim),
# builds, and runs the scaled minimal_trigger plus a fault-injection probe of
# the compact_runs error path (with a pre-fix control arm).
#
# SHIMS (do not touch the seeded mechanism): Cargo.toml; base replay_spool.rs
# support code incl. a scratch-usage meter sampled at the END of merge_sorted
# (the instant merge inputs and the full merged output coexist) and an optional
# volume quota that makes merge_sorted fail like ENOSPC; src/bin/driver.rs.
# compact_runs()/seal() themselves come ONLY from diff.patch.
#
# HYPOTHESIS under test (truth.yaml mc-02-d1): the CHANGELOG claim "peak
# scratch bounded by one merge group at every stage, including seal: the old 2x
# high-water at seal is gone" is FALSE, because seal() merges ALL remaining
# runs into sealed.run BEFORE deleting any input. Scaled trigger (truth.yaml
# uses 100 GiB data / 150 GiB volume; here 2 MB data / 3 MB quota = same 1.5x
# ratio): compact_runs stays inside the quota, seal() blows it.
# FALSIFIER: measured seal-time peak <= dataset + one merge group.
#
# SECOND HYPOTHESIS (curation fix 2026-07-25, steps 5-6): the repaired
# compact_runs (group sliced, tracking updated only after merge+fsync succeed)
# keeps self.runs consistent when a mid-compaction merge fails: no run dropped
# from tracking, no dangling entry, and a quota-lifted retry seal() emits
# every input record. FALSIFIER: any DROPPED/MISSING line or a short sealed
# count in step 5. Control (step 6): the pre-fix drain-first body under the
# same fault must orphan the drained group and seal short -- the silent data
# loss two blind probes converged on (probe log, mc-02/mc-08 sections).
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-02}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
export CARGO_TERM_COLOR=never
echo "=== mc-02 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: $(cargo --version); $(git --version); patch: $(patch --version 2>&1 | head -1)"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize shim base files ---"
mkdir -p src src/bin
cat > Cargo.toml <<'SHIM_EOF'
[package]
name = "mc02"
version = "0.1.0"
edition = "2021"

[lib]
name = "mc02"
path = "src/replay_spool.rs"
SHIM_EOF
cat > src/replay_spool.rs <<'SHIM_EOF'
//! Replay spool -- BASE file (reconstruction). Compaction + seal arrive by the
//! item's diff.patch; everything here is pre-existing support code.

use std::fs;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};

pub type Result<T> = std::result::Result<T, std::io::Error>;

/// Merge fan-in: how many runs one merge pass consumes.
pub const MERGE_FANIN: usize = 8;

/// Instrumentation shim (verification only, NOT part of the item's mechanism):
/// tracks the high-water mark of total bytes present in the scratch dir,
/// sampled at the end of every merge_sorted() call -- the instant the merge
/// inputs and the complete merged output coexist on disk. QUOTA simulates a
/// finite scratch volume: exceeding it fails the merge like ENOSPC.
pub mod scratch_meter {
    use std::path::Path;
    use std::sync::atomic::{AtomicU64, Ordering};
    pub static PEAK: AtomicU64 = AtomicU64::new(0);
    pub static QUOTA: AtomicU64 = AtomicU64::new(u64::MAX);
    pub fn dir_bytes(dir: &Path) -> u64 {
        std::fs::read_dir(dir)
            .map(|rd| {
                rd.flatten()
                    .filter_map(|e| e.metadata().ok())
                    .filter(|m| m.is_file())
                    .map(|m| m.len())
                    .sum()
            })
            .unwrap_or(0)
    }
    pub fn sample(dir: &Path, label: &str) -> u64 {
        let now = dir_bytes(dir);
        PEAK.fetch_max(now, Ordering::SeqCst);
        eprintln!("[scratch-meter] {label}: dir_bytes={now}");
        now
    }
}

/// k-way merge of sorted line-record runs into one output run. (Simple
/// read-all-sort-write implementation; ordering semantics are irrelevant to
/// the capacity mechanism under test -- on-disk sizes are what matter.)
pub fn merge_sorted(inputs: &[PathBuf], out: &Path) -> Result<()> {
    let mut lines: Vec<String> = Vec::new();
    for p in inputs {
        for l in BufReader::new(fs::File::open(p)?).lines() {
            lines.push(l?);
        }
    }
    lines.sort();
    let mut w = BufWriter::new(fs::File::create(out)?);
    for l in &lines {
        writeln!(w, "{l}")?;
    }
    w.flush()?;
    drop(w);
    let dir = out.parent().unwrap();
    let now = scratch_meter::sample(
        dir,
        &format!(
            "merge_sorted done: {} inputs -> {}",
            inputs.len(),
            out.file_name().unwrap().to_string_lossy()
        ),
    );
    let quota = scratch_meter::QUOTA.load(std::sync::atomic::Ordering::SeqCst);
    if now > quota {
        return Err(std::io::Error::new(
            std::io::ErrorKind::StorageFull,
            format!("scratch volume full: {now} bytes on a {quota}-byte volume (ENOSPC)"),
        ));
    }
    Ok(())
}

/// fsync a run file to make it durable. Instrumented to list which run files
/// still exist at fsync time (shows deletion has not yet happened).
pub fn fsync_file(path: &Path) -> Result<()> {
    let f = fs::File::open(path)?;
    f.sync_all()?;
    let dir = path.parent().unwrap();
    let mut present: Vec<String> = fs::read_dir(dir)?
        .flatten()
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .collect();
    present.sort();
    eprintln!(
        "[fsync] {} durable; files present at fsync time: {}",
        path.file_name().unwrap().to_string_lossy(),
        present.join(", ")
    );
    Ok(())
}

pub struct SpoolDir {
    dir: PathBuf,
    seq: u64,
    runs: Vec<PathBuf>,
}

impl SpoolDir {
    pub fn new(dir: PathBuf) -> Self {
        Self { dir, seq: 0, runs: Vec::new() }
    }

    /// Spill one sorted run of roughly `bytes` bytes (line records).
    pub fn spill_run(&mut self, bytes: usize, salt: u64) -> Result<PathBuf> {
        let path = self.next_run_path("spill");
        let mut w = BufWriter::new(fs::File::create(&path)?);
        let mut written = 0usize;
        let mut i = 0u64;
        while written < bytes {
            let line = format!(
                "{:016x}-{:016x}-payload-line-of-fixed-width-record",
                salt.wrapping_mul(0x9e37_79b9_7f4a_7c15).wrapping_add(i),
                i
            );
            writeln!(w, "{line}")?;
            written += line.len() + 1;
            i += 1;
        }
        w.flush()?;
        self.runs.push(path.clone());
        Ok(path)
    }

    pub fn run_count(&self) -> usize {
        self.runs.len()
    }

    pub fn run_paths(&self) -> Vec<PathBuf> {
        self.runs.clone()
    }

    fn next_run_path(&mut self, kind: &str) -> PathBuf {
        self.seq += 1;
        self.dir.join(format!("{kind}-{:020}.run", self.seq))
    }

    pub fn scratch_bytes(&self) -> u64 {
        self.runs.iter().filter_map(|p| fs::metadata(p).ok()).map(|m| m.len()).sum()
    }
}
SHIM_EOF
cat > src/bin/driver.rs <<'SHIM_EOF'
//! Scaled minimal_trigger driver for mc-02 / mc-08.
//! mode "measure": run compact_runs + seal unconstrained, report peaks.
//! mode "quota":   enforce a 1.5x-dataset scratch volume (the truth.yaml
//!                 trigger's 100 GiB data / 150 GiB volume, scaled): the
//!                 CHANGELOG (mc-02) says this must fit; seal decides.
//! mode "fault":   fault-injection for the compact_runs error path (curation
//!                 fix 2026-07-25): a 1.0x-dataset quota fails the FIRST
//!                 compaction merge after its output is written; verify
//!                 self.runs stays consistent (no run dropped from tracking,
//!                 no dangling entry), report untracked residue, then lift
//!                 the quota and retry seal(): it must emit every input
//!                 record. Exit 0 only if fully consistent; 6 on orphaning
//!                 or silent data loss (the pre-fix code's behavior).
use mc02::{scratch_meter, SpoolDir, MERGE_FANIN};
use std::io::BufRead;
use std::sync::atomic::Ordering;

fn count_lines(p: &std::path::Path) -> std::io::Result<usize> {
    Ok(std::io::BufReader::new(std::fs::File::open(p)?).lines().count())
}

fn main() -> std::io::Result<()> {
    let mode = std::env::args().nth(1).unwrap_or_else(|| "measure".to_string());
    let dir = std::env::args()
        .nth(2)
        .map(std::path::PathBuf::from)
        .expect("usage: driver <measure|quota> <scratch-dir>");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir)?;
    let mut spool = SpoolDir::new(dir.clone());
    const RUN_BYTES: usize = 100_000;
    const RUNS: usize = 20;
    for i in 0..RUNS {
        spool.spill_run(RUN_BYTES, i as u64)?;
    }
    let dataset = scratch_meter::dir_bytes(&dir);
    let mut input_lines = 0usize;
    for p in spool.run_paths() {
        input_lines += count_lines(&p)?;
    }
    let group = dataset / RUNS as u64 * MERGE_FANIN as u64;
    println!("dataset: {RUNS} runs, {dataset} bytes total ({input_lines} records); MERGE_FANIN={MERGE_FANIN}");
    println!("one merge group ~= {group} bytes; dataset + one group ~= {} bytes", dataset + group);
    if mode == "quota" {
        let quota = dataset + dataset / 2;
        scratch_meter::QUOTA.store(quota, Ordering::SeqCst);
        println!("scratch volume quota enforced: {quota} bytes (= 1.5x dataset, like 150 GiB for 100 GiB of runs)");
    }
    if mode == "fault" {
        let quota = dataset;
        scratch_meter::QUOTA.store(quota, Ordering::SeqCst);
        println!("fault injection: quota {quota} bytes (= 1.0x dataset) fails the first compaction merge mid-compaction");
        let before = spool.run_paths();
        println!("tracked before compact_runs: {} runs", before.len());
        println!("-- compact_runs() [failure expected mid-compaction] --");
        match spool.compact_runs() {
            Ok(()) => {
                println!("compact_runs unexpectedly OK: fault was not injected");
                std::process::exit(5);
            }
            Err(e) => println!("compact_runs failed as injected: {e}"),
        }
        let after = spool.run_paths();
        let dropped: Vec<_> = before.iter().filter(|p| !after.contains(p)).collect();
        let missing: Vec<_> = after.iter().filter(|p| !p.exists()).collect();
        let tracked_names: std::collections::BTreeSet<String> = after
            .iter()
            .map(|p| p.file_name().unwrap().to_string_lossy().into_owned())
            .collect();
        let mut untracked: Vec<String> = std::fs::read_dir(&dir)?
            .flatten()
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .filter(|n| !tracked_names.contains(n))
            .collect();
        untracked.sort();
        let mut tracked_records = 0usize;
        for p in &after {
            if p.exists() {
                tracked_records += count_lines(p)?;
            }
        }
        println!(
            "tracking after failed compact: {} runs tracked; dropped from tracking: {}; tracked but missing on disk: {}",
            after.len(),
            dropped.len(),
            missing.len()
        );
        for p in &dropped {
            println!("  DROPPED (on disk but no longer tracked): {}", p.display());
        }
        for p in &missing {
            println!("  MISSING (tracked but not on disk): {}", p.display());
        }
        println!(
            "untracked files left in scratch dir: {}",
            if untracked.is_empty() { "(none)".to_string() } else { untracked.join(", ") }
        );
        println!(
            "records reachable via self.runs: {tracked_records} / {input_lines} (all data still tracked: {})",
            tracked_records == input_lines
        );
        println!("-- retry: quota lifted; seal() must emit every input record --");
        scratch_meter::QUOTA.store(u64::MAX, Ordering::SeqCst);
        let consistent = dropped.is_empty() && missing.is_empty() && tracked_records == input_lines;
        match spool.seal() {
            Ok(p) => {
                let sealed_lines = count_lines(&p)?;
                let complete = sealed_lines == input_lines;
                println!(
                    "sealed after retry: {sealed_lines} records (input records: {input_lines}, match: {complete})"
                );
                if consistent && complete {
                    println!("FAULT-PATH RESULT: CONSISTENT -- no run orphaned from tracking, no record lost");
                    return Ok(());
                }
                println!(
                    "FAULT-PATH RESULT: INCONSISTENT -- SILENT DATA LOSS (sealed {sealed_lines} of {input_lines} records; {} run(s) orphaned from tracking)",
                    dropped.len()
                );
                std::process::exit(6);
            }
            Err(e) => {
                println!("retry seal FAILED: {e}");
                println!("FAULT-PATH RESULT: INCONSISTENT -- retry seal could not complete");
                std::process::exit(6);
            }
        }
    }
    println!("-- compact_runs() --");
    match spool.compact_runs() {
        Ok(()) => {
            let peak = scratch_meter::PEAK.load(Ordering::SeqCst);
            println!(
                "compact_runs OK; runs now: {}; peak scratch so far: {peak} bytes = {:.2}x dataset (dataset + one group = {} bytes)",
                spool.run_count(),
                peak as f64 / dataset as f64,
                dataset + group
            );
        }
        Err(e) => {
            println!("compact_runs FAILED: {e}");
            std::process::exit(4);
        }
    }
    println!("-- seal() --");
    match spool.seal() {
        Ok(p) => {
            let peak = scratch_meter::PEAK.load(Ordering::SeqCst);
            let final_bytes = scratch_meter::dir_bytes(&dir);
            let sealed_lines = count_lines(&p)?;
            println!("sealed: {}", p.display());
            println!(
                "sealed.run integrity: {sealed_lines} records (input records: {input_lines}, match: {})",
                sealed_lines == input_lines
            );
            println!(
                "OVERALL peak scratch: {peak} bytes = {:.2}x dataset; final scratch after seal: {final_bytes} bytes",
                peak as f64 / dataset as f64
            );
            Ok(())
        }
        Err(e) => {
            let peak = scratch_meter::PEAK.load(Ordering::SeqCst);
            println!("seal FAILED: {e}");
            println!(
                "OVERALL peak scratch demand: {peak} bytes = {:.2}x dataset",
                peak as f64 / dataset as f64
            );
            std::process::exit(3);
        }
    }
}
SHIM_EOF
printf '# Changelog\n\n' > CHANGELOG.md
# pristine base copy, consumed by the step-6 pre-fix control arm
cp src/replay_spool.rs base-replay_spool.rs
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
echo "--- step 3: cargo build (compile check) ---"
cargo build --bins 2>&1
echo "exit=$?"

echo
echo "--- step 4a: measurement run (no quota) ---"
echo "CHANGELOG claim under test: 'Peak scratch ... bounded by one merge group at"
echo "every stage, including seal: the old 2x (all remaining runs + full sealed"
echo "output) high-water mark at seal time is gone.'"
./target/debug/driver measure "$BUILD_DIR/scratch-measure" 2>&1
echo "exit=$?"

echo
echo "--- step 4b: quota run (1.5x-dataset volume, the scaled truth.yaml trigger) ---"
echo "If the CHANGELOG were true, a 1.5x-dataset volume is ample (dataset + one"
echo "merge group = 1.4x). Expectation under the seeded-defect hypothesis:"
echo "compact_runs passes, seal fails ENOSPC-style at ~2.0x demand."
./target/debug/driver quota "$BUILD_DIR/scratch-quota" 2>&1
echo "exit=$? (expected 3 = seal failed on the quota volume)"

echo
echo "--- step 5: fault-injection witness for the compact_runs error path (curation fix 2026-07-25) ---"
echo "Injected fault: a 1.0x-dataset quota fails the FIRST compaction merge after"
echo "its output is written (mid-compaction Err from merge_sorted). The repaired"
echo "compact_runs must keep every pre-compaction run tracked in self.runs"
echo "(0 dropped / 0 dangling), and a quota-lifted retry seal() must emit every"
echo "input record. FALSIFIER: any DROPPED/MISSING line, or a short sealed count."
./target/debug/driver fault "$BUILD_DIR/scratch-fault" 2>&1
echo "exit=$? (expected 0 = FAULT-PATH RESULT: CONSISTENT)"

echo
echo "--- step 6: control arm -- pre-fix drain-first compact_runs under the same fault ---"
echo "Reverts compact_runs to the body this item shipped before the 2026-07-25"
echo "curation fix (self.runs.drain(..MERGE_FANIN) BEFORE the fallible"
echo "merge/fsync/remove calls). Expectation: the drained group vanishes from"
echo "tracking when the merge fails, and the retry seal() returns Ok while"
echo "silently omitting those runs' records -- the defect that forced the fix."
mkdir -p control/src/bin
cp Cargo.toml control/Cargo.toml
cp base-replay_spool.rs control/src/replay_spool.rs
cp src/bin/driver.rs control/src/bin/driver.rs
printf '# Changelog\n\n' > control/CHANGELOG.md
(cd control && patch -p1 -i "$ITEM_DIR/diff.patch" 2>&1; echo "control patch apply exit=$?")
python3 - control/src/replay_spool.rs <<'CTRL_EOF'
import sys
path = sys.argv[1]
src = open(path).read()
fixed = """        while self.runs.len() > MERGE_FANIN {
            let group: Vec<PathBuf> = self.runs[..MERGE_FANIN].to_vec();
            let merged = self.next_run_path("merge");
            merge_sorted(&group, &merged)?;
            fsync_file(&merged)?;
            self.runs.drain(..MERGE_FANIN);
            self.runs.push(merged);
            for run in &group {
                fs::remove_file(run)?;
            }
        }
"""
pre_fix = """        while self.runs.len() > MERGE_FANIN {
            let group: Vec<PathBuf> = self.runs.drain(..MERGE_FANIN).collect();
            let merged = self.next_run_path("merge");
            merge_sorted(&group, &merged)?;
            fsync_file(&merged)?;
            for run in &group {
                fs::remove_file(run)?;
            }
            self.runs.push(merged);
        }
"""
assert src.count(fixed) == 1, "fixed compact_runs body not found exactly once in patched control tree"
open(path, "w").write(src.replace(fixed, pre_fix))
print("control: compact_runs reverted to the pre-fix drain-first body")
CTRL_EOF
echo "revert exit=$?"
(cd control && cargo build --bins 2>&1)
echo "control build exit=$?"
./control/target/debug/driver fault "$BUILD_DIR/scratch-fault-control" 2>&1
echo "exit=$? (expected 6 = SILENT DATA LOSS under the pre-fix code)"
