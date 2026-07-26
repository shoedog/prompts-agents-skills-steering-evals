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

**ANALYSIS + ARCHITECTURE MEMO: decorated Python function double-capture**

**Verification**

Confirmed for Python. The Python function query captures both nodes:

- `(function_definition) @func`
- `(decorated_definition) @func`

at `src/queries.rs:92-96`. `Language::function_node_types` mirrors that with both `"function_definition"` and `"decorated_definition"` at `src/languages/mod.rs:84-88`.

The wrapper is normalized to the inner name by `Language::function_name`: if the node is `decorated_definition`, it scans children for the inner `function_definition` and returns that child’s `name` at `src/languages/mod.rs:907-918`. Ownership is also normalized: Python `method_owner` promotes an inner `function_definition` to its parent `decorated_definition` before finding the class block at `src/languages/mod.rs:1084-1099`; `method_owner_class_node` does the same at `src/languages/mod.rs:1182-1197`.

`CallGraph` then creates `FunctionId` directly from each captured node’s line span at every builder path: `build_skeleton` at `src/call_graph.rs:278-302`, full build at `src/call_graph.rs:491-548`, and direct subset at `src/call_graph.rs:1483-1507`. `FunctionId` identity is only `(file, name, start_line, end_line)` at `src/call_graph.rs:16-25`, so wrapper and inner become distinct IDs.

Concrete reproduction against this checkout:

```text
class C:
    @staticmethod
    def helper():
        return 1

    def caller(self):
        return self.helper()
```

`prism nav --no-cache callees --symbol caller --file m.py` returned two `helper` targets:

- `m.py:2-4`, bytes `13..61`, score `0.6`, `self_receiver`
- `m.py:3-4`, bytes `31..61`, score `0.6`, `self_receiver`

`call-stats` on that one-call fixture reported:

```json
"kind_nameonly": { "self_receiver": 2 },
"demoted_edges": 2,
"total_call_sites": 1
```

The inventory path already knows this is a duplicate: `src/navigation/inventory.rs:34-49` drops Python `decorated_definition` wrappers when they contain an inner function. Its test states the root cause directly at `tests/navigation/inventory_test.rs:4-15`.

Refuted for simple JS/TS decorators in this checkout. JS/TS function queries capture `method_definition`, not a decorator wrapper, at `src/queries.rs:98-114`; `function_node_types` agrees at `src/languages/mod.rs:88-101`. I verified `@dec helper() {}` in both `.js` and `.ts` produces one `helper` `FunctionId` and `this.helper()` resolves Exact. TSX shares the TypeScript query path, but I did not separately run a TSX fixture.

Free decorated Python functions are also affected, but differently. A free `@dec def helper()` called as `helper()` returned two `local_def` Exact targets, not NameOnly, because the unqualified local-def arm returns `exact(local, LocalDef)` whenever any local free definitions exist at `src/resolution.rs:1235-1248`. So the issue is not only demotion: it can also produce duplicate full-confidence edges.

**Impact**

This is primarily a precision and graph-identity bug, not a recall bug. The duplicated targets are the same logical callable, so Prism usually still “finds” the method, but with degraded confidence or duplicate edges.

Affected paths:

- `self` / `this` / `cls`: Python self arm narrows to same class, but wrapper + inner survive, so `self_owner_lookup_same_class` demotes when `same_class.len() > 1` at `src/resolution.rs:710-728`; the arm relabels to `SelfReceiver` at `src/resolution.rs:939-970`.
- Qualified owner / R3b: `C.helper()` or simple qualifier-as-owner uses `owner_lookup`, relabeled to `QualifierOwner` at `src/resolution.rs:1025-1034`; duplicate owner bucket demotes in `owner_lookup_in_modules` at `src/resolution.rs:761-779`.
- Typed receiver / R6 step 1: recovered receiver type uses `owner_lookup(recv_ty, name)` at `src/resolution.rs:1101-1118`, so decorated-method duplicates demote.
- Unknown receiver / R6 residue: receiver syntax with only one local owner still returns demoted candidates at `src/resolution.rs:1158-1227`; duplicates inflate that candidate set.
- Free local calls: local free decorated functions can produce two Exact `local_def` edges at `src/resolution.rs:1235-1248`.

