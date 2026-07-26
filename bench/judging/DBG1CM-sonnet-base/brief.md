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

## Summary

Completed the verification gate:

1. **Full test suite**: `cargo test` → 2415 passed, 0 failed, 1 ignored (27 binaries + doctests); `cargo test --features mcp` → 2476 passed, 0 failed, 1 ignored. `cargo fmt --check` is clean.
2. **Test coverage for the fix**: the pre-existing `malformed_member_manifest_does_not_discard_valid_sibling_manifest` test already fails on pre-change code (verified against commit `04c6b0b`) and passes now. I added a new negative/edge-case test, `malformed_root_manifest_does_not_register_empty_member_dir`, covering the other branch of the new guard (malformed **root** manifest must not insert `""` into `workspace_members`) — confirmed it fails without the guard and passes with it.
3. Wrote `VERIFICATION.md` at the repo root with exact commands, totals, and `## Verified` / `## Not verified` sections.

Nothing outside the task's scope failed — the only test failure found was the one this task was about fixing.

## The arm's diff

```diff
diff --git a/src/repo_loader.rs b/src/repo_loader.rs
index a4470ff..25f0d4d 100644
--- a/src/repo_loader.rs
+++ b/src/repo_loader.rs
@@ -361,17 +361,24 @@ fn parse_rust_crate_config(
 
     for manifest_path in manifest_hashes.keys() {
         let abs = root.join(manifest_path);
+        let manifest_dir = manifest_path
+            .strip_suffix("Cargo.toml")
+            .unwrap_or("")
+            .trim_end_matches('/');
         let Ok(text) = std::fs::read_to_string(&abs) else {
             continue;
         };
         let Ok(value) = text.parse::<toml::Value>() else {
+            // Malformed manifest: still a concrete member dir (the workspace root
+            // declared it), so it must survive in `workspace_members` even though we
+            // can't extract its edition/lib/bin/deps here. `crate_roots` falls back
+            // to convention for it via `RustCrateConfig::from_convention` above.
+            if !manifest_dir.is_empty() {
+                workspace_members.insert(manifest_dir.to_string());
+            }
             continue;
         };
         parsed_any = true;
-        let manifest_dir = manifest_path
-            .strip_suffix("Cargo.toml")
-            .unwrap_or("")
-            .trim_end_matches('/');
 
         if value.get("package").is_some() {
             // Cargo default: a `[package]` with no `edition` key is edition 2015.
@@ -1033,8 +1040,14 @@ mod tests {
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
@@ -1056,6 +1069,36 @@ mod tests {
         );
     }
 
+    #[test]
+    fn malformed_root_manifest_does_not_register_empty_member_dir() {
+        // The ROOT Cargo.toml itself (not a member) is malformed TOML. Its
+        // `manifest_dir` is "" (the repo root), which must never be inserted into
+        // `workspace_members` -- only concrete, non-root member dirs belong there.
+        // The valid sibling member must still register normally.
+        let dir = tempfile::tempdir().unwrap();
+        let p = dir.path();
+        std::fs::create_dir_all(p.join("m/src")).unwrap();
+        std::fs::write(p.join("Cargo.toml"), "[workspace\nmembers = [\"m\"]\n").unwrap();
+        std::fs::write(
+            p.join("m/Cargo.toml"),
+            "[package]\nname = \"m\"\nedition = \"2021\"\n",
+        )
+        .unwrap();
+        std::fs::write(p.join("m/src/lib.rs"), "pub fn m() {}\n").unwrap();
+        let repo = load_repo(p).unwrap();
+        let inputs = repo.scope_graph_inputs.expect("scope graph inputs");
+        assert!(
+            !inputs.cfg.workspace_members.iter().any(|m| m.is_empty()),
+            "a malformed root manifest must not register an empty member dir; got {:?}",
+            inputs.cfg.workspace_members
+        );
+        assert_eq!(
+            inputs.cfg.workspace_members,
+            vec!["m".to_string()],
+            "valid member must still register when the root manifest is malformed"
+        );
+    }
+
     #[test]
     fn workspace_dep_records_in_repo_member_dependency() {
         // `a` declares `b_crate = { workspace = true }`; the workspace root has

```
