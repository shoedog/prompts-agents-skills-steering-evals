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

**Prism Slice 1b Memo**

**Verification**

I measured source-level sites that match the current drop condition: `self`/`cls` or `this` call inside a class with bases, own class does not define the method, and the method is found only on a base or not found in repo. In current code, the self arm calls `self_owner_lookup_same_class` for Python/JS/TS, and if that misses it returns `DropReason::UnknownName` (`src/resolution.rs:947-979`). `call-stats` records that as `unresolved_unknown_name` (`src/navigation/queries.rs:204-208`, `src/navigation/queries.rs:274-281`).

| corpus | scanned revision | missing same-class inherited/external self calls | in-repo base, 1b-resolvable | external/unknown base, not 1b |
|---|---:|---:|---:|---:|
| fastapi | `0cb4a8e284b4` | 27 | 12 | 15 |
| pydantic | `363728fe0b35` | 81 | 4 | 77 |
| excalidraw | `0642e72cfa2d` | 222 | 0 | 222 |

FastAPI’s 1a “~10” guess is close: I found 12 call sites, all same-file base cases. Examples: `OAuth2PasswordBearer.__call__` calls base `OAuth2.make_not_authenticated_error()` (`fastapi/security/oauth2.py:330`, `fastapi/security/oauth2.py:401`, `fastapi/security/oauth2.py:541`), and API key subclasses call `APIKeyBase.check_api_key()` (`fastapi/security/api_key.py:11`, `fastapi/security/api_key.py:47`, `fastapi/security/api_key.py:144`). External FastAPI examples are Starlette methods such as `FastAPI.add_route()` and `FastAPI.add_middleware()` (`fastapi/applications.py:42`, `fastapi/applications.py:1120`, `fastapi/applications.py:4718`).

pydantic’s in-repo buy is tiny: `Secret._display -> _SecretBase.get_secret_value` (`pydantic/types.py:1547`, `pydantic/types.py:1689`), `MultiHostDsn -> AnyUrl.validate_host/_validate_port` (`pydantic/v1/networks.py:171`, `pydantic/v1/networks.py:423`, `pydantic/v1/networks.py:444-446`), and one cross-file `BaseSettings.Config -> BaseConfig.get_field_info` (`pydantic/v1/env_settings.py:82-96`, `pydantic/v1/config.py:80`, `pydantic/v1/config.py:118`). If excluding any `/tests/` directory, pydantic still has the same 4 in-repo sites, but external/unknown drops fall from 77 to 21.

Excalidraw has no in-repo inherited `this.method()` buy in this pass. The observed missing calls are React/DOM/native bases such as `React.Component.setState`, `PureComponent.setState`, and `Array.push` (`packages/excalidraw/components/App.tsx:621`, `packages/excalidraw/components/App.tsx:955`, `excalidraw-app/collab/Collab.tsx:132`, `excalidraw-app/collab/Collab.tsx:341`, `packages/excalidraw/tests/helpers/polyfills.ts:50-55`). That is SCIP/stub territory, not slice 1b.

Hierarchy facts: extraction exists, but not where resolution needs it. Python stores `bases` on `PythonClass` and extracts them in `extract_bases` (`src/type_providers/python.rs:31-49`, `src/type_providers/python.rs:231-263`), and it already has a private recursive method collector (`src/type_providers/python.rs:485-508`). TS stores `extends` on `TsClass`, extracts it, and resolves inherited properties privately (`src/type_providers/typescript.rs:51-62`, `src/type_providers/typescript.rs:289-371`, `src/type_providers/typescript.rs:631-660`). `CallGraph` has method owner and class-span identity, but no class hierarchy map (`src/call_graph.rs:143-230`). The builder records owner/class-span via `method_metadata`, not bases (`src/call_graph.rs:514-567`, `src/call_graph.rs:1865-1890`). C++ `TypeDatabase.class_hierarchy` exists, but is separate and clang-only (`src/type_db.rs:179-186`).

