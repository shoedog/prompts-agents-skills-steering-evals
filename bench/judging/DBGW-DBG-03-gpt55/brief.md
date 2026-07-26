# Blind pairwise code-review judgment — DBGW-DBG-03-gpt55

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
index d86d7c65..119f62f9 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -155,4 +155,30 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    #[test]
+    fn lookup_visible_binding_duplicate_same_rib_returns_none() {
+        let src = "fn f(){ let x; let x; x.m(); }\n";
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
+        let binding = lookup_visible_binding(graph, file, call_byte, "x");
+
+        assert!(
+            binding.is_none(),
+            "duplicate same-rib locals must be ambiguous to the build-time lookup"
+        );
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd7..972c66c6 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -330,7 +330,7 @@ fn bind_params(
     file: FileId,
     body_end: usize,
 ) {
-    let facts = with_node(b, path, params_nid, |pf, n| {
+    let locals = with_node(b, path, params_nid, |pf, n| {
         let mut out = Vec::new();
         let mut cursor = n.walk();
         for c in n.children(&mut cursor) {
@@ -344,7 +344,8 @@ fn bind_params(
                     pattern_idents(pf, &p, &mut names);
                     for name in names {
                         out.push((
-                            name,
+                            name.0,
+                            name.1,
                             LocalFact {
                                 kind: BindingKind::Param,
                                 annotation: annotation.clone(),
@@ -357,7 +358,5 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
-    }
+    add_locals(b, body_scope, file, body_end, &locals);
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 2905c9d5..9674dd50 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -86,12 +86,14 @@ fn walk_let(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
         scope,
         ctx.file,
         scope_end,
-        &names,
-        LocalFact {
-            kind,
-            annotation,
-            init,
-        },
+        &locals_with_fact(
+            &names,
+            LocalFact {
+                kind,
+                annotation,
+                init,
+            },
+        ),
     );
     // The initializer expression may contain closures / blocks / macros.
     if let Some(value_nid) = value_nid {
@@ -181,12 +183,14 @@ fn walk_closure(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, c
         body_scope,
         ctx.file,
         hi,
-        &names,
-        LocalFact {
-            kind: BindingKind::Param,
-            annotation: None,
-            init: None,
-        },
+        &locals_with_fact(
+            &names,
+            LocalFact {
+                kind: BindingKind::Param,
+                annotation: None,
+                init: None,
+            },
+        ),
     );
     if let Some(body_nid) = body_nid {
         walk_expr(b, path, &body_nid, body_scope, ctx);
@@ -214,12 +218,14 @@ fn walk_for(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
         loop_scope,
         ctx.file,
         hi,
-        &names,
-        LocalFact {
-            kind: BindingKind::Pattern,
-            annotation: None,
-            init: None,
-        },
+        &locals_with_fact(
+            &names,
+            LocalFact {
+                kind: BindingKind::Pattern,
+                annotation: None,
+                init: None,
+            },
+        ),
     );
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx); // iterator expr is in outer scope
@@ -266,12 +272,14 @@ fn walk_match(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx
             arm_scope,
             ctx.file,
             hi,
-            &names,
-            LocalFact {
-                kind: BindingKind::Pattern,
-                annotation: None,
-                init: None,
-            },
+            &locals_with_fact(
+                &names,
+                LocalFact {
+                    kind: BindingKind::Pattern,
+                    annotation: None,
+                    init: None,
+                },
+            ),
         );
         if let Some(arm_value) = arm_value {
             walk_expr(b, path, &arm_value, arm_scope, ctx);
@@ -306,12 +314,14 @@ fn walk_if_while(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId,
         cond_scope,
         ctx.file,
         hi,
-        &names,
-        LocalFact {
-            kind: BindingKind::Pattern,
-            annotation: None,
-            init: None,
-        },
+        &locals_with_fact(
+            &names,
+            LocalFact {
+                kind: BindingKind::Pattern,
+                annotation: None,
+                init: None,
+            },
+        ),
     );
     for blk in blocks {
         walk_block_body(b, path, &blk, cond_scope, ctx);
@@ -343,10 +353,9 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     scope: ScopeId,
     file: FileId,
     scope_end: usize,
-    names: &[(String, usize)],
-    fact: LocalFact,
+    locals: &[(String, usize, LocalFact)],
 ) {
-    for (i, (name, def_byte)) in names.iter().enumerate() {
+    for (i, (name, def_byte, fact)) in locals.iter().enumerate() {
         b.add_local_fact(file, *def_byte, fact.clone());
         b.add_binding(
             scope,
@@ -372,6 +381,13 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     }
 }
 
+fn locals_with_fact(names: &[(String, usize)], fact: LocalFact) -> Vec<(String, usize, LocalFact)> {
+    names
+        .iter()
+        .map(|(name, def_byte)| (name.clone(), *def_byte, fact.clone()))
+        .collect()
+}
+
 fn init_expr(pf: &ParsedFile, value: &Node) -> Option<InitExpr> {
     match value.kind() {
         "call_expression" => {
diff --git a/tests/name_resolution/rust_populate_test.rs b/tests/name_resolution/rust_populate_test.rs
index a3c26e9c..f6403e48 100644
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
@@ -154,6 +155,21 @@ fn assert_local(res: &Resolution) {
     );
 }
 
+fn resolved_local_ref(res: &Resolution) -> BindingRef {
+    assert_eq!(
+        res.status,
+        ResStatus::Resolved,
+        "expected Resolved(Local), got {:?} ({:?})",
+        res.status,
+        res.candidates
+    );
+    assert_eq!(res.candidates.len(), 1, "expected one candidate");
+    match &res.candidates[0].target {
+        Target::Local(binding_ref) => binding_ref.clone(),
+        other => panic!("expected Local target, got {other:?}"),
+    }
+}
+
 /// Convention-fallback config (no manifest): edition 2015, conventional roots.
 fn convention(fs: &BTreeMap<String, ParsedFile>) -> RustCrateConfig {
     RustCrateConfig::from_convention(fs)
@@ -343,6 +359,38 @@ fn test_local_param_shadows_free_fn() {
     assert_local(&res);
 }
 
+#[test]
+fn test_local_param_ordinals_preserve_source_order() {
+    let src = "fn host(a: i32, b: i32){ let _z = (a, b); }\n";
+    let fs = files(&[("src/lib.rs", src)]);
+    let g = populate_rust(&fs, &convention(&fs), None);
+
+    let a = resolve_bare_at(
+        &g,
+        &fs,
+        2015,
+        "src/lib.rs",
+        byte_of(src, "(a, b"),
+        "a",
+        NS_VALUE,
+    );
+    let b = resolve_bare_at(
+        &g,
+        &fs,
+        2015,
+        "src/lib.rs",
+        byte_of(src, "(a, b"),
+        "b",
+        NS_VALUE,
+    );
+
+    let a_ref = resolved_local_ref(&a);
+    let b_ref = resolved_local_ref(&b);
+    assert_eq!(a_ref.scope, b_ref.scope, "params share the callable rib");
+    assert_eq!(a_ref.ordinal, 0, "first param keeps parent ordinal");
+    assert_eq!(b_ref.ordinal, 1, "second param must not restart at zero");
+}
+
 #[test]
 fn test_local_closure_arg_shadows_free_fn() {
     let src = "pub fn f(){}\nfn host(){ let c = |f| { let _z = f; }; }\n";

```