The pydantic figure in the sibling spec is the right sizing anchor: ~418 of ~2,066 class methods, about 20%, are decorated, and the spec notes this affects `self.validator()`, `obj.prop()`, and `C.helper()` broadly at `docs/superpowers/specs/2026-06-22-python-js-self-receiver-samefile-narrowing.md:310-321`. I did not remeasure pydantic in this clone.

**Blast Radius**

Changing this at extraction affects:

- Function table and AST collection: `ParsedFile::all_functions`, `build_function_table`, and reconstruction at `src/ast.rs:274-370`; query/manual drift tests at `src/ast.rs:5253-5334`; manual fallback at `src/ast.rs:464-475`.
- Call graph identity: `functions`, `calls`, `callers`, `methods`, `method_owners`, `method_class_span`, `receiver_vars`, `method_facts` fields at `src/call_graph.rs:143-225`; all three build paths cited above; incremental remove/merge at `src/call_graph.rs:1029-1103`.
- Resolution: `owner_lookup_in_modules`, `self_owner_lookup_same_class`, R3b, typed receiver, R6 residue, unqualified local free calls, and `resolved_caller_edges` at `src/resolution.rs:710-780`, `939-970`, `1025-1034`, `1101-1227`, `1235-1248`, `1327-1344`.
- CPG: function nodes and indexes are built from `cg.functions` at `src/cpg/build.rs:327-359`; call/return edges resolve by `(file,name,start_line)` at `src/cpg/build.rs:653-707`; arg-to-param edges use callee `FunctionId` and parameter lookup at `src/cpg/build.rs:744-845`.
- DFG: `DataFlowGraph::build` also iterates `parsed.all_functions()` at `src/data_flow.rs:235-241`, so global extraction changes can alter variable/function_start_line keys.
- Navigation: `NavigationIndex` line/name indexes at `src/navigation/mod.rs:43-79`; seed ambiguity at `src/navigation/seed.rs:34-83`; `nodes_at`, `callers`, `callees`, and `ego` consume these identities in `src/navigation/queries.rs`.
- Inventory: already has a local dedup at `src/navigation/inventory.rs:34-49`.
- Framework/decorator consumers: FastAPI and Flask helpers accept either wrapper or inner via `decorated_definition_node` at `src/frameworks/python/fastapi.rs:130-158` and `src/frameworks/python/flask.rs:48-70`, `192-198`; Python taint currently skips inner decorated functions at `src/algorithms/taint.rs:4374-4377`, then unwraps wrapper params at `src/algorithms/taint.rs:4766-4778`.
- Reasoning: scope honesty already filters Python decorated inner functions and canonicalizes wrapper roots at `src/reasoning/scope_honesty.rs:176-194`.

**Options**

A. Fix at extraction / canonical function identity.

Use one logical Python function for decorated functions, preferably the inner `function_definition`.

Why inner: inventory already chooses inner over wrapper (`src/navigation/inventory.rs:34-49`), parameter extraction works on inner nodes (`src/ast.rs:3881-3932`), and decorator-aware consumers can climb to the parent wrapper as FastAPI/Flask already do. Keeping the wrapper as canonical would preserve decorator-line span, but it risks empty parameter names because `find_parameters_node` does not unwrap `decorated_definition`.

Implementation shape: add a central “logical functions” path that filters Python inner/wrapper pairs to the inner node, then route CallGraph, DFG, CPG assembly inputs, and inventory through it. Do not blindly change all `all_functions()` consumers unless each decorator consumer is audited. If `all_functions()` itself changes, Python taint’s `python_is_inner_decorated_function` skip must be removed or it will drop decorated routes.

Trade-off: highest correctness, fixes self/R3b/R6/free calls and graph duplication at the source. Broader blast radius, requires cache version bump and careful tests around decorator-line navigation.

