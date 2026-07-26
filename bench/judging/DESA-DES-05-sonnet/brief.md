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

# Analysis + Architecture Memo: Decorated/Wrapped-Definition Double-Capture

**Status:** verified live (fixture + real corpus), read-only, no code changes made.
**Scope finding upfront:** the defect is **not Python-decorator-specific**. It is a general "wrapper node + inner node both independently captured as a function" defect. Exactly **2 of prism's 11 languages** have this shape today: **Python** (`decorated_definition` wrapping `function_definition`) and **C++** (`template_declaration` wrapping `function_definition`). **JS/TS decorators do not reproduce it** — verified below, refuting that part of the seed hypothesis.

---

## 1. Verification

### 1.1 Root cause

`Language::function_node_types()` (`src/languages/mod.rs:85-112`) is the per-language manifest of tree-sitter node kinds that count as "a function." Two of the eleven arms list a **container kind together with the kind it contains**:

```rust
Self::Python => vec!["function_definition", "decorated_definition"],   // :87
Self::Cpp    => vec!["function_definition", "template_declaration"],   // :105
```

Both the query path (`function_query`, `src/queries.rs:92-97`, `(function_definition) @func` and `(decorated_definition) @func` as separate alternatives) and the manual-walk fallback (`ParsedFile::collect_functions_manual`, `src/ast.rs:466-475`, unconditional `if types.contains(&node.kind()) { out.push(node) }` then unconditional recursion into children) match **both** the wrapper and the nested inner node for the same syntactic unit — because a decorated/templated function's tree literally is `decorated_definition|template_declaration → ... → function_definition`, and tree-sitter queries have no "don't also match ancestors of an already-matched node" concept.

`build_function_table()` (`src/ast.rs:347-371`) maps every result 1:1 into a `FunctionInfo` with no dedup. `CallGraph::build_skeleton`/`build` (`src/call_graph.rs:277-327`, `:484-531`) turn each `FunctionInfo` into a `FunctionId { file, name, start_line, end_line }` (`src/call_graph.rs:20-25`) — **line-range-keyed**, so the wrapper (spans the decorator line through the end) and the inner (spans the `def`/signature line through the end) get **distinct** `FunctionId`s despite being the same logical method.

`Language::function_name` (`src/languages/mod.rs:908-918`) and `Language::method_owner`/`method_owner_class_node` (`:1084-1100`, `:1179-1197`) already **normalize toward the inner node** when handed the wrapper (walk to the `function_definition`/find the class from there) — so both captures resolve to the **identical** `(name, owner, method_class_span)`. This is exactly what produces same-class, same-name, ≥2-candidate collisions rather than two unrelated methods.

**Prior art that proves the project already knows this shape exists:** `src/navigation/inventory.rs:34-55` has a hand-rolled O(n²) span-containment dedup, gated by `outer.kind == "decorated_definition"` (line 47) — but it is **hardcoded to Python only**, and it feeds **only** the one-off Tier-A `functions_inventory()` count (used by `tests/navigation/inventory_test.rs`), which is **not** consumed by `CallGraph`, `resolution.rs`, or the CPG. The actual resolution/navigation stack has no such guard. `src/algorithms/taint.rs:4753-4758`, `src/type_provider.rs:351`, `src/type_providers/python.rs:138,295`, `src/frameworks/python/{fastapi,flask}.rs`, and `src/reasoning/scope_honesty.rs:344-370` all independently special-case "is this `decorated_definition`, drill into the inner" or "is this the inner `function_definition` whose parent is `decorated_definition`" — at least **six** separate reimplementations of the same normalization, none of which touch the `FunctionId`/`CallGraph` layer.

### 1.2 Live reproduction (minimal fixture)

```python
# /tmp/decorator_repro/app.py
class Widget:
    @staticmethod
    def helper(x):
        do_thing(x)
        return x

    def caller(self):
        return self.helper(1)

def do_thing(x):
    return x
```

`prism nav callers --symbol do_thing` returns **two** `helper` results — one `Function{start_line:2,end_line:5}` (the `decorated_definition` wrapper) and one `{start_line:3,end_line:5}` (the inner `function_definition`) — both `score:1.0`, both `"CalledBy":{"caller":"helper","call_site_line":4}`, both `kind: local_def`. **One line of source, two "callers of `do_thing`."**

