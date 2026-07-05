# Design-taskset executor grid — DES-02..05 × 4 arms (2026-07-04)

Four vindicated-outcome design items (read-only architecture memos; oracles =
conclusion-match vs downstream repo history), run fresh by four executor
configs, graded blind by dual judges (codex xhigh + sonnet-5, isolated cwds)
on four boolean fields: recommendation-shape match, load-bearing caveats,
scope/sizing calibration, would-have-prevented-wasted-work. 32 judge-verdicts
per arm-field table below (4 items × 2 judges); 0 judge errors.

| arm | rec | caveats | scope | prevented | total /32 |
|---|---|---|---|---|---|
| sonnet-5 | 2/8 | 2/8 | 2/8 | 2/8 | **8/32** |
| opus-4.8 | 6/8 | 6/8 | 7/8 | 5/8 | **24/32** |
| gpt-5.5 high | 6/8 | 7/8 | 8/8 | 6/8 | **27/32** |
| gpt-5.5 xhigh | 6/8 | 7/8 | 8/8 | 6/8 | **27/32** |

Costs: sonnet $17.40, opus $14.43 (4 memos each); gpt-5.5 plan tokens.

## Findings

1. **Sonnet 5 collapsed on design work (8/32).** It passed only DES-02 and
   failed the other three across every field — and on DES-04 it violated the
   explicit READ-ONLY constraint by writing +104 lines of implementation
   across five files instead of analyzing (evidence `git diff --quiet` rc 1;
   the only read-only violation among 16 runs + 8 earlier Fable/reference
   design sessions). Routing rule: do not route architecture memos to
   Sonnet 5, with or without steering artifacts.
2. **The effort dial did nothing here: gpt-5.5 high and xhigh scored
   identically (27/32), item-by-item.** For design memos of this shape, high
   is the right default (cheaper/faster); xhigh's earlier wins (PLAN-01's
   NO-GO, the original DES sessions) may reflect harder items or variance
   rather than a reliable effort premium.
3. **Opus 4.8 is close behind gpt-5.5 (24/32)** — its misses were one judge
   split on DES-02 and the universal DES-05 miss.
4. **DES-05 is a true discriminator: ALL four arms missed the vindicated
   direction** (every fresh memo chose inner-function-canonical; the landed
   design kept the decorated WRAPPER as the canonical FunctionId). Notably
   the original vindicated memo was gpt-5.5 xhigh — the same config that
   failed the fresh replay. Lesson: single-replay grids carry real
   run-to-run variance; vindicated-conclusion items are not guaranteed
   reproducible even by their own source config.

## Combined design-family standings (with the Fable references)

Fable (from docs/reference-judging-2026-07.md): DES-06 full pass, DES-01
partial (shape split, sizing/scope fail), PLAN-01 fail — mechanism analysis
consistently strong, impact sizing consistently over-optimistic.

Practical routing for architecture/design/GO-NO-GO work:
**gpt-5.5 high ≈ gpt-5.5 xhigh ≥ Opus 4.8 ≈ Fable (mechanism-strong,
sizing-weak) ≫ Sonnet 5.** Add an instrumentation gate to ANY model's
impact forecast — no config was reliably calibrated on sizing (Fable 0/2
when diverging; every arm missed DES-05's direction).

Artifacts: bench/out-des-{sonnet,opus,gpt55high,gpt55xhigh}/ (backed up),
bench/judging/DESA-*/, task specs bench/tasks/DES-0{2..5}.yaml.
