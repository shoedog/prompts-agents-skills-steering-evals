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

Prism should add a member-level visibility tri-state only at deferred-glob member expansion: today `Unresolved + rib_present` collapses known-hidden and undecidable members into the same fail-closed poison path, and the ruff spike says 14,663 of 14,665 `glob_expand.ambiguous` events are in that collapsed population. The sound rule is narrow: continue past a claimed member rib only when every cfg-compatible claimant is provably hidden from the query vantage; poison on any undecidable member, any non-single visible member result, or any unresolved/pending uncertainty. Architecturally, make `scope_member_lookup_probed` return a richer member-rib probe powered by a new policy hook, not Rust-specific inspection in the engine.

**1. Problem & Opportunity**

Current deferred-glob expansion resolves a visible pending glob edge to a single target scope, then calls `scope_member_lookup_probed(graph, target_scope, q, policy, guard)`; if the member result is `Unresolved` with no rib, it continues, but if the rib existed it records `ambiguous` and poisons [src/name_resolution/engine.rs:431](src/name_resolution/engine.rs:431), [src/name_resolution/engine.rs:461](src/name_resolution/engine.rs:461). That was the correct blocker fix: a target scope that may contain the name must not be skipped to let a sibling glob mint a wrong singleton.

The over-conservatism is that `resolve_rib` filters all invisible candidates through `policy.visible(...) -> bool`; when all candidates fail, it can only return `Unresolved`, losing whether the failures were provably hidden or undecidable [src/name_resolution/engine.rs:281](src/name_resolution/engine.rs:281), [src/name_resolution/engine.rs:333](src/name_resolution/engine.rs:333). Rust already has the needed distinction for glob edges via `GlobEdgeVis::{Visible, Hidden, Unknown}` [src/name_resolution/types.rs:435](src/name_resolution/types.rs:435), backed by `vis_reaches(...) -> Option<bool>` [src/name_resolution/rust_policy.rs:146](src/name_resolution/rust_policy.rs:146).

The 14,663 ruff events are the target population, not the guaranteed buy. Real recall gain is only the subset where a known-hidden member lets the lookup continue and then a later sibling glob or valid path produces a clean singleton. If the hidden member is merely `pub(crate)` from another crate and no public sibling exists, the new behavior is continue to `Unresolved`, not a new edge.

Size the buy in two phases: first split the target population into `known_hidden` vs `undecidable`; then record whether `known_hidden` continuation later produces candidates or falls through unresolved. Final realized buy still comes from `call_stats.kind_exact` and `unresolved_unknown_name`, not from expansion-event counters [src/name_resolution/glob_stats.rs:1](src/name_resolution/glob_stats.rs:1), [src/navigation/queries.rs:269](src/navigation/queries.rs:269).

**2. Cardinal Soundness Question**

The invariant is “resolve-or-fall-through, never a wrong target” [src/name_resolution/engine.rs:11](src/name_resolution/engine.rs:11). Continuing past a filtered member is sound only when the engine can prove the visible glob exports no such member for this query.

Private member: sound to continue when queried from outside the defining module subtree. Rust glob re-export does not launder member privacy; `VIS_PRIV` reaches only the defining module and descendants [src/name_resolution/rust_policy.rs:161](src/name_resolution/rust_policy.rs:161). A private `ta::S` behind `pub use ta::*` is genuinely not contributed to an outside query, so a later `pub use tb::*` may resolve `S`.

`pub(crate)` from another crate: sound to continue when `crate_root(def_scope) != crate_root(q.from)` [src/name_resolution/rust_policy.rs:153](src/name_resolution/rust_policy.rs:153). It is not exported to an external dependent crate, so treating that glob as empty for the member is correct.

`pub(super)` / resolved `pub(in path)` from outside the allowed subtree: sound to continue when `vis_reaches` returns `Some(false)` [src/name_resolution/rust_policy.rs:157](src/name_resolution/rust_policy.rs:157). This is a proof of non-reachability, not a heuristic.

Undecidable `pub(in)` with no resolved restrict: must poison. `VIS_PUB_IN` returns `None` when `restrict` is absent [src/name_resolution/rust_policy.rs:161](src/name_resolution/rust_policy.rs:161), and the populator still has a Phase-1 stub returning `None` for restrict resolution [src/name_resolution/rust_populator/walk/mod.rs:268](src/name_resolution/rust_populator/walk/mod.rs:268). If skipped, a sibling glob could create exactly the wrong singleton the prior blocker guarded against; the existing test models this with `pub(in crate::ghost)` plus a public sibling [tests/name_resolution/glob_expand_test.rs:341](tests/name_resolution/glob_expand_test.rs:341).

