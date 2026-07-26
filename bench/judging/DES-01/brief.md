# Conclusion-match grading — task DES-01 (design/architecture)

An engineer wrote the design analysis below in response to the task brief. The
question was later SETTLED empirically by the project's subsequent history.
Grade the analysis against the settled outcome. You do not know who wrote it.
Judge conclusions by SHAPE and substance, not by labels or wording.

## Settled outcome (ground truth, from later repository history)

- The adopted design (spec a069da0, impl 075d686) was **Option B — guarded
  hit-or-fallthrough recovery**: recover typed receivers but gate R6 so a miss
  FALLS THROUGH to existing residue instead of dropping-external; Rust/Go
  byte-identical. The original memo warned the eager variant would spike
  `dropped_external_receiver`.
- The buy was measured NEGLIGIBLE: handoff ce3f5ab records "slice 2
  implemented + acceptance green but BUY NEGLIGIBLE (~+17 Exact); value is
  slice 3/4". Express/JS buy was ~0 (external CommonJS Router).
- JS/TS inclusion was REFUTED in practice: 22deb40 narrowed recovery to
  Python-only after a JS/TS lexical-block soundness hole; 08f019d records "JS
  buy~0"; the slice was later SHELVED (b78c774).

## Grading fields

- recommendation_matches_vindicated: does the analysis's recommended design
  match the adopted Option-B shape (guarded recovery whose MISS falls through
  to existing behavior, never dropping-external; Rust/Go untouched)? Judge by
  SHAPE, not by the letter the analysis assigns its options.
- guarded_fallthrough_shape: does the recommended design include the
  hit-or-fallthrough guard specifically?
- buy_sized_realistically: the measured buy was ~+17 Exact edges total (with
  Express/JS ~0). Is the analysis's quantitative buy prediction consistent
  with that measured reality (an estimate of thousands of new Exact edges is
  NOT)?
- js_ts_scope_correct: does the analysis recommend deferring or excluding
  JS/TS recovery (vindicated), or does it include JS/TS in scope (refuted)?
- would_have_prevented_wasted_work: following the analysis as written, would
  the team have avoided the JS/TS soundness hole and the over-investment that
  led to shelving?
- probe_answer: 2-4 sentences on what the analysis got right and wrong vs the
  settled outcome.

## The task brief the engineer received

# Analyze + architect (xhigh, read-only): prism slice 2 — Python/JS typed-receiver recovery

You are a senior static-analysis architect (codex gpt-5.5, xhigh). **Read-only.** Produce an ANALYSIS +
ARCHITECTURE memo (markdown) for the next Python/JS precision+recall slice in `prism` (tree-sitter CPG /
code-nav, exposed to LLM agents). Cite `file:line`. Session cwd = the prism repo
(`/Users/wesleyjinks/code/slicing`, on `main` — includes the just-merged self-receiver same-class slice and
its `method_class_span`/`method_owner_class_node`). Design only; no code.

## The slice
Resolve `x.method()` in **Python and JS/TS** where the receiver `x`'s static type is syntactically
recoverable — typed params (`def f(x: Foo)`, TS `f(x: Foo)`, fields), constructor locals (`x = Foo()`,
`x = new Foo()`), and TS type annotations — by feeding the recovered owner type into the existing R6
owner-dispatch (`owner_lookup`). This is the Python/JS analogue of what already exists for Rust/Go.

## Verify-first (do this, report numbers)
1. **Size the denominator.** Of the unresolved/`dropped_external_receiver`/`free`-demoted calls in fastapi,
   pydantic, express, how many are `x.method()` with a *recoverable* receiver type (typed param /
   constructor local / TS annotation)? Use `prism nav call-stats` + source greps. The buy hinges on this —
   if small, say so.
