# Blind pairwise code-review judgment — DBGF-DBG-02-gpt55-d2

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
diff --git a/src/ast.rs b/src/ast.rs
index 1656cef..7a43490 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -407,16 +407,18 @@ impl ParsedFile {
     }
 
     /// S3 P6-lite: syntactically-provable receiver type for `receiver` at a call
-    /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
-    /// also recovers `var r T` declarations. Only bindings at or before `call_line`
-    /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// on `call_line` starting at `call_start_byte`. Typed params + constructor
+    /// locals; when `recover_var` is true also recovers `var r T` declarations.
+    /// Only bindings before the call count (before `call_start_byte` for
+    /// Python/JS/TS, at or before `call_line` for Rust/Go); >1 binding before
+    /// the call means shadow bail. Rust + Go + guarded Python/JS/TS.
     /// Returns the raw, unpeeled type text + which fact recovered it.
     pub fn receiver_type_in_fn(
         &self,
         func_node: &Node<'_>,
         receiver: &str,
         call_line: usize,
+        call_start_byte: usize,
         recover_var: bool,
     ) -> Option<(String, crate::resolution::ReceiverRecovery)> {
         use crate::languages::Language;
@@ -512,6 +514,7 @@ impl ParsedFile {
             true,
             receiver,
             call_line,
+            call_start_byte,
             &mut found,
             &mut bindings,
             recover_var,
@@ -4022,12 +4025,14 @@ impl ParsedFile {
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
@@ -4035,12 +4040,38 @@ impl ParsedFile {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        let byte_scoped = matches!(
+            self.language,
+            Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+        );
+        // "Binding before call" is byte-precise for Python/JS/TS: a same-line
+        // binding AFTER the call must not count. Rust/Go keep the line cutoff
+        // (byte-identical; e.g. a `for` post statement binding stays counted).
+        if byte_scoped {
+            if node.start_byte() >= call_start_byte {
+                return;
+            }
+        } else if node.start_position().row + 1 > call_line {
             return;
         }
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
+        // Class bodies are their own binding scope in Python/JS/TS: a nested
+        // class's `x = Foo()` is a class attribute, not a local of the
+        // enclosing function.
+        if !is_root
+            && match self.language {
+                Language::Python => node.kind() == "class_definition",
+                Language::JavaScript | Language::TypeScript | Language::Tsx => matches!(
+                    node.kind(),
+                    "class_declaration" | "abstract_class_declaration" | "class"
+                ),
+                _ => false,
+            }
+        {
+            return;
+        }
 
         match (self.language, node.kind()) {
             (Language::Rust, "let_declaration") => {
@@ -4204,6 +4235,7 @@ impl ParsedFile {
                 false,
                 receiver,
                 call_line,
+                call_start_byte,
                 found,
                 bindings,
                 recover_var,
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..b2beb16 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -68,6 +68,13 @@ pub struct CallSite {
     /// derived from the same scan as receiver_type.
     #[serde(default)]
     pub receiver_recovery: Option<crate::resolution::ReceiverRecovery>,
+    /// A local receiver binding was materialized for `qualifier` — true even
+    /// when `receiver_type` is None because the import/wildcard guard poisoned
+    /// the type. Proves the qualifier is a value, not a module/owner name:
+    /// suppresses R3/R3b for Python/JS/TS callers. Excluded from cmp_key —
+    /// derived from the same scan as receiver_type.
+    #[serde(default)]
+    pub receiver_materialized: bool,
     /// Number of arguments at the call site. `None` = not captured / unknown
     /// (the arity-disambiguation filter treats `None` as "keep").
     /// Excluded from cmp_key — positional data, not part of logical identity.
@@ -371,6 +378,7 @@ impl CallGraph {
                         ),
                         receiver_type: None,
                         receiver_recovery: None,
+                        receiver_materialized: false,
                         arg_count: None,
                         arg_spread: false,
                         receiver_outcome: None,
@@ -635,15 +643,17 @@ impl CallGraph {
                             line,
                             qualifier,
                         );
-                        let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                        let classified = classifier.classify(crate::resolution::ReceiverCtx {
                             receiver_expr,
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
                             call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
                         });
+                        let recovered = classified.recovered();
                         let site = CallSite {
                             caller: caller_id.clone(),
                             callee_name,
@@ -652,8 +662,9 @@ impl CallGraph {
                             start_byte,
                             end_byte,
                             qualifier,
-                            receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                            receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                            receiver_type: recovered.map(|r| r.static_type.clone()),
+                            receiver_recovery: recovered.map(|r| r.recovery),
+                            receiver_materialized: classified.materialized(),
                             arg_count,
                             arg_spread,
                             receiver_outcome: None,
@@ -737,6 +748,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -771,6 +783,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -858,6 +871,7 @@ impl CallGraph {
                                     qualifier: None,
                                     receiver_type: None,
                                     receiver_recovery: None,
+                                    receiver_materialized: false,
                                     arg_count: None,
                                     arg_spread: false,
                                     receiver_outcome: None,
@@ -955,6 +969,7 @@ impl CallGraph {
                                         qualifier: None,
                                         receiver_type: None,
                                         receiver_recovery: None,
+                                        receiver_materialized: false,
                                         arg_count: None,
                                         arg_spread: false,
                                         receiver_outcome: None,
@@ -982,6 +997,7 @@ impl CallGraph {
                                             qualifier: None,
                                             receiver_type: None,
                                             receiver_recovery: None,
+                                            receiver_materialized: false,
                                             arg_count: None,
                                             arg_spread: false,
                                             receiver_outcome: None,
@@ -1610,15 +1626,17 @@ impl CallGraph {
                         line,
                         qualifier,
                     );
-                    let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                    let classified = classifier.classify(crate::resolution::ReceiverCtx {
                         receiver_expr,
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
                         call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
                     });
+                    let recovered = classified.recovered();
                     let site = CallSite {
                         caller: caller_id.clone(),
                         callee_name: callee_name.clone(),
@@ -1627,8 +1645,9 @@ impl CallGraph {
                         start_byte,
                         end_byte,
                         qualifier,
-                        receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                        receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                        receiver_type: recovered.map(|r| r.static_type.clone()),
+                        receiver_recovery: recovered.map(|r| r.recovery),
+                        receiver_materialized: classified.materialized(),
                         arg_count,
                         arg_spread,
                         receiver_outcome: None,
diff --git a/src/cpg_cache.rs b/src/cpg_cache.rs
index 6effcc0..0883595 100644
--- a/src/cpg_cache.rs
+++ b/src/cpg_cache.rs
@@ -66,7 +66,9 @@ use std::path::{Path, PathBuf};
 /// - v22: method_class_span_ambiguous for fail-open line-id collisions.
 /// - v23: wrapper-canonical decorated extraction.
 /// - v24: Python/JS/TS typed-receiver recovery behavior.
-const CACHE_VERSION: u32 = 24; // 24: Python/JS/TS typed-receiver recovery behavior.
+/// - v25: materialized-receiver R3/R3b suppression (CallSite.receiver_materialized)
+///   + scope-aware Python/JS/TS binding recovery.
+const CACHE_VERSION: u32 = 25; // 25: materialized-receiver suppression + scope-aware recovery.
 
 pub const SKIP_POLICY_VERSION: u32 = 1;
 
@@ -571,9 +573,10 @@ mod tests {
     }
 
     #[test]
-    fn cache_version_is_24_for_python_js_typed_receiver_recovery() {
-        // v24: Python/JS/TS typed-receiver recovery changes resolution behavior.
-        assert_eq!(super::CACHE_VERSION, 24);
+    fn cache_version_is_25_for_materialized_receiver_suppression() {
+        // v25: materialized-receiver R3/R3b suppression + scope-aware recovery
+        // change CallSite contents and resolution behavior.
+        assert_eq!(super::CACHE_VERSION, 25);
     }
 
     #[test]
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..3b5f6f1 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -234,6 +234,39 @@ pub struct RecoveredReceiver {
     pub recovery: ReceiverRecovery,
 }
 
+/// Classifier verdict: "a local receiver BINDING was found for the qualifier"
+/// is a state distinct from "the receiver type resolved". A materialized
+/// binding (typed param / constructor local / annotated local) proves the
+/// qualifier is a value — never a module or owner name — so R3/R3b must not
+/// interpret it even when the type itself is import/wildcard-poisoned.
+#[derive(Debug, Clone, PartialEq, Eq)]
+pub enum ReceiverClassification {
+    /// No local receiver binding for the qualifier: the R3 (import) / R3b
+    /// (owner-key) interpretations stay live.
+    Unmaterialized,
+    /// Python/JS/TS only: a binding exists but the import/wildcard guard
+    /// poisoned the recovered type. Suppresses R3/R3b; the site routes to the
+    /// R6 residue (NameOnly/drop), never `owner_lookup`.
+    MaterializedPoisoned,
+    /// A binding exists and its type resolved: routes to R6 `owner_lookup`.
+    Recovered(RecoveredReceiver),
+}
+
+impl ReceiverClassification {
+    /// True when a local receiver binding was found, resolved or poisoned.
+    pub fn materialized(&self) -> bool {
+        !matches!(self, Self::Unmaterialized)
+    }
+
+    /// The recovered type, when one resolved unpoisoned.
+    pub fn recovered(&self) -> Option<&RecoveredReceiver> {
+        match self {
+            Self::Recovered(r) => Some(r),
+            _ => None,
+        }
+    }
+}
+
 /// Inputs a `ReceiverClassifier` needs to recover a receiver's static type. Borrows
 /// from the ParsedFile/tree of the call's enclosing function. Carries `recv_var` +
 /// `file_imports` because the legacy gate tests `is_recv`/`is_import`
@@ -249,6 +282,9 @@ pub struct ReceiverCtx<'a> {
     pub fn_node: tree_sitter::Node<'a>,
     /// 1-indexed call line.
     pub call_line: usize,
+    /// Start byte of the call expression (receiver included) — the byte-precise
+    /// "binding before call" cutoff for Python/JS/TS scope-aware recovery.
+    pub call_start_byte: usize,
     /// For node_text + the legacy `receiver_type_in_fn` scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
@@ -260,7 +296,7 @@ pub struct ReceiverCtx<'a> {
 /// Swappable receiver-recovery strategy (strangler seam, spec §2). `Sync` because
 /// the CPG build extracts call sites with rayon (`call_graph.rs` par_iter).
 pub trait ReceiverClassifier: Sync {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver>;
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification;
 }
 
 /// Receiver-recovery mode (spec §13.3). `Expanded` (default) turns the implemented
@@ -315,7 +351,7 @@ impl ReceiverRecoveryConfig {
 /// Runs the qualifier/keyword/recv-var/import gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
 /// is true), peeled + owner-keyed.
-fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<RecoveredReceiver> {
+fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverClassification {
     use crate::languages::Language;
     if !matches!(
         ctx.parsed.language,
@@ -326,30 +362,48 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
             | Language::TypeScript
             | Language::Tsx
     ) {
-        return None;
+        return ReceiverClassification::Unmaterialized;
     }
-    let q = ctx.qualifier?;
+    let Some(q) = ctx.qualifier else {
+        return ReceiverClassification::Unmaterialized;
+    };
     let simple = !q.is_empty() && q.chars().all(|c| c.is_alphanumeric() || c == '_');
     let is_kw = matches!(q, "self" | "this" | "cls");
     let is_recv = ctx.recv_var == Some(q);
     let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
-    if !(simple && !is_kw && !is_recv && !is_import) {
-        return None;
-    }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
-    let static_type = owner_key(&peel_type(&ty));
-    if matches!(
+    let scoped = matches!(
         ctx.parsed.language,
         Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
+    );
+    if !(simple && !is_kw && !is_recv) {
+        return ReceiverClassification::Unmaterialized;
+    }
+    // Rust/Go keep the import-name bail (byte-identical). For Python/JS/TS a
+    // local binding shadows a same-named import, so the scan must run first;
+    // only a scan miss leaves the import interpretation (R3) live.
+    if is_import && !scoped {
+        return ReceiverClassification::Unmaterialized;
+    }
+    let Some((ty, how)) = ctx.parsed.receiver_type_in_fn(
+        &ctx.fn_node,
+        q,
+        ctx.call_line,
+        ctx.call_start_byte,
+        recover_var,
+    ) else {
+        return ReceiverClassification::Unmaterialized;
+    };
+    let static_type = owner_key(&peel_type(&ty));
+    if scoped
+        && ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
     {
-        return None;
+        // The binding is real even though the type is poisoned: the qualifier
+        // is provably a value, so R3/R3b stay suppressed (residue routing).
+        return ReceiverClassification::MaterializedPoisoned;
     }
-    Some(RecoveredReceiver {
+    ReceiverClassification::Recovered(RecoveredReceiver {
         static_type,
         recovery: how,
     })
@@ -359,14 +413,14 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
 /// `call_graph::recover_receiver` (the qualifier/keyword/recv-var/import gate, then
 /// the typed-param / constructor-local scan, peeled + owner-keyed).
 /// Byte-identical to PR-1: `recover_var = false`.
-pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
+pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> ReceiverClassification {
     recover_simple_ident(ctx, false)
 }
 
 /// `legacy` — PR-1 behavior, no new forms.
 pub struct LegacyClassifier;
 impl ReceiverClassifier for LegacyClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification {
         legacy_recover(&ctx)
     }
 }
@@ -377,16 +431,17 @@ pub struct ExpandedClassifier {
     pub var_local: bool,
 }
 impl ReceiverClassifier for ExpandedClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
-        if let Some(r) = recover_simple_ident(&ctx, self.var_local) {
-            return Some(r);
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification {
+        let classified = recover_simple_ident(&ctx, self.var_local);
+        if classified.materialized() {
+            return classified;
         }
         if self.type_assertion {
             if let Some(r) = recover_type_assertion(&ctx) {
-                return Some(r);
+                return ReceiverClassification::Recovered(r);
             }
         }
-        None
+        ReceiverClassification::Unmaterialized
     }
 }
 
@@ -1007,6 +1062,10 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
+                // `receiver_materialized` covers the poisoned case: the
+                // import/wildcard guard skipped recovery (receiver_type is
+                // None) but the binding still proves the qualifier is a value,
+                // so R3/R3b stay suppressed — hit or miss, like the Rust shape.
                 let recovered_recv_materialized = matches!(
                     caller_lang,
                     Some(
@@ -1015,7 +1074,8 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && (site.receiver_type.is_some()
+                    || site.receiver_materialized);
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -2138,6 +2198,7 @@ mod scope_resolution_predicate_tests {
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
diff --git a/tests/lang/javascript/typed_receiver_test.rs b/tests/lang/javascript/typed_receiver_test.rs
index 695a64d..77616f3 100644
--- a/tests/lang/javascript/typed_receiver_test.rs
+++ b/tests/lang/javascript/typed_receiver_test.rs
@@ -40,3 +40,19 @@ fn test_javascript_new_constructor_recovers_bare_call_does_not() {
     assert_eq!(factory.receiver_type, None);
     assert!(cg.resolve_call_site(&factory).is_empty());
 }
+
+#[test]
+fn test_javascript_nested_class_body_binding_does_not_recover() {
+    // A class body is its own binding scope: an assignment inside a nested
+    // class's static block must not recover `x: Foo` for the call after it.
+    let cg = graph(
+        "class Foo { m() {} }\nfunction run() {\n  class C { static { x = new Foo(); } }\n  x.m();\n}\n",
+    );
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+    assert!(cg
+        .resolve_call_site(&s)
+        .iter()
+        .all(|c| c.kind != ResolutionKind::ConstructorLocal));
+}
diff --git a/tests/lang/python/typed_receiver_test.rs b/tests/lang/python/typed_receiver_test.rs
index ec612c4..4c5556b 100644
--- a/tests/lang/python/typed_receiver_test.rs
+++ b/tests/lang/python/typed_receiver_test.rs
@@ -89,6 +89,79 @@ fn test_python_shadow_import_wildcard_and_singleton_external_skip() {
     }
 }
 
+#[test]
+fn test_python_poisoned_typed_param_suppresses_r3b_owner_binding() {
+    // Import-poisoned `Foo` skips recovery, but the binding `x: Foo` still
+    // proves `x` is a value — R3b must not bind the receiver name to `class x`.
+    let poisoned = graph(&[(
+        "svc.py",
+        "from ext import Foo\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&poisoned, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(s.receiver_materialized);
+    let r = poisoned.resolve_call_site(&s);
+    assert!(r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner));
+    assert!(r
+        .iter()
+        .all(|c| c.confidence == ResolutionConfidence::NameOnly));
+
+    // Wildcard variant of the same poison: `from ext import *` leaves `Foo`
+    // unresolvable, but the binding still suppresses the R3b owner binding.
+    let wildcard = graph(&[(
+        "wild.py",
+        "from ext import *\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&wildcard, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(s.receiver_materialized);
+    let r = wildcard.resolve_call_site(&s);
+    assert!(r.iter().all(|c| c.kind != ResolutionKind::QualifierOwner));
+    assert!(r
+        .iter()
+        .all(|c| c.confidence == ResolutionConfidence::NameOnly));
+
+    // Positive control: same shape, no poisoning import — the recovered type
+    // still wins Exact TypedParam over the colliding `class x` owner key.
+    let control = graph(&[(
+        "ctl.py",
+        "class Foo:\n    def m(self):\n        pass\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&control, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    let r = control.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].target.start_line, 2);
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+}
+
+#[test]
+fn test_python_scope_aware_recovery_skips_class_body_and_after_call_bindings() {
+    // `C.x` is a class attribute in its own binding scope, not a local of
+    // `run` — it must not recover `x: Foo` for the call below the class.
+    let nested = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    class C:\n        x = Foo()\n    x.m()\n",
+    )]);
+    let s = site(&nested, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+    assert!(nested
+        .resolve_call_site(&s)
+        .iter()
+        .all(|c| c.kind != ResolutionKind::ConstructorLocal));
+
+    // A same-line binding AFTER the call is not "before the call".
+    let after = graph(&[(
+        "line.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    x.m(); x = Foo()\n",
+    )]);
+    let s = site(&after, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+}
+
 #[test]
 fn test_python_r3b_collision_and_local_miss_fallthrough() {
     let collision = graph(&[(
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 77b4b71..123f81c 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -1,14 +1,23 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionKind};
+use prism::resolution::{ReceiverRecovery, ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
 fn graph(src: &str) -> CallGraph {
-    let files = BTreeMap::from([(
-        "svc.ts".to_string(),
-        ParsedFile::parse("svc.ts", src, Language::TypeScript).expect("parse ts"),
-    )]);
+    graph_files(&[("svc.ts", src)])
+}
+
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
     CallGraph::build(&files)
 }
 
@@ -44,6 +53,44 @@ fn test_typescript_parameter_annotation_and_new_constructor_recover() {
     }
 }
 
+#[test]
+fn test_typescript_import_shadowing_typed_param_suppresses_import_qualified() {
+    // The param `api: Foo` shadows the `./api` import: `api.m()` is a method
+    // call on a Foo value, never an import-qualified free-function call.
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from \"./api\";\nclass Foo { m() {} }\nfunction run(api: Foo) { api.m(); }\n",
+        ),
+    ]);
+    let s = site(&cg, "run", "m");
+    let r = cg.resolve_call_site(&s);
+    assert!(r.iter().all(|c| c.kind != ResolutionKind::ImportQualified));
+    assert!(s.receiver_materialized);
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].target.file, "svc.ts");
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+
+    // Control: with no shadowing binding in scope, the import interpretation
+    // stays live — `api.m()` still resolves ImportQualified to ./api.
+    let unshadowed = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from \"./api\";\nfunction run() { api.m(); }\n",
+        ),
+    ]);
+    let s = site(&unshadowed, "run", "m");
+    assert!(!s.receiver_materialized);
+    let r = unshadowed.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].target.file, "api.ts");
+    assert_eq!(r[0].kind, ResolutionKind::ImportQualified);
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

## Arm B diff

```diff
diff --git a/src/ast.rs b/src/ast.rs
index 1656cef..b003ad7 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -407,18 +407,29 @@ impl ParsedFile {
     }
 
     /// S3 P6-lite: syntactically-provable receiver type for `receiver` at a call
-    /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
-    /// also recovers `var r T` declarations. Only bindings at or before `call_line`
-    /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// starting at `call_start_byte`. Typed params + constructor locals; when
+    /// `recover_var` is true also recovers `var r T` declarations. Only bindings
+    /// before the call start count; >1 binding before the call means shadow bail.
+    /// Rust + Go + guarded Python/JS/TS.
     /// Returns the raw, unpeeled type text + which fact recovered it.
     pub fn receiver_type_in_fn(
         &self,
         func_node: &Node<'_>,
         receiver: &str,
-        call_line: usize,
+        call_start_byte: usize,
         recover_var: bool,
     ) -> Option<(String, crate::resolution::ReceiverRecovery)> {
+        self.receiver_binding_in_fn(func_node, receiver, call_start_byte, recover_var)
+            .0
+    }
+
+    pub fn receiver_binding_in_fn(
+        &self,
+        func_node: &Node<'_>,
+        receiver: &str,
+        call_start_byte: usize,
+        recover_var: bool,
+    ) -> (Option<(String, crate::resolution::ReceiverRecovery)>, bool) {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
@@ -431,11 +442,12 @@ impl ParsedFile {
                 | Language::TypeScript
                 | Language::Tsx
         ) {
-            return None;
+            return (None, false);
         }
 
         let mut found: Option<(String, ReceiverRecovery)> = None;
         let mut bindings = 0usize;
+        let mut materialized = false;
 
         if let Some(params) = self.find_parameters_node(func_node) {
             let mut cursor = params.walk();
@@ -454,8 +466,10 @@ impl ParsedFile {
                                 ReceiverRecovery::TypedParam,
                             ));
                             bindings += 1;
+                            materialized = true;
                         } else if self.node_binds_name(pattern, receiver) {
                             bindings += 1;
+                            materialized = true;
                             found = None;
                         }
                     }
@@ -469,6 +483,7 @@ impl ParsedFile {
                                 ReceiverRecovery::TypedParam,
                             ));
                             bindings += 1;
+                            materialized = true;
                         }
                     }
                     Language::Python
@@ -486,6 +501,7 @@ impl ParsedFile {
                                 ReceiverRecovery::TypedParam,
                             ));
                             bindings += 1;
+                            materialized = true;
                         }
                     }
                     Language::TypeScript | Language::Tsx | Language::JavaScript
@@ -500,6 +516,7 @@ impl ParsedFile {
                                 ReceiverRecovery::TypedParam,
                             ));
                             bindings += 1;
+                            materialized = true;
                         }
                     }
                     _ => {}
@@ -511,15 +528,16 @@ impl ParsedFile {
             *func_node,
             true,
             receiver,
-            call_line,
+            call_start_byte,
             &mut found,
             &mut bindings,
+            &mut materialized,
             recover_var,
         );
         if bindings > 1 {
-            return None;
+            return (None, materialized);
         }
-        found
+        (found, materialized)
     }
 
     /// Manual recursive function collection (pre-query fallback).
@@ -4027,26 +4045,40 @@ impl ParsedFile {
         node: Node<'_>,
         is_root: bool,
         receiver: &str,
-        call_line: usize,
+        call_start_byte: usize,
         found: &mut Option<(String, crate::resolution::ReceiverRecovery)>,
         bindings: &mut usize,
+        materialized: &mut bool,
         recover_var: bool,
     ) {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        if node.start_byte() >= call_start_byte {
             return;
         }
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
+        if !is_root
+            && matches!(
+                self.language,
+                Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+            )
+            && matches!(
+                node.kind(),
+                "class_definition" | "class_declaration" | "class"
+            )
+        {
+            return;
+        }
 
         match (self.language, node.kind()) {
             (Language::Rust, "let_declaration") => {
                 if let Some(pattern) = node.child_by_field_name("pattern") {
                     if self.simple_binding_text(&pattern).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         if let Some(ty) = node.child_by_field_name("type") {
                             *found = Some((
                                 self.node_text(&ty).to_string(),
@@ -4061,6 +4093,7 @@ impl ParsedFile {
                         }
                     } else if self.node_binds_name(pattern, receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4075,6 +4108,7 @@ impl ParsedFile {
                 if let Some(left) = left {
                     if self.simple_binding_text(&left).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = right.and_then(|r| {
                             self.constructor_type(&r)
                                 .or_else(|| self.first_constructor_type_child(&r))
@@ -4082,6 +4116,7 @@ impl ParsedFile {
                         });
                     } else if self.node_binds_name(left, receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4096,6 +4131,7 @@ impl ParsedFile {
                     .any(|n| self.simple_binding_text(n).as_deref() == Some(receiver));
                 if matched {
                     *bindings += 1;
+                    *materialized = true;
                     if let Some(ty) = node.child_by_field_name("type") {
                         // `var r T` / `var a, b T` — the declared type applies to every name.
                         *found = Some((self.node_text(&ty).to_string(), ReceiverRecovery::VarDecl));
@@ -4120,6 +4156,7 @@ impl ParsedFile {
                 if let Some(left) = left {
                     if self.simple_binding_text(&left).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         if let Some(ty) = node.child_by_field_name("type") {
                             *found = Some((
                                 self.node_text(&ty).to_string(),
@@ -4134,6 +4171,7 @@ impl ParsedFile {
                         }
                     } else if self.node_binds_name(left, receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4146,6 +4184,7 @@ impl ParsedFile {
                 if let Some(name) = name {
                     if self.simple_binding_text(&name).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         if let Some(ty) = node.child_by_field_name("type") {
                             *found = Some((
                                 self.type_annotation_text(&ty),
@@ -4160,6 +4199,7 @@ impl ParsedFile {
                         }
                     } else if self.node_binds_name(name, receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4172,6 +4212,7 @@ impl ParsedFile {
                 if let Some(left) = left {
                     if self.simple_binding_text(&left).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = node
                             .child_by_field_name("right")
                             .or_else(|| node.child_by_field_name("value"))
@@ -4179,6 +4220,7 @@ impl ParsedFile {
                             .map(|ty| (ty, ReceiverRecovery::ConstructorLocal));
                     } else if self.node_binds_name(left, receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4190,6 +4232,7 @@ impl ParsedFile {
                 if let Some(left) = left {
                     if self.simple_binding_text(&left).as_deref() == Some(receiver) {
                         *bindings += 1;
+                        *materialized = true;
                         *found = None;
                     }
                 }
@@ -4203,9 +4246,10 @@ impl ParsedFile {
                 child,
                 false,
                 receiver,
-                call_line,
+                call_start_byte,
                 found,
                 bindings,
+                materialized,
                 recover_var,
             );
         }
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..1750e09 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -68,6 +68,10 @@ pub struct CallSite {
     /// derived from the same scan as receiver_type.
     #[serde(default)]
     pub receiver_recovery: Option<crate::resolution::ReceiverRecovery>,
+    /// True when a local receiver binding was found for the qualifier, even if
+    /// the static type was rejected as poisoned/unresolved.
+    #[serde(default)]
+    pub receiver_materialized: bool,
     /// Number of arguments at the call site. `None` = not captured / unknown
     /// (the arity-disambiguation filter treats `None` as "keep").
     /// Excluded from cmp_key — positional data, not part of logical identity.
@@ -371,6 +375,7 @@ impl CallGraph {
                         ),
                         receiver_type: None,
                         receiver_recovery: None,
+                        receiver_materialized: false,
                         arg_count: None,
                         arg_spread: false,
                         receiver_outcome: None,
@@ -635,11 +640,12 @@ impl CallGraph {
                             line,
                             qualifier,
                         );
-                        let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                        let classified = classifier.classify(crate::resolution::ReceiverCtx {
                             receiver_expr,
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
                             call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
@@ -652,8 +658,12 @@ impl CallGraph {
                             start_byte,
                             end_byte,
                             qualifier,
-                            receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                            receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                            receiver_type: classified
+                                .recovered
+                                .as_ref()
+                                .map(|r| r.static_type.clone()),
+                            receiver_recovery: classified.recovered.as_ref().map(|r| r.recovery),
+                            receiver_materialized: classified.materialized,
                             arg_count,
                             arg_spread,
                             receiver_outcome: None,
@@ -737,6 +747,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -771,6 +782,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -858,6 +870,7 @@ impl CallGraph {
                                     qualifier: None,
                                     receiver_type: None,
                                     receiver_recovery: None,
+                                    receiver_materialized: false,
                                     arg_count: None,
                                     arg_spread: false,
                                     receiver_outcome: None,
@@ -955,6 +968,7 @@ impl CallGraph {
                                         qualifier: None,
                                         receiver_type: None,
                                         receiver_recovery: None,
+                                        receiver_materialized: false,
                                         arg_count: None,
                                         arg_spread: false,
                                         receiver_outcome: None,
@@ -982,6 +996,7 @@ impl CallGraph {
                                             qualifier: None,
                                             receiver_type: None,
                                             receiver_recovery: None,
+                                            receiver_materialized: false,
                                             arg_count: None,
                                             arg_spread: false,
                                             receiver_outcome: None,
@@ -1610,11 +1625,12 @@ impl CallGraph {
                         line,
                         qualifier,
                     );
-                    let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                    let classified = classifier.classify(crate::resolution::ReceiverCtx {
                         receiver_expr,
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
                         call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
@@ -1627,8 +1643,9 @@ impl CallGraph {
                         start_byte,
                         end_byte,
                         qualifier,
-                        receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
-                        receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                        receiver_type: classified.recovered.as_ref().map(|r| r.static_type.clone()),
+                        receiver_recovery: classified.recovered.as_ref().map(|r| r.recovery),
+                        receiver_materialized: classified.materialized,
                         arg_count,
                         arg_spread,
                         receiver_outcome: None,
diff --git a/src/cpg_cache.rs b/src/cpg_cache.rs
index 6effcc0..591f440 100644
--- a/src/cpg_cache.rs
+++ b/src/cpg_cache.rs
@@ -66,7 +66,8 @@ use std::path::{Path, PathBuf};
 /// - v22: method_class_span_ambiguous for fail-open line-id collisions.
 /// - v23: wrapper-canonical decorated extraction.
 /// - v24: Python/JS/TS typed-receiver recovery behavior.
-const CACHE_VERSION: u32 = 24; // 24: Python/JS/TS typed-receiver recovery behavior.
+/// - v25: CallSite.receiver_materialized for poisoned Python/JS/TS receivers.
+const CACHE_VERSION: u32 = 25; // 25: CallSite.receiver_materialized.
 
 pub const SKIP_POLICY_VERSION: u32 = 1;
 
@@ -571,9 +572,9 @@ mod tests {
     }
 
     #[test]
-    fn cache_version_is_24_for_python_js_typed_receiver_recovery() {
-        // v24: Python/JS/TS typed-receiver recovery changes resolution behavior.
-        assert_eq!(super::CACHE_VERSION, 24);
+    fn cache_version_is_25_for_receiver_materialization() {
+        // v25: CallSite.receiver_materialized changes serialized CallGraph shape.
+        assert_eq!(super::CACHE_VERSION, 25);
     }
 
     #[test]
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..792c97d 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -234,6 +234,34 @@ pub struct RecoveredReceiver {
     pub recovery: ReceiverRecovery,
 }
 
+/// Receiver classification separates "a local receiver binding exists" from
+/// "that binding's type is accepted for owner lookup".
+#[derive(Debug, Clone, PartialEq, Eq, Default)]
+pub struct ReceiverClassification {
+    pub recovered: Option<RecoveredReceiver>,
+    pub materialized: bool,
+}
+
+impl ReceiverClassification {
+    fn none() -> Self {
+        Self::default()
+    }
+
+    fn materialized_without_type() -> Self {
+        Self {
+            recovered: None,
+            materialized: true,
+        }
+    }
+
+    fn recovered(recovered: RecoveredReceiver) -> Self {
+        Self {
+            recovered: Some(recovered),
+            materialized: true,
+        }
+    }
+}
+
 /// Inputs a `ReceiverClassifier` needs to recover a receiver's static type. Borrows
 /// from the ParsedFile/tree of the call's enclosing function. Carries `recv_var` +
 /// `file_imports` because the legacy gate tests `is_recv`/`is_import`
@@ -249,7 +277,9 @@ pub struct ReceiverCtx<'a> {
     pub fn_node: tree_sitter::Node<'a>,
     /// 1-indexed call line.
     pub call_line: usize,
-    /// For node_text + the legacy `receiver_type_in_fn` scan.
+    /// Start byte of the method call expression.
+    pub call_start_byte: usize,
+    /// For node_text + the receiver binding scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
     pub recv_var: Option<&'a str>,
@@ -260,7 +290,7 @@ pub struct ReceiverCtx<'a> {
 /// Swappable receiver-recovery strategy (strangler seam, spec §2). `Sync` because
 /// the CPG build extracts call sites with rayon (`call_graph.rs` par_iter).
 pub trait ReceiverClassifier: Sync {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver>;
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification;
 }
 
 /// Receiver-recovery mode (spec §13.3). `Expanded` (default) turns the implemented
@@ -315,7 +345,7 @@ impl ReceiverRecoveryConfig {
 /// Runs the qualifier/keyword/recv-var/import gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
 /// is true), peeled + owner-keyed.
-fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<RecoveredReceiver> {
+fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverClassification {
     use crate::languages::Language;
     if !matches!(
         ctx.parsed.language,
@@ -326,30 +356,44 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
             | Language::TypeScript
             | Language::Tsx
     ) {
-        return None;
+        return ReceiverClassification::none();
     }
-    let q = ctx.qualifier?;
+    let Some(q) = ctx.qualifier else {
+        return ReceiverClassification::none();
+    };
+    let py_js_ts = matches!(
+        ctx.parsed.language,
+        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+    );
     let simple = !q.is_empty() && q.chars().all(|c| c.is_alphanumeric() || c == '_');
     let is_kw = matches!(q, "self" | "this" | "cls");
     let is_recv = ctx.recv_var == Some(q);
     let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
-    if !(simple && !is_kw && !is_recv && !is_import) {
-        return None;
-    }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
+    if !(simple && !is_kw && !is_recv) {
+        return ReceiverClassification::none();
+    }
+    if is_import && !py_js_ts {
+        return ReceiverClassification::none();
+    }
+    let (recovered, materialized) =
+        ctx.parsed
+            .receiver_binding_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var);
+    let Some((ty, how)) = recovered else {
+        return if materialized {
+            ReceiverClassification::materialized_without_type()
+        } else {
+            ReceiverClassification::none()
+        };
+    };
     let static_type = owner_key(&peel_type(&ty));
-    if matches!(
-        ctx.parsed.language,
-        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
+    if py_js_ts
+        && ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
     {
-        return None;
+        return ReceiverClassification::materialized_without_type();
     }
-    Some(RecoveredReceiver {
+    ReceiverClassification::recovered(RecoveredReceiver {
         static_type,
         recovery: how,
     })
@@ -360,14 +404,14 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
 /// the typed-param / constructor-local scan, peeled + owner-keyed).
 /// Byte-identical to PR-1: `recover_var = false`.
 pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
-    recover_simple_ident(ctx, false)
+    recover_simple_ident(ctx, false).recovered
 }
 
 /// `legacy` — PR-1 behavior, no new forms.
 pub struct LegacyClassifier;
 impl ReceiverClassifier for LegacyClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
-        legacy_recover(&ctx)
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification {
+        recover_simple_ident(&ctx, false)
     }
 }
 
@@ -377,16 +421,17 @@ pub struct ExpandedClassifier {
     pub var_local: bool,
 }
 impl ReceiverClassifier for ExpandedClassifier {
-    fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
-        if let Some(r) = recover_simple_ident(&ctx, self.var_local) {
-            return Some(r);
+    fn classify(&self, ctx: ReceiverCtx<'_>) -> ReceiverClassification {
+        let simple = recover_simple_ident(&ctx, self.var_local);
+        if simple.materialized {
+            return simple;
         }
         if self.type_assertion {
             if let Some(r) = recover_type_assertion(&ctx) {
-                return Some(r);
+                return ReceiverClassification::recovered(r);
             }
         }
-        None
+        ReceiverClassification::none()
     }
 }
 
@@ -1015,7 +1060,7 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && site.receiver_materialized;
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -2110,6 +2155,157 @@ mod self_receiver_same_class_tests {
     }
 }
 
+#[cfg(test)]
+mod py_js_receiver_materialization_tests {
+    use super::*;
+    use crate::ast::ParsedFile;
+    use crate::languages::Language;
+    use std::collections::BTreeMap;
+
+    fn files(pairs: &[(&str, &str)]) -> BTreeMap<String, ParsedFile> {
+        pairs
+            .iter()
+            .map(|(p, s)| {
+                let lang = Language::from_path(p).expect("known extension");
+                (
+                    (*p).to_string(),
+                    ParsedFile::parse(p, s, lang).expect("parse"),
+                )
+            })
+            .collect()
+    }
+
+    fn site<'a>(cg: &'a CallGraph, caller_file: &str, caller: &str, callee: &str) -> &'a CallSite {
+        let caller = cg
+            .functions
+            .get(caller)
+            .and_then(|v| v.iter().find(|f| f.file == caller_file))
+            .expect("caller fn");
+        cg.calls
+            .get(caller)
+            .and_then(|sites| sites.iter().find(|s| s.callee_name == callee))
+            .expect("call site")
+    }
+
+    fn out<'a>(
+        cg: &'a CallGraph,
+        caller_file: &str,
+        caller: &str,
+        callee: &str,
+    ) -> ResolutionOutcome<'a> {
+        cg.resolve_call_site_full(site(cg, caller_file, caller, callee))
+    }
+
+    fn has_exact_kind(out: &ResolutionOutcome<'_>, kind: ResolutionKind, file: &str) -> bool {
+        out.resolved.iter().any(|r| {
+            r.confidence == ResolutionConfidence::Exact && r.kind == kind && r.target.file == file
+        })
+    }
+
+    #[test]
+    fn python_import_poisoned_typed_param_suppresses_qualifier_owner() {
+        let cg = CallGraph::build(&files(&[(
+            "a.py",
+            "from ext import Foo\n\
+             class x:\n\
+             \tdef m(self):\n\
+             \t\treturn 1\n\
+             def run(x: Foo):\n\
+             \treturn x.m()\n",
+        )]));
+
+        let resolved = out(&cg, "a.py", "run", "m");
+        assert!(
+            !has_exact_kind(&resolved, ResolutionKind::QualifierOwner, "a.py"),
+            "typed local receiver x: imported Foo must not bind to class x.m: {resolved:?}"
+        );
+    }
+
+    #[test]
+    fn typescript_import_shadowed_typed_param_suppresses_import_qualified() {
+        let cg = CallGraph::build(&files(&[
+            (
+                "main.ts",
+                "import api from './api';\n\
+                 class Foo { m() { return 1; } }\n\
+                 function run(api: Foo) { return api.m(); }\n",
+            ),
+            ("api.ts", "export function m() { return 2; }\n"),
+        ]));
+
+        let resolved = out(&cg, "main.ts", "run", "m");
+        assert!(
+            !has_exact_kind(&resolved, ResolutionKind::ImportQualified, "api.ts"),
+            "typed local receiver api: Foo must not bind to imported api.m: {resolved:?}"
+        );
+        assert!(
+            has_exact_kind(&resolved, ResolutionKind::TypedParam, "main.ts"),
+            "non-poisoned local type should still resolve through R6 TypedParam: {resolved:?}"
+        );
+    }
+
+    #[test]
+    fn python_nested_class_body_assignment_is_not_local_receiver_binding() {
+        let cg = CallGraph::build(&files(&[(
+            "a.py",
+            "class Foo:\n\
+             \tdef m(self):\n\
+             \t\treturn 1\n\
+             def run():\n\
+             \tclass C:\n\
+             \t\tx = Foo()\n\
+             \treturn x.m()\n",
+        )]));
+
+        let call = site(&cg, "a.py", "run", "m");
+        assert_eq!(
+            call.receiver_type, None,
+            "class-body C.x must not recover as run()'s local receiver"
+        );
+        let resolved = cg.resolve_call_site_full(call);
+        assert!(
+            !has_exact_kind(&resolved, ResolutionKind::ConstructorLocal, "a.py"),
+            "class-body C.x must not produce an Exact constructor-local receiver edge: {resolved:?}"
+        );
+    }
+
+    #[test]
+    fn python_same_line_after_call_assignment_is_not_before_call_binding() {
+        let cg = CallGraph::build(&files(&[(
+            "a.py",
+            "class Foo:\n\
+             \tdef m(self):\n\
+             \t\treturn 1\n\
+             def run():\n\
+             \tx.m(); x = Foo()\n",
+        )]));
+
+        let call = site(&cg, "a.py", "run", "m");
+        assert_eq!(
+            call.receiver_type, None,
+            "assignment after the call start byte must not count as prior receiver binding"
+        );
+    }
+
+    #[test]
+    fn python_non_poisoned_typed_param_still_resolves_exact_typed_param() {
+        let cg = CallGraph::build(&files(&[(
+            "a.py",
+            "class Foo:\n\
+             \tdef m(self):\n\
+             \t\treturn 1\n\
+             def run(x: Foo):\n\
+             \treturn x.m()\n",
+        )]));
+
+        let resolved = out(&cg, "a.py", "run", "m");
+        assert!(
+            has_exact_kind(&resolved, ResolutionKind::TypedParam, "a.py"),
+            "ordinary local typed param recovery regressed: {resolved:?}"
+        );
+    }
+}
+
 #[cfg(test)]
 mod scope_resolution_predicate_tests {
     use super::*;
@@ -2138,6 +2334,7 @@ mod scope_resolution_predicate_tests {
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
