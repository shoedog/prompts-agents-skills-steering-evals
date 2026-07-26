# Conclusion-match grading — DES-03 (design/architecture), one anonymous arm

An engineer wrote the design memo below in response to the task brief. The
question was later SETTLED by the project's subsequent history. Grade the
memo against the settled outcome. You do not know who wrote it. Judge by
SHAPE and substance, not labels.

## Settled outcome (ground truth: the vindicated conclusion + repo evidence)

- conclusion: **Ship B (import-qualified narrowing)** — model `from x import foo
  as bar` / JS named / CommonJS destructured imports, resolve to a repo file, add
  a bare-call rung after R4-local and before R5-free-multi (Exact only on one
  candidate). **Reject A (same-directory/same-package Exact): unsound for
  Python/JS because sibling files are NOT in scope unless imported — it would
  mint wrong edges; keep same-dir as telemetry only.**
- vindication evidence: slice 3 **landed on main** as exactly rung B —
  `bf58508 feat(resolution): R4c import-member resolution for Python (Slice 3)`,
  hardened `5dde32b fix(slice3): R4c soundness — nested fn, compound bindings,
  relative stem, Python-only` and `54dbabc … module-scope-only imports + dotted-path
  matching`. No same-directory Exact rung was ever added. CONFIRMED: the
  import-qualified rung shipped; the same-dir approach the memo rejected as
  unsound was never shipped.
- proposed oracle: full marks = ships import-binding narrowing AND explicitly
  rejects same-dir/same-package Exact as unsound for Python/JS (fail-open to R5
  on miss/external). Fail = proposes a Go-style same-directory free-function
  preference (the naive answer; the memo and repo both reject it as edge-minting).

## Grading fields

- recommendation_matches_vindicated: does the memo's recommended design/option
  match the SHAPE of what was vindicated and landed?
- load_bearing_caveats_matched: does the memo carry the settled outcome's
  load-bearing caveats/constraints (the parts the vindication text calls out
  as decisive — e.g. narrowings, guards, buy-sizing, language scoping)?
- scope_calibrated: is the memo's scope and quantitative sizing consistent
  with what reality delivered (neither materially over- nor under-scoped)?
- would_have_prevented_wasted_work: following the memo as written, would the
  team have avoided the missteps the vindication record shows (if any)?
- probe_answer: 2-4 sentences on what the memo got right and wrong vs the
  settled outcome.

## The task brief the engineer received

# Analyze + architect (xhigh, read-only): prism slice 3 — Python/JS import & same-module scoping (free_multi)

You are a senior static-analysis architect (codex gpt-5.5, xhigh). **Read-only.** Produce an ANALYSIS +
ARCHITECTURE memo (markdown). Cite `file:line`. Session cwd = the prism repo
(`/Users/wesleyjinks/code/slicing`, on `main`). Design only; no code.

## The slice
Lift the dominant Python precision lever: **`free_multi`** — a bare-name call `foo()` that matches MULTIPLE
same-named free functions across files demotes to NameOnly. Measured: **pydantic ~25,293** `free_multi`
NameOnly. The fix: prefer the **same-module / same-file** candidate (the call's own module's `foo` wins)
before the repo-wide multi-match, parallel to Go's same-package R4.5. Plus JS: resolve relative-import
paths to narrow the candidate directory.

## Verify-first (do this, report numbers)
1. **Confirm the free_multi mechanism + size the fixable subset.** In pydantic/fastapi/express, of the
   `free_multi` NameOnly sites, how many have a candidate in the **caller's own file/module** (→
   same-module preference makes Exact) vs genuinely ambiguous cross-module vs external? Sample to estimate
   the real buy (the 25k is an upper bound).
2. **Locate the resolver rungs.** Go same-package preference at `src/resolution.rs:1226-1248`; the repo-wide
   free-multi fallback `src/resolution.rs:~1270-1318` (`FreeMulti` demote); the imports map
   (`CallGraph.imports`, `ParsedFile::extract_imports`); any existing file→module/dir mapping. Confirm
   whether Python free calls currently reach a same-module narrowing at all.

