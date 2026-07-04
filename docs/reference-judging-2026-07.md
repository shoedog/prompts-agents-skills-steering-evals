# Fable-vs-gpt-5.5 reference judging — 2026-07-04

12 tasks, each completed independently by Fable 5 (fresh replay, bench harness)
and by gpt-5.5 (the original codex session the task was mined from). 11 judged
as blind A/B pairs (randomized arm order, sealed keys); RES-01 judged
single-arm against its ground-truth deliverable. Two judges per item, one per
family: codex gpt-5.5 xhigh (isolated scratch cwd) and claude-sonnet-5.
Binary verdicts; "materially better" = a reviewer would insist the other arm
adopt the difference.

Inputs per pair: verbatim task envelope + both final diffs (both arms' suites
green). Artifacts: `bench/judging/<ID>/{brief.md,key.json,verdict-*.json}`,
diffs in `bench/out/<ID>/{fable.diff,reference.diff}`.

## Verdicts (unblinded)

| Task | codex judge | sonnet judge | Consensus |
|---|---|---|---|
| IMPL-01 watchdog | fable | fable | **Fable** |
| IMPL-03 sqlite batch | reference | fable | split |
| IMPL-04 retry config | reference | reference | **Reference** |
| IMPL-05 commit-msg refactor | reference | ~~fable~~ VOID¹ | single-judge: reference |
| IMPL-06 snapshot merge | fable | fable | **Fable** |
| IMPL-08 scope-graph wiring | reference | reference | **Reference** |
| IMPL-12 binding lookup (probe) | fable | fable | **Fable** |
| IMPL-13 mailbox loop (py) | reference | reference | **Reference** |
| INFRA-01 gawk fix | parity | parity | **Parity** |
| REF-01 mint-parity refactor | fable | fable | **Fable** |
| REF-03 descope refactor | reference | parity | split |
| RES-01 docs audit (rubric) | GT better² | candidate better² | diverge |

¹ The sonnet judge for IMPL-05 ran `cat key.json` in its cwd (the brief dir)
— verdict unblinded, voided. Codex judges ran in isolated scratch dirs and
could not reach keys. Fix for future rounds: claude judge cwd must not
contain key files.
² Divergent rubric readings: sonnet graded drift-finding recall (11/15
covered, 10 correct extras, 1 unsupported → candidate better); codex graded
against the GT doc as spec (13/18 covered but 7 prescriptions unsupported /
required outputs missing, e.g. no `docs/REPO_MAP.md` → GT better).

**Tally (valid consensus): Fable 4 · Reference 3 · Parity 1 · Split 2 ·
single-judge 1.** Judge agreement 8/11 (73%); each judge leaned mildly toward
its own family (sonnet +2 fable-relative, codex +3 reference-relative) — the
consensus core is the robust result. The 3 unresolved rows (IMPL-03, IMPL-05,
REF-03) go to owner spotcheck.

## The one consistent Fable edge: test rigor

On the tests-stronger dimension the judges agreed 10/11: **Fable's tests
stronger in 7 pairs** (IMPL-01/03/05/06/12, REF-01/03), reference stronger in
2 (IMPL-08/13), parity elsewhere. This held even in pairs where the overall
verdict went to the reference arm.

Flagship (IMPL-12, the latent-bug probe): gpt-5.5's original shipped a
per-param BindingRef ordinal collision (every multi-param fn's params got
ordinal 0) that its own tests missed. In the blind replay, **Fable's
implementation batches the param bind (ordinals verified unique) and its 9
tests cover shadowing/relet/poisoning/ambiguity classes; the sonnet judge
empirically reproduced gpt-5.5's collision from the diffs in a scratch
worktree.** Nuance from the codex judge: even Fable's tests don't assert the
two-param BindingRef case *directly* — the probe is passed by design choice
plus adjacent coverage, not by an explicit regression test.

## Where the reference (gpt-5.5) won

- IMPL-04: Fable made a semantically-equivalent but unauthorized edit in a
  second crate (checked_mul→saturating_mul) on a task scoped to one file —
  scope-discipline loss, both judges.
- IMPL-08: Fable omitted a required mixed-edition fixture from the task's
  explicit test list — a real completeness gap, both judges.
- IMPL-13: reference's test breadth on failure modes was stronger.

## Cost (bench/judging/costs.json)

Fable dollars are measured; gpt-5.5 ran on the owner's plan (tokens only).
Across the 11 comparable tasks Fable emitted **2–4× the output tokens** of
gpt-5.5 for the same tasks (e.g. IMPL-12: 73k vs 19k; REF-01: 55k vs 13k).
Fable per-task cost: $1.25–$15.75 (median ≈ $7). RES-01's gpt-5.5 token
totals are not comparable (source session continued into unrelated work).

## Reading (for the parity program)

1. **On successful implement/refactor work, gpt-5.5 is already near parity
   with Fable on outcome quality** — consensus 4:3:1 with 2 splits is close
   to a coin flip — at roughly a third of the output tokens.
2. **Fable's reproducible premium is verification depth** (tests-stronger
   7/11), plus behavioral extras the pair-judging can't see (IMPL-08's rerun
   surfaced an out-of-scope shipped-test regression and stop-and-reported).
   This is exactly deltas D1/D4/D7 — steer cheaper models there first.
3. Fable is not uniformly more careful: it lost IMPL-04 on scope discipline
   and IMPL-08 on a checklist item — "more tokens" ≠ "more compliant".

## Caveats

- Survivorship: all originals were *successful* sessions (grade-A mined
  nominations). This measures quality-of-successful-work, not success rate.
- Replay asymmetry: Fable ran single-shot headless with a replay preface; the
  originals had the owner in the loop (though all these envelopes were
  fire-and-forget dispatches).
- Judges are agentic: the sonnet judge verified claims empirically in scratch
  worktrees (strengthens findings, but it is more than diff-reading); codex
  judged read-only from the brief.
- IMPL-05 sonnet verdict voided (key read); one-judge rows are marked.
