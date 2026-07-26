# Blind pairwise code-review judgment — task REF-03

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Both arms passed
the repo's build and the task's mechanical test evidence (suite green in both cases).

Answer the JSON schema exactly. Binary verdicts: `a_materially_better` /
`b_materially_better` may not both be true; both false = parity. "Materially
better" = a reviewer would insist the other arm adopt the difference
(correctness, safety, coverage of the specified requirements) — NOT style.

## Task brief (verbatim, both arms received this)

# Narrow slice 2 to PYTHON-ONLY typed-receiver recovery (drop JS/TS) — strict TDD

Senior Rust engineer. Session cwd = `/tmp/prism-slice2` (branch `slice2-typed-receivers`). workspace-write.
The slice + the diff-review fix are committed (tip `0ddfe98`). A fix re-review found a NEW BLOCKER: JS/TS
`walk_receiver_bindings` descends into nested lexical blocks (`{ const x = … }`) and materializes the
receiver from a binding NOT visible at the call site → suppresses legit R3 import-qualified.

**Decision: narrow the slice to PYTHON-ONLY recovery** (JS measured buy ≈ 0 — Express is CommonJS — so JS/TS
recovery adds a lexical-scope soundness trap for ~no buy; the architect recommended deferring JS). This
REMOVES the trap-class entirely. Python is function-scoped (no `let`/`const` block scope), so the existing
function/class skip is sufficient for Python.

## Changes (strict TDD — adjust tests first, then narrow)
1. **Gates:** `receiver_type_in_fn` (`src/ast.rs:424`) and `recover_simple_ident` (`src/resolution.rs:320`)
   recover for **Python ONLY** (remove `JavaScript|TypeScript|Tsx`).
2. **Recovery cases:** keep Python typed_parameter/`x = Foo()`/`x: Foo`; **remove** the TS `type_annotation`
   + `new_expression` recovery cases.
3. **Materialized-receiver R3/R3b suppression** (`src/resolution.rs` ~:1057): narrow the language gate from
   Python/JS/TS to **Python only**.
4. **Import/wildcard guard + wildcard sentinel:** Python only (unchanged behavior for Python).
5. **Tests:** keep all Python tests (they must stay green: typed-param hit, constructor-local, annotation,
   poisoned-materialized→NameOnly, import-shadow→typed_param, nested-class skip, same-line-after-call).
   **Convert the TS typed-receiver tests** to assert **TS is NOT recovered** (`receiver_type.is_none()`,
   `receiver_materialized == false`) — i.e. TS behavior is unchanged from main. **Add a JS/TS lexical-block
   non-regression** (the re-review's repro: `import api from "./api"; function run(){ { const api: Foo =
   make(); } api.m(); }` → R3 `import_qualified` preserved, NOT suppressed). Keep Rust/Go non-regression.
6. **Docs:** update the spec (`docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md`) +
   plan to state **Python-only this slice; JS/TS deferred** (architect's recommendation; JS buy ≈0 + the
   lexical-scope trap). Keep `CACHE_VERSION` at 25 (already bumped; the `CallSite` field stays).

## Rules
- Git: explicit `git add`, never `-a`, never `eval/`; trailer
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Can't write `.git` — implement+
  verify, orchestrator commits.
- Finish: `cargo fmt`; `cargo fmt --check` + `cargo test` + `cargo test --features mcp` green.

## Report
Confirm gates are Python-only; TS recovery removed; the JS lexical-block non-regression passes (R3 preserved);
Python tests green; Rust/Go/JS-TS non-regression; cargo counts; any deviation.


## Probe question (answer in `probe_answer`, per arm)

DESCOPE PROBE: the task requires REMOVING shipped JS/TS recovery behavior, not gating/patching around it. For each arm: (a) are JS/TS recovery paths actually removed (not just disabled)? (b) are TS tests CONVERTED to assert NO recovery? (c) is the JS/TS lexical-block non-regression (import api; { const api = ... } api.m() => R3 preserved) present and correct?

## Arm A diff

```diff
diff --git a/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md b/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
index 0cc79fe..0353e68 100644
--- a/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
+++ b/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
@@ -1,4 +1,4 @@
-# Python/JS Typed-Receiver Recovery — Implementation Plan (rev 3)
+# Python/JS Typed-Receiver Recovery — Implementation Plan (rev 4)
 
 > Strict TDD. Design-of-record: `…/specs/2026-06-23-python-js-typed-receiver-recovery.md` (rev 4, SHIP).
 > Branch `slice2-typed-receivers` off merged main. codex-implement (orchestrator commits).
@@ -21,6 +21,19 @@ non-imported, non-wildcard-file local classes; sound; no external-drop spike; Ru
 > set so no recovery-enabled commit can pass without pre-emption. (MINOR) spec rev-4 §3.4/§7 still ask for
 > the `skipped_*` telemetry split — **owner-deferred** (note in the PR checklist), buy measured via
 > `kind_exact` deltas.
+>
+> **Rev 4 — fix re-review fold (spec rev 5): NARROWED TO PYTHON-ONLY; JS/TS deferred.** The fix re-review
+> found a NEW BLOCKER: JS/TS `walk_receiver_bindings` descends into nested lexical blocks
+> (`{ const x = … }`) and materializes the receiver from a binding not visible at the call site →
+> suppresses legit R3 import-qualified. JS measured buy ≈ 0 (Express is CommonJS) → architect recommended
+> deferring JS; narrowing removes the trap-class entirely (Python is function-scoped, so the existing
+> function/class skip suffices). Strict TDD, tests-first: TS typed-receiver fixtures **converted** to
+> assert NOT-recovered (`receiver_type.is_none()`, `receiver_materialized == false` — TS behavior
+> unchanged from main); JS/TS **nested-block R3 non-regression added** (the re-review repro; R3
+> `import_qualified` preserved); then both gates + the R3/R3b suppression + R6 miss-fallthrough narrowed
+> to Python-only and the TS `type_annotation`/`new_expression` recovery cases removed. Python fixtures
+> stay green unchanged; Rust/Go non-regression unchanged; `CACHE_VERSION` stays 25 (the
+> `CallSite.receiver_materialized` field stays).
 
 **TDD order:** **T1+T2 = ONE commit** (gates + guarded recovery + wildcard sentinel + R3/R3b pre-emption +
 R6 miss→fallthrough — recovery never lands without pre-emption) → T3 cache → T4 fixtures → T5 acceptance.