B. Fix at resolution/index.

Collapse wrapper+inner candidates before classification. For candidates with same `(file, name, owner)` where one span contains the other and the outer is a Python `decorated_definition`, keep the inner. Apply before `exact`/`demoted` in `owner_lookup_in_modules`, `self_owner_lookup_same_class`, R6 residue, and free local resolution.

Trade-off: narrower and cheaper for call confidence, but it is a band-aid. It does not remove duplicate `FunctionId`s from `functions`, CPG nodes, DFG keys, navigation seed ambiguity, inventory workarounds, or exact duplicate local free edges unless every resolver arm is patched. It also needs source/AST access or a side index to know which span is a wrapper.

C. Build a canonical ID alias map.

Keep raw captures, but add `canonical_function_id: BTreeMap<FunctionId, FunctionId>` or canonicalize on insertion into graph indexes. Wrapper maps to inner. All call graph maps store canonical IDs; raw AST consumers can still inspect wrappers.

Trade-off: more explicit and migration-friendly than globally changing `all_functions`, but more machinery. Every map keyed by `FunctionId` must be canonicalized consistently, or bugs become harder to reason about.

**Recommendation**

Take Option A, but as a scoped canonical extraction API rather than a blind global rewrite.

Add a `ParsedFile` helper with an explicit name like `logical_functions()` / `callable_definitions()` that returns one node per logical callable and filters Python `decorated_definition` wrappers in favor of the inner `function_definition`. Use it first in `CallGraph` and `DataFlowGraph`, then delete the navigation inventory’s local workaround or make it consume the same helper. Keep raw tree scanning available for framework/decorator analysis.

Thin slice:

1. Add canonical helper and tests:
   - Python decorated free function: raw query has 2, logical has 1 inner.
   - Python decorated method: logical ID is `def` line, owner and class span still populate.
   - Nested same-name ordinary functions remain two.
   - JS/TS decorated methods remain one.
2. Change CallGraph builders to use logical functions in both definition and call-site passes.
3. Change DFG to use logical functions so CPG variable keys match canonical function starts.
4. Remove or simplify inventory dedup after it uses the same helper.
5. Add resolution fixtures that fail pre-change:
   - `self.helper()` on `@staticmethod`: one Exact `self_receiver`.
   - `C.helper()` / typed receiver / unknown receiver: one candidate, not duplicate NameOnly.
   - free `@dec def helper()` local call: one Exact `local_def`, no multi-target exact.
   - negative: two distinct same-name methods in nested classes do not collapse.
6. Add canaries:
   - FastAPI/Flask decorated route detection still works.
   - Python taint decorated route source detection still works.
   - JS/TS decorator fixture byte-stable.
   - Rust/Go call-stats byte-identical.

Acceptance signal: pydantic `kind_exact` rises and `kind_nameonly` falls for decorated-method paths; `multi_target_exact_sites` drops for local decorated free calls; Tier-A matrix/quick and full `cargo test` pass. Per AGENTS, because this touches call resolution/navigation/CPG, run `cargo build --release`, `cd eval && uv run tier-a --matrix-only --allow-stale-sut`, `cd eval && uv run tier-a --quick --allow-stale-sut`, then full tests.

**Risks / Unknowns**

- Decorator-line navigation changes if canonical span starts at `def` instead of `@decorator`. Decide explicitly whether `nodes_at` on a decorator line should return the function; if yes, add a separate decorator-line-to-function index rather than keeping duplicate `FunctionId`s.
- Python taint currently assumes wrappers survive and skips inner decorated functions. This must be adjusted if graph/DFG canonicalization shares the same helper.
- `@property` reads are not call expressions, so this slice improves `obj.prop()`-style calls, not bare property access.
- JS/TS simple method decorators are single-capture today, but decorated class-field arrow functions may have separate gaps; defer unless a fixture proves double-capture.
- I ran targeted verification and one inventory test, not the full suite, because this was a read-only architecture task.


