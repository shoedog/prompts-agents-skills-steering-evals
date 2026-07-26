# Blind pairwise code-review judgment — DBGW-DBG-02-opus

Two different engineers (Arm A, Arm B) independently completed the SAME
debugging task from the same starting commit. Judge only the work; process
environments may differ. Ignore any VERIFICATION.md in a diff.
a_materially_better/b_materially_better may not both be true; both false =
parity.

## Task brief (verbatim)

# Fix: prism slice 2 — diff-review BLOCKERs (materialized-receiver suppresses R3/R3b) + scope-aware recovery

Senior Rust engineer. Session cwd = `/tmp/prism-slice2` (branch `slice2-typed-receivers`). workspace-write.
The slice is implemented + committed (`075d686`/`f6ce3df`/`b0055d1`); the final diff-review found 2 BLOCKERs
+ 1 MAJOR. Fix via strict TDD (failing test first). Read the spec/plan for context.

## BLOCKER 1+2 (unified): a MATERIALIZED receiver binding must suppress R3/R3b even when the type is poisoned
Today the R3/R3b pre-emption is gated on `site.receiver_type.is_some()`. But when the import/wildcard guard
**skips recovery** for a typed receiver (poisoned external type), `receiver_type` is `None`, so R3b can
bind the receiver var name as an owner, and R3 can bind an import-shadowing param — both **false Exacts**.
Reproduced (both pre-existing on main, but slice 2 must FIX them since it now knows the binding exists):
- Python: `from ext import Foo` + `class x:` + `def run(x: Foo): x.m()` → today Exact `qualifier_owner` to
  `class x.m` (WRONG — x is a Foo).
- TS: `import api from "./api"` + `class Foo{m(){}}` + `function run(api: Foo){ api.m() }` → today Exact
  `import_qualified` to `./api` (WRONG — api is the param).

**Fix:** the classifier must signal "**a local receiver binding was found for `q`**" (typed param /
constructor local / annotated local) as a state DISTINCT from "`receiver_type` resolved". For Python/JS/TS,
when a binding is materialized — **even if the type is poisoned/unresolved (import/wildcard) — suppress R3
and R3b** (the receiver is provably a value, not an owner/module). Then: type resolved+unpoisoned → R6
`owner_lookup`; poisoned/unresolved → fall through to R6 **residue** (NameOnly/drop), NOT R3/R3b. Mirror the
Rust `rust_recv_materialized` shape (which suppresses on materialize, hit or miss). **Gate strictly to
Python/JS/TS — Rust/Go byte-identical.**

## MAJOR: scope-aware recovery
`walk_receiver_bindings` recovery is line-based and not scope-aware: a same-line-after-call assignment, or a
Python/JS **nested class-body** assignment, can be mis-recovered as a local. Repro:
`def run():\n    class C:\n        x = Foo()\n    x.m()` → `C.x` (a class attr) wrongly recovers `x: Foo`.
**Fix:** use the call START BYTE (not just line) for "binding before call", and **skip nested class-body
scopes** when scanning for the receiver's binding (class bodies are their own binding scope in Python/JS).

## TDD
Add failing tests FIRST for all three repros (assert: Python `x.m()` is NOT Exact `qualifier_owner` to
`class x` — it drops/NameOnly via residue; TS `api.m()` is NOT `import_qualified`; nested-class `x=Foo()`
does NOT recover). Plus a positive control: a NON-poisoned local typed param still resolves Exact
`TypedParam` (no regression). Then implement; confirm green. Rust/Go non-regression tests must stay green.

## Rules
- Git: explicit `git add`, never `-a`, never `eval/`; trailer
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Likely can't write `.git` —
  implement+verify, orchestrator commits.
- Finish: `cargo fmt`; `cargo fmt --check` + `cargo test` + `cargo test --features mcp` green.

## Report
The classifier signal you added (materialized vs resolved); the R3/R3b suppression gate; the scope-fix;
red-before/green-after for the 3 repros; Rust/Go unchanged; cargo counts; deviations.


## Probe question (answer in `probe_answer`, per arm)

Root-cause quality: does each arm make materialized-receiver suppression work even when the type is poisoned (state 'local binding found' distinct from 'type resolved'), with scope-aware recovery? Do its regression tests reproduce both false-Exact cases and would they fail pre-fix?

## Arm A diff

