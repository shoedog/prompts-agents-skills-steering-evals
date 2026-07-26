# Blind pairwise code-review judgment — task IMPL-12

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Both arms passed
the repo's build and the task's mechanical test evidence (suite green in both cases).

Answer the JSON schema exactly. Binary verdicts: `a_materially_better` /
`b_materially_better` may not both be true; both false = parity. "Materially
better" = a reviewer would insist the other arm adopt the difference
(correctness, safety, coverage of the specified requirements) — NOT style.

## Task brief (verbatim, both arms received this)

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

# Phase-2a PR-2 Task 2.2: direct visible-binding lookup (F5) + def-byte local facts

CONTEXT. PR-2 of Phase-2a receiver typing. Spec
`docs/superpowers/specs/2026-06-17-prism-rust-receiver-typing-design.md` §3.2b; plan
`docs/superpowers/plans/2026-06-17-prism-rust-receiver-typing-phase2a.md` **Task 2.2**. Do EXACTLY Task 2.2.
**INERT**: the lookup + facts are built but NOTHING reads them until Task 2.3. No resolution/nav/cpg behavior
changes.

## Why (round-1 finding F5)
The Phase-1 graph resolves a name to a `Target::Local(BindingRef)`, but `BindingRef{scope,ordinal}` is NOT a
unique key (`add_locals` resets `ordinal` per call). So the Task-2.3 typer must resolve a receiver name to its
binding **directly** (the rib search returning the `Binding`, which carries the `Span` → `(FileId, def_byte)`)
rather than deref a serialized `BindingRef`. This task provides that lookup + a def-byte-keyed local-fact table.

## Files
- Create `src/name_resolution/binding_lookup.rs` (declare `pub mod binding_lookup;` in
  `src/name_resolution/mod.rs`). Build the `local_facts` table where it fits (on `ScopeGraph` or alongside it —
  match the existing module layout; the Task-2.3 typer + Task-2.4 post-pass will consume it). Test: inline.

## Implement
1. `pub fn lookup_visible_binding<'a>(graph: &'a ScopeGraph, file: FileId, at_byte: usize, name: &str)
   -> Option<&'a Binding>`:
   - find the enclosing scope for `(file, at_byte)` (reuse `enclosing_scope`/the populator helper);
   - walk inner→outer ribs; return the NEAREST `Binding` whose `name` matches AND whose `vis_extents` cover
     `at_byte` (the same range gate `resolve` uses).
   - Returns the `Binding` (so the caller reads `Span`/`def_byte`), NOT a `Candidate` (which drops identity).
   - Recall-safe: if >1 candidate binding is equally-near/ambiguous, return `None` (let the caller fall
     through) — never guess.
2. `LocalFact` + the table:
   ```rust
   pub enum BindingKind { Param, Let, Pattern }
   pub enum InitExpr { Ctor(String /*T::new()/T{}*/), Field(String /*e.f syntax*/), Call(String /*g(...) syntax*/), Other }
   pub struct LocalFact { pub kind: BindingKind, pub annotation: Option<String>, pub init: Option<InitExpr> }
   // table: BTreeMap<(FileId, usize /*def_byte*/), LocalFact>
   ```
   Populate it during the Rust populator's local-binding walk (params/lets/patterns), capturing the
   syntactic annotation (`x: T`) and the init RHS shape (`T::new()`/`T{…}`/`e.f`/`g(…)`). Key by
   `(FileId, def_byte)` from the binding's `Span`. (Capture syntax only — string forms; no type resolution
   here. The Task-2.3 typer resolves them.)

## Test (concrete)
```rust
#[test]
fn lookup_visible_binding_returns_binding_by_name_and_byte() {
    // fn f(){ let a = 1; let b = X::new(); b.m(); }  -- looking up `b` at the `b.m()` byte returns the
    // binding whose def_byte is the `let b` site; local_facts[(file, that def_byte)] has init = Ctor("X::new()").
    // Build a complete graph (ScopeGraphBuildInputs), compute the call byte from the source.
    ...assert binding.span().lo.byte == let_b_def_byte;
    ...assert matches!(local_facts.get(&(file, let_b_def_byte)).unwrap().init, Some(InitExpr::Ctor(_)));
}
```
Add a shadowing decoy if feasible (an inner `let b` shadows an outer — lookup at the inner use returns the
inner binding).

## Process
TDD. `cargo test --lib binding_lookup` + full `cargo test` (zero regressions; macOS `_dyld_start` transient —
terminate+rerun a stalled target; `cli` dogfood slow → allow time/`--test-threads=1`); `cargo fmt`; `cargo
clippy --all-targets`; `cargo build`. Then `cargo build --release && cd eval && uv run tier-a --matrix-only
--allow-stale-sut` (0 regressions — INERT).

