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

# Prism Slice 1b — Python/JS/TS Inherited Self-Method Resolution (MRO)

**Analysis + architecture memo. Read-only — no code changes made.** All line numbers verified against the working tree at `184208a` (`main`).

## 0. Bottom line up front

The in-repo-inherited buy is **small and structurally simple** — 13 real hits across three large corpora (fastapi 12, pydantic 1, excalidraw 0), and **100% of them are same-file, single-base relationships**. That empirical shape licenses a much cheaper design than a general MRO/C3 engine: generalize the byte-span narrowing 1a already built, walk it one hop at a time up a same-file base chain, and bail (no resolution, unchanged from today) the instant a class has more than one direct base. Full cross-file / multiple-inheritance support (Option A below) is buildable on the same plumbing but should be **deferred** — it's real extra soundness-proofing code for zero measured benefit in these corpora.

**Also: the task's stated acceptance test doesn't hold.** `eval/fixtures/python/inherited_override` is not the 1b case — it tests a different, unrelated gap (untyped-receiver virtual dispatch, `c.go()` where `c` is a plain parameter, not `self`). Implementing 1b as scoped will not and structurally cannot flip it. See §1.

---

## 1. Critical finding: `inherited_override` is the wrong fixture

The task brief says: *"Today this is the `python/inherited_override` Tier-A expected_gap"* and asks for acceptance including *"the `inherited_override` Tier-A case flipping ok."* I read the fixture and it does not test what slice 1b targets.

`eval/fixtures/python/inherited_override/app.py`:
```python
class Base:
    def go(self):
        pass

class Child(Base):
    def go(self):     # <- Child OVERRIDES go
        pass

def run(c):            # <- c is an untyped parameter, NOT self/this/cls
    c.go()
```
`expected.toml`'s own comment is explicit: *"`c.go()` with `c` untyped and `go` defined on both Base and Child is a genuine multi-owner collision: the R6 precision floor drops it... Disambiguating needs the receiver's type... Phase-IP."* (`eval/fixtures/python/inherited_override/expected.toml`)