**Architecture Options**

A. Plumb class hierarchy into `CallGraph`.

Add a serialized map beside `method_class_span`, e.g. `(file, class_span) -> { owner, bases }`, plus a class-name index for proven in-repo base resolution. Populate it in full, skeleton, and direct-subset builds; retain/merge it like `method_class_span` (`src/call_graph.rs:1048-1101`, `src/call_graph.rs:1107-1147`) and bump cache version (`src/cpg_cache.rs:63-67`).

Resolver hook: keep same-class lookup first. If `self_owner_lookup_same_class` returns `None`, find the caller class by `(caller.file, method_class_span[caller])`, walk its proven in-repo bases, and look up methods by exact base class span, not by bare owner alone. Return `Exact` only for one proven target; if multiple proven base targets remain, demote to `NameOnly`; if a base is external/unknown, do not bind it to an in-repo same-named class.

Soundness rule: same-file base resolution is safe. Cross-file base resolution should require import/module proof. Do not use repo-wide “unique class named Base” as proof, because `BaseModel`, `Starlette`, `Component`, etc. can be external while an in-repo namesake exists.

MRO: full Python C3 is not required for the thin slice if the rule is “unique proven inherited target only.” Ordered DFS is sound under that rule because conflicts demote instead of claiming `Exact`. Full C3 only buys extra exactness for multiple-inheritance conflict cases and can be deferred. JS/TS single `extends` can walk the chain directly.

B. Narrow same-file direct-base slice.

Store only direct same-file base edges and resolve inherited self calls through that map. This covers all 12 FastAPI in-repo sites and 3 of pydantic’s 4, with much lower import-resolution surface. It misses pydantic’s cross-file `BaseConfig` case and any future clean cross-module base, but it is the cheapest sound version.

**Recommendation**

Implement A-lite: add the `CallGraph` hierarchy map now, but admit only proven bases: same-file first, then import-proven in-repo cross-file if that is already cheap through `imports`. Use unique-hit DFS with ambiguity demotion. This keeps the data model ready for later import/stub work while keeping the exactness contract narrow.

Do not treat the current Tier-A `python/inherited_override` fixture as an acceptance flip for this slice. The checked-in fixture is untyped `c.go()` with both `Base.go` and `Child.go` defined (`eval/fixtures/python/inherited_override/app.py:1-10`), and its own expected file says it needs receiver type information (`eval/fixtures/python/inherited_override/expected.toml:4-8`). A self/this inherited MRO slice cannot soundly resolve that to `Child.go`; flipping it would be a warning sign. Add a true `self_inherited_base` Tier-A fixture, or expand the fixture/scope explicitly.

Thin-slice plan:

1. Add `class_bases`/`classes_by_name` to `CallGraph`, with serde defaults, remove/merge support, and cache v23.
2. Extract Python and JS/TS class base facts during build using exact class spans from `method_owner_class_node`.
3. Add `self_owner_lookup_inherited_class`, called only after same-class miss in the Python/JS/TS self arm.
4. Tests: Python same-file base exact; Python child override wins same-class; external base with in-repo namesake stays unresolved; multiple inherited candidates demote; TS `this` base exact; React `setState` stays unresolved.
5. Acceptance: FastAPI in-repo inherited-self sites recovered, pydantic 3-4 recovered depending on import-proof scope, Excalidraw no in-repo buy expected, `multi_target_exact_sites` flat, Rust/Go call-stats byte-identical, Tier-A no regressions. Add a new Tier-A inherited-self fixture rather than flipping the current untyped override fixture.

**Risks / Unknowns**

Decorated Python methods can produce duplicate FunctionIds and should stay `NameOnly` if duplicated. Dynamic Python bases, metaclasses, mixins, `typing.Generic`, React/DOM/native bases, and external package bases are out of scope until SCIP/stubs. Cross-file imports are the main soundness trap: bind only when import proof points at an in-repo class. I did not edit code or run the full suite; this was read-only source and corpus measurement.
