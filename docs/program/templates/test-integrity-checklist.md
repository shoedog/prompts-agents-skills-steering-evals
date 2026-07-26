# Test-integrity review checklist (Family 5 bundle, catalog v2)

Apply when reviewing tests or accepting green suites as evidence.

1. CAUSAL POWER (B3): can this test catch the regression it names? A "concurrency" test
   with immediately-ready futures, no barrier/yield, single-thread runtime is sequential
   theater. Detector signature: concurrency claim + assertions unchanged by reverting the fix.
2. PINNED NEGATIVES (D-F3): a negative test that stops failing must become a loud error
   (@ts-expect-error / compile_fail / #[should_panic(expected=...)]) — never silently vacuous.
   Each witness varies exactly ONE field (internally consistent otherwise).
3. FORGED FIXTURES (A5): when strengthened validation breaks tests, classify fixtures
   constructible-vs-forged; repair forged ones through the production-equivalent
   constructor. Production validation never weakens for test convenience.
4. PREDICATE RETENTION (A6): before replacing a gate with a broader scan, list the old
   gate's predicates; retain every predicate not logically implied by the new scan.
5. ENTRY-PATH × MODE MATRIX (B4/E3): enumerate cold/warm, CLI/serve/submit/batch,
   flag-on/off; one negative regression per path. Green on one path proves one path.
6. STATE COVERAGE vs GREEN FIXTURES (E4): passed scenarios ≠ covered state dimensions;
   name the uncovered dimensions (time, purpose, topology, caller) explicitly.
7. EMPTY-RESULT OBSERVABILITY (B5): "passed" and "never ran" must be distinguishable
   downstream — clean runs still emit durable result artifacts.
8. SAFE FAILURE DIRECTION (F1): the spec names which direction is safe to fail toward;
   reviewers verify each ambiguity resolves toward it.
9. GATE VACUITY (R6): for every gate, show an input that fails it.
10. IMPEACHES-ME-FIRST (D-F3): adjudicate the finding that contradicts your own
    verification before all others.