diff --git a/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md b/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
index 5e962be..4a74e23 100644
--- a/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
+++ b/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
@@ -1,4 +1,4 @@
-# Python/JS Typed-Receiver Recovery — Design (2026-06-23, rev 4)
+# Python/JS Typed-Receiver Recovery — Design (2026-06-23, rev 5)
 
 > Slice 2 of the Python/JS resolution-maturity loop (after 1a #131 + decorated #132). Basis: codex
 > architect memo + spec-review. Branch `slice2-typed-receivers` off merged main.
@@ -24,6 +24,19 @@
 > (singleton Exact / multi-owner NameOnly — `owner_lookup` demotes) (§3.2.2). (MINOR) telemetry splits
 > `skipped_imported` vs `skipped_wildcard` (§3.4). The guard has CONVERGED on the simplest sound rule:
 > recover only **non-imported, non-wildcard-file** bare types.
+>
+> **Rev 5 — fix re-review fold (BLOCKER → descope): PYTHON-ONLY this slice; JS/TS deferred.** The JS/TS
+> `walk_receiver_bindings` scan descended into nested lexical blocks (`{ const x = … }`) and materialized
+> the receiver from a binding NOT visible at the call site → suppressed a legit R3 import-qualified edge.
+> JS measured buy ≈ 0 (Express is CommonJS), so JS/TS recovery adds a lexical-scope soundness trap for ~no
+> buy — the architect recommended deferring JS. Narrowing removes the trap-class entirely: Python is
+> function-scoped (no `let`/`const` block scope), so the existing function/class skip is sufficient.
+> Gates (`receiver_type_in_fn`, `classify_simple_ident`) are Python-only (Rust/Go untouched); the TS
+> `type_annotation` + `new_expression` recovery cases are removed; the R3/R3b materialized-receiver
+> suppression and R6 miss-fallthrough are gated Python-only; TS/JS fixtures now pin
+> behavior-unchanged-from-main, plus a JS/TS nested-block R3 non-regression (the re-review repro).
+> `CACHE_VERSION` stays 25 (the `CallSite.receiver_materialized` field stays). Sound JS/TS recovery needs
+> a lexical-scope-aware binding scan — slice 3+ if the buy ever materializes.
 
 ## 1. Problem
 `x.method()` where `x`'s static type is syntactically recoverable (typed param `def f(x: Foo)` / TS
@@ -35,7 +48,8 @@ the type to R6 `owner_lookup(recv_ty, name)` (`src/resolution.rs:~1110`) → `Ty
 is less after demote-on-multi + the triage; Express ≈0).
 
 ## 2. Goal
-Recover the receiver static type for Python/JS/TS and resolve `x.method()` to the in-repo owner's method,
+Recover the receiver static type for Python (rev 5 — JS/TS deferred) and resolve `x.method()` to the
+in-repo owner's method,
 **without** minting a false Exact to a same-named in-repo class when the real type is external, **without**
 a `dropped_external_receiver` spike, and **byte-identical for Rust/Go**.
 
@@ -92,11 +106,13 @@ over-skip of in-repo *imported* types and *all* wildcard-file types (recall cost
 - Rust/Go byte-identical (language gate + preserved drop-on-miss).
 
 ## 5. Scope
-**In:** open the 2 gates Python/JS/TS; recover typed-params + constructor-locals (`Foo()` Python /
-`new Foo()` JS-TS) + explicit annotations of **local** classes; the §3.2 triage + §3.3 type-name guard +
-miss→fallthrough (Python/JS, do-not-return); telemetry; tests. **Out:** imported/cross-module type
-resolution (slice 3/4), Python `self.field: Foo` field types, TS structural/interface typing,
-CommonJS/prototype/factory typing, chained-receiver, span-keyed typed identity.
+**In (rev 5 — Python only):** open the 2 gates for Python; recover Python typed-params +
+constructor-locals (`Foo()`) + explicit annotations (`x: Foo`) of **local** classes; the §3.2 triage +
+§3.3 type-name guard + wildcard sentinel + miss→fallthrough (Python, do-not-return); tests. **Out:**
+**JS/TS recovery (rev 5 — deferred: nested-lexical-block bindings make the function-level scan unsound,
+and the JS buy ≈ 0)**, imported/cross-module type resolution (slice 3/4), Python `self.field: Foo` field
+types, TS structural/interface typing, CommonJS/prototype/factory typing, chained-receiver, span-keyed
+typed identity.
 
 ## 6. Files
 - `src/ast.rs` — `receiver_type_in_fn` (`:424` gate + Python/JS/TS param/annotation/constructor cases;
diff --git a/src/ast.rs b/src/ast.rs
index f8ba460..cda0c7f 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -410,7 +410,9 @@ impl ParsedFile {
     /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
     /// also recovers `var r T` declarations. Only bindings at or before `call_line`
     /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// guarded Python. Python is function-scoped, so the function/class skip in
+    /// `walk_receiver_bindings` suffices; JS/TS are deferred — `let`/`const`
+    /// block scope would need a lexical-scope-aware scan.
     /// Returns the raw, unpeeled type text + which fact recovered it.
     pub fn receiver_type_in_fn(
         &self,
@@ -425,12 +427,7 @@ impl ParsedFile {
 
         if !matches!(
             self.language,
-            Language::Rust
-                | Language::Go
-                | Language::Python
-                | Language::JavaScript
-                | Language::TypeScript
-                | Language::Tsx
+            Language::Rust | Language::Go | Language::Python
         ) {
             return None;
         }
@@ -489,20 +486,6 @@ impl ParsedFile {
                             bindings += 1;
                         }
                     }
-                    Language::TypeScript | Language::Tsx | Language::JavaScript
-                        if matches!(param.kind(), "required_parameter" | "optional_parameter") =>
-                    {
-                        let Some(ty) = param.child_by_field_name("type") else {
-                            continue;
-                        };
-                        if self.parameter_binds_name_before_type(param, ty, receiver) {
-                            found = Some((
-                                self.type_annotation_text(&ty),
-                                ReceiverRecovery::TypedParam,
-                            ));
-                            bindings += 1;
-                        }
-                    }
                     _ => {}
                 }
             }
@@ -4047,16 +4030,7 @@ impl ParsedFile {
         if !is_root && self.language.function_node_types().contains(&node.kind()) {
             return;
         }
-        if !is_root
-            && matches!(
-                self.language,
-                Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-            )
-            && matches!(
-                node.kind(),
-                "class_definition" | "class_declaration" | "class"
-            )
-        {
+        if !is_root && self.language == Language::Python && node.kind() == "class_definition" {
             return;
         }
 
@@ -4156,51 +4130,6 @@ impl ParsedFile {
                     }
                 }
             }
-            (
-                Language::JavaScript | Language::TypeScript | Language::Tsx,
-                "variable_declarator",
-            ) => {
-                let name = node.child_by_field_name("name");
-                if let Some(name) = name {
-                    if self.simple_binding_text(&name).as_deref() == Some(receiver) {
-                        *bindings += 1;
-                        if let Some(ty) = node.child_by_field_name("type") {
-                            *found = Some((
-                                self.type_annotation_text(&ty),
-                                ReceiverRecovery::ConstructorLocal,
-                            ));
-                        } else if let Some(value) = node.child_by_field_name("value") {
-                            *found = self
-                                .constructor_type(&value)
-                                .map(|ty| (ty, ReceiverRecovery::ConstructorLocal));
-                        } else {
-                            *found = None;
-                        }
-                    } else if self.node_binds_name(name, receiver) {
-                        *bindings += 1;
-                        *found = None;
-                    }
-                }
-            }
-            (
-                Language::JavaScript | Language::TypeScript | Language::Tsx,
-                "assignment_expression",
-            ) => {
-                let left = node.child_by_field_name("left");
-                if let Some(left) = left {
-                    if self.simple_binding_text(&left).as_deref() == Some(receiver) {
-                        *bindings += 1;
-                        *found = node
-                            .child_by_field_name("right")
-                            .or_else(|| node.child_by_field_name("value"))
-                            .and_then(|value| self.constructor_type(&value))
-                            .map(|ty| (ty, ReceiverRecovery::ConstructorLocal));
-                    } else if self.node_binds_name(left, receiver) {
-                        *bindings += 1;
-                        *found = None;
-                    }
-                }
-            }
             (Language::Go, "assignment_statement") | (Language::Rust, "assignment_expression") => {
                 let left = node
                     .child_by_field_name("left")
@@ -4273,18 +4202,6 @@ impl ParsedFile {
                 }
                 None
             }
-            "new_expression"
-                if matches!(
-                    self.language,
-                    Language::JavaScript | Language::TypeScript | Language::Tsx
-                ) =>
-            {
-                let ty = node
-                    .child_by_field_name("type")
-                    .or_else(|| node.child_by_field_name("constructor"))
-                    .or_else(|| node.named_child(0))?;
-                Some(self.node_text(&ty).to_string())
-            }
             "struct_expression" | "composite_literal" => {
                 let ty = node
                     .child_by_field_name("name")
@@ -4366,11 +4283,6 @@ impl ParsedFile {
         false
     }
 
-    fn type_annotation_text(&self, node: &Node<'_>) -> String {
-        let text = self.node_text(node).trim();
-        text.strip_prefix(':').unwrap_or(text).trim().to_string()
-    }
-
     /// Extract the parameter name from a parameter declaration node.
     fn extract_param_name(&self, node: &Node<'_>) -> Option<String> {
         match node.kind() {
diff --git a/src/resolution.rs b/src/resolution.rs
index 3a7d055..f792153 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -345,18 +345,15 @@ impl ReceiverRecoveryConfig {
 /// Inner gate + scan shared by `legacy_recover` and `ExpandedClassifier`.
 /// Runs the qualifier/keyword/recv-var gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
-/// is true), peeled + owner-keyed. Python/JS/TS still scan when the qualifier
-/// also names an import so local receiver bindings can suppress R3.
+/// is true), peeled + owner-keyed. Python still scans when the qualifier
+/// also names an import so local receiver bindings can suppress R3. JS/TS are
+/// deferred: `let`/`const` block scope makes the function-level binding scan
+/// unsound (a nested-block binding is not visible at the call site).
 fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverClassification {
     use crate::languages::Language;
     if !matches!(
         ctx.parsed.language,
-        Language::Rust
-            | Language::Go
-            | Language::Python
-            | Language::JavaScript
-            | Language::TypeScript
-            | Language::Tsx
+        Language::Rust | Language::Go | Language::Python
     ) {
         return ReceiverClassification::none();
     }
@@ -370,12 +367,7 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
     if !(simple && !is_kw && !is_recv) {
         return ReceiverClassification::none();
     }
-    if is_import
-        && !matches!(
-            ctx.parsed.language,
-            Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-        )
-    {
+    if is_import && ctx.parsed.language != Language::Python {
         return ReceiverClassification::none();
     }
     let Some((ty, how)) = ctx.parsed.receiver_type_in_fn(
@@ -388,12 +380,10 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
         return ReceiverClassification::none();
     };
     let static_type = owner_key(&peel_type(&ty));
-    if matches!(
-        ctx.parsed.language,
-        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
+    if ctx.parsed.language == Language::Python
+        && ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
     {
         return ReceiverClassification::materialized_only();
     }
@@ -403,7 +393,7 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
     })
 }
 
-/// PR-1 P6-lite recovery shape with `recover_var = false`. Python/JS/TS keep the
+/// PR-1 P6-lite recovery shape with `recover_var = false`. Python keeps the
 /// materialized-receiver shadowing fix from the shared classifier.
 pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
     classify_simple_ident(ctx, false).recovered
@@ -1054,15 +1044,9 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
-                let recovered_recv_materialized = matches!(
-                    caller_lang,
-                    Some(
-                        crate::languages::Language::Python
-                            | crate::languages::Language::JavaScript
-                            | crate::languages::Language::TypeScript
-                            | crate::languages::Language::Tsx
-                    )
-                ) && site.receiver_materialized;
+                let recovered_recv_materialized = caller_lang
+                    == Some(crate::languages::Language::Python)
+                    && site.receiver_materialized;
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -1238,16 +1222,7 @@ impl CallGraph {
                                 }
                             }
                         }
-                        None if !matches!(
-                            caller_lang,
-                            Some(
-                                crate::languages::Language::Python
-                                    | crate::languages::Language::JavaScript
-                                    | crate::languages::Language::TypeScript
-                                    | crate::languages::Language::Tsx
-                            )
-                        ) =>
-                        {
+                        None if caller_lang != Some(crate::languages::Language::Python) => {
                             return ResolutionOutcome::dropped(DropReason::ExternalReceiver);
                         }
                         None => {}
diff --git a/tests/integration/resolution_test.rs b/tests/integration/resolution_test.rs
index aa5d727..fca1674 100644
--- a/tests/integration/resolution_test.rs
+++ b/tests/integration/resolution_test.rs
@@ -2831,28 +2831,22 @@ fn py_recovered_multi_owner_hit_preserves_nameonly_confidence() {
 }
 
 #[test]
-fn js_new_constructor_recovers_but_bare_call_does_not() {
+fn js_typed_receiver_not_recovered_python_only_slice() {
+    // Slice 2 narrowed to Python-only recovery: a JS `new Foo()` local no
+    // longer recovers the receiver; JS behavior is unchanged from main.
     use prism::languages::Language::JavaScript;
-    use prism::resolution::ReceiverRecovery;
     let (cg, _) = build(&[(
         "svc.js",
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction made() { const x = new Foo(); x.m(); }\nfunction factory() { const x = Foo(); x.m(); }\n",
         JavaScript,
     )]);
-    let made = site_in(&cg, "made", "m");
-    assert_eq!(made.receiver_type.as_deref(), Some("Foo"));
-    assert_eq!(
-        made.receiver_recovery,
-        Some(ReceiverRecovery::ConstructorLocal)
-    );
-    let r = cg.resolve_call_site(&made);
-    assert_eq!(r.len(), 1);
-    assert_eq!(r[0].target.file, "svc.js");
-    assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
-
-    let factory = site_in(&cg, "factory", "m");
-    assert_eq!(factory.receiver_type, None);
-    assert!(cg.resolve_call_site(&factory).is_empty());
+    for caller in ["made", "factory"] {
+        let site = site_in(&cg, caller, "m");
+        assert_eq!(site.receiver_type, None, "{caller}");
+        assert_eq!(site.receiver_recovery, None, "{caller}");
+        assert!(!site.receiver_materialized, "{caller}");
+        assert!(cg.resolve_call_site(&site).is_empty(), "{caller}");
+    }
 }
 
 #[test]
diff --git a/tests/lang/javascript/typed_receiver_test.rs b/tests/lang/javascript/typed_receiver_test.rs
index 695a64d..3ae7b0f 100644
--- a/tests/lang/javascript/typed_receiver_test.rs
+++ b/tests/lang/javascript/typed_receiver_test.rs
@@ -1,14 +1,24 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionKind};
+use prism::resolution::{ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
-fn graph(src: &str) -> CallGraph {
-    let files = BTreeMap::from([(
-        "svc.js".to_string(),
-        ParsedFile::parse("svc.js", src, Language::JavaScript).expect("parse js"),
-    )]);
+// Slice 2 is narrowed to Python-only typed-receiver recovery: JS recovery is
+// deferred (buy ~0 — Express is CommonJS — and `let`/`const` block scope makes
+// the function-level binding scan unsound). These fixtures pin JS behavior to
+// main: nothing is recovered or materialized.
+
+fn graph_files(srcs: &[(&str, &str)]) -> CallGraph {
+    let files: BTreeMap<_, _> = srcs
+        .iter()
+        .map(|(path, src)| {
+            (
+                (*path).to_string(),
+                ParsedFile::parse(path, src, Language::JavaScript).expect("parse js"),
+            )
+        })
+        .collect();
     CallGraph::build(&files)
 }
 
@@ -22,21 +32,41 @@ fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
 }
 
 #[test]
-fn test_javascript_new_constructor_recovers_bare_call_does_not() {
-    let cg = graph(
+fn test_javascript_new_constructor_not_recovered() {
+    let cg = graph_files(&[(
+        "svc.js",
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction made() { const x = new Foo(); x.m(); }\nfunction factory() { const x = Foo(); x.m(); }\n",
-    );
-    let made = site(&cg, "made", "m");
-    assert_eq!(made.receiver_type.as_deref(), Some("Foo"));
-    assert_eq!(
-        made.receiver_recovery,
-        Some(ReceiverRecovery::ConstructorLocal)
-    );
-    let r = cg.resolve_call_site(&made);
-    assert_eq!(r.len(), 1);
-    assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
+    )]);
+    for caller in ["made", "factory"] {
+        let s = site(&cg, caller, "m");
+        assert_eq!(s.receiver_type, None, "{caller}");
+        assert_eq!(s.receiver_recovery, None, "{caller}");
+        assert!(!s.receiver_materialized, "{caller}");
+        // Two same-named owners and no receiver type: the R6 precision floor
+        // drops the site, exactly as on main.
+        assert!(cg.resolve_call_site(&s).is_empty(), "{caller}");
+    }
+}
+
+#[test]
+fn test_javascript_nested_block_binding_does_not_suppress_r3() {
+    // Fix re-review BLOCKER repro: a `const` binding inside a nested lexical
+    // block is NOT visible at the call site; it must not materialize the
+    // receiver and suppress the legit R3 import-qualified edge.
+    let cg = graph_files(&[
+        ("api.js", "export function m() {}\n"),
+        (
+            "svc.js",
+            "import api from './api';\nclass Foo { m() {} }\nfunction run() { { const api = new Foo(); } api.m(); }\n",
+        ),
+    ]);
 
-    let factory = site(&cg, "factory", "m");
-    assert_eq!(factory.receiver_type, None);
-    assert!(cg.resolve_call_site(&factory).is_empty());
+    let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+    let out = cg.resolve_call_site(&s);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.js");
 }
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 001b46c..5c85f64 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -1,9 +1,14 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionConfidence, ResolutionKind};
+use prism::resolution::{ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
+// Slice 2 is narrowed to Python-only typed-receiver recovery: TS/JS recovery
+// is deferred (JS buy ~0 — Express is CommonJS — and `let`/`const` block scope
+// makes the function-level binding scan unsound). These fixtures pin TS
+// behavior to main: nothing is recovered or materialized.
+
 fn graph(src: &str) -> CallGraph {
     graph_files(&[("svc.ts", src)])
 }
@@ -31,25 +36,18 @@ fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
 }
 
 #[test]
-fn test_typescript_parameter_annotation_and_new_constructor_recover() {
+fn test_typescript_parameter_annotation_and_new_constructor_not_recovered() {
     let cg = graph(
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction req(x: Foo) { x.m(); }\nfunction opt(x?: Foo) { x.m(); }\nfunction annotated() { const x: Foo = other(); x.m(); }\nfunction made() { const x = new Foo(); x.m(); }\n",
     );
     for caller in ["req", "opt", "annotated", "made"] {
         let s = site(&cg, caller, "m");
-        assert_eq!(s.receiver_type.as_deref(), Some("Foo"), "{caller}");
-        let r = cg.resolve_call_site(&s);
-        assert_eq!(r.len(), 1, "{caller}");
-        if matches!(caller, "req" | "opt") {
-            assert_eq!(s.receiver_recovery, Some(ReceiverRecovery::TypedParam));
-            assert_eq!(r[0].kind, ResolutionKind::TypedParam);
-        } else {
-            assert_eq!(
-                s.receiver_recovery,
-                Some(ReceiverRecovery::ConstructorLocal)
-            );
-            assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
-        }
+        assert_eq!(s.receiver_type, None, "{caller}");
+        assert_eq!(s.receiver_recovery, None, "{caller}");
+        assert!(!s.receiver_materialized, "{caller}");
+        // Two same-named owners and no receiver type: the R6 precision floor
+        // drops the site, exactly as on main.
+        assert!(cg.resolve_call_site(&s).is_empty(), "{caller}");
     }
 }
 
@@ -60,11 +58,12 @@ fn test_typescript_bare_factory_call_does_not_recover() {
     );
     let s = site(&cg, "factory", "m");
     assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
     assert!(cg.resolve_call_site(&s).is_empty());
 }
 
 #[test]
-fn test_typescript_import_shadowing_materialized_param_suppresses_import_qualified() {
+fn test_typescript_import_shadowing_param_keeps_r3_import_qualified() {
     let cg = graph_files(&[
         ("api.ts", "export function m() {}\n"),
         (
@@ -73,25 +72,30 @@ fn test_typescript_import_shadowing_materialized_param_suppresses_import_qualifi
         ),
     ]);
 
+    // `api` is import-bound and TS recovery is off: R3 import-qualified wins,
+    // as on main.
     let shadow = site(&cg, "run", "m");
+    assert_eq!(shadow.receiver_type, None);
+    assert!(!shadow.receiver_materialized);
     let shadow_out = cg.resolve_call_site(&shadow);
-    assert_eq!(shadow.receiver_type.as_deref(), Some("Foo"));
-    assert!(shadow.receiver_materialized);
     assert_eq!(shadow_out.len(), 1);
-    assert_eq!(shadow_out[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(shadow_out[0].kind, ResolutionKind::ImportQualified);
     assert_eq!(shadow_out[0].confidence, ResolutionConfidence::Exact);
-    assert_ne!(shadow_out[0].target.file, "api.ts");
+    assert_eq!(shadow_out[0].target.file, "api.ts");
 
+    // The annotated non-import receiver is not recovered either: the single
+    // same-file owner comes back demoted via the R6 residue.
     let ok = site(&cg, "ok", "m");
+    assert_eq!(ok.receiver_type, None);
+    assert!(!ok.receiver_materialized);
     let ok_out = cg.resolve_call_site(&ok);
-    assert_eq!(ok.receiver_type.as_deref(), Some("Foo"));
     assert_eq!(ok_out.len(), 1);
-    assert_eq!(ok_out[0].kind, ResolutionKind::TypedParam);
-    assert_eq!(ok_out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(ok_out[0].kind, ResolutionKind::R6SingleOwner);
+    assert_eq!(ok_out[0].confidence, ResolutionConfidence::NameOnly);
 }
 
 #[test]
-fn test_typescript_poisoned_type_materialized_param_suppresses_import_qualified() {
+fn test_typescript_poisoned_type_param_keeps_r3_import_qualified() {
     let cg = graph_files(&[
         ("api.ts", "export function m() {}\n"),
         ("types.ts", "export class Foo {}\n"),
@@ -102,12 +106,34 @@ fn test_typescript_poisoned_type_materialized_param_suppresses_import_qualified(
     ]);
 
     let s = site(&cg, "run", "m");
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
     let out = cg.resolve_call_site(&s);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.ts");
+}
+
+#[test]
+fn test_typescript_nested_block_binding_does_not_suppress_r3() {
+    // Fix re-review BLOCKER repro: a `const` binding inside a nested lexical
+    // block is NOT visible at the call site; it must not materialize the
+    // receiver and suppress the legit R3 import-qualified edge.
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from './api';\nclass Foo { m() {} }\nfunction run() { { const api: Foo = make(); } api.m(); }\n",
+        ),
+    ]);
+
+    let s = site(&cg, "run", "m");
     assert_eq!(s.receiver_type, None);
-    assert!(s.receiver_materialized);
-    assert!(out.iter().all(|c| {
-        c.kind != ResolutionKind::ImportQualified
-            || c.confidence != ResolutionConfidence::Exact
-            || c.target.file != "api.ts"
-    }));
+    assert!(!s.receiver_materialized);
+    let out = cg.resolve_call_site(&s);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.ts");
 }

```

## Arm B diff

```diff
diff --git a/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md b/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
index 0cc79fe..2a78d91 100644
--- a/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
+++ b/docs/superpowers/plans/2026-06-23-python-js-typed-receiver-recovery.md
@@ -1,6 +1,6 @@
-# Python/JS Typed-Receiver Recovery — Implementation Plan (rev 3)
+# Python Typed-Receiver Recovery — Implementation Plan (rev 4)
 
-> Strict TDD. Design-of-record: `…/specs/2026-06-23-python-js-typed-receiver-recovery.md` (rev 4, SHIP).
+> Strict TDD. Design-of-record: `…/specs/2026-06-23-python-js-typed-receiver-recovery.md` (rev 5, SHIP).
 > Branch `slice2-typed-receivers` off merged main. codex-implement (orchestrator commits).
 >
 > **Rev 2 — codex plan-review fold (REWORK):** (BLOCKER) telemetry needs CallSite-level evidence →
@@ -11,7 +11,7 @@
 > asserts `receiver_type.is_none()` + no Exact-TypedParam (NameOnly residue allowed); Tier-A `--matrix-only`
 > added per-AGENTS; TS param kinds named.
 
-**Goal:** as spec — guarded Python/JS/TS typed-receiver recovery → Exact `TypedParam`/`ConstructorLocal` for
+**Goal:** as spec — guarded Python typed-receiver recovery → Exact `TypedParam`/`ConstructorLocal` for
 non-imported, non-wildcard-file local classes; sound; no external-drop spike; Rust/Go byte-identical.
 
 > **Rev 3 — plan re-review-2 fold (REWORK, ordering only; design verdicts 1-4,6 TRUE):** (BLOCKER) Task 1
@@ -21,8 +21,14 @@ non-imported, non-wildcard-file local classes; sound; no external-drop spike; Ru
 > set so no recovery-enabled commit can pass without pre-emption. (MINOR) spec rev-4 §3.4/§7 still ask for
 > the `skipped_*` telemetry split — **owner-deferred** (note in the PR checklist), buy measured via
 > `kind_exact` deltas.
+>
+> **Rev 4 — fix re-review blocker fold:** narrow this slice to **Python-only**. JS/TS recovery is deferred
+> because the binding walk descends into nested lexical blocks and can materialize a receiver that is not
+> visible at the call site, suppressing legitimate R3 import-qualified resolution. JS buy is ≈0 on the
+> Express/CommonJS corpus, so remove JS/TS recovery and add lexical-block non-regression tests that preserve
+> R3.
 
-**TDD order:** **T1+T2 = ONE commit** (gates + guarded recovery + wildcard sentinel + R3/R3b pre-emption +
+**TDD order:** **T1+T2 = ONE commit** (Python gates + guarded recovery + wildcard sentinel + R3/R3b pre-emption +
 R6 miss→fallthrough — recovery never lands without pre-emption) → T3 cache → T4 fixtures → T5 acceptance.
 The two tasks below stay as separate TDD *steps* but share a single commit; the first failing-test set MUST
 include the R3b-collision case.
@@ -38,23 +44,25 @@ include the R3b-collision case.
   `site.receiver_type` AND the resolved kind so they can't pass pre-change:
   (a) Python local typed-param → `receiver_type==Some(Foo)` + Exact `TypedParam`; (b) imported `Foo` →
   `receiver_type.is_none()` (skipped); (c) wildcard file → `receiver_type.is_none()` (both class orders);
-  (d) JS `new Foo()` local → Exact; bare JS `Foo()` → `receiver_type.is_none()`.
+  (d) TS typed-param/annotation/`new Foo()` and JS `new Foo()` → `receiver_type.is_none()` and
+  `receiver_materialized == false`; (e) JS/TS nested lexical-block binding repro preserves R3
+  `ImportQualified`.
 - [ ] **Step 2 — run-fail.**
-- [ ] **Step 3 — implement:** open both gates for `Python|JS|TS|Tsx`; recovery in `receiver_type_in_fn`/
+- [ ] **Step 3 — implement:** open both gates for `Python` only; recovery in `receiver_type_in_fn`/
   `walk_receiver_bindings`: Python `typed_parameter`/`typed_default_parameter` (`type` field), `x = Foo()`
-  (Python), `x: Foo` annotated-assignment; TS `required_parameter`/`optional_parameter` `type_annotation`
-  (strip leading `:`), `const x: Foo`, `x = new Foo()` (`new_expression`). **Wildcard sentinel:** in
+  (Python), `x: Foo` annotated-assignment. Remove JS/TS parameter `type_annotation`, `const x: Foo`, and
+  `x = new Foo()` recovery. **Wildcard sentinel:** in
   `extract_imports`, on a `wildcard_import` child, insert a reserved key (e.g. `"*" -> "*"`) into the file's
   imports map (reuses `CallGraph.imports`/`ReceiverCtx.file_imports` — no new field/merge/cache plumbing).
   **Guard (in `recover_simple_ident`, on the PEELED type `T`, before storing `owner_key`):** return `None`
-  if `T` is in `file_imports` OR `file_imports` contains the `"*"` sentinel. Language-gate to Python/JS/TS
+  if `T` is in `file_imports` OR `file_imports` contains the `"*"` sentinel. Language-gate to Python
   (Rust/Go untouched).
 - [ ] **Step 4 — run-pass + build.** **Do NOT commit yet** — recovery must not land without T2's R3b
   pre-emption (else an unsound false-Exact window). Continue to T2; commit T1+T2 together.
 
 ---
 
-## Task 2: R3/R3b pre-emption + R6 miss→fallthrough (Python/JS/TS)
+## Task 2: R3/R3b pre-emption + R6 miss→fallthrough (Python)
 **Files:** `src/resolution.rs` (the `Some(q)` qualifier arm R3/R3b `~:988-1042`; R6 recovered branch
 `~:1110-1166`); tests.
 
@@ -65,19 +73,20 @@ include the R3b-collision case.
   (d) Rust/Go recovered-miss → still `dropped(ExternalReceiver)` (byte-identical).
 - [ ] **Step 2 — run-fail.**
 - [ ] **Step 3 — implement:** mirror Rust's `rust_recv_materialized` pre-emption (`~:988`): for a
-  `Python|JS|TS|Tsx` site with `site.receiver_type.is_some()`, **skip R3 (import-qualifier) and R3b
+  `Python` site with `site.receiver_materialized`, **skip R3 (import-qualifier) and R3b
   (owner-key)** so the recovered type drives resolution (gate so Rust/Go behavior is unchanged). Then in the
-  R6 recovered branch, on a Python/JS/TS `owner_lookup` **miss do NOT return** — fall through to residue
+  R6 recovered branch, on a Python `owner_lookup` **miss do NOT return** — fall through to residue
   (`~:1166`); keep `dropped(ExternalReceiver)` + the Go interface consult for Rust/Go only. Hits preserve
   confidence (owner_lookup demotes multi).
 - [ ] **Step 4 — run-pass + `cargo test --lib`. Step 5 — commit T1+T2 TOGETHER** (one sound commit):
-  `feat: guarded Python/JS typed-receiver recovery + R3b pre-emption + miss-fallthrough`. The R3b-collision
+  `feat: guarded Python typed-receiver recovery + R3b pre-emption + miss-fallthrough`. The R3b-collision
   test must have been RED before this commit.
 
 ---
 
-## Task 3: `CACHE_VERSION` bump
-- [ ] `src/cpg_cache.rs` 23→24 (+ assertion test, assertion-first). Commit `chore(cache): CACHE_VERSION 23->24`.
+## Task 3: `CACHE_VERSION`
+- [ ] Keep `CACHE_VERSION` at 25. It was already bumped for the additive `CallSite.receiver_materialized`
+  field, which remains in this Python-only slice.
 
 ---
 
@@ -89,7 +98,9 @@ include the R3b-collision case.
   assert `receiver_type.is_none()` AND **no Exact `TypedParam`/`ConstructorLocal`** to the in-repo `Foo.m`
   (NameOnly residue is acceptable — the spec skips recovery, it does not poison residue); R3b-collision case;
   local-miss→residue parity.
-- [ ] TS typed-param/`const x: Foo`/`new Foo()` hit; bare `Foo()` not recovered. Rust/Go non-regression.
+- [ ] TS typed-param/`const x: Foo`/`new Foo()` and JS `new Foo()` **not** recovered
+  (`receiver_type.is_none()`, `receiver_materialized == false`); JS/TS nested lexical-block binding repro
+  preserves R3 `ImportQualified`. Rust/Go non-regression.
 - [ ] Commit `test(slice2): typed-receiver discriminating fixtures`.
 
 ---
@@ -101,16 +112,17 @@ include the R3b-collision case.
   **rise**; `dropped_multi_owner`+`r6_single_owner` NameOnly **fall**; **`dropped_external_receiver`
   byte-FLAT**; canary `multi_target_exact_sites` byte-flat. **Report the realized buy — flag if negligible**
   (the import/wildcard guard shrinks it below the ~700 headline).
-- [ ] **Rust (ripgrep)+Go (caddy) byte-identical** (owner accepts in lieu of `--quick`); Express/JS flat.
+- [ ] **Rust (ripgrep)+Go (caddy) byte-identical** (owner accepts in lieu of `--quick`); Express/JS-TS flat.
   Suite + `--features mcp` + `fmt` green.
 
 ## Deferred (this slice)
-`py_js_receiver_recovery { skipped_imported, skipped_wildcard }` telemetry (needs CallSite-level
+JS/TS typed-receiver recovery (needs scope-aware lexical binding, unlike the discarded recursive binding
+walk); `py_receiver_recovery { skipped_imported, skipped_wildcard }` telemetry (needs CallSite-level
 skip-reason persistence — build/merge/cache plumbing); the buy is measured via `kind_exact` deltas instead.
 
 ## Self-review
 - Spec coverage: T1 §3.1+§3.2.1+§3.3 (recovery+guard+wildcard sentinel); T2 §3.2.2 (fallthrough+confidence)
   **+ the R3b pre-emption the plan-review surfaced** (spec intent: recovered type drives resolution);
   T3 cache; T4 §7 fixtures (singleton asserts receiver_type.is_none); T5 §7 acceptance + Tier-A.
-- Soundness-critical: the §3.3 guard (T1) + R3b pre-emption gated to Python/JS/TS (T2) + ExternalReceiver
+- Soundness-critical: the §3.3 guard (T1) + R3b pre-emption gated to Python (T2) + ExternalReceiver
   drop kept Rust/Go-only (T2).
diff --git a/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md b/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
index 5e962be..ff31054 100644
--- a/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
+++ b/docs/superpowers/specs/2026-06-23-python-js-typed-receiver-recovery.md
@@ -1,4 +1,4 @@
-# Python/JS Typed-Receiver Recovery — Design (2026-06-23, rev 4)
+# Python Typed-Receiver Recovery — Design (2026-06-23, rev 5)
 
 > Slice 2 of the Python/JS resolution-maturity loop (after 1a #131 + decorated #132). Basis: codex
 > architect memo + spec-review. Branch `slice2-typed-receivers` off merged main.
@@ -24,30 +24,39 @@
 > (singleton Exact / multi-owner NameOnly — `owner_lookup` demotes) (§3.2.2). (MINOR) telemetry splits
 > `skipped_imported` vs `skipped_wildcard` (§3.4). The guard has CONVERGED on the simplest sound rule:
 > recover only **non-imported, non-wildcard-file** bare types.
+>
+> **Rev 5 — slice narrowed after fix re-review:** JS/TS recovery is **deferred**. `walk_receiver_bindings`
+> descends into nested lexical blocks (`{ const x = ... }`) and can materialize a receiver binding that is
+> not visible at the call site, suppressing legitimate R3 import-qualified resolution. JS measured buy is
+> approximately zero for the current Express/CommonJS corpus, so this slice is **Python-only**; the Python
+> function/class skip remains sound for Python's function-scoped binding model. JS/TS fixtures now assert
+> no recovery/materialization and preserve R3 in the lexical-block repro.
 
 ## 1. Problem
-`x.method()` where `x`'s static type is syntactically recoverable (typed param `def f(x: Foo)` / TS
-`f(x: Foo)`; Python constructor local `x = Foo()`; JS/TS `x = new Foo()`; explicit annotation `x: Foo`) is
-unresolved/NameOnly-demoted for Python/JS/TS. The P6-lite recovery is `Rust|Go`-gated at
+`x.method()` where `x`'s static type is syntactically recoverable in Python (typed param
+`def f(x: Foo)`, constructor local `x = Foo()`, explicit annotation `x: Foo`) is unresolved/NameOnly-demoted.
+The P6-lite recovery is `Rust|Go`-gated at
 `receiver_type_in_fn` (`src/ast.rs:424`) and `recover_simple_ident` (`src/resolution.rs:320`); Rust/Go feed
 the type to R6 `owner_lookup(recv_ty, name)` (`src/resolution.rs:~1110`) → `TypedParam`/`ConstructorLocal`.
 **Buy:** ~171 FastAPI + ~542 pydantic recoverable owner-hit sites (opportunity denominator — realized Exact
-is less after demote-on-multi + the triage; Express ≈0).
+is less after demote-on-multi + the triage). JS/TS is deferred; Express/JS buy measured ≈0 and TS lexical
+block scoping needs a separate sound scope-aware design.
 
 ## 2. Goal
-Recover the receiver static type for Python/JS/TS and resolve `x.method()` to the in-repo owner's method,
+Recover the receiver static type for Python and resolve `x.method()` to the in-repo owner's method,
 **without** minting a false Exact to a same-named in-repo class when the real type is external, **without**
 a `dropped_external_receiver` spike, and **byte-identical for Rust/Go**.
 
 ## 3. Mechanism
 
 ### 3.1 Recovery (what produces a `static_type`)
-Open the gates for `Python|JavaScript|TypeScript|Tsx` and recover, reusing the one-binding+shadow-bail scan:
-- **Typed params:** Python `typed_parameter`/`typed_default_parameter` (`type` field); TS parameter
-  `type_annotation` (strip the leading `:` — see `type_providers/typescript.rs:277-283`).
-- **Constructor locals:** Python `x = Foo()` (a `call` whose function is a bare class-like name) — **Python
-  only**; JS/TS `x = new Foo()` (`new_expression`) — **NOT** bare `Foo()` (that's a factory call, unsound).
-- **Explicit annotations:** Python `x: Foo` annotated assignment; TS `const x: Foo`.
+Open the gates for `Python` and recover, reusing the one-binding+shadow-bail scan:
+- **Typed params:** Python `typed_parameter`/`typed_default_parameter` (`type` field).
+- **Constructor locals:** Python `x = Foo()` (a `call` whose function is a bare class-like name).
+- **Explicit annotations:** Python `x: Foo` annotated assignment.
+
+JS/TS `type_annotation`, `const x: Foo`, and `new_expression` recovery are out of this slice. Tests assert
+`receiver_type.is_none()` and `receiver_materialized == false` for those cases.
 
 ### 3.2 Triage (BLOCKER-1 fix — the miss-behavior, replaces the old contradiction)
 After recovery, peel + owner-key the type to `T`, then:
@@ -63,11 +72,11 @@ After recovery, peel + owner-key the type to `T`, then:
      subset.
    - **miss** — `owner_lookup` returns None, which conflates *known-local-owner-lacks-method* AND
      *no-owner-key-for-`T`* (the resolver has no separate "known local owner" index); **both** → for
-     `Python|JS|TS|Tsx` **fall through to the R6 residue** (do **NOT** `return dropped(ExternalReceiver)`).
+     `Python` **fall through to the R6 residue** (do **NOT** `return dropped(ExternalReceiver)`).
      **Rust/Go keep drop-on-miss (byte-identical).**
 
 **Implementation note (MAJOR fix):** the R6 recovered-receiver block currently early-`return`s on miss
-(`src/resolution.rs:~1117`/`~1162`). The plan MUST restructure so a Python/JS/TS miss does **not** return —
+(`src/resolution.rs:~1117`/`~1162`). The plan MUST restructure so a Python miss does **not** return —
 it continues into the residue path (`~:1166`). Gate the existing `dropped(ExternalReceiver)` to
 Rust/Go.
 
@@ -83,7 +92,7 @@ over-skip of in-repo *imported* types and *all* wildcard-file types (recall cost
 `skipped_imported`/`skipped_wildcard` telemetry). This is the sound first-merge floor.
 
 ### 3.4 Telemetry
-`py_js_receiver_recovery { hit, miss_fallthrough, skipped_imported, skipped_wildcard }` in call-stats.
+`py_receiver_recovery { hit, miss_fallthrough, skipped_imported, skipped_wildcard }` in call-stats.
 
 ## 4. Soundness
 - Multi-owner: `owner_lookup` demotes (`resolution.rs:773`) → no multi-owner wrong-Exact.
@@ -92,20 +101,19 @@ over-skip of in-repo *imported* types and *all* wildcard-file types (recall cost
 - Rust/Go byte-identical (language gate + preserved drop-on-miss).
 
 ## 5. Scope
-**In:** open the 2 gates Python/JS/TS; recover typed-params + constructor-locals (`Foo()` Python /
-`new Foo()` JS-TS) + explicit annotations of **local** classes; the §3.2 triage + §3.3 type-name guard +
-miss→fallthrough (Python/JS, do-not-return); telemetry; tests. **Out:** imported/cross-module type
+**In:** open the 2 gates for Python only; recover typed-params + constructor-locals (`Foo()` Python) +
+explicit annotations of **local** classes; the §3.2 triage + §3.3 type-name guard + miss→fallthrough
+(Python, do-not-return); tests. **Out:** JS/TS typed-receiver recovery, imported/cross-module type
 resolution (slice 3/4), Python `self.field: Foo` field types, TS structural/interface typing,
-CommonJS/prototype/factory typing, chained-receiver, span-keyed typed identity.
+CommonJS/prototype/factory typing, chained-receiver, span-keyed typed identity, telemetry.
 
 ## 6. Files
-- `src/ast.rs` — `receiver_type_in_fn` (`:424` gate + Python/JS/TS param/annotation/constructor cases;
-  JS/TS constructor = `new_expression` only); `walk_receiver_bindings` (`~:3955-4074`) Python/JS arms;
-  constructor recovery currently Rust/Go-only at `~:4106-4126`.
+- `src/ast.rs` — `receiver_type_in_fn` (`:424` gate + Python param/annotation/constructor cases);
+  `walk_receiver_bindings` (`~:3955-4074`) Python arms.
 - `src/resolution.rs` — `recover_simple_ident` (`:320` gate); the **post-recovery type-name import guard**;
-  R6 (`~:1110-1166`) miss→fallthrough for Python/JS/TS (do-not-return; `ExternalReceiver` drop → Rust/Go).
-- `src/resolution_receiver.rs` — `PythonReceiverTyper`/`JsReceiverTyper` or per-language Expanded arms.
-- `src/navigation/queries.rs` (+ stats) — telemetry. `src/cpg_cache.rs` — `CACHE_VERSION` bump.
+  R6 (`~:1110-1166`) miss→fallthrough for Python (do-not-return; `ExternalReceiver` drop → Rust/Go);
+  R3/R3b materialized-receiver suppression gated to Python.
+- `src/cpg_cache.rs` — `CACHE_VERSION` remains 25 for the existing `CallSite.receiver_materialized` field.
 - tests (see §7).
 
 ## 7. Acceptance
@@ -117,9 +125,12 @@ CommonJS/prototype/factory typing, chained-receiver, span-keyed typed identity.
 - **Wildcard false-Exact test (rev-4):** `from ext import *` + `def f(x: Foo): x.m()` with a single in-repo
   `class Foo.m` → must **NOT** recover/Exact-bind, in **both** orders (incl. a same-file `class Foo` defined
   AFTER the annotation — the whole wildcard file is skipped, so declaration order is irrelevant).
-- **Triage tests:** local typed-param hit → Exact; local-miss → residue (not dropped); imported type →
-  skipped (residue); shadow-bail; `new Foo()` JS hit; bare `Foo()` in JS → NOT recovered.
-- **Rust (ripgrep) + Go (caddy)** call-stats **byte-identical**. Express/JS guard flat. Tier-A
+- **Triage tests:** Python local typed-param hit → Exact; local-miss → residue (not dropped);
+  imported type → skipped (residue); shadow-bail; Python constructor/annotation hit.
+- **JS/TS deferred tests:** TS typed-param/`const x: Foo`/`new Foo()` and JS `new Foo()` are not recovered
+  (`receiver_type == None`, `receiver_materialized == false`); nested lexical-block import repro preserves
+  Exact `ImportQualified`.
+- **Rust (ripgrep) + Go (caddy)** call-stats **byte-identical**. Express/JS-TS guard flat. Tier-A
   `--matrix-only` 0-regr; suite green; `fmt` clean. Report the telemetry hit/miss/skipped split.
 
 ## 8. Pipeline
diff --git a/src/ast.rs b/src/ast.rs
index f8ba460..e861d80 100644
--- a/src/ast.rs
+++ b/src/ast.rs
@@ -410,7 +410,7 @@ impl ParsedFile {
     /// on `call_line`. Typed params + constructor locals; when `recover_var` is true
     /// also recovers `var r T` declarations. Only bindings at or before `call_line`
     /// count; >1 binding before the call means shadow bail. Rust + Go +
-    /// guarded Python/JS/TS.
+    /// guarded Python.
     /// Returns the raw, unpeeled type text + which fact recovered it.
     pub fn receiver_type_in_fn(
         &self,
@@ -425,12 +425,7 @@ impl ParsedFile {
 
         if !matches!(
             self.language,
-            Language::Rust
-                | Language::Go
-                | Language::Python
-                | Language::JavaScript
-                | Language::TypeScript
-                | Language::Tsx
+            Language::Rust | Language::Go | Language::Python
         ) {
             return None;
         }
@@ -489,20 +484,6 @@ impl ParsedFile {
                             bindings += 1;
                         }
                     }
-                    Language::TypeScript | Language::Tsx | Language::JavaScript
-                        if matches!(param.kind(), "required_parameter" | "optional_parameter") =>
-                    {
-                        let Some(ty) = param.child_by_field_name("type") else {
-                            continue;
-                        };
-                        if self.parameter_binds_name_before_type(param, ty, receiver) {
-                            found = Some((
-                                self.type_annotation_text(&ty),
-                                ReceiverRecovery::TypedParam,
-                            ));
-                            bindings += 1;
-                        }
-                    }
                     _ => {}
                 }
             }
@@ -4048,10 +4029,7 @@ impl ParsedFile {
             return;
         }
         if !is_root
-            && matches!(
-                self.language,
-                Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-            )
+            && matches!(self.language, Language::Python)
             && matches!(
                 node.kind(),
                 "class_definition" | "class_declaration" | "class"
@@ -4156,51 +4134,6 @@ impl ParsedFile {
                     }
                 }
             }
-            (
-                Language::JavaScript | Language::TypeScript | Language::Tsx,
-                "variable_declarator",
-            ) => {
-                let name = node.child_by_field_name("name");
-                if let Some(name) = name {
-                    if self.simple_binding_text(&name).as_deref() == Some(receiver) {
-                        *bindings += 1;
-                        if let Some(ty) = node.child_by_field_name("type") {
-                            *found = Some((
-                                self.type_annotation_text(&ty),
-                                ReceiverRecovery::ConstructorLocal,
-                            ));
-                        } else if let Some(value) = node.child_by_field_name("value") {
-                            *found = self
-                                .constructor_type(&value)
-                                .map(|ty| (ty, ReceiverRecovery::ConstructorLocal));
-                        } else {
-                            *found = None;
-                        }
-                    } else if self.node_binds_name(name, receiver) {
-                        *bindings += 1;
-                        *found = None;
-                    }
-                }
-            }
-            (
-                Language::JavaScript | Language::TypeScript | Language::Tsx,
-                "assignment_expression",
-            ) => {
-                let left = node.child_by_field_name("left");
-                if let Some(left) = left {
-                    if self.simple_binding_text(&left).as_deref() == Some(receiver) {
-                        *bindings += 1;
-                        *found = node
-                            .child_by_field_name("right")
-                            .or_else(|| node.child_by_field_name("value"))
-                            .and_then(|value| self.constructor_type(&value))
-                            .map(|ty| (ty, ReceiverRecovery::ConstructorLocal));
-                    } else if self.node_binds_name(left, receiver) {
-                        *bindings += 1;
-                        *found = None;
-                    }
-                }
-            }
             (Language::Go, "assignment_statement") | (Language::Rust, "assignment_expression") => {
                 let left = node
                     .child_by_field_name("left")
@@ -4273,18 +4206,6 @@ impl ParsedFile {
                 }
                 None
             }
-            "new_expression"
-                if matches!(
-                    self.language,
-                    Language::JavaScript | Language::TypeScript | Language::Tsx
-                ) =>
-            {
-                let ty = node
-                    .child_by_field_name("type")
-                    .or_else(|| node.child_by_field_name("constructor"))
-                    .or_else(|| node.named_child(0))?;
-                Some(self.node_text(&ty).to_string())
-            }
             "struct_expression" | "composite_literal" => {
                 let ty = node
                     .child_by_field_name("name")
@@ -4366,11 +4287,6 @@ impl ParsedFile {
         false
     }
 
-    fn type_annotation_text(&self, node: &Node<'_>) -> String {
-        let text = self.node_text(node).trim();
-        text.strip_prefix(':').unwrap_or(text).trim().to_string()
-    }
-
     /// Extract the parameter name from a parameter declaration node.
     fn extract_param_name(&self, node: &Node<'_>) -> Option<String> {
         match node.kind() {
diff --git a/src/resolution.rs b/src/resolution.rs
index 3a7d055..1d2a074 100644
--- a/src/resolution.rs
+++ b/src/resolution.rs
@@ -345,18 +345,13 @@ impl ReceiverRecoveryConfig {
 /// Inner gate + scan shared by `legacy_recover` and `ExpandedClassifier`.
 /// Runs the qualifier/keyword/recv-var gate, then the typed-param /
 /// constructor-local scan (and optionally `var` declarations when `recover_var`
-/// is true), peeled + owner-keyed. Python/JS/TS still scan when the qualifier
-/// also names an import so local receiver bindings can suppress R3.
+/// is true), peeled + owner-keyed. Python still scans when the qualifier also
+/// names an import so local receiver bindings can suppress R3.
 fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverClassification {
     use crate::languages::Language;
     if !matches!(
         ctx.parsed.language,
-        Language::Rust
-            | Language::Go
-            | Language::Python
-            | Language::JavaScript
-            | Language::TypeScript
-            | Language::Tsx
+        Language::Rust | Language::Go | Language::Python
     ) {
         return ReceiverClassification::none();
     }
@@ -370,12 +365,7 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
     if !(simple && !is_kw && !is_recv) {
         return ReceiverClassification::none();
     }
-    if is_import
-        && !matches!(
-            ctx.parsed.language,
-            Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-        )
-    {
+    if is_import && !matches!(ctx.parsed.language, Language::Python) {
         return ReceiverClassification::none();
     }
     let Some((ty, how)) = ctx.parsed.receiver_type_in_fn(
@@ -388,12 +378,10 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
         return ReceiverClassification::none();
     };
     let static_type = owner_key(&peel_type(&ty));
-    if matches!(
-        ctx.parsed.language,
-        Language::Python | Language::JavaScript | Language::TypeScript | Language::Tsx
-    ) && ctx
-        .file_imports
-        .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
+    if matches!(ctx.parsed.language, Language::Python)
+        && ctx
+            .file_imports
+            .is_some_and(|m| m.contains_key(&static_type) || m.contains_key("*"))
     {
         return ReceiverClassification::materialized_only();
     }
@@ -403,7 +391,7 @@ fn classify_simple_ident(ctx: &ReceiverCtx<'_>, recover_var: bool) -> ReceiverCl
     })
 }
 
-/// PR-1 P6-lite recovery shape with `recover_var = false`. Python/JS/TS keep the
+/// PR-1 P6-lite recovery shape with `recover_var = false`. Python keeps the
 /// materialized-receiver shadowing fix from the shared classifier.
 pub fn legacy_recover(ctx: &ReceiverCtx<'_>) -> Option<RecoveredReceiver> {
     classify_simple_ident(ctx, false).recovered
@@ -1054,15 +1042,9 @@ impl CallGraph {
                 // for these sites.
                 let rust_recv_materialized = caller_lang == Some(crate::languages::Language::Rust)
                     && site.receiver_outcome.is_some();
-                let recovered_recv_materialized = matches!(
-                    caller_lang,
-                    Some(
-                        crate::languages::Language::Python
-                            | crate::languages::Language::JavaScript
-                            | crate::languages::Language::TypeScript
-                            | crate::languages::Language::Tsx
-                    )
-                ) && site.receiver_materialized;
+                let recovered_recv_materialized =
+                    matches!(caller_lang, Some(crate::languages::Language::Python))
+                        && site.receiver_materialized;
                 let recv_materialized = rust_recv_materialized || recovered_recv_materialized;
 
                 // R3: imported-module qualifier. If an import matches, the
@@ -1240,12 +1222,7 @@ impl CallGraph {
                         }
                         None if !matches!(
                             caller_lang,
-                            Some(
-                                crate::languages::Language::Python
-                                    | crate::languages::Language::JavaScript
-                                    | crate::languages::Language::TypeScript
-                                    | crate::languages::Language::Tsx
-                            )
+                            Some(crate::languages::Language::Python)
                         ) =>
                         {
                             return ResolutionOutcome::dropped(DropReason::ExternalReceiver);
diff --git a/tests/integration/resolution_test.rs b/tests/integration/resolution_test.rs
index aa5d727..18e5165 100644
--- a/tests/integration/resolution_test.rs
+++ b/tests/integration/resolution_test.rs
@@ -2831,27 +2831,21 @@ fn py_recovered_multi_owner_hit_preserves_nameonly_confidence() {
 }
 
 #[test]
-fn js_new_constructor_recovers_but_bare_call_does_not() {
+fn js_new_constructor_and_bare_call_do_not_recover() {
     use prism::languages::Language::JavaScript;
-    use prism::resolution::ReceiverRecovery;
     let (cg, _) = build(&[(
         "svc.js",
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction made() { const x = new Foo(); x.m(); }\nfunction factory() { const x = Foo(); x.m(); }\n",
         JavaScript,
     )]);
     let made = site_in(&cg, "made", "m");
-    assert_eq!(made.receiver_type.as_deref(), Some("Foo"));
-    assert_eq!(
-        made.receiver_recovery,
-        Some(ReceiverRecovery::ConstructorLocal)
-    );
-    let r = cg.resolve_call_site(&made);
-    assert_eq!(r.len(), 1);
-    assert_eq!(r[0].target.file, "svc.js");
-    assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
+    assert_eq!(made.receiver_type, None);
+    assert!(!made.receiver_materialized);
+    assert!(cg.resolve_call_site(&made).is_empty());
 
     let factory = site_in(&cg, "factory", "m");
     assert_eq!(factory.receiver_type, None);
+    assert!(!factory.receiver_materialized);
     assert!(cg.resolve_call_site(&factory).is_empty());
 }
 
diff --git a/tests/lang/javascript/typed_receiver_test.rs b/tests/lang/javascript/typed_receiver_test.rs
index 695a64d..a1060c0 100644
--- a/tests/lang/javascript/typed_receiver_test.rs
+++ b/tests/lang/javascript/typed_receiver_test.rs
@@ -1,14 +1,23 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionKind};
+use prism::resolution::{ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
 fn graph(src: &str) -> CallGraph {
-    let files = BTreeMap::from([(
-        "svc.js".to_string(),
-        ParsedFile::parse("svc.js", src, Language::JavaScript).expect("parse js"),
-    )]);
+    graph_files(&[("svc.js", src)])
+}
+
+fn graph_files(srcs: &[(&str, &str)]) -> CallGraph {
+    let files: BTreeMap<_, _> = srcs
+        .iter()
+        .map(|(path, src)| {
+            (
+                (*path).to_string(),
+                ParsedFile::parse(path, src, Language::JavaScript).expect("parse js"),
+            )
+        })
+        .collect();
     CallGraph::build(&files)
 }
 
@@ -22,21 +31,37 @@ fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
 }
 
 #[test]
-fn test_javascript_new_constructor_recovers_bare_call_does_not() {
+fn test_javascript_new_constructor_and_bare_call_do_not_recover() {
     let cg = graph(
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction made() { const x = new Foo(); x.m(); }\nfunction factory() { const x = Foo(); x.m(); }\n",
     );
     let made = site(&cg, "made", "m");
-    assert_eq!(made.receiver_type.as_deref(), Some("Foo"));
-    assert_eq!(
-        made.receiver_recovery,
-        Some(ReceiverRecovery::ConstructorLocal)
-    );
-    let r = cg.resolve_call_site(&made);
-    assert_eq!(r.len(), 1);
-    assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
+    assert_eq!(made.receiver_type, None);
+    assert!(!made.receiver_materialized);
+    assert!(cg.resolve_call_site(&made).is_empty());
 
     let factory = site(&cg, "factory", "m");
     assert_eq!(factory.receiver_type, None);
+    assert!(!factory.receiver_materialized);
     assert!(cg.resolve_call_site(&factory).is_empty());
 }
+
+#[test]
+fn test_javascript_nested_block_binding_does_not_suppress_import_qualified() {
+    let cg = graph_files(&[
+        ("api.js", "export function m() {}\n"),
+        (
+            "svc.js",
+            "import api from './api';\nclass Foo { m() {} }\nfunction run() { { const api = new Foo(); } api.m(); }\n",
+        ),
+    ]);
+
+    let s = site(&cg, "run", "m");
+    let out = cg.resolve_call_site(&s);
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.js");
+}
diff --git a/tests/lang/typescript/typed_receiver_test.rs b/tests/lang/typescript/typed_receiver_test.rs
index 001b46c..7661ba0 100644
--- a/tests/lang/typescript/typed_receiver_test.rs
+++ b/tests/lang/typescript/typed_receiver_test.rs
@@ -1,7 +1,7 @@
 use prism::ast::ParsedFile;
 use prism::call_graph::{CallGraph, CallSite};
 use prism::languages::Language;
-use prism::resolution::{ReceiverRecovery, ResolutionConfidence, ResolutionKind};
+use prism::resolution::{ResolutionConfidence, ResolutionKind};
 use std::collections::BTreeMap;
 
 fn graph(src: &str) -> CallGraph {
@@ -31,25 +31,15 @@ fn site(cg: &CallGraph, caller: &str, callee: &str) -> CallSite {
 }
 
 #[test]
-fn test_typescript_parameter_annotation_and_new_constructor_recover() {
+fn test_typescript_parameter_annotation_and_new_constructor_do_not_recover() {
     let cg = graph(
         "class Foo { m() {} }\nclass Other { m() {} }\nfunction req(x: Foo) { x.m(); }\nfunction opt(x?: Foo) { x.m(); }\nfunction annotated() { const x: Foo = other(); x.m(); }\nfunction made() { const x = new Foo(); x.m(); }\n",
     );
     for caller in ["req", "opt", "annotated", "made"] {
         let s = site(&cg, caller, "m");
-        assert_eq!(s.receiver_type.as_deref(), Some("Foo"), "{caller}");
-        let r = cg.resolve_call_site(&s);
-        assert_eq!(r.len(), 1, "{caller}");
-        if matches!(caller, "req" | "opt") {
-            assert_eq!(s.receiver_recovery, Some(ReceiverRecovery::TypedParam));
-            assert_eq!(r[0].kind, ResolutionKind::TypedParam);
-        } else {
-            assert_eq!(
-                s.receiver_recovery,
-                Some(ReceiverRecovery::ConstructorLocal)
-            );
-            assert_eq!(r[0].kind, ResolutionKind::ConstructorLocal);
-        }
+        assert_eq!(s.receiver_type, None, "{caller}");
+        assert!(!s.receiver_materialized, "{caller}");
+        assert!(cg.resolve_call_site(&s).is_empty(), "{caller}");
     }
 }
 
@@ -60,11 +50,12 @@ fn test_typescript_bare_factory_call_does_not_recover() {
     );
     let s = site(&cg, "factory", "m");
     assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
     assert!(cg.resolve_call_site(&s).is_empty());
 }
 
 #[test]
-fn test_typescript_import_shadowing_materialized_param_suppresses_import_qualified() {
+fn test_typescript_import_shadowing_param_preserves_import_qualified() {
     let cg = graph_files(&[
         ("api.ts", "export function m() {}\n"),
         (
@@ -75,23 +66,24 @@ fn test_typescript_import_shadowing_materialized_param_suppresses_import_qualifi
 
     let shadow = site(&cg, "run", "m");
     let shadow_out = cg.resolve_call_site(&shadow);
-    assert_eq!(shadow.receiver_type.as_deref(), Some("Foo"));
-    assert!(shadow.receiver_materialized);
+    assert_eq!(shadow.receiver_type, None);
+    assert!(!shadow.receiver_materialized);
     assert_eq!(shadow_out.len(), 1);
-    assert_eq!(shadow_out[0].kind, ResolutionKind::TypedParam);
+    assert_eq!(shadow_out[0].kind, ResolutionKind::ImportQualified);
     assert_eq!(shadow_out[0].confidence, ResolutionConfidence::Exact);
-    assert_ne!(shadow_out[0].target.file, "api.ts");
+    assert_eq!(shadow_out[0].target.file, "api.ts");
 
     let ok = site(&cg, "ok", "m");
     let ok_out = cg.resolve_call_site(&ok);
-    assert_eq!(ok.receiver_type.as_deref(), Some("Foo"));
-    assert_eq!(ok_out.len(), 1);
-    assert_eq!(ok_out[0].kind, ResolutionKind::TypedParam);
-    assert_eq!(ok_out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(ok.receiver_type, None);
+    assert!(!ok.receiver_materialized);
+    assert!(ok_out.iter().all(|c| {
+        c.kind != ResolutionKind::TypedParam && c.kind != ResolutionKind::ConstructorLocal
+    }));
 }
 
 #[test]
-fn test_typescript_poisoned_type_materialized_param_suppresses_import_qualified() {
+fn test_typescript_imported_type_param_preserves_import_qualified() {
     let cg = graph_files(&[
         ("api.ts", "export function m() {}\n"),
         ("types.ts", "export class Foo {}\n"),
@@ -104,10 +96,29 @@ fn test_typescript_poisoned_type_materialized_param_suppresses_import_qualified(
     let s = site(&cg, "run", "m");
     let out = cg.resolve_call_site(&s);
     assert_eq!(s.receiver_type, None);
-    assert!(s.receiver_materialized);
-    assert!(out.iter().all(|c| {
-        c.kind != ResolutionKind::ImportQualified
-            || c.confidence != ResolutionConfidence::Exact
-            || c.target.file != "api.ts"
-    }));
+    assert!(!s.receiver_materialized);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.ts");
+}
+
+#[test]
+fn test_typescript_nested_block_binding_does_not_suppress_import_qualified() {
+    let cg = graph_files(&[
+        ("api.ts", "export function m() {}\n"),
+        (
+            "svc.ts",
+            "import api from './api';\nclass Foo { m() {} }\nfunction make(): Foo { return new Foo(); }\nfunction run() { { const api: Foo = make(); } api.m(); }\n",
+        ),
+    ]);
+
+    let s = site(&cg, "run", "m");
+    let out = cg.resolve_call_site(&s);
+    assert_eq!(s.receiver_type, None);
+    assert!(!s.receiver_materialized);
+    assert_eq!(out.len(), 1);
+    assert_eq!(out[0].kind, ResolutionKind::ImportQualified);
+    assert_eq!(out[0].confidence, ResolutionConfidence::Exact);
+    assert_eq!(out[0].target.file, "api.ts");
 }

```
