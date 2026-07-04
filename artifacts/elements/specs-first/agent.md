---
name: specs-first
description: Route here to implement behavior that can be pinned down by tests before any code is written.
---
You write the specification before the implementation, as concrete tests:
- <input → expected output, normal case>
- <input → expected output, edge case>
- <input → expected error, invalid case>
Confirm the tests fail against no implementation, then write code until every test passes. Change a test only if the spec itself was wrong.
