# Conclusion-match grading — DES-05 (design/architecture), one anonymous arm

An engineer wrote the design memo below in response to the task brief. The
question was later SETTLED by the project's subsequent history. Grade the
memo against the settled outcome. You do not know who wrote it. Judge by
SHAPE and substance, not labels.

## Settled outcome (ground truth: the vindicated conclusion + repo evidence)

- conclusion: Confirmed a real precision bug for decorated PYTHON methods only
  (both `function_definition` and `decorated_definition` captured, same owner ⇒
  ambiguity demote); fix at extraction by making the **decorated wrapper the
  single canonical FunctionId (drop the inner)**. Explicitly scopes it
  **Python-only**: JS stores decorators inside `method_definition` and TS
  captures the inner arrow — neither double-captures today; add canaries, don't
  assume.
- vindication evidence: shipped exactly wrapper-canonical, Python-only, and
  **merged (#132)** — `0a8cebc feat: unwrap_decorated for decorated-fn field
  readers (ast + contract_slice)`, `339d8ca fix(cfg): do not double-build CFG for
  decorated wrapper+inner`, `1304ab9 fix(nav): inventory keeps decorated wrapper,
  preserves nested defs`, `666ffcc docs(decorated): spec — Python decorated-method
  double-capture (wrapper-canonical)`, `2a01246 docs(handoff): decorated MERGED
  (#132)` (all on main). CONFIRMED. (This memo is the design behind IMPL-09 in
  `nominations.md`.)
- proposed oracle: full marks = identifies the double-capture, chooses
  wrapper-canonical unwrap at extraction, AND scopes it Python-only with the
  JS/TS "does not currently double-capture" reasoning. Fail = "fix for all
  languages" without checking JS/TS grammar (the naive scope error), or a
  post-hoc dedup that doesn't address the caller-side double-scan.

## Grading fields

- recommendation_matches_vindicated: does the memo's recommended design/option
  match the SHAPE of what was vindicated and landed?
- load_bearing_caveats_matched: does the memo carry the settled outcome's
  load-bearing caveats/constraints (the parts the vindication text calls out
  as decisive — e.g. narrowings, guards, buy-sizing, language scoping)?
- scope_calibrated: is the memo's scope and quantitative sizing consistent
  with what reality delivered (neither materially over- nor under-scoped)?
- would_have_prevented_wasted_work: following the memo as written, would the
  team have avoided the missteps the vindication record shows (if any)?
- probe_answer: 2-4 sentences on what the memo got right and wrong vs the
  settled outcome.

## The task brief the engineer received

# Analyze + architect (xhigh, read-only): prism decorated-method double-capture (next Python/JS precision slice)

You are a senior static-analysis architect (codex gpt-5.5, xhigh). **Read-only.** Produce an
ANALYSIS + ARCHITECTURE memo (markdown) for the next precision slice in `prism` (a tree-sitter CPG /
code-navigation tool, 11 languages, exposed to LLM coding agents). Be concrete; cite `file:line`. Session
cwd is the prism repo (`/Users/wesleyjinks/code/slicing`). Do NOT write code or edits — design only.

## The problem (verify it first, then architect the fix)
prism appears to capture every **decorated** method as **TWO** `FunctionId`s — the outer
`decorated_definition` (wrapper) node AND the inner `function_definition` node — both with the same name
and same owner class. Consequence: **every call to a decorated method** (`self.validate()`,
`obj.prop()`, `Cls.helper()`, free calls) resolves to ≥2 same-name candidates and **demotes to NameOnly**
(or worse), because the resolver can't pick between the two captures of the *same* method.

Observed while sizing a sibling slice: on pydantic, ~418 of ~2,066 class methods (~20%) are decorated
(`@property` / `@*validator` / `@staticmethod` / `@classmethod` / …); a `@staticmethod` self-call resolved
NameOnly with two candidates (the `decorated_definition` at lines 2-4 and the inner `function_definition`
at 3-4). This likely degrades a large fraction of Python (and JS/TS decorator) method-call resolution
across the whole dynamic stack — plausibly a **bigger precision lever than the same-class narrowing slice
just shipped**.

## Context docs
- `docs/superpowers/specs/2026-06-22-python-js-self-receiver-samefile-narrowing.md` — the sibling slice;
  read its **§9 "Discovered follow-on — decorated-method double-capture"** (the seed for this memo) and
  §1/§3 for how the owner index + self arm work.
- The committed sibling change is on branch `self-receiver-samefile-narrowing` (don't depend on it; this is
  a separate slice).

## Where to look (verify the mechanism)
- Function extraction: `ParsedFile::all_functions` and the Calls/Functions tree-sitter queries
  (`src/queries.rs` — note the decorated capture; `Language::function_name`,
  `Language::method_owner` in `src/languages/mod.rs` which already normalizes `decorated_definition`).
- The index built from functions: `CallGraph::build*` in `src/call_graph.rs` (the `functions`, `methods`,
  `method_owners` maps; how a method becomes a `FunctionId`).
- Consumers of the (possibly doubled) `FunctionId`s — map the BLAST RADIUS: the resolver
  (`src/resolution.rs` owner_lookup / the R6 + self arms / `exact`/`demoted`), navigation
  (`src/navigation/` — `inventory.rs`, callers/callees/ego), the CPG, witnesses, and anything that counts
  or de-dups functions.

## Deliver (the memo)
1. **Verification:** confirm (or refute) the double-capture with `file:line` evidence — which node kinds
   are captured, in which languages (Python decorators for sure; check JS/TS decorators, and whether
   `function_name`/`method_owner` already collapse them anywhere). Is it 2 `FunctionId`s with distinct
   spans but same `(name, owner)`?
2. **Impact sizing (qualitative + where measurable):** which resolution paths degrade (self_receiver,
   qualifier_owner/R3b, R6, free) and roughly how much (use the ~20%-of-methods figure; note that it hits
   ALL call shapes, not just self). Distinguish precision (NameOnly that should be Exact) from any recall
   effect.
3. **Blast radius:** the complete list of consumers that would be affected by changing the capture (so a
   fix doesn't silently break navigation counts, witnesses, caller/callee, dedup, etc.).
4. **Architecture options** (≥2, with trade-offs, soundness, blast radius, risk):
   - **A — fix at extraction:** capture ONE `FunctionId` per decorated method (e.g., prefer the inner
     `function_definition`, or the `decorated_definition` with a canonical span/name). What breaks? Which
     consumers rely on the wrapper node (e.g., decorator-name access, line ranges)?
   - **B — fix at resolution/index:** collapse wrapper+inner that are the same logical method (span
     containment / same `(file, name, owner)`) into one candidate before Exact/NameOnly classification.
     Less invasive but a band-aid? Does it generalize to non-self call shapes?
   - any **C** you see.
5. **Recommendation + slice outline:** the approach you'd take, why, and a thin-slice plan (what to change,
   how to test it discriminatingly, the acceptance signal — e.g., pydantic kind_exact rise + canary flat +
   Rust/Go byte-identical), plus what to explicitly defer.
6. **Risks / unknowns / where you're uncertain.**

Be opinionated. Prefer the cheapest sound design that yields a real precision buy without regressing
navigation or recall.


## The memo to grade

**Analysis + Architecture Memo: Decorated-Method Double-Capture**

**Verification**
Python is confirmed. The Python function query captures both `(function_definition)` and `(decorated_definition)` as `@func` (`src/queries.rs:92-96`). `ParsedFile::all_functions_via_tree` pushes every capture without dedup (`src/ast.rs:323-337`), and `build_function_table` records each captured node’s own `kind_id`, byte span, and line span (`src/ast.rs:346-369`).

Those two captures then normalize to the same logical name/owner: `Language::function_name` unwraps `decorated_definition` to its child `function_definition` name (`src/languages/mod.rs:907-918`), while Python `method_owner` treats both the wrapper and the inner function as owned by the same enclosing class (`src/languages/mod.rs:1084-1099`). `FunctionId` identity includes `file`, `name`, `start_line`, and `end_line` (`src/call_graph.rs:20-25`), so a decorated method becomes two distinct `FunctionId`s with the same `(file, name, owner)` but different spans.

The call graph uses those raw captures directly. Both `build_skeleton` and full `build` iterate `parsed.all_functions()`, construct a `FunctionId` from the captured node line range, then insert it into `functions` and `methods` (`src/call_graph.rs:276-315`, `src/call_graph.rs:491-562`). Phase 2 repeats `parsed.all_functions()` to collect call sites, so decorated functions are duplicated as callers too (`src/call_graph.rs:582-597`).

This is already recognized elsewhere: `nav functions` has an emission-only dedup that drops Python `decorated_definition` wrappers (`src/navigation/inventory.rs:34-55`), and its test states that without dedup a decorated function emits two records (`tests/navigation/inventory_test.rs:4-15`). The prior spec records the same reproduction and pydantic sizing: ~418 / 2,066 class methods decorated (`docs/superpowers/specs/2026-06-22-python-js-self-receiver-samefile-narrowing.md:310-320`).

JS/TS is not confirmed for the same wrapper+inner bug in this checkout. JS/TS function queries capture `method_definition`, `arrow_function`, etc., but no decorator wrapper node (`src/queries.rs:98-114`), and owner lookup works from the captured method node to the enclosing class (`src/languages/mod.rs:1101-1113`). JS/TS decorator-aware taint code treats decorators as children/header text of the same function node (`src/algorithms/taint.rs:2286-2304`). Add a fixture, but do not assume the Python double-capture mechanism applies to JS/TS.

**Impact**
The main precision loss is “one real method becomes two same-owner candidates,” so paths that should be singleton Exact become multi-candidate NameOnly:

- `self` / `this` / `cls`: `self_owner_lookup_same_class` filters by same file/class span, then demotes when `same_class.len() > 1` (`src/resolution.rs:710-728`, relabeled at `src/resolution.rs:939-968`).
- `Cls.helper()` / owner qualifier: R3b calls `owner_lookup`, then relabels to `QualifierOwner` (`src/resolution.rs:1025-1034`). `owner_lookup_in_modules` demotes any same-primary-owner pool with `pool.len() > 1` (`src/resolution.rs:737-780`).
- Typed receiver / P6-lite: recovered receiver types call `owner_lookup(recv_ty, name)` and inherit the demotion (`src/resolution.rs:1101-1118`).
- Unknown receiver R6 residue: method candidates come from `functions[name]` and filter to `method_owners`; duplicates inflate the NameOnly fanout (`src/resolution.rs:1158-1227`).
- Free decorated functions are worse in same-file local calls: R4 returns `exact(local, LocalDef)` for all local free definitions, with no singleton check (`src/resolution.rs:1229-1248`). A decorated top-level function can therefore produce two Exact edges to the same logical function. Cross-file free calls demote as `FreeMulti` (`src/resolution.rs:1305-1318`).

There is also caller-side duplication: a decorated function body can be indexed under both wrapper and inner caller `FunctionId`s. CPG then creates function nodes from `cg.functions` (`src/cpg/build.rs:327-350`) and emits call/return edges for every resolved caller/callee pair (`src/cpg/build.rs:673-704`). Interprocedural dataflow is exposed too: parameter lookup keys on `(callee.file, callee.name, callee.start_line)` (`src/cpg/build.rs:28-30`), while parameter extraction does not unwrap `decorated_definition` (`src/ast.rs:3881-3892`, `src/ast.rs:3922-3931`), so wrapper-target edges can have empty params while inner-target edges have real params.

Qualitatively: recall mostly stays the same or is inflated; precision and evidence quality degrade through NameOnly demotion, duplicate Exact edges, duplicate caller/callee evidence, and inconsistent CPG dataflow. The pydantic ~20% decorated-method figure is a credible upper-bound signal, and unlike the same-class self slice this hits all call shapes, not just self calls.

**Blast Radius**
Changing this affects every `FunctionId` producer/consumer:

- Function capture/table: `ParsedFile::all_functions`, `FunctionInfo`, `functions()` (`src/ast.rs:43-61`, `src/ast.rs:373-375`).
- Call graph maps: `functions`, `calls`, `callers`, `methods`, `method_owners`, `method_class_span`, `receiver_vars`, `method_facts` (`src/call_graph.rs:143-192`).
- Resolver arms listed above, plus call-stats telemetry (`src/navigation/queries.rs:156-254`).
- CPG build/query/cache: function nodes and indexes (`src/cpg/build.rs:319-355`), Step 5 call edges (`src/cpg/build.rs:657-705`), Step 5b param binding (`src/cpg/build.rs:775-811`), cache reindexing (`src/cpg_cache.rs:424-442`), `function_node_for_id` (`src/cpg/query.rs:43-48`).
- Navigation: symbol seeding can become ambiguous by name when duplicate nodes survive (`src/navigation/seed.rs:61-82`), location seed picks innermost (`src/navigation/mod.rs:81-94`), callers/callees use exact `FunctionId` identity (`src/navigation/queries.rs:624-690`, `src/navigation/queries.rs:739-815`).
- Algorithms using raw `all_functions`: taint explicitly skips Python inner decorated functions today (`src/algorithms/taint.rs:4374-4377`), scope honesty has wrapper-specific behavior/tests (`src/reasoning/scope_honesty.rs:351-370`, `tests/reasoning/scope_honesty_test.rs:172-213`), and Python type extraction already unwraps decorated definitions (`src/type_providers/python.rs:149-167`, `src/type_providers/python.rs:295-306`).

**Architecture Options**
A. Fix at extraction / identity creation. Emit one logical `FunctionId` per Python decorated function. Prefer the inner `function_definition` as the identity node because it already has correct params and matches the `nav functions` dedup contract. Risk: if applied globally to `all_functions`, it breaks decorator-aware consumers that rely on wrapper spans. Safer variant: add a call-graph logical-function iterator and leave raw AST enumeration untouched.

B. Fix at resolver/index. Before Exact/NameOnly classification, collapse wrapper+inner candidates by containment plus same `(file, name, owner/class_span)`. This is less invasive, but it is a band-aid: it leaves duplicate callers, duplicate CPG nodes, navigation symbol ambiguity, inflated counts, and the wrapper-param bug. It must also be repeated for owner lookup, self lookup, free lookup, R6, and CPG edge emission.

C. Recommended hybrid: canonical `FunctionId` view. Keep `ParsedFile::all_functions()` raw, but introduce one central “logical functions for call graph” view used by `CallGraph::build*`, subset builds, and helper lookups. For Python, skip `decorated_definition` wrapper nodes and keep the inner `function_definition`; do not collapse nested same-name functions or overload-like independent definitions. Decorator-aware analyses can still inspect parents from the raw AST.

**Recommendation + Slice Outline**
Take C: extraction-level canonicalization at the `FunctionId` boundary, not resolver-only and not a global `all_functions` behavior change.

Thin slice:

1. Add a canonical iterator/helper used by `CallGraph::build_skeleton`, `CallGraph::build`, `build_direct_subset_with_receiver_config`, and `function_node_for_id`.
2. Python rule: omit `decorated_definition`; keep its child `function_definition`. All other languages unchanged.
3. Add tests that fail before the change:
   - decorated Python method has one `FunctionId` in `functions["helper"]` and one in `methods[("C","helper")]`;
   - `self.helper()` on decorated method becomes one Exact `SelfReceiver`;
   - `C.helper()` becomes one Exact `QualifierOwner`;
   - top-level decorated free call no longer creates two Exact `LocalDef` edges;
   - decorated caller body calls are not duplicated;
   - nested same-name functions still both survive.
4. Add JS/TS decorated-method canary proving current behavior is one function identity, or pin any discovered grammar-specific duplicate separately.
5. Acceptance: full `cargo test` with totals; because this touches call resolution/CPG construction, also `cargo build --release`, `cd eval && uv run tier-a --matrix-only --allow-stale-sut`, and `cd eval && uv run tier-a --quick --allow-stale-sut`.
6. Measurement: pydantic/fastapi call-stats should show `kind_exact` rising and `kind_nameonly` falling for `self_receiver`, `qualifier_owner`, and typed/owner paths; `multi_target_exact_sites` should not rise; Rust/Go should be byte-identical or explicitly explained.

Defer: decorator application call modeling, Python `@property` attribute-access semantics, overload/stub unification, and any JS/TS decorator change unless the canary proves duplicate identities.

**Risks / Unknowns**
The main risk is span semantics: inner identity drops decorator-line coverage from CPG/nav function nodes. That matches current `nav functions` behavior, but location queries on decorator lines may change if they depend on CPG nodes rather than raw scope-honesty logic. Also, dropping wrapper caller collection may remove decorator-expression call edges if Prism currently emits them; decide that explicitly, because existing docs suggest decorator chains are not modeled as call edges. JS/TS remains an unknown until fixture-verified.
