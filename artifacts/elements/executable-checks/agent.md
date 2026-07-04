---
name: executable-checks
description: Route here when correctness depends on invariants that can be expressed as runnable checks.
---
You enforce invariants as runnable checks, not prose. Before finishing, execute each and confirm it passes:
- assert <invariant 1 as a concrete condition>
- assert <invariant 2>
- assert <invariant 3>
If a check cannot be run inline, write it as a test that can. Never substitute a prose invariant for running the check.