2. **Confirm the seam works for Python/JS.** The Rust/Go receiver typing flows through `ReceiverClassifier`
   (`src/resolution.rs:262`), R6 step 1 (`src/resolution.rs:1066-1121` → `owner_lookup(recv_ty, name)`),
   `RustReceiverTyper` (`src/resolution_receiver.rs:31-108`), build-time materialization
   (`src/call_graph.rs:~595-640`), and the AST scan `receiver_type_in_fn` (`src/ast.rs:393-447`, gated
   `Rust|Go`) + `recover_simple_ident` (`src/resolution.rs:318`, gated `Rust|Go`, skips `self|this|cls`).
   Confirm what opening these gates for Python/JS would entail and whether `owner_lookup` (now class-aware
   via the merged slice) is the right sink.

## Deliver
- **Verification** (the denominator + seam facts, with evidence).
- **Architecture options** (≥2): e.g. (A) a `PythonReceiverTyper`/`JsReceiverTyper` beside
  `RustReceiverTyper` extending the existing P6-lite scan to Python type-hints/constructor-locals + TS type
  nodes, routed through R6; (B) something lighter/narrower. Trade-offs, soundness (owner-key collisions —
  does it need the same `(file, class-span)` identity the merged slice added?), blast radius, risk.
- **Recommendation + thin-slice plan** (what to change, discriminating tests, acceptance = which call-stats
  buckets rise, canary flat, Rust/Go byte-identical), + what to defer (cross-module type resolution / the
  scope-graph = slice 4).
- **Risks / unknowns.**
Be opinionated; cheapest sound design that yields a real measured buy.


## The analysis to grade

All verification is done — I have the seam facts, five corpus measurements, and baselines. Writing the memo now.

---

# ANALYSIS + ARCHITECTURE MEMO — prism slice 2: Python/JS typed-receiver recovery

**Scope:** resolve `x.method()` in Python/JS/TS where `x`'s type is syntactically recoverable, routed into R6 owner-dispatch. Read-only analysis; design only. All citations against `main` @ `184208a`.

---

## 1. Verification

### 1.1 The seam — confirmed, with two corrections to the brief

The P6-lite pipeline is exactly where the brief says, and every stage is language-gated at two chokepoints:

| Stage | Where | Gate |
|---|---|---|
| Classifier trait (`ReceiverClassifier::classify`) | `src/resolution.rs:262` | none (swappable seam) |
| Shared recovery gate `recover_simple_ident` | `src/resolution.rs:318-337` | **`Rust \| Go` at `:320`**; skips `self\|this\|cls` (`:325`), import aliases (`:327`) |
| AST scan `receiver_type_in_fn` | `src/ast.rs:393-462` | **`Rust \| Go` at `:403`**; typed-param arms `:414` (Rust) / `:432` (Go); shadow-bail `>1` binding at `:458-460` |
| Binding walk `walk_receiver_bindings` | `src/ast.rs:3955-4074` | per-arm `(Language, node.kind())` match — Rust/Go arms only; pre-call-line guard `:3968` |
| Constructor heuristic `constructor_type` | `src/ast.rs:4076-4109` | Rust `T::new/default`, Go `NewT`/composite literal — no Py/JS arm |
| Build-time materialization | `src/call_graph.rs:638-656` (phase-2 par_iter) and `:1613-1631` (diff-scoped subset build) | **none — classifier already runs for every language on every call site**; result stored as `CallSite.receiver_type/receiver_recovery` |
| R6 step 1 routing | `src/resolution.rs:1109-1164` | none — fires on `site.receiver_type.is_some()`; hit → `owner_lookup(recv_ty, name)` at `:1117`, relabeled `TypedParam`/`ConstructorLocal`; miss → Go-only interface consult (`:1132`), else `DropReason::ExternalReceiver` (`:1162`) |

So opening the gates for Python/JS/TS requires **zero materialization or routing plumbing** — only (a) the `Rust|Go` matches at `resolution.rs:320` and `ast.rs:403`, (b) Py/TS arms in the param scan / binding walk / constructor heuristic, and (c) a Py/TS annotation normalizer. Qualifier extraction already works: Python `attribute.object` and JS/TS `member_expression.object` at `src/languages/mod.rs:731-732` produce `qualifier="x"`, `name="m"` for `x.m()`.

