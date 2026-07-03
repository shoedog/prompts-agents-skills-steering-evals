# Reasoning-Capture Formats by SWE Task Type + Element-Level Evidence Triage (Pass 3, Deep-Research Extension)

## Executive summary

- **Which SWE types genuinely differ in capture shape:** Only three shapes are load-bearing. **Code review / evaluation** (criteria checklist + disconfirm-first + default-REJECT + binary verdicts) is the single best-evidenced differentiated shape. **Debugging** differs by front-loading named failure-signatures + disconfirm-first hypothesis ordering. **Design/architecture** differs by carrying rejected-alternatives-with-boundary-conditions. **Development/implementation** and **feature planning** collapse toward the shared skeleton (feature planning adds explicit decomposition + per-subtask done-checks). Evaluation largely collapses INTO the code-review shape.
- **What the evidence SETTLES (skip testing):** (1) A compact resolved plan handed from a stronger to a weaker executor helps at inference time — settled on math AND code by COPE (MBPP) and MutaGReP (repository code). (2) Compact/reusable reasoning units cut tokens/latency at inference without hurting accuracy (Metacognitive Reuse, Retrieval-of-Thought) — settled for reasoning/math. (3) Repository-overview/narrative context files do NOT reliably help and inflate cost — settled for SWE by the ETH AGENTS.md study. (4) Criteria-anchored review with a verification/filter layer works in production (BitsAI-CR, Defect-Focused Review).
- **The single most important negative:** Repository-level context files (AGENTS.md/CLAUDE.md) in the *overview/narrative* form do NOT generally improve task success and raise inference cost >20% (ETH Zurich, arXiv 2602.11988). Instructions/conventions are followed and marginally useful; narrative repository summaries are not.
- **How thin SWE-specific inference-time element evidence is:** Very thin. Outside COPE, MutaGReP, and the AGENTS.md cluster, essentially NO study isolates individual capture elements (goal restatement, invariants, rejected-alternatives, failure-signatures) for a weaker in-context code executor. Most element-triage verdicts remain extrapolated from general/math or human tiers and are flagged as such.
- **Top structural moves by weaker-executor evidence strength:** (1) Decomposition (least-to-most, plan-and-solve, COPE) — strongest, works on code. (2) Disconfirmation/competing-hypotheses (chain-of-verification, self-consistency) — strong, code-review-adjacent. (3) Abstraction-first (step-back) — strong but math/QA. (4) Multiple-attempts+aggregation (self-consistency) — robust but a RUNTIME strategy, not a capture element. (5) Prospective-failure-imagination (pre-mortem → failure-signatures) — human-strong, LLM-untested on code.

-----

## Part A: Anchor-source verification

**1. Evaluating AGENTS.md (arXiv 2602.11988, Gloaguen et al., ETH Zurich + LogicStar.ai; Feb 2026). VERIFIED — claims accurate, with sharpening.**
Domain tier: SWE. Inference-time. The paper evaluates coding agents in two settings: established SWE-bench tasks with LLM-generated context files, and a novel dataset (AGENTbench, 138 real-world Python tasks from niche repositories) with developer-committed files, across four agents (Claude 3.5 Sonnet, Codex GPT-5.2 and GPT-5.1-mini, Qwen Code) in three conditions (no file / LLM-generated / human-written). Headline: context files “do not generally improve task success rates, while increasing inference cost by over 20% on average,” holding across LLMs, agents, and both file provenances.  Behavioral trace analysis: agents follow the instructions, so they run more tests, read more files, grep more, and do more quality checks — thorough but unnecessary for the specific task.  Nuance confirmed: LLM-generated files had a marginal NEGATIVE effect on success; developer-written files gave a marginal positive gain  (~4% per secondary reporting), but both incurred the cost penalty. Instructions/conventions and non-inferable tooling commands are followed and useful; architecture overviews “do not provide effective overviews.”  This is the highest-value SWE-specific datapoint and it is confirmed.

**2. On the Impact of AGENTS.md on Efficiency (arXiv 2601.20404, Lulla et al.; Jan 2026, ICSE JAWs 2026). VERIFIED — reconciliation confirmed.**
Domain tier: SWE. Inference-time. Study of OpenAI Codex (gpt-5.2-codex) on 10 repositories / 124 PRs, paired same-task/same-repo runs with and without AGENTS.md.  Result: presence of AGENTS.md associated with **lower median runtime (Δ28.64%)** and **reduced OUTPUT token consumption (Δ16.58%)**, with comparable task completion.  Reconciliation with paper #1 confirmed: (a) this measures OUTPUT tokens only, not total (input re-read overhead per step is exactly what 2602.11988’s >20% cost figure captures); (b) the paper notes the reduction concentrates in a small number of very high-cost runs, not uniform;  (c) small-scope changes (≤100 LoC, ≤5 files), efficiency metrics only, no correctness/robustness claim. The two papers are NOT in genuine conflict: efficiency-per-completed-task vs. success-rate-and-total-cost are different axes.

**3. Metacognitive Reuse (arXiv 2509.13237, Didolkar, Ballas, Arora & Goyal — Meta / Mila / Princeton) & Retrieval-of-Thought (arXiv 2509.21743, Ahmed & Khan et al. — Univ. of Minnesota / UC Santa Cruz / Argonne). VERIFIED — domain is reasoning/math, NOT code.**
Domain tier: general (math reasoning). Inference-time (both also have training-time variants). Metacognitive Reuse converts recurring reasoning fragments into named “behaviors”  in a handbook; the authors report that “providing the LLM relevant behaviors in-context during reasoning reduces number of reasoning tokens by up to 46% while matching or improving baseline accuracy.” Examples are explicitly math (triangle angle sums, Lagrange multipliers).  RoT reuses prior reasoning as composable “thought” steps in a thought-graph, “reducing output tokens by up to 40%, inference latency by 82%, and cost by 59% while maintaining accuracy” — evaluated on reasoning benchmarks. Both corroborate the compact-reusable-unit thesis at inference time but neither is code. This matters for extrapolation honesty: the compact-plan mechanism is proven on math, extended to code only via COPE/MutaGReP.

