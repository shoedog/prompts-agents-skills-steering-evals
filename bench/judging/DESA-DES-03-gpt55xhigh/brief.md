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

## Analysis + Architecture Memo

**Verification**

I measured current `FreeMulti` using `cargo build --release`, then:

`./target/release/prism nav --no-cache call-stats --repo <repo>`

I also used a scratch analyzer under ignored `target/` to split current `FreeMulti` sites. Source tree stayed clean: `git diff --stat` and `git status --short` were empty.

Key note: `call-stats.kind_nameonly.free_multi` is an edge count, not unique site count. The split below reports both.

| corpus | HEAD | `FreeMulti` sites / edges | same-file | raw same-dir singleton | raw same-dir multi | import-bound singleton | import-bound external | import-bound multi |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pydantic | `363728fe0b35` | 3,448 / 25,293 | 0 / 0 | 225 / 225 | 314 / 895 | 300 / 300 | 2,012 / 18,929 | 240 / 1,166 |
| fastapi | `0cb4a8e284b4` | 142 / 488 | 0 / 0 | 96 / 96 | 7 / 18 | 113 / 113 | 3 / 6 | 4 / 8 |
| express | `18e5985b8a9d` | 13 / 72 | 0 / 0 | 0 / 0 | 6 / 30 | 0 / 0 | 1 / 12 | 0 / 0 |

Rung facts:

- Same-file free definitions already win before `FreeMulti`: R4 collects `f.file == caller.file` and returns `LocalDef` Exact at `src/resolution.rs:1248` and `src/resolution.rs:1254`.
- Go already has same-directory/package narrowing before R5 at `src/resolution.rs:1258` and `src/resolution.rs:1269`.
- Python/JS do not have an equivalent same-dir/module rung. They fall through to R5, where multiple non-static free functions demote as `FreeMulti` at `src/resolution.rs:1313` and `src/resolution.rs:1325`.
- Import metadata exists as `CallGraph.imports` at `src/call_graph.rs:155`, is populated from `ParsedFile::extract_imports` at `src/call_graph.rs:471`, but module paths are explicitly stored unresolved at `src/ast.rs:571`.
- Current import-qualified resolution only handles qualified calls like `util.helper()`, not bare `helper()` imported by `from util import helper`; R3 starts at `src/resolution.rs:993`, drops external matches at `src/resolution.rs:1022`, and returns `ImportQualified` Exact at `src/resolution.rs:1025`. The existing module-deps test documents that `from util import helper; helper()` remains a bare call, not R3, at `tests/navigation/module_graph_test.rs:106`.
- Python `from x import foo` extraction is already present at `src/ast.rs:617`; JS import extraction is at `src/ast.rs:665`; CommonJS `require` binding extraction is at `src/ast.rs:757`.

**Architecture Options**

Option A: raw same-dir preference for Python/JS free calls.

This is cheap and mirrors Go mechanically, but it is not sound for Python or JS. A sibling file’s `foo` is not in lexical scope just because it shares a directory. Same-file is already handled, and same-dir singleton would mint Exact for coincidental neighbors. The measured raw buy is modest anyway: pydantic 225 exactable sites, fastapi 96, express 0. I would not ship raw same-dir Exact for Python/JS.

Option B: import-bound narrowing for bare free calls.

For `site.qualifier == None`, check `imports[caller.file][callee_name]`. If present, resolve the module path to candidate file(s), then intersect with free non-method functions of that name.

Resolution policy:

- one candidate in resolved module: Exact, probably `ImportQualified` or a new `ImportBoundFree`;
- multiple candidates in resolved module: demote only that narrowed set;
- external module: `ImportExternal` drop;
- unresolved module/re-export/source-root uncertainty: fail open to current R5 `FreeMulti`.

This is the sounder high-value slice. It turns pydantic’s headline from “25k possible Exact” into a more honest split: about 300 direct Exact edges, plus a much larger external false-edge cleanup of ~18,929 NameOnly edges if the module resolver is trusted. Fastapi gets 113 Exact edges. Express has no Exact buy in this corpus, but the JS relative-path resolver still needs tests because current imports keep `./mod` unresolved.

**Recommendation**

Implement Option B first, and treat Option A as telemetry only unless there is an import binding proving scope. The “same-module” winner for Python/JS should mean “the imported module that bound this bare name,” not “same directory by coincidence.”

Thin slice:

1. Add a small module-path resolver used by the `None`/bare-call branch before R5.
2. Resolve Python absolute/relative module paths against package roots and `__init__.py`; resolve JS/TS `./` and `../` against caller dir with extension and `index.*` probing.
3. Add a bare-import narrowing rung after `LocalDef` and before R5. Keep Go R4.5 unchanged.
4. Fail open on re-exports, star imports, local assignment shadowing, duplicate definitions, and unresolved source roots unless a simple guard proves the binding.
5. Add tests:
   - Python `from util import helper; helper()` with another `helper` elsewhere becomes Exact to `util.py`.
   - Python relative `.utils` with same-named `utils.py` siblings resolves caller-dir module only.
   - No import + same-dir candidate does not become Exact.
   - JS `const { helper } = require('./util'); helper()` narrows to `util`.
   - External `from typing_extensions import get_origin` / `require('http-errors')` does not bind same-name repo functions.
   - Multi definitions in the resolved module demote, not Exact.

Acceptance:

- pydantic: `free_multi` NameOnly → Exact delta at least +300 edges/sites; external-drop delta reported separately.
- fastapi: at least +113 Exact edges/sites.
- express: no required Exact gain, but external `http-errors` should not bind repo test helpers.
- `multi_target_exact_sites` stays flat: current pydantic 439, fastapi 70, express 0.
- Rust/Go call-stats JSON byte-identical for representative corpora, because the new rung is gated to Python/JS/TS bare imports.

**Defer**

Full cross-module authoritative resolution belongs in scope-graph slice 4: Python re-exports, `__all__`, star imports, `pyproject` source roots, TS path aliases, package exports, and lexical shadowing beyond cheap guards.

**Risks / Unknowns**

The biggest risk is wrong Exact from per-file imports: `CallGraph.imports` is file-wide, not lexical-scope aware. Local assignment shadowing can make an imported bare name not be the callable. Fail open when a same-name local binding is detected inside the caller span.

The pydantic number is corpus-shaped: many free_multi edges come from tests and external imports. Express is tiny here and not in `eval/corpora.toml`; I measured the local bench repo checkout directly.

I did not run the full test suite because this was read-only architecture work with no source implementation. Verified: release build, three `call-stats` runs, site/edge split analyzer, and clean source status.