**Correction 1 — `RustReceiverTyper` is not the analogue to copy.** `RustReceiverTyper` (`src/resolution_receiver.rs:31-108`) is not P6-lite: it is the scope-graph-backed typer (`.expect("requires a populated scope graph")` at `:76-80`, Rust-gated at `:83-86`) doing field/return/method-chain typing with visited-set recursion, feeding the separate Rust-only `receiver_outcome` routing block at `resolution.rs:1045-1107`. A `PythonReceiverTyper` "beside" it means building a Python scope graph — that is slice 4 by definition, not this slice. The correct analogue for slice 2 is `recover_simple_ident` + `receiver_type_in_fn`, i.e. the same P6-lite tier Go uses.

**Correction 2 — `owner_lookup` is not class-aware.** The merged slice's `(file, class-span)` identity lives only in `self_owner_lookup_same_class` (`src/resolution.rs:710-737`), invoked solely from the `self|this|cls` rung for Py/JS/TS callers (`:955-968`). `owner_lookup` (`:692-708` → `owner_lookup_in_modules` `:745-789`) remains bare-name keyed: 1 candidate → Exact; >1 same-owner → demoted `QualifiedOwner`; >1 distinct owners → demoted `TraitCha`. **It is still the right sink**: Python/JS/TS classes are already fully indexed — `method_owner` (`languages/mod.rs:1084-1114`) populates `methods[(owner, name)]`, and `method_owner_class_node` (`:1182-1211`) populates `method_class_span` — so a recovered `Foo` hits cross-file with no scope graph. Collisions ride the existing recall-safe demote floor (measured below: small).

Today, a Py/JS `x.m()` with unknown receiver falls through R3 (import qualifier, `:995-1029`), R3b (qualifier-is-owner-key, `:1034-1043`), past the skipped R6 step 1, into the **R6 residue** (`:1166-1235`): own-file-single-owner or repo-single-owner → demoted `R6SingleOwner`; else `MultiOwnerCollision` drop. That residue is the population this slice converts.

### 1.2 The denominator — measured

Method: `prism nav call-stats` (release build) for baselines, plus a Python-`ast` mirror of prism's exact semantics (simple-ident receiver; import/R3b/self exclusions; typed-param / annotated-local / constructor-local recovery with shadow-bail; simulated `owner_lookup` on the bare-name index; replicated R6 residue for the "current bucket"). Package-scoped — note the bench `pydantic` checkout vendors `pydantic-core` (Rust), so whole-repo numbers there mix languages.

**Baselines (call-stats):**

| corpus | total sites | unknown-name drops | multi-owner drops | r6_single_owner demotes |
|---|---|---|---|---|
| fastapi/fastapi | 2,802 | 1,978 | 86 | 103 |
| pydantic/pydantic | 9,468 | 5,452 | 525 | 1,391 |
| mypy/mypy | 37,891 | 18,949 | 3,341 | 2,823 |
| express (full) | 949 | 876 | 0 | 0 |

**Flip prediction (script; `x.m()` simple-ident-receiver sites only):**

| corpus | `x.m()` sites | recoverable | → new **Exact** | …of which brand-new edges (from multi-owner drops) | demote→Exact | wrong-demote→clean-drop | inherited-miss | owner-key collisions |
|---|---|---|---|---|---|---|---|---|
| fastapi | 225 | 52 (23%) | **3** | 1 | 2 | 7 | 2 | 0 |
| pydantic | 1,196 | 262 (22%) | **48** | 20 | 28 | 53 | 0 | 10 |
| express | ~0 | 0 | 0 | — | — | — | — | — |
| black | 643 | 172 (27%) | **87** | 13 | 74 | 9 | 9 | 0 |
| httpx | 1,006 | 356 (35%) | **235** | 174 | 61 | 4 | 22 | 0 |
| mypy | 8,154 | 3,393 (**42%**) | **2,800** | 1,814 | 986 | 188 | 88 | 159 |