**4. Plan-and-Act / plan transfer. PARTIALLY REMAPPED.** The relevant verified anchors are plan-and-solve (arXiv 2305.04091) and least-to-most (arXiv 2205.10625); Plan-and-Act as a web-agent long-horizon plan-transfer paper is adjacent-to-code, not pure code. Domain tier: general/agent. Inference-time. The transferable-plan family is well-supported; treat “Plan-and-Act” as one instance of a broader plan-transfer literature.

**5. COPE — RESOLVED. The citation exists: “Efficient LLM Collaboration via Planning,” arXiv 2506.11578 (Lee et al., KAIST/Yonsei; v4 May 2026).** Domain tier: SWE + general. Inference-time, training-free, few-shot-free.  This is materially STRONGER than the existing report assumed. COPE is a test-time framework where a planner model emits a lightweight plan (goal or guideline) that guides an executor.  Key verified findings that directly answer the core weaker-executor question: “Larger planners help smaller executors” (Llama-3B rises 42.8%→53.0% with a GPT-mini plan; Llama-1B rises 25.2%→36.4% with a Llama-3B plan)  and, critically, “Smaller planners degrade larger executors” (GPT-mini drops 73.8%→70.6%/69.6% under weak plans).  It also found small executors benefit more from a GOAL (what to achieve) than a GUIDELINE (how to solve): Llama-1B 30.2% with goal vs 23.2% with guideline vs 25.2% none.  Crucially, COPE reports results on BOTH MATH-500 (75.8% vs GPT-4o’s 75.2%, ~45% cost cut) AND MBPP code generation (66.4% vs GPT-4o’s 64.0%, ~75% cost cut),  plus MT-Bench and ALFWorld. So the compact-plan-transfer-to-weaker-executor claim is verified on code, not just math. The existing report’s inability to verify COPE was a citation-matching failure, not a substantive one.

**6. BitsAI-CR (arXiv 2501.15134, FSE 2025 Industry) & Defect-Focused Code Review (arXiv 2505.17928, ICML 2025 Spotlight). VERIFIED — production/studied criteria-anchored systems.**
Domain tier: SWE. Inference-time (LLM pipelines). BitsAI-CR (ByteDance): two-stage RuleChecker (detection against a comprehensive review-rule taxonomy) + ReviewFilter (precision verification), data-flywheel improvement,  75.0% precision, 26.7% Outdated Rate on Go, 12,000+ WAU.  Defect-Focused (400M-DAU company, C++): code-slicing for context, multi-role LLM framework for key-bug-inclusion, a filtering mechanism for false-alarm reduction,  2× improvement over standard LLMs and 10× over prior baselines.  Both confirm the criteria-anchored review + filtering/verification-layer architecture that underwrites the code-review capture shape.

**7. Hypothesis-driven bug localization (arXiv 2601.12522, CogniGent, ICPC 2026) & graph-retrieval+Reflexion fault localization (arXiv 2409.13642, LLM4FL, Rafi et al.). VERIFIED — in-episode diagnosis structuring, not static-context transfer.**
Domain tier: SWE. Inference-time. CogniGent emulates “dynamic cognitive debugging” with causal-reasoning agents that conduct hypothesis testing during code exploration (591 bug reports; MAP +23.33–38.57%, MRR +25.14–53.74%). LLM4FL uses graph-based retrieval + a Reflexion mechanism to iteratively critique and refine fault hypotheses across reasoning rounds. Both structure diagnosis around hypotheses/reflection WITHIN an episode — they validate disconfirm-first/hypothesis-ordering as a runtime move, but do not test handing a static failure-signature artifact to a weaker executor.

**8. AgenticAKM (arXiv 2602.04445, Dhar et al., ICSE AGENT 2026). VERIFIED — it MANAGES architecture knowledge; does NOT test ADR-rationale transfer to a weaker executor.** Domain tier: SWE. Inference-time. Multi-agent workflow (Extraction/Retrieval/Generation/Validation) that GENERATES ADRs from code repositories, validated by a user study showing better ADRs than a single-LLM baseline. It is about producing architecture knowledge, not about feeding ADR-shaped rationale into a weaker executor and measuring downstream lift — so it is adjacent to, not a test of, the design-capture-transfer question.

**9. Codified Context, Contextual Verifiers, trajectory-memory cluster. ALL VERIFIED, domain/mechanism confirmed.**

- Codified Context (arXiv 2602.20478): SWE; 3-tier context infrastructure for a 108k-line C# codebase; single-author OBSERVATIONAL case study (283 sessions), no controlled ablation — weak evidentiary weight. Inference-time.
- Agentic Rubrics as Contextual Verifiers (arXiv 2601.04171): SWE; expert agent builds a repo-grounded rubric checklist for execution-free patch scoring; SWE-bench Verified 54.2% (Qwen3-Coder-30B), +3.5pp over baseline. Inference-time (test-time scaling). Directly supports criteria-checklist-as-verifier.
- AutoRefine (arXiv 2601.22758): general agents (ALFWorld/ScienceWorld/TravelPlanner), extracts reusable “Experience Patterns” from trajectories; inference-time. NOT code.
- MemGovern (arXiv 2601.06789): SWE; governs raw GitHub issue data into 135K “experience cards” + agentic retrieval; +4.65% on SWE-bench Verified; inference-time (plug-in memory, no fine-tuning).
- MeCo (arXiv 2601.20577): multi-robot collaboration via similar-task memoization; general/robotics; inference-time. NOT code.
  All are retrieve-distilled-experience-across-episodes systems with degradation/maintenance failure modes — adjacent to, but not the same as, the in-context compact-plan question.

