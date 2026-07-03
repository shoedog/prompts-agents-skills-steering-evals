# Evaluation Framework: Cross-Project Design Reference

**Version:** 1.1 (April 2026, with citation classifications and pre-2026 lineage verification, both added April 2026)
**Changes from v1.0:** Incorporated Feb–April 2026 research across LLM-as-judge calibration, selective prediction / abstention, and weak supervision / noisy-label evaluation. Added Statistical Estimation Reference (Rogan–Gladen, Lang–Reiczigel CI, PPI++/EIF). Added seventh framework principle (reliability engineering as co-equal framing). Added C3 cross-cutting concern referencing Companion A. Updated RAG diagnostic, code review agent, agentic SDLC, and LLM-as-judge profiles with specific citations and protocol recipes. **Post-v1.1 additions (April 2026):** (1) classification of citations as load-bearing vs. illustrative with confidence percentages; (2) model-generation caveats on pre-June-2025 research where mechanism vs. magnitude distinctions matter; (3) **pre-2026 lineage verification** via research-agent verification of foundational research papers — corrected several misattributions (Eyuboglu→Zrnic & Candès for active inference; Anil→Agarwal for many-shot ICL; KnowNo paper title; Bavaresco venue), surfaced previously-unstated lineages (LLM-judge ordinal IRR, memory systems including Reflexion/Voyager), and recalibrated several confidence ratings upward where Q1 2026 papers turned out to extend well-established lineages rather than being single-paper claims.

## Citation Classification Legend

Every research citation in this document and Companion A is classified to help you triage which findings drive recommendations vs. which illustrate mechanisms. Calibrated estimates of "likelihood the finding would replicate or hold up under scrutiny" — these are my honest assessments, not objective probabilities.

- **[LB-95%]** Load-bearing, high confidence. Recommendation depends on this finding. Confident the finding is current and correct.
- **[LB-75%]** Load-bearing, moderate confidence. Recommendation depends on this; some concern about currency, generalizability, or replication.
- **[LB-50%]** Load-bearing, uncertain. Recommendation depends on this; validate before executing.
- **[IL-90%]** Illustrative, high confidence. Demonstrates a real mechanism; recommendation stands regardless of specific magnitude.
- **[IL-60%]** Illustrative, lower confidence. Mechanism plausible but empirical grounding weaker; verify before over-indexing.
- **[IL-30%]** Illustrative, speculative. Included because the mechanism is interesting; treat as hypothesis.

**Model-generation caveat marker [MG-CAVEAT]:** flagged on findings from before June 2025 where the underlying empirical magnitude is sensitive to model generation. Marker indicates: mechanism likely real, magnitude likely smaller on current frontier models, measure on your target model rather than assuming.

A consolidated References section at the document end provides full citations grouped by classification, formatted for semantic-scholar feeding.

---

## Preamble

### What this document is

A working design reference for evaluating LLM-powered systems — from single prompts and skills up through multi-agent flagship systems. It emerged from a specific problem (Wesley has multiple concurrent projects all with underspecified evaluation) and generalized from there. The document is organized as per-instantiation profiles grouped by complexity tier, plus cross-cutting concerns that apply across tiers.

The framework's value is not in any single axis or profile. It's in providing a shared vocabulary that makes the *reusable parts* of eval design transfer across projects, and in surfacing the places where each specific project needs bespoke ground-truth work (Stage 0) that can't be borrowed from anywhere else.

### How to use this document

Three modes of use:

1. **Reference while designing a new eval.** Find the instantiation closest to your case, read that profile, check the cross-cutting concerns, and borrow machinery from adjacent tiers. Most flagship evals are assemblies of commodity + middle-tier patterns plus bespoke Stage 0 work.

2. **Diagnostic for an existing eval.** Walk the 11 axes against your current eval. For each axis: is it load-bearing for my system? Am I treating it as load-bearing? The mismatch between "should be load-bearing" and "actually treated as load-bearing" is where eval quality is lost.

