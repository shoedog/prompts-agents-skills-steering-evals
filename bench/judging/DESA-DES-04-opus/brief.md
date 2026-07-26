# Conclusion-match grading — DES-04 (design/architecture), one anonymous arm

An engineer wrote the design memo below in response to the task brief. The
question was later SETTLED by the project's subsequent history. Grade the
memo against the settled outcome. You do not know who wrote it. Judge by
SHAPE and substance, not labels.

## Settled outcome (ground truth: the vindicated conclusion + repo evidence)

- conclusion: Recommend **option (b): a runtime member-visibility TRI-STATE
  policy** — split the blanket into `known_hidden / undecidable / member_multi`,
  continue past a filtered member rib ONLY when every binding is provably
  `Hidden` (never on `Unknown` — undecidable `pub(in)` must still poison),
  preserving the cardinal invariant "prism may miss an edge but must never mint a
  wrong singleton." Warns the realized buy is only the small subset that reaches
  a valid later result, NOT the 14,663 raw ambiguous events.
- vindication evidence: the tri-state design **landed on main** as design-of-record
  and staged read-inert exactly as recommended — `1a601f4 docs(spec):
  member-visibility tri-state design — design-of-record`, `ec8936d refactor:
  rename GlobEdgeVis -> VisibilityDecision (shared member/edge tri-state)`,
  `00ff23a feat(name-res): member_visible tri-state policy hook (read-inert)`,
  `daf29b1 feat(name-res): add member-visibility tri-state glob_stats counters
  (additive)`, `099ad84 feat(nav): clean-replace glob_expand ambiguous with
  member tri-state buckets`, cache `19->20`. CONFIRMED.
- proposed oracle: full marks = tri-state (hidden/undecidable/multi) with
  continue-only-if-all-proven-Hidden, poison-on-Unknown, cardinal-invariant
  stated, AND the "buy is the small reached-a-later-result subset, not the raw
  ambiguous count" caveat. Fail = "recover the ~14.6k ambiguous events as recall"
  (the naive over-claim) or any rule that continues on Unknown (unsound).

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

# Architecture analysis (xhigh, read-only) — prism member-visibility tri-state (glob expansion follow-on)

You are a senior compiler/static-analysis architect (codex gpt-5.5, xhigh). **Read-only.** Produce a
thorough **analysis + architecture design** for the next prism slice, grounded in the ACTUAL merged
code + a measured spike. Your output is the design seed a fresh session will turn into a formal spec —
so be concrete, opinionated, and complete. Cite `file:line`. Output **markdown** (a design doc): start
with a one-paragraph executive summary, then the sections below.

## Context — what just shipped (read it)

prism's Rust name-resolution engine now **expands deferred glob re-exports** (`pub use mod::*`) instead
of poisoning — merged to `main` (the glob-export-member-expansion slice). Read:
- `src/name_resolution/engine.rs`: `glob_lookup` (the deferred-`Pending` expansion arm), the member
  lookup `let (member_res, member_rib_present) = scope_member_lookup_probed(...)` and the match on
  `member_res.status`. **The arm you are extending:** `Unresolved if !member_rib_present => continue`
  (provably absent) vs `Unresolved => { record_ambiguous(); Poison }` (a rib CLAIMED the name but every
  candidate was visibility-filtered → conservatively poison). Also `scope_member_lookup_probed` (how
  `rib_present` is set), `resolve_rib` (returns `Unresolved` when all candidates fail `policy.visible`),
  and `CycleGuard`.
- `src/name_resolution/rust_policy.rs`: `visible(binding,q,trav)`, the tri-state
  `glob_edge_visible(edge,q,trav) -> GlobEdgeVis{Visible,Hidden,Unknown}`, and the shared
  `vis_reaches(vis, def_scope, from) -> Option<bool>` helper (Some(true)=visible, Some(false)=hidden,
  None=undecidable e.g. `pub(in)` with an unresolved restrict — `resolve_restrict` is a Phase-1 stub
  returning None, `rust_populator/walk/mod.rs`).
- `src/name_resolution/types.rs`: the `ResolutionPolicy` trait, `GlobEdgeVis`, `Edge`/`Binding`/`Vis`.
- `src/navigation/queries.rs`: `call_stats` → the `glob_expand` histogram (8 buckets incl. `ambiguous`).
- Spec/plan of the shipped slice: `docs/superpowers/{specs,plans}/2026-06-22-glob-export-member-expansion*`
  (esp. spec §3.2 member arm, §3.4 visibility, §9 deferred — the member-visibility tri-state is listed
  there as the biggest deferred lever).

## The measured spike (the lever)