**10. Mid-2026 post-anchor AGENTS.md cluster + training-time anchors. VERIFIED — they deepen the negative.**

- Context Rot in AI-Assisted Software Development (arXiv 2606.09090, Treude & Baltes): SWE; context in CLAUDE.md/AGENTS.md/.cursorrules goes stale (“context rot”); applying an existing README/wiki consistency checker to 356 repositories found stale code-element references in 23.0%. Drift is now a first-class failure mode. Inference-time concern.
- Configuration Smells in AGENTS.md (arXiv 2606.15828, UFMG, dos Santos et al.): SWE; catalogs config smells across 100 popular files; Lint Leakage (62%), Context Bloat (42%), Skill Leakage (35%); “bloated configuration files increase token consumption, raise costs, and reduce the visibility of important instructions.”
- Probe-and-Refine Tuning of Repository Guidance (arXiv 2606.20512, Shepard & Albrecht, Williams College): SWE; synthetic bug-fix probes iteratively refine an AGENTS.md file via single-shot LLM calls (no gradient updates); SWE-bench Verified 33.0% vs 28.3% static baseline. Explicitly notes the literature is “contested” on whether LLM-generated guidance helps or harms, and deliberately uses the SAME model for tuning and execution to avoid capability mismatch. Modest effect, single model family.
- LeDex (arXiv 2405.18649, Jiang et al., NeurIPS 2024): CODE but TRAINING-TIME (SFT+RL to self-debug; up to +15.92% pass@1). EXCLUDED from in-context recommendations except as evidence for the weaker-executor premise: its stated motivation is that few-shot self-debug prompting “works poorly on small open-sourced LLMs.” 
- DeepPlanning (arXiv 2601.18137, Qwen team): general long-horizon planning benchmark (travel/shopping, not code); documents that even frontier agentic LLMs struggle with long-horizon planning. Inference-time (benchmark).
- Program-synthesis abstraction learning (arXiv 2602.00929, “Learning Abstractions for Hierarchical Planning in Program-Synthesis Agents”): program-synthesis/theory-based RL; in-context abstraction learning; inference-time (no LLM weight training).

No anchor ID failed to resolve. Two naming collisions were flagged and disambiguated: “AutoRefine” (2601.22758 agent-refinement ≠ 2505.11277 RAG-RL) and “MeCo” (2601.20577 multi-robot ≠ 2606.09677 speech separation).

-----

## How much SWE-specific inference-time element evidence actually exists (quantified honestly)

Counting studies that isolate a capture element’s effect for a weaker/less-capable in-context executor on code:

- **Directly on code, weaker executor, inference-time:** essentially TWO strong studies — COPE (2506.11578, plan element on MBPP) and MutaGReP (2502.15872, plan element on repository code, with an explicit capability gradient: Llama-3.2-3B 7.4%→32.9%, Qwen-2.5-7B 17.5%→45.0% overlap when given plans).  Both isolate exactly ONE element: the compact plan.
- **On code, element = few-shot exemplar quality/choice (not weaker-executor-specific):** two studies — “Does Few-Shot Learning Help LLM Performance in Code Synthesis?” (2412.02906, HumanEval+) and Explain-then-Translate (2311.07070, exemplar correctness matters).
- **On the captured-context-file element:** the AGENTS.md cluster (2602.11988, 2601.20404, 2606.09090, 2606.15828, 2606.20512) — collectively the richest SWE element evidence, and it is a NEGATIVE for the narrative/overview form.
- **On every other element** (goal restatement, pruned dead-ends, named failure-signatures, invariants-as-checks-vs-prose, one nearby worked example, rejected-alternatives-with-boundary-conditions, sensitivity notes, stop-criterion, self-explanation prompts): **ZERO code-specific weaker-executor ablations located.** All verdicts for these rest on general/math (step-back, analogical, self-consistency, chain-of-verification, distraction studies) or human-methods tiers.

Bottom line: the existing report’s admission that element-level code evidence “barely exists” is correct and, if anything, understated. The plan element is settled; the context-file element is settled (negative for narrative); everything else is extrapolation.

-----

## Per-type capture shapes (verified & deepened)

**(1) Debugging / diagnostic.** Type: debugging — SWE evidence: moderate (in-episode only) — Human donor: Critical Decision Method / CDM (untested for code). Recommended shape: skeleton + front-loaded named failure-signatures + disconfirm-first hypothesis ordering. SWE evidence: CogniGent (2601.12522) and LLM4FL (2409.13642) show hypothesis-testing and Reflexion-style reflection improve fault localization WITHIN an episode — validating the runtime moves, but NOT validating handing a static failure-signature artifact to a weaker executor. Human-donor status: CDM is borrowed from naturalistic decision-making and remains untested as a capture format for code. Per-type unknown: does a pre-computed named-failure-signature list actually help a weaker executor, or does it merely bias search? Must-test.

**(2) Development / implementation.** Type: development — SWE evidence: collapses to skeleton — Human donor: none needed. Recommended shape: the shared skeleton (goal + resolved forks + pruned dead-ends + stop criterion). SWE evidence: COPE’s MBPP result and MutaGReP’s repository-code result show a compact plan is the operative element; no development-specific structure beyond the skeleton is evidenced. Collapses to skeleton — confirmed.

