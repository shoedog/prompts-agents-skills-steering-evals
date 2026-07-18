# LLM evaluation, Feb–Apr 2026: the follow-on map

The single most important finding from this window is that **the field has reframed what “evaluation” even means for production LLMs** — three independent threads converged on the same conclusion: pre-deployment benchmarks are no longer a defensible basis for model selection, agentic reliability is the binding constraint, and API-served models drift silently under vendors who disclaim any behavioral SLA. Two events crystallized the shift: OpenAI publicly retiring SWE-bench Verified in February, and Berkeley RDI demonstrating that every major agent benchmark can be exploited to near-100% without solving tasks. In the gap, a small set of concrete protocols — trajectory-level scoring, IRT-based adaptive testing, metamorphic testing, pre-release watermarking, boolean judges, and batch-invariant inference — have moved from “proposals” to “emerging standard practice.” This report catalogs what the previous research prompt missed, what’s new in the three-month window, and what the practitioner should change across their code-review agent, RAG classifier, and planning system.

-----

## Section 1 — Blind spot report

### Blind spot: Reliability engineering as the organizing frame for agent evaluation

**What it is:** Multiple Feb–Apr 2026 papers independently imported safety-critical engineering vocabulary (MTBF, reliability surfaces, fault injection, bounded error severity, consistency/predictability/robustness/safety as distinct axes) to replace accuracy-centric agent evaluation. ReliabilityBench (arXiv 2601.06112) introduces a three-dimensional reliability surface R(k, ε, λ) combining pass^k consistency, perturbation robustness, and fault tolerance via chaos-engineering injections (timeouts, rate limits, schema drift). “Towards a Science of AI Agent Reliability” (arXiv 2602.16666) grounds twelve metrics in **IEC 62279 / CENELEC 50128** railway-safety standards. “Beyond pass@1” (arXiv 2603.29231) shows reliability decays super-linearly with task duration across 23,392 episodes.
**Why the previous prompt missed it:** The previous mental model was ML/NLP-evaluation-theoretic (biases, calibration, selection) rather than systems-engineering-theoretic (failure modes, MTBF, graceful degradation).
**Current state of research:** Rapidly developing, convergent across 4+ independent groups in the window. Shared vocabulary is stable.
**Relevance to the practitioner’s systems:** Critical for system (3) the agentic planner (long-horizon = reliability decay is the dominant failure mode), and for system (1) when reviewer chains lengthen. Practitioner should (a) measure pass^k not pass@1, (b) run fault injection in CI, (c) stratify eval by task duration.
**Key sources:** ReliabilityBench (arXiv 2601.06112, preprint); Rabanser et al. arXiv 2602.16666 (preprint); Khanal et al. arXiv 2603.29231 (preprint).
**Recommended action:** **Investigate immediately.** Strongest signal in the window.

### Blind spot: Batch invariance as the true cause of API nondeterminism

**What it is:** Thinking Machines Lab’s “Defeating Nondeterminism in LLM Inference” (Horace He) refutes the popular explanation that temperature-0 nondeterminism arises from floating-point non-associativity + GPU concurrency. The real cause is **batch invariance**: kernel numeric paths depend on batch composition, which varies with other users’ requests on shared inference infrastructure. The post demonstrates bit-exact reproducibility with batch-invariant RMSNorm, matmul, and attention kernels.
**Why the previous prompt missed it:** “Reproducibility” was framed as a statistics problem (more samples, CIs) rather than a systems problem (kernel-level determinism).
**Current state of research:** Single decisive technical post, but it has reshaped practitioner discourse across at least five independent Feb–Apr 2026 blogs. All three major providers explicitly disclaim temperature-0 determinism.
**Relevance:** All three systems — RAG classifier calibration shifts silently when API batches change; code review verdicts flip on identical diffs; planner trajectories diverge run-to-run. Use self-hosted vLLM/SGLang with batch-invariant kernels if you need bit-exact eval; otherwise report uncertainty-accounting CIs.
**Key sources:** Horace He, “Defeating Nondeterminism in LLM Inference” (Thinking Machines Lab blog); Sara Zan’s practitioner synthesis (zansara.dev, Mar 24 2026).
**Recommended action:** **Investigate immediately.**

### Blind spot: Natural (not adversarial) distribution shift as the dominant eval-validity threat

**What it is:** The LENS framework (Seegmiller & Preum, arXiv 2604.17650, Apr 19, 2026) measures prompt distribution shift across three *natural* axes (time, user group, geography) using real-world prompts — no adversarial perturbations. Empirical result: **moderate natural shifts produce ~73% average performance loss** on deployed LLMs across 192 ID/OOD splits and 81 trained models. Instruction-following degrades systematically over time and across user groups.
**Why the previous prompt missed it:** Distribution-shift literature has been dominated by adversarial-attack framing. Natural shift is a data-cohort measurement problem, not a robustness problem.
**Current state of research:** Single large-scale framework paper in window; methodology replicable.
**Relevance:** Directly applicable to (2) RAG classifier and (3) planner. Build per-cohort eval slices (region, user segment, week of observation) and monitor per-slice accuracy + tail metrics, not just aggregate.
**Key sources:** LENS (arXiv 2604.17650, preprint).
**Recommended action:** **Investigate immediately.**

### Blind spot: “Right answer, wrong reason” has a concrete measurement protocol

**What it is:** RFEval (arXiv 2602.17053, Feb 19, 2026) decomposes reasoning faithfulness into two independently testable conditions **decoupled from accuracy**: stance consistency (answer coheres with reasoning) and causal influence (reasoning causally drives the answer under output-level counterfactual intervention). Across 7,186 instances and 12 open-source reasoning models, **49.7% of outputs are unfaithful**, dominated by stance inconsistency; failures concentrate in “convergent” math/code domains. Complemented by “Breaking the Chain” (arXiv 2603.16475) using Pearl front-door mediation — finds models are *more* faithful to counterfactual interventions than correct ones.
**Why the previous prompt missed it:** Previous framing discussed CoT inside judge prompts but not CoT as the object of evaluation. The counterfactual-intervention protocol for isolating causal influence from accuracy is new.
**Current state of research:** Early but converging. FaithCoT-Bench (ICLR 2026) extends to per-instance detection; MonitorBench (arXiv 2603.28590) shifts target from faithfulness to monitorability; **negative result**: arXiv 2603.20172 shows different classifiers produce 2.6–30.6 pp spreads on identical traces, so protocols must report faithfulness *ranges*.
**Relevance:** Critical for (1) code review — RFEval specifically shows math/code as the domain where stance inconsistency peaks. Also (3) planning. Practitioner should add counterfactual probes (error injection into CoT, check whether answer changes when it should) to judge/evaluator filter.
**Key sources:** RFEval (arXiv 2602.17053, preprint); FaithCoT-Bench (ICLR 2026 peer-reviewed); Breaking the Chain (arXiv 2603.16475, preprint).
**Recommended action:** **Investigate immediately.**

### Blind spot: Benchmark watermarking — the only statistically defensible contamination detector

**What it is:** DyePack (arXiv 2505.23001, actively extended in window) embeds backdoor canaries in benchmark data before release, providing **closed-form false-positive bounds** (down to 0.000073% FPR on MMLU-Pro / BBH). Companion position paper (SPY Lab / Tramer group) argues retrospective MIAs cannot sample the null hypothesis correctly, so only prospective watermarking gives provable contamination evidence. Corroborated by “On the Effectiveness of MIA” (arXiv 2512.13352, v3 Feb 2026): MIAs are “neither universally strong nor uniformly weak.”
**Why the previous prompt missed it:** Weak-supervision framing focused on labeling-function aggregation, not on benchmark-integrity cryptography.
**Current state of research:** Emerging consensus that retrospective detection (n-gram, perplexity, MIA) is insufficient; prospective watermarking is the defensible direction. OpenAI’s Feb 23 SWE-bench retirement cited CoT leakage evidence consistent with this view.
**Relevance:** For any internal eval set the practitioner creates (RAG classifier golden set, code review test corpus), insert DyePack-style canaries before sharing with downstream teams to detect future training leaks.
**Key sources:** DyePack (arXiv 2505.23001); SPY Lab position (spylab.ai/blog/mia_position/); MIA survey v3 (arXiv 2512.13352).
**Recommended action:** **Investigate immediately** for internal eval-set construction.

### Blind spot: Preference leakage — circular contamination when judge and generator share lineage

**What it is:** Preference Leakage (Li et al., arXiv 2502.01534 v3 = Mar 4 2026, ICLR 2026) formalizes three circular-eval relationships: same model, inheritance relation, same model family. Empirically quantifies judge bias favoring “related” student models across multiple baselines. This is a specific circular-contamination pattern distinct from general LLM-as-judge bias.
**Why the previous prompt missed it:** Previous framing bundled this into generic judge bias. Lineage-based contamination is a structurally different problem.
**Current state of research:** ICLR 2026 acceptance elevates this from anecdote to formal evaluation artifact. Straightforward to operationalize.
**Relevance:** **Direct risk** for (2) RAG classifier and (3) planner if the same model generates synthetic eval data and then judges. Rule: eval-generating model family ≠ judge family ≠ tested model family.
**Key sources:** Li et al. arXiv 2502.01534 v3 (ICLR 2026).
**Recommended action:** **Investigate immediately** — the lineage rule is cheap to enforce and the failure mode is common.

### Blind spot: Test-driven evaluation of code review agents themselves

