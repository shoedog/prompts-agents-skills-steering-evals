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

Memo delivered: **`MEMO-slice3-free-multi-import-scoping.md`** (repo root, untracked — no code touched). Here's the substance.

## What I verified (real numbers, this clone)

**Baseline reproduces exactly** (`prism nav call-stats`, release build):

| corpus | total sites | `free_multi` NameOnly **edges** | canary `multi_target_exact_sites` |
|---|--:|--:|--:|
| pydantic | 65,645 | **25,293** (38.5% of all sites; 76% of all demotions) | 439 |
| fastapi | 19,919 | **488** | 70 |
| express | 949 | **72** | 0 |

Confirmed corpus-dominant: pydantic's `free_multi` is **52× fastapi's**. This is a pydantic-shaped win, not a universal Python one.

**Mechanism (root cause), confirmed by grep:** `CallGraph.imports` is read for resolution in *exactly one place* — `resolution.rs:996-997`, the **qualified** `q.name()` branch (R3). The bare-call branch (`None =>`, `resolution.rs:1237-1328`) has **no import rung**, so `from x import foo; foo()` falls straight to the `FreeMulti` demote at `resolution.rs:1325`. The data the fix needs already exists: `extract_imports` (`ast.rs:564-663`) already binds `from utils import func → {"func":"utils"}`. It's simply never queried for bare names.

**Two facts that reshape the framing:**
1. **Same-file preference already ships** — R4 (`resolution.rs:1248-1256`) returns Exact `LocalDef`. So Option A's "prefer the caller's own module" is *already true at file granularity*. Its only net-new part — a same-*directory* tier — is **unsound for Python** (a bare non-local call must have been imported; co-location ≠ target). Option A buys ~nothing sound.
2. **The fix is Option B (import→path narrowing), and it must use path-suffix, not R3's stem.** Proof from the corpus: `Field` (pydantic's #1 `free_multi`) is `def`'d in `pydantic/fields.py` **and** `pydantic/v1/fields.py` — same last-segment `fields`, so R3's stem match keeps both. Full path-suffix (`pydantic.fields → pydantic/fields.py`) + relative-dir resolution disambiguates to one.

**Soundness measured, not asserted** (independent probe over the real corpora): when a `free_multi` name is imported, path-matching narrows to **exactly one target with 0 path collisions** (pydantic 612 unique / 0 multi / 4 external; fastapi 63 / 0 / 0). Zero collisions ⇒ **the canary cannot rise** ⇒ no wrong multi-target Exact.

## Recommendation

Ship **Option B only**: a lang-gated (Py/JS/TS) rung in the bare-call branch, firing **only on the would-be-`FreeMulti` set**, that looks up the name in the caller's imports and narrows by resolved path — 1⇒Exact, >1⇒demote (unchanged outcome), 0⇒fall through (pure Pareto, never removes an existing edge). ~30–40 lines, **no `CACHE_VERSION` bump** (imports already serialized), Rust/Go byte-identical by construction. Full details, discriminating-test list, acceptance gate, and deferred scope (authoritative `__init__.py`/`import *` resolution → scope-graph slice 4; R3 tightening) are in the memo.

## Honest caveats
- `call_stats` counts **edges, not sites** — one `FreeMulti` site (fan-out ≥2) emits multiple edges, so the reported drop will exceed sites-fixed; the PR should state both.
- I do **not** quote a precise converted-edge integer: my probe samples only ~12–15% of prism's calls and is biased against class-body `Field(...)` defaults. The exact pydantic delta *is* the acceptance gate, measured after implementation. The probe establishes structure + soundness, not the headline number.

One deviation from the brief's line refs (expected per the replay note — clone differs from the original branch): Go same-package is at `resolution.rs:1258-1291` and the `FreeMulti` demote at `1313-1326`, not the cited `1226-1248`/`1270-1318`.