**(3) Design & architecture.** Type: design — SWE evidence: weak/extrapolated — Human donor: ADR/MADR (zero agent-side reuse evidence). Recommended shape: skeleton + rejected-alternatives-with-boundary-conditions. SWE evidence: AgenticAKM (2602.04445) GENERATES ADRs well but does not measure downstream executor lift from consuming ADR rationale. Human-donor status: ADR/MADR is a documentation convention; no located study feeds ADR-shaped rationale to a weaker executor and measures benefit. Per-type unknown: whether boundary-conditioned rejected-alternatives help or merely add tokens. Must-test.

**(4) Code review.** Type: code review — SWE evidence: strong — Human donor: ACH (partially transferred). Recommended shape: skeleton + explicit criteria/checklist + disconfirm-first + default-REJECT + binary verdicts. SWE evidence: BEST-supported per-type shape. BitsAI-CR (2501.15134) and Defect-Focused Review (2505.17928) demonstrate criteria taxonomy + verification/filter layer in production; Agentic Rubrics (2601.04171) shows repo-grounded rubric checklists as contextual verifiers improve patch scoring. Human-donor status: the disconfirm-first / competing-hypotheses logic (ACH) is realized in the filtering layer; binary verdicts and default-REJECT are engineering choices that align with human review discipline. This shape genuinely differs and is validated.

**(5) Evaluation / judging (incl. LLM-artifact evaluation).** Type: evaluation — SWE evidence: moderate (via review analogy) — Human donor: ACH (untested as such). Recommended shape: largely COLLAPSES into the code-review shape — binary pass/fail over Likert, disconfirm-first, judge from a DIFFERENT model family seeing only the finding text, deterministic pre/post filters. SWE evidence: the filtering/verification layers in BitsAI-CR and Defect-Focused Review are effectively judge stages; chain-of-verification (2309.11495) supports independent-verification-question structure and cross-model verification to reduce correlated errors. Per-type unknown: the different-model-family-judge and finding-text-only isolation are principled but not directly ablated on code. Collapses into review shape.

**(6) Feature planning & implementation.** Type: feature planning — SWE evidence: moderate (decomposition proven, sequencing extrapolated) — Human donor: none needed. Recommended shape: skeleton + explicit decomposition/sequencing with dependencies and per-subtask done-checks. SWE evidence: least-to-most (2205.10625) and plan-and-solve (2305.04091) prove decomposition helps easy-to-hard generalization (least-to-most: SCAN 16%→99.7% with code-davinci-002); COPE proves compact planning helps code execution. Per-subtask done-checks are extrapolated from the stop-criterion element. Largely skeleton + explicit dependency graph.

**Human-donor mapping test (CDM→debugging, ADR/MADR→design, ACH→evaluation/review):** ACH→review is the only mapping with SWE-side realization (via filtering/verification layers). CDM→debugging and ADR/MADR→design remain human-borrowed and UNTESTED as capture formats for code — do not present them as validated.

-----

## THE ELEMENT × EVIDENCE TRIAGE TABLE (centerpiece)

|Capture element                                                                       |Best evidence & source                                                                                  |Domain tier            |Inference-time?|Verdict                   |Confidence |
|--------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|-----------------------|---------------|--------------------------|-----------|
|Goal / problem restatement                                                            |COPE (2506.11578): small executors benefit MORE from a GOAL than a guideline (Llama-1B 25.2%→30.2%)     |SWE + general          |Yes            |include (resolved-helps)  |Medium-high|
|Ordered resolved-decision path (compact plan)                                         |COPE (MBPP 66.4% vs 64.0%); MutaGReP (2502.15872, weaker models gain most on repo code)                 |SWE                    |Yes            |include (resolved-helps)  |High       |
|Pruned dead-ends                                                                      |RoT (2509.21743) reduces redundant exploration; no code-specific ablation                               |general                |Yes            |test-if-cheap             |Low-medium |
|Named failure-signatures                                                              |Pre-mortem/prospective-hindsight (human, +30% risk ID); CogniGent (in-episode only)                     |human + SWE(in-episode)|Yes (human n/a)|test-if-cheap             |Low-medium |
|Invariants/checks AS executable checks                                                |Agentic Rubrics (2601.04171) rubric-as-verifier; AGENTS.md “programmatic checks” advisory               |SWE                    |Yes            |include (resolved-helps)  |Medium     |
|Invariants/checks AS prose                                                            |AGENTS.md negative (2602.11988): prose guidance followed but often cost-inflating                       |SWE                    |Yes            |exclude-or-minimize       |Medium     |
|One nearby worked example                                                             |Analogical prompting (2310.01714, GSM8K/MATH, self-gen tops); expertise-reversal risk for capable models|general                |Yes            |test-if-cheap             |Medium     |
|Rejected-alternatives-with-boundary-conditions                                        |ADR/MADR (human); AgenticAKM generates but doesn’t test lift                                            |human + SWE(adjacent)  |Yes (human n/a)|must-test                 |Low        |
|Sensitivity notes                                                                     |No located evidence                                                                                     |—                      |—              |must-test                 |Very low   |
|Confirmation / stop criterion                                                         |COPE confidence-thresholds (majority vote / test-pass); satisficing (Simon, human)                      |SWE + human            |Yes            |include (resolved-helps)  |Medium     |
|Self-explanation prompts                                                              |Chi et al. self-explanation effect (human); “explanation ≠ faithful belief” caution for LLMs            |human                  |Yes (human n/a)|test-if-cheap             |Low        |
|Captured-context/instruction-file (AGENTS.md/CLAUDE.md style), narrative/overview form|ETH AGENTS.md (2602.11988): no general success gain, >20% cost; smells/rot (2606.15828, 2606.09090)     |SWE                    |Yes            |exclude-or-minimize       |High       |
|Captured-context file, imperative instructions/conventions/non-inferable tooling      |ETH AGENTS.md: instructions followed, developer-written marginally positive (~4%)                       |SWE                    |Yes            |include (minimal, curated)|Medium-high|