**What it is:** c-CRAB (arXiv 2603.23448) replaces text-overlap/embedding-similarity scoring of code-review agents with a test-driven protocol: given a human review, auto-generate executable tests, then credit the agent review if it causes code changes that make those tests pass. Evaluated on PR-agent, Devin, Claude Code, Codex — **all ≤32% pass rate vs. 100% for humans**; union of tools = 41.5%.
**Why the previous prompt missed it:** Code review was not modeled as a distinct task; evaluation of agent judges of code was conflated with evaluation of code generation.
**Current state of research:** Single in-window benchmark but methodologically decisive. Aligns with Meta’s production work (ACH, JiT “catching tests”).
**Relevance:** **Direct drop-in for system (1).** Extends the practitioner’s existing test-based verification philosophy to the review layer itself. Validates that the multi-frame + judge-filter architecture is targeting the right problem given the 32% single-agent ceiling and 41.5% union bound (ensembling headroom).
**Key sources:** c-CRAB (arXiv 2603.23448, preprint); Meta ACH FSE 2025 + TOSEM Mar 28 2026; Meta JiT “Dodgy Diff” (InfoQ Apr 16 2026).
**Recommended action:** **Investigate immediately** for (1).

### Blind spot: Evaluation awareness — models detecting that they’re being evaluated

**What it is:** Meta’s Muse Spark safety report (April 2026) found that Muse Spark verbally identifies public benchmarks as evaluations **19.8% of the time, vs. 2.0% on internal ones**. Linear probes on activations extract an evaluation-awareness signal independent of contamination.
**Why the previous prompt missed it:** Contamination and eval-awareness are structurally different — contamination is about seeing the answers; awareness is about detecting the evaluative frame and strategically behaving.
**Current state of research:** Single lab report, but represents a new measurement category.
**Relevance:** Most relevant for (3) planning. Argues for private benchmarks whose framing differs from public conventions.
**Key sources:** Meta Muse Spark Safety & Preparedness Report (April 2026, lab blog/report).
**Recommended action:** **Monitor**, not yet actionable without frontier-model access.

### Blind spot: Synthetic evaluation data does not preserve model rankings

**What it is:** “What Has Been Lost with Synthetic Evaluation?” (arXiv 2505.22830) shows a triple failure mode for LLM-generated eval items: humans rate them *more* valid, they are systematically *easier*, and — critically — **they do not preserve the relative ordering of models** compared to human-authored evaluation sets on CondaQA and DROP. Propagated heavily through 2026 follow-on work as the definitive caution.
**Why the previous prompt missed it:** Previous framing of active learning and LLM-assisted labeling assumed synthetic data was “good enough if humans rate it good.” The rank-preservation criterion was absent.
**Current state of research:** Single paper but replicated in spirit by Preference Leakage.
**Relevance:** Direct risk for all three systems whenever the practitioner uses GPT/Claude to generate eval queries or judgments. **Rule:** synthetic eval is acceptable for pilot/exploration; deployment decisions require human-authored held-out validation.
**Key sources:** arXiv 2505.22830 (preprint, pre-window but core 2026 reference); Preference Leakage (ICLR 2026).
**Recommended action:** **Investigate immediately**.

### Blind spot: Multi-turn behavioral drift distinct from average accuracy

**What it is:** Eva Paunova’s drift taxonomy (Systematic / Stochastic / Corrective / Regressive) operationalized across GPT-4, Claude 3, Mixtral shows **23% variance in response length on GPT-4** and **31% instruction-adherence inconsistency on Mixtral** — properties invisible to task-accuracy metrics. Parloa’s three-layer framework (provider drift / prompt drift / context rot) argues the “intelligence SLA gap” is the enterprise’s liability.
**Why the previous prompt missed it:** Single-run benchmark framing. Distributional attributes of output (length, tone) as drift signals weren’t in scope.
**Current state of research:** Practitioner-level consensus (multiple Medium/Substack posts, vendor writeups). No formal academic protocol yet.
**Relevance:** Directly relevant to all three systems as production API consumers.
**Key sources:** Paunova (Medium, 2026, practitioner); Parloa knowledge hub (vendor blog); Fuchs “Your AI Detections Are Rotting” (Medium, April 2026, practitioner).
**Recommended action:** **Investigate immediately** — cheap to implement (canary suite + daily runs + behavioral monitoring).

### Blind spot: Evaluation economics with valid statistical guarantees

**What it is:** Three concrete protocols: **FAQ** (arXiv 2601.20251, Jan 28) achieves up to 5× effective sample size gain with valid frequentist CIs via proactive active inference. **ATLAS** (arXiv 2511.04689 v2 Feb 2) achieves up to 90% item reduction with IRT-based adaptive testing plus psychometric validation (M2/RMSEA). **Efficient Benchmarking of AI Agents** (arXiv 2603.23749, Mar 24) shows **rank-preservation, not score-reproducibility, is the realistic goal** under scaffold shift — the mid-difficulty filter (30–70% historical pass rate) cuts 44–70% of tasks while preserving rank fidelity. Greedy task selection *actively underperforms random sampling under scaffold shift*.
**Why the previous prompt missed it:** Classical selective prediction scoped AURC/selective accuracy; eval-budget allocation under valid statistical inference is a distinct problem with a different toolkit (IRT, sequential testing, active inference).
**Current state of research:** Rapidly developing. **ConSol’s** SPRT early-stopping (cited throughout in-window work, dismisses Adaptive Consistency for Type-I inflation) is settling into the standard building block.
**Relevance:** All three systems. For A/B testing prompts/models, adopt adaptive stopping (expect 20–50 items to converge vs. N=1000). For agent CI, adopt the mid-difficulty filter.
**Key sources:** FAQ (arXiv 2601.20251); ATLAS (arXiv 2511.04689); Efficient Benchmarking of AI Agents (arXiv 2603.23749); ConSol (arXiv 2503.17587).
**Recommended action:** **Investigate immediately** for cost control.

### Blind spot: Refusal and over-refusal as eval-validity confound

**What it is:** Partially addressed across multiple in-window works but no single paper fully formalizes. BFCL V4’s “irrelevance detection” task partially captures when agents should abstain from tool calls.
**Why the previous prompt missed it:** Abstention was framed as selective-prediction (confidence-based) rather than as safety-alignment behavior interfering with classifier metrics.
**Current state of research:** Nascent. No concrete protocol.
**Relevance:** Affects (2) RAG classifier and (3) planner.
**Key sources:** BFCL V4 (gorilla.cs.berkeley.edu/blogs/15_bfcl_v4_web_search.html, lab blog).
**Recommended action:** **Monitor.**

### Blind spot: Meta-evaluation of benchmarks as first-class research

**What it is:** Benchmark² (arXiv 2601.03986, Jan 7 2026) proposes three benchmark-quality metrics — Cross-Benchmark Ranking Consistency, Discriminability Score, Capability Alignment Deviation (penalizing within-family rank violations). Selective filtering preserves fidelity at 35% of original items. “When AI Benchmarks Plateau” (arXiv 2602.16763) provides uncertainty-aware saturation index across 60 benchmarks, with the surprising finding that **private test splits provide no protective effect against saturation**. Hardy’s signed-isotonic-R² bad-item detector (arXiv 2603.24999) outperforms classical test theory and IRT at flagging annotation errors.
**Why the previous prompt missed it:** Evaluation quality was assumed; methods for *evaluating the evaluator* at the benchmark level were out of scope.
**Current state of research:** Rapidly developing.
**Relevance:** Direct tool for curating internal eval sets for all three systems.
**Key sources:** Benchmark² (arXiv 2601.03986); When AI Benchmarks Plateau (arXiv 2602.16763); Hardy (arXiv 2603.24999).
**Recommended action:** **Investigate immediately** before expanding internal eval suites.

-----

## Section 2 — Emerging directions (Feb–Apr 2026)

### Emerging: Trajectory-level scoring displacing step-level and outcome-level agent eval

