# Blind pairwise code-review judgment — DBGF-DBG-02-sonnet-d2

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
index 1656cef..9748fd0 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -407,16 +407,18 @@ impl ParsedFile {
     }
 
     /// S3 P6-lite: syntactically-provable receiver type for `receiver` at a call
-    /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
-    /// also recovers `var r T` declarations. Only bindings at or before `call_line`
-    /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// starting at `call_start_byte`. Typed params + constructor locals; when
+    /// `recover_var` is true also recovers `var r T` declarations. Only bindings
+    /// whose start byte is strictly before `call_start_byte` count (MAJOR
+    /// scope-aware-recovery fix: byte-precise, not line-precise, so a same-line
+    /// binding AFTER the call is never mistaken for one before it); >1 binding
+    /// before the call means shadow bail. Rust + Go + guarded Python/JS/TS.
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
@@ -511,7 +513,7 @@ impl ParsedFile {
             *func_node,
             true,
             receiver,
-            call_line,
+            call_start_byte,
             &mut found,
             &mut bindings,
             recover_var,
@@ -4027,7 +4029,7 @@ impl ParsedFile {
         node: Node<'_>,
         is_root: bool,
         receiver: &str,
-        call_line: usize,
+        call_start_byte: usize,
         found: &mut Option<(String, crate::resolution::ReceiverRecovery)>,
         bindings: &mut usize,
         recover_var: bool,
@@ -4035,12 +4037,32 @@ impl ParsedFile {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        // MAJOR scope-aware-recovery fix: byte-precise "before the call" cutoff.
+        // A line-precise cutoff can't distinguish a same-line binding BEFORE the
+        // call from one AFTER it (`x.m(); x = Foo()`) — the latter must not
+        // count as a binding for the call's receiver.
+        if node.start_byte() >= call_start_byte {
             return;
         }
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
+        // MAJOR scope-aware-recovery fix: a NESTED class body is its OWN
+        // binding scope (Python/JS) — an assignment inside it (`class C: x =
+        // Foo()`) defines an attribute of that class, not a local of the
+        // enclosing function, so never descend into one.
+        if !is_root
+            && matches!(
+                (self.language, node.kind()),
+                (Language::Python, "class_definition")
+                    | (
+                        Language::JavaScript | Language::TypeScript | Language::Tsx,
+                        "class_declaration" | "class"
+                    )
+            )
+        {
+            return;
+        }
 
         match (self.language, node.kind()) {
             (Language::Rust, "let_declaration") => {
@@ -4203,7 +4225,7 @@ impl ParsedFile {
                 child,
                 false,
                 receiver,
-                call_line,
+                call_start_byte,
                 found,
                 bindings,
                 recover_var,
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..1856a2e 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -639,7 +639,7 @@ impl CallGraph {
                             receiver_expr,
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
-                            call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
@@ -652,7 +652,10 @@ impl CallGraph {
                             start_byte,
                             end_byte,
                             qualifier,
-                            receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
+                            receiver_type: recovered
+                                .as_ref()
+                                .filter(|r| !r.poisoned)
+                                .map(|r| r.static_type.clone()),
                             receiver_recovery: recovered.as_ref().map(|r| r.recovery),
                             arg_count,
                             arg_spread,
@@ -1614,7 +1617,7 @@ impl CallGraph {
                         receiver_expr,
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
-                        call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
@@ -1627,7 +1630,10 @@ impl CallGraph {
                         start_byte,
                         end_byte,
                         qualifier,
-                        receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
+                        receiver_type: recovered
+                            .as_ref()
+                            .filter(|r| !r.poisoned)
+                            .map(|r| r.static_type.clone()),
                         receiver_recovery: recovered.as_ref().map(|r| r.recovery),
                         arg_count,
                         arg_spread,
diff --git a/src/cpg_cache.rs b/src/cpg_cache.rs
index 6effcc0..444395f 100644
--- a/src/cpg_cache.rs
+++ b/src/cpg_cache.rs
@@ -66,7 +66,8 @@ use std::path::{Path, PathBuf};
 /// - v22: method_class_span_ambiguous for fail-open line-id collisions.
 /// - v23: wrapper-canonical decorated extraction.
 /// - v24: Python/JS/TS typed-receiver recovery behavior.
-const CACHE_VERSION: u32 = 24; // 24: Python/JS/TS typed-receiver recovery behavior.
+/// - v25: materialized-vs-poisoned R3/R3b pre-emption + byte-precise/scope-aware recovery.
+const CACHE_VERSION: u32 = 25; // 25: R3/R3b materialized-vs-poisoned fix + scope-aware recovery.
 
 pub const SKIP_POLICY_VERSION: u32 = 1;
 
@@ -571,9 +572,11 @@ mod tests {
     }
 
     #[test]
-    fn cache_version_is_24_for_python_js_typed_receiver_recovery() {
-        // v24: Python/JS/TS typed-receiver recovery changes resolution behavior.
-        assert_eq!(super::CACHE_VERSION, 24);
+    fn cache_version_is_25_for_typed_receiver_recovery_r3_r3b_scope_fix() {
+        // v25: slice-2 BLOCKER1+2 (materialized-vs-poisoned R3/R3b pre-emption)
+        // + MAJOR (byte-precise/scope-aware recovery) change resolution
+        // behavior for cached Python/JS/TS call sites.
+        assert_eq!(super::CACHE_VERSION, 25);
     }
 
     #[test]
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..61d918e 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -232,6 +232,17 @@ pub enum ReceiverRecovery {
 pub struct RecoveredReceiver {
     pub static_type: String,
     pub recovery: ReceiverRecovery,
+    /// Slice-2 BLOCKER1+2 fix: `true` when a Python/JS/TS local receiver
+    /// binding MATERIALIZED (typed param / constructor local / annotation) but
+    /// its peeled `static_type` is import-bound or the file has a wildcard
+    /// import (spec §3.2.1/§3.3) — the type is provably external/ambiguous, so
+    /// `static_type` must NOT drive `owner_lookup` (a same-named in-repo class
+    /// could be unrelated). Callers gate `CallSite.receiver_type` on
+    /// `!poisoned` for that reason; `receiver_recovery` is still set, which is
+    /// exactly the distinct "materialized" signal R3/R3b pre-emption needs —
+    /// the receiver is provably a value, not an owner/module, even though its
+    /// exact type isn't routable. Always `false` for Rust/Go.
+    pub poisoned: bool,
 }
 
 /// Inputs a `ReceiverClassifier` needs to recover a receiver's static type. Borrows
@@ -247,8 +258,10 @@ pub struct ReceiverCtx<'a> {
     pub qualifier: Option<&'a str>,
     /// Enclosing function node.
     pub fn_node: tree_sitter::Node<'a>,
-    /// 1-indexed call line.
-    pub call_line: usize,
+    /// Byte offset of the call's start — the scope-aware "binding before call"
+    /// cutoff (MAJOR fix: byte-precise, not line-precise, so a same-line
+    /// binding AFTER the call is never mistaken for one before it).
+    pub call_start_byte: usize,
     /// For node_text + the legacy `receiver_type_in_fn` scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
@@ -315,6 +328,20 @@ impl ReceiverRecoveryConfig {
 /// Runs the qualifier/keyword/recv-var/import gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
 /// is true), peeled + owner-keyed.
+///
+/// Rust/Go: BYTE-IDENTICAL original order — `is_import(q)` on the QUALIFIER
+/// gates BEFORE the scan runs (a package-qualified call is never a receiver
+/// scan candidate for these languages).
+///
+/// Python/JS/TS (BLOCKER1+2 fix): gating on `is_import(q)` before scanning is
+/// scope-blind — a local typed-param/constructor-local binding for `q` can
+/// SHADOW a same-named import (`import api from "./api"` + `function
+/// run(api: Foo) { api.m() }`), so bailing before the scan wrongly treats the
+/// shadowing param as the import. Scan FIRST; only the RECOVERED TYPE NAME
+/// (not `q`) is checked against imports/wildcard (§3.3). A MATERIALIZED
+/// binding whose type fails that check (`poisoned: true`) still signals "this
+/// qualifier is a value, not a module/owner" — callers use it to pre-empt
+/// R3/R3b even though the type itself does not drive `owner_lookup`.
 fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<RecoveredReceiver> {
     use crate::languages::Language;
     if !matches!(
@@ -331,27 +358,46 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
     let q = ctx.qualifier?;
     let simple = !q.is_empty() && q.chars().all(|c| c.is_alphanumeric() || c == '_');
     let is_kw = matches!(q, "self" | "this" | "cls");
-    let is_recv = ctx.recv_var == Some(q);
-    let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
-    if !(simple && !is_kw && !is_recv && !is_import) {
+    if !simple || is_kw {
         return None;
     }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
-    let static_type = owner_key(&peel_type(&ty));
-    if matches!(
+    let is_recv = ctx.recv_var == Some(q);
+
+    let scope_aware = matches!(
         ctx.parsed.language,
         Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
-    {
+    );
+
+    if !scope_aware {
+        let is_import = ctx.file_imports.map(|m| m.contains_key(q)).unwrap_or(false);
+        if is_recv || is_import {
+            return None;
+        }
+        let (ty, how) =
+            ctx.parsed
+                .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var)?;
+        let static_type = owner_key(&peel_type(&ty));
+        return Some(RecoveredReceiver {
+            static_type,
+            recovery: how,
+            poisoned: false,
+        });
+    }
+
+    if is_recv {
         return None;
     }
+    let (ty, how) =
+        ctx.parsed
+            .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var)?;
+    let static_type = owner_key(&peel_type(&ty));
+    let poisoned = ctx
+        .file_imports
+        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"));
     Some(RecoveredReceiver {
         static_type,
         recovery: how,
+        poisoned,
     })
 }
 
@@ -430,6 +476,7 @@ fn recover_type_assertion(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
     Some(RecoveredReceiver {
         static_type,
         recovery: ReceiverRecovery::TypeAssertion,
+        poisoned: false,
     })
 }
 
@@ -1007,6 +1054,14 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
+                // BLOCKER1+2 fix: a Python/JS/TS receiver binding MATERIALIZES
+                // (mirrors `rust_recv_materialized` — suppresses on materialize,
+                // hit OR miss) whenever `receiver_type` resolved OR
+                // `receiver_recovery` is set. The latter alone (`receiver_type`
+                // withheld) is exactly the "materialized but poisoned"
+                // (imported/wildcard) case §3.2.1/§3.3 — the receiver is
+                // provably a value, not an owner/module, even though its type
+                // isn't routable, so R3/R3b must still be pre-empted.
                 let recovered_recv_materialized = matches!(
                     caller_lang,
                     Some(
@@ -1015,7 +1070,8 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && (site.receiver_type.is_some()
+                    || site.receiver_recovery.is_some());
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
diff --git a/tests/lang/javascript/typed_receiver_test.rs b/tests/lang/javascript/typed_receiver_test.rs
index 695a64d..fd189ee 100644
--- a/tests/lang/javascript/typed_receiver_test.rs
+++ b/tests/lang/javascript/typed_receiver_test.rs
@@ -40,3 +40,12 @@ fn test_javascript_new_constructor_recovers_bare_call_does_not() {
     assert_eq!(factory.receiver_type, None);
     assert!(cg.resolve_call_site(&factory).is_empty());
 }
+
+// MAJOR (scope-aware recovery): `x = new Foo()` on the SAME LINE as `x.m()`
+// but AFTER it (byte-wise) must not be treated as a binding "before" the call.
+#[test]
+fn test_javascript_same_line_after_call_assignment_not_recovered() {
+    let cg = graph("class Foo { m() {} }\nfunction run() { x.m(); x = new Foo(); }\n");
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
diff --git a/tests/lang/python/typed_receiver_test.rs b/tests/lang/python/typed_receiver_test.rs
index ec612c4..5c290a9 100644
--- a/tests/lang/python/typed_receiver_test.rs
+++ b/tests/lang/python/typed_receiver_test.rs
@@ -89,6 +89,34 @@ fn test_python_shadow_import_wildcard_and_singleton_external_skip() {
     }
 }
 
+// BLOCKER1+2 (unified): a MATERIALIZED receiver binding must suppress R3b even
+// when the type is poisoned (imported). `Foo` is imported (poisoned) so the
+// import/wildcard guard withholds `receiver_type`; but the qualifier `x` ALSO
+// collides with a same-named LOCAL class `x` that defines `m`. Before the fix,
+// `receiver_type.is_none()` made `recv_materialized` false, so R3b bound `x.m()`
+// Exact `qualifier_owner` to `class x.m` — wrong, since `x` is provably a `Foo`
+// (a value), not the class `x` (an owner/module). After the fix, R3b must still
+// be suppressed; residue may NameOnly-bind `x.m` (§3.2 miss-fallthrough) but
+// must never Exact-bind via `qualifier_owner`.
+#[test]
+fn test_python_poisoned_type_still_suppresses_r3b_collision() {
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import Foo\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    // The poison guard (§3.3) must still withhold `receiver_type` (Foo is imported).
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    // The MATERIALIZED (but poisoned) binding must suppress R3b: no Exact
+    // `qualifier_owner` binding to the same-named local class `x`.
+    assert!(
+        r.iter()
+            .all(|c| c.confidence != ResolutionConfidence::Exact),
+        "{r:?}"
+    );
+}
+
 #[test]
 fn test_python_r3b_collision_and_local_miss_fallthrough() {
     let collision = graph(&[(
@@ -115,3 +143,62 @@ fn test_python_r3b_collision_and_local_miss_fallthrough() {
     assert_eq!(annotated_out.drop, plain_out.drop);
     assert_ne!(annotated_out.drop, Some(DropReason::ExternalReceiver));
 }
+
+// MAJOR (scope-aware recovery): a NESTED class body is its OWN binding scope —
+// `x = Foo()` inside `class C` (nested in `run`) defines a class ATTRIBUTE of
+// `C`, not a local of `run`. The line-based scan is not scope-aware and
+// wrongly recovers it as `run`'s `x`.
+#[test]
+fn test_python_nested_class_body_assignment_not_recovered() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    class C:\n        x = Foo()\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
+
+// MAJOR (scope-aware recovery): `x = Foo()` on the SAME LINE as `x.m()` but
+// AFTER it (byte-wise) must not be treated as a binding "before" the call —
+// line-level granularity can't distinguish same-line-before from
+// same-line-after.
+#[test]
+fn test_python_same_line_after_call_assignment_not_recovered() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    x.m(); x = Foo()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
+
+// Positive control (edge case for the byte cutoff): a binding on the SAME
+// LINE as the call but BEFORE it (byte-wise) must still recover — the `>=`
+// cutoff must reject only same-line-AFTER, not same-line-before.
+#[test]
+fn test_python_same_line_before_call_assignment_still_recovers() {
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    x = Foo(); x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+}
+
+// Negative/edge case for the BLOCKER1+2 restructure: a GENUINE import
+// qualifier with NO local shadowing binding (no param/local named `utils` in
+// `run`) must still resolve via R3 `import_qualified` — scanning first for a
+// local binding must not disable R3 outright for Python when there is no
+// local binding to find.
+#[test]
+fn test_python_plain_import_qualifier_still_resolves_r3() {
+    let cg = graph(&[
+        ("utils.py", "def process():\n    pass\n"),
+        ("svc.py", "import utils\ndef run():\n    utils.process()\n"),
+    ]);
+    let s = site(&cg, "run", "process");
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1, "{r:?}");
+    assert_eq!(r[0].kind, ResolutionKind::ImportQualified);
+}
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 77b4b71..779044c 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -53,3 +53,68 @@ fn test_typescript_bare_factory_call_does_not_recover() {
     assert_eq!(s.receiver_type, None);
     assert!(cg.resolve_call_site(&s).is_empty());
 }
+
+// BLOCKER1+2 (unified): a MATERIALIZED receiver binding must suppress R3 even
+// when the qualifier text collides with an IMPORT alias. `api` is both an
+// import (`import api from "./api"`) AND a locally-typed parameter shadowing
+// it (`function run(api: Foo)`). Before the fix, the qualifier-import gate
+// (`is_import(q)`) bailed BEFORE scanning for a local binding, so `api.m()`
+// bound Exact `import_qualified` to `./api` — wrong, `api` is the `Foo` param,
+// not the module. After the fix, the local binding must be recovered (it is
+// NOT poisoned — `Foo` is a local class) and drive resolution via R6.
+#[test]
+fn test_typescript_local_param_shadows_import_suppresses_r3() {
+    let files = BTreeMap::from([
+        (
+            "api.ts".to_string(),
+            ParsedFile::parse("api.ts", "export function m() {}\n", Language::TypeScript)
+                .expect("parse api.ts"),
+        ),
+        (
+            "svc.ts".to_string(),
+            ParsedFile::parse(
+                "svc.ts",
+                "import api from \"./api\";\nclass Foo { m() {} }\nfunction run(api: Foo) { api.m(); }\n",
+                Language::TypeScript,
+            )
+            .expect("parse svc.ts"),
+        ),
+    ]);
+    let cg = CallGraph::build(&files);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+    assert_eq!(s.receiver_recovery, Some(ReceiverRecovery::TypedParam));
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1, "{r:?}");
+    assert_eq!(r[0].kind, ResolutionKind::TypedParam);
+}
+
+// Negative/edge case for the BLOCKER1+2 restructure: a GENUINE import
+// qualifier with NO local shadowing binding (no param named `api` in `run`)
+// must still resolve via R3 `import_qualified` — scanning first for a local
+// binding must not disable R3 outright when there is no local binding to find.
+#[test]
+fn test_typescript_plain_import_qualifier_no_shadow_still_resolves_r3() {
+    let files = BTreeMap::from([
+        (
+            "api.ts".to_string(),
+            ParsedFile::parse("api.ts", "export function m() {}\n", Language::TypeScript)
+                .expect("parse api.ts"),
+        ),
+        (
+            "svc.ts".to_string(),
+            ParsedFile::parse(
+                "svc.ts",
+                "import api from \"./api\";\nfunction run() { api.m(); }\n",
+                Language::TypeScript,
+            )
+            .expect("parse svc.ts"),
+        ),
+    ]);
+    let cg = CallGraph::build(&files);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1, "{r:?}");
+    assert_eq!(r[0].kind, ResolutionKind::ImportQualified);
+}

```

## Arm B diff

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
