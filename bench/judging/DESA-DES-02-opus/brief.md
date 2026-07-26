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

# Memo: Prism Slice 1b — Inherited `self`/`this` Method Resolution (Py/JS/TS)

**Author:** static-analysis architect · **Mode:** read-only analysis + architecture · **Date:** 2026-07-04
**Verdict up front:** The in-repo-inherited buy is **small but clean** (~15 call sites across fastapi+pydantic+excalidraw, nearly all single-inheritance, single defining ancestor → Exact-eligible). It is worth **one thin slice** — chiefly because it lands the reusable **class-hierarchy map** that the broader §2.4 inheritance work also needs. The named `inherited_override` Tier-A case **will not flip** (it tests receiver typing, not self-inheritance) — 1b needs a **new** fixture. Cheapest sound design: **DFS ancestor walk, same-file base → Exact, cross-file base → NameOnly, external/multi → drop/demote. No C3.**

---

## 1. Verification (evidence)

### 1a. Sizing — the in-repo-inherited buy is ~15 sites, not the aggregate

I measured `self.X()` sites where the enclosing class has a base and `X` is defined on an **in-repo ancestor** (not on the class itself — those are already 1a), modeling the exact design (same-file-preferred base-name→class-identity resolution, then count defining ancestors). Method: Python `ast` on fastapi/pydantic; targeted scan + hand-verification on excalidraw (TS, no Python-ast).

| Corpus | total `self.X()` | 1a own (already resolved) | **1b in-repo inherited** | of which Exact-eligible | external base (SCIP, out of scope) | other dynamic |
|---|--:|--:|--:|--:|--:|--:|
| **fastapi** (`0cb4a8e`) | 82 | 52 (63%) | **12** | **12** (single defining ancestor) | 17 | 1 |
| **pydantic** (`363728f`) | 596 | 561 (94%) | **1** | **1** | 9 | 25 |
| **excalidraw** (`0642e72`, TS) | — | — | **~2–5** | (cross-file base) | ~13 (`Error`×8, `React.Component`, `PureComponent`, `DOMException`, `UIEvent`, `Array`) | — |

- **fastapi's 12 are the recognizable pattern** and all Exact-eligible: `OAuth2PasswordBearer`/`OAuth2AuthorizationCodeBearer` → `self.make_not_authenticated_error()` on base `OAuth2`; `APIKey{Query,Header,Cookie}` → `self.check_api_key()` on `APIKeyBase`; `HTTP{Basic,Bearer,Digest}` → `self.make_not_authenticated_error()` on `HTTPBase`. **Every base is defined in the same file as its subclasses** (`oauth2.py`, `api_key.py`, `http.py`). These are auth/security base classes — exactly the edges a defect-focused review tool wants resolved. The 1a spec's "~10 fastapi" guess was accurate (**12**).
- **pydantic is 94% 1a already** — it defines/overrides on `self`; the only inherited hit is `Secret.get_secret_value → _SecretBase` (`pydantic/types.py`). Its heavy inheritance (`BaseModel`) is **external-shaped** at the point of `self` calls.
- **excalidraw's in-repo inheritance is thin**: of 19 `class … extends …`, ~13 extend external (`Error`, `React.Component`, …). Confirmed inherited `this.X()` hits: `LassoTrail.endPath()` and `EraserTrail.endPath()` → base `AnimatedTrail` (`animatedTrail.ts`). **These bases are cross-file (imported)** — the key structural difference from fastapi/pydantic.
- **The external-base subset is larger than the in-repo subset** (fastapi 17 vs 12; excalidraw ~13 vs ~6). That is SCIP territory (base not in repo → nothing to resolve to), correctly **out of scope for 1b**.

**Net buy: ~15 call sites, single-inheritance, single defining ancestor.** As a fraction of all call sites in these repos (thousands) it is <0.1% — small. But it is *clean* (no diamonds in the buy) and *foundational* (shared plumbing).

### 1b. Ground-truth — inherited self-calls drop today as `unresolved_unknown_name`

Built `target/release/prism` and ran `nav call-stats` on a minimal 3-call fixture (same-class self-call + inherited same-file + inherited cross-file):

