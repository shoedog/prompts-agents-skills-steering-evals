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

Investigated. I did not modify the worktree; `git status --short` is clean.

Root cause: [src/repo_loader.rs](/private/tmp/dbg-g5-ws/DBG-01/src/repo_loader.rs:407) now records `workspace_members` only from successfully parsed `[package]` manifests. That fixes glob workspaces because `crates/*` becomes concrete dirs like `crates/a`, but it drops non-glob declared members whose manifests are malformed. The failing test expects the root `[workspace] members = ["good", "bad"]` to survive even though `bad/Cargo.toml` is malformed.

Reproduced failures:

- `cargo fmt --all -- --check` fails on rustfmt reflow in [src/repo_loader.rs](/private/tmp/dbg-g5-ws/DBG-01/src/repo_loader.rs:1035).
- `cargo test --test name_resolution malformed_member_manifest_does_not_discard_valid_sibling_manifest -- --nocapture` fails at [tests/name_resolution/build_wiring_test.rs](/private/tmp/dbg-g5-ws/DBG-01/tests/name_resolution/build_wiring_test.rs:384):
  `left: ["good"]`, `right: ["bad", "good"]`.
- `cargo test -p prism repo_loader::tests::glob_workspace_members_expand_to_concrete_dirs -- --nocapture` passes, confirming the new glob behavior itself is valid.

The focused fix should be: keep parsed `[package]` dirs for glob safety, and also add declared `[workspace].members` entries that are non-glob, never raw `*` patterns. Then run `cargo fmt --all`, `cargo fmt --all -- --check`, the failing malformed-member test, and the glob regression test.

GitHub note: current PR #124 is merged and latest visible checks are green at a later head SHA, while this isolated clone is at the failing pre-fix SHA `04c6b0b`.



(The arm made no code changes.)
