# Blind pairwise code-review judgment — DBGW-DBG-03-sonnet

Two different engineers (Arm A, Arm B) independently completed the SAME
debugging task from the same starting commit. Judge only the work; process
environments may differ. Ignore any VERIFICATION.md in a diff.
a_materially_better/b_materially_better may not both be true; both false =
parity.

## Task brief (verbatim)

You are an expert Rust engineer working as the IMPLEMENTER on `prism` (a Rust tree-sitter code-slicing
tool). Your session cwd IS the prism repo. You are on a feature git branch — you EDIT the working tree,
run `cargo`, and COMMIT your work. The specific task is below the marker; do EXACTLY it, no more.

## Operating rules
- **Scope discipline:** implement only what the task specifies. Do NOT touch files outside the task's
  stated set. If the task says a change must be INERT / no-behavior-change, honor that exactly.
- **TDD:** when adding behavior, write the failing test FIRST and run it to watch it fail, then implement
  to green. When fixing a bug, add a regression test that fails before your fix.
- **Recall-safety (this subsystem's cardinal rule):** name resolution must **resolve-or-fall-through,
  NEVER emit a wrong target**. A bare/qualified name must never resolve to a wrong same-name item; when
  unsure, return a non-`Resolved` status (`Unresolved`/`Ambiguous`/`Poisoned`/`ResolvedSet`) and let the
  consumer fall through. Never trade this for precision.
- **Conventions:** `BTreeMap`/`BTreeSet` (never `HashMap`/`HashSet`) for determinism; keep each file
  under 600 lines (split by concern if needed, mirroring the existing module layout); match the
  surrounding code's style; derive `Serialize/Deserialize/Clone` on data types; `#[serde(default)]` on
  new fields of cached structs so old caches deserialize.
- **Authoritative sources:** the task cites spec sections (in `docs/superpowers/specs/…`) and file:line
  refs — READ them before coding; transcribe/follow them faithfully (do not invent or rename).

## Process
1. Read the cited spec sections + the existing code you'll touch (and any PR-1 types the task builds on).
2. If a requirement is genuinely ambiguous in a way that affects recall-safety or correctness, make the
   minimal SAFE choice and note it in your report — do not guess on anything expensive to redo.
3. Implement TDD. Then run, in order, and make all green:
   - `cargo test` (the specific `--test` target named in the task, then the full suite — zero regressions)
   - `cargo fmt` then `cargo fmt --check`
   - `cargo clippy --all-targets` (no new warnings in the files you touched)
   - `cargo build` (and `cargo build --features mcp` if the task touches anything build/cache-related)
4. Self-review: completeness vs the task; recall-safety (no path resolves to a wrong target); YAGNI (only
   what was asked); determinism; tests assert real behavior (not trivially-true), with wrong-target
   "decoy" assertions where the task involves fall-through.
5. COMMIT with the exact commit message the task specifies (including its `Co-Authored-By:` trailer).

## Report (plain text, after committing)
- **STATUS:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented; the test list + results (e.g. `cargo test --test name_resolution` count);
  files changed; the **commit SHA**; any file split.
- Self-review findings + any concerns or recall-safety decisions you made.
- If BLOCKED/NEEDS_CONTEXT: exactly what you're stuck on and what you tried. Never silently produce
  recall-safety logic you're unsure about — flag it.

THE TASK:

# Phase-2a PR-2 Task 2.2 — FIX (fold xhigh review [BLOCKER]: param BindingRef ordinal change)

You implemented Task 2.2 as commit `f89dd5c` (HEAD). An adversarial review found ONE real [BLOCKER] —
an INERTNESS BREACH. Fix it + add regressions, then **amend `f89dd5c`** keeping its message.

## The finding (inertness breach in bind_params)
To attach per-binding `local_facts`, `bind_params` now calls `add_locals` ONCE PER PARAMETER
(`src/name_resolution/rust_populator/walk/items.rs:~360` + `walk/locals.rs:~349`). But `add_locals` derives
`Target::Local(BindingRef.ordinal)` from the per-call slice INDEX. So `fn f(a: i32, b: i32)` now gives BOTH
params `ordinal = 0`; parent `48f15d9` gave `a=0, b=1`. That CHANGES the Phase-1 scope-graph `BindingRef`
data (serialized) — an observable populator-data change, violating PR-2's inertness contract. (The matrix
didn't move because no consumer derefs param ordinals today, but inertness means NO Phase-1 data change.)

## Fix
Restore a SINGLE ordered parameter-binding pass so ordinals are `0,1,2,…` exactly as before, while still
capturing per-binding facts:
- Collect all params first as `(name, def_byte, LocalFact)` in source order, then call `add_locals` ONCE with
  the full ordered name/def_byte slice (preserving the original enumerate-based ordinals), and populate
  `local_facts[(file, def_byte)]` for each from the collected vector (facts attach by def_byte, NOT by a
  per-name add_locals call).
- Do the same for any other binding site you split into per-name `add_locals` calls (lets/patterns) IF that
  split likewise changed ordinals — verify each `add_locals` call site still produces the same ordinals as
  parent `48f15d9`. The invariant: `Target::Local(BindingRef)` for every binding must be byte-for-byte
  identical to parent.

## Regression tests (committed; the shipped test missed this)
1. **ordinal preservation:** for `fn f(a: i32, b: i32)`, the two params resolve to distinct `BindingRef`s with
   ordinals `0` and `1` (not both `0`) — assert against the scope graph. (This pins the inertness fix.)
2. **ambiguity → None:** a manually-duplicated same-rib local (`let x; let x;` in one block) → lookup returns
   `None` (recall-safe).
(The shadow + ctor-fact cases are already covered.)

## Verify + amend
Add the ordinal-preservation regression FIRST (watch it fail on the current per-param code), then fix to
green. `cargo test --lib` (relevant) + `cargo test --test name_resolution` → full `cargo test` (zero
regressions; macOS `_dyld_start`/slow-cli transients — terminate+rerun / `--test-threads=1`) → `cargo fmt` →
`cargo clippy --all-targets` → `cargo build` → `cargo build --release && cd eval && uv run tier-a
--matrix-only --allow-stale-sut` (0 regressions). `git commit --amend --no-edit` onto `f89dd5c`; report new SHA.

## Acceptance
- Param/let/pattern `BindingRef` ordinals byte-identical to parent `48f15d9` (inertness restored);
  local_facts still populated; lookup unchanged. STATUS + new SHA + the ordinal regression result.
- Leave untracked eval/snapshot artifacts alone.


## Probe question (answer in `probe_answer`, per arm)

Does each arm remove the per-param ordinal collision at the root (single ordered binding pass) and add a regression test that fails on the buggy code? Is the fix inert beyond the repair?

## Arm A diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
index d86d7c65..4b546bf9 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -155,4 +155,28 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    #[test]
+    fn lookup_visible_binding_duplicate_same_rib_returns_none() {
+        // Two `let x` bindings in the SAME rib (no nested block between them) is
+        // a same-scope name collision — the recall-safe answer is None, never a
+        // guess at which `x` is meant.
+        let src = "fn f(){ let x = 1; let x = 2; let _z = x; }\n";
+        let mut files = std::collections::BTreeMap::new();
+        files.insert(
+            "a.rs".to_string(),
+            ParsedFile::parse("a.rs", src, Rust).unwrap(),
+        );
+        let mut inputs = ScopeGraphBuildInputs::from_files_convention(&files);
+        inputs.cfg = RustCrateConfig {
+            crate_roots: files.keys().cloned().collect(),
+            ..RustCrateConfig::default()
+        };
+        let cg = CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs));
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let use_byte = src.rfind("_z = x").unwrap();
+
+        assert!(lookup_visible_binding(graph, file, use_byte, "x").is_none());
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd7..dde654d8 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -357,7 +357,25 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+    let names: Vec<(String, usize)> = facts.iter().map(|(name, _)| name.clone()).collect();
+    // One ordered `add_locals` call over ALL params preserves ordinals
+    // `0,1,2,…` (a per-param call re-derives ordinal 0 from each
+    // single-element slice, colliding every param's `BindingRef`). Per-param
+    // facts differ (distinct annotations), so they're attached afterward by
+    // def_byte rather than through `add_locals`'s single shared `fact` arg.
+    add_locals(
+        b,
+        body_scope,
+        file,
+        body_end,
+        &names,
+        LocalFact {
+            kind: BindingKind::Param,
+            annotation: None,
+            init: None,
+        },
+    );
+    for ((_, def_byte), fact) in facts {
+        b.add_local_fact(file, def_byte, fact);
     }
 }
