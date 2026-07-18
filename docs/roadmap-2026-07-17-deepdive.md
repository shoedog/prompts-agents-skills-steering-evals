# Roadmap 2026-07-17 — deep dive (second pass)

Companion to docs/roadmap-2026-07-17.md ("the roadmap"; items cited as ST-n / MT-n / LT-n).
Grounded in a re-read of the harness code, scripts/, results/ schema, and bench/ — not just docs.

---

## 1. Unstated assumptions and gaps

**A1 (ST-1).** The roadmap frames claude-as-judge as "add a provider." In code, `judge_cfg["provider"]`
is *decorative*: `harness/judge.py::judge_review` hardcodes `run_codex` regardless of the provider
field that config.py, judge_assert.py, and rejudge.py all dutifully thread through. The real work is
introducing provider dispatch into a function three call sites depend on — and the claude CLI has no
`--output-schema` equivalent, so JSON-enforcement parity with codex was assumed, not established.

**A2 (ST-1).** Which claude model judges is never surfaced (Sonnet vs Opus vs Haiku). This is a real
choice with cost/quality/self-preference implications, since most executors under test are claude-family.

**A3 (ST-1/ST-2).** TRACKER's third FP-audit item — claude-judge cwd isolation after the IMPL-05
incident (a claude judge ran `cat key.json` and voided a verdict) — was dropped from the roadmap.
Tool lockdown + scratch cwd is a hard prerequisite for ST-1, not an implementation detail.

**A4 (ST-2).** "Two judges + disagreement escalation" silently substitutes for what the cited research
actually recommends (PoLL: panel of ≥3 *smaller* judges; CyclicJudge: requires ≥3 judges). Only two
families are wired (`harness/providers/`: claude_cli, codex_cli). So "escalate to a third judge" is
impossible today; the escalation target was left vague.

**A5 (ST-2).** "Agreement" is undefined. A judge row is not one bit: it carries a defects[] found-map,
false_findings, neutral_matched, and derived item_pass. Two judges can agree on item_pass while
disagreeing on which defect matched. Field-level aggregation semantics is the actual design problem.

**A6 (ST-2).** The "cheap" claim is wrong as stated. PoLL's ~7× saving comes from *replacing* one
frontier judge with several small ones; the roadmap proposes *adding* a second frontier-class call
(~2× judge cost, ~7.5k tokens/call observed). Whether the panel is always-on or stakes-gated was never
decided.

**A7 (ST-3).** rh-14's fate is posed by TRACKER as a choice — repair the code vs reclassify as seeded —
with different consequences for the seeded/clean balance and for exp1H's published numbers. The roadmap
said "fix the bug" without choosing.

**A8 (ST-3, LT-2).** "Forward-only" coexists unacknowledged with a sanctioned retro path: rejudge.py
exists precisely to rescore old runs under new truth (exp1-rescored precedent). No stated rule for when
retro rejudging is legitimate vs the gaming TRACKER warns about. Related gap: judge rows record
`truth_path` but no content hash/version, so "which truth graded this row" is unrecoverable once truth
is edited — which LT-2's frozen drift bank quietly depends on.

**A9 (ST-4).** "Verify config.py accepts judge.usd_per_mtok" understates it: `JudgeCfg` has no such
field and `judge_json()` cannot emit it — the plumbing doesn't exist (judge_assert reads the key
defensively; rejudge.py:140 hardcodes `judge_cost_usd=None`). Also unstated: codex reports one blended
`tokens_used` (no in/out split), so any usd_per_mtok is a blended approximation, while a claude judge
reports *measured* `total_cost_usd` — cost provenance (measured vs estimated) needs a field.

**A10 (ST-5).** The calibration unit is unstated: spotcheck.yaml rows are *item-level* agree bits, but
Rogan–Gladen correction of defect_recall needs *finding-level* labels. Also, feeding ST-2's
disagreement-escalated rows into the calibration set biases Se/Sp (sampling conditioned on
disagreement) — the roadmap implies they're the same pool.

**A11 (ST-7).** The mid-difficulty filter is imported from a rank-preservation-across-many-models
context (E2) into a *paired within-model ablation* harness. Dropping easy items shrinks n on 15-item
sets, and clean/easy items are the false-positive instrument — the filter can quietly remove the FP
signal exp-d7 was built on.