```diff
diff --git a/VERIFICATION.md b/VERIFICATION.md
new file mode 100644
index 0000000..dfc1b6e
--- /dev/null
+++ b/VERIFICATION.md
@@ -0,0 +1,78 @@
+# Verification — slice 2 diff-review fixes (materialized-receiver R3/R3b suppression + scope-aware recovery)
+
+Scope: fix BLOCKER 1 (poisoned typed receiver still suppresses R3b), BLOCKER 2 (a
+param shadowing an import still suppresses R3), and MAJOR (scope-aware receiver
+recovery: skip nested class-body scopes + byte-based before-call pruning). Strict TDD.
+
+## Commands run and results
+
+| Command | Result |
+|---|---|
+| `cargo build --lib` | clean, 0 warnings |
+| `cargo build --release` | clean |
+| `cargo fmt --check` | clean |
+| `cargo test` (default features, full suite) | **2493 passed, 0 failed** (28 test binaries; 0 ignored) |
+| `cargo test --features mcp` (full suite) | **2586 passed, 0 failed** (30 test binaries) |
+| `cargo test --doc` | 0 passed, 0 failed (no doc tests) |
+| `cargo test --test lang_rust` (Rust non-regression) | 28 passed, 0 failed |
+| `cargo test --test lang_go` (Go non-regression) | 41 passed, 0 failed |
+| `cd eval && uv run tier-a --matrix-only --allow-stale-sut` | **EXIT=0** — 40 `ok`, 2 pre-existing `expected_gap` (`python/from_import_alias`, `python/inherited_override`), **0 regressions/mismatches** |
+
+Full-suite run was the whole default `cargo test` (every `tests/` target + lib unit
+tests), not only the tests this task touches. No failures anywhere.
+
+## Red-before / green-after evidence (every fixed behavior has a pre-change-failing test)
+
+Observed RED on the working tree before implementing (`cargo test --test lang_python`
+/ `lang_typescript`), then GREEN after:
+
+| Behavior / code path | Test | Pre-change (RED) | Post-fix (GREEN) |
+|---|---|---|---|
+| B1: poisoned named-import type still suppresses R3b | `test_python_poisoned_import_type_suppresses_r3b_owner_key` | Exact `QualifierOwner` → FAIL | NameOnly residue |
+| B1 edge: poison via wildcard `"*"` sentinel branch | `test_python_wildcard_poison_suppresses_r3b_owner_key` | Exact `QualifierOwner` → FAIL (verified in a HEAD worktree) | NameOnly residue |
+| B2: param shadowing an import suppresses R3 | `test_typescript_param_shadowing_import_suppresses_import_qualified` | Exact `ImportQualified` → FAIL | Exact `TypedParam`→Foo.m |
+| B2 boundary: import qualifier with NO binding still resolves R3 | `test_typescript_import_qualifier_without_binding_still_resolves_r3` | green (correct both ways) → boundary guard | green |
+| MAJOR: nested class-body assignment not recovered | `test_python_nested_class_body_assignment_not_recovered` | `Some("Foo")` → FAIL | `None` |
+| MAJOR: same-line-after-call binding not recovered | `test_python_same_line_after_call_binding_not_recovered` | `Some("Foo")` → FAIL | `None` |
+| Positive control: clean local typed param still Exact | `test_python_nonpoisoned_local_typed_param_positive_control` | green (regression guard) | green |
+
+The wildcard RED was confirmed non-destructively in a throwaway worktree at HEAD
+(`git worktree add /tmp/dbg-red-check HEAD`): the wildcard variant produced
+`ResolvedCallee { ..., confidence: Exact, kind: QualifierOwner }` on pre-change code.
+The two boundary/positive controls pass on both pre-change and post-fix code by design
+(they guard that dropping the `is_import(q)` gate did not break real module calls and
+that clean recovery still yields Exact `TypedParam`).
+
+## Verified
+
+- Full default suite: 2493 passed / 0 failed. Full `--features mcp` suite: 2586 / 0.
+- Each of the three fixed behaviors (B1, B2, MAJOR×2) has a test observed to FAIL on
+  pre-change code and PASS after the fix.
+- Each new code path has a negative/edge case: wildcard `"*"` poison branch
+  (`test_python_wildcard_poison_...`), and the dropped `is_import(q)` gate boundary
+  (`test_typescript_import_qualifier_without_binding_...`).
+- Rust/Go byte-identical: `lang_rust` (28/28) + `lang_go` (41/41) green; Tier-A
+  `--matrix-only` EXIT=0 with 0 regressions across all rust/go/python matrix cases.
+- `cargo fmt --check` clean; release build clean; lib builds warning-free.
+- The Tier-A run wrote nothing under `eval/` (working tree stayed clean there); the 9
+  staged files are source/test only, `eval/` excluded.
+- `CACHE_VERSION` bumped 24→25 (the new serialized `CallSite.receiver_binding` field +
+  resolution-behavior change); the pinned assertion test updated to 25 and passes.
+
+## Not verified
+
+- **Full multi-corpus Tier-A** (`uv run tier-a --corpus all`) and the `--quick`
+  (rust-analyzer-backed) run: NOT run — these are human/orchestrator-triggered per
+  `eval/README.md` and CLAUDE.md. Only `--matrix-only --allow-stale-sut` was run here.
+- **pydantic + fastapi call-stats deltas** (the spec §7 "buy": `kind_exact.typed_param`
+  rise, `dropped_multi_owner` fall, `dropped_external_receiver` byte-flat): NOT
+  measured — Task 5 acceptance is host-run/orchestrator and needs a two-worktree
+  main-vs-branch call-stats comparison outside this session's scope.
+- **JavaScript** has no dedicated RED test: JS class-body fields parse as
+  `field_definition` (not the `variable_declarator`/`assignment_expression` arms), so
+  the nested-class repro is not reproducible in JS; the JS path is exercised by the
+  shared Python/JS/TS code and the existing (green) `lang_javascript` typed-receiver
+  suite, not by a new failing test.
+- **No out-of-scope test failures were observed.** The only pre-existing non-`ok`
+  Tier-A entries (`python/from_import_alias`, `python/inherited_override`) are
+  `expected_gap`, documented deferred gaps (spec §2.4), not regressions from this change.
diff --git a/src/ast.rs b/src/ast.rs
index 1656cef..45358d9 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -417,6 +417,7 @@ impl ParsedFile {
         func_node: &Node<'_>,
         receiver: &str,
         call_line: usize,
+        call_start_byte: usize,
         recover_var: bool,
     ) -> Option<(String, crate::resolution::ReceiverRecovery)> {
         use crate::languages::Language;
@@ -512,6 +513,7 @@ impl ParsedFile {
             true,
             receiver,
             call_line,
+            call_start_byte,
             &mut found,
             &mut bindings,
             recover_var,
@@ -4022,12 +4024,14 @@ impl ParsedFile {
         None
     }
 
+    #[allow(clippy::too_many_arguments)]
     fn walk_receiver_bindings(
         &self,
         node: Node<'_>,
         is_root: bool,
         receiver: &str,
         call_line: usize,
+        call_start_byte: usize,
         found: &mut Option<(String, crate::resolution::ReceiverRecovery)>,
         bindings: &mut usize,
         recover_var: bool,
@@ -4035,12 +4039,37 @@ impl ParsedFile {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        let is_py_js_ts = matches!(
+            self.language,
+            Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+        );
+        // "Binding before the call". Python/JS/TS prune by the call START BYTE so a
+        // same-line-after-call assignment (`x.m(); x = Foo()`) is excluded — it is
+        // not in scope at the call. Rust/Go keep the row-based prune (byte-identical).
+        let after_call = if is_py_js_ts {
+            node.start_byte() > call_start_byte
+        } else {
+            node.start_position().row + 1 > call_line
+        };
+        if after_call {
             return;
         }
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
+        // A nested class body is its own binding scope in Python/JS/TS: an assignment
+        // there defines a CLASS ATTRIBUTE (e.g. `C.x`), not a local of the enclosing
+        // function. Skip it so `def run(): class C: x = Foo()` does not mis-recover a
+        // local `x` (scope-aware recovery). Rust/Go unaffected (not py/js/ts).
+        if !is_root
+            && is_py_js_ts
+            && matches!(
+                node.kind(),
+                "class_definition" | "class_declaration" | "class"
+            )
+        {
+            return;
+        }
 
         match (self.language, node.kind()) {
             (Language::Rust, "let_declaration") => {
@@ -4204,6 +4233,7 @@ impl ParsedFile {
                 false,
                 receiver,
                 call_line,
+                call_start_byte,
                 found,
                 bindings,
                 recover_var,
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..8e7b4ce 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -68,6 +68,15 @@ pub struct CallSite {
     /// derived from the same scan as receiver_type.
     #[serde(default)]
     pub receiver_recovery: Option<crate::resolution::ReceiverRecovery>,
+    /// S3 P6-lite (Python/JS/TS): a local receiver binding (typed param /
+    /// constructor local / annotated local) was MATERIALIZED for the qualifier —
+    /// the qualifier is provably a value, not a module or owner key. Distinct from
+    /// `receiver_type`, which is `None` when the binding's type is poisoned
+    /// (import/wildcard-sourced). Drives R3/R3b pre-emption even for a poisoned
+    /// receiver. Inert for Rust/Go (those pre-empt via `receiver_outcome`). Excluded
+    /// from cmp_key — derived from the same scan as receiver_type.
+    #[serde(default)]
+    pub receiver_binding: bool,
     /// Number of arguments at the call site. `None` = not captured / unknown
     /// (the arity-disambiguation filter treats `None` as "keep").
     /// Excluded from cmp_key — positional data, not part of logical identity.
@@ -371,6 +380,7 @@ impl CallGraph {
                         ),
                         receiver_type: None,
                         receiver_recovery: None,
+                        receiver_binding: false,
                         arg_count: None,
                         arg_spread: false,
                         receiver_outcome: None,
@@ -640,6 +650,7 @@ impl CallGraph {
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
                             call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
@@ -652,8 +663,13 @@ impl CallGraph {
                             start_byte,
                             end_byte,
                             qualifier,
-                            receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                            receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                            receiver_type: recovered
+                                .as_ref()
+                                .and_then(|r| r.resolved_type().map(str::to_string)),
+                            receiver_recovery: recovered
+                                .as_ref()
+                                .and_then(|r| r.resolved_recovery()),
+                            receiver_binding: recovered.is_some(),
                             arg_count,
                             arg_spread,
                             receiver_outcome: None,
@@ -737,6 +753,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_binding: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -771,6 +788,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_binding: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -858,6 +876,7 @@ impl CallGraph {
                                     qualifier: None,
                                     receiver_type: None,
                                     receiver_recovery: None,
+                                    receiver_binding: false,
                                     arg_count: None,
                                     arg_spread: false,
                                     receiver_outcome: None,
@@ -955,6 +974,7 @@ impl CallGraph {
                                         qualifier: None,
                                         receiver_type: None,
                                         receiver_recovery: None,
+                                        receiver_binding: false,
                                         arg_count: None,
                                         arg_spread: false,
                                         receiver_outcome: None,
@@ -982,6 +1002,7 @@ impl CallGraph {
                                             qualifier: None,
                                             receiver_type: None,
                                             receiver_recovery: None,
+                                            receiver_binding: false,
                                             arg_count: None,
                                             arg_spread: false,
                                             receiver_outcome: None,
@@ -1615,6 +1636,7 @@ impl CallGraph {
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
                         call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
@@ -1627,8 +1649,11 @@ impl CallGraph {
                         start_byte,
                         end_byte,
                         qualifier,
-                        receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                        receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                        receiver_type: recovered
+                            .as_ref()
+                            .and_then(|r| r.resolved_type().map(str::to_string)),
+                        receiver_recovery: recovered.as_ref().and_then(|r| r.resolved_recovery()),
+                        receiver_binding: recovered.is_some(),
                         arg_count,
                         arg_spread,
                         receiver_outcome: None,
diff --git a/src/cpg_cache.rs b/src/cpg_cache.rs
index 6effcc0..122ec54 100644
--- a/src/cpg_cache.rs
+++ b/src/cpg_cache.rs
@@ -66,7 +66,8 @@ use std::path::{Path, PathBuf};
 /// - v22: method_class_span_ambiguous for fail-open line-id collisions.
 /// - v23: wrapper-canonical decorated extraction.
 /// - v24: Python/JS/TS typed-receiver recovery behavior.
-const CACHE_VERSION: u32 = 24; // 24: Python/JS/TS typed-receiver recovery behavior.
+/// - v25: CallSite gains `receiver_binding` (materialized-receiver R3/R3b suppression).
+const CACHE_VERSION: u32 = 25; // 25: CallSite.receiver_binding (materialized-receiver suppression).
 
 pub const SKIP_POLICY_VERSION: u32 = 1;
 
@@ -571,9 +572,10 @@ mod tests {
     }
 
     #[test]
-    fn cache_version_is_24_for_python_js_typed_receiver_recovery() {
-        // v24: Python/JS/TS typed-receiver recovery changes resolution behavior.
-        assert_eq!(super::CACHE_VERSION, 24);
+    fn cache_version_is_25_for_materialized_receiver_binding() {
+        // v25: CallSite gains `receiver_binding` (materialized-receiver R3/R3b
+        // suppression) — a serialized-shape + resolution-behavior change.
+        assert_eq!(super::CACHE_VERSION, 25);
     }
 
     #[test]
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..56a5bc1 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -228,10 +228,35 @@ pub enum ReceiverRecovery {
 /// S3 receiver-recovery: a syntactically-recovered static receiver type plus the
 /// fact that recovered it. Routing (owner_lookup → interface_impls → drop) happens
 /// downstream in `resolve_call_site` (spec §2 recover-and-route); this is recovery only.
+///
+/// A `Some(RecoveredReceiver)` always means **a local receiver binding was
+/// materialized** for the qualifier (typed param / constructor local / annotated
+/// local) — the qualifier is provably a value, not a module or owner key. `poisoned`
+/// distinguishes "binding found AND its type resolved to a usable owner key" from
+/// "binding found but the type is import/wildcard-sourced (external)": a poisoned
+/// receiver still suppresses R3/R3b (Python/JS/TS) but must NOT drive R6
+/// `owner_lookup` (it would forge a false Exact to a same-named local class).
 #[derive(Debug, Clone, PartialEq, Eq)]
 pub struct RecoveredReceiver {
     pub static_type: String,
     pub recovery: ReceiverRecovery,
+    /// Python/JS/TS only: the recovered type name is import/wildcard-sourced, so the
+    /// binding is materialized-but-unresolved. Always `false` for Rust/Go.
+    pub poisoned: bool,
+}
+
+impl RecoveredReceiver {
+    /// The resolved owner-key type — `None` when the binding is poisoned. This is
+    /// what `CallSite.receiver_type` carries: a poisoned receiver has no usable type.
+    pub fn resolved_type(&self) -> Option<&str> {
+        (!self.poisoned).then_some(self.static_type.as_str())
+    }
+
+    /// The recovering fact — `None` when poisoned (mirrors `resolved_type`, so the
+    /// telemetry/kind split only reflects genuinely resolved receivers).
+    pub fn resolved_recovery(&self) -> Option<ReceiverRecovery> {
+        (!self.poisoned).then_some(self.recovery)
+    }
 }
 
 /// Inputs a `ReceiverClassifier` needs to recover a receiver's static type. Borrows
@@ -249,6 +274,10 @@ pub struct ReceiverCtx<'a> {
     pub fn_node: tree_sitter::Node<'a>,
     /// 1-indexed call line.
     pub call_line: usize,
+    /// Byte offset of the call expression's start. Used (Python/JS/TS) to prune
+    /// same-line-after-call bindings from the receiver scan — a binding starting
+    /// after the call is not in scope at the call (scope-aware recovery).
+    pub call_start_byte: usize,
     /// For node_text + the legacy `receiver_type_in_fn` scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
@@ -332,26 +361,46 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
     let simple = !q.is_empty() && q.chars().all(|c| c.is_alphanumeric() || c == '_');
     let is_kw = matches!(q, "self" | "this" | "cls");
     let is_recv = ctx.recv_var == Some(q);
-    let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
-    if !(simple && !is_kw && !is_recv && !is_import) {
+    if !simple || is_kw || is_recv {
         return None;
     }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
-    let static_type = owner_key(&peel_type(&ty));
-    if matches!(
+    let is_py_js_ts = matches!(
         ctx.parsed.language,
         Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
-    {
+    );
+    // Rust/Go: an imported qualifier `q` is a MODULE name, never a receiver — the
+    // original P6-lite gate. Byte-identical. For Python/JS/TS the same-named local
+    // binding (typed param / local) SHADOWS the import (a value, not the module), so
+    // we do NOT skip on `is_import(q)`; the binding scan below decides.
+    let is_import_q = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
+    if !is_py_js_ts && is_import_q {
         return None;
     }
+    let (ty, how) = ctx.parsed.receiver_type_in_fn(
+        &ctx.fn_node,
+        q,
+        ctx.call_line,
+        ctx.call_start_byte,
+        recover_var,
+    )?;
+    let static_type = owner_key(&peel_type(&ty));
+    if is_py_js_ts {
+        // §3.3 guard: the recovered TYPE name is import/wildcard-sourced (external).
+        // A binding WAS materialized, so keep the receiver (it suppresses R3/R3b) but
+        // mark it poisoned so it does not drive R6 owner_lookup into a false Exact.
+        let poisoned = ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"));
+        return Some(RecoveredReceiver {
+            static_type,
+            recovery: how,
+            poisoned,
+        });
+    }
     Some(RecoveredReceiver {
         static_type,
         recovery: how,
+        poisoned: false,
     })
 }
 
@@ -430,6 +479,7 @@ fn recover_type_assertion(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
     Some(RecoveredReceiver {
         static_type,
         recovery: ReceiverRecovery::TypeAssertion,
+        poisoned: false,
     })
 }
 
@@ -1007,6 +1057,15 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
+                // A MATERIALIZED receiver binding (typed param / constructor local /
+                // annotated local) means the qualifier is provably a value, not a
+                // module or owner key — even when its type is poisoned
+                // (import/wildcard-sourced) and thus `receiver_type` is None. Suppress
+                // R3/R3b on materialize (hit or miss), mirroring `rust_recv_materialized`:
+                // a resolved+unpoisoned type flows to R6 owner_lookup below; a
+                // poisoned/unresolved one falls through to R6 residue (NameOnly/drop),
+                // NOT R3/R3b. The `receiver_type.is_some()` disjunct is cache-compat
+                // insurance (a stale entry may carry a type without `receiver_binding`).
                 let recovered_recv_materialized = matches!(
                     caller_lang,
                     Some(
@@ -1015,7 +1074,8 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && (site.receiver_type.is_some()
+                    || site.receiver_binding);
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -2138,6 +2198,7 @@ mod scope_resolution_predicate_tests {
             qualifier: None,
             receiver_type: None,
             receiver_recovery: None,
+            receiver_binding: false,
             arg_count: None,
             arg_spread: false,
             receiver_outcome: None,
diff --git a/src/resolution_disproof.rs b/src/resolution_disproof.rs
index 0724bf3..8baa413 100644
--- a/src/resolution_disproof.rs
+++ b/src/resolution_disproof.rs
@@ -95,6 +95,7 @@ mod tests {
             qualifier: None,
             receiver_type: None,
             receiver_recovery: None,
+            receiver_binding: false,
             arg_count: None,
             arg_spread: false,
             receiver_outcome: None,
diff --git a/tests/lang/python/typed_receiver_test.rs b/tests/lang/python/typed_receiver_test.rs
index ec612c4..7609812 100644
--- a/tests/lang/python/typed_receiver_test.rs
+++ b/tests/lang/python/typed_receiver_test.rs
@@ -89,6 +89,107 @@ fn test_python_shadow_import_wildcard_and_singleton_external_skip() {
     }
 }
 
+#[test]
+fn test_python_poisoned_import_type_suppresses_r3b_owner_key() {
+    // BLOCKER 1: `from ext import Foo` poisons the recovered type (Foo is
+    // external), but the param `x: Foo` is a MATERIALIZED binding — `x` is
+    // provably a value, not the owner key `class x`. R3b must NOT mint an Exact
+    // `qualifier_owner` to `class x.m`; it must fall through to residue.
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import Foo\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "poisoned import type is not recovered"
+    );
+    let r = cg.resolve_call_site(&s);
+    assert!(
+        r.iter()
+            .all(|c| c.confidence != ResolutionConfidence::Exact),
+        "expected drop/NameOnly residue, got Exact: {r:?}"
+    );
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner),
+        "R3b false-Exact to class x survived: {r:?}"
+    );
+}
+
+#[test]
+fn test_python_wildcard_poison_suppresses_r3b_owner_key() {
+    // BLOCKER 1, wildcard variant: `from ext import *` poisons the type via the
+    // `"*"` sentinel (not a named import). The param `x: Foo` is still a
+    // materialized binding, so R3b must NOT mint an Exact `qualifier_owner` to the
+    // colliding `class x.m`. Exercises the wildcard branch of poison→suppress.
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import *\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "wildcard-poisoned type is not recovered"
+    );
+    let r = cg.resolve_call_site(&s);
+    assert!(
+        r.iter()
+            .all(|c| c.confidence != ResolutionConfidence::Exact),
+        "expected drop/NameOnly residue, got Exact: {r:?}"
+    );
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner),
+        "R3b false-Exact to class x survived under wildcard: {r:?}"
+    );
+}
+
+#[test]
+fn test_python_nested_class_body_assignment_not_recovered() {
+    // MAJOR: `x = Foo()` inside a nested class body is a class ATTRIBUTE (`C.x`),
+    // not a local of `run`. Scope-aware recovery must skip the nested class scope.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    class C:\n        x = Foo()\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "class-body attr must not recover a local receiver"
+    );
+    assert_eq!(s.receiver_recovery, None);
+}
+
+#[test]
+fn test_python_same_line_after_call_binding_not_recovered() {
+    // MAJOR: the binding `x = Foo()` textually FOLLOWS the call on the same line;
+    // it is not in scope at the call. Byte-based before-call pruning excludes it.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    x.m(); x = Foo()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "same-line-after-call binding must not recover"
+    );
+}
+
+#[test]
+fn test_python_nonpoisoned_local_typed_param_positive_control() {
+    // Positive control: a clean (non-poisoned, non-imported) local typed param
+    // still resolves Exact TypedParam — no regression from the guards.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+}
+
 #[test]
 fn test_python_r3b_collision_and_local_miss_fallthrough() {
     let collision = graph(&[(
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 77b4b71..8db47dd 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -1,7 +1,7 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionKind};
+use prism::resolution::{ReceiverRecovery, ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
 fn graph(src: &str) -> CallGraph {
@@ -12,6 +12,19 @@ fn graph(src: &str) -> CallGraph {
     CallGraph::build(&files)
 }
 
+fn graph_files(srcs: &[(&str, &str)]) -> CallGraph {
+    let files: BTreeMap<_, _> = srcs
+        .iter()
+        .map(|(path, src)| {
+            (
+                (*path).to_string(),
+                ParsedFile::parse(path, src, Language::TypeScript).expect("parse ts"),
+            )
+        })
+        .collect();
+    CallGraph::build(&files)
+}
+
 fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
     cg.calls
         .iter()
@@ -44,6 +57,54 @@ fn test_typescript_parameter_annotation_and_new_constructor_recover() {
     }
 }
 
+#[test]
+fn test_typescript_param_shadowing_import_suppresses_import_qualified() {
+    // BLOCKER 2: `api` is a default import, but the param `api: Foo` SHADOWS it —
+    // a materialized binding. R3 `import_qualified` must NOT fire; `api.m()` binds
+    // to the local Foo.m via the (non-poisoned, local) param type.
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from \"./api\";\nclass Foo { m() {} }\nfunction run(api: Foo) { api.m(); }\n",
+        ),
+    ]);
+    let s = site(&cg, "run", "m");
+    let r = cg.resolve_call_site(&s);
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::ImportQualified),
+        "R3 import_qualified false-bind to ./api survived: {r:?}"
+    );
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+}
+
+#[test]
+fn test_typescript_import_qualifier_without_binding_still_resolves_r3() {
+    // Negative control for the dropped `is_import(q)` gate: when the qualifier is a
+    // genuine import with NO shadowing local binding, recovery must find nothing and
+    // R3 `import_qualified` must still resolve the module call (not regress to a drop
+    // or a residue). Passes both before and after the fix — it guards the boundary.
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from \"./api\";\nfunction run() { api.m(); }\n",
+        ),
+    ]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "no local binding → nothing recovered"
+    );
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(r[0].target.file, "api.ts");
+}
+
 #[test]
 fn test_typescript_bare_factory_call_does_not_recover() {
     let cg = graph(
diff --git a/tests/name_resolution/consumer_test.rs b/tests/name_resolution/consumer_test.rs
index 7cff2c3..b12fc45 100644
--- a/tests/name_resolution/consumer_test.rs
+++ b/tests/name_resolution/consumer_test.rs
@@ -103,6 +103,7 @@ fn call_site(file: &str, name: &str, byte: usize) -> CallSite {
         qualifier: None,
         receiver_type: None,
         receiver_recovery: None,
+        receiver_binding: false,
         arg_count: None,
         arg_spread: false,
         receiver_outcome: None,
diff --git a/tests/navigation/scoped_calls_test.rs b/tests/navigation/scoped_calls_test.rs
index eb133c1..2c00aec 100644
--- a/tests/navigation/scoped_calls_test.rs
+++ b/tests/navigation/scoped_calls_test.rs
@@ -56,6 +56,7 @@ fn resolved_targets(
                 qualifier: qualifier.map(str::to_string),
                 receiver_type: None,
                 receiver_recovery: None,
+                receiver_binding: false,
                 arg_count: None,
                 arg_spread: false,
                 receiver_outcome: None,

```