```
total_call_sites: 3
unresolved_unknown_name: 2      # Child.run→Base.helper (same-file) AND Trail.finish→Animator.end_path (cross-file)
kinds: {"self_receiver": 1}     # Base.base_only_caller→Base.helper (same-class) resolves via 1a
```

This confirms the mechanism precisely: the self arm at `resolution.rs:947-978` is **terminal** — when `self_owner_lookup_same_class` returns `None` (caller class doesn't define the name), the arm returns `dropped(DropReason::UnknownName)` (`resolution.rs:978`) and never falls through to another rung. Both inherited cases (same-file and cross-file base) land in the `unresolved_unknown_name` bucket (`queries.rs:281`). Same-class calls resolve via 1a. So the AST count *is* the drop count, and `call-stats`'s `unresolved_unknown_name` / `self_receiver` deltas are the acceptance levers.

### 1c. The `inherited_override` fixture does **not** test 1b — correction to the brief

`eval/fixtures/python/inherited_override/app.py` is `def run(c): c.go()` with `go` on **both** `Base` and `Child`. The seed asks for callers of `Child.go`; resolving `c.go()` requires knowing **`c: Child`** — receiver typing. Per its own `expected.toml`: *"c untyped … genuine multi-owner collision: the R6 precision floor drops it … Disambiguating needs the receiver's type (Python has no P6-lite); spec §2.4 → Phase-IP."* It is classified `dropped_multi_owner`, **not** `unresolved_unknown_name`.

**1b (self/this inherited) will not touch it** — `c.go()` has qualifier `c` (not self/this/cls, not a Go receiver-var), so it takes the general `Some(q)` arm (R3/R3b/P6-lite), never the self arm. **The brief's acceptance criterion "the `inherited_override` Tier-A case flipping ok" is wrong; 1b needs a distinct new fixture** (§4).

### 1d. Plumbing facts — the hierarchy exists, but nowhere the resolver can reach it

- **Base extraction exists only in the enrichment layer, keyed by bare name, last-writer-wins:** Python `extract_bases` (`type_providers/python.rs:231-264`) → `Vec<String>` of **raw AST base-name strings** (no import/FQN resolution); stored in `PythonTypeData.classes: BTreeMap<String, PythonClass>` keyed by **bare name** (global, collision = last-writer-wins). `collect_methods_with_bases` (`python.rs:485-509`) is a DFS "MRO approximation" over `data.classes.get(base)` by bare-name equality; its **only consumer is `field_layout`** (type-enrichment), not the call graph. TS: `TsClass.extends: Option<String>` (single) / `TsInterface.extends: Vec<String>` (multi), captured inline from `class_heritage`/`extends_clause` (`typescript.rs:296-372, 516-539`).
- **`TypeDatabase.class_hierarchy: BTreeMap<String, Vec<String>>` (`type_db.rs:185-186`) is C/C++-only** — populated by `from_compile_commands`/`from_parsed_files`, both of which early-`continue` for non-C/C++ (`type_db.rs:683-689`). It is **absent from the Py/JS/TS resolution path** and is an *Optional* store gated on `--compile-commands`. Not usable for 1b.
- **The CallGraph / resolver has zero base-class handling.** grep for `base`/`extends`/`superclass`/`mro`/`inherit` across `call_graph.rs`, `resolution*.rs`, `name_resolution/`, `cpg/` finds nothing relevant (the `name_resolution` "inherit" hits are about Rust module name (non-)inheritance). The closest existing analog is **Go struct-embedding promotion** (`promoted_aliases`, `call_graph.rs:197-201`) — a good precedent for "record promoted (owner, method)→fids at build," but it is Go-only and mechanically distinct.
- **The build hook already exists.** `method_owner_class_node` (`languages/mod.rs:1182-1211`) returns the enclosing **class-definition node** for Py/JS/TS (None for Rust/Go) — 1a already calls it in `method_metadata` (`call_graph.rs:1886-1889`) to compute `class_span`. From that same node the superclasses (`superclasses` field / `class_heritage`) are one child-lookup away. **There is no language method returning base nodes yet** — a small `class_base_names(class_node)` addition is required (mirror `python.rs:231-264` / `typescript.rs:516-539`).
- **Identity to respect (from 1a):** `method_class_span: BTreeMap<FunctionId,(usize,usize)>` + `method_class_span_ambiguous` (`call_graph.rs:165-172`); `self_owner_lookup_same_class` (`resolution.rs:710-737`) filters by `fid.file == caller.file && method_class_span[fid] == caller_span`, fails open to `owner_lookup` when ambiguous. A class's identity is **`(file, class-span)`**. `owner_key` (`resolution.rs:96-105`) is the base-name normalizer (strips generics/refs; bare last segment).

---

## 2. Architecture options

Shared substrate for all options — a **class-hierarchy map in `CallGraph`**, populated at build from the class node (serde-default fields; `CACHE_VERSION` 22→23):

- `class_bases: BTreeMap<ClassId, Vec<String>>` — class identity → **direct** base bare-names (normalized via `owner_key`).
- `class_defs: BTreeMap<String, Vec<ClassId>>` — base bare-name → in-repo class identities (to resolve a base name to a class).
- `ClassId = (String /*file*/, (usize,usize) /*class span*/)` — the 1a identity.

Populated in the Phase-1 method loop (extend `method_metadata` to also return bases from the class node it already fetches, `call_graph.rs:1886`). Must be recorded in all three build paths that already write `method_class_span` (`call_graph.rs:~277, ~466, ~1494`) and merged in `merge_from` (mirror `call_graph.rs:1123-1129`).

### Option A — Plumb hierarchy into CallGraph; DFS ancestor walk in the self arm (recommended shape)

In the self arm, when `self_owner_lookup_same_class` returns `None`, try inherited before dropping (`resolution.rs:964-968`):

```rust
let looked_up = if narrow {
    self.self_owner_lookup_same_class(owner, name, caller)
        .or_else(|| self.self_inherited_lookup(caller, name))   // 1b
} else {
    self.owner_lookup(owner, name)
};
```

`self_inherited_lookup(caller, name)`:
1. Bail if `caller ∈ method_class_span_ambiguous` (conservative; matches 1a fail-open discipline).
2. `start = (caller.file, method_class_span[caller])`. **DFS** over `class_bases[start]`, resolving each base bare-name via `class_defs` **same-file-first, then in-repo**; cycle-guard on visited `ClassId`.
3. At each ancestor, if it defines `name` — i.e. `methods[(ancestor_owner, name)]` filtered to `fid.file == ancestor.file && method_class_span[fid] == ancestor.span` is non-empty — collect those fids; track whether the resolving ancestor is **same-file** as the caller.
4. Decide by **number of distinct defining ancestor classes**:
   - `0` → `None` (external base or genuinely absent → falls through to today's `dropped(UnknownName)`).
   - `1`, same-file base → `exact(fids, InheritedSelf)`.
   - `1`, cross-file (namesake-unconfirmed) → `demoted(fids, InheritedSelf)` (NameOnly).
   - `>1` → `demoted(fids, InheritedSelf)` (multiple defining ancestors — the diamond case; **do not guess**).

**Why DFS, not C3:** C3 only matters to pick a *single winner* when the method is defined on *multiple* ancestors. That is exactly the case we choose to **demote** (NameOnly, keep all edges). For soundness, `1 defining ancestor → bind, >1 → demote` is order-independent — **full C3 is not needed**. C3 would be a later precision refinement to promote a diamond to a single Exact; defer it. (The measured buy has **zero** multi-defining-ancestor cases, so this costs nothing now.)

**Soundness:**
- Same-file base → Exact is sound: a same-file class definition *is* what the name binds to lexically; it cannot be an external-import shadow. Covers **13/15** measured (all fastapi + pydantic).
- Cross-file → NameOnly avoids the brief's named hazard ("don't bind to an external base's same-named in-repo namesake"): a `class Foo(BaseModel)` whose real `BaseModel` is external but which has a unique in-repo namesake defining the method would otherwise mint a wrong Exact. NameOnly is sound (score 0.6) and still surfaces the edge. Covers excalidraw's ~2.
- `>1` defining ancestors → demote (never a wrong Exact from a diamond).
- New `ResolutionKind::InheritedSelf` (`"inherited_self"`) for telemetry visibility in `call-stats` (Exact/NameOnly split). Gated to Py/JS/TS/Tsx via the existing `narrow` flag (`resolution.rs:955-963`) — **Rust/Go/C/C++/Java never enter this branch.**

**Follow-on (defer):** import-confirmed cross-file Exact — consult `self.imports[caller.file]` for the base alias; if it resolves to an in-repo module (reuse the R3 stem/dir match at `resolution.rs:1002-1019`), promote the cross-file case to Exact. This turns excalidraw's ~2 NameOnly into Exact. Cheap, but not needed for the MVP buy.

### Option B — Narrower: same-file-base-only MVP (no cross-file at all)

Identical to A but `self_inherited_lookup` only walks bases resolvable **same-file** (`class_defs` filtered to `caller.file`), always Exact, and returns `None` otherwise. `class_defs` collapses to a same-file lookup; `class_bases` still needed.

- **Pro:** smallest surface; zero namesake risk; no NameOnly semantics to reason about. Captures **13/15** (all fastapi + pydantic).
- **Con:** misses cross-file inheritance entirely (excalidraw, and any real repo that puts base classes in their own module — common in TS). Leaves the exact plumbing (`class_defs` name→identity) that the §2.4 work will demand un-exercised.

### Option C (rejected) — Reuse the enrichment-layer `collect_methods_with_bases`

Wiring the type-provider MRO map into resolution. **Rejected:** it is keyed by **bare name, global, last-writer-wins** (`python.rs:74, 217`) — it *discards* the `(file, class-span)` identity 1a fought to establish, re-introducing the same-name-collision unsoundness (fastapi has two `OAuth2`, two `HTTPBase`). It also runs only in the optional enrichment pass, not at graph build. Using it would regress 1a's precision floor.

---

## 3. Recommendation

**Ship Option A as one thin slice (1b), scoped to the same-file-Exact MVP + cross-file-NameOnly, and design `class_bases`/`class_defs` as the shared substrate for §2.4.** Defer import-confirmed cross-file Exact, C3, and external bases.

Rationale: the raw buy (~15) is too small to justify a slice *on its own numbers*, but (a) it is the **first consumer of a class-hierarchy map** that Python inheritance (§2.4) and field/return-typed receivers (the S3.1 struct-field-index candidate) will reuse, so the plumbing is a down-payment, not throwaway; (b) the fastapi cases are **security base classes** — high value for defect-focused review; (c) the change is **strictly additive and gated** — it can only convert today's `unresolved_unknown_name` drops into edges for Py/JS/TS, and cannot alter any existing resolved edge, so blast radius is minimal. If the team prefers to minimize slice count, **fold 1b into the next inheritance slice (priority 2/3)** — it shares 100% of the map plumbing; doing it first just banks the substrate earlier at low risk.

### Thin-slice plan (TDD, mirrors the 1a slice shape)

**Changes**
1. `languages/mod.rs`: add `class_base_names(&self, class_node: &Node) -> Vec<String>` (Py `superclasses` field; JS/TS `class_heritage`→`extends_clause`; bare-normalize via `owner_key`). Mirror `python.rs:231-264` / `typescript.rs:516-539`.
2. `call_graph.rs`: add `class_bases` + `class_defs` (serde-default) to the struct, `empty()`, all 3 build paths (extend `method_metadata` to return bases from the node it already fetches), and `merge_from`.
3. `resolution.rs`: add `ResolutionKind::InheritedSelf`; add `self_inherited_lookup`; wire the `.or_else(...)` into the self arm (`resolution.rs:964-968`).
4. `cpg_cache.rs`: `CACHE_VERSION` 22→23 (+ the `assert_eq!` at `:574`).

**Discriminating tests**
- **NEW Tier-A fixture `python/inherited_self`** (the case that actually exercises 1b): `class Base: def helper(self)…` / `class Child(Base): def run(self): self.helper()`; seed `helper`@Base; expect caller `Child.run`. Assert it flips `expected_gap`→`flip_candidate`→`pass` (`matrix.py:78-82`). **Do not** modify `inherited_override`'s expectation — 1b leaves it an `expected_gap` (state this in the PR).
- Resolution unit tests: same-file base → Exact; cross-file base → NameOnly (`InheritedSelf`); two-base multiple-inheritance both defining → demote; external base (base not in `class_defs`) → drop; **1a precedence** — an overriding same-class method still resolves same-class (1b never runs); span-ambiguous caller → drop.
- Integration (mirror `3bd55cf`): Py + JS + TS inherited fixtures + a merged-graph guard that `class_bases`/`class_defs` survive incremental merge.

**Acceptance**
- **Inherited-self buy realized:** on fastapi, `unresolved_unknown_name` drops by ~12 and `kind_exact.inherited_self` gains ~12; pydantic +1; excalidraw ~2 as `kind_nameonly.inherited_self`. (Measure with `nav call-stats --repo <corpus>` before/after — needs no oracle, so fastapi/pydantic's MEASURED-INVALID oracle status is irrelevant.)
- **Canary flat:** Rust/Go corpora `call-stats` **byte-identical** (branch gated to Py/JS/TS; maps empty for Rust/Go). Python/JS canaries: only additions (no existing edge changes).
- **Soundness:** no new wrong Exact — verify via the multiple-inheritance and external-base unit tests; confirm no cross-file case is minted Exact in the MVP.
- Tier-A matrix (`uv run tier-a --matrix-only --allow-stale-sut`) green; new `inherited_self` = `flip_candidate`/`pass`.

**Explicitly defer**
- **External bases → SCIP** (base not in-repo: `BaseModel`, `Starlette`, `Error`, `React.Component`). This is the majority of "unresolved inherited" and is out of scope by construction.
- **C3 / deep multiple-inheritance diamonds** — DFS + demote is sound; C3 is a later precision promotion.
- **Cross-file Exact via import-confirmation** — start cross-file as NameOnly; promote later by reusing R3 import machinery.
- `cls.`-classmethod inherited calls — the `cls` qualifier already routes through the self arm (`resolution.rs:951`), so these come along for free; no extra work, just add a test.

---

## 4. Risks / unknowns

- **Namesake-shadow wrong-Exact (the headline soundness risk).** Mitigated to near-zero by same-file-only Exact; the residual (cross-file) is demoted to NameOnly. Import-confirmation (deferred) closes it fully. *Watch:* ensure `class_defs` same-file filter runs before any cross-file fallback.
- **Method-less intermediate base classes.** Deriving `class_bases`/`class_defs` from the *method* pass misses a base that defines no methods but sits mid-chain. None appear in the measured buy (every resolving ancestor defines the called method). If §2.4 needs completeness, switch to a dedicated class-node pass (no `all_classes()` helper exists today — `ast.rs:279` only has `all_functions()`; a `nodes_of_kind`-style pass would be added). Cheap-version caveat: **`log`/note the limitation** so it isn't mistaken for full MRO.
- **Base-name normalization edge cases.** Python `class C(pkg.mod.Base)` (attribute) and `class C(Generic[T])` (subscript) must bare-normalize to `Base`/`Generic` (mirror `python.rs:242-257`); TS `extends Foo<T>` (`generic_type`) to `Foo`. Metaclass/`__init_subclass__`/mixin-via-`getattr` injection is invisible to AST — correctly falls to "external/absent → drop," never a wrong bind.
- **Cache/merge correctness.** Two new maps across 3 build paths + `merge_from` + a `CACHE_VERSION` bump — the same multi-site discipline `method_class_span` needed. A merge miss silently under-reports (recall loss), not a wrong edge; the merged-graph coverage guard (`3bd55cf`) is the backstop.
- **excalidraw is not a Tier-A corpus** (TS; Tier-A is rust/go/python only, `corpus.py:13`; excalidraw is absent from `corpora.toml`). JS/TS inherited-self must be validated by **integration fixtures + ad-hoc `call-stats`**, not the Tier-A oracle. The JS/TS buy is real but unmeasured by the harness.
- **Value judgment.** If the team weights aggregate accuracy over capability coverage, ~15 sites may not clear the bar for a standalone slice — in which case **fold into §2.4**. The plumbing is identical either way; this memo's recommendation is to *land the map*, whether as slice 1b or as the opening PR of the inheritance slice.

---
*Evidence artifacts: `nav call-stats` on a 3-call minimal fixture (2/3 inherited drop, 1/3 same-class resolves); Python-`ast` census of fastapi (12/82) and pydantic (1/596); targeted scan of excalidraw (19 `extends`, ~6 in-repo bases, ≥2 confirmed inherited `this.X()`). All read-only; temp files cleaned. I can persist this memo to `docs/` if you want it in-tree.*