`prism nav callees --symbol caller` (i.e. resolving `self.helper(1)`) returns the **same two** `helper` nodes, both at `score:0.6` (`self_receiver`, NameOnly) — the callee-side ambiguity the sibling spec's §9 anticipated, reproduced directly.

`prism nav nodes-at --location app.py:2` (the decorator line) resolves to the wrapper `Function{2,5}`. `nodes-at --location app.py:3` (the `def` line) resolves to the inner `Function{3,5}` **plus** an unrelated `Variable` node for the parameter. These are **disconnected node identities** for what a consumer would call "the `helper` method" — which node you get depends on which line you click.

`call-stats` on this 2-real-call-site fixture reports **`total_call_sites: 3`** (`kind_exact.local_def: 2` for the doubled `do_thing` call, `kind_nameonly.self_receiver: 2` for the doubled `self.helper(1)` targets). This is the **caller-side** defect the spec's §9 did not anticipate: `CallGraph::build*`'s Phase 2 (`src/call_graph.rs:330-374`, `:653-707` full build) iterates `parsed.all_functions()` **again** to harvest call sites, using each captured node's own byte range as the call-site query window (`ParsedFile::function_calls_with_spans_on_lines`, `src/ast.rs:3508-3549`, `cursor.set_byte_range(func_node.byte_range())`). Since the wrapper's range **strictly contains** the inner's, every call inside a decorated/templated body is captured **twice**, attributed to **two different caller `FunctionId`s**. This inflates `total_call_sites`, doubles "callers of X" for anything called from inside such a body, and — because the R4 local-free-function arm (`src/resolution.rs:1240-1248`) returns `exact()` for **all** local matches with no `len()==1` gate — can mint **duplicate full-confidence Exact edges**, not just NameOnly ones.

### 1.3 C++ confirmed via the same mechanism

```cpp
int doThing(int x) { return x; }
template <typename T> T helper(T x) { doThing(x); return x; }
int caller() { return helper(1); }
```

`call-stats`: `total_call_sites: 3` for 2 real call sites; `kinds.local_def: 4` (both `doThing` and `helper` doubled — `helper` itself is a free function here, so it hits the ungated R4 arm and mints 2 duplicate Exact edges). `callers --symbol doThing` returns two `helper` entries (`{5,9}` wrapper `template_declaration`, `{6,9}` inner `function_definition`). **Identical defect shape, different language, different wrapper kind.**

### 1.4 JS/TS refuted

```ts
class Widget {
  @staticDecorator
  static helper(x: number): number { doThing(x); return x; }
  caller(): number { return Widget.helper(1); }
}
```

`call-stats`: `total_call_sites: 2` (correct), `callers --symbol doThing` returns **exactly one** `helper`, `Widget.helper(1)` resolves **Exact** (`qualifier_owner`), no NameOnly. Confirmed by grep: `src/algorithms/taint.rs:2292-2304` treats JS/TS `decorator` nodes as **siblings** of the class member (`for child in node.children(...) if child.kind()=="decorator"`), not a wrapping parent — tree-sitter-javascript/typescript never introduces a container node for a decorated method. `function_node_types()` for JS/TS/Tsx (`:88-101`) lists no such wrapper. **The task's premise that JS/TS decorators double-capture is false; the real second language is C++, via templates, not decorators.**

### 1.5 Real-corpus sizing (pydantic @ `c9688f493b05`, live measurement)

This exact worktree already has the sibling same-class-narrowing fix shipped (commits `c2ed1f3`…`7e9ad6f` are on HEAD). Running `call-stats` on the full pydantic repo:

| metric | value (this HEAD) |
|---|--:|
| `total_call_sites` | 65,858 |
| `kind_exact.self_receiver` | 740 |
| `kind_nameonly.self_receiver` | **759** |
| `multi_target_exact_sites` | 439 (`local_def`: 387, `import_qualified`: 52) |

The spec's pre-1a baseline was 1,316 `self_receiver` NameOnly; post-1a it's 759 — confirming the cross-file-collision subset (~557) is already fixed, and the **759 residue is exactly the case-(c) bucket the spec flagged as unfixed** (decorated wrapper+inner, `@overload` stub+impl, static+instance dup).

Independent AST-based measurement (this exact commit, `pydantic/` package only, excluding `tests/`):

```
total class methods: 1142
decorated methods:    349   (30.6%)
  classmethod: 210, staticmethod: 41, property: 40, overload: 35,
  deprecated: 24, field_validator: 4, cached_property: 4, ...
```

