# Conclusion-match grading — DES-02 (design/architecture), one anonymous arm

An engineer wrote the design memo below in response to the task brief. The
question was later SETTLED by the project's subsequent history. Grade the
memo against the settled outcome. You do not know who wrote it. Judge by
SHAPE and substance, not labels.

## Settled outcome (ground truth: the vindicated conclusion + repo evidence)

- conclusion: Recommend **Option A — a span-keyed class-hierarchy map on
  `CallGraph`** (`class_bases: BTreeMap<ClassId,…>`, `ClassId=(file,class_span)`),
  populated across all build paths, with a **conservative MRO policy: Exact only
  when the walk has a single unambiguous first provider; external/ambiguous bases
  are MRO barriers (drop, don't guess); full Python C3 is NOT required.**
- vindication evidence: slice 1b **landed on main** — `498482a feat(resolution):
  Slice 1b — inherited self/this depth-1 base resolution`. After 4 spec REWORKs it
  was deliberately narrowed to exactly the memo's conservative rule: `1df081d
  docs(slice1b): spec rev3 — narrow to DEPTH-1 direct base (sound by
  simplification)` and `2fb6457 … single-inheritance + tri-state + occurrence-clean
  bases`. Later matured via `5ba7b58 Improve Python inherited receiver resolution
  (#145)`. CONFIRMED: span-keyed hierarchy + "single unambiguous first provider /
  external = barrier" is what shipped; the landed depth-1 scope is the memo's
  conservative recommendation, not full MRO.
- proposed oracle: full marks = span-keyed (by class byte-span, NOT bare
  class-name — the memo flags name-keyed reuse would undo slice-1a's collision
  fix) hierarchy with a conservative single-first-provider / barrier rule and an
  explicit "C3 not needed for the thin slice." Fail = proposes full C3/MRO
  linearization or a bare-name `owner_lookup(base,name)` walk (the naive answer;
  repo narrowed away from both).

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

# Analyze + architect (xhigh, read-only): prism slice 1b — Python/JS inherited self-method resolution (MRO)

You are a senior static-analysis architect (codex gpt-5.5, xhigh). **Read-only.** Produce an ANALYSIS +
ARCHITECTURE memo (markdown). Cite `file:line`. Session cwd = the prism repo
(`/Users/wesleyjinks/code/slicing`, on `main` — includes the merged slice 1a: `method_class_span`,
`self_owner_lookup_same_class`, `method_owner_class_node`). Design only; no code.

## The slice
1a resolved `self.method()` when the **caller's own class defines** the method. **1b** adds the
**inherited** case: `self.method()` / `this.method()` where the method is defined on a **base class** —
resolve it by walking the class hierarchy (MRO). Today this is the `python/inherited_override` Tier-A
**expected_gap** (1a leaves it unresolved by design).

## Verify-first (do this, report numbers)
1. **Size it.** How many `self`/`this` calls currently drop (`unresolved_unknown_name`) because the method
   is inherited, in fastapi/pydantic/excalidraw? (Sample: classes with bases that call `self.X()` where X
   is on a base.) Framework code inherits heavily (Starlette/BaseModel) but much is EXTERNAL (base not
   in-repo) — distinguish **in-repo base** (1b-resolvable) from external (SCIP territory, NOT 1b). The buy
   is only the in-repo-base subset; quantify it (the 1a spec guessed "~10 fastapi" — verify).
2. **Confirm the hierarchy is extractable + how to plumb it.** Class-base extraction exists in the
   enrichment layer: `src/type_providers/python.rs:extract_bases`/`collect_methods_with_bases`,
   `src/type_db.rs:class_hierarchy` (`:186`), TS `extract_ts_bases`. But it is NOT in `CallGraph`. Confirm
   what it takes to make a `(class) -> [base classes]` map available at resolution time (a new CallGraph
   field populated at build, like `method_class_span`), and how the MRO walk hooks into the self arm /
   `owner_lookup` when same-class lookup misses.

## Deliver
- **Verification** (the in-repo-inherited size + the hierarchy-plumbing facts, with evidence).
- **Architecture options** (≥2): (A) plumb a class-hierarchy map into `CallGraph`, and in the self arm,
  when `self_owner_lookup_same_class` returns None, walk the caller-class's bases (same-file/same-module
  base first; respect the `(file, class-span)` identity 1a established) and retry `owner_lookup` per base;
  (B) narrower/alternative. Soundness (ambiguous multiple-inheritance → demote/NameOnly, not a wrong
  Exact; don't bind to an external base's same-named in-repo namesake), MRO order (Python C3 vs simple
  DFS — is full C3 needed or is DFS sufficient for resolution?), blast radius, risk.
- **Recommendation + thin-slice plan** (changes, discriminating tests incl. the `inherited_override`
  Tier-A case flipping ok, acceptance = the inherited-self buy + canary flat + Rust/Go byte-identical), +
  what to defer (external bases = SCIP; deep multiple-inheritance edge cases).
- **Risks / unknowns.**
Be opinionated; cheapest sound design. If the in-repo-inherited buy is small (likely, given framework bases
are external), SAY SO and recommend scope accordingly (it may be a small slice or fold into 2/3 priority).


## The memo to grade

**Prism Slice 1b Analysis + Architecture Memo**

**Verification**

Current 1a behavior is narrow and intentionally drops the 1b case. Python/JS/TS `self`/`this` calls enter the self arm at `src/resolution.rs:947`; for those languages it calls `self_owner_lookup_same_class` at `src/resolution.rs:964-966`, and a miss returns `UnknownName` at `src/resolution.rs:978`. That helper only accepts methods with the same caller file and exact class byte span, `src/resolution.rs:710-736`, which is why inherited methods are not resolved today.

Sizing result from the local bench checkouts: FastAPI `0cb4a8e`, Pydantic `363728f`, Excalidraw `0642e72`. I counted class methods calling `self.X()` / `cls.X()` / `this.X()` where `X` is absent on the caller class and present on an in-repo base class.

| corpus | in-repo inherited self/this calls | external / not 1b |
|---|---:|---|
| FastAPI | 12 | 13 obvious external framework-base calls |
| Pydantic | 4 | many external/stdlib/test/plugin bases; not reliable 1b buy |
| Excalidraw | 0 | React/external/own-class noise dominates |

FastAPI’s 12 are real and match the old “~10” guess: `APIKeyBase.check_api_key` called from three subclasses, `fastapi/security/api_key.py:47` and `:144`; `HTTPBase.make_not_authenticated_error` called from HTTP subclasses, `fastapi/security/http.py:87` and `:209`; `OAuth2.make_not_authenticated_error`, `fastapi/security/oauth2.py:401` and `:541`. External examples should stay out of 1b: `FastAPI(Starlette)` calls `self.add_route`, `fastapi/applications.py:42` and `:1120`; `_FrontendStaticFiles(StaticFiles)` calls Starlette methods, `fastapi/routing.py:1801` and `:1825`.

Pydantic’s 4 are real but small: `Secret(_SecretBase)` calls `self.get_secret_value`, `pydantic/types.py:1551`, `:1582`, `:1689`; `Config(BaseConfig)` calls `cls.get_field_info`, `pydantic/v1/env_settings.py:82` and `:96`, defined at `pydantic/v1/config.py:118`; `MultiHostDsn(AnyUrl)` calls inherited validators, `pydantic/v1/networks.py:315`, `:342`, `:423`, `:444`.

Excalidraw had no in-repo inherited `this.method()` buy in the inspected source. The in-repo `extends` cases are mostly constructors/`super` or no inherited `this` calls: `LocalFileManager extends FileManager`, `excalidraw-app/data/LocalData.ts:53`, with base methods in `FileManager.ts:70`; `HistoryDelta extends StoreDelta` uses `super.*`, `packages/excalidraw/history.ts:15-63`; `DurableIncrement/EphemeralIncrement` only call `super`, `packages/element/src/store.ts:476-490`.

One important correction: in this clone, `eval/fixtures/python/inherited_override` is not an inherited `self.method()` fixture. It is `c.go()` on an untyped parameter, `eval/fixtures/python/inherited_override/app.py:5-10`, with the expected gap explicitly tied to receiver typing, `eval/fixtures/python/inherited_override/expected.toml:4-8`. 1b should not claim that exact checked-in case unless the fixture is replaced with an inherited-self shape.

**Hierarchy Plumbing Facts**

The hierarchy facts exist, but not where resolver needs them. `CallGraph` has `methods`, `method_owners`, and the 1a `method_class_span` identity fields, `src/call_graph.rs:158-172`; the span is populated through `method_metadata`, `src/call_graph.rs:1865-1890`, and build sites such as `src/call_graph.rs:514-567`.

Python provider extraction already reads bases, `src/type_providers/python.rs:197-228` and `:231-263`, and has an inherited-method merge, `src/type_providers/python.rs:485-508`, used for field layout at `src/type_providers/python.rs:575-590`. TypeScript provider stores `extends`, `src/type_providers/typescript.rs:51-62` and `:289-370`, and resolves inherited properties, `src/type_providers/typescript.rs:631-659`. But providers are registered in CPG context, `src/cpg/context.rs:315-339`; `resolve_call_site_full` only has serialized `CallGraph` fields.

Also, the prompt’s `extract_ts_bases` reference is C/C++ tree-sitter fallback in `TypeDatabase`, not TypeScript: `src/type_db.rs:185-186`, `:666-702`, `:888-916`.

**Architecture Options**

Option A: add class hierarchy identity to `CallGraph`. Recommended.

Add a serialized class map, keyed by `(file, class_span)`, roughly:

```rust
class_bases: BTreeMap<(String, (usize, usize)), Vec<BaseRef>>
class_names: BTreeMap<(String, (usize, usize)), String>
```

`BaseRef` should distinguish `InRepo { file, span, name }`, `External(raw)`, and `Ambiguous(raw)`. Populate it during CallGraph build alongside `method_class_span`, using the existing class node identity from `method_owner_class_node`, `src/languages/mod.rs:1182-1208`, plus a small per-language base extractor. Update `empty`, full build, skeleton/subset build, `remove_files`, `merge`, and bump cache version from v22, `src/cpg_cache.rs:65-67`.

Resolution hook: in the Python/JS/TS self arm, first run `self_owner_lookup_same_class`. If it misses, get the caller class `(file, span)`, walk base refs in MRO order, and look up methods by base class identity, not by bare owner name. This preserves the 1a precision tests that currently drop instead of binding unrelated same-named classes, `src/resolution.rs:1975-1992` and `:2012-2023`.

Soundness rules:
- Never resolve an external base by matching a same-named in-repo class.
- If a base ref is ambiguous before the candidate in MRO, drop or return NameOnly, not Exact.
- If multiple in-repo candidates survive for one base class, keep current demotion behavior, like `src/resolution.rs:732-736`.
- Relabel returned `QualifiedOwner` edges to `SelfReceiver` in the existing self branch.

MRO: full C3 is required for exact Python multiple-inheritance behavior. For the thin slice, a cheaper sound policy is acceptable: exact for single-inheritance chains; for multiple bases, either implement C3 or demote/drop. The measured 16-call buy is all recoverable with single-chain handling. JS/TS only have single `extends`, so a simple chain is enough.

Option B: build inherited aliases into the method index.

At build time, insert base methods into subclass `(owner, method)` buckets as promoted aliases, then let the existing self arm find them. This is cheaper at the resolver hook but riskier: `methods` feeds non-self resolution paths too, including qualifier-owner and typed receiver paths. Unless aliases are quarantined to a self-only side table, this can mint wrong edges outside the intended slice. I do not recommend this as the main design.

Option C: ask type providers during resolution.

This reuses `PythonTypeProvider` / `TypeScriptTypeProvider`, but it crosses a bad boundary: `CallGraph` resolution is serialized/cacheable and does not retain provider objects. It also needs `FunctionId` identity, which Python’s provider method map does not expose. Not recommended for 1b.

**Recommendation + Thin Slice**

Implement Option A, but scope the first implementation to exact in-repo base identity and single-chain MRO. Include same-file and import-resolved same-repo bases; do not guess by bare class name when an import path points outside the repo. This gets the real FastAPI/Pydantic buy without opening SCIP/external-base territory.

Tests:
- Python same-file inherited self: `class Base: def m`; `class Child(Base): def run: self.m()` flips Exact/SelfReceiver.
- Python cross-file local import: `from base import Base`; child self-call resolves only if the import maps to an in-repo class.
- Negative external namesake: `import vendor; class Base: def m`; `class Child(vendor.Base): self.m()` drops.
- Multiple inheritance ambiguous case demotes or drops, not wrong Exact.
- JS/TS same-file `class Child extends Base { run() { return this.m(); } }`.
- Existing 1a canaries stay green: Python/JS/TS same-class self tests in `tests/lang/.../self_receiver_test.rs`, and the unrelated same-name drop tests in `src/resolution.rs:1975-2023`.

Acceptance: +16 inherited-self calls in the measured corpora, `multi_target_exact_sites` flat, Rust/Go call stats byte-identical, and Tier-A matrix/quick after a fresh release build. If the checked-in `python/inherited_override` remains as `c.go()`, leave it as expected_gap; add or update a true inherited-self Tier-A case instead.

**Risks / Unknowns**

The main risk is false Exact through bare class names. Avoid that by requiring class-span identity for every in-repo base. The second risk is incomplete import resolution for Python/TS; fail closed on anything not proven local. C3 can be deferred only if multiple inheritance is explicitly demoted/dropped. External framework bases are the larger visible population, but they are SCIP/stub/type-provider work, not 1b.

No code was changed and I did not run the full test suite; this was a read-only architecture pass with source census and code-path inspection.


