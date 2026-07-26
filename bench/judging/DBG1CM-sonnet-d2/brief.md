# Debug diagnosis grading — DBG-01, one anonymous arm

An engineer was given the terse task below in a repo whose CI failed. Grade
their final report (and diff, if any) against the settled ground truth. You
do not know who the engineer is.

Ground truth (verified against the repository's actual history):
- Root cause of the test failure: commit 04c6b0b ("expand workspace member
  globs to concrete dirs") records only directories with a parsed [package],
  which DROPS declared non-glob members whose manifests are malformed —
  breaking malformed_member_manifest_does_not_discard_valid_sibling_manifest.
- Independent second failure: a rustfmt violation on a long assert! in the
  same commit (the CI format check).
- The landed fix (16faa4e, "keep non-glob workspace members") UNIONS the
  parsed-package dirs with the declared non-glob members, preserving the
  original glob-expansion fix.
Grading: root_cause_match = names the non-glob-member drop mechanism;
fmt_issue_identified = separately identifies the rustfmt violation;
fix_attempted = the arm changed code (vs diagnosis-only report);
fix_shape_match = if a fix exists, it unions/preserves both behaviors (false
when no fix was attempted).

## The task (verbatim)

Format check and test suite failed on PR #124 for branch cross-crate-use-resolution   in this repo. Investigate


## The engineer's final report

## Investigation summary

**Both CI failures trace to the same commit: `04c6b0b` (`fix(repo_loader): expand workspace member globs to concrete dirs`).** They have independent causes.

### Hypothesis log

| # | Hypothesis | Probe | Result |
|---|---|---|---|
| 0 | Current checkout already reproduces the failing PR state | `cargo fmt --check` / `cargo test` | Format check failed (1 diff), test suite failed (1 test) → confirmed, checkout is the failing state |
| 1 | Format failure is just unformatted new code, unrelated to the test regression | `cargo fmt --check` output | Single diff, confined to the new test added in `04c6b0b` (`src/repo_loader.rs:1033`) — cosmetic only |
| 2 | Test failure (`malformed_member_manifest_does_not_discard_valid_sibling_manifest`) is a regression introduced by `04c6b0b`, not a pre-existing/newly-added gap | Checked out `repo_loader.rs` from the parent commit `53ab724`, reran just that test | **Passed** on pre-`04c6b0b` code, **fails** on current HEAD → confirms `04c6b0b` is the regression source. Also confirmed via `git log -S` that the test dates to `629384a` (2026-06-17), 5 days before `04c6b0b` — not a new/untested case. |
| 3 (alt. cause ruled out) | Maybe the malformed manifest merely lacks a `[package]` table (parses fine) rather than failing TOML parsing outright — would locate the bug at a different check | Built a throwaway crate with `toml = "0.8.23"` and parsed the exact malformed string (`"[package\nname = \"bad\"\n"`) | **Hard parse error** ("invalid table header", unclosed `[package`) — not a missing-key case |
| 4 (alt. cause ruled out) | Maybe `bad/Cargo.toml` never reaches the parsing loop at all (excluded earlier, e.g. from `manifest_hashes`) | Read `collect_manifest_hashes_inner` (`src/repo_loader.rs:186`) | It hashes every file literally named `Cargo.toml` with zero content validation — `bad/Cargo.toml` **is** in `manifest_hashes` |

### Root cause

`04c6b0b` rewrote how `workspace_members` gets populated (`src/repo_loader.rs:294-409`). The old code read the root manifest's declared `[workspace].members` patterns directly. The new code instead derives `workspace_members` *exclusively* from directories with a manifest that both (a) parses as valid TOML and (b) contains a `[package]` table — a real fix for the glob case (ruff's `crates/*` never prefix-matched concrete paths), but it dropped the old members-list-based source entirely.

Side effect: at line 367, `let Ok(value) = text.parse::<toml::Value>() else { continue; };` skips the *entire* per-manifest body — including the `workspace_members.insert(...)` at line 408 — for any manifest that fails to parse. So a workspace member whose own `Cargo.toml` is malformed (e.g. truncated `[package` header) silently disappears from `workspace_members`, even though it's still declared in the root workspace and still recovered into `crate_roots` via the separate, parse-independent `from_convention()` fallback (line 280 / 461). That asymmetry is exactly what the test `malformed_member_manifest_does_not_discard_valid_sibling_manifest` (`tests/name_resolution/build_wiring_test.rs:356-389`) catches: expects `workspace_members == ["bad", "good"]`, gets `["good"]`.

The format-check failure is unrelated in substance — just the new test block in the same commit never got run through `cargo fmt`.

I haven't made any changes yet. Want me to fix both (rustfmt the new test, and restore `workspace_members` inclusion for declared-but-malformed members without reintroducing the glob-pattern bug the commit was fixing)?

(The arm made no code changes.)