**A12 (MT-1).** pass^k on judged outcomes conflates executor variance with judge variance; no design
separates them (judge each of k outputs once vs re-judge one output k times measures different noise).
And replica cost was never estimated: observed debug arms cost $13–19 each; 3 models × 2 arms × k=5 is
a real budget line, not a flag flip.

**A13 (MT-5).** The exploitability audit targets "the executor side" without noting the two paths
differ radically: harness executors are single-turn and tool-disabled (`--max-turns 1`,
`--disallowedTools Bash,Edit,...` in claude_cli.py) — tiny surface — while bench replay agents run
full-tool in cloned repos. The audit belongs on the bench path; the roadmap conflates them.

**A14 (LT-2 vs ST-3).** Direct contradiction left unresolved: LT-2 freezes task banks for longitudinal
comparability while ST-3 commits to continuously tightening truth forward-only. A drift series needs
one truth version; which one, and what happens to the series when truth improves, is never stated.

**A15 (LT-1).** The certification reframe (Noisy-HT deployment gates) assumes a human calibration set
large enough to matter. E1's Hardt ceiling: when judge accuracy ≈ judged-model accuracy — likely here,
frontier judging frontier — debiasing saves at most 2× labels. The ST-5 → LT-1 dependency was never
sized; 50–100 labels may not support certification-grade claims.

**A16 (LT-5).** c-CRAB scoring requires executing generated tests against the item's repo state.
Harness review items ship as context.md + diff.patch (execution-verified at curation time, but the
runnable repo is not part of the item format). The prototype needs a repo-snapshot story first.

---

## 2. Options analysis per assumption

**A1 — claude judge JSON enforcement.**
- *(a) Prompt-embedded schema + parse/validate/retry-once* (reuse `_parse_and_validate`). Pros: symmetric
  with codex path, no CLI-feature dependency, retry semantics already tested. Cons: malformed-rate
  unknown for claude; risk of higher judge_error rate. Cost: ~0 extra code beyond dispatch. **Default.**
- *(b) Two-turn repair loop* (reprompt with the parse error). Pros: lower error rate. Cons: breaks the
  retry-once contract callers rely on; more tokens; new failure semantics. Reject for v1.
- *(c) Wait for a CLI schema flag.* Blocks ST-1 on vendor timeline. Reject.
Decision needed before spec: measure malformed-rate empirically on ~20 replayed normalized blocks.

**A2 — judge model.**
- *Sonnet 4.6/5:* cheap, fast; E1 (CodeJudgeBench) says reasoning capability, not size, drives judge
  quality — a reasoning-mode Sonnet is defensible. Risk: judging its own family's executor outputs
  (see A4 lineage note). **Default for cost.**
- *Opus:* better on hard grading, ~5× cost; reserve as escalation/audit judge.
- *Haiku:* cheapest; E1 warns small non-reasoning judges fail validity floors. Reject for grading;
  fine for smoke tests.

**A3 — isolation.** Non-optional. Options are only *how*: (a) reuse `DISALLOWED_TOOLS` + empty scratch
cwd (mirror codex `judge_scratch`) — cheap, already proven pattern; (b) also strip MCP
(`--strict-mcp-config` already in claude_cli). Do both; add a test asserting the judge argv contains the
lockdown flags. No real tradeoff — this is a checklist item that must be in the ST-1 acceptance gate.

**A4 — panel composition.** Real candidates given wired providers:
- *(i) codex judge + claude judge, human as tiebreak.* Pros: only option available without new provider
  work; two true families; disagreements become labeled human data (feeds ST-5). Cons: human latency on
  every disagreement; disagreement rate unknown (measure first via A-b below). **Default.**
- *(ii) codex + 2 claude models (Sonnet + Opus) as 3-judge majority.* Pros: automatic resolution;
  CyclicJudge-compatible. Cons: 2 of 3 judges share a family — preference-leakage (E2) undermines the
  vote exactly when executor is claude-family; ~3× cost. Use only for claude-free executors.
- *(iii) add a third family (gemini CLI).* Pros: clean 3-family panel. Cons: new provider wrapper,
  auth, token parsing, unknown CLI stability — a workstream, not a tweak. Defer; revisit if human
  tiebreak volume is painful.