## Deliver
- **Verification** (the free_multi split + rung facts, with evidence).
- **Architecture options** (≥2): (A) same-module preference for free calls (the caller's file/dir candidate
  wins; demote only when truly cross-module-ambiguous); (B) import-qualified narrowing
  (`from x import foo` → resolve to x's module) for the qualified subset; how they compose. Trade-offs,
  soundness (must not mint a wrong Exact when the same-module candidate is coincidental), recall, blast
  radius, risk.
- **Recommendation + thin-slice plan** (changes, discriminating tests, acceptance = pydantic free_multi
  NameOnly→Exact delta + canary `multi_target_exact_sites` flat + Rust/Go byte-identical), + what to defer
  (full cross-module authoritative resolution = scope-graph slice 4).
- **Risks / unknowns.**
Be opinionated; cheapest sound design that yields a real measured buy. Note: this is the SAME `free_multi`
the deferred-work doc flagged as the dominant Python lever; it is corpus-dependent (huge pydantic, small
fastapi) — quantify per corpus.


## The memo to grade

**Analysis Memo: `free_multi` Python/JS Scoping**

**Verification**

Baseline reproduced in this clone (`prism` `184208a`) with local corpora: pydantic `363728f`, fastapi `0cb4a8e`, express `18e5985`.

| corpus | call sites | `free_multi` sites | `free_multi` NameOnly edges | same-file candidates | import-bound singleton | same-dir singleton upper bound |
|---|---:|---:|---:|---:|---:|---:|
| pydantic | 65,645 | 3,448 | 25,293 | 0 | 129 | 225 |
| fastapi | 19,919 | 142 | 488 | 0 | 96 | 96 |
| express | 949 | 13 | 72 | 0 | 0 | 0 |

Key split:
- Same-file/module-as-file is already handled: `LocalDef` runs before `FreeMulti` and returns Exact for any local free definition, not just Go: `src/resolution.rs:1248`.
- Therefore, true same-file Python/JS `free_multi` buy is **zero** in all three measured corpora.
- Same-directory is a small upper bound, but it is not sound for Python/JS bare calls without import evidence. Bare `foo()` does not see sibling files just because they share a directory.
- The sound cheap subset is import-bound bare names: `from .utils import foo; foo()` / `const {foo}=require("./utils"); foo()`. That is 129 pydantic edges and 96 fastapi edges to Exact if singleton-narrowed.

Resolver facts:
- `free_multi` is a `ResolutionKind` and serializes as `"free_multi"`: `src/resolution.rs:31`, `src/resolution.rs:53`.
- `call_stats` counts per resolved edge, which explains pydantic’s 25,293 edge count from 3,448 sites: `src/navigation/queries.rs:222`.
- Go has same-directory package narrowing before R5: `src/resolution.rs:1258`.
- R5 demotes multiple repo-wide free functions to `FreeMulti` NameOnly: `src/resolution.rs:1313`.
- `CallGraph.imports` exists and is populated from `ParsedFile::extract_imports`: `src/call_graph.rs:155`, `src/call_graph.rs:471`.
- Import paths are explicitly stored “as-is,” not filesystem-resolved: `src/ast.rs:564`.
- Python/JS import extraction already captures `from x import foo`, ES imports, and CommonJS require bindings: `src/ast.rs:589`, `src/ast.rs:665`, `src/ast.rs:757`.
- Qualified import narrowing exists only for `q.foo()`, not bare `foo()`: `src/resolution.rs:947`.
- Non-Rust module-deps currently labels Python/JS imports as unresolved heuristic imports, so there is no authoritative file→module map for them: `src/navigation/module_graph.rs:322`.

**Architecture Options**

Option A: same-module preference for free calls  
If “same module” means same file, this is already implemented by `LocalDef`; add regression tests, but no architecture change. If it means same directory/package, do not ship it as Exact for Python/JS. It would fix at most 225 pydantic sites and 96 fastapi sites, but can mint wrong Exact edges for coincidental test helpers like `fn`, `schema`, or `receive`.

Option B: import-qualified narrowing for bare imported names  
Add a rung for `site.qualifier == None` before R5: if `imports[caller.file][callee_name]` exists, resolve that module path to candidate files, restrict to free functions in those files, then:
- 1 candidate -> Exact `ImportQualified`
- >1 candidate -> NameOnly `ImportQualified`
- 0 in-repo candidates -> `ImportExternal`

This composes cleanly after `LocalDef` and before repo-wide `FreeMulti`. For thin slice, support relative Python and JS/TS paths first (`.utils`, `./utils`, `../utils`, `index.js`, `__init__.py`). Keep absolute package re-export resolution deferred; pydantic’s big names like `Field` and `field_validator` mostly need real package/export reasoning, not directory heuristics.

**Recommendation**

Ship Option B only, plus tests that pin Option A’s existing same-file behavior. Do not add naked same-directory Exact for Python/JS.

Expected measured buy:
- pydantic: at least 129 `free_multi` NameOnly edges become Exact.
- fastapi: at least 96 edges become Exact.
- express: no Exact gain in this corpus; likely one external import drop for `http-errors`.

This is not the full 25k pydantic lever. It is the cheapest sound step. The dominant pydantic residue is import/re-export/package resolution and should be Slice 4 scope-graph work.

**Thin-Slice Plan**

1. Add helper: resolve Python/JS/TS relative module strings from caller file to candidate files.
2. Add bare-import rung after `LocalDef`, before Go same-package/R5.
3. Gate to Python, JS, TS, TSX only.
4. Exact only on singleton; demote multi; drop external.
5. Tests:
   - Python relative import singleton beats cross-file same-name.
   - Python same-directory without import remains `FreeMulti`.
   - Python import resolving to multiple files demotes, not Exact.
   - JS named import / require destructuring singleton Exact.
   - JS external import drops rather than matching repo-wide names.
   - Rust/Go call-stats byte-identical.

Acceptance:
- pydantic `kind_nameonly.free_multi` decreases with `ImportQualified` Exact delta >= 129.
- fastapi delta >= 96.
- `multi_target_exact_sites` stays flat.
- Rust/Go canaries byte-identical.
- Run required resolver validation: `cargo build --release`, `cd eval && uv run tier-a --matrix-only --allow-stale-sut`, then quick Tier-A before review.

**Risks / Unknowns**

- Current import extraction loses export semantics; absolute package imports can overmatch or under-resolve.
- Python runtime rebinding and `__all__`/re-export chains are out of scope.
- JS resolution needs extension/index handling, but not full Node package semantics.
- Dropping external bare imports is probably sound for in-repo call graph precision, but should be measured separately from NameOnly→Exact wins.

No repo files were changed. Full tests were not run because this was read-only architecture work; verification was via `call-stats` plus a temporary analyzer in `/private/tmp`.