Note: “must-test” is a GAP, not a recommendation — it flags where no located evidence exists.

-----

## The captured-context-file finding (called out on its own)

The single most consequential SWE-specific negative in this literature: **repository-level context files do NOT behave like free performance.** The ETH Zurich study (2602.11988) shows that across four agents and both file provenances, context files fail to generally improve task success and raise inference cost  by >20% on average, because agents dutifully follow the extra instructions and over-explore.  The post-anchor cluster deepens this into three named failure modes: **drift/context-rot** (2606.09090, 23.0% of repos carry stale code-element references), **configuration smells** (2606.15828 — lint leakage 62%, context bloat 42%), and **contested efficacy** even under careful tuning (2606.20512, only 33.0% vs 28.3%).

Precise implication for the reader’s artifact: a compact resolved-decision-path sits at the **instruction/plan end** of the spectrum (followed-and-useful, per COPE/MutaGReP), NOT the **repository-overview/narrative end** (unhelpful and cost-inflating, per 2602.11988). Concretely: (a) do NOT pad the artifact with narrative repository summaries or architecture prose; (b) DO include imperative, non-inferable, task-relevant content (exact commands, hard constraints, the resolved plan); (c) prefer executable checks over prose invariants; (d) keep it short — bloat measurably buries the instructions that matter. The 28.6%/16.6% efficiency result (2601.20404) is consistent with this: a lean, imperative file reduces output tokens on completed tasks even as narrative files inflate total cost.

-----

## THE STRUCTURAL-MOVES CATALOG (major new section)

Core thesis: the value of a capture artifact is not generic deliberation — it is imposing the PARTICULAR structural move the task needs. Each move is classified as a capture ELEMENT (static text that transfers) or a RUNTIME strategy (something the executor must DO at inference and cannot be handed as static text). This distinction is load-bearing: a runtime strategy cannot be a capture element even if highly effective.

**1. Decomposition (ordered subproblems).** Human: Polya’s heuristics, means-ends analysis. LLM analog + effect: least-to-most (2205.10625, Zhou et al., Google — code-davinci-002 solves SCAN in any split “with an accuracy of at least 99% using just 14 exemplars, compared to only 16% accuracy with chain-of-thought prompting”; generalizes easy-to-hard); plan-and-solve (2305.04091 — PS+ up to +8% over zero-shot CoT);  COPE (2506.11578 — code + math, weaker executor). SWE task-shape served: feature planning, development. Tier: SWE + general. Inference-time. Weaker-executor verdict: HELPS (strongest evidence; proven on code). Classification: **capture ELEMENT** (the ordered plan is static transferable text).

**2. Abstraction-first (governing principle before diving in).** Human: first-principles reasoning, reasoning from invariants. LLM analog + effect: step-back prompting (2310.06117, Zheng et al., Google DeepMind) — the abstract reports “STEP-BACK PROMPTING improves PaLM-2L performance on MMLU Physics and Chemistry by 7% and 11%, TimeQA by 34%, and MuSiQue by 7%” (the v2 body text reports TimeQA +27%; cite +7%/+11%/±27–34%/+7%). SWE task-shape: design/architecture. Tier: general (STEM/QA, not code). Inference-time. Weaker-executor verdict: likely helps but UNTESTED on code. Classification: **RUNTIME strategy** when self-generated; becomes a capture ELEMENT if the governing principle is pre-computed and handed over.

**3. Disconfirmation / competing hypotheses.** Human: “consider the opposite” (Lord, Lepper & Preston 1984; Hirt & Markman 1995 showed considering ANY plausible alternative, not just the opposite, triggers debiasing; effect maintained 8 weeks in a pre-registered training study, ScienceDirect S0361476X20300096) and Analysis of Competing Hypotheses (ACH). LLM analog + effect: self-consistency (sample diverse paths, majority vote); chain-of-verification (2309.11495, Dhuliawala et al., Jason Weston lab — the model “answers those questions independently so the answers are not biased by other responses”; on closed-book MultiSpanQA “CoVe improves the F1 score by 23% (from 0.39 to 0.48)”). SWE task-shape: code review / judging (disconfirm-first + default-REJECT). Tier: general + SWE(review). Inference-time. Weaker-executor verdict: HELPS (realized in BitsAI-CR/Defect-Focused filtering layers). Classification: **RUNTIME strategy** (the executor must generate/score alternatives), though the criteria checklist that triggers it IS a capture element.

**4. Reference-class / outside view (base-rate anchoring).** Human: reference-class forecasting — VERIFIED: Kahneman & Tversky (1979) “Intuitive Prediction” and Lovallo & Kahneman (2003) show people default to the inside view and underweight distributional information (the planning fallacy), and outside-view framing improves forecast accuracy. LLM analog: weak — retrieval/RAG of similar cases, under-explored. SWE task-shape: estimation, feature planning. Tier: human (LLM analog thin). Inference-time. Weaker-executor verdict: UNKNOWN — worth testing. Classification: **capture ELEMENT** if base-rates/reference-class data are supplied as text; the strongest human debiasing result for estimation but the weakest LLM analog.

**5. Analogical transfer (retrieve a nearby solved case).** Human: case-based reasoning. LLM analog + effect: analogical prompting (2310.01714) — self-generated exemplars outperform 0-shot and few-shot CoT on GSM8K and MATH and code generation (Codeforces);  documented failure mode is a generalization gap when the target is harder than generated exemplars.  SWE task-shape: implementation, debugging. Tier: general (some code). Inference-time. Weaker-executor verdict: TEST-IF-CHEAP — anchoring risk for a capable model (matches expertise-reversal caution on the worked-example element; LLM-simulated expertise-reversal reproduced in 2403.02795).  Classification: **capture ELEMENT** (one nearby worked example is static text) — but with anchoring risk.