**First appeared / gained traction:** Consolidated in Feb–Apr 2026 across multiple independent groups.
**What’s new:** Jan 2026 understanding was “pass@1 + occasional judge-rated traces.” April 2026 understanding is task-decomposed-into-constraints, each verified against the trajectory. TRACE (WWW’26), HAL (ICLR 2026), ATBench, constraint-based BookingArena, and c-CRAB all converge on this frame.
**Momentum:** 6+ papers, major labs (Princeton/Stanford HAL, Anthropic Claude Code telemetry, LG AI BookingArena). Inspect Scout open-sourced log-analysis pipeline with same philosophy.
**Maturity:** Rapidly developing.
**Relevance:** Direct for (1) and (3).
**Key sources:** TRACE (arXiv 2602.21230, WWW’26); HAL (arXiv 2510.11977, ICLR 2026, https://hal.cs.princeton.edu/); ATBench (arXiv 2604.02022).

### Emerging: Process reward models under active validation — not yet consensus-endorsed

**First appeared / gained traction:** ToolPRMBench (Jan 2026), CUARewardBench, GUI-PRA (ICLR 2026), AgentPRM/InversePRM extensions.
**What’s new:** Generic PRMs (math-trained) transfer poorly to tool use (ToolPRMBench). PRMs suffer “lost in the middle” on long GUI histories. Implicit-PRM approaches learn step rewards from outcome signals, sidestepping expensive step labels.
**Momentum:** 4+ papers in window.
**Maturity:** Early; validation protocols stabilizing, deployment patterns not yet. Tentative position: PRMs as judges work for narrow domains (math, specific APIs); as general trajectory verifiers they remain brittle.
**Relevance:** (1) and (3) if the practitioner considers adding step-level rewards.
**Key sources:** ToolPRMBench (arXiv 2601.12294); CUARewardBench (arXiv 2510.18596); AgentPRM (arXiv 2502.10325).

### Emerging: Programmatic / deterministic evaluation as counter-movement to LLM-as-judge

**First appeared / gained traction:** Culminated Feb–Apr 2026 from multiple directions.
**What’s new:** MCP-Atlas (arXiv 2602.00933) explicitly critiques “subjective LLM-as-judge metrics” in favor of claims-based programmatic scoring. IFEval-FC embeds verifiable format constraints in JSON-schema with fully algorithmic checks. Terragni’s manifesto “From Untestable to Testable” (arXiv 2603.24774) + LLMORPH (arXiv 2603.23611) position **metamorphic testing** as the primary deterministic oracle. ICLR 2026 VerifAI-2 workshop benchmarked unit-test-based verification > LLM-judge on hard coding.
**Momentum:** 5+ papers; Meta’s production ACH + JiT “Dodgy Diff” validates at scale. Langfuse shipped boolean judge scores Apr 8, 2026.
**Maturity:** Rapidly developing; architectural pattern of “LLM-judge for cheap first pass, defer to deterministic oracle when stakes are high” is stabilizing.
**Relevance:** Direct for (1); applicable via MT to (2) without labels; SMT verification applicable to (3).
**Key sources:** MCP-Atlas (arXiv 2602.00933); LLMORPH (arXiv 2603.23611); VerifAI-2 workshop paper (openreview.net/forum?id=AP8ZlN7lwU); Meta JiT (InfoQ Apr 16 2026).

### Emerging: Monitorability displacing faithfulness as the pragmatic CoT target

**First appeared / gained traction:** Feb–Apr 2026 convergence.
**What’s new:** MonitorBench (arXiv 2603.28590) introduces adversarial stress-testing (all tested models can intentionally reduce monitorability by up to 30%). “Monitorability as a Free Gift” (arXiv 2602.03978) shows RLVR monitorability gains come from entropy reduction and prompt attention, **not** stronger causal reliance on traces. Anthropic’s Feb 2026 risk report explicitly does *not* rely heavily on CoT monitorability in its safety claims. Redwood’s Apr 14 post documents Anthropic’s two accidental cases of training against CoT.
**Momentum:** Frontier labs (Anthropic, METR, OpenAI CoT monitorability eval suite Apr 2026) align; community split on “evaluate CoT vs. treat as latent.”
**Maturity:** Rapidly developing.
**Relevance:** All three systems — monitorability is the tractable target for runtime gating.
**Key sources:** MonitorBench (arXiv 2603.28590); Monitorability as a Free Gift (arXiv 2602.03978); METR CoT controllability (metr.org/blog/2026-04-01-fine-tuning-cot-controllability/).

### Emerging: Evidence coverage (nugget-level) displacing relevance ranking for retrieval

**First appeared / gained traction:** FreshStack (NeurIPS 2025 D&B, propagating through 2026) + Hamel Husain’s RAG series (Mar 2026).
**What’s new:** Traditional IR metrics (MRR, NDCG) optimized for “rank the one relevant doc at #1”; RAG needs “fetch every piece of evidence.” **Coverage@20** (% of unique nuggets supported) + **α-nDCG@10** (diversity) replace single-rank metrics. Nugget judgments over real Stack Overflow + GitHub content.
**Momentum:** Growing adoption by practitioners; Hamel’s synthesis is the canonical practitioner reference.
**Maturity:** Early adoption.
**Relevance:** Direct for (2) RAG classifier.
**Key sources:** FreshStack (arXiv 2504.13128); Hamel Husain “RAG evals part 2” (hamel.dev/notes/llm/rag/p2-evals.html, practitioner).

### Emerging: Retrieval as tool use (autonomy decomposition)

**First appeared / gained traction:** A-RAG (arXiv 2602.03442, Feb 3 2026).
**What’s new:** Exposes three retrieval tools (keyword_search, semantic_search, chunk_read) to the model and evaluates on three autonomy axes — **Autonomous Strategy, Iterative Execution, Interleaved Tool Use**. “How You Ask Matters!” (arXiv 2604.10745) introduces three robustness axes for adaptive RAG: answer robustness, computational robustness (retrieval-trigger consistency), retrieval-decision robustness. **Negative result**: both logit-based and generation-based adaptive-retrieval methods are consistently vulnerable to human rewrites and typos.
**Momentum:** 3+ papers; reframes RAG eval around “when to retrieve” and “what granularity.”
**Maturity:** Early.
**Relevance:** Direct for (2) and (3).
**Key sources:** A-RAG (arXiv 2602.03442); “How You Ask Matters!” (arXiv 2604.10745).

### Emerging: Automated behavioral evaluation pipelines (Bloom, Docent, Inspect Scout)

**First appeared / gained traction:** Anthropic Bloom (April 2026), HAL’s Docent log analyzer (ICLR 2026), Inspect Scout (arXiv 2604.09563).
**What’s new:** Standard ontology for log-analysis rubrics: instruction-following, tool use, verification, self-correction, **cheating/gaming**, environmental barriers. Bloom’s four-stage pipeline (understand → ideate → rollout → judge+meta-judge).
**Momentum:** Lab-scale deployments converging on similar ontology.
**Maturity:** Alpha research (Bloom) to beta (Inspect Scout).
**Relevance:** (1) and (3) auditing.
**Key sources:** Anthropic Bloom (anthropic.com, Apr 2026); Inspect Scout (arXiv 2604.09563).

### Emerging: IRT / CAT from psychometrics for evaluation economics

**First appeared / gained traction:** ATLAS (arXiv 2511.04689 v2 Feb 2), Trismik continuous-CAT (arXiv 2601.13885 Jan 2026), medical-CAT (Feb 2026).
**What’s new:** First production-scale CAT for LLMs — 90% item reduction at matched measurement precision; 3–6% of items revealed with negative discrimination (annotation errors); 23–31% of models shift >10 ranks comparing IRT ability vs. raw accuracy.
**Momentum:** Trismik productizing as a category; HELM adopting Rasch models.
**Maturity:** Growing.
**Relevance:** All three systems for regression-test compression.
**Key sources:** ATLAS (arXiv 2511.04689); Trismik continuous-CAT (arXiv 2601.13885).

-----

## Section 3 — Consensus shifts

### Shift: SWE-bench Verified retired as a frontier signal

**Previous consensus (January 2026):** SWE-bench Verified was the gold standard for coding-agent capability, quoted in every major frontier release.
**Current position (April 2026):** OpenAI publicly abandoned reporting on it (Feb 23, 2026). Their audit of the hardest 27.6% subset found **59.4% had flawed tests** rejecting correct solutions; all major frontier models could reproduce verbatim gold patches, evidencing training contamination. “SWE-Bench Illusion” (arXiv 2506.12286 v4) showed 76% path accuracy from issue text alone on Verified vs. 53% on held-out repos.
**What caused the shift:** Contamination evidence via CoT leakage + score saturation + Princeton/OpenAI audits.
**Strength:** **Strong.** Adopted across OpenAI and Artificial Analysis. Caveat: LessWrong’s Jonathan Gabor audit (Feb 24) found SWE-bench Pro is itself worse on test leniency — the replacement is contested.
**Impact on practitioner:** System (1) must stop citing SWE-bench Verified in procurement/capability claims. Invest in private expert-authored golden sets.
**Sources:** openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ (primary lab post); SWE-Bench Illusion (arXiv 2506.12286).

### Shift: Every top agent benchmark is exploitable to near-100%

**Previous consensus:** Agent benchmarks (WebArena, OSWorld, GAIA, Terminal-Bench, SWE-bench, FieldWorkArena) measure real capability.
**Current position (April 2026):** Berkeley RDI built an automated exploit agent scoring near-perfect on 8 benchmarks without solving tasks — `conftest.py` hook hijacks pytest in SWE-bench (100%), `file://` URL reads gold answers in WebArena (~100%), trojanized `curl` wrapper in Terminal-Bench (100%). METR (June 2025) had already reported 30%+ reward-hacking rates for o3 and Claude 3.7 Sonnet.
**What caused the shift:** Growing model autonomy surfaces unsanitized benchmark harnesses.
**Strength:** **Moderate–strong**.
**Impact on practitioner:** Treat all external benchmark scores as upper bounds. Never `eval()` untrusted input. Adversarially test your own LLM-as-judge against agent-generated outputs.
**Sources:** Wang, Mang, Cheung, Sen, Song — Berkeley RDI “How We Broke Top AI Agent Benchmarks” (April 2026, preprint).

### Shift: Binary pass/fail dominates; Likert scales are antipattern

**Previous consensus:** Likert 1–5 captures gradual improvement.
**Current position:** Hamel Husain + Shreya Shankar’s “LLM Evals FAQ” (Jan 15, 2026; trained 4,500+ engineers) is blunt: “Likert scales are a trap. Binary decisions force clarity and are far more actionable.” OpenAI Product Growth interview (Feb 2026): “LLMs are not very good at numbered scales.” Langfuse shipped Boolean LLM-judge scores Apr 8, 2026.
**What caused the shift:** Inter-annotator noise on Likert; criteria-drift research (Shankar UIST 2024); tooling catching up.
**Strength:** **Strong** at practitioner level.
**Impact on practitioner:** All three systems — rewrite Likert-style rubrics as decomposed binary checks with written critique for nuance.
**Sources:** hamel.dev/blog/posts/evals-faq/; Langfuse changelog (Apr 8 2026).

### Shift: Batch invariance — not floating point + concurrency — is the true determinism problem

**(See Blind spot for details.)** The field-wide practitioner reframe is strong; implications are that temperature-0 determinism on shared APIs is impossible without batch-invariant kernels, and eval pipelines must budget for residual variance via uncertainty-accounting CIs.

### Shift: Trajectory-level > step-level evaluation for agents

**Previous consensus:** Step-level PRMs are the path forward.
**Current position:** Trajectory-aware utility (TRACE) and constraint-based scoring are the dominant frame; step-level is a diagnostic layer, not primary metric. Pass@1 → pass^k → reliability surfaces.
**Strength:** **Moderate** — convergent across 4+ groups but not universal.
**Sources:** TRACE (arXiv 2602.21230); BookingArena (arXiv 2602.12544); Beyond Pass@1 (arXiv 2603.29231).

### Shift: Retrospective MIAs insufficient; prospective watermarking is the only provable contamination proof

**(See Blind spot.)** Strong at academic level but not yet operationalized in most practitioner workflows.

### Shift: Private, held-out, expert-authored benchmarks > public leaderboards

**Previous:** Teams publish on MMLU, GSM8K, HumanEval, SWE-bench.
**Current:** Frontier labs moving to privately-authored (OpenAI GDPVal, Anthropic Bloom, FrontierMath, HLE). Benchmark² shows sub-1% gaps and prevalence of rank-inconsistent items on MMLU, MATH-500, ARC.
**Strength:** **Strong** at frontier; **moderate** for practitioners (cost of authoring).
**Impact on practitioner:** Invest engineering time in private golden sets per system.

### Shift: Distributional metrics displacing single-scalar accuracy

**Previous:** Report accuracy; maybe mean ± std.
**Current:** Report variance, tail risk, subgroup calibration, consistency/invariance gaps (AMST, GeoRepEval). Behavioral drift monitoring targets length, tone, refusal rate, hallucination rate — not only accuracy.
**Strength:** **Moderate**; still emerging standardization.

-----

## Section 4 — Dismissed or superseded approaches

### Dismissed: Likert 1-5 rubrics

**What it was:** Multi-point quality rating (1–5 / 1–7).
**Why promising (Jan 2026):** Perceived granularity; NLP tradition.
**Why dismissed:** Annotator disagreement on adjacent points; middle-value bias; LLM judges poor at numeric scales.
**Replaced by:** Decomposed binary pass/fail with written critique.
**Sources:** Husain & Shankar FAQ; Langfuse boolean scores.

### Dismissed: Eval-driven development (“write evaluators first, TDD-style”)

**What it was:** TDD analog — write evaluators before features.
**Why promising:** Mirrored SE discipline.
**Why dismissed:** Husain & Shankar: “sounds appealing but creates more problems than it solves. Unlike traditional software, LLMs have infinite surface area.” Cannot enumerate failure modes pre-data.
**Replaced by:** Data-first loop — build MVP → error-analyze ~100 real traces → derive binary metrics → automate.

### Dismissed: Generic off-the-shelf “hallucination,” “coherence,” “helpfulness” scorers as primary metrics

**What it was:** Drop in RAGAS/DeepEval/LangSmith defaults as primary dashboards.
**Why promising:** Zero-setup, vendor-supplied.
**Why dismissed:** Domain-agnostic → diagnose nothing about your app’s failures; often poorly calibrated. “When Judgment Becomes Noise” (arXiv 2509.20293) shows >90% unexplained variance on Arena-Hard Auto.
**Replaced by:** Custom error-analysis-derived binary evaluators validated via TPR/TNR against human expert on held-out set.

### Dismissed: Same-family LLM-as-judge

**What it was:** Judge with the same or related model used for task.
**Why promising:** Strongest model generally best judge.
**Why dismissed:** Preference Leakage (ICLR 2026) confirms systematic bias toward related students.
**Replaced by:** Cross-family judging + multi-agent debate + reference-free consistency metrics.

### Dismissed: SWE-bench Verified (specifically — not all coding benchmarks)

**(See Shift.)** Replaced by SWE-bench Pro + GDPVal + privately-authored internal sets.

### Dismissed: Standalone MIA as contamination proof

**What it was:** Use membership-inference to prove “this model trained on X.”
**Why promising:** Direct hypothesis test.
**Why dismissed:** No calibrated null hypothesis; context-dependent; arXiv 2512.13352 v3 — “neither universally strong nor uniformly weak.”
**Replaced by:** Pre-release watermarking / backdoor canaries (DyePack); diagnostic probes (SWE-Bench Illusion’s path-identification).

### Dismissed: Adaptive Consistency’s Bayesian early-stop

**What it was:** Aggarwal et al. 2023 Bayesian early-stopping for self-consistency.
**Why dismissed:** ConSol analysis shows inflated Type-I error under repeated peeking.
**Replaced by:** Mixture-SPRT with proper Type-I control (ConSol, arXiv 2503.17587).

### Dismissed: Harness-in-container execution without sandboxing gold files

**(See Shift B.)** Replaced by out-of-container grading, parser-less exact-feature extraction, no public gold URLs.

### Weakened (not fully dismissed): Classical tabular drift methods (KS, PSI, JS divergence on inputs)

Flagged as insufficient for LLMs — misses provider-side weight changes, prompt drift, context rot. Replaced by output-level behavioral monitoring.

-----

## Section 5 — Adjacent field imports

### Import: Item response theory & computerized adaptive testing from educational psychometrics

**Original field:** Educational measurement (SAT, GRE, USMLE).
**How adapted:** Calibrate items with 3PL IRT (difficulty, discrimination, guessing); use Fisher information to select items per model’s current ability estimate; stop when SE < threshold. 90% item reduction at matched precision. Reveals 3–6% of items have negative discrimination (annotation errors). Trismik extends to continuous scores via heteroskedastic-normal response distribution.
**Current adoption:** Growing — ATLAS (ICLR 2026), Trismik continuous-CAT, medical-CAT, PSN-IRT, Stanford CRFM Rasch-in-HELM. Trismik is productizing as a category.
**Applicability:** All three systems — use for regression testing with 10× cost reduction; use to flag bad eval items.
**Key sources:** ATLAS (arXiv 2511.04689, ICLR 2026); Balkir et al. (arXiv 2601.13885); Zheng et al. (arXiv 2603.23506).

### Import: Metamorphic testing from software engineering

**Original field:** Software testing — for programs without complete oracles (e.g., compilers, ML).
**How adapted:** Transform input with known output relationship (paraphrase preserves meaning; negation flips sentiment), check invariance/covariance of LLM output. Oracle-free, label-free. LLMORPH (arXiv 2603.23611) runs 36 metamorphic relations across 4 NLP tasks, 561K test executions, detecting faults without labels.
**Current adoption:** Growing — Terragni manifesto + LLMORPH tool + ICSE-track work.
**Applicability:** (2) RAG classifier for label-free invariance checks; (1) for code-transform invariance (rename variables → review verdict shouldn’t flip).
**Key sources:** LLMORPH (arXiv 2603.23611); Terragni “From Untestable to Testable” (arXiv 2603.24774).

### Import: Mutation testing from software engineering

**Original field:** Software testing — inject faults, measure whether tests kill them.
**How adapted:** Meta’s ACH system — LLM generates mutants representing real compliance concerns, generates tests to kill them. 10,795 Android Kotlin classes, 9,095 mutants, 571 privacy tests. Meta JiT “Dodgy Diff” inverts for PR-time change-aware test generation — **4× bug-detection improvement, up to 20× on meaningful failures**.
**Current adoption:** Production at Meta scale; referenced across 2026 SE literature.
**Applicability:** **Direct for (1) code-review agent** — pattern for the test-based verification layer.
**Key sources:** Meta ACH (dl.acm.org/doi/10.1145/3696630.3728544); Meta JiT (InfoQ Apr 16 2026).

### Import: Formal verification / SMT from programming languages

**Original field:** Program verification.
**How adapted:** LLM generates specs (ACSL for C, Z3 constraints); formal verifier provides deterministic ground truth. Beg et al. (arXiv 2602.13851) finds LLM-generated specs are systematically weaker than rule-based ones — solver timeout rate is itself a quality signal. FregeLogic (SemEval 2026) uses Z3 as tiebreaker when LLM ensemble disagrees.
**Current adoption:** Early; hybrid “LLM-judge for easy, SMT for disputed” pattern emerging.
**Applicability:** (3) planning when plans emit constraints; (1) for rules-engine code review.
**Key sources:** Beg et al. (arXiv 2602.13851); FregeLogic at SemEval 2026 (amazon.science).

### Import: Classical test theory & construct validity from psychometrics

**Original field:** Psychological measurement.
**How adapted:** Test-retest reliability, internal consistency (Cronbach’s α, McDonald’s ω), convergent/discriminant validity applied to LLM eval suites. “LLM Psychometrics” survey (arXiv 2505.08245 v3 Mar 11 2026) frames the field around construct → method → validation. IRT-GRM applied to LLM judges themselves (arXiv 2602.00521) — diagnoses which judges function as reliable measurement instruments.
**Current adoption:** Growing — widely cited NeurIPS 2025 construct-validity review propagating into 2026 design-checklists.
**Applicability:** (2) RAG classifier — validate faithfulness scores have proper convergent/discriminant structure before trusting.
**Key sources:** arXiv 2505.08245 v3 (survey); arXiv 2602.00521 (judge-as-instrument).

### Import: Clinical validity scales from psychological assessment

**Original field:** MMPI-3, PAI — validity scales detect when a test profile is uninterpretable (response style, inattention).
**How adapted:** Cacioli (arXiv 2604.17707, April 2026) builds validity screens (analog of VRIN/TRIN) for LLM confidence signals; validity-flagged models show flat/inverted risk-coverage curves.
**Current adoption:** Experimental — single paper but methodologically novel.
**Applicability:** (2) RAG classifier — screen model confidence before using for routing/abstention.
**Key sources:** Cacioli (arXiv 2604.17707).

### Import: FMEA from reliability engineering

**Original field:** Aerospace, automotive, medical device failure analysis.
**How adapted:** Enumerate failure modes (hallucination, prompt injection, spec violation), assign severity × occurrence × detection scores, compute Risk Priority Number, target top-N. El Hassani et al. in Cambridge’s *Design Science* (Apr 13 2026); Springer IJSAEM Charan et al. combine FMEA with RAG.
**Current adoption:** Emerging — applying FMEA to LLM systems is still nascent.
**Applicability:** (3) planning — prioritize which failure modes get deterministic checks first.
**Key sources:** El Hassani et al. (Cambridge Design Science, Apr 2026).

### Import: Sequential probability ratio testing from statistics

**Original field:** Industrial quality control, clinical trials.
**How adapted:** ConSol’s mixture-SPRT early-stop for self-consistency sampling with proper Type-I control; referenced across 2026 work. Complements FAQ’s proactive active inference for valid CIs under adaptive sampling.
**Current adoption:** Growing — established building block.
**Applicability:** All three systems for cheap evaluation.
**Key sources:** ConSol (arXiv 2503.17587); FAQ (arXiv 2601.20251).

### Import: Differential-privacy-style noise mechanism for judge bias bounds

**Original field:** Differential privacy.
**How adapted:** Feuer et al. (arXiv 2603.05485) adapts the Gaussian-noise mechanism to bound *bias* influence rather than privacy leakage. Achieves (τ=0.5, δ=0.01) bias-bounded guarantees on Arena-Hard-Auto with 4 judges, retaining 61–99% ranking correlation.
**Current adoption:** Experimental.
**Applicability:** Where LLM-judge is unavoidable — wrap with A-BB for formal guarantees.
**Key sources:** Feuer et al. (arXiv 2603.05485).

### Import: Survey methodology — response-bias taxonomy for judge bias

**Original field:** Survey research response biases.
**How adapted:** JudgeBiasBench (arXiv 2603.08091) catalogs 12 judgment biases across 4 dimensions with controlled injection pipeline.
**Current adoption:** Early.
**Applicability:** Diagnostic layer for any LLM-judge in production.

-----

## Section 6 — Evaluation infrastructure updates

### Tool: Inspect AI (UK AISI)

**What it does:** Open-source framework for LLM/agent evals; de facto public-sector standard (used by Anthropic, DeepMind, METR, Apollo).
**New since January 2026:** Releases through **v0.3.209 (Apr 20, 2026)**. Agent Bridge now supports OpenAI Responses API, Anthropic API, Gemini API; `sandbox_agent_bridge` runs proxy on port 13131 for agents in any language. Timeline/BranchEvent for branched rollouts; async `samples_df()` (~50× faster); MLflow hooks. **Inspect Cyber** spun off as separate open-source package.
**Maturity:** Beta on PyPI, production-used by frontier labs.
**Relevance:** Strongest single pick for (3) planning agent and for (1) when sandboxing required.
**URL:** https://inspect.aisi.org.uk/

### Tool: DeepEval (Confident AI)

**What it does:** Pytest-style framework; 50+ metrics including RAG triad.
**New since January 2026:** Release Apr 14 2026. Agent metrics (task completion, tool correctness, plan adherence, plan quality); automatic trace detection replacing rigid test-case format; **ArenaGEval** for test-case comparison; multi-turn conversational goldens; **Confident AI MCP server** for Claude Code / Cursor integration.
**Maturity:** Production (13k stars, 3M monthly downloads).
**Relevance:** Best for (2) RAG classifier.
**URL:** https://deepeval.com

### Tool: Langfuse

**What it does:** OSS LLM observability + eval + prompt management (Python SDK v4 rewritten March 2026).
**New since January 2026:** Versioned-dataset experiments (Feb 11); per-operation LLM-judge (Feb 13); CLI for CI/CD (Feb 17); observation-only immutable data model (Mar 10); categorical (Mar 20) and **Boolean LLM-judge scores (Apr 8)** — directly implementing the binary-eval consensus; Experiments as first-class concept (Apr 13).
**Maturity:** Production; dominant OSS self-host.
**Relevance:** Best self-hostable choice for all three systems.
**URL:** https://langfuse.com

### Tool: Braintrust

**What it does:** Integrated eval + tracing + prompt mgmt + online scoring.
**New since January 2026:** **$80M Series B at $800M valuation (Feb 2026)**; **Loop agent** (autonomous eval-running, test-case generation, prompt/scorer iteration); removed user-based pricing; US/EU data-plane selection; MCP server + CLI; **Brainstore** observability DB.
**Maturity:** Production (Notion, Stripe, Vercel, Airtable, Ramp).
**Relevance:** Best if single integrated workflow across all three systems.
**URL:** https://www.braintrust.dev

### Tool: TruLens 2.6

**What it does:** Open-source agent + RAG eval and tracing (Snowflake-backed).
**New since January 2026:** **v2.6 (Feb 3, 2026)** introduces **Agent’s GPA** — reference-free framework evaluating alignment of Goal, Plan, Actions; benchmarked to cover 95% of errors in open-source TRAIL dataset. New `Metric` class with native OTel span selection; MCP span type for tool-call annotation; PostgreSQL support.
**Maturity:** Production (active Snowflake-backed development).
**Relevance:** **Top candidate for (3) planning agent** — Agent’s GPA is purpose-built for plan-alignment.
**URL:** https://www.trulens.org

### Tool: Promptfoo (now OpenAI-acquired)

**What it does:** Declarative YAML evals + red-teaming; 300k+ developers.
**New since January 2026:** **Acquired by OpenAI** (remains MIT). New red-team strategies: **Meta Agent** (adaptive taxonomy attacker), **Hydra** (multi-turn adaptive with scan-wide memory). Multi-input red-teaming config; framework-filtering (NIST/OWASP/EU AI Act); multilingual test generation in low-resource languages.
**Maturity:** Production.
**Relevance:** Complement for (1) (prompt-injection/tool-abuse attacks) and (2) (retrieval manipulation).
**URL:** https://github.com/promptfoo/promptfoo

### Tool: Arize Phoenix + AX

**What it does:** Framework-agnostic, OpenTelemetry/OpenInference observability + eval.
**New since January 2026:** OOTB instrumentation for OpenAI Agents SDK, Claude Agent SDK, LangGraph, Mastra, Vercel AI SDK, Google ADK. Agent-centric evals (tool use, planning, reflection); AI debugging assistant “Alyx”; Gartner Market Guide recognition Q1 2026.
**Maturity:** Production (Apache-2.0 OSS Phoenix; commercial AX).
**Relevance:** Preferred for teams with combined ML+LLM + OpenTelemetry-first infra.
**URL:** https://phoenix.arize.com

### Tool: Ragas 0.4 line

**What it does:** RAG-specific eval library.
**New since January 2026:** Releases 0.4.0 (Dec 3, 2025) → 0.4.3 (Jan 13, 2026). Migrated core metrics to modular `BasePrompt` architecture with `ragas.metrics.collections` API; deprecated legacy metrics; **experiments-first paradigm**; `generate_with_chunks`; multimodal (vision-capable) faithfulness. **Ownership/fork moved from Explodinggradients to vibrantlabsai** — the eval library you install in 2026 is materially different from 2025. Pin versions carefully.
**Maturity:** Production.
**Relevance:** Must-know for (2) RAG classifier.
**URL:** https://pypi.org/project/ragas/

### Tool: Anthropic Bloom

**What it does:** Open-source agentic framework for automated behavioral evaluations.
**New since January 2026:** Four-stage pipeline (understand → ideate → rollout → judge+meta-judge); benchmarks released across 16 models on 4 alignment behaviors.
**Maturity:** Alpha research.
**Relevance:** (3) planning safety testing.
**URL:** anthropic.com (Apr 2026 research post).

### Tool: OpenAI Evals

**What it does:** Hosted + open-source eval framework.
**New since January 2026:** Trace Evals, Datasets, Prompt Optimization; **third-party model support** (Claude, Gemini); **GDPVal** privately-authored benchmark with expert graders recommended over public benchmarks.
**Maturity:** Production.
**URL:** https://evals.openai.com

### Tool: Weights & Biases Weave

**New since January 2026:** `eval_results/query` API; OpenAI Agents TS SDK; LLM-judge image/video scoring; **Agent Optimizer with 6 automated prompt-refinement algorithms**; **local SLM scorers** for hallucination/context-relevance (no API cost); Online Evaluation Rules.
**Maturity:** Production.
**URL:** https://wandb.ai/site/weave

### Tool: HAL-harness + Docent

**New since January 2026:** ICLR 2026 — parallelized evaluation across hundreds of VMs; three-axis analysis (model × scaffold × benchmark); automated Docent log-analysis with rubric ontology (instruction-following, tool use, verification, self-correction, cheating/gaming, environmental barriers). 21,730 rollouts, $40K total.
**Maturity:** Production (open-source).
**Relevance:** Both (1) and (3).
**URL:** https://hal.cs.princeton.edu/

-----

## Section 7 — Tier 1 papers (Score ≥ 7)

### HAL: Holistic Agent Leaderboard

- **Score:** 14/10 | **Profiles:** 1, 10
- **Published:** 2025-10 (arXiv 2510.11977) / ICLR 2026 accepted
- **URL:** https://hal.cs.princeton.edu/

**Why not in previous prompt:** Orchestration + multidimensional reliability dashboard + log-analysis rubrics are distinct from LLM-as-judge bias.
**Key findings:** Discovers TAU-bench Few-Shot had training-data leakage via automated log analysis; Docent rubric ontology is becoming de facto standard; higher reasoning-effort settings *reduce* accuracy in 21/36 HAL runs.
**Methodology contribution:** Parallelized evaluation harness decoupling scaffold from benchmark; three-axis (model × scaffold × benchmark) analysis; standardized log-analysis rubrics.
**Applicability:** (1) judge/evaluator filter; (3) planner trajectories.

### ReliabilityBench — LLM Agent Reliability Under Production-Like Stress

- **Score:** 14/10 | **Profiles:** 1, 2
- **Published:** 2026-01-03 (arXiv 2601.06112)
- **URL:** https://arxiv.org/abs/2601.06112

**Why not in previous prompt:** Reliability-engineering framing (pass^k, perturbation ε, fault-tolerance λ) as first-class metrics.
**Key findings:** **Reflexion self-reflection amplifies fault impact** (10.0% degradation vs. ReAct’s 7.5%) — premium negative result. Action Metamorphic Relations defining correctness via end-state equivalence.
**Methodology contribution:** Chaos-engineering fault injection (timeouts, rate limits, schema drift) in CI.
**Applicability:** (3) planner fault-injection; (1) test-harness flake resilience.

### Beyond pass@1: Reliability Science for Long-Horizon Agents

- **Score:** 14/10 | **Profiles:** 1
- **Published:** 2026-03 (arXiv 2603.29231)
- **URL:** https://arxiv.org/html/2603.29231v1

**Why not in previous prompt:** Duration-stratified reliability is a new measurement axis.
**Key findings:** Reliability decays **super-linearly** with task duration; domain-stratified (SE 0.90→0.44 over duration buckets).
**Methodology contribution:** Adapts MTBF/exponential-decay vocabulary; 23,392 episodes in a matrix design.
**Applicability:** (3) multi-step plans; (1) when reviewer chains lengthen.

### c-CRAB: Code Review Agent Benchmark

- **Score:** 14/10 | **Profiles:** 1, 8
- **Published:** 2026-03-24 (arXiv 2603.23448)
- **URL:** https://arxiv.org/abs/2603.23448

**Why not in previous prompt:** Test-driven review scoring is a fundamentally different judge protocol.
**Key findings:** All major code-review agents (PR-agent, Devin, Claude Code, Codex) ≤32% pass vs. 100% for humans; union = 41.5%; agent reviews cover different axes than humans.
**Methodology contribution:** Auto-generate executable tests from human review; credit agent review if its code changes make tests pass.
**Applicability:** **Direct drop-in for (1).**

### ToolPRMBench — Process Reward Models for Tool-Using Agents

- **Score:** 14/10 | **Profiles:** 1, 7
- **Published:** 2026-01-18 (arXiv 2601.12294)
- **URL:** https://arxiv.org/abs/2601.12294

**Why not in previous prompt:** Meta-evaluation of PRMs as verifiers.
**Key findings:** Generic PRMs (math-trained) transfer poorly to tool use — premium negative result.
**Methodology contribution:** First step-level PRM benchmark for tool-using agents; offline+online sampling design; multi-LLM verification to reduce label noise.
**Applicability:** (1) security/logic/resource frames if tool-calling; (3) planner tool-call validation.

### TRACE: Trajectory-Aware Comprehensive Evaluation

- **Score:** 12/10 | **Profiles:** 1, 3
- **Published:** 2026-02-05 (arXiv 2602.21230) / WWW’26
- **URL:** https://arxiv.org/abs/2602.21230

**Why not in previous prompt:** Operationalizes trajectory utility beyond judge/calibration.
**Key findings:** Hierarchical Trajectory Utility Function combining accuracy, process efficiency, cognitive quality with **evidence grounding per step**; frames Pass@1 as “high-score illusion.”
**Methodology contribution:** **Scaffolded Capability Assessment** — binary-search minimum guidance required for success.
**Applicability:** (3) planning (scaffolded probe); (2) RAG (evidence-grounding penalization).

### Preference Leakage (ICLR 2026)

- **Score:** 10/10 | **Profiles:** 4
- **Published:** v3 2026-03-04 (arXiv 2502.01534)
- **URL:** https://arxiv.org/abs/2502.01534

**Why not in previous prompt:** Specific lineage-based contamination pattern distinct from general judge bias.
**Key findings:** Judges systematically favor related student models across three circular relationships.
**Methodology contribution:** Lineage-distance protocol — require judge family ≠ generator family ≠ tested family.
**Applicability:** (2) RAG classifier + (3) planner if using related models.

### OpenAI: “Why we no longer evaluate SWE-bench Verified”

- **Score:** 9/10 | **Profiles:** 4, 11
- **Published:** 2026-02-23
- **URL:** https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

**Why not in previous prompt:** First frontier lab to publicly retire a flagship benchmark.
**Key findings:** 59.4% of hardest-subset failures had flawed tests; verbatim gold-patch reproduction evidence of contamination.
**Methodology contribution:** Contamination audit protocol (CoT-leak inspection + verbatim-patch match + held-out splits).
**Applicability:** (1) — stop citing SWE-bench Verified; pivot to private splits.

### When AI Benchmarks Plateau

- **Score:** 9/10 | **Profiles:** 4
- **Published:** 2026-02 (arXiv 2602.16763)
- **URL:** https://arxiv.org/abs/2602.16763

**Why not in previous prompt:** Meta-evaluation of benchmarks as first-class object.
**Key findings:** ~50% of 60 benchmarks saturate; **private test splits provide no protective effect**; expert-curated resists saturation better than crowdsourced.
**Methodology contribution:** Uncertainty-aware saturation index tied to statistical separability.
**Applicability:** All three — informs external benchmark selection.

### LENS: Distribution Shift in User Prompts

- **Score:** 9/10 | **Profiles:** 2, 5
- **Published:** 2026-04-19 (arXiv 2604.17650)
- **URL:** https://arxiv.org/abs/2604.17650

**Why not in previous prompt:** Natural (non-adversarial) shift was underweighted.
**Key findings:** Moderate natural prompt shifts → **73% average performance loss**; instruction-following degrades systematically over time/user groups.
**Methodology contribution:** Three-axis (time, user group, geography) natural-shift framework with natural-language divergence measures correlating with degradation.
**Applicability:** (2) + (3).

### FAQ: Efficient Evaluation with Statistical Guarantees

- **Score:** 9/10 | **Profiles:** 6
- **Published:** 2026-01-28 (arXiv 2601.20251)
- **URL:** https://arxiv.org/abs/2601.20251

**Why not in previous prompt:** Eval-budget allocation under valid inference was out of classical selective-prediction scope.
**Key findings:** Up to 5× effective sample size gain; **preserves valid frequentist CIs under adaptive sampling** (a property most pipelines violate).
**Methodology contribution:** Proactive Active Inference (finite-population extension of Zrnic & Candès) + Bayesian factor model + variance-reduced sampling.
**Applicability:** All three, especially A/B testing of variants.

### Efficient Benchmarking of AI Agents

- **Score:** 9/10 | **Profiles:** 1, 6
- **Published:** 2026-03-24 (arXiv 2603.23749)
- **URL:** https://arxiv.org/abs/2603.23749

**Why not in previous prompt:** **Rank-preservation-under-scaffold-shift** is a novel economics/robustness concept.
**Key findings:** Mid-difficulty filter (30–70% historical pass) cuts 44–70% of tasks while preserving rank under shift; **greedy task selection actively underperforms random under scaffold shift** — negative result.
**Methodology contribution:** Empirical separation of ranking fidelity from score prediction under shift.
**Applicability:** (1) CI triage; (3) ongoing agent eval.

### RFEval — Faithfulness under Counterfactual Intervention

- **Score:** 9/10 | **Profiles:** 3
- **Published:** 2026-02-19 (arXiv 2602.17053)
- **URL:** https://arxiv.org/abs/2602.17053

**Why not in previous prompt:** Previous framing discussed CoT in judge prompts, not CoT as object of evaluation.
**Key findings:** **49.7% unfaithful outputs**; stance inconsistency dominates; worst in math/code (convergent) domains — directly warns (1).
**Methodology contribution:** Two decoupled conditions — stance consistency + causal influence — independent of accuracy.
**Applicability:** (1), (3).

### Monitorability as a Free Gift — negative result on RLVR

- **Score:** 9/10 | **Profiles:** 3, 11
- **Published:** 2026-02-03 (arXiv 2602.03978)
- **URL:** https://arxiv.org/abs/2602.03978

**Why not in previous prompt:** Mechanistic decoupling of monitorability from reasoning reliance.
**Key findings:** RLVR monitorability gains come from **entropy reduction and prompt-attention, not stronger causal reliance on CoT** — premium negative result.
**Methodology contribution:** Mechanistic + behavioral diagnosis separating apparent from real faithfulness gains.
**Applicability:** All three — warns against CoT-based trust metrics as training objectives.

### MonitorBench

- **Score:** 8/10 | **Profiles:** 3
- **Published:** 2026-03 (arXiv 2603.28590)
- **URL:** https://arxiv.org/html/2603.28590

**Why not in previous prompt:** Adversarial stress-testing for monitorability is new.
**Key findings:** More capable LLMs have **lower** monitorability; models can intentionally reduce monitorability by up to 30% under stress.
**Methodology contribution:** 1,514 instances, 19 tasks, decision-critical-factor construction, two stress-test settings.
**Applicability:** Runtime gating in (3).

### Meta JiT “Dodgy Diff” + ACH

- **Score:** 9/10 | **Profiles:** 8
- **Published:** 2025-07 FSE + 2026-03-28 TOSEM + 2026-04 news
- **URL:** https://www.infoq.com/news/2026/04/meta-jit-testing-ai-detection/ ; https://dl.acm.org/doi/10.1145/3696630.3728544

**Why not in previous prompt:** Production-scale deterministic verification import; production evidence for SE-derived eval protocols.
**Key findings:** **4× bug-detection improvement**; up to **20× on meaningful failures**; 22,000 generated tests.
**Methodology contribution:** Change-aware test generation (tests must fail on proposed change, pass on parent).
**Applicability:** **Direct drop-in for (1).**

### LLMORPH

- **Score:** 9/10 | **Profiles:** 8, 9
- **Published:** 2026-03-24 (arXiv 2603.23611)
- **URL:** https://arxiv.org/abs/2603.23611

**Why not in previous prompt:** Metamorphic-testing import as label-free oracle.
**Key findings:** 36 MRs × 4 NLP tasks × 3 LLMs; 561K test executions detecting faults without labels.
**Methodology contribution:** JSON-encoded extensible MRs.
**Applicability:** (2) — label-free invariance checks.

### ATLAS — IRT-based adaptive testing

- **Score:** 9/10 | **Profiles:** 6, 9
- **Published:** v2 2026-02-02 (arXiv 2511.04689)
- **URL:** https://arxiv.org/html/2511.04689v1

**Why not in previous prompt:** Psychometric CAT import was absent from classical-eval framing.
**Key findings:** **90% item reduction** at matched precision (41/5,600 HellaSwag items); 3–6% of items have negative discrimination (annotation errors); **23–31% of models shift >10 ranks** when comparing IRT ability vs. raw accuracy.
**Methodology contribution:** 3PL IRT calibration + Fisher-information item selection + SE-controlled stopping.
**Applicability:** RAG classifier A/B testing; any regression testing over historical item bank.

### Confident Rankings with Fewer Items (Trismik)

- **Score:** 9/10 | **Profiles:** 6, 9
- **Published:** 2026-01 (arXiv 2601.13885)
- **URL:** https://arxiv.org/abs/2601.13885

**Why not in previous prompt:** CAT extended to continuous outputs is new.
**Key findings:** **2% of items** improves Kendall τ by 0.12 vs. random; 95% accuracy on confident predictions.
**Methodology contribution:** Heteroskedastic-normal IRT response distribution for continuous metrics.
**Applicability:** A/B testing prompts/models with early stopping.

### MCP-Atlas — claims-based programmatic rubric

- **Score:** 8/10 | **Profiles:** 7, 8
- **Published:** 2026-02-01 (arXiv 2602.00933)
- **URL:** https://arxiv.org/abs/2602.00933

**Why not in previous prompt:** Explicit counter-movement to LLM-as-judge for tool use.
**Key findings:** 36 real MCP servers, 220 tools, 1,000 tasks; top models still <50% pass.
**Methodology contribution:** Claims-based partial credit + internal diagnostics (tool discovery, parameterization, syntax, error recovery, efficiency) — all programmatic.
**Applicability:** (3) planning.

### VerifAI-2 workshop (ICLR 2026): Code Verification Strategies

- **Score:** 9/10 | **Profiles:** 8
- **Published:** 2026-03-02
- **URL:** https://openreview.net/forum?id=AP8ZlN7lwU

**Why not in previous prompt:** Head-to-head programmatic vs. judge with empirical backing.
**Key findings:** LLM judges struggle on harder coding problems; **auto-regressive unit-test generation beats parallel sampling**; hybrid implicit+test-gen beats either alone.
**Methodology contribution:** Systematic benchmark of code verification *strategies*.
**Applicability:** **Direct validation of (1)’s architecture.**

### Benchmark² — Systematic Evaluation of Benchmarks

- **Score:** 8/10 | **Profiles:** 4
- **Published:** 2026-01-07 (arXiv 2601.03986)
- **URL:** https://arxiv.org/abs/2601.03986

**Why not in previous prompt:** Meta-evaluation framework with reference-independent quality metrics.
**Key findings:** Selective filtering preserves fidelity at 35% of items; **Capability Alignment Deviation** flags contamination via within-family rank violations.
**Methodology contribution:** Three complementary metrics (CBRC, DS, CAD).
**Applicability:** All three — curate internal eval sets.

### Thinking Machines: Defeating Nondeterminism in LLM Inference

- **Score:** 8/10 | **Profiles:** 5
- **Published:** In-window
- **URL:** https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

**Why not in previous prompt:** Systems-level cause of nondeterminism absent from statistical framing.
**Key findings:** **Batch invariance**, not floating-point + concurrency, is the true culprit.
**Methodology contribution:** Batch-invariant kernels; bit-exact reproducibility demonstration.
**Applicability:** All three — informs eval reproducibility strategy.

### Meta Muse Spark / Evaluation Awareness

- **Score:** 7/10 | **Profiles:** 4
- **Published:** 2026-04
- **URL:** https://kili-technology.com/blog/llm-benchmarks-evaluation-awareness-muse-spark-report

**Why not in previous prompt:** Evaluation-awareness-as-measurement is a new category.
**Key findings:** Muse Spark verbally identifies public benchmarks as evals 19.8% vs. 2.0% on internal.
**Methodology contribution:** Linear probes on activations extract eval-awareness signal.
**Applicability:** (3) — argues for differently-framed private benchmarks.

### Anthropic: Measuring AI Agent Autonomy in Practice

- **Score:** 7/10 | **Profiles:** 1, 10
- **Published:** 2026-02
- **URL:** https://www.anthropic.com/research/measuring-agent-autonomy

**Why not in previous prompt:** Production telemetry as evaluation signal.
**Key findings:** 99.9th-percentile turn duration nearly doubled Oct’25→Jan’26; auto-approve rate rises 20% → 40%+ with tenure; pre-deployment evals **systematically underestimate in-the-wild autonomy**.
**Methodology contribution:** Post-deployment observational protocol.
**Applicability:** (1), (3) — ship telemetry alongside offline eval.

### TruLens 2.6 Agent’s GPA

- **Score:** 7/10 | **Profiles:** 1, 10
- **Published:** 2026-02-03
- **URL:** https://www.trulens.org

**Why not in previous prompt:** Reference-free Goal/Plan/Action alignment framework.
**Key findings:** Covers 95% of errors in TRAIL dataset (SWE + data-agent traces).
**Methodology contribution:** Purpose-built agent-plan-alignment metric.
**Applicability:** (3).

-----

## Section 8 — Tier 2 papers (Score 4–6)

|ID   |Title                                                                      |Score|Category  |Key finding                                                                                               |
|-----|---------------------------------------------------------------------------|-----|----------|----------------------------------------------------------------------------------------------------------|
|T2.1 |A-RAG: Agentic RAG via Hierarchical Retrieval Interfaces (arXiv 2602.03442)|6    |Emerging  |Three autonomy axes for RAG — Autonomous Strategy, Iterative Execution, Interleaved Tool Use              |
|T2.2 |TRAJECT-Bench (OpenReview ICLR 2026)                                       |6    |Emerging  |Decomposes tool-use into selection/parameters/dependency order — Claude-4 EM drops 0.846→0.445 simple→hard|
|T2.3 |ToolTree — Dual Pre/Post-Execution Eval (arXiv 2603.12740, ICLR 2026)      |6    |Emerging  |Bidirectional MCTS pruning; pre-execution prior + post-execution reward                                   |
|T2.4 |ToolRLA — Multiplicative Reward Decomposition (arXiv 2603.01620)           |6    |Blind Spot|93% ↓ regulatory violations via multiplicative format × selection × parameter × compliance                |
|T2.5 |FreshStack / Coverage@20 (arXiv 2504.13128 + 2026 follow-ons)              |6    |Shift     |Coverage@20 + α-nDCG@10 replace NDCG for evidence-collection RAG                                          |
|T2.6 |How You Ask Matters! (arXiv 2604.10745)                                    |5    |Blind Spot|Adaptive RAG retrieval-decision flips on human rewrites and typos — premium negative                      |
|T2.7 |Retrieval or Representation? (arXiv 2603.04238)                            |6    |Shift     |BM25 matches dense retrievers once document preprocessing fixed — premium negative                        |
|T2.8 |Breaking the Chain (arXiv 2603.16475)                                      |5    |Blind Spot|Models more faithful to counterfactual than correct interventions                                         |
|T2.9 |Classifier Sensitivity in CoT Eval (arXiv 2603.20172)                      |5    |Shift     |2.6–30.6 pp faithfulness spread across classifiers on identical data — premium negative                   |
|T2.10|FaithCoT-Bench (ICLR 2026)                                                 |6    |Blind Spot|Instance-level unfaithfulness detection with step-level evidence labels                                   |
|T2.11|FACT-E (arXiv 2604.10693)                                                  |5    |Blind Spot|ACE instrumental-variable causal sensitivity for CoT                                                      |
|T2.12|ReFIne (ICLR 2026)                                                         |5    |Emerging  |Trains CoT for interpretability/faithfulness/reliability as separate objectives                           |
|T2.13|Thought Anchors (ICLR 2026)                                                |5    |Emerging  |Sentence-level attribution — planning/uncertainty-management sentences dominate                           |
|T2.14|Beyond Solving: Generator-Verifier Gap (ICLR 2026)                         |5    |Shift     |**Self-verification yields little gain across all tasks** — premium negative                              |
|T2.15|ConsistencyBench (ICLR 2026 Workshop)                                      |5    |Emerging  |Universal 36–57 pp gap between individual accuracy (83%) and set-level consistency (46.7%)                |
|T2.16|DyePack (arXiv 2505.23001)                                                 |6    |Blind Spot|Backdoor canaries give closed-form FPR bounds (0.000073%)                                                 |
|T2.17|RIKER (arXiv 2601.08847)                                                   |5    |Blind Spot|Paradigm inversion — generate documents from ground truth, regenerable corpora                            |
|T2.18|Overcoming ‘Impracticality’ of RAG (arXiv 2604.02640)                      |4    |Emerging  |Four-axis RAG-eval diagnostic taxonomy                                                                    |
|T2.19|Cross-Context Verification (arXiv 2603.21454)                              |5    |Blind Spot|Session-isolated diversity as contamination probe; hierarchical review collapses to 100% sycophancy       |
|T2.20|LongCLI-Bench (arXiv 2602.14337)                                           |5    |Emerging  |Dual-set (fail-to-pass + pass-to-pass) protocol                                                           |
|T2.21|BFCL V4 Agentic                                                            |5    |Emerging  |Format-sensitivity axis added; irrelevance-detection task                                                 |
|T2.22|IFEval-FC (arXiv 2509.18420)                                               |5    |Blind Spot|Verifiable format constraints in JSON-schema — no LLM judge                                               |
|T2.23|AMST Adversarial Moral Stress (arXiv 2604.01108)                           |4    |Emerging  |Distribution-aware robustness metrics (variance, tail, multi-turn drift)                                  |
|T2.24|Hardy signed-isotonic-R² (arXiv 2603.24999)                                |4    |Blind Spot|Lightweight bad-item detector beats classical test theory                                                 |
|T2.25|GeoRepEval (arXiv 2604.16421)                                              |4    |Emerging  |Consistency-Invariance gap as first-class metric                                                          |
|T2.26|AgentPRM / InversePRM (arXiv 2502.10325)                                   |4    |Emerging  |Learn step rewards from outcomes — addresses step-label scalability                                       |
|T2.27|SoK Agentic RAG (arXiv 2603.07379)                                         |5    |Adjacent  |Finite-horizon POMDP framing for agentic RAG                                                              |
|T2.28|CUARewardBench (arXiv 2510.18596)                                          |5    |Emerging  |ORM/PRM eval on computer-using agents; strict-unanimous voting pattern                                    |
|T2.29|CARE multi-hop retriever eval (arXiv 2604.18234)                           |4    |Emerging  |Judge all contexts jointly — per-passage judging misses joint relevance                                   |
|T2.30|IRT-GRM Diagnosing LLM-Judge (arXiv 2602.00521)                            |5    |Adjacent  |Psychometric scale validation applied to judges                                                           |
|T2.31|Cacioli Validity Scaling (arXiv 2604.17707)                                |4    |Adjacent  |Clinical MMPI-style validity screens for LLM confidence                                                   |
|T2.32|AI-driven FMEA (Cambridge Design Science Apr 2026)                         |4    |Adjacent  |Reliability-engineering risk priority numbers for LLM failure modes                                       |
|T2.33|Bias-Bounded Evaluation (arXiv 2603.05485)                                 |4    |Adjacent  |DP-style noise for provable bias bounds on judges                                                         |
|T2.34|JudgeBiasBench (arXiv 2603.08091)                                          |5    |Adjacent  |Survey-methodology-style 12-bias taxonomy with controlled injection                                       |
|T2.35|METR Fine-tuning CoT Controllability                                       |4    |Emerging  |~950 SFT examples raise OOD controllability from 2.9% to 8.8% — CoT is fragile                            |
|T2.36|Berkeley RDI “How We Broke Agent Benchmarks”                               |6    |Shift     |Exploit agent near-100% on 8 benchmarks without solving tasks                                             |
|T2.37|Rethinking Agent-Generated Tests (arXiv 2602.07900)                        |5    |Shift     |Test-writing doesn’t correlate with task success — premium negative                                       |
|T2.38|MVES minimum viable eval suite (arXiv 2601.22025)                          |4    |Economics |Per-method human-agreement + cost-per-1000 table                                                          |
|T2.39|Benchmarking Knowledge-Extraction Attack on RAG (arXiv 2602.09319)         |4    |Blind Spot|Unified attack/defense benchmark for RAG stacks                                                           |

-----

## Section 9 — Updated research roadmap

### Immediate additions (strong evidence, directly relevant)

- **Adopt c-CRAB test-driven scoring for the code-review agent** — the 32% single-agent ceiling validates the multi-frame + judge-filter architecture, and the protocol extends existing test-based philosophy to the review layer.
- **Implement Meta JiT “Dodgy Diff” change-aware test generation** — 4× bug-detection improvement at production scale; aligns with AST-sliced diff analysis via tree-sitter. Use auto-regressive (not parallel-sampled) test generation per VerifAI-2.
- **Enforce cross-family judge lineage rule** — eval-generating model family ≠ judge family ≠ tested family. Preference Leakage provides the empirical case; cheap to implement.
- **Add fault-injection CI for the planner** — ReliabilityBench’s chaos-engineering protocol. Reflexion-style self-reflection amplifies fault impact, so do not reflexively add reflection layers.
- **Stop Likert-scale rubrics; switch to decomposed binary pass/fail with written critique.** Langfuse’s Apr 8 boolean scores operationalizes this.
- **Refresh eval reporting to include pass^k and duration-stratified metrics.** Report variance, tail risk, and behavioral attributes (length, refusal rate, hallucination rate) alongside accuracy.
- **Build per-cohort eval slices** (time, region, user segment) per LENS.
- **Adopt ConSol mixture-SPRT for inference-time early stopping** on self-consistency sampling in code-review agent’s test-based verification.
- **Retire SWE-bench Verified citations**; pivot to SWE-bench Pro + private expert-authored golden sets. Run SWE-Bench Illusion path-identification probe on any code benchmark before trusting.
- **Use Inspect AI’s Agent Bridge** to wrap the planning agent, and layer TruLens 2.6 Agent’s GPA for Goal/Plan/Action alignment scoring.

### Investigate further (promising but needs validation)

- **IRT-based adaptive testing (ATLAS, Trismik)** for regression-test compression — validate 10× cost reduction on actual RAG classifier + planner eval sets.
- **RFEval counterfactual-intervention protocol** for “right answer wrong reason” detection in code review.
- **MonitorBench stress tests** for CoT monitorability.
- **Coverage@20 nugget metrics** for RAG retrieval — validate against existing NDCG on held-out set.
- **MCP-Atlas claims-based programmatic rubric** as counter to LLM-judge for planner tool-call validation.
- **LLMORPH metamorphic testing** for RAG classifier — label-free invariance checks under paraphrase, negation, entity substitution.
- **FMEA for the planning system** — enumerate failure modes with SOD scoring to prioritize which get deterministic checks first.
- **Pre-release DyePack-style watermarking** on any internal eval set before sharing.
- **Meta-evaluation metrics (Benchmark² CBRC/DS/CAD, Hardy signed-isotonic-R²)** to flag bad items in internal eval sets.

### Monitor (emerging, not yet actionable)

- **Evaluation awareness** (Muse Spark 19.8% detection rate).
- **Process Reward Models for tool use** — wait for specialized PRMs validated on similar domains.
- **Thought Anchors sentence-level attribution** — watch for production-scale validation.
- **Anthropic Bloom automated behavioral evaluations** — alpha research.
- **Consistency-Guided Decoding** (ConsistencyBench).
- **Agent’s GPA maturity** — currently covers 95% of TRAIL errors, but TRAIL is narrow.

### Deprioritize (was on radar but evidence has weakened)

- **“Eval-driven development” (write evaluators first)** — adopt data-first loop instead.
- **Generic off-the-shelf RAG metrics as primary dashboards** — validate against 30–50 hand-graded traces before trusting.
- **Standalone MIA as contamination proof** — shift to prospective watermarking.
- **Same-family or self-judging for LLM-as-judge** — Preference Leakage formalizes the bias.
- **Adaptive Consistency Bayesian early-stop** — switch to mixture-SPRT.
- **Fixed-seed determinism at temperature=0 on public APIs** — impossible without batch-invariant kernels.
- **Classical tabular drift detection (KS, PSI, JS on inputs)** — insufficient for API-served LLMs.
- **Naive self-verification layers** — Beyond Solving shows little gain; require cross-family verifier.

-----

## Section 10 — Meta-observation

**The field is diverging methodologically while converging paradigmatically.** A shared high-level story is emerging across Feb–Apr 2026: pre-deployment benchmarks are lossy proxies; evaluation must be trajectory-aware, reliability-engineered, contamination-resistant, and statistically efficient. But the *concrete protocols* implementing that story — TRACE, HAL, ReliabilityBench, ATLAS, RFEval, MCP-Atlas, DyePack, FAQ, A-RAG, c-CRAB — are proliferating without standardization. This is a healthy “Cambrian explosion” phase. The practitioner should expect 12–18 months before dominant protocols emerge per task type.

**Evaluation practices are becoming more fragmented for research and more standardized for production.** Frontier labs are converging on private expert-authored benchmarks + behavioral/monitorability probes + cross-family judging + fault injection + pre-release watermarking. Research literature is fragmenting into 15+ competing methodology proposals. Practitioners should lean on the consolidating production consensus (Husain & Shankar FAQ; HAL Docent rubrics; TruLens Agent’s GPA; Inspect) and sample selectively from research proposals after validation on internal data.

**The biggest risk the practitioner faces** is that their three systems rely on architectures and benchmarks calibrated to a pre-Feb-2026 reality. Specifically: (1) the code-review agent’s test-based verification is validated by Meta JiT, c-CRAB, and VerifAI-2 — but if the agent emits Likert-style judge scores internally or uses the same model family for generation and judging, both protocols break. (2) The RAG classifier likely relies on NDCG or vendor-default faithfulness scores — both dismissed in window. (3) The planning system almost certainly reports pass@1 and doesn’t instrument for duration-stratified reliability — the most-reproduced finding in window is that this under-reports failures super-linearly with task length. The common thread: **the systems probably measure what their benchmarks measured, not what production actually fails on.**

**The single most important thing to investigate: build a private, expert-authored, behaviorally-instrumented golden set per system, graded on binary pass/fail with written critique, evaluated with cross-family judges, and regenerated / watermarked against contamination.** Every in-window consensus shift points to this single operational change. The second most important thing — specific to the practitioner’s architecture — is to validate the code-review agent’s multi-frame + judge-filter pipeline against c-CRAB-style test-driven review scoring. The practitioner’s architecture is well-aligned with where the field is converging (programmatic verification, specialized reviewers, judge filtering), but only c-CRAB-style evaluation can demonstrate whether the multi-frame decomposition adds real signal over a monolithic reviewer — and the 41.5% union bound from c-CRAB suggests specialized-frame ensembling *is* where the headroom lives.