This is **virtual-dispatch-on-an-unknown-receiver-variable** (Child *overrides* `go`; the ambiguity is "which concrete type is `c`"), not **inherited-method-lookup-via-self** (method absent on the caller's own class, present only on a base). Two different resolution problems, two different fixes:

- `c.go()` needs receiver *type* inference for a plain variable — that's the P6-lite `ReceiverClassifier` / Phase-IP line of work already described in the project CLAUDE.md, structurally unrelated to 1b.
- 1b's target is `self.go()` called from *inside a method of `Child`* where `Child` does **not** define `go` and `Base` does — the case the 1a spec doc (`docs/superpowers/specs/2026-06-22-python-js-self-receiver-samefile-narrowing.md:227`) itself calls out: *"absent everywhere (inherited) | 0 | 0 | drop | drop (1b resolves)"*.

I confirmed mechanically that 1b's mechanism cannot touch `inherited_override` even in principle:
- The self-arm gate at `src/resolution.rs:947-952` only fires when `q ∈ {self, this, cls}` or `self.receiver_vars.get(caller) == Some(q)`.
- `receiver_vars` is populated *exclusively* from `parsed.language.go_receiver_var(func_node)` (`src/call_graph.rs:1882-1885`) — Go-only. Python never populates it (consistent with the `inherited_override` comment: *"Python has no P6-lite"*).
- `run`'s parameter is `c`, not `self`/`this`/`cls`, and isn't in `receiver_vars` — so the call never reaches the self arm at all, regardless of what 1b adds there.
- Even if it did: `method_owners.get(caller)` for `run` is `None` (`run` is a free function, not a method) — the self arm's first line (`if let Some(owner) = self.method_owners.get(caller)`) already requires the caller to be a method.

**Recommendation:** don't gate 1b acceptance on `inherited_override` flipping — it won't, and shouldn't. Author a **new** fixture for the actual 1b case (e.g. `python/self_inherited_method`, modeled on the real fastapi/pydantic samples in §2), and leave a one-line clarifying comment on `inherited_override`'s `expected.toml` noting it exercises the P6/Phase-IP gap, not 1b, so a future reader doesn't re-make this mix-up. This is a real defect in how the task was scoped, not a nitpick — worth surfacing before anyone writes a plan against the wrong acceptance gate.

---

## 2. Verification: sizing the in-repo-inherited buy

### 2.1 Method

No existing tool query answers "how many `self.X()`/`this.X()` calls are dropped because `X` is inherited from an in-repo base." I wrote independent sizing scripts (not part of the repo) against the three named corpora, all pinned locally at `~/code/bench-repos/{fastapi,pydantic,excalidraw}`:

- **Python (fastapi, pydantic):** `ast`-based. Build a class registry (name → bases, own methods), find `self.X()` calls inside class methods, skip calls resolvable on the caller's own class (that's 1a's territory), then DFS the base chain. Classify each miss as: resolved on exactly one in-repo base branch (**1b target**), resolved on ≥2 distinct branches (**ambiguous**, would need a demote), or unresolved (**external base or truly unknown**). "External" is decided by cross-referencing each file's import table — a base name imported from outside the package is never treated as in-repo, closing exactly the false-positive risk the brief calls out (binding to an external base's same-named in-repo namesake).
- **TypeScript/TSX (excalidraw):** same algorithm, `tree-sitter-typescript` (Python bindings) instead of `ast`, matching real production node kinds (`class_declaration`, `class_heritage`/`extends_clause`, `member_expression` with `object.type == "this"`).

This mirrors what a production 1b implementation would actually see (same node-kind matching prism itself uses — see §2.3's `abstract_class_declaration` finding, which came directly out of this).

### 2.2 Results

| Corpus | files | classes w/ bases | `self`/`this.X()` resolved on **own** class (1a) | resolved on **in-repo base** (1b target) | base external / not found | ambiguous (≥2 branches) |
|---|--:|--:|--:|--:|--:|--:|
| fastapi | 48 | 97 | 51 | **12** | 15 | 0 |
| pydantic | 112 | 423 | 144 | **1** | 14 | 0 |
| excalidraw (ts/tsx) | 472 | 18 | 109 | **0** | 533 | 0 |

Context from `prism nav call-stats` (release binary, this checkout):

| Corpus | total call sites | `unresolved_unknown_name` | `self_receiver` Exact (1a) | `self_receiver` NameOnly |
|---|--:|--:|--:|--:|
| fastapi | 19,919 | 11,758 | 75 | — |
| pydantic | 65,645 | 35,687 | 735 | 759 |
| excalidraw | 24,546 | 10,294 | 484 | — |

**13 resolvable self/this calls, total, across three large real-world corpora**, against tens of thousands of `unresolved_unknown_name` each and hundreds of already-1a-resolved `self_receiver` Exact hits per corpus. This matches the 1a spec's own guess almost exactly (fastapi ~12 vs. its "~10" estimate) and confirms the framework-inheritance-is-mostly-external hypothesis: excalidraw is React-heavy (18 classes total have any base at all; the ones that do — `TopErrorBoundary`, `App` — extend `React.Component`, an external base) and yields **zero**.

**100% of the 13 hits are single-base and same-file** (verified explicitly, not eyeballed):
```
fastapi: same_file=12 cross_file=0 single_base=12 multi_base=0
pydantic: same_file=1 cross_file=0 single_base=1 multi_base=0
```
Representative samples (`fastapi/security/api_key.py:144`, `:232`, `:320`; `fastapi/security/http.py:218` etc.): `class APIKeyQuery(bases=['APIKeyBase'])` calling `self.check_api_key()`, where `APIKeyBase` and its subclasses live in the same file (`api_key.py:11`). `pydantic/types.py:1689`: `class Secret(bases=['_SecretBase'])` calling `self.get_secret_value()`, base at `types.py:1547`, same file.

This is the load-bearing fact for the recommendation in §5: a cross-file, multiple-inheritance-aware walk is solving a problem the measured corpora don't have.

### 2.3 Side finding: TS `abstract class` isn't recognized as a class at all

While sizing excalidraw, three genuinely-in-repo single-base pairs (`DurableIncrement`/`EphemeralIncrement extends StoreIncrement`, `packages/element/src/store.ts:454` `export abstract class StoreIncrement`) initially scored as "external" until I checked why: `tree-sitter-typescript` parses `abstract class Foo` as a **distinct node kind**, `abstract_class_declaration`, not `class_declaration`. Confirmed by direct parse:
```
abstract_class_declaration
  abstract  class  type_identifier  class_heritage  class_body
```
Both `TypeScriptTypeProvider::extract_class` (`src/type_providers/typescript.rs:173`, matches only `"class_declaration"`) and — more importantly — the production resolution path's `Language::method_owner_class_node` (`src/languages/mod.rs:1198-1211`, `matches!(cls.kind(), "class_declaration" | "class")`) **both miss `abstract_class_declaration`**. This isn't a new gap introduced by 1b — it's a **pre-existing 1a gap**: a `this.method()` call made from *inside* an abstract class's own method body never even gets a `method_class_span`/owner-class identity today, because the class-node walk doesn't recognize it as a class. Base classes in TS are disproportionately `abstract class` (that's exactly the `StoreIncrement`/`FileManager`-style pattern excalidraw uses), so this matters more for 1b (which needs to walk *to* base classes) than it did for 1a (same-class only). **Any 1b implementation must extend `method_owner_class_node`'s match arm to include `abstract_class_declaration`**, and this fix is worth backporting to 1a's own narrowing too since it's a strict superset of correctness (currently: `self`/`this` calls inside an abstract-class method get zero narrowing and unconditionally fall to global `owner_lookup`).

### 2.4 Hierarchy is extractable; the plumbing gap is real but small

Class/base extraction already exists, in three independent, un-wired forms:

1. **`src/type_providers/python.rs:232-264` `extract_bases`** — walks `class Foo(Base1, Base2):`'s `superclasses` field, handles `identifier`/`attribute`/generic `subscript` bases (e.g. `Protocol[T]`).
2. **`src/type_providers/python.rs:487-509` `collect_methods_with_bases`** — already a DFS MRO approximation with cycle protection (`visited: BTreeSet`), recursively unions base methods then overrides with the child's own. **This has a latent order bug for true diamonds**: it iterates `cls.bases` in listed order and calls `methods.extend(base_methods)` per base, so when two *distinct* bases both define the same name, the **last-listed** base wins, not the first (Python's actual C3 prefers the first). This is currently harmless because it only feeds `field_layout` (informational hover-style method enumeration, not resolution), but it means **this routine cannot be reused as-is for 1b** if 1b ever needs a "who wins" answer — which is exactly why §4's recommended design never asks "who wins" and demotes on genuine multi-branch conflicts instead.
3. **`src/type_providers/typescript.rs:173-358`** — `extract_class` captures `extends`/`implements` similarly (`class_heritage`/`extends_clause` walk, handles multiple tree-sitter-TS shapes).
4. **`src/type_db.rs:186` `class_hierarchy`** — a red herring for this task: it's C/C++-only, populated from a clang AST dump keyed on `compile_commands.json` (`type_db.rs:238-244`). Not usable for Python/JS/TS; no code sharing opportunity here beyond the field-naming precedent.

None of (1)–(3) are visible to `CallGraph`/`resolution.rs` today — `TypeRegistry` (the thing that owns them) is built into `CpgContext` (`src/cpg/context.rs:259-333`), a layer above and built independently of `CallGraph`. **But there is a direct, already-shipped precedent for exactly this kind of cross-wiring**: Go embedding promotion. `CallGraph::apply_go_embedding_promotion` (`src/call_graph.rs:1378-1430`) builds a **fresh, throwaway** `GoTypeProvider::from_parsed_files(files)` (`:1388`) purely to walk struct-embedding depth, then folds the result into `self.methods` as `promoted_aliases` keyed by `(owner_key, method) -> FunctionId`, with `owner_lookup` (`resolution.rs:692-708`) relabeling matches to `ResolutionKind::EmbeddedPromotion`. This is proof the codebase already tolerates "spin up a type provider on demand, mine one fact out of it, throw it away" as an enrichment pattern — 1b can follow the same shape rather than threading `TypeRegistry` itself through `CallGraph`.

The one thing Go's pattern *can't* be copied wholesale: `apply_go_embedding_promotion` promotes eagerly into the **global**, name-keyed `self.methods` map. 1a explicitly rejected exactly this kind of global name-keying for self-calls (`docs/superpowers/specs/2026-06-22-python-js-self-receiver-samefile-narrowing.md` rev 2/3 history: bare-name owner keys collide across files — pydantic alone has 142 class names defined in >1 file). Promoting a base's method into a bare `(owner_key(ClassName), method)` bucket would silently resurrect that exact collision class for 1b. So 1b's lookup must stay **span-scoped** like `self_owner_lookup_same_class`, not name-scoped like Go's promotion — see §4.

---

## 3. The exact hook point

`src/resolution.rs:947-979`, the self arm:
```rust
match site.qualifier.as_deref() {
    Some(q) if q == "self" || q == "this" || q == "cls" || self.receiver_vars... => {
        if let Some(owner) = self.method_owners.get(caller) {
            let narrow = matches!(Language::from_path(&caller.file), Python | JavaScript | TypeScript | Tsx);
            let looked_up = if narrow {
                self.self_owner_lookup_same_class(owner, name, caller)   // <- 1a
            } else {
                self.owner_lookup(owner, name)
            };
            if let Some(mut resolved) = looked_up { ... return ResolutionOutcome::hit(resolved); }
        }
        ResolutionOutcome::dropped(DropReason::UnknownName)              // <- 1b's insertion point
    }
    ...
}
```
`self_owner_lookup_same_class` (`resolution.rs:710-737`) does exactly one thing: given the caller's `(file, class_span)` (from `method_class_span`, populated once at build time per `CallGraph::apply_go_embedding_promotion`'s sibling passes), it filters `self.methods[(owner, name)]` down to candidates whose *own* `method_class_span` equals the caller's — i.e. "defined by literally this class node." When that filter yields zero candidates, it returns `None` today, which falls through to the drop at line 978. **That `None` is the entire surface area 1b needs to extend.**

