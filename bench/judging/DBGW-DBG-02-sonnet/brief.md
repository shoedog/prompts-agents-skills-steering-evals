# Blind pairwise code-review judgment — DBGW-DBG-02-sonnet

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
index 1656cef..f5bf7ac 100644
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
+    /// strictly before the call's start byte count (byte, not line, so a same-line
+    /// binding written after the call is correctly excluded); >1 binding before the
+    /// call means shadow bail. Rust + Go + guarded Python/JS/TS.
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
@@ -4035,10 +4036,16 @@ impl ParsedFile {
         use crate::languages::Language;
         use crate::resolution::ReceiverRecovery;
 
-        if node.start_position().row + 1 > call_line {
+        // Byte, not line: a same-line binding written AFTER the call (e.g.
+        // `x.m(); x = Foo()`) must not count as "before" it — line comparison alone
+        // can't see order within one line.
+        if node.start_byte() >= call_start_byte {
             return;
         }
-        if !is_root && self.language.function_node_types().contains(&node.kind()) {
+        if !is_root
+            && (self.language.function_node_types().contains(&node.kind())
+                || self.is_nested_class_scope(&node))
+        {
             return;
         }
 
@@ -4203,7 +4210,7 @@ impl ParsedFile {
                 child,
                 false,
                 receiver,
-                call_line,
+                call_start_byte,
                 found,
                 bindings,
                 recover_var,
@@ -4211,6 +4218,23 @@ impl ParsedFile {
         }
     }
 
+    /// True for a nested class scope root (Python `class_definition`; JS/TS/Tsx
+    /// `class_declaration`/`class` expression). Class bodies are their own binding
+    /// scope — an attribute assignment there (e.g. `class C: x = Foo()`) is `C.x`,
+    /// never a local of the function the class happens to be nested in, so
+    /// `walk_receiver_bindings` must not descend into one.
+    fn is_nested_class_scope(&self, node: &Node<'_>) -> bool {
+        use crate::languages::Language;
+        matches!(
+            (self.language, node.kind()),
+            (Language::Python, "class_definition")
+                | (
+                    Language::JavaScript | Language::TypeScript | Language::Tsx,
+                    "class_declaration" | "class"
+                )
+        )
+    }
+
     fn constructor_type(&self, node: &Node<'_>) -> Option<String> {
         use crate::languages::Language;
 
diff --git a/src/call_graph.rs b/src/call_graph.rs
index 05faf2d..f12d8f1 100644
--- a/src/call_graph.rs
+++ b/src/call_graph.rs
@@ -68,6 +68,15 @@ pub struct CallSite {
     /// derived from the same scan as receiver_type.
     #[serde(default)]
     pub receiver_recovery: Option<crate::resolution::ReceiverRecovery>,
+    /// Slice-2 BLOCKER fix: true when a local receiver binding (typed param /
+    /// constructor local / annotated local) was found for the qualifier at
+    /// extraction time, independent of whether `receiver_type` ended up poisoned
+    /// (import/wildcard guard) or unset (import-shadowed qualifier name). Drives the
+    /// R3/R3b pre-emption in `resolve_call_site_full` — a materialized-but-poisoned
+    /// receiver is still provably a value, not a module/owner name. Excluded from
+    /// cmp_key — derived from the same scan as receiver_type.
+    #[serde(default)]
+    pub receiver_materialized: bool,
     /// Number of arguments at the call site. `None` = not captured / unknown
     /// (the arity-disambiguation filter treats `None` as "keep").
     /// Excluded from cmp_key — positional data, not part of logical identity.
@@ -371,6 +380,7 @@ impl CallGraph {
                         ),
                         receiver_type: None,
                         receiver_recovery: None,
+                        receiver_materialized: false,
                         arg_count: None,
                         arg_spread: false,
                         receiver_outcome: None,
@@ -635,15 +645,18 @@ impl CallGraph {
                             line,
                             qualifier,
                         );
-                        let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                        let recv_ctx = crate::resolution::ReceiverCtx {
                             receiver_expr,
                             qualifier: qualifier.as_deref(),
                             fn_node: func_node,
                             call_line: line,
+                            call_start_byte: start_byte,
                             parsed,
                             recv_var: recv_var.as_deref(),
                             file_imports: file_imports_ref,
-                        });
+                        };
+                        let recovered = classifier.classify(recv_ctx);
+                        let materialized = classifier.materialized(recv_ctx);
                         let site = CallSite {
                             caller: caller_id.clone(),
                             callee_name,
@@ -654,6 +667,7 @@ impl CallGraph {
                             qualifier,
                             receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
                             receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                            receiver_materialized: materialized,
                             arg_count,
                             arg_spread,
                             receiver_outcome: None,
@@ -737,6 +751,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -771,6 +786,7 @@ impl CallGraph {
                                 qualifier: None,
                                 receiver_type: None,
                                 receiver_recovery: None,
+                                receiver_materialized: false,
                                 arg_count: None,
                                 arg_spread: false,
                                 receiver_outcome: None,
@@ -858,6 +874,7 @@ impl CallGraph {
                                     qualifier: None,
                                     receiver_type: None,
                                     receiver_recovery: None,
+                                    receiver_materialized: false,
                                     arg_count: None,
                                     arg_spread: false,
                                     receiver_outcome: None,
@@ -955,6 +972,7 @@ impl CallGraph {
                                         qualifier: None,
                                         receiver_type: None,
                                         receiver_recovery: None,
+                                        receiver_materialized: false,
                                         arg_count: None,
                                         arg_spread: false,
                                         receiver_outcome: None,
@@ -982,6 +1000,7 @@ impl CallGraph {
                                             qualifier: None,
                                             receiver_type: None,
                                             receiver_recovery: None,
+                                            receiver_materialized: false,
                                             arg_count: None,
                                             arg_spread: false,
                                             receiver_outcome: None,
@@ -1610,15 +1629,18 @@ impl CallGraph {
                         line,
                         qualifier,
                     );
-                    let recovered = classifier.classify(crate::resolution::ReceiverCtx {
+                    let recv_ctx = crate::resolution::ReceiverCtx {
                         receiver_expr,
                         qualifier: qualifier.as_deref(),
                         fn_node: func_node,
                         call_line: line,
+                        call_start_byte: start_byte,
                         parsed,
                         recv_var: recv_var.as_deref(),
                         file_imports: file_imports_ref,
-                    });
+                    };
+                    let recovered = classifier.classify(recv_ctx);
+                    let materialized = classifier.materialized(recv_ctx);
                     let site = CallSite {
                         caller: caller_id.clone(),
                         callee_name: callee_name.clone(),
@@ -1629,6 +1651,7 @@ impl CallGraph {
                         qualifier,
                         receiver_type: recovered.as_ref().map(|r| r.static_type.clone()),
                         receiver_recovery: recovered.as_ref().map(|r| r.recovery),
+                        receiver_materialized: materialized,
                         arg_count,
                         arg_spread,
                         receiver_outcome: None,
diff --git a/src/resolution.rs b/src/resolution.rs
index 5f98f16..a26dd3a 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -249,6 +249,10 @@ pub struct ReceiverCtx<'a> {
     pub fn_node: tree_sitter::Node<'a>,
     /// 1-indexed call line.
     pub call_line: usize,
+    /// Byte offset the call expression starts at. Scope-aware "binding before the
+    /// call" checks must compare against this, not `call_line` — a same-line binding
+    /// written after the call is otherwise indistinguishable from one before it.
+    pub call_start_byte: usize,
     /// For node_text + the legacy `receiver_type_in_fn` scan.
     pub parsed: &'a crate::ast::ParsedFile,
     /// Go receiver variable of the enclosing method (legacy gate: `is_recv`).
@@ -261,6 +265,18 @@ pub struct ReceiverCtx<'a> {
 /// the CPG build extracts call sites with rayon (`call_graph.rs` par_iter).
 pub trait ReceiverClassifier: Sync {
     fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver>;
+
+    /// True when a local receiver binding (typed param / constructor local /
+    /// annotated local) was found for the qualifier — a state DISTINCT from
+    /// `classify(..).is_some()`. §3.3's import/wildcard guard can poison the
+    /// resolved type (or the legacy gate can bail outright when the qualifier's
+    /// name collides with an import), even though a binding provably exists; R3/R3b
+    /// must still be suppressed in that case, because the qualifier is a value, not
+    /// a module or owner name. Default false: Rust/Go classifiers don't need this —
+    /// their pre-emption already runs off `receiver_outcome`.
+    fn materialized(&self, _ctx: ReceiverCtx<'_>) -> bool {
+        false
+    }
 }
 
 /// Receiver-recovery mode (spec §13.3). `Expanded` (default) turns the implemented
@@ -336,9 +352,9 @@ fn recover_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> Option<Reco
     if !(simple && !is_kw && !is_recv && !is_import) {
         return None;
     }
-    let (ty, how) = ctx
-        .parsed
-        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_line, recover_var)?;
+    let (ty, how) =
+        ctx.parsed
+            .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var)?;
     let static_type = owner_key(&peel_type(&ty));
     if matches!(
         ctx.parsed.language,
@@ -363,12 +379,45 @@ pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
     recover_simple_ident(ctx, false)
 }
 
+/// BLOCKER 1+2 fix: is there a local receiver binding (typed param / constructor
+/// local / annotated local) for the qualifier, independent of `recover_simple_ident`?
+/// Unlike `recover_simple_ident`, this does NOT bail when the qualifier's name also
+/// happens to be an import (`is_import(q)`) — a local parameter/local shadows an
+/// outer-scope import within the function body, so that collision does not mean "no
+/// binding," it means "the classify() path conservatively declines to name the
+/// type." The materialized signal must still see the binding so R3/R3b don't treat
+/// the qualifier as a module or owner name. Gated to Python/JS/TS/Tsx — Rust/Go
+/// pre-emption already runs off `receiver_outcome`, not this.
+fn recv_binding_materialized(ctx: &ReceiverCtx<'_>, recover_var: bool) -> bool {
+    use crate::languages::Language;
+    if !matches!(
+        ctx.parsed.language,
+        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
+    ) {
+        return false;
+    }
+    let Some(q) = ctx.qualifier else {
+        return false;
+    };
+    let simple = !q.is_empty() && q.chars().all(|c| c.is_alphanumeric() || c == '_');
+    if !simple || matches!(q, "self" | "this" | "cls") {
+        return false;
+    }
+    ctx.parsed
+        .receiver_type_in_fn(&ctx.fn_node, q, ctx.call_start_byte, recover_var)
+        .is_some()
+}
+
 /// `legacy` — PR-1 behavior, no new forms.
 pub struct LegacyClassifier;
 impl ReceiverClassifier for LegacyClassifier {
     fn classify(&self, ctx: ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
         legacy_recover(&ctx)
     }
+
+    fn materialized(&self, ctx: ReceiverCtx<'_>) -> bool {
+        recv_binding_materialized(&ctx, false)
+    }
 }
 
 /// `expanded` — `legacy` ∪ the new forms.
@@ -388,6 +437,10 @@ impl ReceiverClassifier for ExpandedClassifier {
         }
         None
     }
+
+    fn materialized(&self, ctx: ReceiverCtx<'_>) -> bool {
+        recv_binding_materialized(&ctx, self.var_local)
+    }
 }
 
 /// Recover the statically-asserted type from a Go `x.(T).M()` call.
@@ -1007,6 +1060,14 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
+                // BLOCKER 1+2 fix: gate on `site.receiver_materialized`, NOT
+                // `site.receiver_type.is_some()`. §3.3's guard can poison the
+                // recovered type (import/wildcard) or the legacy gate can bail on an
+                // import-shadowed qualifier name, leaving `receiver_type` None even
+                // though a local binding provably exists — in both cases the
+                // qualifier is still a value, not a module/owner name, so R3/R3b must
+                // still be pre-empted (mirrors `rust_recv_materialized`, which
+                // suppresses on materialize, hit or miss).
                 let recovered_recv_materialized = matches!(
                     caller_lang,
                     Some(
@@ -1015,7 +1076,7 @@ impl CallGraph {
                             | crate::languages::Language::TypeScript
                             | crate::languages::Language::Tsx
                     )
-                ) && site.receiver_type.is_some();
+                ) && site.receiver_materialized;
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -2138,6 +2199,7 @@ mod scope_resolution_predicate_tests {
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
index 695a64d..8c850c3 100644
--- a/tests/lang/javascript/typed_receiver_test.rs
+++ b/tests/lang/javascript/typed_receiver_test.rs
@@ -40,3 +40,15 @@ fn test_javascript_new_constructor_recovers_bare_call_does_not() {
     assert_eq!(factory.receiver_type, None);
     assert!(cg.resolve_call_site(&factory).is_empty());
 }
+
+#[test]
+fn test_javascript_nested_class_static_block_assignment_not_recovered() {
+    // MAJOR scope-fix repro: a nested class's static-init-block binding is that
+    // class's own scope, not a local of the enclosing function — must not leak into
+    // `run`'s binding scan.
+    let cg = graph(
+        "class Foo { m() {} }\nfunction run() {\n  class C {\n    static {\n      let x = new Foo();\n    }\n  }\n  x.m();\n}\n",
+    );
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
diff --git a/tests/lang/python/typed_receiver_test.rs b/tests/lang/python/typed_receiver_test.rs
index ec612c4..4781f75 100644
--- a/tests/lang/python/typed_receiver_test.rs
+++ b/tests/lang/python/typed_receiver_test.rs
@@ -115,3 +115,92 @@ fn test_python_r3b_collision_and_local_miss_fallthrough() {
     assert_eq!(annotated_out.drop, plain_out.drop);
     assert_ne!(annotated_out.drop, Some(DropReason::ExternalReceiver));
 }
+
+#[test]
+fn test_python_poisoned_import_still_suppresses_r3b_collision() {
+    // BLOCKER 1+2 repro: the import guard poisons `receiver_type` to None (Foo is
+    // external), but a typed-param binding for `x` was still found — that
+    // materialized binding must suppress R3b so the call doesn't false-Exact to the
+    // unrelated same-named `class x`.
+    let cg = graph(&[(
+        "svc.py",
+        "from ext import Foo\nclass x:\n    def m(self):\n        pass\ndef run(x: Foo):\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None, "poisoned by the import guard");
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_ne!(r[0].kind, ResolutionKind::QualifierOwner);
+    assert_eq!(r[0].confidence, ResolutionConfidence::NameOnly);
+}
+
+#[test]
+fn test_python_nested_class_body_assignment_not_recovered() {
+    // MAJOR scope-fix repro: `C.x` is a class attribute in the nested class's own
+    // binding scope; it must not be mistaken for a local binding of the `x` used in
+    // `run`'s own scope after the nested class.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    class C:\n        x = Foo()\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
+
+#[test]
+fn test_python_same_line_after_call_assignment_not_recovered() {
+    // MAJOR scope-fix repro: a same-line assignment AFTER the call must not count as
+    // a binding "before" the call — a line-based comparison can't see byte order
+    // within one line.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run(x):\n    x.m(); x = Foo()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+}
+
+#[test]
+fn test_python_outer_binding_still_recovered_despite_nested_class_shadow() {
+    // Negative/edge case for the class-scope skip: a nested class's own attribute
+    // binding must be ignored WITHOUT swallowing the enclosing function's real
+    // binding for the same name (or falsely inflating the shadow-bail count).
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\nclass Bar:\n    def m(self):\n        pass\ndef run():\n    x = Foo()\n    class C:\n        x = Bar()\n    x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+}
+
+#[test]
+fn test_python_unshadowed_import_qualifier_still_resolves_import_qualified() {
+    // Negative/edge case for the materialized signal itself: when the qualifier has
+    // NO local binding at all (a genuine module import, not shadowed by any
+    // param/local), R3 must still fire normally — the fix must not over-suppress.
+    let cg = graph(&[
+        ("utils.py", "def process(data):\n    return data\n"),
+        (
+            "caller.py",
+            "import utils\ndef run():\n    utils.process(1)\n",
+        ),
+    ]);
+    let s = site(&cg, "run", "process");
+    assert_eq!(s.receiver_type, None);
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_eq!(r[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(r[0].confidence, ResolutionConfidence::Exact);
+}
+
+#[test]
+fn test_python_same_line_before_call_assignment_still_recovered() {
+    // Negative/edge case for the byte-based fix: only a binding written AFTER the
+    // call must be excluded — one written before it on the same line is still valid.
+    let cg = graph(&[(
+        "svc.py",
+        "class Foo:\n    def m(self):\n        pass\ndef run():\n    x = Foo(); x.m()\n",
+    )]);
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type.as_deref(), Some("Foo"));
+}
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 77b4b71..1925ecc 100644
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
@@ -53,3 +53,39 @@ fn test_typescript_bare_factory_call_does_not_recover() {
     assert_eq!(s.receiver_type, None);
     assert!(cg.resolve_call_site(&s).is_empty());
 }
+
+#[test]
+fn test_typescript_import_shadowing_param_suppresses_import_qualified() {
+    // BLOCKER 2 repro: `api` is both an import binding (resolving to a real free
+    // function `m` in api.ts) AND a local typed-param name; the local parameter
+    // shadows the import within `run`, so R3 must not treat the qualifier as the
+    // import and false-Exact to api.ts's unrelated free `m`.
+    let files: BTreeMap<_, _> = [
+        (
+            "api.ts".to_string(),
+            ParsedFile::parse("api.ts", "export function m() {}\n", Language::TypeScript)
+                .expect("parse ts"),
+        ),
+        (
+            "svc.ts".to_string(),
+            ParsedFile::parse(
+                "svc.ts",
+                "import api from \"./api\";\nclass Foo { m() {} }\nfunction run(api: Foo) { api.m(); }\n",
+                Language::TypeScript,
+            )
+            .expect("parse ts"),
+        ),
+    ]
+    .into_iter()
+    .collect();
+    let cg = CallGraph::build(&files);
+    let s = site(&cg, "run", "m");
+    assert_eq!(
+        s.receiver_type, None,
+        "recovery still bails on q in imports"
+    );
+    let r = cg.resolve_call_site(&s);
+    assert_eq!(r.len(), 1);
+    assert_ne!(r[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(r[0].confidence, ResolutionConfidence::NameOnly);
+}
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
