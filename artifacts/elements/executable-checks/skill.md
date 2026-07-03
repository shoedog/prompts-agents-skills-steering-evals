Use when: correctness depends on invariants or constraints that can be tested.

Enforce these invariants as runnable checks, not prose. Execute each and confirm it passes before finishing:
- assert <invariant 1 as a concrete condition>
- assert <invariant 2>
- assert <invariant 3>
If a check cannot be run inline, write it as a test that can. Never substitute a prose invariant for running the check.