3. **Checklist for a system that doesn't have an eval yet.** Use the relevant profile as a spec. Stage 0 (labeled ground truth) before Stages 1+ (everything else built on that ground truth). The seduction is always to build the system first and retrofit the eval; sometimes that works (when a pre-built benchmark exists) and sometimes it doesn't (when your system's ground truth is specific enough that nobody else has built it).

### Axis glossary

The 11 axes that structure every profile:

1. **Output shape** — Classification, ranking, generation, decision-with-abstention, trajectory, or composite. Determines which eval patterns apply at all.

2. **Truth regime** — Gold (reliable human labels), silver (noisy proxy labels), reference-free (no labels, rubric or judge-based), or unlabelable (must rely on user signal or downstream outcomes).

3. **Truth-proxy quality** — When using a proxy for truth, how close is the proxy to truth? Trusted / known-biased-with-bounded-error / unverifiable. The *gap* between proxy and truth is where silent eval failures hide.

4. **Baseline** — What the system is compared against. Random, rule-based floor, current-state (what you're replacing), strong-simple (a well-prompted single call), or "do nothing." Baseline choice is often the ship criterion: if the system isn't meaningfully better than what the user already has, the metric doesn't matter.

5. **Coverage requirement** — Must the system answer every query, or is abstention first-class? Abstention-capable systems need risk-coverage curves, not single accuracy numbers.

6. **Failure-cost asymmetry** — Are all failure cells equally bad? Usually not. FP and FN often have wildly different costs, and for multi-class systems each off-diagonal cell has its own cost. Cost-weighted error is the honest metric; unweighted accuracy obscures.

7. **Distribution shape** — Uniform, long-tailed, adversarial clusters. Long-tailed distributions demand slice analysis; adversarial clusters demand adversarial eval sets; uniform is rare in practice.

8. **Granularity need** — Aggregate, segmented, or slice-discovery. Aggregate metrics hide failure modes; segmented metrics surface them along known dimensions; slice-discovery finds failure modes you didn't anticipate.

9. **Temporal regime** — Static offline, live online, or hybrid with shadow mode. Memory systems and long-running agents especially need temporal eval — "works at time T" doesn't mean "works sustained over T+3 months."

10. **Labeler economics** — Who labels, how expensive, what's the IAA ceiling. Often the binding resource constraint on flagship eval. Domain-expert labeling on open-ended outputs is the most expensive corner.

11. **Measurement tractability** — A pair: (measurability: crisp / soft / proxy-only) × (generalizability: bespoke / family / broad). Drives the build-vs-reuse decision on eval machinery. High-generalizability corners are where cheap reusable infrastructure pays off; bespoke corners require per-project investment.

### Sub-pattern: TP/FP/TN/FN matrix

For instantiations with classification or decision-with-abstention shapes, the confusion matrix is first-class. Four components, all of them usually relevant:

- **Cells themselves** (TP/FP/TN/FN for binary; N×N for multi-class): what happened.
- **Cell costs**: not symmetric in real deployments. Report cost-weighted error, not accuracy.
- **Base rate**: a classifier at 95% accuracy on a 99/1 split is worse than random on the minority class. Accuracy without base rate is decorative.
- **Confidence-stratified view**: for systems with abstention, what does the matrix look like at top-decile confidence vs. bottom-decile? This is where calibration quality is visible.

Multi-class extension: the 2×2 matrix becomes an N×N matrix where off-diagonal structure reveals *which* confusions the system makes, not just how many errors. Critical for systems where some confusions are far more expensive than others (e.g., the RAG diagnostic's defect→lab error is worse than its transient→lab error).

### Framework principles

Seven principles emerged across tiers. These are the operational takeaways:

**1. Stage 0 is the work.** For flagship systems, 70% of eval effort is building labeled ground truth. Stages 1+ are relatively mechanical once Stage 0 exists. Plan accordingly.

**2. Stage 0 can sometimes be retrofitted; sometimes it can't.** Know which case you're in before you start building. The code review agent could retrofit Stage 0 via CVE benchmarks because structurally-similar ground truth existed. The RAG diagnostic cannot — three-way failure classification on telecom lab data has no pre-existing ground-truth corpus. If you're in the can't-retrofit case, do Stage 0 first or accept that your system ships without credible eval.

**3. Baseline is the ship criterion.** Not accuracy. Not F1. Whatever the system is *replacing* — that's the baseline. If the system isn't meaningfully better than a senior engineer with existing tools, or better than the current human process, or better than a strong-simple prompt — it doesn't ship, regardless of what its internal metrics say.

**4. Document the gap between proxy and truth — and now you can bound it formally.** When you evaluate against a proxy (ticket resolutions, commit-proximity, citation patterns), the proxy has failure modes. Bound them. Report metrics with the bound acknowledged. As of Q1 2026, this is no longer a rhetorical principle — the Rogan–Gladen + Lang–Reiczigel CI + PPI++/EIF statistical skeleton (Chen et al. 2601.05420 [LB-95%], Lee et al. 2511.21140 [LB-90%], Feng et al. 2601.20913 [LB-85%]) gives a unified estimator: `P_true = (P̂ + q₀ − 1) / (q₀ + q₁ − 1)` with variance inflation `(q₀ + q₁ − 1)⁻²`. See the Statistical Estimation Reference sub-section below.

**5. Composite outputs get composite evals.** Don't try to collapse retrieval+generation, or structural+content+ship-readiness, or contract+usability into a single metric. Evaluate each layer with appropriate machinery. The sum tells you whether the system works; the layers tell you what to fix.

**6. Model-update regression and judging-the-judge are cross-cutting.** Every eval in this framework should be re-runnable on model version change and should have its judge calibrated against human IAA ceiling. Without both disciplines, the eval stack is built on untrustworthy ground and you won't know when it starts to fail. **Hardt ceiling (2410.13341 [LB-95%]):** when judge accuracy ≤ judged-model accuracy, debiasing cannot save more than 2× labels. Budget human calibration accordingly.

**7. Reliability engineering is co-equal framing for agents and long-horizon systems.** For agents and anything running sustained sequences of tool-use or reasoning, accuracy-centric eval is insufficient. The field as of Q1 2026 has converged on importing safety-critical engineering vocabulary — MTBF, pass^k consistency, fault injection, reliability surfaces. "Beyond pass@1" (2603.29231 [LB-75%]) demonstrates reliability decays super-linearly with task duration across 23,392 episodes. For these systems, see the **Reliability Engineering Companion Document** — it's a distinct framing that runs in parallel with this one rather than replacing it.

### Structure of this document and companions

**This document:**
- **Tier 1 — Commodity layer** (4 profiles): prompts, MCP servers, skills, steering.
- **Tier 2 — Middle layer** (6 profiles): agents, RAG pipelines, classifiers, evaluators (LLM-as-judge), context assembly, memory systems.
- **Tier 3 — Flagship layer** (4 profiles): RAG diagnostic, code review agent, agentic SDLC, chunking experiment.
- **Tier 4 — Edge profiles** (2 profiles): narrow general reasoning, document generators.
- **Cross-cutting concerns** (3 sections): model-update regression (C1), judging the judge (C2), reliability engineering (C3 — reference section; full treatment in companion doc).
- **Statistical Estimation Reference** (sub-section near top): formulas for proxy-bounded metrics, referenced throughout.

**Companion documents:**
- **Companion A — Reliability Engineering Framing:** Importing IEC 62279/MTBF/pass^k/fault-injection vocabulary. Separate because it's a distinct framing, not a patch. Critical for tier 2 agents and tier 3 agentic SDLC.
- **Companion B — Tooling & Infrastructure Landscape (April 2026):** Current library recommendations (Inspect AI, Langfuse, TruLens 2.6 Agent's GPA, DeepEval, Braintrust, TorchCP, ppi-py, etc.). Separate because tooling changes faster than framework principles.
- **Companion C — Frontier Watch List:** Emerging approaches worth monitoring but not adopting yet (process reward models, IRT/CAT adaptive testing, benchmark watermarking, evaluation awareness, metamorphic/mutation testing for LLM systems). Revisit quarterly.

### What's in scope and what isn't

**In scope:** Eval design for LLM-powered systems. Reusable patterns. Shared vocabulary. Stage 0 planning. Cross-cutting discipline. Now with formal statistical grounding for proxy-bounded metrics (v1.1).

**Not in scope:** Eval of non-LLM systems (classical ML has its own mature literature; this framework borrows from it but isn't replacing it). Ethical/safety eval as a primary focus (guardrails were considered and deferred as orthogonal). Fine-tuned model eval (not in scope for current projects; would fit as a middle-tier addition if it becomes relevant).

**Research status (v1.1):** Framework updated April 2026 to incorporate Feb–April 2026 developments across three requested areas (LLM-as-judge calibration, selective prediction for LLM classifiers, weak supervision / noisy-label eval construction) plus an unrequested adjacent area (reliability engineering framing for agents — moved to Companion A). Specific citations in-line where they ground a framework claim; full references in the research-feed documents.

### Statistical Estimation Reference

Proxy-bounded metrics: the unified statistical skeleton. Applied throughout this document (Category D in code review, resolution-text ambiguity in RAG, noisy historical labels in agentic SDLC).

**Setup:** you evaluate a system against a proxy (LLM judge, resolution-text field, commit-proximity heuristic) rather than gold truth. The proxy has known/measurable failure modes: sensitivity `q₁` (true-positive rate of the proxy), specificity `q₀` (true-negative rate). Let FPR `ρ₋ = 1 − q₀`, FNR `ρ₊ = 1 − q₁`.

**Rogan–Gladen point estimate** (classical, 1978; re-grounded for LLM-era by Lee et al. 2511.21140 [LB-90%]):

`P_true = (P̂ + q₀ − 1) / (q₀ + q₁ − 1)`

**Natarajan unbiased-loss lower bound** (NeurIPS 2013 [LB-95%], for worst-case reporting):

`P_true ≥ (P̂ − ρ₋) / (1 − ρ₊ − ρ₋)`

**Variance inflation (delta method, Youden):**

`Var(P̂_corrected) ≈ Var(P̂_observed) / (q₀ + q₁ − 1)²`

**Confidence interval:** Lang–Reiczigel correction (see Lee et al. 2511.21140 v3 [LB-85%] for the current LLM-era formulation; handles calibration uncertainty properly).

**Worked example — Code review agent Category D (ε = 0.125 symmetric proxy error):** denominator `q₀ + q₁ − 1 = 0.75`. Point estimate formula becomes `P_true ≈ 1.33·P̂ − 0.167`. At observed P̂ = 0.80, corrected `P_true ≈ 0.90` (lower bound). CI widens ~1.3–1.4× before Lang–Reiczigel correction adds more. Minimum 100 calibration items for stable `q̂₀, q̂₁` estimates.

**Choice of estimator:**
- **Rogan–Gladen (with Lang–Reiczigel CI):** robust default. Robust to distribution shift between calibration set and test set. Use when calibration-test shift is plausible (it usually is for historical ticket data).
- **EIF / PPI++ (Chen et al. 2601.05420 [LB-90%], Feng et al. 2601.20913 [LB-80%]):** efficient default when shift is small or controllable. CIs 3–15× narrower than Rogan–Gladen when judge/proxy is weak. Implementation: `ppi-py`.
- **Transport audit (CJE, 2512.11150 [LB-70%]; Noisy-but-Valid, 2601.20913 [LB-75%]):** run per-policy residual-mean test before trusting calibrated estimates; detects distribution shift between calibration and test. Alert if it fails. This is how you detect calibration drift (C1) automatically.

**Hardt ceiling (2410.13341 [LB-95%]):** when the judge/proxy is no more accurate than the model being evaluated, debiasing cannot reduce ground-truth-label requirements by more than 2×. For high-stakes judging of frontier agents, budget for large human calibration sets — don't expect tenfold savings from bias correction.

---

## Reference Card

**Axes:**
1. Output shape
2. Truth regime
3. Truth-proxy quality
4. Baseline
5. Coverage requirement
6. Failure-cost asymmetry
7. Distribution shape
8. Granularity need
9. Temporal regime
10. Labeler economics
11. Measurement tractability

**Sub-pattern:** TP/FP/TN/FN matrix + cell costs + base rate + confidence-stratified view (for classification/decision-with-abstention shapes).

**Cross-cutting:** C1 Model-update regression. C2 Judging the judge (with Hardt ceiling). C3 Reliability engineering (see Companion A).

**Seven principles:** Stage 0 is the work. Sometimes retrofittable, sometimes not. Baseline is the ship criterion. Document the proxy-truth gap — and bound it formally (RG/PPI++/EIF). Composite outputs get composite evals. Re-run on model updates, calibrate judges against IAA, respect the Hardt ceiling. Reliability engineering is co-equal framing for agents and long-horizon systems.

**Core statistical formulas:**
- Rogan–Gladen: `P_true = (P̂ + q₀ − 1) / (q₀ + q₁ − 1)`
- Natarajan lower bound: `P_true ≥ (P̂ − ρ₋) / (1 − ρ₊ − ρ₋)`
- Variance inflation: `(q₀ + q₁ − 1)⁻²`
- Hardt ceiling: weak judge → at most 2× label savings from debiasing

**Companions:** A (Reliability Engineering), B (Tooling Apr 2026), C (Frontier Watch List).

---

## Tier 1: Commodity Layer

These are the unglamorous eval targets that make up the majority of what a team ships. Framework value here comes from cheap, reusable eval machinery.

### 1. Prompts

**What it is:** A single system prompt or user prompt template. Change the wording, behavior shifts. Deployed everywhere from application features to skills to agent instructions.

**Load-bearing axes:**

- **Output shape** — Usually generation, sometimes classification (if the prompt extracts or categorizes). This is the primary driver: a prompt that generates prose is evaluated differently from a prompt that returns structured JSON.
- **Truth regime** — Typically reference-free (no gold answer for "write a good summary") or silver (golden-set regression where "previous output we accepted" is the reference). Gold is rare and expensive.
- **Baseline** — Previous prompt version. This is the *only* baseline that matters for prompt iteration. Comparing to a random baseline is theater; comparing to the prompt you shipped last week is substance.
- **Measurement tractability** — High generalizability (the eval machinery is reusable across thousands of prompts), variable measurability (crisp for extraction, soft for generation).

**The actual eval (cheap version):**

Golden-set regression. A curated set of 20–100 input/expected-output pairs maintained per prompt. On every prompt change: rerun, diff outputs, flag regressions. For generation tasks where exact match is wrong, use LLM-judge with a strict rubric ("does the new output cover the same key points as the reference").

**Why most teams don't do this:** It feels like heavy process for "just a prompt change." The cost is real (build+maintain the golden set) but small per prompt if the machinery exists. The payoff compounds — every prompt change becomes safer, and silent regressions stop happening.

**Sub-pattern (when prompt is a classifier):** Standard TP/FP/TN/FN. Base rate from production data. Costs asymmetric in almost all real deployments (e.g., a prompt that classifies support tickets — misrouting a billing issue as technical costs different from the reverse).

**Standard axes (mentioned for completeness, not design drivers):** Coverage (usually full — prompts answer every input); temporal regime (offline); distribution shape (matches production, or should).

---

### 2. MCP Servers

**What it is:** A server exposing tools to an LLM via the Model Context Protocol. Quality has two components: does the server work (contract), and can the model actually drive it (usability).

**Load-bearing axes:**

- **Output shape** — Composite. Contract eval is classifier-shaped (does the server return what its schema claims, yes/no per tool call). Usability eval is trajectory-shaped (did the model figure out how to use this tool correctly).
- **Truth regime** — Gold for contracts (the schema is the truth), reference-free or silver for usability (did the agent succeed on the task).
- **Granularity need** — Per-tool granularity is essential. Aggregate "MCP server quality score" hides the fact that 2 of 15 tools are broken or unusable. Slice analysis across tool types reveals systematic failures (e.g., all write-operations underperform reads).
- **Measurement tractability** — High measurability for contracts (deterministic), soft for usability. High generalizability: contract tests are reusable across servers; the usability eval harness once built works for any MCP server.

**The actual eval:**

Two layers.

*Contract layer:* Deterministic tests per tool. For each tool: valid input returns schema-conformant output; invalid input returns proper error; edge cases (empty, oversized, malformed) handled. Standard API testing discipline.

*Usability layer:* Fixed battery of tasks that require using the server. Run a capable model (Sonnet, Opus) against the tasks. Measure: tool-use success rate, number of incorrect tool calls before success, whether the model gave up. The interesting failure mode is "technically works but model can't figure out how to use it" — usually bad tool descriptions, ambiguous parameter names, or missing examples.

**Sub-pattern (contract layer):** TP/FP/TN/FN at the per-tool level. TN is the big one here — a server that returns proper errors on invalid input is doing the right thing; eval frameworks that ignore TN understate MCP server quality.

**Cross-reference to Wesley's world:** The Mermaid Chart MCP in this session's tool list is a candidate for exactly this kind of eval. So is any internal MCP server Charter builds as part of the agentic SDLC work.

---

### 3. Skills

**What it is:** A SKILL.md file + supporting assets that Claude loads when relevant. Two eval questions, often conflated:

1. *Triggering:* Does Claude load the skill when it should, and skip it when it shouldn't?
2. *Execution:* When loaded, does following the skill produce the claimed outcome?

**Load-bearing axes:**

- **Output shape** — Triggering is classification (load/don't-load). Execution is generation or artifact-production depending on what the skill does.
- **Failure-cost asymmetry** — Highly asymmetric and direction depends on the skill. For a skill that prevents a bad output (e.g., product-self-knowledge, which stops hallucinated product facts): FN (skill not loaded when needed) is expensive, FP (loaded when not needed) is cheap. For a skill that's heavy to load (large document, lots of assets): FP (loaded unnecessarily) costs tokens and latency.
- **Labeler economics** — Skill authors are typically the labelers. Cheap when the skill owner maintains the eval; expensive when eval is someone else's job.
- **Measurement tractability** — Triggering: high measurability, high generalizability (same eval shape across all skills). Execution: variable by skill.

**The actual eval:**

*Triggering eval:* Curated set of 30–50 queries per skill. Half should trigger, half shouldn't. Run with the skill in the available-skills list, check which triggered. This is a binary classifier eval, straightforward to build and maintain.

*Execution eval:* Depends on skill output. For the pptx skill: does following it produce a valid pptx that meets stated design constraints? For a code-writing skill: does the output pass tests? Golden-set regression when possible, LLM-judge with rubric otherwise.

**Sub-pattern (triggering):**

|                   | Actually needed | Actually not needed |
|-------------------|-----------------|---------------------|
| Skill triggered   | TP              | FP                  |
| Skill not triggered | FN            | TN                  |

Base rate matters enormously — most queries don't need most skills. A skill with a 1% base rate and 99% accuracy might still have terrible precision. Report precision/recall, not accuracy.

---

### 4. Steering

**What it is:** System-level instructions or directives that shape behavior across many interactions (Kiro steering files, Claude Code CLAUDE.md, system prompt directives). Adherence and side-effects are both evaluated.

**Load-bearing axes:**

- **Output shape** — Behavioral adherence (did the model follow the directive) is classification-shaped. Side effects are generation-shaped (did unrelated behavior change).
- **Truth regime** — Gold for explicit directives ("always use TypeScript" is checkable). Reference-free for soft directives ("prefer concise responses"). Steering docs often mix both and evals should separate them.
- **Coverage requirement** — Every interaction, not a sample. Steering is ambient; eval has to reflect that.
- **Distribution shape** — Adversarial clusters matter: scenarios designed to tempt the model away from the directive. A directive that holds 100% of the time in normal scenarios but fails on 3 specific edge cases is a real problem, and uniform sampling won't find it.
- **Temporal regime** — Matters because steering interacts with model updates. A steering file that works with Sonnet 4.5 may behave differently with Sonnet 4.6. Eval needs to be rerun on model changes, not just steering changes.

**The actual eval:**

*Adherence battery:* Fixed scenarios covering both normal cases and adversarial tempters. Run with steering applied, check directive compliance. Binary per scenario; report per-directive compliance rate.

*Side-effect detection:* Same battery run without the new steering, diff the outputs. If adding "always use TypeScript" also changed how the model responds to code review requests, that's a side effect worth knowing about.

**The subtle one:** Steering can rot silently when the model updates. A steering file that worked well with Sonnet 4.5 may be unnecessary, harmful, or differently-interpreted by 4.6. Eval should run on model version changes, not just steering content changes. Most teams don't do this and are surprised when "the same prompts" start behaving differently.

**Cross-reference:** The kiro-knowledge-steering.md file in Wesley's code review project is a direct example. The steering there governs how subagents behave; regression eval on model changes would catch silent drift.

---

## Tier 1 synthesis (before moving to middle tier)

Patterns across commodity:

1. **Golden-set regression is the workhorse.** Four of four use it. The eval machinery to support it (curated sets, diff tooling, LLM-judge harness) is the single highest-leverage infrastructure investment at the commodity layer.

2. **Triggering/adherence is a classifier problem even when the thing itself isn't one.** Skills, steering, and MCP tool selection all have a "should this apply here" question that's classification-shaped regardless of what the thing does once activated.

3. **Base rate and cost asymmetry are usually skipped and usually shouldn't be.** Accuracy without base rate is meaningless; TP/FP/TN/FN without cost weights is decorative.

4. **Measurement tractability is high-generalizability across this whole tier.** Build the eval harness once per shape, reuse across instances. This is why commodity-first was the right place to start — it exposed the reusable machinery.

5. **Model updates are a silent source of regression.** Every commodity eval should be rerunnable on model version changes, not just content changes.

---


---

## Tier 2: Middle Layer

These sit between single-purpose commodity components and full flagship systems. Each has enough complexity that bespoke eval machinery is partially justified, but not so much that every project needs one-off evals.

### 5. Agents / Agent Loops

**What it is:** A single-purpose agent that perceives, reasons, acts via tools, observes, and iterates. ReAct loops, subagents in a larger orchestration (your code review reviewer, diff-analyzer, patch-proposer individually), standalone task agents.

**Load-bearing axes:**

- **Output shape** — Trajectory, not just final output. This is the axis that most distinguishes agent eval from everything else. An agent that arrives at the right answer via a disastrous path (10 wrong tool calls, wasted tokens, near-infinite-loop) is worse than one that arrives there cleanly, even though outcome-only eval scores them identically.
- **Truth regime** — Typically silver or reference-free. Gold trajectories are almost never available — "the right way to solve this problem" usually has multiple valid paths. LLM-judge against a rubric is common; trajectory traces + human review is the gold standard but expensive.
- **Granularity need** — Multi-level. Per-step eval (was each action reasonable given prior observations?) plus overall trajectory eval (did the agent accomplish the task?). Aggregate success rate hides most of the actionable information.
- **Failure-cost asymmetry** — Cost structure is unusual: tokens/latency/tool-call-budget are failure modes in themselves, not just quality degradations. An agent that succeeds in 50 steps when 5 would do is *technically* correct but operationally broken.
- **Distribution shape** — Long-tailed on task difficulty. A small number of hard tasks dominate failure cases. Uniform sampling misleads; difficulty-stratified eval is usually right.

**The actual eval:**

Three layers, each cheap-to-expensive:

*Outcome eval (cheapest):* Fixed task battery, binary success/failure. Measure success rate, tokens-per-task, steps-per-task, tool-call-count. This catches catastrophic regressions but nothing subtle.

*Trajectory eval (middle):* For a sampled subset (or all, if cheap), LLM-judge scores the trajectory: were the steps reasonable, were there avoidable detours, did the agent recover from errors. Rubric-based. Catches "succeeded despite being bad at the task."

*Human trajectory review (most expensive):* For a small set of the most important tasks, human expert reviews the trace. Gold standard. Use this to calibrate the LLM-judge layer above.

**Sub-pattern (when outcome is binary):** TP/FP/TN/FN on task success matters less than the trajectory metrics. But if the agent itself makes classification-shaped decisions during its loop (your code review reviewer deciding "is this a defect"), each of those decisions gets its own confusion matrix.

**The thing most teams get wrong:** They evaluate agents like they evaluate prompts — on outcome only — and miss that trajectory quality is where agents silently degrade. An agent can maintain high outcome success while becoming wildly inefficient or taking dangerous paths.

**Cross-reference:** Your code review agent's subagents are each evaluable at this layer. The orchestrator is a different shape (closer to a router/dispatcher). The trajectory-vs-outcome split maps directly onto Wesley's meta-analysis finding that 64% of misses are reasoning failures — a trajectory eval would have surfaced that earlier than an outcome eval does.

---

### 6. RAG Pipelines (as a unit)

**What it is:** Retrieval + generation, evaluated end-to-end as a commodity pattern. Distinct from the flagship RAG diagnostic because this is the generic version — "does retrieval surface the right docs and does the model answer correctly from them."

**Load-bearing axes:**

- **Output shape** — Composite: retrieval (ranking) + generation (free-text answer). Standard practice evaluates these separately, which is right.
- **Truth regime** — Mixed. Retrieval: can be gold (curated queries with known-relevant docs). Generation: typically reference-free (faithfulness to retrieved context) or silver (reference answer from a human).
- **Truth-proxy quality** — Known-biased in a specific way: "faithful to retrieved context" is not the same as "correct." A RAG system that faithfully answers from a wrong retrieved doc scores well on faithfulness and badly on ground truth. This gap is the most common silent failure mode in RAG eval.
- **Granularity need** — Segmented by query type (factual, comparative, multi-hop, ambiguous). Aggregate numbers hide that the system is 95% on factual and 30% on multi-hop.
- **Measurement tractability** — High measurability for retrieval (precision@k, recall@k, MRR, nDCG are standard and automatable). Soft for generation (faithfulness, answer quality, groundedness — usually LLM-judge or human eval). High generalizability: the eval harness is reusable across RAG deployments.

**The actual eval (standard stack):**

*Retrieval metrics:* For each eval query, known-relevant docs are identified. Compute recall@k (did we retrieve the right docs), precision@k (how many retrieved were relevant), MRR (how high was the top relevant result ranked).

*Generation metrics:* Faithfulness (does the answer match the retrieved context), answer relevance (does it address the question), groundedness (are claims supported by retrieved content). Typically LLM-judge with a rubric.

*End-to-end metrics:* Correctness (does the answer match ground truth, when ground truth exists). This is the metric most often missing — because building ground-truth eval sets is expensive — and its absence is what allows "faithful to wrong retrieval" failures to slip through.

**Sub-pattern (retrieval as classification of "relevant or not per doc"):** Standard TP/FP/TN/FN with the wrinkle that TN is usually enormous (most docs in the corpus are not relevant to most queries). Precision and recall are more informative than accuracy.

**The thing most teams get wrong:** Optimizing retrieval and generation separately without the end-to-end correctness check. A retriever that hits 95% recall@5 and a generator that's 95% faithful can still produce a system that's 60% correct — because the 5% missed retrievals and the 5% unfaithful generations compound, and faithfulness to bad retrievals doesn't register as failure.

**Cross-reference:** This is exactly the commodity version of the flagship RAG diagnostic. When we get to that flagship profile, the load-bearing axes will be additive to these (three-way classification, abstention, domain-specific truth regimes) — not replacements.

---

### 7. Classifiers / Extractors

**What it is:** Narrow LLM-powered classification or extraction. "Is this ticket a bug or a feature request," "extract all acronyms from this text," "tag this code comment as documentation or dead-code." Sits between prompts and agents — more complex than a one-shot prompt because it's deployed at scale with measured quality, but simpler than agents because there's no loop.

**Load-bearing axes:**

- **Output shape** — Classification (categorical or multi-label) or extraction (structured output). Cleanest eval shape in this whole document.
- **Truth regime** — Usually gold-feasible. Labels are discrete enough that human annotation is tractable. This is what makes classifiers attractive as an eval archetype: the whole classical ML eval stack applies directly.
- **Labeler economics** — Often the binding constraint. Domain classifiers (Wesley's acronym expansion, telecom-specific ticket classification) need domain experts as labelers. 500 labeled examples might cost more than building the system.
- **Distribution shape** — Class imbalance is almost always present in real deployments. Bug vs. feature request might be 80/20; defect vs. lab-flakiness vs. transient (your RAG case) is extremely imbalanced toward defect.
- **Failure-cost asymmetry** — Domain-specific but usually significant. Mis-routing is not symmetric.

**The actual eval:**

Classical ML eval stack:
- Held-out labeled test set, stratified by class
- Report per-class precision/recall/F1, not just accuracy
- Confusion matrix in full (not just TP/FP/TN/FN when >2 classes — the full matrix)
- Calibration: if the classifier outputs confidence, is 80% confidence actually right 80% of the time
- Slice analysis: performance by subpopulation (time period, source, domain subfield)

**Sub-pattern (multi-class):** The 2×2 TP/FP/TN/FN matrix generalizes to an N×N confusion matrix. Row = true class, column = predicted class. Diagonal = correct. Off-diagonal structure reveals *which* confusions the classifier makes — crucial for understanding failure modes. A classifier that confuses "lab flakiness" with "transient" is a different problem from one that confuses "defect" with "transient."

**The thing most teams get wrong:** Skipping the stratified held-out set and calibration. Reported numbers are then either biased by class imbalance (accuracy looks great because you always predict the majority class) or misleading about confidence ("high-confidence" predictions aren't actually more reliable).

**Cross-reference:** The acronym expansion work in the RAG project is a classifier. The "is this Jira ticket a bug, feature, or task" work for the metrics framework is a classifier. The triggering logic in skills (tier 1) is a classifier. Classifier eval machinery is the single most reusable piece in this whole framework.

---

### 8. Evaluators (LLM-as-Judge)

**What it is:** An LLM evaluating another LLM's output. Increasingly the default for anything reference-free. Has to be evaluated itself, or the whole eval stack is built on untrustworthy ground.

**Load-bearing axes:**

- **Output shape** — Classification (pass/fail, preferred/not) or scalar score. Rubric-based or reference-based.
- **Truth regime** — Gold (human ratings on a curated sample) is the only viable option. This is the axis that most teams handle poorly: they skip human calibration entirely and treat LLM-judge outputs as ground truth by fiat.
- **Truth-proxy quality** — Known-biased in specific documented ways: position bias (first option favored), length bias (longer answer favored), self-preference (judges from the same model family rate their own outputs higher), style bias (fluent answers rated higher than correct-but-terse). These biases are *known to exist by default*; assume they're present in any new judge unless tested.
- **Labeler economics** — High. Evaluating the evaluator requires human expert ratings on the same items the judge rates. But it's a one-time cost per judge (with periodic re-validation on model updates).
- **Measurement tractability** — Measurability is crisp (agreement metrics with humans). Generalizability is mixed: judge-eval machinery reuses, but specific bias checks are judge-specific.

**The actual eval:**

*Agreement eval:* Sample 100–500 items, have humans rate them, have the judge rate them, measure agreement (Cohen's kappa, Krippendorff's alpha, or for scalar scores Spearman correlation). This is the headline metric. Kappa below 0.6 means the judge is not trustworthy; above 0.8 means it's usable.

*Bias battery:* Fixed test suite for known biases. Swap position, add verbosity without content, present own-model-family vs. cross-family outputs, vary style while holding substance constant. Measure how much judge ratings shift under these manipulations. High shift = high bias = need mitigation (position randomization, length normalization, cross-family judging).

*Calibration check:* If the judge outputs a scalar score, does score magnitude correlate with human rating magnitude, or is the judge just ordinal?

**Sub-pattern:** When the judge is binary pass/fail, standard TP/FP/TN/FN *against human labels as ground truth*. The confusion matrix cells here have a meta-character — FP means "judge said pass, human said fail," which is a failure mode of the eval infrastructure itself.

**The recursive problem:** Evaluating the judge requires humans; humans are inconsistent; human inter-annotator agreement caps what the judge can achieve. A judge hitting 0.75 agreement with humans who agree with each other at 0.80 is near the ceiling. Reporting judge quality without reporting human IAA ceiling is common and misleading.

**Cross-reference:** Your code review agent's reviewer is judged by the orchestrator's verification pass — that's a judge evaluating a judge, and neither has been calibrated against human expert ratings to my knowledge from the project summary. This is a gap. The RAG diagnostic's confidence scorer is also a judge-shaped component.

**v1.1 research updates (Feb–Apr 2026 incorporations):**

- **Unified calibration protocol** (Chen et al. 2601.05420 [LB-90%], Lee et al. 2511.21140 [LB-90%], Feng et al. 2601.20913 [LB-80%]): the statistical skeleton under "judge calibration" has converged. Recipe: (1) 100–500 item human calibration set, (2) estimate judge sensitivity/specificity, (3) apply Rogan–Gladen correction with Lang–Reiczigel CI (or EIF/PPI++ when calibration-test shift is small), (4) run transport-audit test per policy/version, (5) recalibrate on model-version change. See Statistical Estimation Reference in preamble.
- **Jury patterns mature, CyclicJudge is the new default.** PoLL (Verga 2024 [LB-75%] [MG-CAVEAT — pre-June 2025; multi-judge mechanism robust, specific 7× cost-ratio claim depends on then-current pricing]): 3-judge panel beats GPT-4 at ~7× lower cost. Sage (2512.16041 [IL-70%]): +15% max from panels. **CyclicJudge (2603.01865 [LB-65%]): round-robin judge-to-scenario assignment eliminates systematic bias at same cost as single-judge.** This is the recommended default when compute allows. Avoid *adversarial debate* ensembles (ChatEval [IL-60%]) — can hurt reliability.
- **κ heuristics refined.** Still: human-human κ = 0.80 is the deployment bar for general response-pair judging (Judge's Verdict 2510.09738 [LB-80%]); top judges reach 0.78–0.82. **Must report κ AND correlation jointly** — r=0.95 with κ=0.5 signals systematic bias (judge ordering is right, absolute values wrong). **Set your domain-specific IAA as the target** — don't target 0.8 if your expert raters disagree at 0.6.
- **Calibration drift formally measured for the first time** (Wiese PLOS ONE, Feb 2026 [LB-85%]): 10-week preregistered tracking, 3 model families. Uncalibrated judge Kendall's τ = 0.38–0.52 (volatile); Bradley-Terry-corrected τ = 0.59–0.68 (stable). Methodology: 240-prompt fixed bank × 6 domains, PELT/MBIC change-point detection. Blueprint for monitoring judge drift over time.
- **Scale mechanics matter more than judge choice on some tasks** (2601.03444 [LB-80%]): 0–5 scale yields strongest human–LLM alignment; 0–10 weakest. 4-level severity (critical/high/medium/low) is near-optimum for code review. Resist adding sub-levels or switching to numeric 1–10.
- **Small reasoning judges can replace large non-reasoning judges on code** (CodeJudgeBench, 2507.10535 [LB-75%]): thinking Qwen3-8B outperforms 70B non-thinking fine-tuned judges. Caveat: sub-7B models fail to emit valid judgments ~15% of the time on code (2507.16587 [LB-70%]). Reasoning-capable small models only.
- **AXIOM warning (2512.20159 [LB-70%]):** "complex agentic judges" (CodeJudge, CodeVisionary) *decrease* Krippendorff's α by 78.2% on ordinal code quality, with systematic under-estimation bias (mean 1.33 vs ground-truth 2.45). Simpler rule-based or rubric-based judges often outperform agentic ones on ordinal tasks. Relevant when designing the code review verification-pass judge.
- **Hardt ceiling (2410.13341 [LB-95%]):** when judge accuracy ≤ judged-model accuracy, debiasing saves at most 2× labels. For high-stakes judging of frontier agents, budget large human calibration sets — the "calibrate once, benefit forever" economics don't hold.
- **Judge benchmarks now exist as a defensible stack.** CodeJudgeBench [LB-75%] for code, RubricEval [LB-65%] for rubric-level, JudgeBiasBench (2603.08091 [LB-70%]) for bias taxonomy, Judge Reliability Harness (2603.05399 [LB-70%]) for ordinal-grading stress tests, AXIOM [LB-70%] for ordinal code quality. Pick the one matching your domain rather than generic leaderboard judges.
- **Preference leakage** (ICLR 2026 [LB-80%]): same-family judges are contaminated by shared training data. Claude-3 judging Claude-3.5 is contaminated. Cross-lineage, not just cross-family, is the right discipline.
- **Ordinal agreement metrics** (no LLM-native standard yet; use classical): quadratic-weighted κ (penalizes critical→low 9× more than high→medium), Krippendorff's α with ordinal distance, Gwet's AC2-Q (skewed distributions), Kendall's τ-b (rank agreement). AXIOM uses Krippendorff's α as primary. Report multiple and document choice.

---

### 9. Context Assembly / Retrieval Preprocessors

**What it is:** Chunkers, rerankers, context compressors, query expansion modules. Components that shape *what the model sees* before generation. The chunking experiment in the code review project lives here.

**Load-bearing axes:**

- **Output shape** — Intermediate artifact, not a final answer. Chunks, reranked lists, compressed contexts. This is the axis that makes eval subtle: the preprocessor's output isn't directly consumed by a user.
- **Measurement tractability** — The split between intrinsic and extrinsic eval is the defining feature. Intrinsic: does the chunker produce chunks that satisfy some intrinsic quality metric (coherence, size distribution, boundary quality)? Extrinsic: does downstream task quality improve when using this preprocessor vs. another?
- **Baseline** — Extrinsic baselines are usually "the current preprocessor" and "no preprocessing" (e.g., for chunking: fixed-size baseline; for reranking: raw retrieval order). Both matter — no-preprocessing tells you if the component is worth its cost at all.
- **Truth regime** — Intrinsic: reference-free or rule-based. Extrinsic: whatever the downstream task's truth regime is.

**The actual eval:**

*Intrinsic (cheap, fast):* Metrics computed directly on the preprocessor's output. For chunking: chunk size distribution, semantic coherence of chunks (embedding-based), boundary quality. For reranking: how much does the reranked order differ from input. These are iteration-friendly — fast feedback for preprocessor tuning.

*Extrinsic (slower, more meaningful):* Downstream task eval with and without the preprocessor. For the chunking experiment: run the full code review pipeline with chunks at 100 LOC, 300 LOC, 600 LOC, 1000 LOC; measure recall. This is the eval that actually justifies the preprocessor's existence.

**The thing most teams get wrong:** Over-trusting intrinsic metrics. Chunks that look coherent by embedding similarity can underperform downstream. Rerankers that produce "better" orderings by some intrinsic metric can harm end-to-end task performance. Extrinsic eval is the only one that pays the bills.

**Cross-reference:** The chunking experiment in the code review project is explicitly extrinsic (recall as the outcome metric), which is the right choice. The 301–600 LOC sweet spot finding is an extrinsic result; any intrinsic chunking metric would have missed the specifics of where chunking actually helps vs. doesn't.

---

### 10. Memory Systems

**What it is:** Persistent storage and retrieval of information across sessions or within long-running contexts. Wesley's ghost-loom three-tier memory, the Intelligent Decay mechanisms in the Agentic SDLC project, Claude's own cross-conversation memory.

**Load-bearing axes:**

- **Output shape** — Composite: retrieval (did the right memory surface at the right time) + retention (was the right thing remembered/forgotten over time).
- **Temporal regime** — This is *the* distinguishing axis. Memory eval is inherently temporal. Static offline eval captures "given this memory state, does retrieval work," but misses the harder question: "under sustained use, does the memory state itself stay healthy."
- **Failure-cost asymmetry** — Highly asymmetric and direction-dependent:
  - For working memory (within-session): FN (forgot something needed) is usually more expensive than FP (retrieved something irrelevant).
  - For long-term memory with capacity limits: the calculus flips. Storing everything eventually poisons retrieval. FN of forgetting-a-thing-we-should-have-forgotten is expensive.
  - This bidirectionality is why "Intelligent Decay" is a nontrivial design problem.
- **Distribution shape** — Long-tailed: most memories will never be retrieved; a few are retrieved constantly. Recency and frequency both matter.

**The actual eval:**

*Retrieval eval (standard):* Given a query and a memory state, does the right memory surface? Precision@k, recall@k. This is classical IR eval with the twist that "relevance" is contextual (the same query might need different memories depending on session context).

*Retention eval (the harder one):* Simulate extended use — inject memories over time, query across time, measure whether important-but-old memories remain retrievable and whether unimportant-but-recent memories don't crowd them out. This usually requires synthetic workloads because real long-term traces are rare.

*Self-degradation eval (the one the Agentic SDLC project flagged as essential):* Specifically for estimation/feedback loops where the system's own outputs become future memories. Does the system drift toward its own past predictions rather than ground truth? This is a form of feedback-loop evaluation that's hard to do without careful instrumentation.

**Sub-pattern (retrieval as classification):** TP/FP/TN/FN per query, but with the complication that "relevant" changes over time. A memory that was relevant three months ago may not be now.

**The thing most teams get wrong:** Evaluating memory only on retrieval quality at a point in time, missing the temporal dimension. A memory system that's 95% retrieval accuracy on week 1 and 60% on week 12 is a different problem from one that's 80% throughout.

**Cross-reference:** Wesley's own cross-conversation memory visible in this session is a memory system. The temporal regime question applies: memory summaries update periodically, recent conversations may not yet be reflected, deletion propagates nightly. All of these are temporal eval concerns that apply to production memory systems.

---

## Tier 2 synthesis

Patterns across middle tier:

1. **Composite output shapes dominate.** Five of six have composite output shapes (retrieval+generation, contract+usability, classification+extraction, intrinsic+extrinsic, retrieval+retention). The axis doesn't just describe the output — it forces separation of eval concerns that are often conflated.

2. **Truth-proxy quality becomes load-bearing.** At the commodity tier, truth regime was usually load-bearing but truth-proxy quality was often standard ("the proxy is the proxy"). At the middle tier, the *gap between proxy and truth* becomes a major design issue — most visible in LLM-as-judge (the evaluator is the proxy) and RAG (faithfulness is not correctness).

3. **Trajectory and temporal axes emerge.** Agents force trajectory eval; memory systems force temporal eval. Neither existed meaningfully at the commodity tier. These are the axes that most differentiate middle-tier eval from commodity.

4. **Extrinsic eval beats intrinsic, almost always.** Context assembly surfaced it explicitly, but it applies to all middle-tier cases: the only metric that pays the bills is whether the downstream task improves.

5. **Recursive eval problem (judging the judge).** LLM-as-judge is increasingly the evaluation method across this whole tier, which means the judge itself needs calibration. This is a gap in every project I've seen documented and is a leading candidate for the cross-cutting section alongside model-update regressions.

---

## Tier 3: Flagship Layer

These are the full-system evals that motivated this framework. Each builds on the commodity and middle-tier patterns rather than replacing them — the eval machinery below *layers* onto the earlier tiers.

### 11. RAG Diagnostic Assistant (three-way classification with abstention)

**What it is:** The flagship RAG system for telecom test failure classification. Three-way classification (device defect / lab stability / transient) with calibrated abstention, target ≥50% accuracy on a 200-engineer deployment.

**Load-bearing axes (all eleven show up, which is itself diagnostic):**

- **Output shape** — Composite and unusual: three-way classification + abstention + supporting evidence (retrieved docs, reasoning chain). Each component needs its own eval.
- **Truth regime** — Silver-standard, with known noise. Jira resolution notes are the primary truth source; they're written by engineers for operational purposes, not for labeling. Resolutions like "hardware swap resolved issue" don't tell you whether the original problem was truly a defect or lab flakiness that coincidentally cleared.
- **Truth-proxy quality** — This is *the* load-bearing axis for this project. The proxy (ticket resolution text) has documented failure modes. Two specifically:
  1. *Resolution ambiguity:* The same resolution ("replaced cable modem") can correspond to true defect, true lab issue, or neither. Engineers don't distinguish in writing.
  2. *Survivorship bias:* Jira only contains tickets that were filed. Transient issues that cleared before a ticket was filed don't exist in the corpus. The class "transient" is underrepresented relative to its true base rate.
- **Baseline** — Multiple, and the choice shapes credibility:
  - Random three-way baseline: 33%. Embarrassingly easy to beat.
  - Majority-class baseline: whatever the most common class is (probably "defect" given survivorship). Harder.
  - *Current engineer practice:* Senior engineer ad-hoc diagnosis with Confluence + Jira search. **This is the real baseline** because it's what the system replaces. If the RAG system isn't meaningfully better than a capable engineer with existing tools, it doesn't ship.
  - Strong-simple baseline: well-prompted single-model call with BM25 retrieval. Tells you whether the full agentic + KG architecture is justified over something simpler.
- **Coverage requirement** — Abstention is first-class. The system must be willing to say "I don't know" on cases where confidence is insufficient. Coverage is therefore a *tunable parameter*, not a fixed requirement. The eval must operate across coverage levels (risk-coverage curves).
- **Failure-cost asymmetry** — All three cells of off-diagonal error have different costs:
  - Defect → Lab stability (real bug called as lab issue): escaped defect reaches customers. Expensive.
  - Lab stability → Defect (lab flakiness called as bug): false alarm wastes engineering time, erodes trust. Moderate.
  - Defect → Transient (real bug called as transient): defect papered over. Expensive, delayed discovery.
  - Transient → Defect: wasted investigation. Mild.
  - Eval must report cost-weighted error, not accuracy.
- **Distribution shape** — Severely long-tailed. Top 10 failure modes dominate. A system that's 70% accurate on the top 10 and 20% accurate on the long tail might be operationally better than one that's 50% uniformly.
- **Granularity need** — Slice eval by failure type is non-negotiable. Aggregate accuracy is not the ship/no-ship metric.
- **Temporal regime** — Offline eval on historical Jira for calibration; shadow-mode online eval for production validation; eventual online eval via engineer feedback. All three layers required, not optional.
- **Labeler economics** — Expensive. Domain expert labelers (senior network engineers) reviewing historical tickets to produce gold labels. Probably the binding resource constraint on the whole eval.
- **Measurement tractability** — Low generalizability (bespoke to this system), moderate measurability (the scoring is crisp if you have gold labels; getting gold labels is hard).

**The actual eval (staged):**

*Stage 0: Gold labeled set construction (the unsolved piece).* Sample ~500 historical Jira tickets stratified by failure type. Two senior engineers label each ticket's true root cause category (defect/lab/transient/unknown). Compute IAA. Reconcile disagreements through discussion. Result: gold eval set with documented IAA ceiling.

Practical note on sampling: stratifying by failure mode matters more than stratifying by time period because of the long tail. But a time-stratified held-out set for the most recent 10% of tickets is also needed to detect temporal drift.

*Stage 1: Retrieval eval (commodity tier + middle tier reused).* Standard recall@k, precision@k on the spec corpus and Jira graph.

*Stage 2: Classification eval (classifier tier pattern).* Per-class precision/recall/F1 against gold. Full 3×3 confusion matrix. Cost-weighted error. Calibration (reliability diagram).

*Stage 3: Abstention eval.* Risk-coverage curve. At each coverage level (50%, 60%, ..., 100%), what's accuracy on answered cases? Where does the knee occur? This is the curve that goes in front of the VP, not a single accuracy number.

*Stage 4: End-to-end eval against engineer baseline.* Human study: for a held-out set of failures, does the RAG system reach the right answer faster or more accurately than a senior engineer with existing tools? This is the shipping metric.

**Sub-pattern (3×3 confusion matrix):**

|                          | True: Defect | True: Lab | True: Transient |
|--------------------------|--------------|-----------|------------------|
| Predicted: Defect        | TP           | FP_lab    | FP_trans         |
| Predicted: Lab           | FN_def→lab   | TP        | FP_lab→trans     |
| Predicted: Transient     | FN_def→trans | FN_lab→trans | TP            |

Off-diagonal cells each have independent cost. Diagonal is correct. Abstention adds a fourth column (predicted: abstain) with its own cost (zero accuracy gain, but zero false-signal cost either).

**The central eval question:** Is this system better than a senior engineer with Cmd-F in Confluence? If yes, by how much, and on which failure types? That's the only question leadership cares about.

**What was unspecified in the original project summary:** Everything in Stage 0 (gold set construction) and Stage 4 (vs-engineer baseline). These are the "eval is the unsolved problem" items from the summary. The framework makes this concrete: without Stage 0, Stages 1–3 don't have ground truth; without Stage 4, the project doesn't have a ship criterion.

**v1.1 research updates (Feb–Apr 2026 incorporations):**

- **Bayesian Orchestration reframing (2601.01522 [LB-80%], Jan 2026):** threshold-based discriminative classification is *formally inadequate* under asymmetric costs with abstention. Treat the LLM as a likelihood and apply Bayes-optimal action rules: choose action minimizing `Σ_y P(y|x)·C(action, y)` with abstain as an explicit action. This is a mental-model correction, not a parameter tweak. Don't use threshold-per-class; use expected-cost minimization over the full action set.
- **RAG actively reduces abstention and increases hallucination** (Joren et al. ICLR 2025, 2411.06037 [IL-60%] [MG-CAVEAT]). Gemini 1.5 Pro abstention collapsed from 100% to 18.6% when RAG was added. **You cannot infer abstention quality from accuracy gains.** Evaluate abstention behavior directly. Sufficient-context autorater + P(True) combined via logistic regression achieves 2–10 pp gain in selective accuracy at matched coverage — use this as the signal.
  - **Model-generation caveat in detail:** Gemini 1.5 Pro is a February 2024 model, and 2024-era prompting did not include explicit abstention licenses common in 2025+ practice. Two parts of this finding stand independently of model age: (a) the *mechanism* — RAG prompt structures bias models toward using provided context, which can suppress abstention as a side effect — is plausibly still partially active in current frontier models, and (b) the *methodological recommendation* — measure abstention behavior directly rather than inferring from accuracy — is robust regardless of magnitude. What likely does NOT generalize: the specific 100% → 18.6% magnitude. Frontier models post-RLHF for "context-insufficient → say so" likely show much smaller abstention shifts. Recommended practice: measure baseline abstention without RAG and with RAG on your target model; treat the delta as your actual abstention effect; re-measure on every model version bump (C1 discipline).
- **Confidence signal ordering: P(True) > semantic entropy > CoCoA > self-consistency > verbalized numeric** (SECL 2604.09624 [LB-70%], CISC ACL 2025 [LB-70%]). P(True) is lower-bounded theoretically and gives ECE reductions of 56–78% across Phi/Gemma. Elicit as single-token probability after "Is this classification correct? Reply 0 or 1." Caveat (Phillips 2603.21172 [LB-65%]): entropy-based signals don't reliably discriminate correct/incorrect for all frontier models — require AUROC ≥ 0.65 on held-out before trusting.
- **Abstention mechanism: 4-option MCQA + split conformal risk control.** Treat {defect, lab_stability, transient, abstain} as 4-option MCQA following the Ren et al. CoRL 2023 template [LB-75%] (paper: "Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners"; the framework introduced therein is commonly referred to as "KnowNo"). Use Angelopoulos et al. 2022 / ICLR 2024 Conformal Risk Control [LB-95%] to calibrate a single threshold τ such that expected per-example cost on accepted items ≤ user budget α. 300–500 calibration examples for marginal coverage; 2–4k if conditional coverage matters (almost certainly yes — class prevalences will differ between calibration and deployment). Library: TorchCP (native LLM support as of 2025).
- **Evaluation stack update:**
  - **Primary metric:** expected cost under explicit (C_defect→lab, C_defect→trans, C_lab→defect, C_trans→defect, C_abstain, ...) cost matrix, plotted vs coverage. Not accuracy.
  - **AUGRC replaces AURC** (Traub et al. NeurIPS 2024, 2407.01032 [LB-85%]): AURC fails monotonicity and over-weights high-confidence failures. Report AUGRC as primary; keep AURC and selective-accuracy@{80%, 90%, 100%} for continuity with prior literature.
  - **AUCM** (Answerable-Unanswerable Confusion Matrix, Madhusudhan COLING 2025, 2407.16221 [LB-75%]): cleanest practitioner-facing metric where abstain-on-answerable and answer-on-unanswerable are different errors.
  - **Abstention precision/recall/F1** (AbstentionBench, 2506.09038 [LB-75%]): as LLM-judge-scored metrics.
- **Stage 0 gold set construction — concrete recipe now exists:**
  1. **Stratified sampling** along (resolution-field value × ticket age × subsystem × resolver team). Document sample frame explicitly.
  2. **LLM pre-labeling** via Adjudicator architecture (2512.13704 [LB-65%]): dynamic KG per item + multi-persona council (Policy Expert + Contextual Analyst + Skeptical Adjudicator) + voting + KG-override. Achieved 0.99 F1 vs 0.48 single-LLM baseline on Mozilla Bugzilla — directly analogous scenario.
  3. **Active-testing prioritization** via GAT (2603.19264 [LB-70%], Feb 2026): 40% estimation-error reduction vs random. Fisher-information-based acquisition, not uncertainty sampling.
  4. **Human expert adjudication** on 5–10% calibration slice. QUEST-style multi-adjudicator protocol until κ ≥ 0.7.
  5. **Rogan–Gladen-corrected metrics** with Lang–Reiczigel CI + bootstrap CI. Document excluded fraction as survivorship disclosure. See Statistical Estimation Reference.
- **Survivorship bias is real and the field mostly ignores it.** Jira only contains tickets that were filed — "transient" is systematically under-represented. MacAvaney et al. (2204.12852 [IL-80%] [MG-CAVEAT — IR methodology pre-2025; mechanism portable, specific MS MARCO results not directly applicable]) on MS MARCO is the only directly portable methodology. Recommendation: sample a **shadow corpus** of non-ticketed events (on-call chats, monitoring auto-resolutions, silent log failures), label a subset, report metrics separately on ticketed vs shadow, and use `min(P_ticketed, P_shadow)` as a survivorship-adjusted bound.
- **Arm-dependent bias impossibility result** (2601.21471 [LB-75%]): proxy-only comparison of system variants is information-theoretically impossible when variants have differential failure modes. When A/B-testing RAG diagnostic versions, always include human audits — you cannot audit exclusively with the system's own confidence signals.
- **Abstention-specific benchmarks now exist** — AbstentionBench (20 datasets, 35k queries [LB-75%]), UA-Bench (2604.17293 [LB-65%], 3,500 items distinguishing data vs model uncertainty — relevant for three-way classification), MedAbstain (2601.12471 [LB-65%], adversarial + CP integration), Sufficient-Context autorater dataset (Joren ICLR 2025 [LB-70%] — RAG-native, directly your use case).

---

### 12. Code Review Agent (agent-knowledge pipeline)

**What it is:** Multi-pass tool-grounded GitLab MR review agent. Already at v0.7.2 deployed in production. Eval has real results (83% recall, 78% precision on Tier 1 CVE benchmark). Question is how to mature the eval from point-in-time benchmarks to continuous quality measurement.

**Load-bearing axes:**

- **Output shape** — Composite: findings (classification per potential issue), severity (ordinal), fixes proposed (generation). Each has its own eval shape.
- **Truth regime** — Silver: known defects from CVE databases (high-signal but narrow), human reviewer ratings on production MRs (broader but noisier). The Category D measurement artifact ("commit-proximity proxy fails on 10-15% of true positives") *is* the truth-proxy-quality problem made explicit.
- **Truth-proxy quality** — Explicitly bounded, which is the right move. The 10-15% measurement artifact is documented, which means precision numbers have a known-minimum true value. Most teams don't even attempt this bounding.
- **Baseline** — Multiple, and all of them matter:
  - Human reviewer: what fraction of findings would an expert human flag? Hard ceiling on utility.
  - Naive prompt: single LLM call on the diff, no tools, no multi-pass. Cost-benefit comparison.
  - Previous version: v0.7.1 vs. v0.7.2 on the same benchmark. Regression detection.
- **Failure-cost asymmetry** — Sharply asymmetric and direction-dependent:
  - Critical severity: FN (missed real critical bug) >> FP (false alarm on critical). High-severity findings warrant more false positives if they catch real bugs.
  - Nitpick severity: FP (nitpick that isn't worth fixing) > FN (missed nitpick). Here false positives erode developer trust fast.
  - The existing severity-specific precision targets (~60/50/45/40%) reflect this intuition. Framework validation: this is the right shape, and the numbers are defensible because they're weighted by cell cost.
- **Distribution shape** — Long-tailed on defect type. Most bugs are common patterns (null deref, off-by-one, auth bypass); a few are novel. A system that catches 90% of common bugs and 20% of novel is different from one that catches 60% uniformly — both have their place; the eval needs to report the distribution.
- **Granularity need** — Slice eval by severity (already done), by language (already done), by defect type (less done), by MR size (partially done — the 301–600 LOC chunking finding came from this). The meta-analysis is *exactly* slice analysis at scale.
- **Temporal regime** — Online via production deployment. Offline via benchmark rerun. The gap: no continuous regression tracking across model versions yet.
- **Measurement tractability** — Moderate measurability (defect presence can be verified with tests; severity is judgment), low generalizability (very bespoke to this pipeline).

**The actual eval (already mostly in place, gaps flagged):**

*Benchmark (done):* Tier 1 CVE benchmark, 6 firmware/networking vulnerabilities, recall and precision measured. This is the headline.

*Meta-analysis (done):* ~55-60 missed bugs analyzed for root cause. Result: 64% reasoning failures, 43-50% attention failure at 301-600 LOC. This is slice analysis producing actionable design input.

*Backtesting infrastructure (P1-5, gap):* Continuous eval on historical MRs. Without this, regressions between versions are detected late. Framework says: this is the cross-cutting "model-update regression" concern applied to this system specifically.

*Judge layer (P1-2, gap):* LLM-as-judge as a precision oracle. Framework says: this is the recursive "judge the judge" concern — if the judge is built, it needs its own calibration against human ratings.

*Precision calibration study (P0-9, gap):* Manual human review of a sample of findings to calibrate the commit-proximity proxy. This directly addresses the Category D measurement artifact.

**Sub-pattern (per-severity confusion matrix):** For each severity tier, separate TP/FP/TN/FN with tier-specific cost weights. The aggregate precision/recall numbers are misleading without this breakdown. This is already the practice; framework just affirms it.

**The central eval question:** Given the measured results (83% recall, 78% precision with the Category D caveat), is the system catching bugs at rates that justify its cost *and* is it reliable enough that developers trust it and don't start ignoring its output? Trust erosion is a quieter failure mode than accuracy, and it's not directly in the current eval stack.

**The connection to the RAG diagnostic:** Both systems have explicit measurement-artifact problems (Category D for code review, resolution-text ambiguity for RAG) and both benefit from the same framework move — bound the error, document the bound, report numbers with the bound acknowledged.

**v1.1 research updates (Feb–Apr 2026 incorporations):**

- **Category D bounding is now formal math, not rhetoric.** Apply Rogan–Gladen directly. At ε = 0.125 symmetric proxy error (your documented 12.5% midpoint), `P_true ≈ 1.33·P̂ − 0.167`. At observed P̂ = 0.78, corrected **P_true ≈ 0.87 lower bound** with variance inflation ~1.78× (denominator 0.75 squared). Lang–Reiczigel CI correction required for honest reporting. Minimum 100 calibration items for stable sensitivity/specificity estimates. See Statistical Estimation Reference in preamble. **This reframes the "78% precision with Category D caveat" reporting as a concrete bounded claim rather than a hedge.** [LB-95% — math is solid, applied correctly]
- **CodeJudgeBench (2507.10535 [LB-75%]) is your judge-benchmark.** Don't use generic response-pair benchmarks like MT-Bench for code review judge validation. CodeJudgeBench uses LiveCodeBench-v6 problems (1,055 items, May 2023–Apr 2025 contamination-controlled) with position-swap evaluation. Validates your judge choice and confirms pair-wise > point-wise for code.
- **Small reasoning judge can replace Opus 4.6 for verification pass.** Thinking Qwen3-8B outperforms fine-tuned 70B non-thinking judges on code (CodeJudgeBench [LB-75%]). Your current architecture uses Opus 4.6 for review and Haiku for supporting agents. Consider evaluating a small reasoning judge for the verification pass — likely substantial cost reduction with no quality loss. Caveat: sub-7B models fail to emit valid judgments ~15% of the time on code [LB-70%], so test empirically before swapping.
- **CyclicJudge (2603.01865 [LB-65%]) is the drop-in jury pattern at no extra cost.** Round-robin judge-to-scenario assignment eliminates systematic judge bias at the same total cost as single-judge evaluation. Specifically applicable to the verification pass — instead of one Opus reviewing every finding, cycle 3 judges across findings with provably optimal variance properties.
- **AXIOM warning — complex agentic judges underperform on ordinal code quality** (2512.20159 [LB-70%]). CodeJudge, CodeVisionary decrease Krippendorff's α by 78.2% on ordinal severity (mean 1.33 vs ground-truth 2.45, systematic under-estimation). Implication for your severity scoring (critical/high/medium/low): simpler rule-based or rubric-based judges likely outperform elaborate agentic verification. Test the verification pass specifically for systematic severity under-estimation.
- **Ordinal agreement: report Krippendorff's α (with ordinal distance) + quadratic-weighted κ + Kendall's τ-b.** [LB-95% — classical statistics, well-established] Weighted κ penalizes critical→low 9× more than high→medium, reflecting cost asymmetry. AXIOM uses α as primary; join it with κ and τ-b for robustness.
- **Grading scale mechanics favor your 4-level severity** (2601.03444 [LB-80%]). 0–5 scale yields strongest human–LLM alignment; 0–10 weakest; result stable across temperature 0.1–1.0. Your critical/high/medium/low (4 levels) is near-optimum. Resist any push to expand to 1–10 numeric severity.
- **Reasoning effort is not monotonic on code judgment** (2512.01232 [IL-65%], GPT-OSS 120B): LOW reasoning beats HIGH reasoning on mean absolute error and reliability at 41% lower cost. Tune reasoning budget empirically per task rather than defaulting to maximum thinking tokens.
- **Preference leakage warning** (ICLR 2026 [LB-80%]): using Claude as judge for Claude output is contaminated. Cross-lineage judging (e.g., GPT-family judge of Claude output) is the right discipline for high-stakes eval.
- **Reliability engineering reframing applies to long MR review sessions.** See Companion A. Reviewer chains that span many files + many passes decay super-linearly with duration (2603.29231 [LB-75%]). Measure pass^k not pass@1 for multi-file reviews; stratify eval by MR size (already done) *and* by trajectory length.
- **Backtesting infrastructure gap (P1-5) is more urgent than it reads.** Wiese PLOS ONE (Feb 2026 [LB-85%]) measured judge drift formally for the first time: uncalibrated Kendall's τ = 0.38–0.52 (volatile) vs. Bradley-Terry-corrected τ = 0.59–0.68 (stable). Without continuous backtesting, you won't detect when the reviewer silently shifts on model updates. Recommended: adopt the 240-prompt fixed bank methodology + PELT/MBIC change-point detection.

---

### 13. Agentic SDLC Planning System

**What it is:** Multi-agent system for upstream SDLC work (planning, architecture, requirements). No code yet; research-phase complete. The framework's most useful contribution here is probably the eval design itself, because the project summary explicitly flags evaluation as the biggest unsolved piece.

**Load-bearing axes:**

- **Output shape** — Generation (written artifacts: stories, architecture docs, estimates). Trajectory (multi-agent collaboration process). Decision (routing, consensus, disagreement resolution).
- **Truth regime** — Reference-free for most outputs. "Did this agent produce a good user story" has no gold answer. Silver at best (expert rating against a rubric). Gold exists only for narrow tasks like estimation accuracy, which *can* be ground-truthed against actuals — and estimation calibration is therefore the highest-leverage sub-eval.
- **Truth-proxy quality** — The estimation feedback loop is where truth-proxy quality becomes existential: the system's own past estimates become training signal for future estimates. Without careful instrumentation, drift is inevitable. The original summary flagged this ("memory self-degradation in estimation loops") as essential; framework says: this is a specific kind of truth-proxy degradation where the proxy *is* the system's prior output.
- **Baseline** — Critical and underspecified. The baseline is "how POs and architects currently plan without the system." This requires:
  - Historical planning artifacts (stories written by humans, architectural decisions made by humans)
  - Rating these by the same rubric the system's outputs will be rated by
  - Comparing system vs. human outputs blinded
  Without this, "the agents produce good outputs" is unfalsifiable.
- **Failure-cost asymmetry** — Variable by workflow:
  - Story splitting: FP (over-split) wastes a little time; FN (under-split, stories too big) causes downstream delivery pain. Asymmetric toward thoroughness.
  - Estimation: systematic under-estimation is worse than over (commitments miss deadlines); calibration more than point accuracy.
  - Architecture decisions: FN (missed risk) >> FP (flagged non-risk). This is the code review pattern again.
- **Labeler economics** — Very high. Rubric-based expert ratings on open-ended outputs. Inter-rater agreement will be lower than for classification tasks. IAA ceiling will be meaningful (probably ~0.6-0.7 for rubric ratings on open-ended artifacts).
- **Measurement tractability** — Low measurability (open-ended outputs), low generalizability (bespoke to this system + domain). This is the hardest-to-eval of the flagships.

**The actual eval (proposed, because nothing exists yet):**

*Narrow sub-eval: estimation calibration.* Track predicted-vs-actual for estimates over time. This is the only part with crisp ground truth. Report calibration error, Brier score. Critically: watch for drift as the system's own estimates become inputs.

*Narrow sub-eval: story splitting.* Historical epic→stories decompositions as training data *and* held-out eval. "Given this epic, did the system produce decomposition similar to what humans produced?" Silver truth from historical data. Because story splitting is called out as novel contribution territory, this eval is also research contribution.

*Broad sub-eval: rubric-based rating.* For each artifact type (story, arch doc, decision doc), a rubric is built with ~5-8 dimensions. Expert raters score system outputs and human baseline outputs blinded. Compare distributions. Report both aggregate scores and per-dimension breakdowns.

*Trajectory sub-eval:* For multi-agent workflows, record trajectories. For a sample, expert reviewer judges: did agents collaborate effectively, were disagreements resolved well, was the process faster or slower than human-only. This is where the iReDev vs. strong-single-agent question gets tested empirically.

*Adversarial eval:* Cases designed to probe specific failure modes from MAST taxonomy. This is the "MAST pre-mortem" the original summary flagged as essential. Framework specifics: this is distribution-shape axis applied to known-adversarial clusters.

**Sub-pattern (estimation as the only classification-shaped sub-eval):** For estimation bucketed into size classes (XS/S/M/L/XL), confusion matrix of predicted vs. actual class. Calibration check: does "M" predicted actually map to M-sized actuals.

**The central eval question:** Does this system make the 14-person team's planning process *better or faster*, measurably, relative to the current process? If the answer is "roughly the same, but more fun to use," that's not a ship criterion. The baseline comparison is the hard ask.

**What was underspecified in the original summary:** The evaluation baseline. The summary identifies it as "arguably the most valuable unsolved piece" and framework agrees. Stage 0 here is "get the human-written planning artifacts and rate them" — exactly parallel to the RAG diagnostic's Stage 0 ("get the gold labels"). Both flagships need to build the ground-truth substrate before they can build on top.

**v1.1 research updates (Feb–Apr 2026 incorporations):**

- **Reliability engineering framing is load-bearing here — see Companion A.** Agentic SDLC is a long-horizon multi-agent system; accuracy-centric eval is insufficient. "Beyond pass@1" (2603.29231 [LB-75%]) demonstrates reliability decays super-linearly with task duration across 23,392 episodes; this is *the* dominant failure mode for long-horizon agents. Measure pass^k not pass@1. Include fault injection (timeouts, rate limits, schema drift) in CI. Stratify eval by trajectory length.
- **Memory system evaluation stack** (for the "Intelligent Decay" mechanism flagged in the original summary):
  - **MemoryAgentBench (2507.05257 v3 Mar 2026 [LB-70%])** is the paper to build around. Four competencies framework: accurate retrieval, test-time learning, long-range understanding, **selective forgetting**. Selective forgetting is the conspicuous failure mode across MemGPT, Mem0, Cognee, Zep, MIRIX, MemoryLLM, M+.
  - **LoCoMo-Plus (2602.10715 [LB-65%], Feb 2026)** adds cue-trigger constraint-consistency scenarios — memory as implicit constraint rather than factual recall. Exactly the planner feedback-loop shape.
  - **ICRH (in-context reward hacking)** [IL-80%] is the named failure mode for planner outputs becoming future memories that subtly optimize a misaligned objective over cycles. Requires multi-cycle stress-testing. No canonical benchmark exists — run your own multi-cycle stress runs.
  - **Critical caveat:** LoCoMo has documented ground-truth errors (~99 items per dial481 audit; Category 5 unscorable ~23%) [LB-75%]. ATANT v1.1 (2604.10981 [LB-65%]) shows none of the popular memory benchmarks actually measure *continuity*. Treat published memory benchmark numbers as suggestive. Combine MemoryAgentBench + LoCoMo-Plus + your own ICRH multi-cycle stress; don't trust any single published number.
- **Stage 0 for planning artifacts — use Adjudicator pattern.** For building a gold eval set from historical Jira epics/stories/decisions, adapt the Adjudicator architecture (2512.13704 [LB-65%]): dynamic KG per item (text + metadata + history) + multi-persona LLM council (Policy Expert + Contextual Analyst + Skeptical Adjudicator) + voting + KG-override for structural errors. Achieved 0.99 F1 vs 0.48 single-LLM baseline on Mozilla Bugzilla (100K bug reports) — directly analogous to your historical planning corpus.
- **Retrospective root-cause labeling has a known ceiling.** Roy et al. (FSE 2024, Microsoft, 2403.04123 [IL-85%] [MG-CAVEAT — pre-June 2025; ReAct-specific failure-mode characterization, but the underlying "ticket text alone is insufficient" finding is robust across model generations and domain studies]): 66% of ReAct RCA failures are due to insufficient information in the ticket itself. When retrospectively labeling planning decisions as "what should have been decided," budget for augmented context — KB articles, similar-historical-incident retrieval, stakeholder interviews. Don't expect clean labels from ticket text alone.
- **Rubric design: use 4–5 level ordinals across the board.** (2601.03444 [LB-80%]): 0–5 scale yields strongest human–LLM alignment; 0–10 weakest. For artifact rubrics (story quality, arch doc quality, decision doc quality), resist 10-point numeric scales.
- **Planning-agent trajectory eval** — see TruLens 2.6's Agent's GPA (Feb 2026 [LB-70%], benchmarked to cover 95% of errors in TRAIL dataset) for purpose-built plan-alignment evaluation (Companion B for tooling). Evaluates alignment of Goal, Plan, Actions.
- **Active testing for planning eval set construction.** GAT (2603.19264 [LB-70%]) reports 40% estimation-error reduction vs random sampling. Active Evaluation Acquisition (ICML 2025 [LB-75%]) reports ~90% cost reduction. Fisher-information-based acquisition, not uncertainty sampling. Worth it for expensive rubric-rated eval sets where each item costs significant expert time.
- **Estimation calibration feedback-loop specifically (ICRH instance):** multi-cycle stress test is essential. Simulate 3+ estimation cycles where the system's own past estimates become inputs. Measure drift toward prior predictions vs. ground-truth actuals. Report calibration error over cycles, not just at a point in time. This directly addresses "memory self-degradation in estimation loops" that the original summary flagged. [IL-85% — mechanism robust, specific protocol untested]
- **Arm-dependent bias impossibility result applies to multi-agent variant comparison.** (2601.21471 [LB-75%]): proxy-only comparison of agent architectures is information-theoretically impossible when variants have differential failure modes. When evaluating iReDev vs. strong-single-agent vs. MAAD architectures, always include human audits. You cannot audit exclusively via the system's own signals.

---

### 14. Chunking Experiment (code review context preprocessing)

**What it is:** The 3-5 day experiment in the code review project testing chunking strategies at different MR sizes. This is more of a self-contained eval than a full system, which is why it deserves its own profile — it shows how a focused experiment uses the framework.

**Load-bearing axes:**

- **Output shape** — Intermediate (chunks) feeding downstream (recall on defect detection). This is extrinsic eval.
- **Baseline** — Three natural baselines:
  - No chunking (feed whole MR as single context): establishes whether chunking is needed at all
  - Fixed-size chunking (200 LOC, 400 LOC, 800 LOC): establishes whether *smart* chunking beats naive
  - Current production chunking: establishes whether the experiment improves on shipping
- **Distribution shape** — The experiment's whole point is that MR size distribution matters. Uniform sampling across MR sizes would miss the 301-600 LOC sweet spot. The distribution of the eval set *must* cover the size range the experiment targets.
- **Granularity need** — Slice by MR size is non-negotiable; that's the experiment. Slice by defect type is a bonus that might reveal interactions.
- **Measurement tractability** — High measurability (recall is crisp given labeled defects), low generalizability (this specific experimental design is bespoke).

**The actual eval:**

Pairwise comparison holding everything constant except chunking strategy:
- Same model, same prompt, same tools, same evaluation set
- Vary chunking strategy across (no chunk, fixed-100, fixed-200, fixed-400, fixed-800, semantic-chunked, current-production)
- Report recall@defect, precision@finding, cost (tokens, time)
- Slice by MR size bin

Secondary analysis:
- At what MR size does chunking start to help?
- At what MR size does chunking start to hurt?
- What's the cost-benefit tradeoff? (Chunking increases tokens but may increase recall)

**The thing this experiment does right:** It's extrinsic (recall is the outcome metric), it has multiple baselines, and it's sliced on the dimension of interest. The framework affirms the experimental design; mostly this profile is an object lesson in what a good focused eval looks like.

**The cross-connection to Bedrock:** The chunking experiment's results feed Bedrock migration decisions. If chunking strategy matters differently under Bedrock's constraints, the experiment needs to be rerun post-migration. This is the "temporal regime" axis applied to infrastructure changes, not just model updates.

---

## Tier 3 synthesis

Patterns across flagship tier:

1. **All eleven axes become load-bearing.** Unlike commodity (4-5 load-bearing per profile) and middle tier (5-6), flagship profiles exercise nearly every axis. This is diagnostic: when all axes matter, the system is genuinely complex and the eval has to be correspondingly thorough.

2. **Stage 0 is the work.** Two of three full-system flagships (RAG diagnostic, agentic SDLC) have "build the ground-truth substrate" as the critical path item. The code review agent already has it via CVE benchmarks, which is why it's further along. The pattern: flagship eval is 70% getting labeled data, 30% everything else.

3. **Baseline is the ship criterion.** Human baseline, current-process baseline, strong-simple baseline. The RAG diagnostic's baseline is "senior engineer with Cmd-F." The agentic SDLC's baseline is "current PO+architect process." Without these, the system can't show it's worth shipping.

4. **Truth-proxy quality gaps become the most important eval insights.** Category D in code review, resolution ambiguity in RAG, estimation feedback loop in agentic SDLC. Each is a specific documented way the proxy differs from truth, and each one's documentation is what makes the reported metrics trustworthy rather than aspirational.

5. **Commodity and middle-tier patterns reuse heavily.** The flagship evals aren't starting from scratch — they compose classifier eval (tier 2) + judge eval (tier 2) + trajectory eval (tier 2) + golden-set regression (tier 1) into system-scale machinery. This is the framework's biggest practical payoff: a flagship eval is mostly an *assembly* of tier-1 and tier-2 machinery, plus bespoke Stage 0 ground truth.

---


---

## Tier 4: Edge Profiles

Two instantiations that didn't fit cleanly into commodity/middle/flagship but are important enough to include.

### 15. Narrow General Reasoning

**What it is:** Math, logic, multi-hop inference on clean inputs. GSM8K, MATH, BBH, ARC-style tasks. The clean exemplar of high-measurability/high-generalizability eval — which is why it's included. Router-like decisions live underneath as a sub-case.

**Load-bearing axes:**

- **Output shape** — Classification in disguise. "What's 47 × 23" has a right answer; the eval checks whether the model produced it. The twist: reasoning chain quality sometimes matters independently of final-answer correctness (partial credit for showing work, or penalty for getting right answer via wrong reasoning).
- **Truth regime** — Gold, reliably. This is the regime's distinguishing feature and why benchmarks here are so reusable.
- **Measurement tractability** — High measurability, high generalizability. Benchmarks reuse across model versions, across teams, across years. This corner of the eval space is as "solved" as eval gets.
- **Distribution shape** — Benchmark-specific, but often adversarial or difficulty-stratified by design. Modern benchmarks (BBH, ARC-AGI) deliberately include problems that probe specific reasoning failure modes.
- **Temporal regime** — Static benchmarks with a known shelf life. GSM8K was saturated within years; MATH faces the same trajectory. Eval requires rotation to new benchmarks as old ones get memorized into training data.

**The actual eval:**

Standard benchmark stack. Run the model, check answer correctness, report pass rate. Optionally: score reasoning chains with rubric or with LLM-judge. For the partial-credit variant: sub-score intermediate steps.

**Sub-pattern (binary correct/incorrect):** Trivial TP/TN; FP and FN collapse to "wrong answer" without directional cost asymmetry (most benchmarks score all wrong answers equally). The confusion matrix sub-pattern is mostly N/A here — this is one of the rare cases where accuracy is actually the right headline metric.

**The thing most teams get wrong:** Treating benchmark performance as proxy for capability in production tasks. A model that's 90% on GSM8K isn't necessarily 90% on your domain's reasoning tasks. The high generalizability of benchmark *machinery* doesn't mean benchmark *results* generalize.

**Why this profile exists:** It's the corner case that illustrates what eval looks like when all the normally-hard axes are easy. Every other instantiation in this framework has at least one load-bearing axis with thorny tradeoffs. Narrow general reasoning mostly doesn't. If your eval shape *isn't* this shape, you can't borrow this tier's solutions directly — but knowing this corner exists helps calibrate what "hard eval" actually means elsewhere.

**Router-as-sub-case:** A router deciding "should I use the cheap model or the expensive model for this query" is reasoning-about-queries. The eval is classification (right routing decision vs. wrong) weighted by cost of each error cell (unnecessary-expensive-call vs. cheap-model-fails-and-has-to-retry). Borrows the classifier-tier eval pattern, with reasoning-tier benchmark rigor for what constitutes "right" routing.

---

### 16. Document / Artifact Generators

**What it is:** Composite systems that produce shippable artifacts — pptx decks, generated code files, architectural docs, reports. Not just text generation: combines prompts + data analysis + tool use (file creation, formatting, validation) into a deliverable. Includes Wesley's GVP deck build, the code review agent's patch proposer, the canvas-design/algorithmic-art skills when they produce files.

**Load-bearing axes:**

- **Output shape** — Artifact, which splits into three separable quality dimensions:
  1. *Structural validity:* Does the file parse, open, render? A .pptx that won't open is broken regardless of content.
  2. *Content correctness:* Are the facts/numbers/claims right? This is where the composite nature bites — it's downstream of data analysis, retrieval, reasoning.
  3. *Ship-readiness:* Would a human send this without edits? This is the acceptance metric and the hardest to automate.
- **Truth regime** — Mixed by dimension. Structural validity is gold-checkable (parsers either accept or don't). Content correctness is silver-to-gold depending on data source. Ship-readiness is reference-free and typically rubric-based.
- **Baseline** — Human-authored version of the same artifact. "Would the human spend the same time authoring this?" is the implicit comparison. A generator that produces a pptx in 30 seconds that needs 2 hours of human editing is worse than a human authoring from scratch in 90 minutes.
- **Failure-cost asymmetry** — Structural failures are binary and cheap to detect. Content errors are the dangerous ones — a deck that looks professional but has a wrong number in front of a VP damages credibility more than no deck at all. "Looks good, isn't true" is the failure mode most worth testing against.
- **Measurement tractability** — Structural: high measurability. Content: variable. Ship-readiness: low measurability, low generalizability (what ships depends heavily on context, audience, stakes). This is a composite generator *across measurement tractability levels* — the eval needs separate machinery for each.

**The actual eval (three layers):**

*Layer 1: Structural validation (automatable).* Does the file parse? Pass format-specific linters? Meet structural constraints (slide count, section presence, required metadata)? This layer catches catastrophic failures cheaply.

*Layer 2: Content verification (semi-automated).* Are the facts in the artifact traceable to source data? For a data-driven deck: every number should be verifiable against its source. Automated cross-checking where possible; LLM-judge + human spot check where not.

*Layer 3: Ship-readiness review (human).* For high-stakes artifacts, blinded human review: would you send this? Score on a rubric (polish, clarity, persuasiveness, fitness for audience). Compare to human-authored control.

**Sub-pattern:** This is a composite where each layer has its own eval shape. Structural = classification (valid/invalid). Content = fact-verification (classification per fact). Ship-readiness = rating (ordinal or binary). The confusion matrix pattern applies at the content layer but not meaningfully at the other two.

**The thing most teams get wrong:** Skipping Layer 2 because it's tedious. Layer 1 passes (file opens), Layer 3 looks good (human rater approves the vibe), and a wrong number ships into a VP deck. The GVP deck build is exactly where this risk lives — Wesley's documented preference for "honest uncertainty over polished but hollow confidence" is the cultural version of "make Layer 2 non-negotiable."

**The Wesley-specific framing:** His "fabricated ROI numbers" concern and the "baselines must be labeled" tension in the ops deck are both Layer 2 problems. The artifact generator produces content that *could* contain either — fabricated numbers, mislabeled baselines — and Layer 2 is the eval stage that catches these before they ship. If an LLM-powered deck-builder skill is used, it needs Layer 2 discipline built in, not bolted on.

**Cross-reference:** The pptx skill, canvas-design skill, and algorithmic-art skill in the available-skills list all produce artifacts and all would benefit from this three-layer pattern. Currently these skills have their own quality checks (follow the skill, produce the output) but not formal layered eval.

---

## Tier 4 synthesis

The two edge profiles serve different functions:

- Narrow general reasoning is the "easy mode" reference — shows what eval looks like when the axes are kind.
- Document generators are the "composite across measurement tractability" case — shows what happens when a single instantiation spans multiple eval shapes and needs layered machinery.

Together they bracket the framework. If your eval problem is simpler than narrow general reasoning, you're probably over-engineering. If it's harder than document generators' full three-layer stack, you've got a flagship.

---

## Cross-Cutting Concerns

Two concerns emerged repeatedly across profiles that don't fit cleanly into a single axis. Each gets its own section because they apply *across* the framework, not to specific instantiations.

### C1: Model-Update Regression

**What it is:** When the model underneath any LLM-powered system updates (Sonnet 4.5 → 4.6 → 4.7, Opus 4.6 → 4.7, etc.), behavior shifts in ways that can silently break:
- Prompts that relied on specific model quirks
- Steering files calibrated to the old model's defaults
- Evaluators whose bias patterns change across model versions
- Agent loops whose tool-use patterns shift
- Memory systems whose retrieval quality depends on model-specific embedding or reasoning behavior

The naive assumption — "newer model is better, so behavior should be at-least-as-good" — is wrong often enough to cause real damage. Better on average doesn't mean better on your specific eval slice.

**Where it showed up in profiles:**
- Steering (tier 1): explicit — "steering can rot silently when the model updates"
- LLM-as-judge (tier 2): "periodic re-validation on model updates"
- Code review agent (tier 3): "no continuous regression tracking across model versions yet" — flagged as a gap
- Memory systems (tier 2): model-specific embedding/reasoning behavior
- Agents (tier 2): tool-use patterns shift

Essentially everywhere. The commodity tier is most exposed because golden-set regressions are the cheapest check and most teams don't run them.

**The eval discipline:**

Every eval in this framework should be re-runnable on model version change, not just content change. Three practical moves:

1. *Tag eval runs with model version.* Every benchmark result should record which model it ran against. Comparing across runs without this is meaningless.
2. *Run eval on version bump, not on content change alone.* "We upgraded to Sonnet 4.7" should trigger the eval suite, same as "we changed the prompt." Most teams do the second but not the first.
3. *Report deltas, not just absolutes.* "Recall went from 83% to 79% on model upgrade" is the finding. "Recall is 79%" obscures it.

**The cultural piece:** This is one of those concerns that reads as fussy overhead until it bites you, and then it reads as common sense in hindsight. Teams that have been burned once tend to build this discipline; teams that haven't, don't. The framework's position: build it before you get burned. The cost is low (mostly tooling), the cost of not having it is a production regression you can't explain.

**Connection to Wesley's world:** The feature flag architecture work with its three-layer fallback has a conceptual parallel here — model updates are to eval what architectural changes are to feature flags. You want graceful handling, not silent failure. Both cultures are "assume the thing you're depending on will change and build eval/fallback for that case."

---

### C2: Judging the Judge (Recursive Evaluation)

**What it is:** When LLM-as-judge is used to evaluate LLM outputs (increasingly the default for reference-free evals), the judge itself is an LLM whose quality must be evaluated. Without this, the eval stack is built on untrustworthy ground — you don't know whether "the system improved" or "the judge got more lenient."

**Where it showed up in profiles:**
- LLM-as-judge profile (tier 2): the profile is entirely about this
- Code review agent (tier 3): the orchestrator's verification pass judges the reviewer — explicit "judge evaluating a judge, neither calibrated against human expert ratings"
- Agents (tier 2): trajectory eval via LLM-judge requires the judge to be calibrated
- RAG diagnostic (tier 3): the confidence scorer is judge-shaped
- Agentic SDLC (tier 3): rubric-based rating will almost certainly use LLM-judge assistance for scale

Every middle and flagship tier profile touches this. It's recursive because the discipline of evaluating the judge is itself eval work that needs to be done once per judge, and updated as the judge's underlying model updates (connecting to C1).

**The eval discipline:**

Three moves, in order of increasing cost:

1. *Establish human IAA ceiling first.* Have 2-3 human raters label a sample. Measure their agreement with each other. This is the ceiling the judge can aspire to — reporting judge quality above this ceiling is a red flag (overfitting to a specific rater's bias).

2. *Measure judge-human agreement against the ceiling.* Cohen's kappa, Krippendorff's alpha, or for scalar scores Spearman correlation. Report as a fraction of ceiling, not absolute: "0.75 agreement against 0.82 IAA ceiling" is meaningful; "0.75 agreement" alone is not.

3. *Run the bias battery.* Position bias, length bias, self-preference, style bias. These are *known* to exist by default in LLM judges. Measure how much judge ratings shift under controlled manipulations (swap position, add filler, present own-family vs. cross-family). High shift = high bias = mitigation required (randomization, normalization, cross-family judging).

**The recursion problem explicitly:** Evaluating the judge requires humans. Humans are inconsistent. Human IAA caps what the judge can achieve. This isn't solvable — it's a fundamental ceiling — but it's manageable:
- Pick raters with domain expertise (higher IAA than random raters)
- Use rubrics rather than holistic ratings (higher IAA than subjective scoring)
- Reconcile rater disagreements (raises effective IAA by resolving ambiguity)

**Connection to Wesley's world:** The code review agent's multi-pass design has a version of this already — the verification pass functions as a judge of the reviewer. Framework says: formalize this. Calibrate the verification pass against human expert ratings on a sample. Without that, "the verification pass caught X issues" is a claim without ground truth.

Similarly, any work on the RAG diagnostic's confidence scorer should treat it as a judge — it's producing a calibrated judgment about whether to answer. Evaluating its calibration is judging-the-judge.

---

### How C1 and C2 interact

They compound. A judge calibrated against humans on model version N becomes uncalibrated on model version N+1. If you only run C1 discipline (version tagging) without C2 discipline (judge calibration), you see that "eval scores dropped on model upgrade" but don't know if the system got worse or the judge got stricter. If you run C2 without C1, you don't detect version-related judge drift.

Both disciplines together create the minimum trustworthy eval infrastructure: versioned runs + calibrated judges + bias checks rerun on upgrades. This is what distinguishes "we have evals" (common) from "we have trustworthy evals" (rare).

---

### C3: Reliability Engineering Framing (Companion A reference)

**What it is:** For agents and long-horizon systems, accuracy-centric eval is insufficient. The field as of Q1 2026 has imported safety-critical engineering vocabulary — MTBF, pass^k consistency, reliability surfaces, fault injection, graceful degradation — as a co-equal framing that runs alongside classical eval rather than replacing it.

**Why this is a cross-cutting concern, not a profile addition:** It applies across multiple instantiations (agents in tier 2, agentic SDLC in tier 3, multi-pass code review reviewer in tier 3) and introduces vocabulary and metrics that don't map cleanly onto the 11 axes. Pass^k consistency is not just "distribution shape" — it's a fundamentally different question. Fault injection is not just "adversarial cluster" — it's a systems discipline.

**Minimum discipline to adopt even without full Companion A:**
1. **Measure pass^k, not pass@1, for agent systems.** "Reliability decays super-linearly with task duration across 23,392 episodes" (2603.29231 [LB-75%]) means single-run success rate over-estimates production reliability.
2. **Run fault injection in CI.** Timeouts, rate limits, schema drift, tool failures. ReliabilityBench (2601.06112 [LB-65%]) provides chaos-engineering test recipes.
3. **Stratify eval by task duration/trajectory length.** Long trajectories have qualitatively different failure modes than short ones.

**Full treatment:** Companion A — Reliability Engineering Framing. Includes ReliabilityBench methodology, IEC 62279 grounding, MTBF for agents, fault injection recipes, graceful-degradation patterns, and how reliability engineering framing interacts with the 11 axes of this main framework.

---

### How C1, C2, and C3 interact

C1 and C2 compound as described above. C3 adds another layer: reliability engineering framing cares about *sustained behavior under stress*, which is where judge drift (C2 failure) and model-update regression (C1 failure) manifest operationally. A system that tests well on a static benchmark may fail under fault injection because the judge was calibrated on clean inputs; or because the model version changed and pass^k dropped 15 points at trajectory length 20+.

Three disciplines together — versioned runs (C1) + calibrated judges (C2) + reliability surface measurements including fault injection (C3) — form the minimum eval infrastructure for agent systems in production. Commodity and middle-tier components need C1 + C2. Agents and flagships need all three.

---

*End of main framework document. See Companion A (Reliability Engineering), Companion B (Tooling April 2026), Companion C (Frontier Watch List).*

---

## References (Consolidated, Classified)

Citations grouped by classification confidence. arXiv IDs in five-digit YYMM.NNNNN format. Use these for semantic-scholar follow-up searches.

### Load-bearing, high confidence ([LB-95%], [LB-90%])

- **Hardt et al. (2410.13341)** — Debiased Tail Bounds for LLM Judges. Theoretical ceiling: weak judge → at most 2× label savings. Foundational for C2 economics.
- **Chen et al. (2601.05420)** — PPI++ for LLM Evaluation. Statistical skeleton for proxy-bounded metrics.
- **Lee et al. (2511.21140)** — Rogan-Gladen Re-grounded for LLM-Era. Lang-Reiczigel CI formulation. Core estimator paper.
- **Natarajan et al. NeurIPS 2013** — Learning with Noisy Labels. Unbiased loss bound. Foundational.
- **Angelopoulos et al. 2022/2024 — Conformal Risk Control** (arXiv:2208.02814; ICLR 2024). Foundational for abstention threshold calibration.
- **Traub et al. NeurIPS 2024 (2407.01032)** — AUGRC. Replaces AURC due to monotonicity failures.

### Load-bearing, moderate confidence ([LB-85%], [LB-80%], [LB-75%])

- **Wiese PLOS ONE Feb 2026** — Calibration Drift Measurement. 10-week tracking, 3 model families. Best methodology for judge drift monitoring.
- **Feng et al. (2601.20913)** — Noisy-but-Valid + EIF. Companion to Chen for transport-audit.
- **MacAvaney et al. (2204.12852)** — IR Survivorship Methodology on MS MARCO. Pre-2025 but mechanism portable.
- **Madhusudhan COLING 2025 (2407.16221)** — AUCM. Practitioner-facing abstention metric.
- **(2601.03444)** — Scale Mechanics for LLM Grading. 0-5 vs 0-10 alignment finding.
- **(2601.01522)** — Bayesian Orchestration. Threshold-based classification formally inadequate under asymmetric costs.
- **CodeJudgeBench (2507.10535)** — Reasoning-judge benchmark for code. Validates pair-wise > point-wise.
- **(2603.29231)** — Beyond pass@1. 23,392 episodes; super-linear reliability decay with task duration.
- **AbstentionBench (2506.09038)** — 20 datasets, 35k queries. Reference implementation for abstention metrics.
- **Judge's Verdict (2510.09738)** — κ heuristics for response-pair judging.
- **Preference Leakage ICLR 2026** — Same-family judge contamination.
- **Arm-Dependent Bias (2601.21471)** — Impossibility result for proxy-only A/B comparison.
- **(2603.19264)** — GAT active testing. 40% estimation error reduction.
- **AXIOM (2512.20159)** — Complex agentic judges underperform on ordinal code quality.

### Load-bearing, lower confidence ([LB-70%], [LB-65%])

- **CyclicJudge (2603.01865)** — Round-robin jury at single-judge cost. Compelling but single paper.
- **Adjudicator (2512.13704)** — KG-informed council for noisy-label correction. 0.99 F1 on Mozilla Bugzilla.
- **MemoryAgentBench (2507.05257 v3)** — Four competencies framework. LoCoMo audit caveat applies.
- **LoCoMo-Plus (2602.10715)** — Cue-trigger constraint-consistency.
- **ATANT v1.1 (2604.10981)** — Memory benchmark continuity audit.
- **JudgeBiasBench (2603.08091)** — Bias taxonomy + injection pipeline.
- **Judge Reliability Harness (2603.05399)** — Ordinal-grading stress tests.
- **CISC ACL 2025 / SECL (2604.09624)** — P(True) ordering. Strong on Phi/Gemma; less validated on frontier.
- **Phillips (2603.21172)** — Entropy-signal frontier-model caveat.
- **ReliabilityBench (2601.06112)** — Reliability surface R(k, ε, λ). Single foundational paper.
- **Active Evaluation Acquisition ICML 2025** — ~90% cost reduction. Domain-dependent.
- **TruLens 2.6 Agent's GPA Feb 2026** — TRAIL coverage benchmark.
- **(2511.16708)** — CodeX-Verify submodularity proof for decorrelated agents (referenced in code review project history).
- **UA-Bench (2604.17293)** — Data vs model uncertainty distinction.
- **MedAbstain (2601.12471)** — Adversarial + CP for medical abstention.
- **Sage (2512.16041)** — Panel-judge gain ceiling (+15%).
- **CJE (2512.11150)** — Calibrated judge eval transport audit.
- **(2507.16587)** — Sub-7B judge validity rate on code.
- **KnowNo template** — Ren et al. CoRL 2023 (paper title: "Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners"; arXiv:2307.01928). 4-option MCQA-with-abstain pattern. CoRL 2023 Best Student Paper. Widely cited (>500). Adopted on simple QA originally; needs validation on three-way classification.

### Illustrative, high confidence ([IL-90%], [IL-85%], [IL-80%])

- **Roy et al. FSE 2024 (2403.04123)** — Microsoft ReAct RCA failures, 66% from insufficient ticket info. Pre-June 2025 but underlying finding robust.
- **ICRH (in-context reward hacking)** — Mechanism named in literature. Specific instances vary; mechanism real.

### Illustrative, lower confidence ([IL-65%], [IL-60%])

- **Joren et al. ICLR 2025 (2411.06037)** — RAG abstention collapse. **Pre-June 2025 caveat applies; mechanism likely real, magnitude likely smaller on current frontier models.** See in-line caveat in RAG diagnostic profile.
- **(2512.01232)** — Reasoning-effort non-monotonicity on code judgment. Single-model finding.
- **PoLL (Verga 2024)** — 3-judge panel cost claim. Pre-June 2025 pricing dependence.
- **ChatEval** — Adversarial debate hurts reliability. Single paper, contested.

### Pre-June 2025 with Model-Generation Caveats ([MG-CAVEAT])

These findings have specific magnitude/numeric claims dependent on model generation. Mechanisms are likely portable; specific numbers should be re-measured on your target model:

- **Joren et al. ICLR 2025 (2411.06037)** — Abstention collapse magnitude
- **PoLL (Verga 2024)** — Specific cost ratios
- **MacAvaney et al. (2204.12852)** — Specific MS MARCO results (methodology portable)
- **Roy et al. FSE 2024 (2403.04123)** — Specific 66% number (mechanism robust)

### Pre-2026 Lineage (verified April 2026)

Each Q1 2026 citation in the framework builds on established lineages. This section surfaces those foundations — verified bibliographic details from a research-agent verification pass. **Most of these foundations are widely cited (>500–1000 citations);** the lineages are well-grounded, not single-paper results dressed up. The implication for confidence calibration: many [LB-65%] to [LB-75%] Q1 2026 citations effectively read as "latest layer of widely-validated lineage" rather than "single new paper."

#### Statistical proxy-correction lineage (foundations for principle 4)

- **Rogan & Gladen 1978**, "Estimating prevalence from the results of a screening test," *American Journal of Epidemiology* 107(1):71–76. DOI 10.1093/oxfordjournals.aje.a112510. Widely cited (>2,000). The classical foundation for proxy correction.
- **Lang & Reiczigel 2014**, "Confidence limits for prevalence of disease adjusted for estimated sensitivity and specificity," *Preventive Veterinary Medicine* 113(1):13–22. Moderately cited (~150–250). Source of the Lang-Reiczigel CI correction used in v1.1.
- **Angelopoulos et al. 2023**, "Prediction-Powered Inference," *Science* 382(6671):669–674; arXiv:2301.09633. Widely cited (>1,000). Foundational PPI paper. Lineage: PPI → PPI++ (Chen et al. 2601.05420).
- **Boyeau et al. 2024**, "AutoEval Done Right: Using Synthetic Data for Model Evaluation," arXiv:2403.07008; ICML 2025. New/niche (~30–50). Synthetic-data + human-validated subset pattern.
- **Saad-Falcon et al. 2024**, "ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems," NAACL-HLT 2024 pp. 338–354; arXiv:2311.09476. Widely cited (>400). Applied the pattern to RAG.
- **Zrnic & Candès 2024**, "Active Statistical Inference," arXiv:2403.03208; ICML 2024. Moderately cited (~80–120). Active-testing-for-eval lineage. *(Substitute for the misattributed "Eyuboglu" citation — Eyuboglu does not have an active-inference-for-eval paper.)*
- **Kossen et al. 2021**, "Active Testing: Sample-Efficient Model Evaluation," arXiv:2103.05331; ICML 2021. Direct precursor to GAT and active-testing-for-eval thread.

**Lineage implication:** Chen et al. 2601.05420 (PPI++ for LLM Eval) sits atop a 4-decade lineage. Confidence on [LB-90%] is well-justified.

#### LLM-as-judge bias lineage (foundations for the v1.1 judge profile)

- **Zheng et al. 2023**, "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena," NeurIPS 2023 Datasets & Benchmarks Track; arXiv:2306.05685. Widely cited (~6,000+). Foundational paper documenting position bias and self-preference.
- **Wang et al. 2024**, "Large Language Models are not Fair Evaluators," ACL 2024 Long Papers pp. 9440–9450; arXiv:2305.17926. Widely cited (>1,500). Position bias quantification. *(Verified venue: ACL 2024, not pre-publication 2023.)*
- **Liu et al. 2023 (G-Eval)**, "G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment," EMNLP 2023 pp. 2511–2522; arXiv:2303.16634. Widely cited (>2,000). Early LLM-as-judge with chain-of-thought.
- **Chiang & Lee 2023**, "Can Large Language Models Be an Alternative to Human Evaluations?" ACL 2023 Long Papers pp. 15607–15631; arXiv:2305.01937. Widely cited (>1,000). Early systematic study.
- **Bavaresco et al. 2025**, "LLMs instead of Human Judges? A Large Scale Empirical Study across 20 NLP Evaluation Tasks," ACL 2025 Short Papers pp. 238–255; arXiv:2406.18403. Moderately cited (~80–150). *(Verified: ACL 2025 short, not EMNLP 2024.)*
- **Verga et al. 2024 (PoLL)**, "Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models," arXiv:2404.18796 (Cohere preprint). Moderately cited (~150–300).

**Lineage implication:** The CyclicJudge paper (2603.01865, [LB-65%]) sits atop a deep 2023–2024 lineage of jury and bias work. Effective confidence is higher than the single-paper marker suggests.

#### Selective prediction / abstention foundations (precursors to the RAG diagnostic abstention design)

- **El-Yaniv & Wiener 2010**, "On the Foundations of Noise-free Selective Classification," *JMLR* 11:1605–1641. Widely cited (>500). Classical risk-coverage curve definition.
- **Geifman & El-Yaniv 2017**, "Selective Classification for Deep Neural Networks," NeurIPS 2017 pp. 4878–4887; arXiv:1705.08500. Widely cited (>800). Bridge to deep learning.
- **Kadavath et al. 2022**, "Language Models (Mostly) Know What They Know," arXiv:2207.05221 (Anthropic technical report). Widely cited (>1,500). Introduced P(True). The lineage SECL/CISC builds on directly.
- **Ren et al. 2023 (KnowNo paper)**, "Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners," CoRL 2023 (Best Student Paper); arXiv:2307.01928. Widely cited (>500). 4-option MCQA-with-abstain pattern. *(Title verified: "KnowNo" is the framework name only.)*
- **Manakul et al. 2023 (SelfCheckGPT)**, EMNLP 2023 Main pp. 9004–9017; arXiv:2303.08896. Widely cited (>1,500). Foundational hallucination-detection / abstention.
- **Abbasi-Yadkori et al. 2024**, "To Believe or Not to Believe Your LLM," NeurIPS 2024; arXiv:2406.02543. Moderately cited (~80–150). Recent LLM-specific selective prediction. *(Author name verified as hyphenated "Abbasi-Yadkori.")*

**Lineage implication:** The P(True) recommendation [LB-70%] in v1.1 is the latest layer of an Anthropic-grounded lineage going back 4 years. Effective confidence higher.

#### Conformal prediction lineage

- **Vovk, Gammerman & Shafer 2005**, *Algorithmic Learning in a Random World*, Springer 1st ed. (also 2nd ed. 2022). Foundational textbook.
- **Romano, Patterson & Candès 2019**, "Conformalized Quantile Regression," NeurIPS 2019 pp. 3538–3548; arXiv:1905.03222. Widely cited.
- **Angelopoulos & Bates 2021**, "A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification," arXiv:2107.07511; published as *Foundations and Trends in Machine Learning* 16(4):494–591 (2023). Practitioner reference.
- **Angelopoulos et al. 2022/ICLR 2024**, "Conformal Risk Control," arXiv:2208.02814. The CRC paper used in v1.1. *(Note: 2022 preprint, 2024 ICLR publication.)*

**Lineage implication:** TorchCP recommendation rests on 20-year statistical foundation, not a recent fashion.

#### Reliability engineering for ML (precursors to the agent-reliability thread in Companion A)

- **Sculley et al. 2014 (workshop)**, "Machine Learning: The High Interest Credit Card of Technical Debt," SE4ML at NIPS 2014.
- **Sculley et al. 2015 (NeurIPS)**, "Hidden Technical Debt in Machine Learning Systems," NIPS 2015 pp. 2503–2511. *(Verified distinction: 2014 workshop has different title; "Hidden Technical Debt" is the 2015 extension.)*
- **Amodei et al. 2016**, "Concrete Problems in AI Safety," arXiv:1606.06565.
- **Breck et al. 2017**, "The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction," IEEE Big Data 2017 pp. 1123–1132. DOI 10.1109/BigData.2017.8258038.
- **Ribeiro et al. 2020 (CheckList)**, ACL 2020 Best Paper pp. 4902–4912; arXiv:2005.04118.
- **Basiri et al. 2016**, "Chaos Engineering," *IEEE Software* 33(3):35–41. Distributed-systems chaos engineering foundation.

**Lineage implication — and important novelty claim verification:** None of these precursors address LLM-agent-level reliability. Sculley, Ribeiro, Breck are ML model/pipeline reliability. Amodei is classical RL agent safety, predates LLM agent paradigm. Basiri is distributed-systems reliability. **This justifies "Beyond pass@1" and "Towards a Science of AI Agent Reliability" as genuinely novel** in extending reliability engineering specifically to LLM-agent trajectories. Companion A's reliance on these Q1 2026 papers reflects a real gap in prior work, not a missed lineage.

#### Long-horizon agent evaluation lineage (foundations for trajectory eval and pass^k)

- **Yao et al. 2023 (ReAct)**, ICLR 2023; arXiv:2210.03629. Widely cited (~5,000+). Foundational tool-using agents.
- **Yao et al. 2023 (Tree of Thoughts)**, NeurIPS 2023 oral; arXiv:2305.10601. Widely cited (>3,000).
- **Liu et al. 2024 (AgentBench)**, ICLR 2024; arXiv:2308.03688. Widely cited (>1,000).
- **Zhou et al. 2024 (WebArena)**, ICLR 2024; arXiv:2307.13854. Widely cited (>1,500).
- **Mialon et al. 2024 (GAIA)**, ICLR 2024; arXiv:2311.12983. Widely cited (~700–1,000+).

**Lineage implication:** The agent-evaluation thread has rich 2023–2024 foundation. "Beyond pass@1" extends it; the lineage is well-established.

#### Memory systems lineage

- **Park et al. 2023 (Generative Agents)**, UIST 2023; arXiv:2304.03442.
- **Packer et al. 2023 (MemGPT)**, arXiv:2310.08560 (preprint).
- **Maharana et al. 2024 (LoCoMo original)**, "Evaluating Very Long-Term Conversational Memory of LLM Agents," ACL 2024 Long Papers; arXiv:2402.17753.
- **Zhong et al. 2024 (MemoryBank)**, AAAI-24 38(17):19724–19731; arXiv:2305.10250.
- **Shinn et al. 2023 (Reflexion)**, NeurIPS 2023; arXiv:2303.11366. Foundational for episodic memory buffers / verbal-reflection-as-memory.
- **Wang et al. 2024 (Voyager)**, TMLR 2024; arXiv:2305.16291. Foundational for skill-library memory.
- **Zhang et al. 2024**, "A Survey on the Memory Mechanism of Large Language Model based Agents," arXiv:2404.13501.

**Lineage implication:** The memory-systems thread has substantial 2023–2024 foundation. MemoryAgentBench [LB-70%] sits atop deep prior work; effective confidence higher than single-paper marker.

#### Inter-rater agreement / ordinal metrics for LLM judges (newly surfaced)

The framework recommends "Krippendorff α with ordinal distance + quadratic-weighted κ + Kendall τ-b." A 2024–2025 lineage extends classical IRR for LLM-judge contexts:

- **Walker et al. 2025**, "LLM-as-a-Judge: Rapid Evaluation of Legal Document Recommendation for RAG," arXiv:2509.12382. Compares Krippendorff α (ordinal), Cohen κ, Spearman ρ, Kendall τ, Gwet AC2-L, AC2-Q under skewed ordinal distributions; argues weighted Gwet AC2 may outperform Krippendorff α for LLM-judge.
- **Sonkar/Shin et al. 2025**, "An Empirical Study of LLM-as-a-Judge: How Design Choices Impact Evaluation Reliability," arXiv:2506.13639.
- **"Rating Roulette" (Findings of EMNLP 2025)**, arXiv:2510.27106. Adapts α for intra-rater (self-consistency) reliability of LLM judges.
- **Guerdan et al. 2025**, "Validating LLM-as-a-Judge Systems Under Rating Indeterminacy," arXiv:2503.05965. Argues classical IRR is misapplied in LLM-judge contexts.

**Lineage implication:** This is an active research area with at least 4 papers in 2025. The framework's "report multiple ordinal metrics" recommendation is consistent with current practice but the question of *which* metric is best for LLM-judge is genuinely contested. Worth monitoring; potential Companion C item if the answer converges.

#### Prompting research foundations (under-the-surface foundations)

- **Wei et al. 2022 (Chain-of-Thought)**, NeurIPS 2022 pp. 24824–24837; arXiv:2201.11903. CoT foundation.
- **Lu et al. 2022 (Fantastically Ordered Prompts)**, ACL 2022 Outstanding Paper pp. 8086–8098; arXiv:2104.08786. Order sensitivity.
- **Sclar et al. 2024**, "Quantifying Language Models' Sensitivity to Spurious Features in Prompt Design," ICLR 2024 Poster; arXiv:2310.11324. Prompt sensitivity / format brittleness.
- **Agarwal et al. 2024**, "Many-Shot In-Context Learning," NeurIPS 2024 Spotlight; arXiv:2404.11018. *(First author verified as Agarwal, not Anil — there is a separate "Many-Shot Jailbreaking" paper by Cem Anil et al.)*

**Lineage implication:** Prompt sensitivity and format brittleness are foundational for understanding why LLM-judge calibration is non-trivial and why prompting choices matter to eval reproducibility. Implicit in v1.1's "judges have known biases" claim.

### Pattern across the citation pool

**Updated April 2026 after pre-2026 lineage verification.** The earlier pattern read "60% of citations sit in [LB-65%] to [LB-75%]" — that framing was misleading because it treated Q1 2026 papers as standalone results when they're actually the latest layer of well-established lineages. With pre-2026 lineage surfaced:

- **High-confidence load-bearing citations** cluster in: classical statistical theory (Hardt, Natarajan, Rogan-Gladen, Angelopoulos PPI/CRC), and Q1 2026 papers extending well-validated lineages (Chen et al. PPI++, Wiese drift methodology, AUGRC).
- **Moderate-confidence load-bearing citations** are mostly Q1 2026 papers that *do* sit on established lineages (CyclicJudge → 2023–2024 jury work; CodeJudgeBench → 2023–2024 LLM-judge work; MemoryAgentBench → 2023–2024 memory work). These are not single-paper claims; they're recent extensions. Effective confidence is higher than the [LB-65%]–[LB-75%] markers suggest.
- **Lower-confidence (genuinely single-paper) citations** are now visible as a smaller subset: Adjudicator architecture, ReliabilityBench, ATANT v1.1, "Towards a Science of AI Agent Reliability" — these are recent papers with thinner prior work behind them, and they should remain at moderate confidence pending replication.
- **Deliberately novel claims** — "Beyond pass@1" extends reliability engineering to LLM-agent trajectories where prior work was ML-model or distributed-systems level. The Group 5 verification confirmed this novelty claim is genuine; not a missed-lineage problem.

For semantic-scholar feeding: the highest-leverage targets remain the Q1 2026 papers that *don't* yet have follow-up work — not those well-grounded in lineage. Adjudicator (2512.13704) and ReliabilityBench (2601.06112) are top priority for replication-or-contradiction monitoring.