Recovery-kind mix everywhere: typed params ~80%, constructor locals ~15%, annotated locals ~5%.

**Honest read of the brief's three corpora: the buy there is small.** fastapi+pydantic yield ~51 new Exact edges and ~60 removed wrong edges — mostly precision, because their typed receivers (`Request`, `WebSocket`, `Scope`, `CoreSchema`, `ConfigDict`) are starlette/pydantic-core/TypedDict types with no in-repo method entries; today's `r6_single_owner` demotes on those sites bind to unrelated same-name methods, and the slice converts them to clean `ExternalReceiver` drops. **Express is exactly zero**: its `lib/` has **no ES classes** — `Router`/`View` methods are `prototype`-assigned, which `method_owner` (requires `class_body`) never indexes, so there is nothing to route to even with a perfect typer.

**But the slice is not small where prism is actually gated.** The committed Tier-A Python anchors are the typed corpora: mypy alone converts 1,814 multi-owner *drops* into Exact edges (54% of its drop bucket) plus 986 demote→Exact upgrades — a simultaneous recall and precision jump on the corpus that gates PRs. httpx and black confirm the trend. For TS, excalidraw shows a real population (64 classes, 248 `new Foo()` locals, ~278 simple typed params by rough grep) — moderate, nonzero.

Two measured soundness facts that drive the design:

- **Inherited-miss is real but bounded (~2.5% of recoverable):** sites where the recovered class is in-repo but `m` comes from a base class (mypy 88, httpx 22). Naïve Rust-style drop-on-miss would *regress* the subset of these that today gets a correct single-owner demote (mypy 50, httpx 13).
- **Bare-name owner collisions are minor:** 159 sites on mypy (~5% of recoverable), 0–10 elsewhere. The existing demote floor absorbs them; no new identity needed.

---

## 2. Architecture options

### Option A — open the P6-lite gates (recommended)

Extend the *existing* syntactic tier to Python/TS (JS gets the constructor-local arm for free), routed through the unchanged R6 step 1 → `owner_lookup`, with **one deliberate divergence from Rust/Go on the miss path**.