Precise rule: for a deferred-glob target’s explicit member rib, continue only if all cfg-compatible bindings in that rib have member visibility `Hidden`, and none are `Visible` or `Unknown`. If any binding is `Unknown`, poison. If visible bindings exist, the existing single-clean-member rule applies: exactly one visible resolved candidate can contribute; non-single, `ResolvedSet`, `Ambiguous`, or pending poison remains fail-closed [src/name_resolution/engine.rs:433](src/name_resolution/engine.rs:433).

**3. Architecture**

Recommend option B: enrich `scope_member_lookup_probed` to return a structured probe, backed by a new policy-level member visibility hook. Do not re-examine Rust visibility in `glob_lookup`; the engine is explicitly language-neutral [src/name_resolution/engine.rs:1](src/name_resolution/engine.rs:1).

Add in `types.rs`:

```rust
pub enum MemberVis {
    Visible,
    Hidden,
    Unknown,
}

pub trait ResolutionPolicy {
    fn visible(&self, binding: &Binding, q: &ResolveQuery, trav: &TraversalCtx) -> bool;

    fn member_visible(&self, binding: &Binding, q: &ResolveQuery, trav: &TraversalCtx) -> MemberVis {
        if self.visible(binding, q, trav) { MemberVis::Visible } else { MemberVis::Hidden }
    }
}
```

Rust overrides `member_visible` using the same `vis_reaches(&binding.vis, binding.scope, q.from)` mapping used by `glob_edge_visible` [src/name_resolution/rust_policy.rs:241](src/name_resolution/rust_policy.rs:241), [src/name_resolution/rust_policy.rs:246](src/name_resolution/rust_policy.rs:246). The default is recall-safe for non-Rust policies: no `Unknown`, so old boolean behavior is preserved.

Change the probe shape:

```rust
enum MemberProbe {
    NoExplicitRib,
    ExplicitRib {
        saw_visible: bool,
        saw_known_hidden: bool,
        saw_unknown: bool,
    },
}
```

Then have `scope_member_lookup_probed` return `(Resolution, MemberProbe)` instead of `(Resolution, bool)` [src/name_resolution/engine.rs:605](src/name_resolution/engine.rs:605). `resolve_path_guarded` keeps using `probe.has_explicit_rib()` for the extern-crate fallback gate [src/name_resolution/engine.rs:549](src/name_resolution/engine.rs:549). The deferred-glob member arm uses the richer probe only when `member_res.status == Unresolved`.

Implementation detail: factor `resolve_rib` into `resolve_rib_classified(...) -> (Resolution, ExplicitRibProbe)` so the rib is scanned once. Visible bindings are processed exactly as today; hidden and unknown are skipped for candidate production, but the probe records which kind occurred. For ordinary `resolve_bare` and `resolve_path_guarded`, preserve current behavior: an explicit rib that filters to empty still returns `Unresolved` and does not lexically fall outward [src/name_resolution/engine.rs:201](src/name_resolution/engine.rs:201). The behavior change is only in the deferred-glob expansion member arm, where “known hidden” means “this glob contributes no such exported member.”

Reject option C. Having `glob_lookup` re-open the target rib and call Rust `vis_reaches` would duplicate `resolve_rib`’s cfg, pending, combine, and visibility semantics, and would violate the engine/policy split.

**4. Telemetry**

Split `glob_expand.ambiguous` instead of adding another overloaded bucket [src/navigation/queries.rs:297](src/navigation/queries.rs:297):

`member_multi`: visible member lookup returned `Resolved` with non-one candidate, `ResolvedSet`, or `Ambiguous`.

`member_hidden_continued`: explicit rib existed, all candidates were known hidden, and the glob was skipped as empty.

`member_hidden_then_candidate`: after at least one hidden continuation in this `glob_lookup`, a later glob produced at least one candidate.

`member_hidden_then_unresolved`: hidden continuation occurred but the lookup ultimately returned empty.

`member_undecidable`: explicit rib included at least one `Unknown`; poison.

For compatibility, keep legacy `ambiguous` for one slice as `member_multi + member_undecidable`, or update the call-stats shape test in the same PR [tests/integration/resolution_test.rs:1761](tests/integration/resolution_test.rs:1761).

**5. Tests & Acceptance**

