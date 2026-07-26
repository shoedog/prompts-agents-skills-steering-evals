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

Verification gate complete. Final state below.

## Investigation summary

Both CI failures on PR #124 traced to a **single commit — `04c6b0b`** ("fix(repo_loader): expand workspace member globs to concrete dirs").

**Debug log (hypothesis → probe → result)**

| Hypothesis | Probe | Result |
|---|---|---|
| Format check fails | `cargo fmt --check` | ✅ unformatted `assert!` chain in `repo_loader.rs`, added by `04c6b0b` |
| Test suite fails | `cargo test` | ✅ one failure: `malformed_member_manifest_does_not_discard_valid_sibling_manifest` (`["good"]` vs `["bad","good"]`) |
| **A:** `04c6b0b` regressed member population | bisect at `04c6b0b^` vs `04c6b0b` | ✅ passes at parent, fails at commit → **root cause** |
| **B:** test is a new spec, not a regression | `git log -S` | ❌ ruled out — test added in #103, passed at parent |
| **C:** `crate_roots`/`workspace_members` share a broken path | read code | ❌ ruled out — `bad/src/lib.rs` reaches `crate_roots` via `from_convention` (file scan); only `workspace_members` regressed |

**Root cause:** `04c6b0b` switched `workspace_members` from the root manifest's declared `[workspace].members` to the dirs of *successfully-parsed* `[package]` manifests. A member whose own `Cargo.toml` is malformed fails `toml::parse` and is skipped (`repo_loader.rs:367`), so it vanishes from the member set.