**A5 — agreement definition.** Options, per field:
- *item_pass equality only.* Pros: simple; matches what metrics consume. Cons: masks defect-attribution
  disagreement (judges agree "fail" for different reasons). 
- *Strict field agreement* (defect found-map equal AND false_findings equal). Pros: honest. Cons: high
  escalation volume on count fields (false_findings is a count, judges legitimately vary ±1).
- **Recommended tier:** consensus requires item_pass equal AND defect found-maps equal; false_findings
  disagreement tolerated when both are >0 or both ==0 (it only gates pass via ==0). Escalate otherwise.
  This keeps escalations meaningful without count-level noise. Must be written into the rubric spec.

**A6 — panel cost policy.**
- *Always-on:* +1 judge call/item (~$0.05–0.15). Pros: uniform data. Cons: doubles judge line on smokes.
- *Stakes-gated* (panel for headline experiments; single judge + periodic dual-judge audit for smokes):
  Pros: budget-proportional. Cons: two code paths, config surface. 
- **Recommended:** config flag `judge.panel: true|false`, default false; required-true enforced by
  convention for publishable experiments. Revisit after measuring disagreement rate.

**A7 — rh-14 fate.**
- *(a) Repair the code* (fix the Lock+depth guard): keeps 15-item set and clean-count balance; the item
  input changes, so prior captures are non-comparable — forward-only by construction. Cost: re-run the
  execution-verification for the item. **Recommended.**
- *(b) Reclassify as seeded:* preserves comparability with exp1H captures (the defect was really
  there); requires authoring truth defect + acceptable_match/reject_if; shifts seeded/clean balance and
  base_rate in confusion metrics. Reasonable alternative if exp1H reanalysis matters more than balance.
- *(c) Retire the item:* n drops to 14; wastes a hard item. Reject.
Either way: run a drop-rh-14 sensitivity pass on exp1H (metrics-only, free) and file the delta.

**A8 — retro-rejudge rule.** Options:
- *Ban retro entirely:* maximal anti-gaming; wastes rejudge.py and blocks legitimate symmetric rescores
  (exp1-rescored was one). Too strict.
- **Pre-registered symmetric rescore:** truth edits may be applied to past runs ONLY via full-both-arms
  rejudge with the edit list written down before rerunning, reported alongside (never replacing) the
  original. Codify in TRACKER/docs. Pros: preserves the one honest retro path. Cons: discipline cost.
- Independent of choice: add `truth_sha` (content hash) to judge rows — additive, cheap, and it
  dissolves the A14 ambiguity by making every row self-describing.

**A9 — cost provenance.** Add `judge_cost_source: "measured"|"rate"|null` alongside judge_cost_usd.
Measured (claude CLI total_cost_usd) always beats rate-derived. Codex blended-rate caveat goes in the
field docs, not in a report footnote. Alternative — separate in/out rates for codex — impossible
(single tokens_used); don't fake precision.

**A10 — calibration unit.**
- *Item-level (verdict agree bits):* data already exists (spotcheck.yaml across 6+ runs); supports RG on
  pass_rate only. **Phase 1.**
- *Finding-level labels:* supports RG on defect_recall/FP-rate (the metrics that actually moved in
  exp-d7); ~3–5× labeling effort per item. Phase 2, using the panel's defect-level disagreements to
  prioritize — but keep the *random* stratum separate from the *escalated* stratum, and estimate Se/Sp
  from the random stratum only (escalated rows are disagreement-conditioned and biased by construction).

**A11 — ceiling-item filter.**
- *Drop items from manifests:* shrinks n, removes FP surface. Reject as stated.
- **Annotate-and-stratify:** add a difficulty band field; keep items in runs, exclude ceiling items only
  from headline aggregates while still counting FP behavior on clean/easy items. Costs nothing at
  runtime and reverses freely. This corrects the roadmap's ST-7 as written.

**A12 — replica design.** Separate the two variances explicitly: (i) executor replicas judged once each
(k=3 before 5 — cost gate), reporting pass^k + flip counts; (ii) a one-time judge-stability probe:
re-judge ~10 archived normalized blocks 5× each (rejudge machinery, no executor cost) to bound judge
noise first. If (ii) shows judge flip-rate >~5%, panel (ST-2) becomes a prerequisite for (i), not a
parallel item — that ordering dependency was invisible in the roadmap.

