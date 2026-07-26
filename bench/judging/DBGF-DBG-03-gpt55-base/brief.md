# Blind pairwise code-review judgment — DBGF-DBG-03-gpt55-base

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
index d86d7c65..429067f6 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -155,4 +155,29 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    #[test]
+    fn lookup_visible_binding_returns_none_for_duplicate_same_rib_local() {
+        let src = "struct X;\nimpl X { fn new() -> Self { X } fn m(&self) {} }\nfn f(){ let x = X::new(); let x = X::new(); x.m(); }\n";
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
+        let call_byte = src.rfind("x.m()").unwrap();
+
+        assert_eq!(
+            lookup_visible_binding(graph, file, call_byte, "x"),
+            None,
+            "same-rib duplicate locals must fall through instead of choosing one"
+        );
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd7..ceddc6b1 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -342,9 +342,10 @@ fn bind_params(
                 if let Some(p) = c.child_by_field_name("pattern") {
                     let mut names = Vec::new();
                     pattern_idents(pf, &p, &mut names);
-                    for name in names {
+                    for (name, def_byte) in names {
                         out.push((
                             name,
+                            def_byte,
                             LocalFact {
                                 kind: BindingKind::Param,
                                 annotation: annotation.clone(),
@@ -357,7 +358,26 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+    if facts.is_empty() {
+        return;
+    }
+    let names: Vec<(String, usize)> = facts
+        .iter()
+        .map(|(name, def_byte, _)| (name.clone(), *def_byte))
+        .collect();
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
+    for (_, def_byte, fact) in facts {
+        b.add_local_fact(file, def_byte, fact);
     }
 }
diff --git a/tests/name_resolution/rust_populate_test.rs b/tests/name_resolution/rust_populate_test.rs
index a3c26e9c..69c7e4de 100644
--- a/tests/name_resolution/rust_populate_test.rs
+++ b/tests/name_resolution/rust_populate_test.rs
@@ -21,7 +21,8 @@ use prism::name_resolution::rust_populator::{
     enclosing_scope, file_id, populate_rust, RustCrateConfig,
 };
 use prism::name_resolution::types::{
-    Anchor, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery, SourceLoc, Target,
+    Anchor, BindTarget, BindingRef, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery,
+    SourceLoc, Target,
 };
 
 // ── fixture + query helpers ───────────────────────────────────────────────────
@@ -154,6 +155,24 @@ fn assert_local(res: &Resolution) {
     );
 }
 
+fn local_ref_at_def(g: &ScopeGraph, name: &str, def_byte: usize) -> BindingRef {
+    let binding = g
+        .bindings
+        .iter()
+        .find(|binding| {
+            binding.name == name
+                && binding
+                    .vis_extents
+                    .iter()
+                    .any(|span| span.lo.byte == def_byte)
+        })
+        .unwrap_or_else(|| panic!("missing local binding {name:?} at byte {def_byte}"));
+    match &binding.target {
+        BindTarget::Resolved(Target::Local(local_ref)) => local_ref.clone(),
+        other => panic!("expected local binding target for {name:?}, got {other:?}"),
+    }
+}
+
 /// Convention-fallback config (no manifest): edition 2015, conventional roots.
 fn convention(fs: &BTreeMap<String, ParsedFile>) -> RustCrateConfig {
     RustCrateConfig::from_convention(fs)
@@ -343,6 +362,20 @@ fn test_local_param_shadows_free_fn() {
     assert_local(&res);
 }
 
+#[test]
+fn test_param_binding_refs_preserve_source_order_ordinals() {
+    let src = "fn f(a: i32, b: i32) { let _ = (a, b); }\n";
+    let fs = files(&[("src/lib.rs", src)]);
+    let g = populate_rust(&fs, &convention(&fs), None);
+    let a = local_ref_at_def(&g, "a", byte_of(src, "a: i32"));
+    let b = local_ref_at_def(&g, "b", byte_of(src, "b: i32"));
+
+    assert_eq!(a.scope, b.scope, "params must bind in the same body scope");
+    assert_eq!(a.ordinal, 0, "first param ordinal changed");
+    assert_eq!(b.ordinal, 1, "second param ordinal changed");
+    assert_ne!(a, b, "distinct params must not share one BindingRef");
+}
+
 #[test]
 fn test_local_closure_arg_shadows_free_fn() {
     let src = "pub fn f(){}\nfn host(){ let c = |f| { let _z = f; }; }\n";

```

## Arm B diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
index d86d7c6..9ba9986 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -122,9 +122,7 @@ mod tests {
     use crate::languages::Language::Rust;
     use crate::name_resolution::rust_populator::RustCrateConfig;
 
-    #[test]
-    fn lookup_visible_binding_returns_binding_by_name_and_byte() {
-        let src = "struct X;\nimpl X { fn new() -> Self { X } fn m(&self) {} }\nfn f(){ let b = X::new(); { let b = X::new(); b.m(); } }\n";
+    fn build(src: &str) -> CallGraph {
         let mut files = std::collections::BTreeMap::new();
         files.insert(
             "a.rs".to_string(),
@@ -135,7 +133,13 @@ mod tests {
             crate_roots: files.keys().cloned().collect(),
             ..RustCrateConfig::default()
         };
-        let cg = CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs));
+        CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs))
+    }
+
+    #[test]
+    fn lookup_visible_binding_returns_binding_by_name_and_byte() {
+        let src = "struct X;\nimpl X { fn new() -> Self { X } fn m(&self) {} }\nfn f(){ let b = X::new(); { let b = X::new(); b.m(); } }\n";
+        let cg = build(src);
         let graph = cg.scope_graph.as_ref().expect("scope graph");
         let file = graph.file_paths["a.rs"];
         let outer_let_b_def_byte = src.find("b = X::new").unwrap();
@@ -155,4 +159,29 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    #[test]
+    fn lookup_same_rib_duplicate_names_returns_none() {
+        // Recall-safety: two same-name locals in ONE rib (not a nested-block
+        // shadow) are ambiguous at a byte both extents cover — the lookup must
+        // return None and let the consumer fall through, never pick either.
+        let src = "fn f(){ let x = 1; let x = 2; let _z = x; }\n";
+        let cg = build(src);
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let first_x_def_byte = src.find("x = 1").unwrap();
+
+        // Between the two lets only the first `x` is visible — the lookup
+        // machinery itself works on this fixture (the None below is not vacuous).
+        let between_byte = src.find("let x = 2").unwrap();
+        let visible = lookup_visible_binding(graph, file, between_byte, "x").expect("binding");
+        assert_eq!(
+            visible.vis_extents.first().unwrap().lo.byte,
+            first_x_def_byte
+        );
+
+        // After the second let, both extents cover the use byte → ambiguous.
+        let use_byte = src.find("_z = x").unwrap();
+        assert!(lookup_visible_binding(graph, file, use_byte, "x").is_none());
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd..29dd6d1 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -14,7 +14,7 @@ use super::super::scopes::{
     child_of_kind, name_text, parse_cfg_for_item, parse_use, parse_vis, pattern_idents, vis,
     UseItem,
 };
-use super::locals::{add_locals, walk_block_body};
+use super::locals::{add_local_bindings, walk_block_body};
 use super::{
     full_file_span, full_scope_span, node_range, resolve_restrict, vis_extent_from, with_node, Ctx,
     NodeId,
@@ -330,7 +330,7 @@ fn bind_params(
     file: FileId,
     body_end: usize,
 ) {
-    let facts = with_node(b, path, params_nid, |pf, n| {
+    let params = with_node(b, path, params_nid, |pf, n| {
         let mut out = Vec::new();
         let mut cursor = n.walk();
         for c in n.children(&mut cursor) {
@@ -357,7 +357,12 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+    // One ordered binding pass over ALL params — `BindingRef.ordinal` is
+    // positional, so a per-param call would restart every ordinal at 0.
+    // Per-param facts (annotations differ) attach by def byte instead.
+    let names: Vec<(String, usize)> = params.iter().map(|(name, _)| name.clone()).collect();
+    add_local_bindings(b, body_scope, file, body_end, &names);
+    for ((_, def_byte), fact) in params {
+        b.add_local_fact(file, def_byte, fact);
     }
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 2905c9d..720a330 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -334,7 +334,8 @@ fn collect_match_pattern(pf: &ParsedFile, node: &Node, out: &mut Vec<(String, us
 }
 
 /// Add a `Target::Local` binding (Value ns) for each `(name, def_byte)`, visible
-/// from its def byte to `scope_end`.
+/// from its def byte to `scope_end`, and record the same `LocalFact` for each
+/// binding under `(file, def_byte)`.
 ///
 /// A local's accessibility is its lexical extent, not a Rust `pub`; `VIS_PUB`
 /// makes the policy's `visible()` return true (the gate is the `vis_extents`).
@@ -346,8 +347,24 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     names: &[(String, usize)],
     fact: LocalFact,
 ) {
-    for (i, (name, def_byte)) in names.iter().enumerate() {
+    for (_, def_byte) in names {
         b.add_local_fact(file, *def_byte, fact.clone());
+    }
+    add_local_bindings(b, scope, file, scope_end, names);
+}
+
+/// The binding pass of [`add_locals`]: `BindingRef.ordinal` is the position
+/// within `names`, so ALL of a site's bindings must arrive in ONE ordered slice
+/// (a per-name call would restart every ordinal at 0). Callers with per-binding
+/// facts attach them by def byte via `Builder::add_local_fact` instead.
+pub(in crate::name_resolution::rust_populator::walk) fn add_local_bindings(
+    b: &mut Builder<'_>,
+    scope: ScopeId,
+    file: FileId,
+    scope_end: usize,
+    names: &[(String, usize)],
+) {
+    for (i, (name, def_byte)) in names.iter().enumerate() {
         b.add_binding(
             scope,
             name.clone(),
diff --git a/tests/name_resolution/rust_populate_test.rs b/tests/name_resolution/rust_populate_test.rs
index a3c26e9..bd123c1 100644
--- a/tests/name_resolution/rust_populate_test.rs
+++ b/tests/name_resolution/rust_populate_test.rs
@@ -21,7 +21,8 @@ use prism::name_resolution::rust_populator::{
     enclosing_scope, file_id, populate_rust, RustCrateConfig,
 };
 use prism::name_resolution::types::{
-    Anchor, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery, SourceLoc, Target,
+    Anchor, BindTarget, BindingRef, NamespaceId, RawPath, ResStatus, Resolution, ResolveQuery,
+    SourceLoc, Target,
 };
 
 // ── fixture + query helpers ───────────────────────────────────────────────────
@@ -410,6 +411,40 @@ fn test_local_closure_tuple_non_first_ident() {
     assert_local(&res);
 }
 
+// ── param `BindingRef` ordinals (Phase-1 inertness pin) ───────────────────────
+
+/// The single `Target::Local(BindingRef)` for the value binding `name`.
+fn local_binding_ref(g: &ScopeGraph, name: &str) -> BindingRef {
+    let refs: Vec<BindingRef> = g
+        .bindings
+        .iter()
+        .filter(|bind| bind.name == name && bind.ns == NS_VALUE)
+        .filter_map(|bind| match &bind.target {
+            BindTarget::Resolved(Target::Local(r)) => Some(r.clone()),
+            _ => None,
+        })
+        .collect();
+    assert_eq!(refs.len(), 1, "expected one local binding for {name:?}");
+    refs.into_iter().next().unwrap()
+}
+
+#[test]
+fn test_param_binding_ordinals_are_positional() {
+    // Regression: per-param `add_locals` calls restarted the enumerate-based
+    // ordinal at 0 for every parameter, collapsing `fn f(a, b)` onto one
+    // `BindingRef` — the serialized scope-graph data must stay positional.
+    let src = "fn f(a: i32, b: i32) { let _z = a; }\n";
+    let fs = files(&[("src/lib.rs", src)]);
+    let g = populate_rust(&fs, &convention(&fs), None);
+
+    let a = local_binding_ref(&g, "a");
+    let b = local_binding_ref(&g, "b");
+    assert_eq!(a.scope, b.scope, "params share the fn-body scope");
+    assert_eq!(a.ordinal, 0, "param `a` keeps positional ordinal 0");
+    assert_eq!(b.ordinal, 1, "param `b` keeps positional ordinal 1");
+    assert_ne!(a, b, "distinct params must have distinct BindingRefs");
+}
+
 // ═══════════════════════════════════════════════════════════════════════════
 // BLOCK-LOCAL `use` extent
 // ═══════════════════════════════════════════════════════════════════════════

```