diff --git a/tests/name_resolution/rust_populate_test.rs b/tests/name_resolution/rust_populate_test.rs
index a3c26e9c..dac89919 100644
--- a/tests/name_resolution/rust_populate_test.rs
+++ b/tests/name_resolution/rust_populate_test.rs
@@ -21,7 +21,8 @@ use prism::name_resolution::rust_populator::{
     enclosing_scope, file_id, populate_rust, RustCrateConfig,
 };
 use prism::name_resolution::types::{
-    Anchor, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery, SourceLoc, Target,
+    Anchor, BindingRef, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery, SourceLoc,
+    Target,
 };
 
 // ── fixture + query helpers ───────────────────────────────────────────────────
@@ -343,6 +344,27 @@ fn test_local_param_shadows_free_fn() {
     assert_local(&res);
 }
 
+#[test]
+fn test_param_ordinals_preserve_source_order() {
+    // fn f(a: i32, b: i32) — `a` and `b` must resolve to DISTINCT BindingRef
+    // ordinals (0, 1) matching their source order, never both collapsing to 0.
+    let src = "fn f(a: i32, b: i32){ let _x = a; let _y = b; }\n";
+    let (res_a, _) = single_file_resolve(src, 2015, "_x = a", "a", NS_VALUE);
+    let (res_b, _) = single_file_resolve(src, 2015, "_y = b", "b", NS_VALUE);
+    assert_local(&res_a);
+    assert_local(&res_b);
+    let ordinal = |res: &Resolution| match &res.candidates[0].target {
+        Target::Local(BindingRef { ordinal, .. }) => *ordinal,
+        other => panic!("expected Local target, got {other:?}"),
+    };
+    assert_eq!(ordinal(&res_a), 0, "param `a` must keep ordinal 0");
+    assert_eq!(
+        ordinal(&res_b),
+        1,
+        "param `b` must keep ordinal 1, not collapse to 0"
+    );
+}
+
 #[test]
 fn test_local_closure_arg_shadows_free_fn() {
     let src = "pub fn f(){}\nfn host(){ let c = |f| { let _z = f; }; }\n";

```

## Arm B diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
index d86d7c6..51c79de 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -121,6 +121,7 @@ mod tests {
     use crate::call_graph::{CallGraph, ScopeGraphBuildInputs};
     use crate::languages::Language::Rust;
     use crate::name_resolution::rust_populator::RustCrateConfig;
+    use crate::name_resolution::types::BindingRef;
 
     #[test]
     fn lookup_visible_binding_returns_binding_by_name_and_byte() {
@@ -155,4 +156,63 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    /// Regression: `bind_params` must preserve enumerate-based `BindingRef`
+    /// ordinals (0, 1, 2, …) across all parameters. A prior per-parameter
+    /// `add_locals` call collapsed every ordinal to 0.
+    #[test]
+    fn param_bindings_get_distinct_ordinals() {
+        let src = "fn f(a: i32, b: i32) { a; b; }\n";
+        let mut files = std::collections::BTreeMap::new();
+        files.insert(
+            "a.rs".to_string(),
+            ParsedFile::parse("a.rs", src, Rust).unwrap(),
+        );
+        let mut inputs = ScopeGraphBuildInputs::from_files_convention(&files);
+        inputs.cfg = RustCrateConfig {
+            crate_roots: files.keys().cloned().collect(),
+            ..RustCrateConfig::default()
+        };
+        let cg = CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs));
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let at_byte = src.find("a;").unwrap();
+
+        let binding_a = lookup_visible_binding(graph, file, at_byte, "a").expect("binding a");
+        let binding_b = lookup_visible_binding(graph, file, at_byte, "b").expect("binding b");
+
+        let ordinal = |binding: &Binding| match &binding.target {
+            BindTarget::Resolved(Target::Local(BindingRef { ordinal, .. })) => *ordinal,
+            other => panic!("expected a Target::Local binding, got {other:?}"),
+        };
+        let (ordinal_a, ordinal_b) = (ordinal(binding_a), ordinal(binding_b));
+        assert_eq!(
+            (ordinal_a, ordinal_b),
+            (0, 1),
+            "param ordinals must be 0,1 in source order, got a={ordinal_a} b={ordinal_b}"
+        );
+    }
+
+    /// Recall-safety: two same-name bindings in the same rib (no nested scope
+    /// between them) must make lookup return `None`, not silently pick one.
+    #[test]
+    fn duplicate_same_rib_local_is_ambiguous() {
+        let src = "fn f() { let x = 1; let x = 2; x; }\n";
+        let mut files = std::collections::BTreeMap::new();
+        files.insert(
+            "a.rs".to_string(),
+            ParsedFile::parse("a.rs", src, Rust).unwrap(),
+        );
+        let mut inputs = ScopeGraphBuildInputs::from_files_convention(&files);
+        inputs.cfg = RustCrateConfig {
+            crate_roots: files.keys().cloned().collect(),
+            ..RustCrateConfig::default()
+        };
+        let cg = CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs));
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let use_byte = src.rfind("x;").unwrap();
+
+        assert_eq!(lookup_visible_binding(graph, file, use_byte, "x"), None);
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd..e994e3e 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -357,7 +357,23 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+    // One `add_locals` call over the full ordered slice keeps `BindingRef.ordinal`
+    // (0,1,2,…) identical across all params; splitting into per-name calls
+    // would reset the enumerate-based ordinal to 0 for every param.
+    let names: Vec<(String, usize)> = facts.iter().map(|(name, _)| name.clone()).collect();
+    add_locals(
+        b,
+        body_scope,
+        file,
+        body_end,
+        &names,
+        LocalFact {
+            kind: BindingKind::Param,
+            annotation: None,
+            init: None,
+        },
+    );
+    for ((_, def_byte), fact) in facts {
+        b.add_local_fact(file, def_byte, fact);
     }
 }

```
