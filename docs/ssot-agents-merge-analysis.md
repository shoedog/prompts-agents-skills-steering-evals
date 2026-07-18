# Should prompts-skills-steering and ssot-agents be one repo?

Date: 2026-07-17. Scope: read-only audit of both repos plus the a2a-bridge
coordination precedent (`~/Documents/SSOT_AGENTS_BRIDGE_COORDINATION.md`).

## Verdict: keep separate, add a lightweight coordination contract

Do not merge. The repos share a *subject* (skills, hooks, steering,
subagents) but have disjoint *roles*: this repo decides **which** steering
content changes model behavior (a research campaign with LLM-judged
experiments); ssot-agents decides **how** agent-config content is expressed
once and compiled to Claude/Codex/Kiro/opencode (an engineering build with
mutation-gated tests). The correct relationship is producer/consumer across a
narrow interface — validated moves flow out of the eval harness as candidate
portable definitions; compiled target outputs could flow back in as fixtures —
and the owner already has a working pattern for exactly this: the
ssot-agents ↔ a2a-bridge coordination file (written cross-repo doc, explicit
ownership rules, GitHub Issues as canonical intake, neither repo mutating the
other). Replicate that pattern; do not fuse the codebases.

## Evidence

### Zero existing coupling

- Grepping this repo for `ssot` finds only false positives: `LassoTrail`
  (contains "ssoT") in bench transcripts under `bench/out-des-*/`.
- Grepping ssot-agents for `prompts-skills-steering`, `human-moves`,
  `human_moves`: zero hits. No imports, no shared fixtures, no path
  references in either direction.

### Real stack divergence — the "Node half" here is a mirage

- This repo is Python-first: `harness/` (run.py, judge.py, providers,
  rubrics, gen_promptfoo.py), pytest via `ci/` + `harness/tests`,
  uv/pyproject. Its tracked file census has **zero** .js/.ts/.mjs files;
  package.json exists solely to pin `promptfoo 0.121.17` as a devDependency
  that Python-generated YAML configs drive. There is no Node code to merge.
- ssot-agents is pure strict TypeScript: 283 .ts files, `node --test` via
  tsx, `tsc --noEmit` build gate, 88 test files, plus nine per-feature
  mutation-gate scripts (`test:portable-*-mutations`) with a
  `VERIFICATION.md` discipline (e.g. 799/799 tests, 41/41 hook mutations).
  Nothing on the Python side can host or run under that regime.

### Different lifecycles, both real

- prompts-skills-steering: 77 commits in a 3-day burst (2026-07-03..05),
  then 12 days of experiment output accumulating **uncommitted** — 145
  untracked paths (bench logs, `bench/judging/*` dirs). It is in
  results-campaign mode; git history is not its heartbeat.
- ssot-agents: 110 commits over 2026-07-12..17, including today. It is in
  active milestone build mode (docs/research + docs/superpowers show a dated
  design→handoff trail per portable feature).
- Remotes differ: this repo pushes to
  `shoedog/prompts-agents-skills-steering-evals`; ssot-agents has **no git
  remote at all**. A merge would force a publication decision for ssot-agents
  as a side effect, or orphan the eval repo's existing GitHub history.

### No CI to unify

Neither repo has `.github/workflows`. Test entry points are pytest
(`testpaths = ["ci", "harness"]`) vs npm scripts. A monorepo would create CI
complexity (path-filtered pipelines, two toolchains, two lockfile ecosystems)
where today there is none to share.

### The genuine overlap — and why it argues for an interface, not a merge

Each move in `artifacts/elements/*` is hand-authored in up to four carrier
formats: `agent.md`, `prompt.md`, `skill.md`, `steering.md` (see
`artifacts/elements/wrong-vs-smell/`). That is precisely the
author-once/compile-to-targets problem ssot-agents exists to solve, and
`bench/hooks-d1/.claude/` shows this repo already tests hooks as treatment
arms while ssot-agents portabilizes hooks. But the dependency is
directional and asynchronous:

1. **Eval → SSOT:** a move validated here (wrong-vs-smell and
   predict-then-probe already graduated into the owner's global CLAUDE.md)
   becomes a candidate portable definition in ssot-agents. That is an
   occasional content handoff, not a code dependency.
2. **SSOT → eval:** once the compiler emits Claude/Codex/Kiro artifacts, the
   harness could consume compiled output as treatment fixtures — a fixture
   *input*, pinned by version, exactly how promptfoo is pinned today.

Merging would couple a fast-moving research campaign (whose failures are
"inconclusive experiment") to a correctness-obsessed compiler (whose failures
are "mutation gate red") in one blast radius, one review flow, and one
history. Neither gains: the harness doesn't need the compiler's 88-file test
suite in its `git status`, and the compiler doesn't need 145 untracked bench
logs near its VERIFICATION.md discipline.

### Merge mechanics, if it were done anyway

Cleanest path would be `git subtree add` (or filter-repo) into a
`packages/`-style monorepo with two toolchains (uv + npm), path-scoped CI,
and a decision about the missing ssot-agents remote. Cost: interleaved
history from two unrelated cadences, permission/settings scope collisions
(both repos carry `.claude/` material with different intents — one as
*subject under test*, one as *compilation target*), and worse
discoverability (the eval repo's README/eval-framework framing would no
longer describe the repo). Benefit: saving one `cd`. Not worth it.

## Recommended arrangement

1. Keep both repos as-is; do not add a code dependency now.
2. When the first real handoff happens (a validated move to portabilize, or
   compiled output wanted as a fixture), open a coordination file modeled on
   `SSOT_AGENTS_BRIDGE_COORDINATION.md`: written questions/answers, explicit
   ownership (eval owns move content and validation verdicts; ssot owns
   portable schema and target fidelity), GitHub Issues as canonical intake,
   neither repo writing into the other's tree.
3. Pin any future fixture exchange by artifact version/commit, the same way
   promptfoo is version-pinned, so the harness never tracks ssot-agents HEAD.
4. Revisit only if the repos start sharing *code* (not subject matter) —
   e.g. a common skills-format library both import. None exists today.
