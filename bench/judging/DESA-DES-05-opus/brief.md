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

Memo written to `docs/superpowers/specs/2026-07-04-python-decorated-method-double-capture-analysis.md`. Read-only — no source touched. Here's the substance.

## Verification (confirmed, with one correction to the §9 seed)

The double-capture is **real and Python-only**:
- `src/queries.rs:92-97` — the Python Functions query captures **both** `(function_definition)` and `(decorated_definition)`. Both survive as `FunctionId`s (`src/call_graph.rs:20-25`) sharing `(file, name, owner, end_line, class_span)` and differing **only in `start_line`** (decorator line vs `def` line). `function_name` (`languages/mod.rs:908-918`), `method_owner` (`:1084-1100`), and `method_owner_class_node` (`:1182-1197`) all normalize the wrapper onto the inner's name/owner/class-node — which is exactly why **1a's same-class narrowing can never separate them** (they land in its `≥2 → NameOnly` arm, `resolution.rs:724-728`).

**Correction to §9:** JS/TS do **not** double-capture — their query has no decorator-wrapper alternative (`queries.rs:98-115`); decorators are *child* nodes (proven by prism's own `taint.rs:2292-2299`). So this is a **Python-only** gate, and the buy is smaller than §9's "JS/TS similar" framing implied. **C++ templates** double-capture identically (`queries.rs:129-134`) — a parallel instance, deferred.

## Impact — bigger than §9 framed
Beyond the callee-side NameOnly demotes (`self.m()`, `Cls.m()`, cross-file free `helper()`), I found the **caller-side loop also iterates `all_functions()`** (`call_graph.rs:582-645`), so it attributes body calls to **both** the wrapper and inner caller IDs → **every call a decorated method makes is recorded twice**, plus decorator invocations (`@validator(...)`, `@app.route(...)`) become spurious call edges. And the **CPG mints two `Function` nodes** per decorated method (`cpg/build.rs:328-360`). It's all **precision, no recall loss** — both captures point at the same real method.

## Recommendation — Option A (skip the wrapper at index build)
Add a Python-only `if func_node.kind() == "decorated_definition" { continue; }` at the six `FunctionId`-minting loops in `call_graph.rs`, keeping the **inner**. This:
- fixes callee precision, caller-side doubling, decorator-edge pollution, and CPG node doubling **in one move**;
- leaves `all_functions()` and its AST consumers **untouched** — decisive, because `taint` relies on the *wrapper* (`taint.rs:4374-4375,4753-4758`) while `inventory` already dedups to the *inner* (`inventory.rs:34-56`, the reusable precedent). The wrapper node is wanted; only the second *`FunctionId`* is not — so fix at the id layer, not the AST (rules out Option C) and not the resolver (Option B misses the caller-side + CPG doubling).
- is recall-neutral (the inner is always captured; decorated *classes* already produce no id) and can only move `multi_target_exact_sites` **down**.

Thin slice: shared skip predicate across the 6 sites → `CACHE_VERSION` 21→22 → discriminating unit/free-fn/caller/CPG-node/merged-graph fixtures → pydantic `call-stats` (Exact↑, NameOnly↓, `total_call_sites`↓, canary flat/down) with Rust/Go byte-identical. Deferred: C++ templates, decorator-line `nodes-at`.

Key risk: **six edit sites** — miss one (esp. a caller loop or `build_direct_subset`) and the phantom returns on that path; guard with 1a's merged-graph (`extend`) test.
