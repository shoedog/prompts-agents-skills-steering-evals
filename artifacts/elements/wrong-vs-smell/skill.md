Use when: reviewing code or a diff and reporting findings.

Tag every finding with exactly one severity class:
- WRONG — the code provably does the wrong thing. Name the concrete input or state and the incorrect output or effect.
- SMELL — a risk, gap, or style concern with no demonstrated incorrect behavior.

Report WRONG items first. A finding without a concrete failure scenario cannot be WRONG — downgrade it to SMELL instead of inflating it. Never present a SMELL as blocking. If evidence for WRONG is uncertain, state the one check that would settle it.