On ruff, `glob_expand.ambiguous` = **14665**. A throwaway counter split it:
- **14663 (99.99%)** = the **claimed-but-visibility-filtered** member case (`Unresolved` + `rib_present`)
  — i.e. a facade `pub use mod::*` member lookup found a rib for the name in the target, but every
  candidate failed `policy.visible` (private / `pub(crate)` cross-vantage / `pub(super)` / undecidable
  `pub(in)`), so the current code conservatively **poisons**.
- **2** = genuinely multiply-defined members (`ResolvedSet`/`Ambiguous`).

So nearly the entire `ambiguous` bucket is the conservative blanket-poison. The shipped slice's BLOCKER
fix (the `member_rib_present` gate) is **recall-safe but conservative**: it poisons *both* a
**known-hidden** member (a private item the glob soundly does NOT re-export → the lookup could continue
to a sibling glob / outer scope) AND an **undecidable** `pub(in)` member (which MUST poison). The
proposed slice distinguishes them — a **member-visibility tri-state**, mirroring `glob_edge_visible` at
the member level.

## Deliver these sections

1. **Problem & opportunity.** Restate precisely what is conservatively poisoned and why; quantify the
   target (14663) and explain why it is the *target population*, not the guaranteed recall buy (the
   actual gain is the subset where *continuing* past a known-hidden member reaches a clean resolution —
   many may be `pub(crate)` cross-vantage names that resolve nowhere else → continue→unresolved, no
   edge). Propose how to SIZE the real buy before/within the slice (a deeper instrumentation split:
   known-hidden vs undecidable, and — harder — continue→resolves vs continue→unresolved).

