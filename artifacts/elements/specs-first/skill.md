Use when: implementing behavior that can be pinned down by tests before coding.

Write the specification before the implementation, as concrete tests:
- <input → expected output, normal case>
- <input → expected output, edge case>
- <input → expected error, invalid case>
Confirm they fail, then write code until every test passes. Change a test only if the spec itself was wrong.