**6. Multiple independent attempts + aggregation.** Human: wisdom-of-crowds, Delphi, dialectical inquiry. LLM analog + effect: self-consistency (majority vote over sampled paths) — robust across reasoning and code. SWE task-shape: any high-stakes decision. Tier: general + SWE. Inference-time. Weaker-executor verdict: HELPS. Classification: **RUNTIME strategy** — explicitly NOT a capture element (cannot be handed as static text; it is a sampling procedure).

**7. Prospective failure imagination.** Human: pre-mortem / prospective hindsight (Klein 2007; Mitchell, Russo & Pennington 1989) — VERIFIED: imagining a plan has already failed and generating causes improves ability to identify reasons for future outcomes by ~30% vs “what could go wrong.” LLM analog: named-failure-signatures element (untested on code as a transferred artifact). SWE task-shape: debugging, design risk. Tier: human (LLM analog untested). Inference-time. Weaker-executor verdict: TEST-IF-CHEAP. Classification: **capture ELEMENT** (the failure-signature list is static text) — but note that surfacing the signatures is a runtime move; only the resulting list transfers.

### Added structural moves

**8. Constraint propagation / invariant-first reasoning.** Human: constraint satisfaction, design-by-contract, type-driven development. LLM analog: executable-check/rubric conditioning (Agentic Rubrics 2601.04171); COPE’s qualitative example shows a planner surfacing a divisibility+inequality constraint that fixes the executor’s error. SWE task-shape: implementation correctness, review. Tier: SWE. Inference-time. Weaker-executor verdict: HELPS when invariants are executable checks; exclude when prose. Classification: **capture ELEMENT** (as checks).

**9. Differential / bisection diagnosis.** Human: differential diagnosis (medicine), binary-search debugging, git bisect logic. LLM analog: hypothesis-ordering in CogniGent (2601.12522), Reflexion refinement in LLM4FL (2409.13642). SWE task-shape: debugging/fault localization. Tier: SWE (in-episode). Inference-time. Weaker-executor verdict: HELPS as a runtime procedure; unknown as transferred artifact. Classification: **RUNTIME strategy**.

**10. Rubber-duck / self-explanation.** Human: self-explanation effect (Chi et al. 1989, Cognitive Science 13(2):145–182; 1994 prompting study — prompting self-explanation causally improves learning and transfer). LLM analog: self-explanation prompting, with the crucial caution that LLM “explanation ≠ faithful belief” (post-hoc rationalization). SWE task-shape: implementation, learning-heavy tasks. Tier: human. Inference-time. Weaker-executor verdict: TEST-IF-CHEAP. Classification: **RUNTIME strategy** (the act of explaining), not transferable as static text.

**11. Type-driven / contract-driven reasoning.** Human: parse-don’t-validate, make-illegal-states-unrepresentable. LLM analog: under-studied; overlaps move #8. SWE task-shape: implementation, API design. Tier: human/general. Inference-time. Weaker-executor verdict: MUST-TEST. Classification: **capture ELEMENT** (types/contracts are static text).

**12. Counterfactual / ablation reasoning.** Human: systematically remove/vary one factor; causal reasoning. LLM analog: distraction studies (2302.00093, Shi et al., Google, ICML 2023 — introduces GSM-IC and finds “model performance is dramatically decreased when irrelevant information is included,” mitigated by self-consistency and an instruction to ignore irrelevant information) show the inverse (context sensitivity). SWE task-shape: debugging, evaluation. Tier: general. Inference-time. Weaker-executor verdict: MUST-TEST on code. Classification: **RUNTIME strategy**.

**13. Inversion (solve the inverse / avoid-stupidity).** Human: Munger’s inversion; overlaps pre-mortem. LLM analog: none located. SWE task-shape: design, risk. Tier: human. Weaker-executor verdict: MUST-TEST. Classification: **RUNTIME strategy**.

**14. Occam / minimum-description-length parsimony.** Human: parsimony heuristics. LLM analog: compact-plan results (Metacognitive Reuse, RoT) implicitly reward brevity; AGENTS.md bloat findings (2606.15828) show verbosity hurts. SWE task-shape: all. Tier: general + SWE. Inference-time. Weaker-executor verdict: HELPS (keep artifacts compact). Classification: **capture ELEMENT** (a constraint on artifact form).

**15. Checklist-driven reasoning.** Human: Gawande’s checklist manifesto — VERIFIED: WHO Surgical Safety Checklist (Haynes et al. 2009, NEJM 360:491–9) cut death 1.5%→0.8% and inpatient complications 11.0%→7.0% across eight global hospitals. LLM analog: criteria checklists in review/eval (BitsAI-CR taxonomy, Agentic Rubrics). SWE task-shape: code review, evaluation. Tier: human + SWE. Inference-time. Weaker-executor verdict: HELPS (best-evidenced per-type shape). Classification: **capture ELEMENT** (the checklist is static text).

**16. Fermi estimation / order-of-magnitude bounding.** Human: Fermi estimation. LLM analog: none strong located. SWE task-shape: performance/complexity reasoning, estimation. Tier: human. Weaker-executor verdict: MUST-TEST. Classification: **RUNTIME strategy**.

**17. Specification-first / test-first reasoning.** Human: TDD as a reasoning discipline; property-based testing thinking. LLM analog: test-pass as COPE’s code confidence signal; Agentic Rubrics as pre-specified acceptance criteria. SWE task-shape: development, feature planning. Tier: SWE-adjacent. Inference-time. Weaker-executor verdict: TEST-IF-CHEAP (specifications/tests as supplied text plausibly help). Classification: **capture ELEMENT** (specs/tests are static text).

