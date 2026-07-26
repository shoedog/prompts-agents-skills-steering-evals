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

**Investigation Result**

Root cause for the failing snapshot in this clone is `src/repo_loader.rs` narrowing `workspace_members` to only successfully parsed `[package]` manifest dirs. That fixed glob workspace members, but it dropped declared non-glob workspace members whose manifests are malformed. The failing test’s fixture declares `members = ["good", "bad"]`, but `bad/Cargo.toml` is intentionally malformed, so current code returns only `["good"]`.

Relevant local evidence:
- Local `HEAD`: `04c6b0b fix(repo_loader): expand workspace member globs to concrete dirs`
- Current GitHub PR #124 is already merged at `16faa4e`, with green checks from June 22, 2026, so the live PR has moved past this failing isolated snapshot.
- Format failure: `cargo fmt --check` wants only a rustfmt reflow in [src/repo_loader.rs](/private/tmp/dbg-g5d2-ws/DBG-01/src/repo_loader.rs:1035).
- Test failure: [tests/name_resolution/build_wiring_test.rs](/private/tmp/dbg-g5d2-ws/DBG-01/tests/name_resolution/build_wiring_test.rs:356) fails with `left: ["good"]`, `right: ["bad", "good"]`.
- Cause location: [src/repo_loader.rs](/private/tmp/dbg-g5d2-ws/DBG-01/src/repo_loader.rs:399) inserts only parsed `[package]` manifest dirs into `workspace_members`.

**Running Log**

1. Hypothesis: clone is pinned to the failing PR snapshot. Result: yes, detached at `04c6b0b`; clean worktree.
2. Alternative considered: format and tests could be independent. Result: format failure is only rustfmt in `repo_loader.rs`; test failure is workspace-member specific.
3. Alternative considered: resolver/cross-crate logic caused the test failure. Result: fixture/code inspection rules that out; `bad` is dropped before resolver behavior matters.
4. Hypothesis: last commit introduced this by replacing declared members with parsed package dirs. Result: yes, parent code inserted `[workspace].members`; `HEAD` does parsed `[package]` dirs only.
5. Hypothesis: full suite has only this local failure. Result: `cargo test` aborted at `name_resolution`; completed binaries totaled `1348 passed, 1 failed, 1 ignored` before abort.
6. Hypothesis: live PR still failed. Result: falsified; PR #124 is merged and checks are green at newer head `16faa4e`.

**Recommended Fix**

Use the union of:
- parsed `[package]` dirs, for glob expansion safety, and
- declared `[workspace].members` entries that are non-glob, so malformed declared members still survive.

Then run `cargo fmt --all -- --check`, the malformed-member test, the glob regression test, and the full relevant suite.

I did not edit files in this investigation pass.



(The arm made no code changes.)