2. **The cardinal soundness question.** Under the §7 invariant (resolve-or-fall-through, NEVER a wrong
   target): when is "continue past a claimed-but-filtered member" SOUND? Walk the cases — private
   member (glob re-exports only `pub`, so a private same-name is genuinely not brought → continue is
   sound), `pub(crate)` from another crate, `pub(super)`/`pub(in)` from outside, and the UNDECIDABLE
   `pub(in)`-no-restrict (must poison — can't prove not-visible). Is there ANY case where continuing
   past a filtered member could let a SIBLING glob mint a wrong singleton (the exact hole the parent
   BLOCKER fixed)? Define the precise rule that is provably recall-safe.

3. **Architecture.** Design the mechanism. Options to weigh: (a) a new `ResolutionPolicy` tri-state
   hook `member_visible(binding,q,trav) -> {Visible,Hidden,Unknown}` consulted in `resolve_rib`/the
   glob member arm; (b) extending `scope_member_lookup_probed` to return a richer probe (e.g. a
   tri-state "rib outcome": resolved / all-known-hidden / some-undecidable / no-rib) instead of the
   bool; (c) re-classifying in `glob_lookup` by re-examining the target rib's bindings via `vis_reaches`.
   Recommend ONE, with the trait/signature changes, where it plugs in, how it composes with the
   existing edge tri-state, and whether the engine stays language-neutral (the engine must not call
   `vis_reaches` directly — that's Rust-policy-internal). Address: does this also change the NON-glob
   bare-name path (`resolve_bare` step-2), or only the glob-expansion member arm? What is the recall-
   safe default for non-Rust policies?

4. **Telemetry.** What new `glob_expand` buckets make the recovery measurable + the conservatism
   sized (e.g. split `ambiguous` → `member_multi` / `member_hidden_continued` / `member_undecidable`)?

5. **Tests & acceptance.** The discriminating fixtures (a known-hidden member behind a facade with a
   public sibling same-name → resolves via the sibling; an undecidable `pub(in)` member → still
   poisons; no wrong-singleton). The acceptance metrics (the `kind_exact` buy, canary
   `multi_target_exact_sites` byte-flat, the bucket split, Tier-A).

6. **Risks & edge cases.** The soundness traps (this is the member-level mirror of a BLOCKER the parent
   reviews caught three times in this area — enumerate where it could go wrong). Interaction with
   depth-2 recursion, cross-glob `combine`, the empty-path sentinel.

7. **Recommendation & open questions.** Your recommended architecture in 3-5 bullets, the effort
   estimate (is this a light slice on the established tri-state pattern, or heavier?), and the open
   questions the formal spec must resolve.

Be rigorous on §2 (soundness) and §3 (architecture) — those are the core. Do not hand-wave the
recall-safety. Prefer the design that is provably sound + minimal over a clever one.


## The memo to grade

I now have the complete picture — the engine arm, the policy tri-state, the probe plumbing, the telemetry, the exact BLOCKER commit the design must not reopen, and the test infrastructure. Here is the design doc.

---

# Member-Visibility Tri-State for Glob Re-Export Expansion — Architecture & Design Seed

**Executive summary.** prism's Rust name-resolution engine now expands deferred `pub use mod::*` globs instead of poisoning, but it fails closed on one large class: when a facade's glob target *claims* the queried name in a rib yet every candidate is visibility-filtered, the engine poisons (`engine.rs:462-465`) rather than risk falling through to a sibling glob's wrong same-name — the exact hole the parent BLOCKER `bad55a6` closed. On ruff this blanket-poison accounts for **14663 of 14665** `glob_expand.ambiguous` events. The blanket is *recall-safe but conservative*: it treats a **known-hidden** member (a private/`pub(crate)`-cross-vantage/`pub(super)`-outside item the glob provably does *not* re-export) identically to an **undecidable** `pub(in)`-no-restrict member (which genuinely must poison). This slice introduces a **member-visibility tri-state** — the exact member-level mirror of the already-shipped edge-level `glob_edge_visible` (`rust_policy.rs:246-257`) — so a *provably* known-hidden member lets the lookup **continue** to a sibling glob while an undecidable member still poisons. The recommended mechanism is a new language-neutral `ResolutionPolicy::member_visible → {Visible,Hidden,Unknown}` hook aggregated by `resolve_rib`/`scope_member_lookup_probed` into a richer probe, keeping the engine language-neutral (it never calls `vis_reaches` directly). Soundness rests on Rust's re-export **visibility cap** (a `pub use` cannot widen a name past the item's own visibility), which makes "member's own vis provably does not reach the query origin" equivalent to "this facade does not deliver the name to the query origin." The change is tightly scoped to the glob-expansion member arm only; it must **not** touch `resolve_bare` step-1 or the path-prefix/crate-root-fallback path. Estimated effort: a **light-to-medium slice** on the established tri-state pattern, dominated by the soundness review, not the code.

---

## 1. Problem & opportunity

### What is conservatively poisoned

The changed arm is the deferred-`Pending` glob member lookup in `glob_lookup` (`engine.rs:431-466`). After the glob's target path resolves to a single in-repo `Target::Scope(T)`, the engine looks the queried name up in `T`:

```rust
let (member_res, member_rib_present) =
    scope_member_lookup_probed(graph, target_scope, q, policy, guard);   // engine.rs:431
match member_res.status {
    ResStatus::Resolved if …len()==1 => …contribute…,                     // the win
    …ResolvedSet | Ambiguous          => { record_ambiguous(); Poison }   // engine.rs:445  (genuine multi)
    ResStatus::Poisoned               => Poison,                          // engine.rs:449
    ResStatus::Unresolved if !member_rib_present => Empty,                // engine.rs:461  (provably absent → continue)
    ResStatus::Unresolved             => { record_ambiguous(); Poison }   // engine.rs:462  (CLAIMED-but-filtered → blanket poison)
}
```

`scope_member_lookup_probed` (`engine.rs:605-642`) builds the rib of explicit `(name,ns)` bindings in `T` (`:618-626`) and, when present, returns `resolve_rib(...)` (`:627-628`). `resolve_rib` (`engine.rs:265-339`) filters each binding through `policy.visible` (`:281`); a candidate that **claims the name but is not visible** is dropped without contributing and **without ascending** (`:281-286`). If every candidate is filtered, `candidates.is_empty()` → `unresolved()` (`:333-335`). So `Unresolved` + `member_rib_present == true` means: *a rib claimed the name in `T`, but every candidate failed `policy.visible`*. That is the `engine.rs:462` arm — a blanket `Poison`.

### The target population (14663) and why it is not the buy

The spike split the ruff `glob_expand.ambiguous = 14665` bucket (surfaced at `navigation/queries.rs:304`):
- **14663 (99.99 %)** = the `engine.rs:462` claimed-but-filtered blanket-poison.
- **2** = genuine multiply-defined members (`engine.rs:445`, `ResolvedSet`/`Ambiguous`).

14663 is the **target population**, *not* the recall buy. The blanket-poisoned population decomposes twice over:

1. **Known-hidden vs undecidable.** `policy.visible` collapses two distinct `vis_reaches` outcomes into `false` (`rust_policy.rs:241-244`): `Some(false)` (**known-hidden** — private, `pub(crate)` cross-crate, `pub(super)`/`pub(in)` from outside) and `None` (**undecidable** — `pub(in path)` whose `resolve_restrict` is the Phase-1 stub, `walk/mod.rs:271-277`). Only the *known-hidden* subset is a candidate for continuation; the undecidable subset **must** keep poisoning.

2. **continue→resolves vs continue→unresolved.** Even within the known-hidden subset, the *actual* buy is only the sites where *continuing past* the hidden member reaches a clean single resolution — a sibling glob (or, rarely, an outer scope inside the module boundary) that yields exactly one visible candidate. A large share of the 14663 are plausibly `pub(crate)` names queried cross-vantage (cross-crate facade re-exports) that resolve **nowhere else** → continue → `Unresolved` → **no edge minted, no buy, no harm** (just a different but equivalent negative result). The realized edge buy is `kind_exact` (`queries.rs:286`), not the bucket size.

### Sizing the real buy — a two-stage instrumentation plan

**Stage 1 (cheap, ship-before or ship-with as instrumentation).** In the `engine.rs:462` arm, re-scan `T`'s claimed rib and classify via `vis_reaches`: does *every* filtered binding return `Some(false)` (known-hidden), or does *any* return `None` (undecidable)? Split the single `record_ambiguous()` into `member_hidden` vs `member_undecidable`. This partitions 14663 into the *continuable upper bound* and the *forced-poison floor* at ~zero cost (one extra pass over an already-materialized rib).

**Stage 2 (harder — the true buy).** continue→resolves vs continue→unresolved cannot be read off the rib; it requires performing the continuation and observing the outcome. Two options: (a) a shadow counter — when the arm *would* continue, run the remainder of `glob_lookup` + the caller's `combine` in shadow and record whether the final status is `Resolved`; or (b) simply build the slice behind the existing local-sink test seam (`resolve_with_stats`, `engine.rs:73`) and diff `kind_exact`/`unresolved_unknown_name` on ruff+prism against a `main` worktree (the spec's own acceptance method, §7). **Recommend (b)** — the `kind_exact` delta *is* the ground-truth buy; a shadow counter would essentially re-implement the slice. Report Stage-1 as the upper bound and the `kind_exact` delta as the realized buy.

---

## 2. The cardinal soundness question

The §7 invariant (`engine.rs:11-15`): **resolve-or-fall-through, NEVER a wrong target.** For the glob member arm, "fall through" means *continue to the next glob edge (or the outer walk)* instead of poisoning. The question: **when is continuing past a claimed-but-filtered member SOUND?**

### The governing Rust rule: the re-export visibility cap

`pub use m::*` in facade module `S`, queried for `N` from origin `V`. For `V` to receive `N` through the facade, two independent hurdles must both pass:

1. **`N` must be accessible from `S`** (the facade). A glob import brings only items visible from the module containing the `use`; a `pub use` does **not** launder privacy.
2. **The re-exported name in `S` must reach `V`.** Rust caps the effective re-export visibility at `min(edge visibility, item's own visibility)` — **a `pub use` can never make a name *more* visible than the item itself.**

The engine splits these: the **edge** hurdle is `glob_edge_visible` (`rust_policy.rs:246-257`), already gating each edge before it may contribute or poison; the **member** hurdle is `policy.visible` on the target binding, judged from `q.from == V` (the original origin is threaded unchanged into `scope_member_lookup_probed`, `engine.rs:432`).

**The cap is the whole soundness argument.** If the member's *own* declared visibility provably does not reach `V` (`vis_reaches(member.vis, member.scope, V) == Some(false)`), then because the effective re-exported visibility is ≤ the member's own visibility, the re-exported name *also* provably does not reach `V`. **This facade does not deliver `N` to `V`.** Therefore continuing past it — to a sibling glob, or (within the module boundary) the outer walk — cannot drop a real candidate. The member was never a candidate for `V` in the first place.

### Case walk

| Member vis (from `V`) | `vis_reaches` | Delivered to `V`? | Continue sound? |
|---|---|---|---|
| **private** (glob re-exports only accessible items; a private same-name is not brought) | `Some(false)` | No | **Yes** |
| **`pub(crate)`, `V` in another crate** | `Some(false)` | No (cross-crate cap) | **Yes** |
| **`pub(super)` / `pub(in P)` with `V` outside the subtree** | `Some(false)` | No (cap) | **Yes** |
| **`pub(in P)` with `resolve_restrict` unresolved** | `None` | **Cannot prove** | **No — MUST poison** |

The undecidable `pub(in)`-no-restrict row is the hard case. `resolve_restrict` returns `None` (`walk/mod.rs:271-277`) and the populator discards the `pub(in)` path (spec §3.4). We *cannot prove* the member does not reach `V`, so it *might* be the real, delivered target — and letting a sibling glob mint a singleton for a *different* `N` would violate §7. This is precisely the edge-level `Unknown → Poison` rule (`engine.rs:385-388`) mirrored at the member level.

### The sibling-glob wrong-singleton hole — closed by construction

This is the exact hole the parent BLOCKER `bad55a6` closed. Its discriminating test `glob_expand_filtered_member_rib_does_not_fall_through` (`tests/name_resolution/glob_expand_test.rs:340-362`) uses `mod ta { pub(in crate::ghost) struct S; }` + `mod tb { pub struct S; }` + two globs: without the probe it fell through `ta` and minted the **wrong singleton `tb::S`**; with the probe it poisons.

Crucially, that fixture is the **undecidable** case (`pub(in crate::ghost)`, restrict unresolved → `None`). The tri-state **keeps poisoning it** — it lands in the `Unknown` branch. The tri-state only continues on the **provable `Some(false)`** branch, where the cap guarantees `ta`'s member is not delivered to `V`, so `tb::S` is the *sole* delivered candidate and resolving to it is **correct**, not a wrong singleton.

Is there *any* case where continuing past a `Some(false)` member lets a sibling mint a wrong singleton? Only if `vis_reaches` were unsound (reporting `Some(false)` for a member that actually reaches `V`). But the tri-state reuses the **same** `vis_reaches` (`rust_policy.rs:146-165`) that `visible()` and `glob_edge_visible()` already trust for the resolve/filter/skip decisions — **no new visibility rule, one new application of the existing rule** (mirroring the shipped edge tri-state, spec §3.4). The tri-state introduces **no new soundness surface**.

### The precise recall-safe rule

> In the `engine.rs:462` arm (`Unresolved` with a claimed rib), re-examine the claimed rib's bindings. **Continue** (`Empty`) iff **every** filtered binding's `vis_reaches(binding.vis, binding.scope, q.from) == Some(false)` (all-known-hidden). **Poison** if **any** filtered binding returns `None` (some-undecidable). The all-visible case never reaches here (it resolves).

Because we are in the `Unresolved` arm, `candidates` is empty ⇒ every binding was filtered ⇒ each is `Some(false)` or `None`. `resolve_rib`'s `Pending`-chase failure paths (`:322`, `:328`) surface as `Ambiguous`/`Poisoned`, **not** `Unresolved`, so they are handled by the earlier arms and never reach this classification.

---

## 3. Architecture

### The three options, weighed

- **(a) A policy tri-state hook** `member_visible(binding,q,trav) -> {Visible,Hidden,Unknown}`, mirroring `glob_edge_visible`. Necessary: the classification *requires* per-binding tri-state, and `policy.visible` returns a lossy `bool`. Only the policy may compute it (`vis_reaches` is Rust-internal).
- **(b) A richer probe from `scope_member_lookup_probed`** — replace the `bool` `rib_present` (`engine.rs:611`) with a small enum carrying `NoRib / Contributed / AllHidden / SomeUndecidable`. Necessary as the *carrier* — the glob arm switches on it.
- **(c) Re-classify inside `glob_lookup` by re-examining `T`'s bindings via `vis_reaches`.** **Rejected on architecture grounds:** the engine must stay language-neutral (`engine.rs:5`, "No Rust-ism lives here"); calling `vis_reaches` directly from the engine leaks a Rust-policy internal. Routing it through a hook collapses (c) into (a).

### Recommendation: (a) ⊕ (b) — hook + probe, they compose

They are **not** alternatives. (a) supplies the per-binding tri-state; (b) is where the engine aggregates it structurally and hands it to the glob arm. This keeps the engine neutral (it aggregates, never interprets visibility) and makes the member tri-state the exact structural twin of the edge tri-state.

**1. Neutral tri-state enum.** Reuse the existing `GlobEdgeVis { Visible, Hidden, Unknown }` (`types.rs:435-440`) for both hooks; rename to a neutral `VisTriState` (edge and member both alias it) so the name no longer implies "edge-only." (Mechanical; a type alias avoids churn if a rename is undesired.)

**2. New policy hook** on `ResolutionPolicy` (`types.rs:551`), sibling to `glob_edge_visible` (`types.rs:582-589`):

```rust
/// Tri-state member accessibility for glob-expansion continue-vs-poison.
/// Default preserves today's conservative poison: Visible iff `visible()`,
/// else Unknown (a non-adopting policy keeps failing closed).
fn member_visible(&self, binding: &Binding, q: &ResolveQuery, trav: &TraversalCtx) -> VisTriState {
    if self.visible(binding, q, trav) { VisTriState::Visible } else { VisTriState::Unknown }
}
```

Rust impl (`rust_policy.rs`), a 3-line mirror of `glob_edge_visible` (`:246-257`) over the shared `vis_reaches`:

```rust
fn member_visible(&self, binding, q, _trav) -> VisTriState {
    match self.vis_reaches(&binding.vis, binding.scope, q.from) {
        Some(true) => VisTriState::Visible,
        Some(false) => VisTriState::Hidden,
        None => VisTriState::Unknown,
    }
}
```

**3. Aggregate in `resolve_rib`.** Replace the `policy.visible` filter (`engine.rs:281`) with `policy.member_visible`: `Visible` → contribute (unchanged); `Hidden` → skip, note `saw_hidden`; `Unknown` → skip, note `saw_unknown`. When `candidates.is_empty()` at `:333`, produce the probe: `saw_unknown ⇒ SomeUndecidable` else `AllHidden`. `resolve_rib` returns `(Resolution, RibProbe)`; its two callers — `resolve_bare:215` (discards the probe) and `scope_member_lookup_probed:628` (forwards it) — adjust trivially. The `Pending`-chase early returns (`:322,:328`) carry a placeholder probe (irrelevant — the glob arm reads `status` first).

**4. Thread the probe** through `scope_member_lookup_probed` — change its return from `(Resolution, bool)` (`engine.rs:611`) to `(Resolution, RibProbe)`. The no-glob-rib path (`:636-641`) returns `NoRib`.

**5. The glob member arm** (`engine.rs:433-466`) switches on `(status, probe)`:

```rust
ResStatus::Unresolved => match probe {
    RibProbe::NoRib          => GlobOutcome::Empty,        // provably absent (unchanged)
    RibProbe::AllHidden      => { record_member_hidden();     GlobOutcome::Empty  }  // NEW: continue
    RibProbe::SomeUndecidable=> { record_member_undecidable();GlobOutcome::Poison }  // was the blanket poison
    _ /*Contributed*/        => unreachable!("Unresolved ⇒ nothing contributed"),
}
```

### Composition with the edge tri-state

Perfect structural mirror: edge → `glob_edge_visible` gates *whether the whole edge participates* (`engine.rs:383-390`); member → `member_visible` gates *whether a target member is delivered*. Both use `VisTriState`, both delegate to the single `vis_reaches`, both map `Unknown → Poison` and `Hidden → skip/continue`. The engine composes them structurally and remains language-neutral.

### Blast radius — what does NOT change

- **`resolve_bare` step-1 (bare-name self rib)** is **unaffected.** A claimed self rib returns `resolve_rib(...)` and stops regardless of the result (`engine.rs:213-216`) — the §7 decoy rule. A bare name never has a "sibling glob" to continue to (the rib is authoritative; the module-boundary stop, `rust_policy.rs:181-189`, prevents outer fall-through). `resolve_bare` simply drops the new probe. (In practice bare self-rib filtering is near-empty anyway: a private local item is visible to its own module.)
- **The path-prefix walk and the crate-root fallback** are **unaffected.** `resolve_path_guarded`'s fallback gate keys only on `NoRib` (`engine.rs:560`, today `!rib_present`); `AllHidden`/`SomeUndecidable`/`Contributed` all block the fallback exactly as `rib_present==true` does today. An anchored path targets a specific chain and has no sibling to continue to.
- **Only the glob-expansion member arm** gains the `AllHidden → continue` case. This is the surgical scope.

### Recall-safe default for non-Rust policies

The default `member_visible` maps `visible()==true → Visible`, `false → Unknown` — i.e. non-adopters keep **poisoning** on any filtered member (today's behavior). This is behavior-preserving and moot in practice (only the Rust populator emits deferred glob edges, spec §3.2/§9), but it makes the tri-state strictly **opt-in** and closes off any accidental recall change for a future policy.

---

## 4. Telemetry

The `ambiguous` bucket (`glob_stats.rs:62`, surfaced at `queries.rs:304`) is currently **overloaded** across two `record_ambiguous()` call sites — the genuine multi-member (`engine.rs:446`) and the blanket-poison (`engine.rs:463`) — and the spike showed a 14663:2 skew. Split it to make both the recovery and the residual conservatism measurable:

| New bucket | Replaces / adds | Meaning |
|---|---|---|
| `member_multi` | `record_ambiguous()` at `engine.rs:446` | genuine `Resolved(>1)`/`ResolvedSet`/`Ambiguous` member (the "2" on ruff) |
| `member_hidden_continued` | **new**, `AllHidden` arm | provably known-hidden → **now continues** (the realized-recovery upper bound) |
| `member_undecidable` | `record_ambiguous()` at `engine.rs:463` | some-undecidable `pub(in)` → still poisons (the forced-poison floor) |

Add three `AtomicUsize` counters + snapshot fields (`glob_stats.rs:9-30,85-97`), three `record_*` methods, wire into the reset/snapshot arrays, and extend the `glob_expand` JSON object (`queries.rs:297-306`). Retire (or alias) `ambiguous`. Post-slice, `member_hidden_continued` sizes the recovery attempt and `member_undecidable` sizes the remaining conservatism (which the future `resolve_restrict` follow-on, spec §9, would attack). The realized *edge* buy remains read from `kind_exact` (`queries.rs:286`), not from these expansion-event counts (`glob_stats.rs:1-4`).

---

## 5. Tests & acceptance

### Discriminating fixtures (`tests/name_resolution/glob_expand_test.rs`)

Every test must fail under the *old* blanket-poison; use the local-sink `single_file_resolve` helper (`glob_expand_test.rs:66`) for parallel-safe bucket assertions.

1. **`glob_expand_known_hidden_member_continues_to_sibling` (the recovery).** `mod ta { struct S; }` (private) + `mod tb { pub struct S; }` + `pub use ta::*; pub use tb::*;`. Query `S` from root → **`Resolved` to `tb::S`**, `resolved_l1 == 1`, `member_hidden_continued == 1`. (RED today: poisons.) This is the exact structural sibling of the BLOCKER fixture at `:348` with `pub(in crate::ghost)` swapped for a private `struct S` — the *only* difference is decidable-hidden vs undecidable.
2. **`glob_expand_filtered_member_rib_does_not_fall_through` (existing, `:340-362`) must stay GREEN.** The `pub(in crate::ghost)` case is undecidable → still `Poisoned`, now `member_undecidable == 1`. (Update the assertion from `snap.ambiguous` to the renamed bucket.)
3. **`glob_expand_known_hidden_no_sibling_continues_to_unresolved` (no-harm, no-buy).** `mod ta { struct S; } pub use ta::*;` with no other `S`. Query `S` from root → **`Unresolved`** (continue → nothing else), `member_hidden_continued == 1`, no edge, `kind_exact` unchanged. Proves the dominant continue→unresolved path is harmless.
4. **`glob_expand_pub_crate_cross_vantage_member` (the ruff-shape).** `pub(crate)` member queried from a *simulated* other-crate origin → `Hidden` → continue; with a public sibling → resolves to the sibling; without → unresolved. Exercises the realistic 14663-population shape.
5. **`glob_expand_mixed_hidden_and_undecidable_poisons` (the AND rule).** One glob target rib with a private `S` **and** a `pub(in unresolved)` `S` under compatible cfg → `SomeUndecidable` → **poison** (any-undecidable dominates). Guards the "all `Some(false)`" quantifier.
6. **No-wrong-singleton canary at depth 2.** A known-hidden member behind a *two-hop* facade with a sibling → resolves via the sibling at `resolved_l2`; never a wrong singleton. Confirms the classification applies at every glob depth.

### Acceptance metrics

- `cargo fmt --check`; `cargo test --lib`; **`cargo test --test name_resolution`** (the seam the spec flags as must-not-skip, §7); `cargo test --test integration`.
- `cargo build --release`, then call-stats deltas vs a `main` worktree on **ruff** and **prism**: **`kind_exact` increases / `unresolved_unknown_name` decreases** (the buy); **`multi_target_exact_sites` byte-identical** (`queries.rs:291` — the hard wrong-Exact canary; any increase = a wrong singleton = BLOCKER); the new `glob_expand` split populated and self-consistent (`member_hidden_continued + member_undecidable ≈ old ambiguous ≈ 14663 on ruff; member_multi ≈ 2`).
- **Tier-A:** `cd eval && uv run tier-a --matrix-only --allow-stale-sut` (0 regressions), and ruff M2 `uv run tier-a --corpus ruff --allow-stale-sut` (`baseline_invalid=false`, 0 regressions).
- codex xhigh final-diff review: SHIP.

---

## 6. Risks & edge cases

This is the **member-level mirror of a BLOCKER the parent reviews caught three times** in this arm. The soundness traps:

1. **Conflating known-hidden with undecidable (the primary trap).** If the classifier treated `None` (`pub(in)` unresolved) as continuable, it would reopen `bad55a6` exactly. Mitigation: the AND-quantifier rule (continue **iff all** `Some(false)`; **any** `None` ⇒ poison) + fixture #5. `resolve_restrict` remains a `None` stub (`walk/mod.rs:271-277`), so **every** `pub(in)` member is `Unknown` today — the undecidable arm carries real load; do not let it silently narrow.
2. **The member-vantage subtlety.** Member visibility is judged from `q.from == V` (the far origin, `engine.rs:432`), not from the facade module `S`. For the **known-hidden continue** this is sound (the re-export cap: `Some(false)` from `V` ⇒ not delivered to `V`, §2). But the *symmetric over-resolution risk* — a member `Some(true)` from `V` yet not accessible from `S` (e.g. `pub(in P)` with `V ∈ P, S ∉ P`) — is a **pre-existing** property of the shipped resolve arm, currently masked because such members are `pub(in)`-unresolved → `Unknown` → poison. Flag it as an open question (below), not a regression this slice introduces.
3. **Rib-shadows-glob interaction.** If target `T` has an explicit private `S` (rib) *and* a `pub use other::*` bringing a public `S`, the rib shadows the glob (`scope_member_lookup_probed:627` returns at the rib without consulting `T`'s globs). Continuing past a `pub use T::*` on the strength of `T`'s private (hidden) rib `S` is **correct** Rust: the explicit private `S` is the name `S` in `T` and is not re-exported, so `T` delivers no `S`. Sound — but add a test; it is a non-obvious interaction.
4. **Depth-2 recursion.** The classification lives in `resolve_rib`/`scope_member_lookup_probed`, so it applies uniformly at every glob depth (`MAX_GLOB_DEPTH == 2`, `engine.rs:107`). Undecidable/poison always surface up the chain as `Poisoned` (never `Unresolved`), so an inner poison never masquerades as a continuable inner miss. Fixture #6 guards this.
5. **Cross-glob `combine`.** Skipping a known-hidden glob removes a **non-candidate** (it contributed nothing anyway), so `combine` (`rust_policy.rs:191-239`) sees exactly the candidate set it would if the hidden glob truly lacked the name: two surviving distinct globs → `Ambiguous`/`ResolvedSet` (never a silent pick, `glob_expand_distinct_targets_two_globs:330-338`); a diamond → dedup to one `Resolved`. The wrong-Exact canary `multi_target_exact_sites` guards it.
6. **Empty-path sentinel.** `pub use self::*` → empty `RawPath` → `external` bucket (`engine.rs:372-376`), never reaching the member arm. Unaffected.

---

## 7. Recommendation & open questions

### Recommended architecture (3–5 bullets)

- Add a neutral `VisTriState` (rename/alias of `GlobEdgeVis`, `types.rs:435`) and a `ResolutionPolicy::member_visible(binding,q,trav) -> VisTriState` hook — the exact member-level mirror of `glob_edge_visible`, Rust impl delegating to the shared `vis_reaches` (`rust_policy.rs:146`). Default (non-Rust) = `Visible`-else-`Unknown` (poison-preserving, opt-in).
- Replace `policy.visible` in `resolve_rib` (`engine.rs:281`) with `member_visible`, aggregate the per-binding outcomes into a `RibProbe { NoRib, Contributed, AllHidden, SomeUndecidable }`, and thread it in place of the `bool` from `scope_member_lookup_probed` (`engine.rs:611`).
- In the glob member arm (`engine.rs:462`), add `AllHidden → continue`; keep `SomeUndecidable → poison`. **Continue iff all filtered candidates are `Some(false)`; any `None` poisons.** Engine stays language-neutral (aggregates tri-states; never calls `vis_reaches`).
- Split the overloaded `ambiguous` bucket into `member_multi` / `member_hidden_continued` / `member_undecidable` (`glob_stats.rs`, `queries.rs:297-306`) to size recovery vs residual conservatism.
- Do **not** touch `resolve_bare` step-1 or the path-prefix/crate-root fallback; scope strictly to the glob-expansion member arm.

### Effort estimate

A **light-to-medium slice on the established tri-state pattern** — not a heavy one. The tri-state enum, hook shape, `vis_reaches` delegation, `Unknown → Poison` discipline, telemetry seam, and local-sink test harness all already exist from the shipped edge tri-state. The genuine work is (i) the mechanical `bool → RibProbe` thread-through at two call sites, (ii) the telemetry split, and (iii) ~5–6 discriminating fixtures. The dominant cost is the **adversarial soundness review**, given this arm's three-time BLOCKER history — budget for that, not the diff. Roughly one focused session.

### Open questions for the formal spec

1. **Member vantage.** Is `Some(false)`-from-`q.from` sufficient, or should `member_visible` also require visible-from-the-facade-module (the `min(edge, member)` composed at both vantages)? §2 argues the re-export cap makes `Some(false)`-from-`V` sufficient for the *known-hidden continue*; the spec should state that invariant explicitly and decide whether to add a facade-vantage check to close the symmetric over-resolution risk (trap #2) once `resolve_restrict` is populated.
2. **Hook shape.** Should `member_visible` **replace** `visible` inside `resolve_rib` (cleaner, but touches the contribution path) or be a **second call** only over the filtered set (more surgical, one extra call per filtered binding)? Recommend replace + behavior-preserving default; confirm.
3. **`RibProbe` granularity.** Is the 4-variant enum warranted, or does a `(bool no_rib, bool any_unknown)` pair suffice for the two consumers (glob arm + crate-root fallback)? Recommend the enum for readability; confirm the `NoRib`-only mapping of the fallback gate (`engine.rs:560`).
4. **Ordering vs the `ResolvedSet`-propagation follow-on** (spec §9): keep orthogonal (this slice is continue-vs-poison on *filtered* members; that one is propagate-vs-poison on *multi* members). Confirm they land separately.
5. **Should Stage-1 instrumentation ship first** as its own tiny PR (split the bucket, measure known-hidden vs undecidable on ruff) before the behavior change, to de-risk the buy estimate? Recommend yes if the 14663:? split is decision-relevant to prioritization.
