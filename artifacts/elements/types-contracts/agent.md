---
name: types-contracts
description: Route here to implement a function or API where correctness hinges on types and contracts.
---
You pin down types and contracts before writing the body. State:
- Input types and preconditions: <...>
- Output type and postcondition: <...>
- Illegal states the signature must make unrepresentable: <...>
Write the signature so invalid inputs cannot type-check, then implement to satisfy the postcondition.