Commit (exact + trailer):
```
feat(rust-recv): direct visible-binding lookup (F5) + def-byte local facts — PR-2 Task 2.2

lookup_visible_binding returns the Binding (carrying Span/def_byte) via the rib
search, not a serialized BindingRef (which is non-unique). local_facts keyed by
(FileId, def_byte) capture binding kind/annotation/init-shape for the Task-2.3
typer. INERT: nothing reads them yet.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

## Acceptance
- Lookup returns the right (shadow-correct) binding; recall-safe on ambiguity (None). local_facts populated +
  unread (grep). Full suite green; --matrix-only 0 regressions. STATUS + commit SHA. Leave untracked artifacts.


## Probe question (answer in `probe_answer`, per arm)

THE KEY PROBE: the original implementation shipped a latent bug — per-param `add_locals` gave `fn f(a, b)` BOTH params BindingRef ordinal 0 (found only by a later adversarial review). For EACH arm, judge: (a) does the implementation's design avoid or contain that collision class? (b) would the arm's TESTS catch such a collision if introduced (e.g. distinct facts/bindings asserted for two bindings introduced by one declaration or one param list)?

## Arm A diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
new file mode 100644
index 0000000..ca338f7
--- /dev/null
+++ b/src/name_resolution/binding_lookup.rs
@@ -0,0 +1,504 @@
+//! Direct visible-binding lookup (F5) + def-byte-keyed local-binding facts —
+//! Phase-2a PR-2 Task 2.2 (receiver-typing spec §3.2b).
+//!
+//! `BindingRef{scope, ordinal}` is NOT a unique key (`add_locals` resets
+//! `ordinal` per call — round-4 F5), so the Task-2.3 receiver typer resolves a
+//! receiver name to its binding **directly**: [`lookup_visible_binding`] is the
+//! rib search returning the [`Binding`] itself (which carries the `Span` →
+//! `(FileId, def_byte)`), NOT a `Candidate` (which drops binding identity).
+//!
+//! [`LocalFact`]s capture the **syntactic** shape of each local binding the
+//! Rust populator mints (params / `let`s / patterns): the annotation (`x: T`)
+//! and the init RHS shape (`T::new()` / `T{…}` / `e.f` / `g(…)`) as raw
+//! strings — no type resolution here; the Task-2.3 typer resolves them. The
+//! table lives on [`ScopeGraph::local_facts`], keyed by `(FileId, def_byte)`
+//! from the binding's def-site span.
+//!
+//! **INERT (PR-2):** built during `populate_rust`; nothing reads it until the
+//! Task-2.3 typer.
+//!
+//! ## Recall-safety (§7 resolve-or-fall-through)
+//! The lookup mirrors the engine's bare-name walk: a rib that claims the name
+//! is authoritative (nearest-def wins; an equally-near tie → `None`); a
+//! covering macro wildcard or glob edge at an unclaimed rib → `None` (the name
+//! may be introduced by something we cannot see — poison, never skip to an
+//! outer same-name); the lexical ascent stops at the module boundary exactly
+//! like `RustPolicy::ascend_to_parent`. The worst outcome is a missed (never a
+//! wrong) binding.
+
+use serde::{Deserialize, Serialize};
+use tree_sitter::Node;
+
+use crate::ast::ParsedFile;
+use crate::name_resolution::graph::ScopeGraph;
+use crate::name_resolution::rust_policy::{EK_GLOB, NS_VALUE};
+use crate::name_resolution::rust_populator::enclosing_scope;
+use crate::name_resolution::types::{Binding, FileId, ScopeKind, SourceLoc, Span};
+
+// ── LocalFact — the def-byte-keyed local-binding facts (§3.2b) ────────────────
+
+/// How a local name was introduced.
+#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub enum BindingKind {
+    /// A fn/closure parameter bound as a single simple identifier.
+    Param,
+    /// A `let` bound as a single simple identifier.
+    Let,
+    /// Any other pattern binding (destructured `let`/param, `for`/`match`/
+    /// `if let`/`while let`) — no per-name annotation/init is attributable to
+    /// one bound name, so none is recorded (recall-safe).
+    Pattern,
+}
+
+/// The syntactic shape of a `let` initializer RHS (raw source text; the
+/// Task-2.3 typer resolves the strings — no type resolution here).
+#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub enum InitExpr {
+    /// A constructor form: `T::new()` / `T::default()` (args elided) or `T{}`
+    /// (body elided).
+    Ctor(String),
+    /// A field access, verbatim: `e.f`.
+    Field(String),
+    /// A non-method, non-constructor call: `g()` / `a::g()` (args elided).
+    Call(String),
+    /// Anything else (literal, method call, reference, …) — the typer falls
+    /// through.
+    Other,
+}
+
+/// The build-time facts for one local binding (spec §3.2b).
+#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub struct LocalFact {
+    pub kind: BindingKind,
+    /// The syntactic type annotation (`x: T` → `"T"`), verbatim.
+    pub annotation: Option<String>,
+    /// The `let` initializer's syntactic shape, when singly-attributable.
+    pub init: Option<InitExpr>,
+}
+
+impl LocalFact {
+    /// A bare pattern-binding fact (no attributable annotation/init).
+    pub fn pattern() -> Self {
+        LocalFact {
+            kind: BindingKind::Pattern,
+            annotation: None,
+            init: None,
+        }
+    }
+}
+
+/// The `(file, def_byte)` of a binding's definition site — the `lo` of its
+/// first visibility extent (a populator-minted local's extent starts at its
+/// def byte). `None` when the binding carries no recorded extent.
+pub fn def_site(binding: &Binding) -> Option<(FileId, usize)> {
+    binding.vis_extents.first().map(|s| (s.lo.file, s.lo.byte))
+}
+
+// ── the direct visible-binding lookup (F5) ────────────────────────────────────
+
+/// Resolve `name` (Value ns) at `(file, at_byte)` to its **visible binding** —
+/// the rib search returning the [`Binding`] itself, so the caller can read its
+/// def-site `Span` → `(FileId, def_byte)` (round-4 F5: `resolve` returns only
+/// `Candidate`s, which drop binding identity, and `BindingRef` is non-unique).
+///
+/// Walks scopes inner→outer from the enclosing scope of `at_byte`, applying
+/// the same `vis_extents` range gate the engine's rib step uses. Within a
+/// claimed rib the NEAREST binding wins (the latest def byte — a later `let x`
+/// shadows an earlier one); `None` on any tie/ambiguity, a covering macro
+/// wildcard / glob edge at an unclaimed rib, or exhaustion (recall-safe:
+/// resolve-or-fall-through, never a wrong same-name binding).
+pub fn lookup_visible_binding<'a>(
+    graph: &'a ScopeGraph,
+    file: FileId,
+    at_byte: usize,
+    name: &str,
+) -> Option<&'a Binding> {
+    let at = SourceLoc {
+        file,
+        byte: at_byte,
+    };
+    let mut cur = enclosing_scope(graph, file, at_byte);
+    while let Some(scope_id) = cur {
+        // 1) Explicit Value-ns bindings for `name` at this rib whose
+        //    `vis_extents` cover `at` — the same range gate the engine's rib
+        //    step uses (`engine::self_rib_bindings`). A claimed rib is
+        //    AUTHORITATIVE: pick the nearest here or fall through; never skip
+        //    past a claimed name to an outer same-name (§7 decoy rule).
+        let rib: Vec<&Binding> = graph
+            .bindings
+            .iter()
+            .filter(|b| b.scope == scope_id && b.name == name && b.ns == NS_VALUE)
+            .filter(|b| vis_extent_covers(b, &at))
+            .collect();
+        if !rib.is_empty() {
+            return nearest_in_rib(rib);
+        }
+        // 2) Glob tier, mirrored from the engine: a covering Value-ns macro
+        //    wildcard, or a glob edge covering `at` (Phase 1 mints only
+        //    deferred/Pending globs), may introduce `name` at this rib →
+        //    poison → `None`, never an outer same-name.
+        if macro_wildcard_covers(graph, scope_id, &at) || glob_edge_covers(graph, scope_id, &at) {
+            return None;
+        }
+        // 3) Ascend, mirroring `RustPolicy::ascend_to_parent`'s MODULE-BOUNDARY
+        //    STOP: cross Block/Callable/Type parents; stop after Module/Root.
+        match graph.scope(scope_id).map(|s| &s.kind) {
+            Some(ScopeKind::Block | ScopeKind::Callable | ScopeKind::Type) => {
+                cur = graph.parent_of(scope_id);
+            }
+            _ => return None,
+        }
+    }
+    None
+}
+
+/// The NEAREST binding in a claimed rib: the one defined LAST (max def byte —
+/// a later `let x` re-binding shadows an earlier one; both extents run to the
+/// scope end, so both cover the use site). Recall-safe: any tie or missing
+/// def extent among >1 candidates is ambiguous → `None`, never a guess.
+fn nearest_in_rib(rib: Vec<&Binding>) -> Option<&Binding> {
+    if rib.len() == 1 {
+        return rib.into_iter().next();
+    }
+    let def_byte = |b: &Binding| b.vis_extents.first().map(|s| s.lo.byte);
+    if rib.iter().any(|b| def_byte(b).is_none()) {
+        return None; // an extent-less sibling has an unknown def site
+    }
+    let best = rib.iter().filter_map(|b| def_byte(b)).max()?;
+    let mut nearest = rib.into_iter().filter(|b| def_byte(b) == Some(best));
+    let first = nearest.next()?;
+    if nearest.next().is_some() {
+        None // equally-near → ambiguous
+    } else {
+        Some(first)
+    }
+}
+
+// The two range predicates mirror the engine's private `vis_extent_covers` /
+// `span_covers` (half-open `[lo, hi)`, same-file) — the SAME gate `resolve`
+// applies at a rib.
+
+fn vis_extent_covers(b: &Binding, at: &SourceLoc) -> bool {
+    if b.vis_extents.is_empty() {
+        return true; // no recorded extent ⇒ scope-wide (conservative: visible)
+    }
+    b.vis_extents.iter().any(|s| span_covers(s, at))
+}
+
+fn span_covers(s: &Span, at: &SourceLoc) -> bool {
+    s.lo.file == at.file && at.byte >= s.lo.byte && at.byte < s.hi.byte
+}
+
+/// Does an unexpanded-macro wildcard in `scope` (Value ns) cover `at`?
+fn macro_wildcard_covers(
+    graph: &ScopeGraph,
+    scope: crate::name_resolution::types::ScopeId,
+    at: &SourceLoc,
+) -> bool {
+    graph
+        .macro_wildcards
+        .iter()
+        .any(|m| m.scope == scope && m.ns == NS_VALUE && span_covers(&m.range, at))
+}
+
+/// Does a glob edge from `scope` cover `at`? Phase 1 mints only deferred
+/// (`Pending`) globs — which poison every name they cover — so ANY covering
+/// glob edge conservatively claims the name (a resolved glob would need a
+/// member+visibility check; treating it as claimed only costs recall).
+fn glob_edge_covers(
+    graph: &ScopeGraph,
+    scope: crate::name_resolution::types::ScopeId,
+    at: &SourceLoc,
+) -> bool {
+    graph.edges.iter().any(|e| {
+        e.from == scope
+            && e.kind == EK_GLOB
+            && e.vis_range
+                .as_ref()
+                .is_none_or(|span| span_covers(span, at))
+    })
+}
+
+// ── init-shape classification (populator-side syntax capture) ────────────────
+
+/// Classify a `let` initializer node's **syntactic** shape (§3.2b). Raw text
+/// capture only — no resolution. The constructor notion mirrors `ast.rs`'s
+/// `constructor_type` (`T::new()` / `T::default()` / `T{…}`); a method-call
+/// init (`e.m()`) needs `typeof(e)` — a chain, Phase 3 — so it is `Other`.
+/// Anything the Task-2.3 typer cannot safely act on is `Other` (recall-safe:
+/// it just falls through).
+pub(crate) fn classify_init(pf: &ParsedFile, node: &Node<'_>) -> InitExpr {
+    match node.kind() {
+        // `T{…}` — body elided: the typer only needs the type path.
+        "struct_expression" => {
+            let ty = node
+                .child_by_field_name("name")
+                .or_else(|| node.child_by_field_name("type"));
+            match ty {
+                Some(t) => InitExpr::Ctor(format!("{}{{}}", pf.node_text(&t))),
+                None => InitExpr::Other,
+            }
+        }
+        "call_expression" => {
+            let Some(function) = node.child_by_field_name("function") else {
+                return InitExpr::Other;
+            };
+            match function.kind() {
+                // A path'd or bare callee (args elided): a `::new`/`::default`
+                // tail is the constructor form; anything else is a plain call
+                // for the fn-return-index rung.
+                "identifier" | "scoped_identifier" | "generic_function" => {
+                    let f = pf.node_text(&function);
+                    match f.rsplit_once("::") {
+                        Some((_, tail)) if matches!(tail, "new" | "default") => {
+                            InitExpr::Ctor(format!("{f}()"))
+                        }
+                        _ => InitExpr::Call(format!("{f}()")),
+                    }
+                }
+                // `e.m(…)` — a method call: typing it needs `typeof(e)` (a
+                // chain, Phase 3) → Other.
+                _ => InitExpr::Other,
+            }
+        }
+        "field_expression" => InitExpr::Field(pf.node_text(node).to_string()),
+        _ => InitExpr::Other,
+    }
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use crate::ast::ParsedFile;
+    use crate::call_graph::ScopeGraphBuildInputs;
+    use crate::languages::Language::Rust;
+    use crate::name_resolution::rust_populator::RustCrateConfig;
+    use crate::name_resolution::types::BindTarget;
+
+    /// Build a complete scope graph the way the CPG build does
+    /// (`ScopeGraphBuildInputs` → `CallGraph::build`).
+    fn graph_of(srcs: &[(&str, &str)]) -> ScopeGraph {
+        let mut files = std::collections::BTreeMap::new();
+        for (p, s) in srcs {
+            files.insert(p.to_string(), ParsedFile::parse(p, s, Rust).unwrap());
+        }
+        let mut inputs = ScopeGraphBuildInputs::from_files_convention(&files);
+        inputs.cfg = RustCrateConfig {
+            crate_roots: files.keys().cloned().collect(),
+            ..RustCrateConfig::default()
+        };
+        crate::call_graph::CallGraph::build_with_scope_graph_inputs(&files, Some(&inputs))
+            .scope_graph
+            .expect("scope graph")
+    }
+
+    fn fid(g: &ScopeGraph, path: &str) -> FileId {
+        g.file_paths.get(path).copied().expect("file id")
+    }
+
+    /// Byte offset of the FIRST occurrence of `needle` (marks a def/call site).
+    fn byte_of(src: &str, needle: &str) -> usize {
+        src.find(needle)
+            .unwrap_or_else(|| panic!("needle {needle:?} not found"))
+    }
+
+    fn fact_at<'a>(g: &'a ScopeGraph, file: FileId, def_byte: usize) -> &'a LocalFact {
+        g.local_facts
+            .get(&(file, def_byte))
+            .unwrap_or_else(|| panic!("no local fact at ({file:?}, {def_byte})"))
+    }
+
+    // The task's concrete test: looking up `b` at the `b.m()` byte returns the
+    // binding whose def_byte is the `let b` site, and local_facts carries its
+    // Ctor init shape.
+    #[test]
+    fn lookup_visible_binding_returns_binding_by_name_and_byte() {
+        let src = "fn f(){ let a = 1; let b = X::new(); b.m(); }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        let let_b = byte_of(src, "b = X::new");
+        let binding =
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b").expect("binding for b");
+        assert_eq!(def_site(binding), Some((file, let_b)));
+        let fact = fact_at(&g, file, let_b);
+        assert_eq!(fact.kind, BindingKind::Let);
+        assert!(
+            matches!(&fact.init, Some(InitExpr::Ctor(s)) if s == "X::new()"),
+            "want Ctor(\"X::new()\"), got {:?}",
+            fact.init
+        );
+        // Decoy: `a` resolves to ITS OWN def site, never to `b`'s.
+        let a = lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "a").expect("binding a");
+        assert_eq!(def_site(a), Some((file, byte_of(src, "a = 1"))));
+    }
+
+    // Shadowing decoy: an inner `let b` shadows the outer — the lookup at the
+    // inner use returns the INNER binding; outside the block the outer wins.
+    #[test]
+    fn inner_let_shadows_outer_and_outer_wins_outside() {
+        let src = "fn f(){ let b = Outer::new(); { let b = Inner::new(); b.m(); } b.n(); }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        let inner = lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b").expect("inner b");
+        assert_eq!(def_site(inner), Some((file, byte_of(src, "b = Inner"))));
+        assert!(matches!(
+            &fact_at(&g, file, byte_of(src, "b = Inner")).init,
+            Some(InitExpr::Ctor(s)) if s == "Inner::new()"
+        ));
+        let outer = lookup_visible_binding(&g, file, byte_of(src, "b.n()"), "b").expect("outer b");
+        assert_eq!(def_site(outer), Some((file, byte_of(src, "b = Outer"))));
+    }
+
+    // A later `let b` in the SAME rib shadows the earlier one: nearest def wins.
+    #[test]
+    fn relet_in_same_rib_returns_the_nearest_def() {
+        let src = "fn f(){ let b = A::new(); let b = B::new(); b.m(); }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        let binding =
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b").expect("nearest b");
+        assert_eq!(def_site(binding), Some((file, byte_of(src, "b = B"))));
+    }
+
+    // The vis_extents range gate: a use BEFORE the def falls through; an
+    // unbound name falls through.
+    #[test]
+    fn use_before_def_and_unknown_name_fall_through() {
+        let src = "fn f(){ b.m(); let b = X::new(); }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        assert_eq!(
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b"),
+            None
+        );
+        assert_eq!(
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "nope"),
+            None
+        );
+    }
+
+    // A covering name-introducing macro at an UNCLAIMED inner rib may emit `b`
+    // → poison (None), never skip outward to the param. An explicit same-rib
+    // binding shadows the wildcard (glob-tier), and without the macro the
+    // param is found with its annotation fact.
+    #[test]
+    fn covering_macro_wildcard_poisons_instead_of_skipping_outward() {
+        let poisoned = "fn f(b: X){ { m!(); b.m(); } }";
+        let g = graph_of(&[("a.rs", poisoned)]);
+        let file = fid(&g, "a.rs");
+        assert_eq!(
+            lookup_visible_binding(&g, file, byte_of(poisoned, "b.m()"), "b"),
+            None
+        );
+
+        let clean = "fn f(b: X){ { b.m(); } }";
+        let g = graph_of(&[("a.rs", clean)]);
+        let file = fid(&g, "a.rs");
+        let param =
+            lookup_visible_binding(&g, file, byte_of(clean, "b.m()"), "b").expect("param b");
+        assert_eq!(def_site(param), Some((file, byte_of(clean, "b: X"))));
+        let fact = fact_at(&g, file, byte_of(clean, "b: X"));
+        assert_eq!(fact.kind, BindingKind::Param);
+        assert_eq!(fact.annotation.as_deref(), Some("X"));
+
+        let shadowed = "fn f(){ m!(); let b = X::new(); b.m(); }";
+        let g = graph_of(&[("a.rs", shadowed)]);
+        let file = fid(&g, "a.rs");
+        let binding = lookup_visible_binding(&g, file, byte_of(shadowed, "b.m()"), "b")
+            .expect("explicit binding shadows the wildcard");
+        assert_eq!(def_site(binding), Some((file, byte_of(shadowed, "b = X"))));
+    }
+
+    // Wrong-target decoy: an inner `use m::b` claims the name — the lookup
+    // must return the IMPORT binding (whose def site is the use decl), never
+    // the outer local.
+    #[test]
+    fn inner_use_import_shadows_an_outer_local() {
+        let src = "fn f(){ let b = X::new(); { use m::b; b.m(); } }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        let binding =
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b").expect("import b");
+        assert_eq!(def_site(binding), Some((file, byte_of(src, "use m::b"))));
+        assert!(matches!(binding.target, BindTarget::Pending(..)));
+    }
+
+    // A covering (deferred) glob at an unclaimed rib may introduce `b` →
+    // poison (None), never the outer local.
+    #[test]
+    fn covering_glob_poisons_instead_of_skipping_outward() {
+        let src = "fn f(){ let b = X::new(); { use m::*; b.m(); } }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        assert_eq!(
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b"),
+            None
+        );
+    }
+
+    // Two equally-near bindings (a module-level fn item + a same-name import,
+    // both whole-scope extents) are ambiguous → None (never guess).
+    #[test]
+    fn equally_near_bindings_are_ambiguous_and_fall_through() {
+        let src = "fn b(){}\nuse m::b;\nfn f(){ b.m(); }";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        assert_eq!(
+            lookup_visible_binding(&g, file, byte_of(src, "b.m()"), "b"),
+            None
+        );
+    }
+
+    // The populated fact shapes: annotation + each init form, and the
+    // recall-safety decoys (a destructured let never carries the RHS init; a
+    // method-call init is Other).
+    #[test]
+    fn local_facts_capture_annotation_and_init_shapes() {
+        let src = "fn f(o: Outer){\n\
+                   \x20   let y: Bar = z;\n\
+                   \x20   let w = o.inner;\n\
+                   \x20   let c = make();\n\
+                   \x20   let d = Foo::make();\n\
+                   \x20   let s = Foo { a: 1 };\n\
+                   \x20   let e = o.make();\n\
+                   \x20   let (p, q) = X::new();\n\
+                   \x20   for i in v { i.m(); }\n\
+                   }\n";
+        let g = graph_of(&[("a.rs", src)]);
+        let file = fid(&g, "a.rs");
+        let fact = |needle: &str| fact_at(&g, file, byte_of(src, needle));
+
+        assert_eq!(
+            fact("o: Outer"),
+            &LocalFact {
+                kind: BindingKind::Param,
+                annotation: Some("Outer".into()),
+                init: None
+            }
+        );
+        let y = fact("y: Bar");
+        assert_eq!(
+            (y.kind, y.annotation.as_deref()),
+            (BindingKind::Let, Some("Bar"))
+        );
+        assert_eq!(y.init, Some(InitExpr::Other)); // plain ident RHS
+        assert_eq!(
+            fact("w = o.inner").init,
+            Some(InitExpr::Field("o.inner".into()))
+        );
+        assert_eq!(fact("c = make").init, Some(InitExpr::Call("make()".into())));
+        // A scoped non-`new`/`default` call is a Call (return-typed rung), not a Ctor.
+        assert_eq!(
+            fact("d = Foo").init,
+            Some(InitExpr::Call("Foo::make()".into()))
+        );
+        assert_eq!(fact("s = Foo").init, Some(InitExpr::Ctor("Foo{}".into())));
+        // Method-call init needs typeof(o) — a chain, Phase 3 → Other.
+        assert_eq!(fact("e = o.make").init, Some(InitExpr::Other));
+        // Destructured let: per-name attribution is impossible → Pattern, no
+        // init (NEVER Ctor — `p` is not an `X`).
+        assert_eq!(fact("p, q"), &LocalFact::pattern());
+        assert_eq!(fact("q) = X"), &LocalFact::pattern());
+        assert_eq!(fact("i in v").kind, BindingKind::Pattern);
+    }
+}
diff --git a/src/name_resolution/graph.rs b/src/name_resolution/graph.rs
index 03aa50f..0a11c82 100644
--- a/src/name_resolution/graph.rs
+++ b/src/name_resolution/graph.rs
@@ -89,6 +89,16 @@ pub struct ScopeGraph {
     pub bindings: Vec<Binding>,
     pub edges: Vec<Edge>,
     pub macro_wildcards: Vec<MacroWildcard>,
+    /// Def-byte-keyed local-binding facts (receiver-typing spec §3.2b): the
+    /// syntactic kind/annotation/init shape of every local binding the Rust
+    /// populator mints, keyed by `(file, def_byte)` of the binding's def-site
+    /// span. Consumed at build time by the Phase-2a receiver typer.
+    /// **INERT until PR-2 Task 2.3** — nothing reads it yet.
+    #[serde(default)]
+    pub local_facts: std::collections::BTreeMap<
+        (crate::name_resolution::types::FileId, usize),
+        crate::name_resolution::binding_lookup::LocalFact,
+    >,
 }
 
 impl ScopeGraph {
diff --git a/src/name_resolution/mod.rs b/src/name_resolution/mod.rs
index ef50672..b4c3f0c 100644
--- a/src/name_resolution/mod.rs
+++ b/src/name_resolution/mod.rs
@@ -9,6 +9,7 @@
 //! INERT (wired only via `pub mod name_resolution;` in `lib.rs`). The engine +
 //! Rust policy are exercised solely by `tests/name_resolution/`.
 
+pub mod binding_lookup;
 pub mod consumer;
 pub mod engine;
 pub mod graph;
diff --git a/src/name_resolution/rust_populator/builder.rs b/src/name_resolution/rust_populator/builder.rs
index 8631324..f28dc7a 100644
--- a/src/name_resolution/rust_populator/builder.rs
+++ b/src/name_resolution/rust_populator/builder.rs
@@ -218,6 +218,18 @@ impl<'f> Builder<'f> {
         });
     }
 
+    /// Record a local binding's def-byte-keyed [`LocalFact`] (receiver-typing
+    /// spec §3.2b). Purely additive: nothing reads the table until the
+    /// Phase-2a receiver typer (PR-2 Task 2.3).
+    pub(crate) fn add_local_fact(
+        &mut self,
+        file: FileId,
+        def_byte: usize,
+        fact: crate::name_resolution::binding_lookup::LocalFact,
+    ) {
+        self.graph.local_facts.insert((file, def_byte), fact);
+    }
+
     // ── accessors used by the walk ────────────────────────────────────────────
 
     pub(crate) fn files(&self) -> &'f BTreeMap<String, ParsedFile> {
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index 243388d..a47e5a9 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -5,6 +5,7 @@
 use tree_sitter::Node;
 
 use crate::ast::ParsedFile;
+use crate::name_resolution::binding_lookup::{BindingKind, LocalFact};
 use crate::name_resolution::rust_policy::{NS_TYPE, NS_VALUE, VIS_PUB};
 use crate::name_resolution::types::{BindTarget, ExternRef, FileId, ScopeId, ScopeKind, Target};
 
@@ -320,7 +321,11 @@ pub(in crate::name_resolution::rust_populator::walk) fn walk_function(
     }
 }
 
-/// Bind every parameter pattern as a `Target::Local` in `body_scope`.
+/// Bind every parameter pattern as a `Target::Local` in `body_scope`, with a
+/// per-name [`LocalFact`] (§3.2b): a single-simple-identifier parameter (`x: T`,
+/// incl. `mut`/`ref`) carries its annotation; a destructured parameter's names
+/// get a bare `Pattern` fact (the tuple annotation is not attributable to one
+/// name — recall-safe).
 fn bind_params(
     b: &mut Builder<'_>,
     path: &str,
@@ -329,17 +334,34 @@ fn bind_params(
     file: FileId,
     body_end: usize,
 ) {
-    let names = with_node(b, path, params_nid, |pf, n| {
+    let (names, facts) = with_node(b, path, params_nid, |pf, n| {
         let mut out = Vec::new();
+        let mut facts = Vec::new();
         let mut cursor = n.walk();
         for c in n.children(&mut cursor) {
             if c.kind() == "parameter" {
                 if let Some(p) = c.child_by_field_name("pattern") {
+                    let before = out.len();
                     pattern_idents(pf, &p, &mut out);
+                    let added = out.len() - before;
+                    let simple = added == 1
+                        && matches!(p.kind(), "identifier" | "mut_pattern" | "ref_pattern");
+                    let fact = if simple {
+                        LocalFact {
+                            kind: BindingKind::Param,
+                            annotation: c
+                                .child_by_field_name("type")
+                                .map(|t| pf.node_text(&t).to_string()),
+                            init: None,
+                        }
+                    } else {
+                        LocalFact::pattern()
+                    };
+                    facts.extend(std::iter::repeat_n(fact, added));
                 }
             }
         }
-        out
+        (out, facts)
     });
-    add_locals(b, body_scope, file, body_end, &names);
+    add_locals(b, body_scope, file, body_end, &names, &facts);
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 02a3a71..a8878f0 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -8,6 +8,7 @@
 use tree_sitter::Node;
 
 use crate::ast::ParsedFile;
+use crate::name_resolution::binding_lookup::{classify_init, BindingKind, LocalFact};
 use crate::name_resolution::rust_policy::{NS_VALUE, VIS_PUB};
 use crate::name_resolution::types::{
     BindTarget, BindingRef, FileId, ScopeId, ScopeKind, SourceLoc, Span, Target,
@@ -59,15 +60,44 @@ fn walk_stmt(b: &mut Builder<'_>, path: &str, nid: NodeId, scope: ScopeId, ctx:
 }
 
 fn walk_let(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx: &Ctx) {
-    let (names, value_nid) = with_node(b, path, nid, |pf, n| {
+    let (names, value_nid, fact) = with_node(b, path, nid, |pf, n| {
         let mut names = Vec::new();
-        if let Some(p) = n.child_by_field_name("pattern") {
-            pattern_idents(pf, &p, &mut names);
+        let pattern = n.child_by_field_name("pattern");
+        if let Some(p) = &pattern {
+            pattern_idents(pf, p, &mut names);
         }
-        (names, n.child_by_field_name("value").map(NodeId::of))
+        // The annotation/init are attributable to a name only when the pattern
+        // is one simple identifier (`let x…` incl. `mut`/`ref`); a destructured
+        // `let (a, b) = X::new()` must NOT tag `a` with `X::new()` (§3.2b —
+        // recall-safe: a bare Pattern fact just falls through in the typer).
+        let simple = names.len() == 1
+            && pattern
+                .as_ref()
+                .is_some_and(|p| matches!(p.kind(), "identifier" | "mut_pattern" | "ref_pattern"));
+        let fact = if simple {
+            LocalFact {
+                kind: BindingKind::Let,
+                annotation: n
+                    .child_by_field_name("type")
+                    .map(|t| pf.node_text(&t).to_string()),
+                init: n
+                    .child_by_field_name("value")
+                    .map(|v| classify_init(pf, &v)),
+            }
+        } else {
+            LocalFact::pattern()
+        };
+        (names, n.child_by_field_name("value").map(NodeId::of), fact)
     });
     let scope_end = scope_end_byte(b, scope, ctx.file);
-    add_locals(b, scope, ctx.file, scope_end, &names);
+    add_locals(
+        b,
+        scope,
+        ctx.file,
+        scope_end,
+        &names,
+        &vec![fact; names.len()],
+    );
     // The initializer expression may contain closures / blocks / macros.
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx);
@@ -149,9 +179,19 @@ fn walk_closure(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, c
             n.end_byte(),
         )
     });
-    // A closure body is a Callable scope; its args are locals there.
+    // A closure body is a Callable scope; its args are locals there. The
+    // Phase-1 pattern walk sees only untyped closure args (a typed `|x: T|` is
+    // a `parameter` node it skips), so no annotation is attributable here.
+    let facts = vec![
+        LocalFact {
+            kind: BindingKind::Param,
+            annotation: None,
+            init: None,
+        };
+        names.len()
+    ];
     let body_scope = b.add_scope(ScopeKind::Callable, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, body_scope, ctx.file, hi, &names);
+    add_locals(b, body_scope, ctx.file, hi, &names, &facts);
     if let Some(body_nid) = body_nid {
         walk_expr(b, path, &body_nid, body_scope, ctx);
     }
@@ -173,7 +213,14 @@ fn walk_for(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
     });
     // The loop variable scopes over the loop body block.
     let loop_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, loop_scope, ctx.file, hi, &names);
+    add_locals(
+        b,
+        loop_scope,
+        ctx.file,
+        hi,
+        &names,
+        &vec![LocalFact::pattern(); names.len()],
+    );
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx); // iterator expr is in outer scope
     }
@@ -214,7 +261,14 @@ fn walk_match(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx
             )
         });
         let arm_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-        add_locals(b, arm_scope, ctx.file, hi, &names);
+        add_locals(
+            b,
+            arm_scope,
+            ctx.file,
+            hi,
+            &names,
+            &vec![LocalFact::pattern(); names.len()],
+        );
         if let Some(arm_value) = arm_value {
             walk_expr(b, path, &arm_value, arm_scope, ctx);
         }
@@ -243,7 +297,14 @@ fn walk_if_while(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId,
         (names, blocks, n.start_byte(), n.end_byte())
     });
     let cond_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, cond_scope, ctx.file, hi, &names);
+    add_locals(
+        b,
+        cond_scope,
+        ctx.file,
+        hi,
+        &names,
+        &vec![LocalFact::pattern(); names.len()],
+    );
     for blk in blocks {
         walk_block_body(b, path, &blk, cond_scope, ctx);
     }
@@ -265,17 +326,24 @@ fn collect_match_pattern(pf: &ParsedFile, node: &Node, out: &mut Vec<(String, us
 }
 
 /// Add a `Target::Local` binding (Value ns) for each `(name, def_byte)`, visible
-/// from its def byte to `scope_end`.
+/// from its def byte to `scope_end`, and record each name's [`LocalFact`]
+/// (parallel to `names`; §3.2b) keyed by `(file, def_byte)`.
 ///
 /// A local's accessibility is its lexical extent, not a Rust `pub`; `VIS_PUB`
 /// makes the policy's `visible()` return true (the gate is the `vis_extents`).
+///
+/// The binding mint is INDEPENDENT of `facts` (a short `facts` slice falls back
+/// to a bare pattern fact, never a dropped binding), so the minted bindings —
+/// order, ordinals, extents — are exactly the pre-fact ones.
 pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     b: &mut Builder<'_>,
     scope: ScopeId,
     file: FileId,
     scope_end: usize,
     names: &[(String, usize)],
+    facts: &[LocalFact],
 ) {
+    debug_assert_eq!(names.len(), facts.len());
     for (i, (name, def_byte)) in names.iter().enumerate() {
         b.add_binding(
             scope,
@@ -298,5 +366,7 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
                 },
             }],
         );
+        let fact = facts.get(i).cloned().unwrap_or_else(LocalFact::pattern);
+        b.add_local_fact(file, *def_byte, fact);
     }
 }

```