Add focused tests beside the existing glob suite [tests/name_resolution/glob_expand_test.rs:145](tests/name_resolution/glob_expand_test.rs:145):

`glob_expand_known_hidden_member_continues_to_sibling`: `mod ta { struct S; } mod tb { pub struct S; } pub use ta::*; pub use tb::*;` resolves to `tb::S`. This fails before the change.

`glob_expand_known_hidden_member_no_sibling_unresolved`: private or cross-crate `pub(crate)` member behind a facade contributes nothing and does not poison.

`glob_expand_pub_in_unknown_member_still_poisons`: keep the existing `pub(in crate::ghost)` sibling-public fixture, but assert `member_undecidable == 1` instead of generic `ambiguous` [tests/name_resolution/glob_expand_test.rs:348](tests/name_resolution/glob_expand_test.rs:348).

`glob_expand_member_multi_still_poisons`: keep the compatible duplicate and cfg-exclusive `ResolvedSet` tests mapped to `member_multi` [tests/name_resolution/glob_expand_test.rs:188](tests/name_resolution/glob_expand_test.rs:188), [tests/name_resolution/glob_expand_test.rs:198](tests/name_resolution/glob_expand_test.rs:198).

Acceptance: on ruff, the 14,665 old ambiguous events should split roughly into 2 `member_multi` plus 14,663 `member_hidden_continued`/`member_undecidable`. The real win is `kind_exact` increase and/or `unresolved_unknown_name` decrease; precision canary `multi_target_exact_sites` should stay byte-flat [src/navigation/queries.rs:286](src/navigation/queries.rs:286), [src/navigation/queries.rs:291](src/navigation/queries.rs:291). Run full `cargo test`; because this affects name resolution feeding call resolution, also run `cargo build --release`, `cd eval && uv run tier-a --matrix-only --allow-stale-sut`, and `cd eval && uv run tier-a --quick --allow-stale-sut`.

**6. Risks & Edge Cases**

The main trap is turning `Unknown` into `Hidden`. `visible()` currently maps `None` to false for Rust [src/name_resolution/rust_policy.rs:241](src/name_resolution/rust_policy.rs:241); the new code must not derive tri-state from that boolean.

A second trap is changing normal bare-name or anchored-path shadowing. Explicit ribs must remain authoritative for ordinary lookups; the “continue” behavior is only for deciding whether a glob exported a member [src/name_resolution/engine.rs:592](src/name_resolution/engine.rs:592).

Depth-2 recursion and cycles stay unchanged: the tri-state decision happens after the target scope is cleanly resolved under `MAX_GLOB_DEPTH` and `with_glob` [src/name_resolution/engine.rs:107](src/name_resolution/engine.rs:107), [src/name_resolution/engine.rs:394](src/name_resolution/engine.rs:394).

Cross-glob `combine` remains the arbiter after candidates are collected. Continuing past a hidden member can expose two public sibling candidates; that must still become `Ambiguous`, not an arbitrary singleton [src/name_resolution/engine.rs:503](src/name_resolution/engine.rs:503), [src/name_resolution/rust_policy.rs:191](src/name_resolution/rust_policy.rs:191).

The empty-path sentinel for unresolved external globs still poisons before member probing [src/name_resolution/engine.rs:372](src/name_resolution/engine.rs:372). This slice should not reinterpret external/malformed glob targets as hidden.

**7. Recommendation & Open Questions**

Recommended slice:

- Add `MemberVis` and `ResolutionPolicy::member_visible` with a Rust override mirroring `glob_edge_visible`.
- Replace the boolean `rib_present` probe with a structured explicit-rib probe.
- In deferred-glob member expansion, continue only on all-known-hidden; poison on any unknown; preserve all existing non-single and pending fail-closed arms.
- Split telemetry so the 14,663-event population is measurable as known-hidden vs undecidable and as continued-to-candidate vs continued-to-unresolved.
- Keep normal bare-name and path-member behavior unchanged.

Effort estimate: light-to-medium. The core is small because the edge tri-state pattern already exists, but the tests must be precise; this area has repeatedly had blocker-class soundness reviews.

Open questions for the formal spec: whether `member_hidden_then_candidate` should count any later candidate or only a final `Resolved` singleton; whether legacy `ambiguous` remains as an aggregate for one release; and whether the deferred-glob member lookup should thread `TraversalCtx { via_glob: true }` for future non-Rust policies, even though Rust does not currently inspect it for bindings.


