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

Investigation complete. Both CI failures trace to the PR's final commit, `04c6b0b fix(repo_loader): expand workspace member globs to concrete dirs`. Findings below, tagged per severity discipline.

## TL;DR

Commit `04c6b0b` fixed the ruff glob-workspace bug by replacing the source of `workspace_members` — but the replacement silently drops any workspace member whose own `Cargo.toml` is malformed, breaking a pre-existing resilience test from PR #103. The format failure is just an unformatted assertion in the same commit's new test.

## Failure 1 — format check (trivial)

`cargo fmt --check` flags one spot: the `assert!(inputs.cfg.workspace_members.contains(...) && ...)` expression in the new `glob_workspace_members_expand_to_concrete_dirs` test (`src/repo_loader.rs:1033`). The commit was made without running `cargo fmt`. Fix is mechanical: run `cargo fmt`.

## Failure 2 — WRONG: malformed member manifest now drops that member from `workspace_members`

**Failing test:** `build_wiring_test::malformed_member_manifest_does_not_discard_valid_sibling_manifest` (`tests/name_resolution/build_wiring_test.rs:384`) — a pre-existing pin added on main in PR #103, not part of this branch.

**Concrete failure scenario:** Root manifest declares `members = ["good", "bad"]`; `bad/Cargo.toml` is invalid TOML (`[package` — unclosed bracket). Expected `workspace_members == ["bad", "good"]`; actual `["good"]`.

**Causal chain:**
1. Before `04c6b0b`, `parse_rust_crate_config` read the root manifest's declared `[workspace].members` entries — the root manifest parses fine, so `bad` survived its own broken manifest.
2. `04c6b0b` deleted that and instead inserts the concrete dir of every successfully parsed `[package]` manifest (`src/repo_loader.rs:407-408`) — correct for glob workspaces like ruff's `crates/*`, where raw patterns never prefix-match concrete root paths.
3. But now membership *requires* the member's own manifest to parse: `bad/Cargo.toml` fails `text.parse::<toml::Value>()` at `src/repo_loader.rs:367` and the whole manifest is skipped, so `bad` never enters the set. (Its `crate_roots` convention fallback still works via `RustCrateConfig::from_convention` — that's why only the membership assertion fails.)

**Why this matters beyond the test:** `lib_root_member_dir` and `crate_name_for_root` prefix-match `workspace_members` against crate-root paths. A member missing from the list gets no member-dir mapping → no `crate_deps_by_root` entry → the cross-crate fallback (this PR's whole feature) is silently disabled for that member. That's the same silent-degradation shape as the ruff `+0` bug the commit was fixing, just with a different trigger. So the test is right and the code is wrong — this shouldn't be resolved by re-baselining the test.

## Recommended fix (not applied)

Union both sources in `parse_rust_crate_config`:
- Keep the new insertion of each parsed `[package]` manifest's concrete dir (preserves the ruff glob fix).
- Restore insertion of declared `[workspace].members` entries, **skipping entries containing glob metacharacters** (`*`, `?`, `[`) so raw patterns can't re-enter the set.

That makes both tests pass by construction: the glob test's assertions ("concrete dirs present", "no `*` remains") hold because glob entries are skipped and concrete dirs come from the `[package]` walk; the malformed-sibling test holds because `bad` is a literal entry in the valid root manifest. Then `cargo fmt` for failure 1.

Say the word and I'll apply both fixes and re-run the suite.

(The arm made no code changes.)