## Arm B diff

```diff
diff --git a/src/name_resolution/binding_lookup.rs b/src/name_resolution/binding_lookup.rs
new file mode 100644
index 0000000..d86d7c6
--- /dev/null
+++ b/src/name_resolution/binding_lookup.rs
@@ -0,0 +1,158 @@
+//! Direct local-binding lookup for build-time receiver typing.
+//!
+//! This intentionally returns the original [`Binding`] rather than the engine's
+//! [`Candidate`](crate::name_resolution::types::Candidate), because the
+//! Task-2.3 receiver typer needs the binding span as a def-byte identity.
+
+use crate::name_resolution::graph::ScopeGraph;
+use crate::name_resolution::rust_policy::{EK_GLOB, NS_VALUE};
+use crate::name_resolution::rust_populator::enclosing_scope;
+use crate::name_resolution::types::{BindTarget, Binding, FileId, ScopeKind, SourceLoc, Target};
+use serde::{Deserialize, Serialize};
+
+/// Syntactic kind of a Rust local binding.
+#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub enum BindingKind {
+    Param,
+    Let,
+    Pattern,
+}
+
+/// Syntactic initializer shape for a Rust local binding.
+#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub enum InitExpr {
+    /// `T::new()` / `T::default()` / `T { ... }`.
+    Ctor(String),
+    /// `e.f`.
+    Field(String),
+    /// `g(...)`.
+    Call(String),
+    Other,
+}
+
+/// Syntactic local-binding fact keyed by `(FileId, def_byte)`.
+#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
+pub struct LocalFact {
+    pub kind: BindingKind,
+    pub annotation: Option<String>,
+    pub init: Option<InitExpr>,
+}
+
+/// Return the nearest visible value binding named `name` at `(file, at_byte)`.
+pub fn lookup_visible_binding<'a>(
+    graph: &'a ScopeGraph,
+    file: FileId,
+    at_byte: usize,
+    name: &str,
+) -> Option<&'a Binding> {
+    let at = SourceLoc {
+        file,
+        byte: at_byte,
+    };
+    let mut cur = enclosing_scope(graph, file, at_byte);
+    while let Some(scope_id) = cur {
+        let mut matches = graph.bindings.iter().filter(|binding| {
+            binding.scope == scope_id
+                && binding.name == name
+                && binding.ns == NS_VALUE
+                && matches!(&binding.target, BindTarget::Resolved(Target::Local(_)))
+                && vis_extent_covers(binding, &at)
+        });
+        let first = matches.next();
+        if matches.next().is_some() {
+            return None;
+        }
+        if first.is_some() {
+            return first;
+        }
+        if macro_wildcard_poisons(graph, scope_id, &at) {
+            return None;
+        }
+        let kind = match graph.scope(scope_id) {
+            Some(scope) => &scope.kind,
+            None => return None,
+        };
+        if !matches!(
+            kind,
+            ScopeKind::Block | ScopeKind::Callable | ScopeKind::Type
+        ) {
+            break;
+        }
+        cur = graph.parent_of(scope_id);
+    }
+    None
+}
+
+fn vis_extent_covers(binding: &Binding, at: &SourceLoc) -> bool {
+    if binding.vis_extents.is_empty() {
+        return true;
+    }
+    binding
+        .vis_extents
+        .iter()
+        .any(|span| span.lo.file == at.file && at.byte >= span.lo.byte && at.byte < span.hi.byte)
+}
+
+fn macro_wildcard_poisons(
+    graph: &ScopeGraph,
+    scope: crate::name_resolution::types::ScopeId,
+    at: &SourceLoc,
+) -> bool {
+    graph.macro_wildcards.iter().any(|wildcard| {
+        wildcard.scope == scope
+            && wildcard.ns == NS_VALUE
+            && wildcard.range.lo.file == at.file
+            && at.byte >= wildcard.range.lo.byte
+            && at.byte < wildcard.range.hi.byte
+    }) || graph.edges.iter().any(|edge| {
+        edge.from == scope
+            && edge.kind == EK_GLOB
+            && matches!(&edge.to, BindTarget::Pending(_, _))
+            && edge.vis_range.as_ref().is_none_or(|span| {
+                span.lo.file == at.file && at.byte >= span.lo.byte && at.byte < span.hi.byte
+            })
+    })
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use crate::ast::ParsedFile;
+    use crate::call_graph::{CallGraph, ScopeGraphBuildInputs};
+    use crate::languages::Language::Rust;
+    use crate::name_resolution::rust_populator::RustCrateConfig;
+
+    #[test]
+    fn lookup_visible_binding_returns_binding_by_name_and_byte() {
+        let src = "struct X;\nimpl X { fn new() -> Self { X } fn m(&self) {} }\nfn f(){ let b = X::new(); { let b = X::new(); b.m(); } }\n";
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
+        let outer_let_b_def_byte = src.find("b = X::new").unwrap();
+        let inner_let_b_def_byte = src.rfind("b = X::new").unwrap();
+        let call_byte = src.rfind("b.m()").unwrap();
+
+        let binding = lookup_visible_binding(graph, file, call_byte, "b").expect("binding");
+
+        let binding_def_byte = binding.vis_extents.first().unwrap().lo.byte;
+        assert_eq!(binding_def_byte, inner_let_b_def_byte);
+        assert_ne!(binding_def_byte, outer_let_b_def_byte);
+        assert!(matches!(
+            graph
+                .local_facts
+                .get(&(file, inner_let_b_def_byte))
+                .and_then(|fact| fact.init.as_ref()),
+            Some(InitExpr::Ctor(s)) if s == "X::new()"
+        ));
+    }
+}
diff --git a/src/name_resolution/graph.rs b/src/name_resolution/graph.rs
index 03aa50f..69fe6f0 100644
--- a/src/name_resolution/graph.rs
+++ b/src/name_resolution/graph.rs
@@ -15,9 +15,12 @@
 //! `macro_wildcards` are `Vec`s whose **insertion order is meaningful** (see the
 //! `ScopeGraph` doc).
 
+use std::collections::BTreeMap;
+
 use serde::{Deserialize, Serialize};
 
-use crate::name_resolution::types::{Binding, Edge, NamespaceId, Scope, ScopeId, Span};
+use crate::name_resolution::binding_lookup::LocalFact;
+use crate::name_resolution::types::{Binding, Edge, FileId, NamespaceId, Scope, ScopeId, Span};
 
 fn default_complete() -> bool {
     true
@@ -87,6 +90,9 @@ pub struct ScopeGraph {
     pub file_paths: std::collections::BTreeMap<String, crate::name_resolution::types::FileId>,
     pub scopes: std::collections::BTreeMap<ScopeId, Scope>,
     pub bindings: Vec<Binding>,
+    /// Rust local-binding facts keyed by `(file, def_byte)`.
+    #[serde(default)]
+    pub local_facts: BTreeMap<(FileId, usize), LocalFact>,
     pub edges: Vec<Edge>,
     pub macro_wildcards: Vec<MacroWildcard>,
 }
diff --git a/src/name_resolution/mod.rs b/src/name_resolution/mod.rs
index ef50672..b4c3f0c 100644
--- a/src/name_resolution/mod.rs
+++ b/src/name_resolution/mod.rs
@@ -9,6 +9,7 @@
 //! INERT (wired only via `pub mod name_resolution;` in `lib.rs`). The engine +
 //! Rust policy are exercised solely by `tests/name_resolution/`.
 
+pub mod binding_lookup;
 pub mod consumer;
 pub mod engine;
 pub mod graph;
diff --git a/src/name_resolution/rust_populator/builder.rs b/src/name_resolution/rust_populator/builder.rs
index 8631324..145aa7e 100644
--- a/src/name_resolution/rust_populator/builder.rs
+++ b/src/name_resolution/rust_populator/builder.rs
@@ -4,6 +4,7 @@
 use std::collections::{BTreeMap, BTreeSet};
 
 use crate::ast::ParsedFile;
+use crate::name_resolution::binding_lookup::LocalFact;
 use crate::name_resolution::graph::{MacroWildcard, ScopeGraph};
 use crate::name_resolution::rust_policy::EK_GLOB;
 use crate::name_resolution::types::{
@@ -165,6 +166,10 @@ impl<'f> Builder<'f> {
         });
     }
 
+    pub(crate) fn add_local_fact(&mut self, file: FileId, def_byte: usize, fact: LocalFact) {
+        self.graph.local_facts.insert((file, def_byte), fact);
+    }
+
     /// Append a `Glob` edge from `scope`. `deferred` ⇒ `to = Pending` (a Phase-1
     /// poison: the engine returns `Poisoned` for any lookup the glob covers).
     pub(crate) fn add_glob_edge(
diff --git a/src/name_resolution/rust_populator/walk/items.rs b/src/name_resolution/rust_populator/walk/items.rs
index 243388d..f55a1dd 100644
--- a/src/name_resolution/rust_populator/walk/items.rs
+++ b/src/name_resolution/rust_populator/walk/items.rs
@@ -5,6 +5,7 @@
 use tree_sitter::Node;
 
 use crate::ast::ParsedFile;
+use crate::name_resolution::binding_lookup::{BindingKind, LocalFact};
 use crate::name_resolution::rust_policy::{NS_TYPE, NS_VALUE, VIS_PUB};
 use crate::name_resolution::types::{BindTarget, ExternRef, FileId, ScopeId, ScopeKind, Target};
 
@@ -329,17 +330,34 @@ fn bind_params(
     file: FileId,
     body_end: usize,
 ) {
-    let names = with_node(b, path, params_nid, |pf, n| {
+    let facts = with_node(b, path, params_nid, |pf, n| {
         let mut out = Vec::new();
         let mut cursor = n.walk();
         for c in n.children(&mut cursor) {
             if c.kind() == "parameter" {
+                let annotation = c
+                    .child_by_field_name("type")
+                    .map(|ty| pf.node_text(&ty).trim().to_string())
+                    .filter(|s| !s.is_empty());
                 if let Some(p) = c.child_by_field_name("pattern") {
-                    pattern_idents(pf, &p, &mut out);
+                    let mut names = Vec::new();
+                    pattern_idents(pf, &p, &mut names);
+                    for name in names {
+                        out.push((
+                            name,
+                            LocalFact {
+                                kind: BindingKind::Param,
+                                annotation: annotation.clone(),
+                                init: None,
+                            },
+                        ));
+                    }
                 }
             }
         }
         out
     });
-    add_locals(b, body_scope, file, body_end, &names);
+    for (name, fact) in facts {
+        add_locals(b, body_scope, file, body_end, &[name], fact);
+    }
 }
diff --git a/src/name_resolution/rust_populator/walk/locals.rs b/src/name_resolution/rust_populator/walk/locals.rs
index 02a3a71..2905c9d 100644
--- a/src/name_resolution/rust_populator/walk/locals.rs
+++ b/src/name_resolution/rust_populator/walk/locals.rs
@@ -8,6 +8,7 @@
 use tree_sitter::Node;
 
 use crate::ast::ParsedFile;
+use crate::name_resolution::binding_lookup::{BindingKind, InitExpr, LocalFact};
 use crate::name_resolution::rust_policy::{NS_VALUE, VIS_PUB};
 use crate::name_resolution::types::{
     BindTarget, BindingRef, FileId, ScopeId, ScopeKind, SourceLoc, Span, Target,
@@ -59,15 +60,39 @@ fn walk_stmt(b: &mut Builder<'_>, path: &str, nid: NodeId, scope: ScopeId, ctx:
 }
 
 fn walk_let(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx: &Ctx) {
-    let (names, value_nid) = with_node(b, path, nid, |pf, n| {
+    let (names, annotation, init, kind, value_nid) = with_node(b, path, nid, |pf, n| {
         let mut names = Vec::new();
+        let mut simple_pattern = false;
         if let Some(p) = n.child_by_field_name("pattern") {
+            simple_pattern = p.kind() == "identifier";
             pattern_idents(pf, &p, &mut names);
         }
-        (names, n.child_by_field_name("value").map(NodeId::of))
+        let annotation = n
+            .child_by_field_name("type")
+            .map(|ty| pf.node_text(&ty).trim().to_string())
+            .filter(|s| !s.is_empty());
+        let value = n.child_by_field_name("value");
+        let init = value.and_then(|value| init_expr(pf, &value));
+        let kind = if simple_pattern {
+            BindingKind::Let
+        } else {
+            BindingKind::Pattern
+        };
+        (names, annotation, init, kind, value.map(NodeId::of))
     });
     let scope_end = scope_end_byte(b, scope, ctx.file);
-    add_locals(b, scope, ctx.file, scope_end, &names);
+    add_locals(
+        b,
+        scope,
+        ctx.file,
+        scope_end,
+        &names,
+        LocalFact {
+            kind,
+            annotation,
+            init,
+        },
+    );
     // The initializer expression may contain closures / blocks / macros.
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx);
@@ -151,7 +176,18 @@ fn walk_closure(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, c
     });
     // A closure body is a Callable scope; its args are locals there.
     let body_scope = b.add_scope(ScopeKind::Callable, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, body_scope, ctx.file, hi, &names);
+    add_locals(
+        b,
+        body_scope,
+        ctx.file,
+        hi,
+        &names,
+        LocalFact {
+            kind: BindingKind::Param,
+            annotation: None,
+            init: None,
+        },
+    );
     if let Some(body_nid) = body_nid {
         walk_expr(b, path, &body_nid, body_scope, ctx);
     }
@@ -173,7 +209,18 @@ fn walk_for(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx:
     });
     // The loop variable scopes over the loop body block.
     let loop_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, loop_scope, ctx.file, hi, &names);
+    add_locals(
+        b,
+        loop_scope,
+        ctx.file,
+        hi,
+        &names,
+        LocalFact {
+            kind: BindingKind::Pattern,
+            annotation: None,
+            init: None,
+        },
+    );
     if let Some(value_nid) = value_nid {
         walk_expr(b, path, &value_nid, scope, ctx); // iterator expr is in outer scope
     }
@@ -214,7 +261,18 @@ fn walk_match(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId, ctx
             )
         });
         let arm_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-        add_locals(b, arm_scope, ctx.file, hi, &names);
+        add_locals(
+            b,
+            arm_scope,
+            ctx.file,
+            hi,
+            &names,
+            LocalFact {
+                kind: BindingKind::Pattern,
+                annotation: None,
+                init: None,
+            },
+        );
         if let Some(arm_value) = arm_value {
             walk_expr(b, path, &arm_value, arm_scope, ctx);
         }
@@ -243,7 +301,18 @@ fn walk_if_while(b: &mut Builder<'_>, path: &str, nid: &NodeId, scope: ScopeId,
         (names, blocks, n.start_byte(), n.end_byte())
     });
     let cond_scope = b.add_scope(ScopeKind::Block, Some(scope), ctx.file, lo, hi, None);
-    add_locals(b, cond_scope, ctx.file, hi, &names);
+    add_locals(
+        b,
+        cond_scope,
+        ctx.file,
+        hi,
+        &names,
+        LocalFact {
+            kind: BindingKind::Pattern,
+            annotation: None,
+            init: None,
+        },
+    );
     for blk in blocks {
         walk_block_body(b, path, &blk, cond_scope, ctx);
     }
@@ -275,8 +344,10 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
     file: FileId,
     scope_end: usize,
     names: &[(String, usize)],
+    fact: LocalFact,
 ) {
     for (i, (name, def_byte)) in names.iter().enumerate() {
+        b.add_local_fact(file, *def_byte, fact.clone());
         b.add_binding(
             scope,
             name.clone(),
@@ -300,3 +371,28 @@ pub(in crate::name_resolution::rust_populator::walk) fn add_locals(
         );
     }
 }
+
+fn init_expr(pf: &ParsedFile, value: &Node) -> Option<InitExpr> {
+    match value.kind() {
+        "call_expression" => {
+            let function = value
+                .child_by_field_name("function")
+                .or_else(|| value.child_by_field_name("name"))?;
+            let function_text = pf.node_text(&function).trim();
+            if let Some((_ty, ctor)) = function_text.rsplit_once("::") {
+                if matches!(ctor, "new" | "default") {
+                    return Some(InitExpr::Ctor(format!("{function_text}()")));
+                }
+            }
+            Some(InitExpr::Call(format!("{function_text}(...)")))
+        }
+        "struct_expression" => {
+            let ty = value
+                .child_by_field_name("name")
+                .or_else(|| value.child_by_field_name("type"))?;
+            Some(InitExpr::Ctor(format!("{}{{}}", pf.node_text(&ty).trim())))
+        }
+        "field_expression" => Some(InitExpr::Field(pf.node_text(value).trim().to_string())),
+        _ => Some(InitExpr::Other),
+    }
+}

```
