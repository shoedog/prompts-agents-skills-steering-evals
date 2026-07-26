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

I'll stop polling and wait for the monitor to deliver the totals. Pausing here until `br41iv2sr` fires.

## The arm's diff

```diff
diff --git a/src/repo_loader.rs b/src/repo_loader.rs
index a4470ff..47c4f55 100644
--- a/src/repo_loader.rs
+++ b/src/repo_loader.rs
@@ -403,11 +403,37 @@ fn parse_rust_crate_config(
         // (`members = ["crates/*"]`), where a raw `crates/*` pattern never prefix-matches
         // a concrete root path (`crates/ruff_db/src/lib.rs`). prism has already walked
         // every member's `Cargo.toml` into `manifest_hashes`, so their dirs ARE the
-        // expanded member set; the declared patterns are redundant for this purpose.
+        // expanded member set; the declared GLOB patterns are redundant for this
+        // purpose (declared CONCRETE members are still read below, as a fallback for a
+        // member whose own manifest fails to parse).
         if value.get("package").is_some() && !manifest_dir.is_empty() {
             workspace_members.insert(manifest_dir.to_string());
         }
 
+        // A workspace root's DECLARED CONCRETE members are member dirs even when the
+        // member's own `Cargo.toml` is malformed — an unparseable manifest is skipped
+        // above (the `continue` on the TOML parse), so it never reaches the
+        // per-`[package]` recording. Insert the root's non-glob member entries so a
+        // broken sibling manifest never drops the member from `workspace_members`
+        // (`malformed_member_manifest_does_not_discard_valid_sibling_manifest`). GLOB
+        // patterns (`crates/*`) are NOT inserted raw — they carry a glob metacharacter
+        // and are recovered as concrete dirs from each member's parsed `[package]`.
+        if let Some(members) = value
+            .get("workspace")
+            .and_then(|w| w.get("members"))
+            .and_then(|m| m.as_array())
+        {
+            for member in members.iter().filter_map(|m| m.as_str()) {
+                if member.contains(|c| c == '*' || c == '?' || c == '[') {
+                    continue;
+                }
+                let dir = join_manifest_rel(manifest_dir, member);
+                if !dir.is_empty() {
+                    workspace_members.insert(dir);
+                }
+            }
+        }
+
         if let Some(path) = value
             .get("lib")
             .and_then(|l| l.get("path"))
@@ -1033,8 +1059,14 @@ mod tests {
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
@@ -1056,6 +1088,57 @@ mod tests {
         );
     }
 
+    #[test]
+    fn mixed_glob_and_concrete_members_survive_a_malformed_concrete_manifest() {
+        // A MIXED members list (`["crates/*", "xtask"]`, a real Cargo pattern) where the
+        // concretely-listed `xtask` has a MALFORMED `Cargo.toml`. This exercises both
+        // branches of workspace-member recording at once:
+        //   - `crates/a` is recovered from its parsed `[package]` (the glob expansion),
+        //   - `xtask` is dropped by the per-`[package]` pass (its manifest fails to parse)
+        //     but recovered from the root's DECLARED CONCRETE member entry, and
+        //   - the raw `crates/*` glob pattern is never inserted.
+        // Pre-fix (per-`[package]` only) drops `xtask`; without the glob guard the raw
+        // `crates/*` leaks in — so this pins the union of the two sources.
+        let dir = tempfile::tempdir().unwrap();
+        let p = dir.path();
+        std::fs::create_dir_all(p.join("crates/a/src")).unwrap();
+        std::fs::create_dir_all(p.join("xtask/src")).unwrap();
+        std::fs::write(
+            p.join("Cargo.toml"),
+            "[workspace]\nmembers = [\"crates/*\", \"xtask\"]\n[workspace.package]\nedition = \"2021\"\n",
+        )
+        .unwrap();
+        std::fs::write(
+            p.join("crates/a/Cargo.toml"),
+            "[package]\nname = \"a\"\nedition = \"2021\"\n",
+        )
+        .unwrap();
+        // Malformed manifest for the concretely-listed member (missing `]` on `[package`).
+        std::fs::write(p.join("xtask/Cargo.toml"), "[package\nname = \"xtask\"\n").unwrap();
+        std::fs::write(p.join("crates/a/src/lib.rs"), "pub fn a() {}\n").unwrap();
+        std::fs::write(p.join("xtask/src/lib.rs"), "pub fn x() {}\n").unwrap();
+        let repo = load_repo(p).unwrap();
+        let inputs = repo.scope_graph_inputs.expect("scope graph inputs");
+        assert!(
+            inputs
+                .cfg
+                .workspace_members
+                .contains(&"crates/a".to_string()),
+            "glob member `crates/a` must expand from its parsed [package]; got {:?}",
+            inputs.cfg.workspace_members
+        );
+        assert!(
+            inputs.cfg.workspace_members.contains(&"xtask".to_string()),
+            "a malformed concrete member must survive via the root's declared members; got {:?}",
+            inputs.cfg.workspace_members
+        );
+        assert!(
+            !inputs.cfg.workspace_members.iter().any(|m| m.contains('*')),
+            "no raw glob pattern may remain in workspace_members; got {:?}",
+            inputs.cfg.workspace_members
+        );
+    }
+
     #[test]
     fn workspace_dep_records_in_repo_member_dependency() {
         // `a` declares `b_crate = { workspace = true }`; the workspace root has

```
