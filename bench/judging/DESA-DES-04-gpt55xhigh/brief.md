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

Prism should add a member-level visibility tri-state, but only let the deferred-glob member arm use the new “known hidden” proof to continue. The current blanket poison is sound but over-conservative: the ruff spike says 14,663 of 14,665 `glob_expand.ambiguous` events are claimed-member/all-filtered cases, while only 2 are true multi-member ambiguity. The safe slice is to distinguish `Hidden` from `Unknown`, continue only on all-known-hidden members, and preserve poison for undecidable `pub(in)`.

## 1. Problem & Opportunity

Current `glob_lookup` resolves a deferred glob target, calls `scope_member_lookup_probed`, and treats `Unresolved + !member_rib_present` as provable absence but `Unresolved + member_rib_present` as ambiguous poison [src/name_resolution/engine.rs:431](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:431>), [src/name_resolution/engine.rs:461](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:461>). The bool is set when an explicit rib exists, before visibility filtering [src/name_resolution/engine.rs:618](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:618>).

That conflates two cases: known-hidden members and undecidable members. Rust already has the needed distinction internally: `vis_reaches` returns `Some(false)` for known hidden and `None` for undecidable `pub(in)` [src/name_resolution/rust_policy.rs:146](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:146>), while `visible` currently folds `None` into false [src/name_resolution/rust_policy.rs:241](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:241>). Edge visibility already exposes this as `GlobEdgeVis::{Visible,Hidden,Unknown}` [src/name_resolution/rust_policy.rs:246](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:246>), [src/name_resolution/types.rs:435](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/types.rs:435>).

The 14,663 events are the target population, not guaranteed recall. Many may continue to no result. Size the real buy in two phases: first split known-hidden vs undecidable; second track whether a hidden continuation later yields `Hit`, `Empty`, or `Poison`.

## 2. Cardinal Soundness Question

Rule: continue past a claimed-but-filtered member only when every cfg-compatible binding in that rib is policy-proven `Hidden`, with no `Visible` and no `Unknown`. If any binding is `Unknown`, poison.

Cases:

- Private member: outside the defining module, RustPolicy returns `Some(false)` for private visibility [src/name_resolution/rust_policy.rs:161](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:161>). The glob does not bring that member for this query, so continuing is sound.
- `pub(crate)` from another crate: different crate roots produce `Some(false)` [src/name_resolution/rust_policy.rs:153](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:153>). Continue is sound; often it will just become unresolved.
- `pub(super)` / resolved `pub(in)` from outside: if the ancestry check proves the query origin is outside the allowed subtree, continue is sound [src/name_resolution/rust_policy.rs:157](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:157>).
- unresolved `pub(in)`: `restrict == None` returns `None` [src/name_resolution/rust_policy.rs:161](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_policy.rs:161>). This must poison; the populator still discards `use` restricts as `vis(vis_kind, None)` [src/name_resolution/rust_populator/walk/items.rs:187](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_populator/walk/items.rs:187>), [src/name_resolution/rust_populator/walk/items.rs:192](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_populator/walk/items.rs:192>).

A sibling glob can mint a wrong singleton only if the first glob might have contributed the name. With `Some(false)`, it cannot for this vantage. With `None`, it might, so skipping would reopen the blocker fixed by `glob_expand_filtered_member_rib_does_not_fall_through` [tests/name_resolution/glob_expand_test.rs:341](</private/tmp/des-g5x-ws/DES-04/tests/name_resolution/glob_expand_test.rs:341>).

## 3. Architecture

Recommend option B, backed by option A: add a policy tri-state hook, then make `scope_member_lookup_probed` return a richer rib outcome. Do not re-examine Rust visibility in `glob_lookup`.

Proposed types:

```rust
pub enum MemberVis { Visible, Hidden, Unknown }

pub trait ResolutionPolicy {
    fn member_visible(&self, binding: &Binding, q: &ResolveQuery, trav: &TraversalCtx) -> MemberVis {
        if self.visible(binding, q, trav) { MemberVis::Visible } else { MemberVis::Unknown }
    }
}
```

Rust overrides `member_visible` using `vis_reaches`: `Some(true) => Visible`, `Some(false) => Hidden`, `None => Unknown`. The default maps invisible to `Unknown`, preserving fail-closed behavior for non-Rust policies.

Internally, replace `(Resolution, bool)` with something like:

```rust
enum RibProbe { NoRib, HasVisible, AllKnownHidden, SomeUnknown }
struct MemberLookup { resolution: Resolution, rib: RibProbe }
```