**30.6%** of class methods are decorated (higher than the spec's ~20% repo-wide figure — package-only view, or churn since the snapshot). Of the 349, **~300 (86%)** are `classmethod`/`staticmethod`/`property`/`validator`/`field_validator`/`cached_property` — the genuine wrapper+inner double-capture case this memo targets. `@overload` (35, ~10%) is a **different**, legitimate same-class-same-name duplicate (stub + impl are really two definitions) that should **continue** to demote — not something this fix should touch or could accidentally "fix away."

I could not cleanly attribute the exact fraction of the 759 residual NameOnly sites to decorator-double-capture vs. `@overload` vs. static+instance dup without runtime instrumentation (out of scope for a read-only pass); the decorator-density numbers above are the closest available proxy. **Acceptance for any fix should re-measure the actual split**, exactly as the sibling spec's own §6 does — do not assert a number now.

---

## 2. Impact sizing

Two structurally distinct failure modes, both stemming from the same root cause:

**(a) Callee-side ambiguity (precision loss, previously documented in spec §9).** Any resolution rung that reaches `owner_lookup`/`owner_lookup_in_modules` (`src/resolution.rs:692-708`, `:737-781`) or `self_owner_lookup_same_class` (`:710-735`) for a decorated/templated method's `(owner, name)` key gets **≥2 candidates with the same primary owner** → `demoted(..., QualifiedOwner)` (`:776`) → NameOnly. This hits **every call shape** that reaches those helpers, not just self-calls: the `self`/`this`/`cls` arm (`:939-970`), the `Self::` arm (`:876-887`), R1 `T::m`/`mod::T::m` via `owner_lookup_in_modules` (`:890-896`), R3b qualifier-as-owner-key (`:1025-1035`), R4b Java/C++ implicit-`this` (`:1285-1303`), and R6's receiver-typed `owner_lookup(recv_ty, name)` (`:1101-1118`). Recall is not lost (both candidates are kept, demoted) — this is pure precision degradation, exactly as the sibling spec characterized it.

**(b) Caller-side duplication (a distinct, previously-undocumented failure mode, found during this verification).** `CallGraph`'s call-site harvesting phase (`src/call_graph.rs:330-374` skeleton, `:653-707` full build) treats **every captured function node** — wrapper and inner alike — as its own "caller scope" and re-scans for calls within that node's own byte range. Because the wrapper's range is a strict superset of the inner's, **every call inside a decorated/templated body is recorded twice**, under two different caller `FunctionId`s. This is not an ambiguity problem — it's raw duplication, and unlike (a) it also corrupts **Exact** edges: the R4 local-free-function arm (`:1240-1248`) has no `len()==1` gate, so a decorated/templated **free** function's internal calls mint literal duplicate full-confidence Exact edges (confirmed: `kind_exact.local_def` doubled in both fixtures). This inflates `total_call_sites`, doubles "callers of X" fan-in for anything called from inside such a body, and is very plausibly a real (if not yet corpus-measured) contributor to pydantic's `multi_target_exact_sites` (439, of which 387 are `local_def`-kind) — that counter is described in `src/navigation/queries.rs:180-186` as measuring "same-bare-name owner-key collisions," but a decorated/templated free function's doubled `local_def` is a second, distinct contributor to the same counter that the existing comment doesn't account for.

Distinguishing precision from recall: (a) is precision-only (both candidates are legitimate, correctly kept, just not disambiguated). (b) is a correctness bug independent of precision/recall framing — it fabricates call-graph structure that doesn't exist in the source (phantom duplicate callers, inflated counts, sometimes-wrong Exact confidence on an edge that should have been NameOnly-or-Exact-once).

---

## 3. Blast radius

**Confirmed by direct reproduction:**
- `src/resolution.rs` — every owner-lookup-based rung listed in §2(a); demotes decorated/templated method calls to NameOnly.
- `src/resolution.rs:1240-1318` (R4/R4.5/R5 free-function arms) — decorated/templated **free** functions produce duplicate Exact or NameOnly-FreeMulti edges (a distinct duplicate-edge failure mode, not ambiguity).
- `src/call_graph.rs` Phase 2 / `cg.calls` + `cg.callers` (both `build_skeleton` and full `build`) — every call site inside a decorated/templated body double-recorded under two caller identities.
- `src/cpg/build.rs:327-360` (Step 1, one `CpgNode::Function` per `FunctionId` — literally two graph nodes per decorated/templated method) and `:653-707` (Step 5, Call/Return edges) — doubled node count and doubled/fanned-out edges for any decorated/templated method, on both the caller and callee side simultaneously when both endpoints are decorated.
- `src/navigation/queries.rs` (`nodes-at`/`callers`/`callees`, exercised above) — position-anchored lookups land on different, disconnected `Function` identities depending on the exact queried line (decorator/template line vs. signature line).
- `src/navigation/inventory.rs:34-55` — has a **partial** fix already, but it is Python-only (hardcoded `"decorated_definition"`) and feeds only the Tier-A one-off count, not the resolver/CPG; it would **not** catch the C++ template case (verified: the `wrapper` check is a literal string match against `"decorated_definition"`).

**Traced (code-level, not runtime-verified — flagged per severity discipline as PLAUSIBLE, not CONFIRMED):**
- `src/algorithms/horizontal_slice.rs:73-88` — iterates `all_functions()` to find "peer" functions for consistency-slicing; `PeerPattern::NamePattern` and (if reachable for Python) `PeerPattern::ParentClass` (`:147-179`) both call `function_name`/inspect `func_node.parent()`, which normalize identically for wrapper and inner — a decorated peer would be pushed to the `peers` vec **twice**, adding duplicate/overlapping preview lines to the slice output. (Note: `PeerPattern::Decorator` itself, `:149-169`, is accidentally immune — it text-scans lines *above* `func_node.start_position()`, and the wrapper's start position *is* the decorator line, so the wrapper never matches that specific pattern. Only `NamePattern`/`ParentClass` are at risk.)
- `src/algorithms/{contract_slice,peer_consistency_slice,primitive_slice,resonance_slice,spiral_slice,symmetry_slice}.rs`, `src/data_flow.rs:235`, `src/react_hooks.rs:128`, `src/reasoning/seeds.rs:224` (`functions_named` — duplicate seed candidates for decorated/templated names feeding slice witnesses) — all iterate `all_functions()` directly; not individually verified this pass.
- Everything downstream that consumes `resolved_caller_edges`/CPG call edges as slice witnesses — per this project's own categorization (CLAUDE.md), the "graph-based" algorithms (`barrier_slice`, `taint`, `spiral_slice`, `circular_slice`, `vertical_slice`, `threed_slice`, `delta_slice`, `conditioned_slice`, `gradient_slice`, `provenance_slice`, `phantom_slice`, `resonance_slice`, `membrane_slice`, `echo_slice`) all read `CpgContext`/`CallGraph`, so all inherit the doubled-node/doubled-edge structure whenever a decorated/templated method is anywhere in their slice.

**Already immune (operate on raw tree-sitter nodes independent of `FunctionId`/`all_functions()`, so a fix at the extraction layer is orthogonal to them):**
- `src/reasoning/scope_honesty.rs:339-370` (`is_decorated_definition_body`, `is_nested_callable_boundary`) — has its own explicit workaround so it doesn't misclassify the wrapper/inner nesting as "an unmodeled nested callable scope." Independent traversal via `function_node_spanning`, not `all_functions()`.
- `src/type_provider.rs:351`, `src/type_providers/python.rs:138,177,295`, `src/frameworks/python/{fastapi,flask}.rs` — each independently drills from wrapper to inner (or scans wrapper children for decorator names) via raw `.children()`/`.parent()` walks, not via the `FunctionId` layer.

**Test/config surface that must move with any fix:**
- `src/ast.rs:5253` (`all_functions_reconstructed_matches_direct_query_per_language`) — the eager-vs-live-query invariant canary. No decorator/template case in its fixture list today; must gain one so the dedup is locked into the invariant rather than just spot-checked.
- `src/cpg_cache.rs:66` (`CACHE_VERSION: u32 = 21`) — must bump; the on-disk cache format encodes function counts/spans that change shape.
- `tests/navigation/inventory_test.rs:4` (`test_python_decorated_function_emits_one_record`) — already encodes the desired *observable* behavior at the inventory layer; a source-layer fix makes `inventory.rs`'s own dedup loop (`:37-55`) redundant (worth removing in the same change to avoid two copies of the same logic silently drifting apart — the C++ gap is exactly that kind of drift).

---

## 4. Architecture options

### Option A — Fix at extraction: filter the wrapper out of `all_functions()` (RECOMMENDED)

Add one per-language predicate, `Language::is_function_wrapper(&self, node: &Node<'_>) -> bool`, mirroring the exact "does this wrapper have a direct `function_definition` child" check `function_name`/`method_owner` already perform (`src/languages/mod.rs:908-918`, `:1084-1090`):

```rust
pub fn is_function_wrapper(&self, node: &Node<'_>) -> bool {
    match self {
        Self::Python => node.kind() == "decorated_definition"
            && node.children(&mut node.walk()).any(|c| c.kind() == "function_definition"),
        Self::Cpp => node.kind() == "template_declaration"
            && node.children(&mut node.walk()).any(|c| c.kind() == "function_definition"),
        _ => false,
    }
}
```

Apply it as a `retain`/guard at the **two** places nodes are collected: `all_functions_via_tree()`'s query-result loop (`src/ast.rs:318-344`) and `collect_functions_manual`'s push (`:466-475`, guard the `out.push(node)`). The inner node keeps getting captured independently by its own query pattern (Python) or its own recursion step (both languages) — nothing needs to be added to *find* the inner, only to *drop* the outer.

Why the child-existence check, not a bare kind-name filter: a `decorated_definition` can wrap a `class_definition` instead (`@dataclass class Foo: ...`). That capture has **no** independent `function_definition` sibling capture — filtering all `decorated_definition` nodes unconditionally would silently **delete** decorated classes from the function inventory (a real, if debatable, pre-existing behavior this fix must not disturb). The child-existence check leaves that case untouched (no sibling match to prefer, so nothing is dropped) while collapsing the true wrapper+inner duplicate pairs. Same reasoning covers C++ `template_declaration` wrapping a `class_specifier`/`struct_specifier` (template classes) vs. wrapping `function_definition` (template functions) — the check naturally discriminates.

Why prefer the **inner** node as canonical, not the wrapper: every existing normalization helper in the codebase already drills from wrapper→inner (§1.1's "six reimplementations"), so this is the path of least resistance, not a new convention. It also means an **undecorated/untemplated** function's `FunctionId.start_line` is already "the `def`/signature line" — preferring inner keeps decorated/templated functions' span semantics **consistent** with every other function in the corpus (both start at the signature), whereas preferring the wrapper would shift `start_line`/`start_byte` for ~20-30% of Python methods and be the odd one out.

**What this fixes, in one place:** callee ambiguity (§2a), caller-side call-site duplication (§2b), CPG duplicate nodes/edges (§3), `nodes-at` identity split (§1.2), and — as a side effect, not a separate patch — `horizontal_slice.rs`'s traced duplicate-peer issue, since it too reads `all_functions()`.

**Blast radius / risk:** touches the single most fundamental function-enumeration primitive, used by ~20 files (§3's full list) — but every one of those files already treats "a function node" as an opaque, self-contained unit (name/owner/span), and none of the confirmed-immune consumers depend on receiving the wrapper specifically (they walk to it via `.parent()` when they want decorator text, which still works once the wrapper is merely *not separately enumerated* — the wrapper node still exists in the parse tree, it's just not independently yielded by `all_functions()`). Requires `CACHE_VERSION` bump, the canary-test extension, and (ideally) removing the now-redundant `inventory.rs` dedup loop in the same change so the fix has exactly one home instead of two copies that can drift (as they already have, since `inventory.rs`'s copy never covered C++).

### Option B — Fix at resolution/index: collapse wrapper+inner in `CallGraph`'s maps only

Instead of touching `all_functions()`, dedup at the point `methods`/`functions`/`method_owners`/`method_class_span` are populated in `call_graph.rs` (or as a post-`build()` pass): when two `FunctionId`s share `(file, name, owner)` [or `(file, name)` for free functions] and one's span contains the other's, keep only the inner in those index maps.

**What this fixes:** callee ambiguity only (§2a) — a same-class self-call now sees 1 candidate instead of 2, so it resolves Exact.

**What it does NOT fix, which the sibling spec's original framing ("less invasive but a band-aid?") did not anticipate because it predates this verification pass's caller-side finding:** `cg.calls`/`cg.callers` are populated in **Phase 2**, directly from `parsed.all_functions()`, independent of the `methods`/`method_owners` maps this option touches — so `total_call_sites` inflation, doubled "callers of X," and the duplicate-Exact-edge bug (§2b) all **survive untouched**. The CPG still builds two `CpgNode::Function`s (Step 1 reads `cg.functions`, which Option B leaves alone) and still emits doubled Call/Return edges. `nodes-at` still splits identity by line. This option is strictly narrower than what the problem actually is — it treats the symptom the spec's authors could see (NameOnly demotion) without touching the mechanism that generates it (duplicate `FunctionId`s reaching every consumer of `cg.functions`/`cg.calls`, not just `cg.methods`).

**Where it would still be worth having:** if Option A's blast radius across ~20 files proves too risky to land atomically, Option B is a legitimate **first increment** — it buys back the precision loss (§2a, the larger, corpus-measurable number) immediately, cheaply, with a much smaller diff (confined to `call_graph.rs`/`resolution.rs`), while Option A's broader fix follows as a second, separately-reviewable change that additionally cleans up §2b/§3. It does not generalize to C++ automatically unless the same containment check is duplicated here too — a second place that can drift out of sync with `ast.rs`, exactly the failure mode that let the C++ case go unnoticed this long.

### Option C (considered, rejected) — prefer the wrapper node instead of the inner

Symmetric to Option A but keeps the `decorated_definition`/`template_declaration` node and drops the inner. Rejected: shifts `FunctionId.start_line`/`start_byte` for every decorated/templated function relative to today's *inner-preferring* helpers (`function_name`, `method_owner`), i.e. it would require rewriting six existing normalization call sites instead of leaving them alone, and produces a span that starts at the decorator/template line — inconsistent with every non-decorated function's span (which starts at the signature). No consumer inspected in this pass wants the wrapper as the *primary* identity (only as something to reach *from* the inner via `.parent()` when decorator text is needed) — so this option buys nothing Option A doesn't, at a larger and more surprising diff.

---

## 5. Recommendation + slice outline

**Recommend Option A**, landed as a single self-contained slice (not split into A-then-B) — the caller-side duplication (§2b) is at least as consequential as the callee-side ambiguity the sibling spec sized, and Option B provably cannot reach it, so shipping B first would mean re-touching the same territory almost immediately for marginal benefit. The fix itself is small (one new `Language` method, two call sites in `ast.rs` gated by it) even though the *consumers* are numerous — the numerosity is exactly why fixing it once upstream, rather than once per consumer, is the cheaper sound design.

**Thin-slice plan:**

1. `src/languages/mod.rs` — add `is_function_wrapper` (Python: `decorated_definition` + direct `function_definition` child; C++: `template_declaration` + direct `function_definition` child; else `false`).
2. `src/ast.rs` — gate `all_functions_via_tree()`'s query-loop push and `collect_functions_manual`'s push on `!is_function_wrapper`. This is the **only** change needed to `build_function_table`, `CallGraph::build*`, and the CPG — they all consume `all_functions()`/`functions()` unchanged and automatically see one `FunctionInfo`/`FunctionId`/`CpgNode::Function` per method.
3. `src/cpg_cache.rs:66` — bump `CACHE_VERSION` 21→22 with a one-line comment matching the existing style.
4. `src/ast.rs:5253` — extend `all_functions_reconstructed_matches_direct_query_per_language` with a Python-decorated-method case and a C++-templated-function case (each asserting `direct.len()` equals the *undoubled* count, closing exactly the "anti-vacuous" gap this bug lived in).
5. `src/navigation/inventory.rs:34-55` — remove the now-redundant dedup loop (or, if the maintainers prefer defense-in-depth, generalize it to use `is_function_wrapper` too so it can't drift from the source-of-truth fix again).
6. New tests (unit-level, hand-built where possible, mirroring the sibling spec's own testing philosophy): `methods[(owner,name)]` has exactly one entry for a decorated Python method / templated C++ function; a `@staticmethod` self-call resolves **Exact** (the exact case cited in the seed problem statement); `cg.calls`/`total_call_sites` for a small decorated/templated fixture matches the *textual* call count, not double it; CPG node count for a file with one decorated method is 1, not 2; `nodes-at` at the decorator/template line and at the signature line — **decide and test the intended behavior explicitly** (most likely: decorator-line query now finds no function node, or falls through to the enclosing class — whichever the implementation naturally produces, assert it, don't leave it accidental); a `@overload`-stub-plus-impl fixture and a static+instance-same-name fixture **must still demote** (proving this fix doesn't over-collapse genuine duplicates); a Go/Rust/Java/JS/TS fixture asserting **byte-identical** call-stats before/after (since `is_function_wrapper` is `false` for all of them, this is a clean, strong no-op gate).
7. Acceptance, using this session's already-captured pydantic baseline (§1.5) as the "before": measure `kind_exact.self_receiver` rise / `kind_nameonly.self_receiver` fall (do not assert a fixed target — report the actual split, per the sibling spec's own §6 discipline); measure `total_call_sites` drop (a genuinely new signal this fix introduces that the sibling slice didn't have); sample `multi_target_exact_sites`' `local_def`-kind subset (387 today) for reduction; run a C++-heavy corpus (the repo's own `eval/` harness presumably has one, or clone a template-heavy project) for the analogous C++ buy; Tier-A `--matrix-only --allow-stale-sut` zero regressions; `cargo test` green; `cargo fmt --check` clean.

**Explicitly deferred:**
- `@overload`/static+instance same-class duplicates continuing to demote — correct, unrelated, do not touch (verified the `is_function_wrapper` design naturally leaves them alone).
- Method-kind resolution (picking a specific `@overload` variant, or getter-vs-setter `@property`) — out of scope, same boundary the sibling spec drew.
- A full re-audit of all 11 languages' grammars for *other*, not-yet-discovered wrapper-node shapes beyond the two found here (Java annotations, Rust attribute macros, etc.) — this pass verified the *current* `function_node_types()` table exhaustively (only Python + C++ have overlapping entries today), not the grammars' full node vocabularies against future tree-sitter version bumps.
- Deep per-algorithm verification of the "traced but not runtime-verified" consumers in §3 (`horizontal_slice.rs` and the other eight `all_functions()` callers) — Option A very likely fixes them for free (they read the same now-deduped `all_functions()`), but should get a regression test each rather than be assumed fixed.

---

## 6. Risks / unknowns

- **API behavior change is user-visible.** `ParsedFile::all_functions()`/`.functions()` cardinality shrinks for ~20-30% of Python methods and templated C++ functions; a click/query at the decorator or `template<...>` line will resolve differently (likely: no function, or the enclosing class) than it does today. This is a deliberate trade, but worth a clear PR/changelog note since it's an observable navigation behavior change, not just an internal refactor.
- **I verified "only Python + C++ overlap" via a static read of `function_node_types()`, not via fuzzing every grammar's node vocabulary.** A future tree-sitter grammar bump could introduce a similar shape elsewhere (e.g., if a Rust attribute-macro wrapper node were ever added to `function_node_types()`) without this fix's `is_function_wrapper` being updated in lockstep — the design is easy to extend (one match arm), but nothing currently detects the *absence* of coverage automatically. Consider whether `all_functions_reconstructed_matches_direct_query_per_language`'s "anti-vacuous" pattern should grow a general assertion (no two same-file, same-name, containment-related function captures survive) across *all* language fixtures, not just the two now known to need it.
- **`data_flow.rs`'s per-function DFG scoping** (`src/data_flow.rs:235`) was flagged as a consumer but not runtime-verified this pass — it's plausible that a decorated method's data-flow analysis today runs twice (once scoped to the wrapper's byte range, once to the inner's), and I don't know whether that produces silently-duplicated def-use edges, a crash, or is coincidentally harmless. Verify at implementation time before assuming Option A is a pure win for the data-flow layer.
- **Sizing precision:** I could not isolate, without runtime instrumentation, exactly what share of pydantic's 759 residual `self_receiver` NameOnly sites (measured live, this HEAD) is decorator-double-capture vs. `@overload` vs. static+instance dup. The 30.6%-decorated / 86%-double-capturable proxy (§1.5) is the best available stand-in; treat any specific "precision buy" number before implementation as an estimate, and let the acceptance step's direct before/after measurement be authoritative — consistent with the sibling spec's own "measure, don't assert" acceptance discipline.
- **Caller-side inflation magnitude is demonstrated mechanistically (50% inflation in a 2-call-site fixture) but not sized at corpus scale.** It depends on what fraction of a codebase's total call sites originate from inside decorated/templated bodies — plausibly small-to-moderate corpus-wide (decorated methods, especially `@property`/validators, tend to be short), but this is an open question requiring an actual before/after diff, which a read-only pass cannot produce.
