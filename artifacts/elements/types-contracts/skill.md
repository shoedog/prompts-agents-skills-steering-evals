Use when: implementing a function or API where correctness hinges on types and contracts.

Pin down types and contracts before the body. State:
- Input types and preconditions: <...>
- Output type and postcondition: <...>
- Illegal states the signature must make unrepresentable: <...>
Write the signature so invalid inputs cannot type-check, then implement to satisfy the postcondition.