**Fix (`src/repo_loader.rs`):** in the existing `[workspace]` block, also record **concrete** declared members, **skipping glob patterns** — globs are still recovered from parsed `[package]` dirs (keeping `04c6b0b`'s improvement), and concrete members again come straight from the root manifest so a malformed member survives. `cargo fmt` normalized the pre-existing assert chain.

## Verification (per the gate)

- `cargo fmt --check` — **clean**
- `cargo test` (default, full) — **2415 passed, 0 failed, 1 ignored** (28 binaries, exit 0)
- `cargo test --features mcp` (full) — **2476 passed, 0 failed, 1 ignored** (30 binaries, exit 0)
- Every fixed behavior has a test that **fails on pre-change code**: the regression test (bisect-proven) plus a new edge-case test `mixed_concrete_and_glob_members_survive_a_malformed_concrete_manifest` (mixed concrete+glob with a malformed concrete member) — I confirmed both fail by temporarily disabling the fix's insert, then restored it.
- **No failures outside this task's scope.** (Pre-existing `unused_import`/`unused_variable` warnings in `tests/` are noted in `VERIFICATION.md` as untouched/out-of-scope; they are warnings, not failures.)

`VERIFICATION.md` written at repo root with commands, totals, `## Verified`, and `## Not verified` (Tier-A accuracy harness not re-run; malformed-member-inside-a-glob is an inherent limitation, unrelated to #124).

**Working tree:** `src/repo_loader.rs` modified (+75/−2) and new `VERIFICATION.md` — not committed. Want me to commit these to the branch?

## The arm's diff

```diff
diff --git a/src/repo_loader.rs b/src/repo_loader.rs
index a4470ff..d93fba5 100644
--- a/src/repo_loader.rs
+++ b/src/repo_loader.rs
@@ -338,6 +338,20 @@ fn parse_rust_crate_config(
         if ws.is_some() {
             workspace_root_dirs.insert(manifest_dir.to_string());
         }
+        // Record CONCRETE declared `[workspace].members`, skipping glob patterns
+        // (`crates/*`) — a raw glob can't be expanded from the pattern alone and never
+        // prefix-matches a concrete root path, so glob members are recovered from the
+        // parsed `[package]` dirs below instead. Concrete members come straight from the
+        // root manifest, so a member whose OWN `Cargo.toml` is malformed/unparseable still
+        // survives here (it falls back to convention for its crate root) rather than being
+        // silently dropped along with its broken manifest.
+        if let Some(members) = ws.and_then(|w| w.get("members")).and_then(|m| m.as_array()) {
+            for member in members.iter().filter_map(|m| m.as_str()) {
+                if !member.contains('*') {
+                    workspace_members.insert(join_manifest_rel(manifest_dir, member));
+                }
+            }
+        }
         if let Some(ws_deps) = ws
             .and_then(|w| w.get("dependencies"))
             .and_then(|d| d.as_table())
@@ -1033,8 +1047,14 @@ mod tests {
         let inputs = repo.scope_graph_inputs.expect("scope graph inputs");
         // CONCRETE member dirs, never the glob pattern.
         assert!(
-            inputs.cfg.workspace_members.contains(&"crates/a".to_string())
-                && inputs.cfg.workspace_members.contains(&"crates/b".to_string()),
+            inputs
+                .cfg
+                .workspace_members
+                .contains(&"crates/a".to_string())
+                && inputs
+                    .cfg
+                    .workspace_members
+                    .contains(&"crates/b".to_string()),
             "glob members must expand to concrete dirs; got {:?}",
             inputs.cfg.workspace_members
         );
@@ -1056,6 +1076,59 @@ mod tests {
         );
     }
 
+    #[test]
+    fn mixed_concrete_and_glob_members_survive_a_malformed_concrete_manifest() {
+        // A workspace that MIXES a concrete member (`good`) with a glob (`crates/*`) and
+        // exercises BOTH branches of the declared-member recording in one manifest.
+        // `good`'s own Cargo.toml is MALFORMED, so it never parses into a `[package]` dir;
+        // it must still survive as a workspace member from the root's declared concrete
+        // member (the #124 regression). The `crates/*` glob must be dropped (never left as
+        // a raw pattern) and its concrete member `crates/x` recovered from the parsed
+        // `[package]` dir. `vendor/*` is deliberately NOT used: `vendor` is a walk-skip dir.
+        let dir = tempfile::tempdir().unwrap();
+        let p = dir.path();
+        std::fs::create_dir_all(p.join("good/src")).unwrap();
+        std::fs::create_dir_all(p.join("crates/x/src")).unwrap();
+        std::fs::write(
+            p.join("Cargo.toml"),
+            "[workspace]\nmembers = [\"good\", \"crates/*\"]\n",
+        )
+        .unwrap();
+        // Malformed concrete member manifest (unclosed `[package`).
+        std::fs::write(p.join("good/Cargo.toml"), "[package\nname = \"good\"\n").unwrap();
+        std::fs::write(p.join("good/src/lib.rs"), "pub fn good() {}\n").unwrap();
+        // Valid globbed member.
+        std::fs::write(
+            p.join("crates/x/Cargo.toml"),
+            "[package]\nname = \"x\"\nedition = \"2021\"\n",
+        )
+        .unwrap();
+        std::fs::write(p.join("crates/x/src/lib.rs"), "pub fn x() {}\n").unwrap();
+
+        let repo = load_repo(p).unwrap();
+        let members = &repo
+            .scope_graph_inputs
+            .as_ref()
+            .expect("scope graph inputs")
+            .cfg
+            .workspace_members;
+        // Concrete member survives despite its malformed manifest (declared-member branch).
+        assert!(
+            members.contains(&"good".to_string()),
+            "concrete member with a malformed manifest must survive; got {members:?}"
+        );
+        // Globbed member is expanded to its concrete dir (parsed `[package]` branch).
+        assert!(
+            members.contains(&"crates/x".to_string()),
+            "globbed member must expand to its concrete dir; got {members:?}"
+        );
+        // The raw glob pattern is dropped (glob-skip branch).
+        assert!(
+            !members.iter().any(|m| m.contains('*')),
+            "no raw glob pattern may remain; got {members:?}"
+        );
+    }
+
     #[test]
     fn workspace_dep_records_in_repo_member_dependency() {
         // `a` declares `b_crate = { workspace = true }`; the workspace root has

```