**18. Satisficing vs optimizing (stop-criterion move).** Human: Simon’s satisficing. LLM analog: COPE’s confidence-threshold escalation (accept when consensus/test-pass exceeds τ). SWE task-shape: all (defines “done”). Tier: SWE + human. Inference-time. Weaker-executor verdict: HELPS (an explicit stop criterion prevents over-exploration — the exact failure AGENTS.md induces). Classification: **capture ELEMENT** (the stop criterion is static text).

Summary of the ELEMENT vs RUNTIME split: transferable capture ELEMENTS = decomposed plan, goal restatement, executable invariants/checks, one worked example, failure-signature list, reference-class data, checklist, specs/tests, stop criterion, parsimony constraint, types/contracts. RUNTIME strategies (cannot be handed as static text) = self-consistency/multiple-attempts, disconfirmation generation, differential/bisection diagnosis, self-explanation act, counterfactual ablation, inversion, Fermi estimation, and self-generated abstraction. The artifact should encode the elements and TRIGGER the runtime strategies via imperative instruction, not attempt to substitute for them.

-----

## What to build vs. what to test (pruned validation matrix)

**BUILD NOW (evidence settles it — helps a weaker executor):**

- Compact ordered resolved-decision plan (goal + resolved forks + stop criterion). [COPE, MutaGReP]
- Goal restatement in preference to verbose how-to guidelines for weaker executors. [COPE]
- For review/eval: explicit criteria checklist + disconfirm-first + default-REJECT + binary verdicts, with a separate verification/filter stage. [BitsAI-CR, Defect-Focused, Agentic Rubrics, surgical-checklist analog]
- Executable checks over prose invariants. [Agentic Rubrics; AGENTS.md negative]
- An explicit stop/confidence criterion. [COPE]
- Keep the artifact compact and imperative. [AGENTS.md bloat/rot findings]

**EXCLUDE NOW (evidence says it hurts or wastes tokens):**

- Repository-overview / architecture narrative in the context file. [2602.11988]
- LLM-generated whole-repo context files (marginal negative). [2602.11988]
- Redundant guidance a linter/formatter already enforces (lint leakage). [2606.15828]
- Prose invariants as a substitute for checks.

**TEST-IF-CHEAP (suggestive, plausibly helps):**

- Named failure-signatures for debugging [pre-mortem analog]; one nearby worked example [analogical prompting, anchoring risk]; pruned dead-ends [RoT]; self-explanation prompts; specs/tests-first; reference-class data for estimation.

**MUST-TEST (GAP — no located code evidence):**

- Rejected-alternatives-with-boundary-conditions for design; sensitivity notes; type/contract statements; counterfactual/inversion/Fermi as transferred content; CDM→debugging and ADR/MADR→design human-donor mappings.

-----

## Gaps (where SWE evidence is missing and the recommendation rests on general/human transfer)

1. Element-level ablations on code for a weaker in-context executor exist ONLY for the plan element (COPE, MutaGReP) and exemplar quality (2412.02906, 2311.07070). Every other element is extrapolated.
1. The CDM→debugging and ADR/MADR→design human-donor mappings have ZERO agent-side reuse validation on code.
1. Abstraction-first (step-back), disconfirmation debiasing effect sizes, reference-class, pre-mortem, self-explanation, and checklist mortality data are all HUMAN or GENERAL/MATH tier; their transfer to a weaker in-context code executor is assumed, not demonstrated.
1. The “judge from a different model family, seeing only finding text” evaluation discipline is principled (cross-model verification in CoVe) but not directly ablated on code.
1. Field-pace caveat: findings may have shifted since the ~Feb–Mar 2026 anchor. The post-anchor cluster (2606.*) already deepens the AGENTS.md negative; further mid-2026 work may revise effect sizes. COPE’s own v4 is dated May 2026.

-----

## Caveats

- **Extrapolation is the common case, not the exception.** For every element except the compact plan and the context-file, the verdict rests on general/math or human evidence. These are labeled per-row; do not read “include/test-if-cheap” as SWE-proven unless the row’s tier says SWE.
- **In-context-only hard filter applied.** LeDex (2405.18649) is code but training-time and is excluded from recommendations except as premise support; Metacognitive Reuse and RoT have training-time variants but the cited effects are the inference-time in-context ones.
- **Secondary-source figures.** The ETH “~4% developer-written gain” and “~3% LLM-generated drop / 2–4 extra reasoning steps” come from secondary technical write-ups of 2602.11988, not the paper’s abstract; treat as directional. The Configuration-Smells “83% co-occurrence” figure is explicitly flagged by its reporter as directional, not precise.
- **Single-study / single-model-family risks.** MutaGReP, Probe-and-Refine (single Qwen family), Codified Context (single-author observational), and AgenticAKM (one user study) each rest on narrow evidence; corroborate before over-weighting.
- **Step-back deltas have a versioned discrepancy:** the 2310.06117 abstract states TimeQA +34% while the v2 body reports +27%; both figures trace to the same paper.

-----

## Source ledger

Verified primary sources (arXiv ID / venue — domain tier — inference vs training — one-line characterization):