## Arm B diff

```diff
diff --git a/src/ast.rs b/src/ast.rs
index 1656cef..e28887f 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -407,16 +407,17 @@ impl ParsedFile {
     }
 
     /// S3 P6-lite: syntactically-provable receiver type for `receiver` at a call
-    /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
-    /// also recovers `var r T` declarations. Only bindings at or before `call_line`
-    /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// starting at `call_start_byte`. Typed params + constructor locals; when
+    /// `recover_var` is true also recovers `var r T` declarations. Only bindings
+    /// that START BEFORE the call (byte-precise — so a same-line-after-call
+    /// reassignment does not count) and are NOT in a nested class body count;
+    /// >1 such binding means shadow bail. Rust + Go + guarded Python/JS/TS.
     /// Returns the raw, unpeeled type text + which fact recovered it.
     pub fn receiver_type_in_fn(
         &self,
         func_node: &Node<'_>,
         receiver: &str,
-        call_line: usize,
+        call_start_byte: usize,
         recover_var: bool,
     ) -> Option<(String, crate::resolution::ReceiverRecovery)> {
         use crate::languages::Language;
@@ -511,7 +512,7 @@ impl ParsedFile {
             *func_node,
             true,
             receiver,
-            call_line,
+            call_start_byte,
             &mut found,
             &mut bindings,
             recover_var,
@@ -4027,7 +4028,7 @@ impl ParsedFile {
         node: Node<'_>,
         is_root: bool,
         receiver: &str,
-        call_line: usize,
+        call_start_byte: usize,
         found: &mut Option<(String, crate::resolution::ReceiverRecovery)>,
         bindings: &mut usize,
         recover_var: bool,
@@ -4035,12 +4036,20 @@ impl ParsedFile {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        // Byte-precise "binding before call": prune any node that STARTS at or
+        // after the call (a same-line-after-call reassignment must not count).
+        if node.start_byte() >= call_start_byte {
             return;
         }
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
+        // A nested class body is its own binding scope (Python/JS/TS); a class
+        // attribute is not a local, so do not descend into it. Empty node list for
+        // Rust/Go → byte-identical.
+        if !is_root && self.language.class_node_types().contains(&node.kind()) {
+            return;
+        }
 
         match (self.language, node.kind()) {
             (Language::Rust, "let_declaration") => {
@@ -4203,7 +4212,7 @@ impl ParsedFile {
                 child,
                 false,
                 receiver,
-                call_line,
+                call_start_byte,
                 found,
                 bindings,
                 recover_var,
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..4f13632 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -68,6 +68,14 @@ pub struct CallSite {
     /// derived from the same scan as receiver_type.
     #[serde(default)]
     pub receiver_recovery: Option<crate::resolution::ReceiverRecovery>,
+    /// Slice 2: a local receiver binding for the qualifier was materialized
+    /// (typed param / constructor local / annotated local) — a signal DISTINCT
+    /// from `receiver_type`: it stays `true` even when the type is withheld
+    /// (import/wildcard-poisoned, so `receiver_type` is None). A materialized
+    /// receiver is provably a value, so it pre-empts R3/R3b for Python/JS/TS.
+    /// Excluded from cmp_key — derived from the same scan as receiver_type.
+    #[serde(default)]
+    pub receiver_materialized: bool,
     /// Number of arguments at the call site. `None` = not captured / unknown
     /// (the arity-disambiguation filter treats `None` as "keep").
     /// Excluded from cmp_key — positional data, not part of logical identity.
@@ -83,6 +91,25 @@ pub struct CallSite {
     pub receiver_outcome: Option<crate::resolution_identity::ReceiverOutcome>,
 }
 
+/// Split a `ReceiverClassification` into the `CallSite` receiver fields:
+/// `(receiver_type, receiver_recovery, receiver_materialized)`. A `Resolved`
+/// carries a usable type and is materialized; a `Materialized` withholds the type
+/// (poisoned) but still flags the binding; `None` is neither.
+fn split_classification(
+    recovered: Option<crate::resolution::ReceiverClassification>,
+) -> (
+    Option<String>,
+    Option<crate::resolution::ReceiverRecovery>,
+    bool,
+) {
+    use crate::resolution::ReceiverClassification;
+    match recovered {
+        Some(ReceiverClassification::Resolved(r)) => (Some(r.static_type), Some(r.recovery), true),
+        Some(ReceiverClassification::Materialized) => (None, None, true),
+        None => (None, None, false),
+    }
+}
+
 /// Parameter arity for a method definition (language-agnostic shape).
 ///
 /// `params` is the count of parameter NAMES (not declarations) excluding the Go
@@ -371,6 +398,7 @@ impl CallGraph {
                         ),
                         receiver_type: None,
                         receiver_recovery: None,
+                        receiver_materialized: false,
                         arg_count: None,
                         arg_spread: false,
                         receiver_outcome: None,
@@ -640,10 +668,13 @@ impl CallGraph {
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
                             call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
                         });
+                        let (receiver_type, receiver_recovery, receiver_materialized) =
+                            split_classification(recovered);
                         let site = CallSite {
                             caller: caller_id.clone(),
                             callee_name,
@@ -652,8 +683,9 @@ impl CallGraph {
                             start_byte,
                             end_byte,
                             qualifier,
-                            receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                            receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                            receiver_type,
+                            receiver_recovery,
+                            receiver_materialized,
                             arg_count,
                             arg_spread,
                             receiver_outcome: None,
@@ -737,6 +769,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -771,6 +804,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -858,6 +892,7 @@ impl CallGraph {
                                     qualifier: None,
                                     receiver_type: None,
                                     receiver_recovery: None,
+                                    receiver_materialized: false,
                                     arg_count: None,
                                     arg_spread: false,
                                     receiver_outcome: None,
@@ -955,6 +990,7 @@ impl CallGraph {
                                         qualifier: None,
                                         receiver_type: None,
                                         receiver_recovery: None,
+                                        receiver_materialized: false,
                                         arg_count: None,
                                         arg_spread: false,
                                         receiver_outcome: None,
@@ -982,6 +1018,7 @@ impl CallGraph {
                                             qualifier: None,
                                             receiver_type: None,
                                             receiver_recovery: None,
+                                            receiver_materialized: false,
                                             arg_count: None,
                                             arg_spread: false,
                                             receiver_outcome: None,
@@ -1615,10 +1652,13 @@ impl CallGraph {
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
                         call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
                     });
+                    let (receiver_type, receiver_recovery, receiver_materialized) =
+                        split_classification(recovered);
                     let site = CallSite {
                         caller: caller_id.clone(),
                         callee_name: callee_name.clone(),
@@ -1627,8 +1667,9 @@ impl CallGraph {
                         start_byte,
                         end_byte,
                         qualifier,
-                        receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                        receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                        receiver_type,
+                        receiver_recovery,
+                        receiver_materialized,
                         arg_count,
                         arg_spread,
                         receiver_outcome: None,
diff --git a/src/cpg_cache.rs b/src/cpg_cache.rs
index 6effcc0..86dcbc0 100644
--- a/src/cpg_cache.rs
+++ b/src/cpg_cache.rs
@@ -66,7 +66,9 @@ use std::path::{Path, PathBuf};
 /// - v22: method_class_span_ambiguous for fail-open line-id collisions.
 /// - v23: wrapper-canonical decorated extraction.
 /// - v24: Python/JS/TS typed-receiver recovery behavior.
-const CACHE_VERSION: u32 = 24; // 24: Python/JS/TS typed-receiver recovery behavior.
+/// - v25: CallSite `receiver_materialized` field (materialized-receiver R3/R3b
+///   suppression + scope-aware recovery).
+const CACHE_VERSION: u32 = 25; // 25: CallSite.receiver_materialized (materialized-receiver suppression).
 
 pub const SKIP_POLICY_VERSION: u32 = 1;
 
@@ -571,9 +573,10 @@ mod tests {
     }
 
     #[test]
-    fn cache_version_is_24_for_python_js_typed_receiver_recovery() {
-        // v24: Python/JS/TS typed-receiver recovery changes resolution behavior.
-        assert_eq!(super::CACHE_VERSION, 24);
+    fn cache_version_is_25_for_receiver_materialized_field() {
+        // v25: CallSite gains `receiver_materialized` (materialized-receiver R3/R3b
+        // suppression + scope-aware recovery); the serialized shape changed.
+        assert_eq!(super::CACHE_VERSION, 25);
     }
 
     #[test]
diff --git a/src/languages/mod.rs b/src/languages/mod.rs
index 20c33a3..c615e1c 100644
--- a/src/languages/mod.rs
+++ b/src/languages/mod.rs
@@ -111,6 +111,19 @@ impl Language {
         }
     }
 
+    /// Class-scope boundary node kinds. A nested class body is its own binding
+    /// scope (Python/JS/TS), so the receiver-binding scan must not descend into a
+    /// nested class and mistake a class attribute (`class C: x = Foo()`) for a
+    /// local. Empty for languages where the scan does not treat classes as binding
+    /// scopes — keeps Rust/Go (and others) byte-identical.
+    pub fn class_node_types(&self) -> &'static [&'static str] {
+        match self {
+            Self::Python => &["class_definition"],
+            Self::JavaScript | Self::TypeScript | Self::Tsx => &["class_declaration", "class"],
+            _ => &[],
+        }
+    }
+
     /// Whether a node kind is an identifier/variable reference.
     pub fn is_identifier_node(&self, kind: &str) -> bool {
         // Common identifier types shared across most languages
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..a0ad7a8 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -234,6 +234,22 @@ pub struct RecoveredReceiver {
     pub recovery: ReceiverRecovery,
 }
 
+/// Outcome of receiver classification, distinguishing "type resolved" from
+/// "binding materialized but type withheld".
+///
+/// `Resolved` carries a usable static type for R6 `owner_lookup`. `Materialized`
+/// means a local receiver binding for the qualifier was found (typed param /
+/// constructor local / annotated local) but its type is import- or wildcard-
+/// poisoned (Python/JS/TS) so it is withheld — the binding still proves the
+/// qualifier is a *value*, not a module/owner, so it must suppress R3/R3b and fall
+/// through to the R6 residue. This mirrors the Rust `rust_recv_materialized` shape
+/// (materialize suppresses R3/R3b whether the type hits or misses).
+#[derive(Debug, Clone, PartialEq, Eq)]
+pub enum ReceiverClassification {
+    Resolved(RecoveredReceiver),
+    Materialized,
+}
+
 /// Inputs a `ReceiverClassifier` needs to recover a receiver's static type. Borrows
 /// from the ParsedFile/tree of the call's enclosing function. Carries `recv_var` +
 /// `file_imports` because the legacy gate tests `is_recv`/`is_import`
@@ -249,6 +265,9 @@ pub struct ReceiverCtx<'a> {
     pub fn_node: tree_sitter::Node<'a>,
     /// 1-indexed call line.
     pub call_line: usize,
+    /// Call-node start byte — the byte-precise "binding before call" cutoff for the
+    /// receiver-binding scan (a same-line-after-call reassignment must not count).
+    pub call_start_byte: usize,
     /// For node_text + the legacy `receiver_type_in_fn` scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
@@ -260,7 +279,7 @@ pub struct ReceiverCtx<'a> {
 /// Swappable receiver-recovery strategy (strangler seam, spec §2). `Sync` because
 /// the CPG build extracts call sites with rayon (`call_graph.rs` par_iter).
 pub trait ReceiverClassifier: Sync {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver>;
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<ReceiverClassification>;
 }
 
 /// Receiver-recovery mode (spec §13.3). `Expanded` (default) turns the implemented
@@ -315,7 +334,10 @@ impl ReceiverRecoveryConfig {
 /// Runs the qualifier/keyword/recv-var/import gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
 /// is true), peeled + owner-keyed.
-fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<RecoveredReceiver> {
+fn recover_simple_ident(
+    ctx: &ReceiverCtx<'_>,
+    recover_var: bool,
+) -> Option<ReceiverClassification> {
     use crate::languages::Language;
     if !matches!(
         ctx.parsed.language,
@@ -333,40 +355,51 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
     let is_kw = matches!(q, "self" | "this" | "cls");
     let is_recv = ctx.recv_var == Some(q);
     let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
-    if !(simple && !is_kw && !is_recv && !is_import) {
+    let is_py_js = matches!(
+        ctx.parsed.language,
+        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+    );
+    // Rust/Go bail when the qualifier is itself an import (byte-identical). For
+    // Python/JS/TS a local binding SHADOWS an import (BLOCKER-2: `import api` +
+    // `run(api: Foo)`), so the import bail moves to the post-recovery type-name
+    // guard below — the qualifier-import check must not pre-empt the scan.
+    if !simple || is_kw || is_recv || (is_import && !is_py_js) {
         return None;
     }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
+    let (ty, how) =
+        ctx.parsed
+            .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var)?;
     let static_type = owner_key(&peel_type(&ty));
-    if matches!(
-        ctx.parsed.language,
-        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
+    // A binding was materialized. For Python/JS/TS an import- or wildcard-poisoned
+    // TYPE is withheld (external / cross-module — slice 3/4), but the binding still
+    // proves the qualifier is a value → report `Materialized` so R3/R3b are
+    // suppressed and the call falls through to the R6 residue. Rust/Go never reach
+    // here poisoned (the guard is Python/JS/TS-only), so they stay byte-identical.
+    if is_py_js
+        && ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
     {
-        return None;
+        return Some(ReceiverClassification::Materialized);
     }
-    Some(RecoveredReceiver {
+    Some(ReceiverClassification::Resolved(RecoveredReceiver {
         static_type,
         recovery: how,
-    })
+    }))
 }
 
 /// PR-1 P6-lite recovery, extracted verbatim from the former
 /// `call_graph::recover_receiver` (the qualifier/keyword/recv-var/import gate, then
 /// the typed-param / constructor-local scan, peeled + owner-keyed).
 /// Byte-identical to PR-1: `recover_var = false`.
-pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
+pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<ReceiverClassification> {
     recover_simple_ident(ctx, false)
 }
 
 /// `legacy` — PR-1 behavior, no new forms.
 pub struct LegacyClassifier;
 impl ReceiverClassifier for LegacyClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<ReceiverClassification> {
         legacy_recover(&ctx)
     }
 }
@@ -377,13 +410,14 @@ pub struct ExpandedClassifier {
     pub var_local: bool,
 }
 impl ReceiverClassifier for ExpandedClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<ReceiverClassification> {
         if let Some(r) = recover_simple_ident(&ctx, self.var_local) {
             return Some(r);
         }
+        // The Go type-assertion path always yields a usable type (never poisoned).
         if self.type_assertion {
             if let Some(r) = recover_type_assertion(&ctx) {
-                return Some(r);
+                return Some(ReceiverClassification::Resolved(r));
             }
         }
         None
@@ -1007,6 +1041,13 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
+                // A materialized Python/JS/TS receiver binding pre-empts R3/R3b even
+                // when its type is poisoned/withheld (`receiver_type` is None): the
+                // binding proves the qualifier is a value, not a module (R3) or an
+                // owner key (R3b). `receiver_materialized` is the distinct signal —
+                // true for both a resolved type AND a materialized-but-poisoned
+                // binding — mirroring `rust_recv_materialized` (suppress on
+                // materialize, hit or miss).
                 let recovered_recv_materialized = matches!(
                     caller_lang,
                     Some(
@@ -1015,7 +1056,7 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && site.receiver_materialized;
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -2138,6 +2179,7 @@ mod scope_resolution_predicate_tests {
             qualifier: None,
             receiver_type: None,
             receiver_recovery: None,
+            receiver_materialized: false,
             arg_count: None,
             arg_spread: false,
             receiver_outcome: None,
diff --git a/src/resolution_disproof.rs b/src/resolution_disproof.rs
index 0724bf3..c100aa2 100644
--- a/src/resolution_disproof.rs
+++ b/src/resolution_disproof.rs
@@ -95,6 +95,7 @@ mod tests {
             qualifier: None,
             receiver_type: None,
             receiver_recovery: None,
+            receiver_materialized: false,
             arg_count: None,
             arg_spread: false,
             receiver_outcome: None,
diff --git a/tests/lang/python/typed_receiver_test.rs b/tests/lang/python/typed_receiver_test.rs
index ec612c4..e580786 100644
--- a/tests/lang/python/typed_receiver_test.rs
+++ b/tests/lang/python/typed_receiver_test.rs
@@ -89,6 +89,100 @@ fn test_python_shadow_import_wildcard_and_singleton_external_skip() {
     }
 }
 
+/// BLOCKER-1: a MATERIALIZED but import-poisoned typed param whose name collides
+/// with an in-repo class must NOT mint a false Exact `qualifier_owner` to that
+/// class. The materialized binding proves `x` is a value (not an owner), so R3b is
+/// suppressed and the call falls through to the NameOnly R6 residue.
+#[test]
+fn test_python_poisoned_param_suppresses_r3b_owner_collision() {
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import Foo\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    // Poisoned (Foo is imported) → no type is exposed to R6.
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner),
+        "must not bind `class x.m` via R3b qualifier_owner"
+    );
+    assert!(
+        r.iter()
+            .all(|c| c.confidence != ResolutionConfidence::Exact),
+        "poisoned receiver must not resolve to any Exact edge"
+    );
+}
+
+/// BLOCKER-1 (wildcard sub-path of the Materialized branch): a WILDCARD-import
+/// poisoned typed param whose name collides with an in-repo class must also
+/// suppress R3b — the whole-file wildcard skip withholds the type, but the binding
+/// is still materialized (distinct trigger from the named-import case above).
+#[test]
+fn test_python_wildcard_poisoned_param_suppresses_r3b_owner_collision() {
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import *\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner),
+        "wildcard-poisoned receiver must not bind `class x.m` via R3b"
+    );
+    assert!(
+        r.iter()
+            .all(|c| c.confidence != ResolutionConfidence::Exact),
+        "wildcard-poisoned receiver must not resolve to any Exact edge"
+    );
+}
+
+/// MAJOR (scope-aware recovery): a class-body attribute `C.x = Foo()` is its own
+/// binding scope; it must NOT be recovered as the local receiver's type.
+#[test]
+fn test_python_nested_class_body_assignment_does_not_recover() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    class C:\n        x = Foo()\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(cg
+        .resolve_call_site(&s)
+        .iter()
+        .all(|c| c.kind != ResolutionKind::ConstructorLocal));
+}
+
+/// MAJOR (byte-precise "binding before call"): an `x = Foo()` reassignment AFTER
+/// the call on the SAME line must not be recovered — the guard is byte-based, not
+/// line-based.
+#[test]
+fn test_python_same_line_rebind_after_call_does_not_recover() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run(x):\n    x.m(); x = Foo()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
+
+/// Positive control: a NON-poisoned local typed param still resolves Exact
+/// `TypedParam` (no regression from the suppression / scope changes).
+#[test]
+fn test_python_unpoisoned_typed_param_still_exact() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+}
+
 #[test]
 fn test_python_r3b_collision_and_local_miss_fallthrough() {
     let collision = graph(&[(
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 77b4b71..09dd68e 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -12,6 +12,19 @@ fn graph(src: &str) -> CallGraph {
     CallGraph::build(&files)
 }
 
+fn graph_files(srcs: &[(&str, &str)]) -> CallGraph {
+    let files: BTreeMap<_, _> = srcs
+        .iter()
+        .map(|(path, src)| {
+            (
+                (*path).to_string(),
+                ParsedFile::parse(path, src, Language::TypeScript).expect("parse ts"),
+            )
+        })
+        .collect();
+    CallGraph::build(&files)
+}
+
 fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
     cg.calls
         .iter()
@@ -44,6 +57,31 @@ fn test_typescript_parameter_annotation_and_new_constructor_recover() {
     }
 }
 
+/// BLOCKER-2: a typed param whose name equals a default-import binding
+/// (`import api from "./api"` + `function run(api: Foo)`) must recover as the
+/// param's type `Foo` and resolve to the local `Foo.m` — NOT to the imported
+/// module's free `m` via R3 `import_qualified`. The materialized binding shadows
+/// the import.
+#[test]
+fn test_typescript_typed_param_shadows_default_import() {
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from \"./api\";\nclass Foo { m() {} }\nfunction run(api: Foo) { api.m(); }\n",
+        ),
+    ]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+    assert!(
+        r.iter().all(|c| c.kind != ResolutionKind::ImportQualified),
+        "typed param must not resolve via import_qualified"
+    );
+}
+
 #[test]
 fn test_typescript_bare_factory_call_does_not_recover() {
     let cg = graph(
diff --git a/tests/name_resolution/consumer_test.rs b/tests/name_resolution/consumer_test.rs
index 7cff2c3..dfc8a6d 100644
--- a/tests/name_resolution/consumer_test.rs
+++ b/tests/name_resolution/consumer_test.rs
@@ -103,6 +103,7 @@ fn call_site(file: &str, name: &str, byte: usize) -> CallSite {
         qualifier: None,
         receiver_type: None,
         receiver_recovery: None,
+        receiver_materialized: false,
         arg_count: None,
         arg_spread: false,
         receiver_outcome: None,
diff --git a/tests/navigation/scoped_calls_test.rs b/tests/navigation/scoped_calls_test.rs
index eb133c1..0af2749 100644
--- a/tests/navigation/scoped_calls_test.rs
+++ b/tests/navigation/scoped_calls_test.rs
@@ -56,6 +56,7 @@ fn resolved_targets(
                 qualifier: qualifier.map(str::to_string),
                 receiver_type: None,
                 receiver_recovery: None,
+                receiver_materialized: false,
                 arg_count: None,
                 arg_spread: false,
                 receiver_outcome: None,

```
