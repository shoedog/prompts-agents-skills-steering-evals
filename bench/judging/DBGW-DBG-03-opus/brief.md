# Blind pairwise code-review judgment — DBGW-DBG-03-opus

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
index d86d7c6..d959cb0 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -155,4 +155,66 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    /// Build a single-file crate scope graph from `src` (file `a.rs`).
+    fn build_graph(src: &str) -> CallGraph {
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
+        CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs))
+    }
+
+    #[test]
+    fn param_bindings_have_distinct_ordinals() {
+        // Inertness pin (parent 48f15d9): `fn f(a, b)` must give the two params
+        // distinct `BindingRef` ordinals 0 and 1 — NOT both 0, which the per-param
+        // `add_locals` call would produce (each 1-element slice re-starts at 0).
+        let cg = build_graph("fn f(a: i32, b: i32) -> i32 { a + b }\n");
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+
+        let local_ref = |name: &str| {
+            graph.bindings.iter().find_map(|bd| match &bd.target {
+                BindTarget::Resolved(Target::Local(r)) if bd.name == name => Some(r.clone()),
+                _ => None,
+            })
+        };
+        let a = local_ref("a").expect("param `a` local binding");
+        let b = local_ref("b").expect("param `b` local binding");
+        assert_eq!(
+            a.scope, b.scope,
+            "both params bind in the same callable scope"
+        );
+        assert_eq!(a.ordinal, 0, "first param ordinal must be 0");
+        assert_eq!(
+            b.ordinal, 1,
+            "second param ordinal must be 1 (was 0: ordinal breach)"
+        );
+        assert_ne!(
+            a.ordinal, b.ordinal,
+            "params must resolve to distinct BindingRefs"
+        );
+    }
+
+    #[test]
+    fn duplicated_same_rib_local_lookup_is_none() {
+        // Two `let x` in ONE block are a same-rib ambiguity: the visible-binding
+        // lookup must return None (recall-safe), never guess one.
+        let src = "fn f() { let x = 1; let x = 2; let _z = x; }\n";
+        let cg = build_graph(src);
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let use_byte = src.rfind("x;").unwrap();
+
+        assert!(
+            lookup_visible_binding(graph, file, use_byte, "x").is_none(),
+            "duplicated same-rib local must be ambiguous → None"
+        );
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd..087daa2 100644
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
@@ -357,7 +357,13 @@ fn bind_params(
         }
         out
     });
+    // Attach each parameter's fact by its def-byte, then bind ALL params in ONE
+    // ordered pass so `BindingRef` ordinals stay 0,1,2,… (parent-48f15d9 parity).
+    // A per-param `add_locals` call would restart the ordinal at 0 each time.
+    let mut names = Vec::with_capacity(facts.len());
     for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+        b.add_local_fact(file, name.1, fact);
+        names.push(name);
     }
