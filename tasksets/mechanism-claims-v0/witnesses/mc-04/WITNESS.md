# mc-04 — witness interpretation (VERIFIED-SEEDED)

`output.log`: the new-file patch applies (git apply --check and patch
--dry-run exit 0) and the diff's `src/pathfold.ts` passes `tsc --strict
--noEmit` on its own (step 3, exit 0 — the file parses and type-checks; the
seeded issue is doc-vs-code, not a compile error). The compiled trigger
(step 4) runs the exact minimal_trigger: `foldSegments("a/./b/../c")` returns
`["a","c"]` while the doc comment two paragraphs above the loop promises `.`
and `..` are "preserved verbatim in the output" (i.e. `["a",".","b","..","c"]`)
— the loop's `if (seg === ".") continue;` and `if (seg === "..") { out.pop();
… }` lines RESOLVE dot segments. The truth.yaml bad_behavior consequences are
also demonstrated: `foldSegments("../../shared/x")` equals
`foldSegments("shared/x")` (pop on an empty array is a no-op, so leading `..`
vanish) and `foldsUnder("shared", "../../shared/x")` returns `true`, scoping a
root-escaping path as if it lived inside the root. Seeded defect mc-04-d1 is
real and demonstrable exactly as described.