- 2602.11988 (ETH Zurich; under review) — SWE — inference — repository context files don’t generally help, raise cost >20%; the centerpiece negative.
- 2601.20404 (ICSE JAWs 2026) — SWE — inference — AGENTS.md lowers median runtime 28.6% and output tokens 16.6% on completed PRs; not in conflict once output-vs-total tokens separated.
- 2509.13237 (Metacognitive Reuse; Meta/Mila/Princeton) — general/math — inference (+training variant) — named reusable “behaviors” cut reasoning tokens up to 46% while matching/improving accuracy.
- 2509.21743 (Retrieval-of-Thought; UMinnesota/UCSC/Argonne) — general/math — inference — reusable thought-graph cuts output tokens 40%, latency 82%, cost 59%.
- 2506.11578 (COPE, “Efficient LLM Collaboration via Planning”) — SWE + general — inference, training-free — compact plan from stronger planner helps weaker executor on MATH-500 AND MBPP; smaller planners degrade larger executors. RESOLVES the COPE citation.
- 2502.15872 (MutaGReP) — SWE — inference — repository-grounded plans help weaker code models most (Llama-3.2-3B 7.4%→32.9%); capability gradient.
- 2501.15134 (BitsAI-CR, FSE 2025) — SWE — inference — two-stage RuleChecker+ReviewFilter, 75% precision, 12k WAU.
- 2505.17928 (Defect-Focused Review, ICML 2025 Spotlight) — SWE — inference — code-slicing + multi-role + FAR filter; 2×/10× gains.
- 2601.12522 (CogniGent, ICPC 2026) — SWE — inference — hypothesis-testing bug localization, MAP +23–39%.
- 2409.13642 (LLM4FL) — SWE — inference — graph retrieval + Reflexion fault localization.
- 2602.04445 (AgenticAKM, ICSE AGENT 2026) — SWE — inference — generates ADRs; does not test rationale-transfer lift.
- 2602.20478 (Codified Context) — SWE — inference — observational context-infra case study; weak evidence.
- 2601.04171 (Agentic Rubrics as Contextual Verifiers) — SWE — inference — repo-grounded rubric checklists as verifiers; +3.5pp SWE-bench Verified.
- 2601.22758 (AutoRefine) — general agents — inference — reusable Experience Patterns from trajectories.
- 2601.06789 (MemGovern) — SWE — inference — governed GitHub experience cards + retrieval, +4.65% SWE-bench Verified.
- 2601.20577 (MeCo) — robotics/general — inference — similar-task memoization.
- 2606.09090 (Context Rot) — SWE — inference — 23.0% of repos carry stale references; drift as failure mode.
- 2606.15828 (Configuration Smells) — SWE — inference — lint leakage 62%, context bloat 42%.
- 2606.20512 (Probe-and-Refine) — SWE — inference (single-shot tuning) — refined guidance 33.0% vs 28.3%; field “contested.”
- 2405.18649 (LeDex, NeurIPS 2024) — SWE — TRAINING — self-debug SFT+RL; EXCLUDED from in-context recs except premise support.
- 2601.18137 (DeepPlanning) — general — inference (benchmark) — frontier LLMs struggle at long-horizon planning.
- 2602.00929 (Learning Abstractions for Hierarchical Planning in Program-Synthesis Agents) — program-synthesis — inference — in-context abstraction learning.
- 2310.06117 (Step-Back; Google DeepMind) — general/STEM — inference — abstraction-first; MMLU Physics +7%, Chemistry +11%, TimeQA +27–34%, MuSiQue +7%.
- 2205.10625 (Least-to-Most; Google) — general — inference — decomposition; SCAN 16%→99.7% (code-davinci-002, 14 exemplars).
- 2305.04091 (Plan-and-Solve) — general — inference — plan-then-solve; PS+ up to +8% over zero-shot CoT.
- 2310.01714 (Analogical Prompting) — general (+code) — inference — self-generated exemplars beat few-shot CoT on GSM8K/MATH/Codeforces.
- 2309.11495 (Chain-of-Verification; Jason Weston lab) — general — inference — draft→verify-questions→independent-answers→revise; closed-book MultiSpanQA F1 0.39→0.48; cross-model verification reduces correlated errors.
- 2302.00093 (Distracted by Irrelevant Context; Google, ICML 2023) — general/math — inference — GSM-IC; irrelevant context dramatically degrades accuracy.
- 2402.12091 — general/logic — inference — smaller models more perturbed by context changes than larger ones.
- 2412.02906 (Few-Shot in Code Synthesis) — SWE — inference — exemplar choice strongly modulates weaker-model coding.
- 2311.07070 (Explain-then-Translate) — SWE — inference — exemplar correctness matters.
- 2403.02795 — general/education — inference — LLM-simulated learners reproduce expertise-reversal effect.
- Human-methods tier: Haynes et al. 2009 (NEJM 360:491–9, surgical checklist, death 1.5%→0.8%, complications 11.0%→7.0%); Klein 2007 / Mitchell, Russo & Pennington 1989 (pre-mortem, +30%); Lord/Lepper/Preston 1984 & Hirt & Markman 1995 (consider-the-opposite; ScienceDirect S0361476X20300096 for 8-week persistence); Kahneman & Tversky 1979 / Lovallo & Kahneman 2003 (outside view/planning fallacy); Chi et al. 1989 (Cognitive Science 13(2):145–182) / 1994 (self-explanation effect); Simon (satisficing); Munger (inversion).

Unverified leads / resolution outcomes:

- **COPE: RESOLVED** to arXiv 2506.11578 (“Efficient LLM Collaboration via Planning,” KAIST/Yonsei). Not unverifiable — it was a citation-matching failure in the prior pass. Substance (compact-plan transfer, reported on MATH) confirmed, and extended to code (MBPP).
- **“Plan-and-Act”:** treat as one instance of the plan-transfer family (plan-and-solve 2305.04091, least-to-most 2205.10625); web-agent long-horizon plan transfer is adjacent-to-code.
- Naming collisions flagged: AutoRefine 2601.22758 ≠ 2505.11277 (RAG-RL); MeCo 2601.20577 ≠ 2606.09677 (speech separation). All ten queried post-anchor IDs resolved to real, matching papers.