---

## 4. Architecture options

### Option A — General cross-file, multi-inheritance MRO walk

Plumb a full `class_bases: BTreeMap<(file, class_span), Vec<String>>` map into `CallGraph`, populated at the same three build sites as `method_class_span` (`call_graph.rs:277/307`, `:466/561`, `:1494/1537` — full build, `build_skeleton`, `build_direct_subset`), using a new small per-language `class_bases_of(class_node) -> Vec<String>` extractor in `languages/mod.rs` mirroring `extract_bases`/`class_heritage`. On a same-class miss, walk the *full* transitive base graph (not just one hop), across files, checking each base name against the caller-file's import table (`self.imports`, `call_graph.rs:157`) to reject externally-imported names before ever consulting `self.methods`. If the transitive search finds the method defined on exactly one distinct base **class identity** (not just one name — two files can define the same-named base), return it (relabeled, new `ResolutionKind`); if ≥2 distinct base identities define it (a real diamond, or an ambiguous same-name-different-file base), demote to `NameOnly`, never guess.

This is sound (soundness comes from the per-hop external-import check plus multi-branch demotion, not from getting Python's C3 order exactly right — see the diamond-order argument in §5), and it's the design that generalizes cleanly to any future corpus that *does* show cross-file or multi-base inheritance. Cost: a name→span index for cross-file base identity resolution, a new `class_bases` field threaded through 3 build sites + merge (`:1123-1128`) + `remove_files`/retain (`:1069`ish) — the same triplication tax `method_class_span` paid (documented explicitly in the 1a spec's §5 checklist) — plus the import-shadow check at every hop.

### Option B — Same-file, single-inheritance chain only (recommended, §5)

Generalize `self_owner_lookup_same_class`'s existing span-filter into a **parameterized** primitive — "does the class at *this* span define method `m`" — and call it not just with the caller's own span (today) but, on miss, with each ancestor's span up a **same-file-only** chain, stopping (not branching) the moment a class has more than one direct base. No cross-file lookups, no import-table cross-referencing, no multi-branch ambiguity detector, no MRO-order question at all (there's only ever one branch to follow, by construction — a genuine multi-inheritance class is defined as "don't attempt this," not "attempt this and demote"). New data needed is much smaller: just `class_bases: BTreeMap<(file, class_span), Vec<String>>` (still the standard 3-build-site + merge + retain treatment `method_class_span` needed) plus a per-file `(file, class_name) -> Vec<class_span>` index to find "the class named `X` defined in this same file" (an ambiguous >1 same-file-same-name match at any hop = bail, don't guess — the same conservatism 1a already applies).

### Rejected: eager Go-style promotion into `self.methods`

Considered mirroring `apply_go_embedding_promotion` exactly (pre-populate `self.methods[(owner_key(ChildClass), method)]` with the base's `FunctionId`). Rejected because it's **name-keyed**, and 1a's entire reason for existing is that name-keyed self-resolution is unsound across pydantic's 142 duplicate class names — promoting eagerly into the bare-name bucket would let an inherited method on `ClassA` (file X) leak into an unrelated same-named `ClassA` (file Y)'s self-calls. Any 1b design must stay span-scoped at the point of use, like 1a, not eagerly materialized like Go's promotion.

---

## 5. Recommendation

**Ship Option B.** The evidence in §2.2 is unambiguous: every measured real-world instance of this gap is a same-file, single-base relationship; Option A's extra machinery (cross-file base identity, import-shadow checks per hop, multi-branch diamond detection) buys strictly zero additional resolved calls against fastapi/pydantic/excalidraw, while adding real review surface and a second full round of soundness argument. Build Option A's generality only if a future corpus (or user report) actually shows cross-file or multi-base inheritance driving unresolved self-calls — nothing in this analysis suggests that's likely; §9 of the 1a spec already flags a *different*, larger, already-known Python precision lever (decorated-method double-capture, ~20% of pydantic's methods) competing for the "next slice" slot, which is more evidence 1b should stay small.

### Concrete thin-slice plan

1. **`languages/mod.rs`**: fix `method_owner_class_node`'s TS/JS/Tsx arm (`:1198-1211`) to also match `"abstract_class_declaration"` (§2.3) — do this regardless of 1b, it's a strict 1a bug-fix. Add a sibling `class_bases_of(class_node, parsed) -> Vec<String>` per language: Python reads the `superclasses` field exactly like `type_providers/python.rs:232-264`; JS/TS/Tsx reads `class_heritage`/`extends_clause` exactly like `type_providers/typescript.rs:209-358` (only `extends`, never `implements` — TS/JS structurally can't have method-body multiple inheritance, so there is no diamond question there at all, unlike Python).
2. **`call_graph.rs`**: add `pub class_bases: BTreeMap<(String, (usize, usize)), Vec<String>>` next to `method_class_span` (`:168`); populate it at the same 3 build call-sites via a new `record_class_bases` helper mirroring `record_method_class_span` (`:2183-2196`, ambiguity-on-conflicting-write semantics not needed here since a class only has one base list, so this can be a plain insert, deduped since `method_owner_class_node` returns the class node once per method — insert only if the key is absent); thread through `extend`/`remove_files` like `method_class_span` (`:1123-1128`, `:1069`). Add a small per-file name index, e.g. `class_span_by_name_in_file: BTreeMap<(String, String), Vec<(usize, usize)>>`, populated in the same pass.
3. **`resolution.rs`**: generalize `self_owner_lookup_same_class` (`:710-737`) into a span-parameterized helper (e.g. `owner_lookup_at_span(owner, name, target_span)`); keep `self_owner_lookup_same_class` as the depth-0 call. Add `self_owner_lookup_inherited(owner, name, caller)`: read `class_bases.get(caller_span)`; if `!= 1` base, return `None` (bail on 0 or >1 — no MRO branching, ever); else look up that one base's same-file span via `class_span_by_name_in_file[(file, base_name)]` — if `!= 1` match, return `None` (bail on same-file name ambiguity too); else call `owner_lookup_at_span` at that span, and on miss recurse to *that* class's own `class_bases` entry (same single-base-only gate at every hop, cycle-guarded by a small `visited` set exactly like `collect_methods_with_bases`'s pattern in `type_providers/python.rs:490-495` — reuse the *shape*, not the buggy last-base-wins body). Wire into the self arm at `resolution.rs:964-976`: call `self_owner_lookup_inherited` only when `self_owner_lookup_same_class` returns `None`, before the final drop. Introduce a new `ResolutionKind::InheritedSelf` (alongside `EmbeddedPromotion`'s precedent, `resolution.rs:35-58`) rather than reusing `SelfReceiver`, so `call-stats` telemetry can report the 1b buy separately from 1a's.
4. **`cpg_cache.rs`**: bump `CACHE_VERSION` 22 → 23 (`cpg_cache.rs:67`), update the version-assertion test (`:574`) — same treatment as 1a's 20→21, 21→22.
5. **Tests**: hand-built `CallGraph`/`resolve_call_site_full` unit tests in `tests/lang/python/self_receiver_test.rs` and `tests/lang/javascript/self_receiver_test.rs` (extending 1a's existing files, same harness shape — see `resolve_self_call` helper already there), covering: same-file single-base inherited hit (the fastapi/pydantic real-world shape) → `Exact`/`InheritedSelf`; multi-base caller class → unchanged drop (explicitly assert *no* resolution, proving the bail-out); same-file same-name-class collision at the base-name-lookup hop → unchanged drop; TS `abstract class` base → resolves (regression guard for §2.3's fix); a Go/Rust fixture asserting self-arm behavior is unchanged (mirrors 1a's checklist item). Add one **new** Tier-A fixture, e.g. `eval/fixtures/python/self_inherited_method`, modeled directly on the `APIKeyBase`/`APIKeyQuery` shape, with `status = "known_fail"` today and an explicit note that it — not `inherited_override` — is 1b's discriminating case (§1).
6. **Acceptance**, following 1a's own template (`docs/superpowers/specs/...:277-290`): *measure*, don't assert a fixed number — report the actual fastapi/pydantic/excalidraw `self_receiver`-family delta in the PR (expect low single digits given §2.2). `multi_target_exact_sites` byte-flat. Identity-aware regression check: every newly-resolved site's target must be reachable via the exact same-file-single-base chain, no wrong Exacts. Rust/Go/C/C++ corpora (ripgrep, caddy, prism-self) byte-identical (1b's gate excludes those languages entirely, same as 1a's `narrow` check). Tier-A `--matrix-only --allow-stale-sut`: 0 regressions; the **new** fixture flips known_fail→pass; `inherited_override` **stays** `expected_gap` (§1 — don't gate on it moving). `cargo test` green, `cargo fmt --check` clean.

---

## 6. What to defer (explicitly, with reasons)

- **Cross-file inherited bases** (Option A's cross-file half) — zero measured need (§2.2); revisit only with new corpus evidence.
- **True multiple-inheritance / diamond resolution** — zero measured need; and even where it exists, "demote to NameOnly on conflict" (Option A's safety net) costs little relative to guessing, so if ever built, build the demote-on-conflict version, never a first-listed-base-wins shortcut (§5's diamond-order argument in the addendum below explains why naive DFS is actively wrong here, not just imprecise).
- **External bases** (e.g. `class Foo(pydantic.BaseModel):`) — explicitly SCIP/type-database territory per the task brief; nothing in this analysis changes that call. §2.2's "external / not found" column (15, 14, 533) is the size of that deferred bucket, for reference — it dwarfs the in-repo bucket, especially for excalidraw's React-heavy code.
- **Decorated-method double-capture** — not 1b's problem, but flagged by the 1a spec (`docs/superpowers/specs/...:310-321`) as a **larger** Python precision lever (~20% of pydantic's class methods) already queued as "recommended as the next slice after 1a." Worth the reader's attention when prioritizing 1b vs. that: 1b is measurably smaller.

---

## 7. Risks / unknowns

- **Diamond-order unsoundness of naive DFS (why Option A, if ever built, must detect and demote conflicts rather than pick first-hit).** Concretely: `class A: def m()`, `class B(A): pass`, `class C(A): def m()`, `class D(B, C): pass`. True Python MRO(D) = `[D, B, C, A, object]`, so `self.m()` inside D should resolve to `C.m`. A naive "search base 1 (`B`) to full depth before touching base 2 (`C`)" DFS would incorrectly return `A.m` (found while exhausting B's branch) instead of `C.m`. This is exactly why any multi-base extension must detect "found on ≥2 distinct branches" and demote, not just take the first hit in declared order. Option B sidesteps this entirely by never walking past a class with >1 base.
- **`class_bases` population coverage is the real implementation risk**, same as 1a flagged for `method_class_span` (`docs/superpowers/specs/...:294-296`): a missing entry just means "conservative drop" (safe), but the 3-build-site + merge + retain enumeration is easy to under-cover in a first pass — the merged-graph coverage-guard test pattern 1a already added (`tests/lang/python/self_receiver_test.rs::merged_graph_still_narrows_self_calls`) should be replicated for `class_bases`.
- **Sizing sample size is small (n=13).** fastapi/pydantic/excalidraw are three corpora; the "100% same-file single-base" finding is a strong signal but not a proof it holds universally. If this ships and a later corpus run shows a meaningfully different shape (cross-file or multi-base instances appearing in numbers), Option A becomes worth revisiting — the plumbing described in §4/§5 (`class_bases`, span-parameterized lookup) is deliberately structured so extending B→A later is additive, not a rewrite.
- **JS/TS `implements` is a type-only contract, not inheritance** — correctly out of scope; only `extends` chains matter for self/this method-body inheritance in these languages, which is also why TS/JS structurally cannot hit the diamond problem at all (single `extends` parent only).
- **The `abstract_class_declaration` fix (§2.3) is scope creep relative to a narrow reading of "1b only,"** but it's a one-line, low-risk fix that any 1b implementation needs anyway (excalidraw's real base-class pattern uses `abstract class`) — recommend bundling it rather than shipping 1b silently unable to see a common TS pattern.