1. **Gates:** `resolution.rs:320` and `ast.rs:403` → `Rust | Go | Python | JavaScript | TypeScript | Tsx`, behind a new `ReceiverRecoveryConfig` boolean (`py_js: bool`, default on; `legacy()` off) — same rollback-lever pattern as `type_assertion`/`var_local` (`resolution.rs:276-300`).
2. **Typed-param arms** in `receiver_type_in_fn`: Python `typed_parameter`/`typed_default_parameter` (`type` field); TS `required_parameter`/`optional_parameter` (`type` field's inner type node). No JS arm.
3. **Binding-walk arms** in `walk_receiver_bindings` — *the soundness core*: Python `assignment` (ctor recovery when single `Name` target, else bail), `augmented_assignment`, `named_expression`, `for_statement` target, `with … as`, `except … as`, `global`/`nonlocal` (all bail); JS/TS `variable_declarator` (TS type annotation or `new_expression` init), `assignment_expression`, `for_in_statement` binding, `catch_clause` (bail). Comprehension targets are own-scope in py3 — correctly *ignored*, not bailed. The existing `>1 bindings → None` bail and nested-function stop (`ast.rs:3971`) apply unchanged.
4. **Constructor arms** in `constructor_type`: Python `Foo(...)` where callee is a CapWords identifier (not ALL_CAPS; dotted → last segment); JS/TS `new_expression` → constructor identifier. Unsoundness window (CapWords factory functions) is closed downstream: routing only mints an edge if `(Foo, m)` exists in the method index.
5. **Normalizer** `py_ts_receiver_type_key` beside `peel_type` (`owner_key` at `resolution.rs:96-105` strips `<`-generics and `::` but knows nothing of Python syntax): strip quoted annotations, peel `Optional[T]` / `T | None` / `Annotated[T, …]` / TS `| null | undefined`, take the last `.` segment, **refuse every other subscripted type** (`list[T]`, `dict[…]`, `Callable[…]` — a container's methods are not the element's; refusal = no recovery = today's behavior). Closed-list, like `peel_type`.
6. **Miss-path fail-open (the one routing change, `resolution.rs:1162` region):** for Py/JS/TS callers, on `owner_lookup` miss — if the recovered owner is a known in-repo class **with bases** (new `owner_has_bases: BTreeSet<String>`, recorded in build phase 1 where the class node is already in hand next to `method_class_span`, `call_graph.rs:560-567`, via a tiny `Language::class_node_has_bases` helper), **fall through to the R6 residue** instead of dropping; otherwise drop `ExternalReceiver` as Rust does. This kills the measured inherited-miss regression (mypy −50 lost edges) while keeping the precision win: no-base classes and external types (including method-less TypedDicts like pydantic's `ConfigDict`, which never enter the index) still drop. It follows the merged slice's fail-open-on-ambiguity precedent (`184208a`).
7. **Mechanical:** `CACHE_VERSION` 22→23 (`cpg_cache.rs:67`) — `CallSite.receiver_type` is cached and now populated for Py/JS. No call-stats changes needed: `typed_param`/`constructor_local` kinds surface automatically (`queries.rs:156`).

*Soundness:* collisions land in the existing demote floor (measured ≤5%); no `(file, class-span)` identity needed — that construct answers "which class am *I* in" (self receivers), while `x: Foo` collisions need import/module discrimination, which is slice 4's scope graph. *Blast radius:* ~5 files; Rust/Go arms untouched and byte-identical (gate opens beside them, never rewrites them). *Risk:* an unmodeled Python binding form silently skips a rebinding and recovers a stale type — bounded by the enumerated-arm + bail-by-default structure and the discriminating tests below.

### Option B — narrower subsets (constructor-locals only, or typed-params only)

Rejected on the numbers. Ctor-locals-only keeps ~15% of the buy. Typed-params-only keeps ~80% **but shrinks the soundness surface almost not at all**: a typed param rebound mid-function (`def f(x: Foo): x = g(); x.m()`) must still bail, so the full Python/JS binding walk — the only genuinely new risk surface in Option A — is required anyway. When the risky part is mandatory either way, dropping the cheap parts is pure buy-forfeiture.

### Option C — `PythonReceiverTyper` on a Python scope graph

The true `RustReceiverTyper` analogue: import-aware, shadow-precise, field/return-typed, collision-discriminating. It is also, definitionally, slice 4 (cross-module type resolution / scope graph). Everything Option A ships routes through `owner_lookup` behind the `ReceiverClassifier` seam, so C strangles A later without rework. Defer.

---

## 3. Recommendation + thin-slice plan

**Ship Option A** — Python + TS arms, JS inheriting the ctor-local arm, with the has-bases fail-open. It is the cheapest design that is sound at the established precision floor and has a *measured* buy where it matters: predicted on committed anchors ≈ **+2,800 Exact edges on mypy (1,814 brand-new), +235 httpx, +87 black**, plus the precision cleanup on the dynamic corpora (~250 wrong demoted edges removed across the five). Treat script numbers as upper bounds (±15%; the mirror approximates prism's function-attribution and decorator handling).

**PR sequencing (each independently revertable):**
- **PR-1:** `owner_has_bases` extraction + `CACHE_VERSION` 23 (inert data, no behavior).
- **PR-2:** AST arms + normalizer + gate opening behind `py_js` config; R6 miss-path fail-open. All behavior in one reviewable diff, one flag to kill it.
- **PR-3 (optional fast-follow):** loop-carried-rebind hardening — see Risks.

**Discriminating tests:**
- Recovery: Py typed param / `x: Foo = …` / `x = Foo()`; TS `f(x: Foo)`, `x?: Foo`, `const x: Foo`, `x = new Foo()`; quoted + `Optional[…]` + `T | None` peels; dotted `foo.Bar` → `Bar`.
- Soundness (must *refuse*): `x: list[Foo]` (container), rebind-after-param (`x = g()` before call), `for x in xs:` / `with … as x:` / `except E as x:` rebinds, ALL_CAPS call, multi-target assignment.
- Routing: in-repo hit → Exact `TypedParam`; two same-name classes → demoted; external type → `ExternalReceiver` drop; in-repo class with bases + missing `m` → residue fall-through (old demote preserved); no-base class + missing `m` → drop.
- Parity: Rust/Go fixtures byte-identical under `legacy` vs `expanded`; merged-graph coverage guard per the `3bd55cf` pattern.

**Acceptance (call-stats, package-scoped):**
- mypy/mypy: `typed_param`+`constructor_local` Exact kinds appear (~2–3k); `dropped_multi_owner` falls ~3,341 → ~1,700; `r6_single_owner` falls ~2,823 → ~1,900.
- pydantic/pydantic: ~+48 Exact; `dropped_external_receiver` rises from 0; `r6_single_owner` −~80.
- **Canaries flat:** express — zero resolved-edge changes (drop-reason relabels only); prism-itself and one Go anchor (caddy) — byte-identical call-stats; `tier-a --matrix-only` clean before commit, `--quick` on the Python anchors before review.

**Defer explicitly:** field-typed receivers `self.config.m()` (dotted qualifiers dominate the *remaining* residue — mypy's 2,823 demotes vs only 462 simple-ident ones — making S3.1's field-type index the natural slice 3); import-based collision narrowing and return-typed locals (slice 4 scope graph); Python MRO walk on miss (the fail-open flag bounds the loss until then); JS prototype-method indexing (the express population; separate and low-value).

---

## 4. Risks / unknowns

1. **Unmodeled Python binding forms** (the main one). A missed rebinding kind means recovering a stale type and minting a wrong Exact edge. Mitigation: arms enumerate binding kinds and bail by default; the refusal tests above; spot-audit ~30 random new `typed_param` edges on mypy against pyright during review.
2. **Loop-carried reassignment hole (pre-existing, shared with Rust/Go):** the pre-call-line guard (`ast.rs:3968`) ignores `x = other()` *after* the call inside a loop body, so iteration 2 dispatches on the wrong type. Symmetric with today's Rust/Go behavior; Python's mutation-happiness makes it worth a uniform fast-follow (bail when a post-call rebind shares a loop ancestor), not a blocker.
3. **Prediction error:** the mirror script approximates prism (nested-def attribution, decorated methods, `typed_default_parameter` coverage). Bucket *directions* are robust; magnitudes ±15%. Re-measure with real call-stats deltas in the PR description, per repo convention.
4. **Metaclass/`__getattr__` dynamism:** `x: Foo` then `x.m()` served dynamically — pydantic-style codebases can defeat any syntactic typer. The fail-open keeps such classes (they virtually always have bases) at today's behavior rather than dropping.
5. **TS grammar variance:** `Tsx` parameter/heritage node kinds must be covered alongside `TypeScript`; excalidraw (tsx-heavy) is the natural TS smoke corpus, but no TS corpus is Tier-A-gated yet — TS acceptance is call-stats-only for now (an unknown worth naming: no TS oracle in the harness).

**Bottom line:** on the brief's three corpora the denominator is small and I say so — fastapi/pydantic get a modest precision cleanup and express gets nothing. The slice still clears the bar decisively because the corpora that gate prism's accuracy harness (mypy/httpx/black) are exactly where typed receivers live: ~30–42% of unknown-receiver method calls become recoverable, converting thousands of drops and demotes into Exact edges through a seam that needs no new machinery — two language-gate matches, per-language AST arms, a closed-list normalizer, and one measured, bounded fail-open.