+    add_local_bindings(b, body_scope, file, body_end, &names);
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 2905c9d..b1ac112 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -346,8 +346,26 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     names: &[(String, usize)],
     fact: LocalFact,
 ) {
-    for (i, (name, def_byte)) in names.iter().enumerate() {
+    for (_name, def_byte) in names {
         b.add_local_fact(file, *def_byte, fact.clone());
+    }
+    add_local_bindings(b, scope, file, scope_end, names);
+}
+
+/// Add the `Target::Local` bindings (Value ns) only — one per `(name, def_byte)`
+/// with a scope-relative ordinal from the slice index. Split out from
+/// [`add_locals`] so callers with per-binding [`LocalFact`]s (parameters) can
+/// attach facts by def-byte yet still bind every name in ONE ordered pass, so
+/// `BindingRef` ordinals stay `0,1,2,…` (facts are keyed by def-byte, so adding
+/// them first leaves the binding order — and thus every ordinal — unchanged).
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

```

## Arm B diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
index d86d7c6..4fa5563 100644
--- a/src/name_resolution/binding_lookup.rs
+++ b/src/name_resolution/binding_lookup.rs
@@ -155,4 +155,67 @@ mod tests {
             Some(InitExpr::Ctor(s)) if s == "X::new()"
         ));
     }
+
+    fn build_graph(src: &str) -> CallGraph {
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
+        CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs))
+    }
+
+    #[test]
+    fn params_get_sequential_binding_ref_ordinals() {
+        // Inertness pin (Task-2.2 fix): the two params of `fn f(a, b)` must bind
+        // to DISTINCT `BindingRef` ordinals 0 and 1 — a single ordered
+        // `add_locals` pass. The per-param split regressed BOTH params to 0.
+        let cg = build_graph("fn f(a: i32, b: i32) {}\n");
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+
+        let ordinal_of = |name: &str| -> u32 {
+            graph
+                .bindings
+                .iter()
+                .find_map(|bd| match &bd.target {
+                    BindTarget::Resolved(Target::Local(r))
+                        if bd.name == name && bd.ns == NS_VALUE =>
+                    {
+                        Some(r.ordinal)
+                    }
+                    _ => None,
+                })
+                .unwrap_or_else(|| panic!("no local value binding named {name}"))
+        };
+
+        let ord_a = ordinal_of("a");
+        let ord_b = ordinal_of("b");
+        assert_eq!(ord_a, 0, "first param keeps ordinal 0");
+        assert_eq!(
+            ord_b, 1,
+            "second param must be ordinal 1, not 0 (inertness)"
+        );
+        assert_ne!(ord_a, ord_b, "param BindingRefs must be distinct");
+    }
+
+    #[test]
+    fn duplicate_same_rib_local_is_ambiguous_none() {
+        // Recall-safe: two same-name bindings in ONE rib, both visible at the
+        // use site, must return None (never pick a wrong same-name target).
+        let src = "fn f() { let x = 1; let x = 2; drop(x); }\n";
+        let cg = build_graph(src);
+        let graph = cg.scope_graph.as_ref().expect("scope graph");
+        let file = graph.file_paths["a.rs"];
+        let use_byte = src.rfind("x)").unwrap();
+
+        assert!(
+            lookup_visible_binding(graph, file, use_byte, "x").is_none(),
+            "ambiguous same-rib local must resolve to None"
+        );
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index f55a1dd..0d8a68b 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -330,7 +330,7 @@ fn bind_params(
     file: FileId,
     body_end: usize,
 ) {
-    let facts = with_node(b, path, params_nid, |pf, n| {
+    let collected = with_node(b, path, params_nid, |pf, n| {
         let mut out = Vec::new();
         let mut cursor = n.walk();
         for c in n.children(&mut cursor) {
@@ -357,7 +357,12 @@ fn bind_params(
         }
         out
     });
-    for (name, fact) in facts {
-        add_locals(b, body_scope, file, body_end, &[name], fact);
+    // Attach each param's fact by def_byte — params carry distinct annotations, so
+    // they cannot share one fact. Then bind all params in a SINGLE ordered pass so
+    // the `BindingRef` ordinals stay 0,1,2,… (the per-param split collapsed them).
+    for ((_, def_byte), fact) in &collected {
+        b.add_local_fact(file, *def_byte, fact.clone());
     }
+    let names: Vec<(String, usize)> = collected.into_iter().map(|(name, _)| name).collect();
+    add_locals(b, body_scope, file, body_end, &names, None);
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 2905c9d..3e2fd79 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -87,11 +87,11 @@ fn walk_let(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
         ctx.file,
         scope_end,
         &names,
-        LocalFact {
+        Some(LocalFact {
             kind,
             annotation,
             init,
-        },
+        }),
     );
     // The initializer expression may contain closures / blocks / macros.
     if let Some(value_nid) = value_nid {
@@ -182,11 +182,11 @@ fn walk_closure(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, c
         ctx.file,
         hi,
         &names,
-        LocalFact {
+        Some(LocalFact {
             kind: BindingKind::Param,
             annotation: None,
             init: None,
-        },
+        }),
     );
     if let Some(body_nid) = body_nid {
         walk_expr(b, path, &body_nid, body_scope, ctx);
@@ -215,11 +215,11 @@ fn walk_for(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
         ctx.file,
         hi,
         &names,
-        LocalFact {
+        Some(LocalFact {
             kind: BindingKind::Pattern,
             annotation: None,
             init: None,
-        },
+        }),
     );
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx); // iterator expr is in outer scope
@@ -267,11 +267,11 @@ fn walk_match(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx
             ctx.file,
             hi,
             &names,
-            LocalFact {
+            Some(LocalFact {
                 kind: BindingKind::Pattern,
                 annotation: None,
                 init: None,
-            },
+            }),
         );
         if let Some(arm_value) = arm_value {
             walk_expr(b, path, &arm_value, arm_scope, ctx);
@@ -307,11 +307,11 @@ fn walk_if_while(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId,
         ctx.file,
         hi,
         &names,
-        LocalFact {
+        Some(LocalFact {
             kind: BindingKind::Pattern,
             annotation: None,
             init: None,
-        },
+        }),
     );
     for blk in blocks {
         walk_block_body(b, path, &blk, cond_scope, ctx);
@@ -338,16 +338,23 @@ fn collect_match_pattern(pf: &ParsedFile, node: &Node, out: &mut Vec<(String, us
 ///
 /// A local's accessibility is its lexical extent, not a Rust `pub`; `VIS_PUB`
 /// makes the policy's `visible()` return true (the gate is the `vis_extents`).
+///
+/// When `fact` is `Some`, the same fact is attached (keyed by def_byte) to every
+/// binding in `names`; call sites whose bindings carry per-name facts pass `None`
+/// and attach them themselves so a single ordered pass still assigns the
+/// insertion-order ordinals.
 pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     b: &mut Builder<'_>,
     scope: ScopeId,
     file: FileId,
     scope_end: usize,
     names: &[(String, usize)],
-    fact: LocalFact,
+    fact: Option<LocalFact>,
 ) {
     for (i, (name, def_byte)) in names.iter().enumerate() {
-        b.add_local_fact(file, *def_byte, fact.clone());
+        if let Some(fact) = &fact {
+            b.add_local_fact(file, *def_byte, fact.clone());
+        }
         b.add_binding(
             scope,
             name.clone(),

```