`resolve_rib` keeps returning the same `Resolution` for bare/path callers. A new private `resolve_rib_probed` computes `RibProbe`. `scope_member_lookup_probed` returns `MemberLookup`; `resolve_path_guarded` still treats all rib states except `NoRib` as `rib_present` so hidden locals continue blocking extern-crate fallback [src/name_resolution/engine.rs:560](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:560>). Only the deferred-glob member arm interprets `Unresolved + AllKnownHidden` as `Empty`.

Do not change the non-glob bare-name path behavior. Also leave the resolved-scope glob arm alone in this slice; Rust currently populates glob edges as `Pending` [src/name_resolution/rust_populator/walk/items.rs:237](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_populator/walk/items.rs:237>).

## 4. Telemetry

Current `glob_expand` has 8 buckets [src/name_resolution/glob_stats.rs:8](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/glob_stats.rs:8>) and `call_stats` emits them [src/navigation/queries.rs:297](</private/tmp/des-g5x-ws/DES-04/src/navigation/queries.rs:297>). Split `ambiguous` into:

- `member_multi`: `ResolvedSet`, `Ambiguous`, or non-single member result.
- `member_hidden_continued`: all-known-hidden rib, skipped.
- `member_undecidable`: unknown member visibility, poison.
- `member_hidden_then_hit`: a lookup with hidden continuation later returned candidates.
- `member_hidden_then_empty`: hidden continuation reached no resolution.

Keep an aggregate `ambiguous` only if downstream compatibility matters.

## 5. Tests & Acceptance

Add these discriminating fixtures:

- Known-hidden behind facade plus public sibling: `mod ta { struct S; } mod tb { pub struct S; } pub use ta::*; pub use tb::*;` resolves to `tb::S`.
- Undecidable `pub(in crate::ghost) struct S` plus public sibling still poisons, extending the existing blocker fixture [tests/name_resolution/glob_expand_test.rs:348](</private/tmp/des-g5x-ws/DES-04/tests/name_resolution/glob_expand_test.rs:348>).
- Direct path fallback remains blocked by claimed-but-invisible local ribs [tests/name_resolution/rust_populate_test.rs:1449](</private/tmp/des-g5x-ws/DES-04/tests/name_resolution/rust_populate_test.rs:1449>).
- Existing no-rib continuation and multi-glob combine tests stay green [tests/name_resolution/glob_expand_test.rs:239](</private/tmp/des-g5x-ws/DES-04/tests/name_resolution/glob_expand_test.rs:239>), [tests/name_resolution/glob_expand_test.rs:331](</private/tmp/des-g5x-ws/DES-04/tests/name_resolution/glob_expand_test.rs:331>).

Acceptance: `kind_exact` rises only if hidden continuation reaches real targets; `multi_target_exact_sites` must remain byte-flat; `member_undecidable` stays poison; Tier-A matrix/quick per AGENTS because this touches resolution/navigation.

## 6. Risks & Edge Cases

Main traps:

- Treating `Unknown` as `Hidden` recreates the wrong-singleton hole.
- Letting `AllKnownHidden` affect bare/path lookup would break shadowing and extern fallback.
- Reclassifying in `glob_lookup` would make the engine Rust-aware; keep `vis_reaches` inside RustPolicy.
- `ResolvedSet` is not hidden; keep poisoning unless a separate cfg-set propagation slice is designed.
- Hidden continuation must run inside the existing glob guard, preserving depth/cycle behavior [src/name_resolution/engine.rs:394](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:394>).
- Current empty pending glob path poisons before edge visibility [src/name_resolution/engine.rs:372](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/engine.rs:372>); the formal spec should decide whether to preserve or reorder that sentinel. `poison_scope` intentionally emits an empty pending glob [src/name_resolution/rust_populator/builder.rs:226](</private/tmp/des-g5x-ws/DES-04/src/name_resolution/rust_populator/builder.rs:226>).

## 7. Recommendation & Open Questions

Recommended slice:

- Add `MemberVis` plus `ResolutionPolicy::member_visible`, defaulting false to `Unknown`.
- Implement Rust member tri-state via `vis_reaches`, matching `glob_edge_visible`.
- Replace the bool probe with `RibProbe`; only deferred-glob member lookup uses `AllKnownHidden` to continue.
- Split telemetry before judging recall value.
- Keep public engine signatures unchanged.

Effort: light-medium. The pattern already exists for glob edges, but the tests are high value and must be precise.

Open questions: final telemetry schema, whether to apply member tri-state to resolved-scope glob edges later, whether to reorder the empty-path sentinel after edge visibility, and whether this behavior change needs a cache version bump like the parent slice.

Read-only note: I did not run tests or modify files; this is code/spec inspection only.