**A13 — audit scope.** Split MT-5 into: harness path (verify tool lockdown claims with a test that the
argv actually disallows tools — 1 hour) and bench path (adversarial session against run_reference.py
sandboxing, truth/key file reachability, evidence-gate gaming — the real IMPL-05-class risk). Budget
the second, not the first.

**A14 — drift-bank truth policy.** Options: freeze truth at bank-creation (comparable but increasingly
wrong); always-latest truth (right but non-comparable). **Recommended:** version truth (A8's truth_sha),
run drift comparisons under the truth version frozen at bank creation, AND rejudge the full history
under latest truth whenever truth changes (rejudge is cheap: judge calls only). Both series published;
drift claims cite the frozen series.

**A15 — certification sample size.** Before promising LT-1, compute the detectable-effect table: with
judge Se/Sp from ST-5 and n≈15–30 items, what failure-rate bounds are certifiable at all? If the answer
is "nothing tighter than ±15pp," LT-1's pitch changes from "certify" to "bound," and the honest
alternative is growing the task banks first (MT-3 curation feeds this directly).

**A16 — c-CRAB precondition.** Add a step zero: for 5 review-hard items, record whether the source repo
snapshot + failing-test harness is reconstructible (curation notes say execution-verified 29/29, so the
material existed). If not archivable per-item, c-CRAB applies only to future curated items — which
changes LT-5 from "prototype on review-hard" to "bake into MT-3 curation format."

---

## 3. Pre-design analysis — short-term items 1–5

### ST-1 Claude-as-judge provider

- **Decide first:** (1) JSON strategy = prompt-embedded schema + existing `_parse_and_validate` +
  retry-once (A1); measure malformed-rate on ~20 archived normalized blocks before committing.
  (2) Judge model default = Sonnet, Opus as audit judge (A2). (3) Effort mapping: claude CLI enum is
  `low|medium|high|xhigh|max` (bench/run_reference.py:970), codex accepts `[a-z]+` shape-only — the
  per-provider enum table belongs in config.py (joint with ST-4). (4) Same-family guard
  generalization: `_validate_same_family_judge` only refuses codex/codex; make it provider-symmetric
  (claude executor + claude judge refused without override) WITHOUT breaking every legacy config
  (all use claude executor + codex judge — must still load).
- **Touches / can break:** harness/judge.py (introduce dispatch on the currently-ignored provider
  field — all three call sites judge_assert.py, rejudge.py, and tests flow through `judge_review`, so
  the signature must not change); claude_cli.py (judge-mode call: DISALLOWED_TOOLS + `--max-turns 1`
  + scratch cwd — A3 is a blocker requirement here); config.py enums; test_judge.py/test_config.py.
- **Failure protocol:** claude judge failures must produce the same `judge_error=true` row shape —
  never a new error path. Add `judge_provider` + `judge_model` to the row (additive).
- **Backward compat:** old judge rows lack the new fields — metrics.py must tolerate absence (it
  already ignores unknown keys). rejudge.py inherits the new dispatch for free once judge.py owns it.
- **Acceptance:** unit tests for dispatch + lockdown argv; rejudge an existing run (exp-d7) with the
  claude judge and report row-level agreement (κ, not just %) vs the archived codex-judge rows;
  malformed-rate ≤5% after retry on the probe set; guard tests both directions.

### ST-2 Two-family judge panel with escalation

- **Decide first:** aggregation tier (A5 recommended rule); cost policy (`judge.panel` config flag,
  A6); escalation target = human via spotcheck (A4-i): disagreement rows are auto-appended to
  spotcheck.yaml with `agree: null` and a `source: panel_disagreement` tag so check_spotcheck's
  PROVISIONAL/20% gate machinery is reused unchanged. Decide partial-failure semantics NOW: one judge
  errors → row degrades to single-judge with `panel_degraded: true` (not judge_error) vs hard
  judge_error; recommended: degrade + count, so a flaky second judge can't zero out a run.
- **Touches / can break:** judge_assert.py (calls judge_review twice, builds consensus record);
  rejudge.py (must gain the same panel path or explicitly declare rejudge single-judge-only —
  decide!); report.render_spotcheck (new source tag); metrics.py UNCHANGED if top-level row fields
  carry consensus values with per-judge sub-records under a new `panel: [...]` key — this is the
  load-bearing schema decision (bench/judging's separate-dirs layout is the rejected alternative;
  it would fork metrics).
- **Failure protocol:** disagreement is NOT failure — it's data. Only double-judge-error is
  judge_error. Escalated-but-unadjudicated rows count as PROVISIONAL, mirroring spotcheck semantics.
- **Backward compat:** consumers that only read top-level fields (all of metrics.py, regen_spotcheck)
  keep working; single-judge rows and panel rows coexist in results/ history.
- **Acceptance:** measured inter-judge κ + disagreement rate on one rejudged historical run
  (cheap probe before any live run); unit tests for consensus/degraded/double-error paths; verify
  escalated rows appear in spotcheck.yaml and the >20% gate still fires on synthetic disagreement.
- **Ordering:** hard-depends on ST-1; the A12 judge-stability probe should ride along free.

### ST-3 Truth-set hygiene (forward-only)

- **Decide first:** rh-14 option (A7: repair recommended, reclassify acceptable — owner call, both
  written up with the seeded/clean-balance consequence); the retro-rejudge rule (A8: pre-registered
  symmetric rescore only); whether exp1H gets a sensitivity addendum (drop-rh-14 recompute — free,
  do it). Author the six audited neutral_findings entries + rh-06 granularity note + rh-10 neutral
  siblings as ONE pre-registered edit list.
- **Touches / can break:** tasksets/review-hard/items/*/truth.yaml; check_taskset.py (verify it
  validates neutral_findings shape; note judge.py renders neutral_findings ONLY for seeded items —
  if rh-14 stays clean it cannot carry them, only tempting_non_defects; that asymmetry constrains
  the rh-14 choice and nobody has written it down); rejudge.py consumes edited truth transparently.
- **Failure protocol:** any rescored run reports judge_errors nonzero → rescore declared not-clean
  (rejudge.py already exits 1); truth edits land as one commit with a PROVENANCE note.
- **Backward compat:** THE issue — add `truth_sha` to judge rows (A8) so pre-edit and post-edit rows
  are distinguishable forever; old rows without it are implicitly pre-edit.
- **Acceptance:** check_taskset green; repaired rh-14 re-execution-verified (29/29 bar maintained);
  exp1H sensitivity delta filed; edit list visible in the commit before any fresh run uses it.

### ST-4 Judge accounting fixes

- **Decide first:** (1) Token parse: collect the 5 known-undercount stderr/stdout captures from exp1H
  results as regression fixtures BEFORE changing the regex (`_TOKENS_USED_RE` in codex_cli.py); also
  investigate whether the codex CLI `-o` scratch file carries structured usage (would obsolete the
  regex — analysis task, 1 hr). (2) Rate plumbing: add optional `usd_per_mtok` to JudgeCfg +
  judge_json() + rejudge's judge_cfg dict (A9 — the field does not exist today); pick the blended
  rate per judge model and document the blend caveat. (3) Cost provenance field (A9). (4) Effort
  enums: per-provider table in config.py — claude `{low,medium,high,xhigh,max}`, codex
  `{minimal,low,medium,high,xhigh}` (verify against installed CLI first — the enum WILL drift with
  CLI versions, so decide warn-vs-fail; recommended: fail on unknown with an override flag, matching
  the same-family-guard pattern).
- **Touches / can break:** codex_cli.py parse; config.py (JudgeCfg is a dataclass consumed by
  judge_json(), rejudge.py builds its dict by hand — BOTH must add the key or rejudge silently
  never prices); judge_assert._judge_cost_usd (works once the key arrives); rejudge.py:140
  (`judge_cost_usd=None` hardcode must call the same helper — move `_judge_cost_usd` into judge.py
  so asserts and scripts share it); metrics.judge_token_totals (already tolerates None — unchanged).
- **Failure protocol:** token-parse miss stays best-effort (None + judge_tokens_missing count),
  never a row failure; unknown effort fails at config load, not call time (that's the whole point).
- **Backward compat:** all new config keys optional-with-None default; every existing experiment
  YAML must load unmodified (test: load all files in experiments/).
- **Acceptance:** regression fixtures for the undercount cases pass; one live judged item shows
  non-null judge_cost_usd + source; rejudge on a rate-carrying config prices rows; config-load test
  over experiments/ green; effort typo rejected at load with actionable message.

### ST-5 Owner spotchecks → frozen calibration set

- **Decide first:** calibration unit (A10: phase 1 = item-level from existing spotcheck rows;
  phase 2 = finding-level); sampling design — random stratum (arm × seeded × pass/fail stratified,
  extending report.render_spotcheck's arm-stratification) kept PERMANENTLY separate from the
  panel-escalated stratum, Se/Sp estimated from random only; per-judge-config keying — Se/Sp are
  properties of (judge model, effort, rubric hash), so the set's schema needs those columns or
  pooling silently mixes instruments; human-only labels for the frozen set (the 20/20 spot-check
  was an AI stand-in, disclosed — fine for a gate, not for calibration; E2's synthetic-eval finding
  backs this).
- **Touches / can break:** new file (e.g. calibration/judge-calibration.yaml) + aggregation script
  pulling from results/*/spotcheck.yaml; check_spotcheck.py gains κ reporting next to the raw >20%
  gate (E1: report agreement AND κ jointly — raw % overstates on skewed pass rates); the pending
  owner items (3 split judging rows + exp1h spotcheck file) are INPUTS — chase them first, they're
  the only human rows that exist.
- **Failure protocol:** below-threshold n → the set reports itself PROVISIONAL and RG stays OFF
  (raw + κ only); RG correction activates at n≥100 per E1 guidance, never silently.
- **Backward compat:** existing spotcheck.yaml files are readable as-is (task_id/arm/agree fields);
  the aggregator must tolerate historical runs' rubric drift by recording rubric hash per row.
- **Acceptance:** ≥50 human item-level labels spanning both truth states with κ + Wilson CI
  published; a written activation rule for RG; escalated-vs-random strata never pooled in any
  emitted estimate (test the aggregator refuses it).

---

## 4. What to analyze before writing a technical design/spec in this repo (reusable checklist)

Extracted from where all five analyses kept converging:

1. **Name the unit and the field semantics first.** Item vs finding vs token; blended vs split
   counts; consensus vs per-judge. Most roadmap vagueness traced to an unnamed unit of analysis.
2. **Sweep every consumer of the results schema.** Any judge/calls row change must be checked
   against metrics.py, report.py, rejudge.py, regen_spotcheck.py, check_spotcheck.py, and tests.
   Rule that held: additive fields only; top-level fields keep their old meaning (consensus lives
   at top level, detail nests below).
3. **Audit provider asymmetry explicitly.** Any feature touching both CLIs needs a capability
   table first: schema forcing, token/cost reporting, effort enums, tool lockdown, cwd isolation.
   Never assume parity — judge.py's ignored provider field came from assuming it.
4. **Stamp provenance on every graded artifact.** Judge model/effort, rubric hash, truth content
   hash. Un-versioned instruments made three separate items (A8, A14, ST-5 pooling) harder.
5. **Write the retro-vs-forward rule before changing any instrument.** Truth, rubric, or scoring
   edits: either pre-registered symmetric rescore of both arms, or forward-only with old rows
   distinguishable — never silent mixing. rejudge.py is the only sanctioned retro path.
6. **Cost it in calls before committing.** items × arms × models × replicas × judges, against
   token_budget. "Cheap because the wrapper exists" was wrong once already (A6).
7. **Define the failure-mode row, not just the happy path.** Every new step needs its judge_error
   analog: counted, surfaced, never laundered into a smaller-but-clean run (metrics.py invariant).
   Include the partial-failure tier (degraded ≠ failed).
8. **Validate by replay before fresh spend.** Archived normalized blocks + rejudge machinery can
   de-risk judges, panels, parsers, and rubrics with zero executor cost. Every ST item had a
   replay-first probe available.
9. **Check blinding/isolation for every new process.** What can this component read (cwd, tools,
   truth files) beyond what its prompt shows? (IMPL-05 lesson — it recurred in ST-1, ST-2, MT-5.)
10. **Check estimator sampling for conditioning bias.** If data feeds Se/Sp, κ, or any correction:
    was it sampled conditioned on disagreement, failure, or difficulty? Keep adversarial and random
    strata separate (A10, A11).
