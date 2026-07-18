# LLM evaluation methodology: three gaps, three months, what changed

## 1. Executive summary

**Post-January 2026, the statistical foundations under LLM evaluation have hardened substantially while the application layer remains fragmented.** The biggest shift is methodological: a cluster of ICLR-2026 and early-2026 arxiv papers (Chen et al. 2601.05420, Feng et al. 2601.20913, Lee et al. 2511.21140 v3) now provides a **converged statistical skeleton** — small human calibration set + large LLM-proxy set + Rogan–Gladen or PPI++/EIF estimator + valid confidence interval — that unifies what was previously a fragmented debate between measurement-error correction and prediction-powered inference. For your three target systems this means bias-corrected metrics are no longer research-only; they have reference recipes and variance formulas usable directly. The second shift is that **judge reliability tooling became concrete**: CyclicJudge (2603.01865), the RAND Judge Reliability Harness (2603.05399), JudgeBiasBench (2603.08091), and Bias-Bounded Evaluation (2603.05485) provide operational protocols rather than findings. The third shift is sobering: the LoCoMo audit cycle and ATANT v1.1 (2604.10981) expose that most published agent-memory benchmark numbers are not reproducible, forcing self-evaluation for any planning-system memory.

**“Think I know” items — overall scorecard.** Cross-family judging *partially confirmed* — it reduces self-preference but family-bias persists and the DBG paper (EMNLP 2025) argues much “self-preference” is legitimate quality. LLM-as-jury reliability gain *confirmed and quantified* — PoLL ~7× cheaper than single GPT-4;  Sage reports ~15% max gain from panels;  BT-σ beats uniform averaging unsupervised. 0.6/0.8 kappa heuristics *mostly confirmed but refined* — κ ≥ 0.8 is still the deployment bar, but correlation-plus-κ must be reported jointly (r=0.95, κ=0.5 signals systematic bias). Calibration drift *formally measured* for the first time in Wiese PLOS ONE (Feb 2026) — uncalibrated Kendall’s τ 0.38–0.52 volatile, Bradley-Terry-corrected 0.59–0.68 stable.  Conformal prediction for LLMs *exists and is newly usable* (TorchCP native LLM support 2025) but not deployed in production publicly. Multi-class abstention literature *confirmed thin* — classical theory mature (Ramaswamy, Cao), LLM empirical work still evaluates binary abstain/answer.

**Answered questions.** The precision-lower-bound math you asked for is Rogan–Gladen: P_true = (P̂ + Sp − 1)/(Se + Sp − 1),  with Lang–Reiczigel CI correction.   A standard judge-calibration recipe now exists (calibrate → bias-correct → audit transport per policy → recalibrate on version change). Judge benchmarks exist (JudgeBench, CodeJudgeBench, RubricEval, JudgeBiasBench, JRH). Small reasoning judges can replace large non-reasoning judges on code (CodeJudgeBench: Qwen3-8B thinking beats 70B non-thinking). Active-learning-for-eval-set-construction is a recognized subfield (“active testing,” Kossen & Rainforth et al.).

**Remaining gaps.** No LLM-specific ordinal-severity evaluation standard — you fall back to weighted κ, Krippendorff’s α with ordinal distance, Gwet’s AC2. No systematic cross-version drift study on named API transitions (GPT-4→4o→4.1→5→5.4). Survivorship bias in eval sets is nearly untreated — MS MARCO paper is the only directly portable methodology. No widely adopted three-way-with-abstention benchmark. No longitudinal specialized-vs-frontier judge comparison.

**Surprises you didn’t ask about.** (1) Grading scale matters mechanically — 0–5 beats 0–10 and 0–100 for human-LLM alignment  (arxiv 2601.03444);  4-level severity is near optimum. (2) Hardt et al. proved a hard theoretical ceiling: when the judge is no more accurate than the judged model, no debiasing can reduce ground-truth-label requirements by more than 2×. (3) Bayesian Orchestration (2601.01522) reframes cost-asymmetric classification: threshold-based discriminative approaches are *formally inadequate* for FP ≠ FN ≠ abstain; treat the LLM as a likelihood and apply Bayes-optimal rules.  (4) RAG often *reduces* abstention and increases hallucination vs. no-RAG (Joren et al. ICLR 2025) — your RAG classifier must be evaluated specifically on abstention behavior, not just accuracy. 

-----

## 2. LLM-as-judge calibration

### Confirmations and corrections

|Item                                |Status                       |Evidence                                                                                                                                                                                                                                                                                          |Update                                                                                                                                                                                                                                                                              |
|------------------------------------|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|Cross-family reduces self-preference|**Partially confirmed**      |Play Favorites (arxiv 2508.06709) isolates bias via regression on 596 prompts                                                                                                                                                                                                                     |Family-bias persists within the family (Claude-3→3.5 still favored). DBG (EMNLP 2025) decomposes apparent self-preference and finds much is legitimate quality; steering vectors can cut “unjustified” portion up to 97% but destabilize. Cross-family is necessary, not sufficient.|
|LLM-as-jury improves reliability    |**Confirmed with magnitudes**|PoLL (Verga 2024): 3-judge panel beats GPT-4 at ~7× lower cost.   Sage (2512.16041): up to +15% from panels.  BT-σ (2602.16610): unsupervised judge-aware aggregation beats uniform averaging.  CyclicJudge (2603.01865): round-robin eliminates systematic bias at **same cost as single-judge**.|Debate-based ensembles (ChatEval) can *hurt* — panels good,  adversarial debates risky.                                                                                                                                                                                             |
|0.6 / 0.8 κ heuristics              |**Confirmed and refined**    |Judge’s Verdict (arxiv 2510.09738): human–human κ = 0.801 baseline; top judges reach κ 0.781–0.816.  Thakur 2024: only GPT-4-Turbo (~0.84) and Llama-3-70B (~0.79) reach “excellent.”                                                                                                             |**Must report correlation AND κ jointly.** A judge with r=0.95 and κ=0.5 is systematically biased.  Also set human-human κ on *your* domain as the target — don’t target 0.8 if humans disagree at 0.6.                                                                             |
|Calibration drift formally measured |**Newly confirmed**          |Wiese PLOS ONE (Feb 2026): preregistered 10-week longitudinal study, 240-prompt fixed bank, 3 model families.  Uncalibrated judge τ = 0.38–0.52 (volatile); BT-corrected τ = 0.59–0.68 (stable).  PELT/MBIC change-point detection surfaces three divergent trajectories.                         |Still no named-API-version transition study (GPT-4→4o→4.1→5→5.4 as judge). This gap remains.                                                                                                                                                                                        |

### Answered open questions

**A. Standard judge-calibration protocol?** Answer: **Converging, not yet standardized.** The current reference recipe is (1) collect small human-labeled calibration set (100–500 items), (2) estimate judge sensitivity/specificity, (3) apply Rogan–Gladen correction with Lang–Reiczigel CI   (Lee et al. 2511.21140 v3) or EIF/PPI++ (Chen et al. 2601.05420), (4) run transport-audit test per policy/version (CJE, 2512.11150), (5) recalibrate on model-version change. Confidence: **High** on the statistical template; **Medium** on whether it generalizes beyond binary outcomes (multi-class extension via Buonaccorsi confusion-matrix inversion is classical but not benchmarked for LLM-judges). Caveat: Hardt et al. (2410.13341) prove a hard ceiling — when judge accuracy ≤ judged model, debiasing saves at most 2× labels.  

**B. Benchmark-of-judges?** Answer: **Exists in multiple forms.** JudgeBench (arxiv 2410.12784, ICLR 2025) for general response pairs;  **CodeJudgeBench** (arxiv 2507.10535) directly on-domain for code — use this; JudgeBiasBench (2603.08091) for bias-taxonomy;  RubricEval (2603.25133) for rubric-level judgment; Judge Reliability Harness (2603.05399) with ordinal-grading stress tests;   AXIOM (2512.20159) for ordinal code quality with Krippendorff’s α as primary. Confidence: **High.**

**C. Debiasing beyond position randomization?** Answer: **Many operational methods.** CyclicJudge round-robin (2603.01865), BT-σ unsupervised aggregation (2602.16610), Reasoning-based Bias Detector (RBD-8B: +18.5% accuracy, +10.9% consistency across 8 judges  — arxiv 2505.17100),  Bias-Bounded Evaluation with formal (τ=0.5, δ=0.01)  guarantees (2603.05485),  FairJudge’s curriculum SFT→DPO→GRPO  (2602.06625), linear probes on hidden states (FAIR Meta, 2512.22245). **Criteria injection + ensemble (RewardBench 2 study 2604.13717): +11.9 pp at 5× cost;  calibration-context anchoring did NOT help**  — contradicts common practitioner advice. Confidence: **High on availability, Medium on which combination is best.**

**D. Judge capability vs. general capability in smaller models?** Answer: **Reasoning capability matters more than parameter count.** CodeJudgeBench (arxiv 2507.10535): thinking Qwen3-8B outperforms 70B non-thinking specialized judges on code.  Caveat: arxiv 2507.16587 found sub-7B models fail to emit valid judgments ~15% of the time on code;  reasoning-capable small models only. For frontier-comparable absolute-accuracy tasks you still need frontier or fine-tuned-judge models to hit κ ≥ 0.8 (Thakur 2024). Confidence: **High.**

**E. Ordinal severity interaction with judge calibration?** Answer: **No LLM-specific standard.** Fall back to classical ordinal agreement — quadratic-weighted Cohen’s κ (penalizes critical→low 9× more than high→medium), Krippendorff’s α with ordinal distance function, Gwet’s AC2 for skewed distributions, Kendall’s τ-b for rank agreement, ICC for absolute agreement. AXIOM paper uses Krippendorff’s α as primary (ICE-Score α ≈ 0.62 Java baseline; complex agentic judges *decrease α by 78.2%* exhibiting systematic under-estimation bias). arxiv 2601.03444 (Jan 2026) empirically: **0–5 scale yields strongest human–LLM alignment; 0–10 weakest.**  Your 4-level critical/high/medium/low sits near the optimum. Confidence: **Medium-High** that weighted-κ + Krippendorff is the right stack; **Low** that any LLM-native ordinal metric will emerge soon.

### New findings (post-January 2026) you didn’t ask about

- **Scale mechanics matter more than judge choice on some tasks.** arxiv 2601.03444: 0–5 scale outperforms 0–10 and 0–100 across 6 judges × 12 human annotators; result stable across decoding temperature 0.1–1.0.  Design implication: keep your 4-level ordinal; resist the temptation to add “very critical” or a 1–10 numeric scale.
- **Reasoning effort is not monotonic on code judgment.** arxiv 2512.01232 (GPT-OSS 120B): LOW reasoning beats HIGH reasoning on mean absolute error *and* reliability *at 41% lower cost*.  High reasoning can be self-defeating; tune reasoning budget empirically per task.
- **Preference leakage contaminates inherited families** (ICLR 2026): Claude-3 judging Claude-3.5 is contaminated by shared training data  — cross-family isn’t the same as cross-lineage.
- **Agent-as-a-Judge** (arxiv 2410.10934): for task-list-structured outputs (code-review findings are essentially a task list), an agent-judge verifying against hierarchical requirements outperforms monolithic LLM-judge.  Relevant if your severity scoring involves multi-criterion verification.
- **Bayesian Orchestration (arxiv 2601.01522)**: threshold-based discriminative LLM approaches are *formally inadequate* under asymmetric costs; Bayes-optimal rule operates on the LLM as a likelihood — “interview any candidate with 1.75% qualification probability when FN is 16× FP.”  This surfaces a framing shift you’d otherwise miss.

### Current state assessment

- **Judge calibration protocols: Converging.** Statistical skeleton (calibration set + RG/PPI++/EIF + Lang–Reiczigel CI + transport audit) is reference-level post-Feb 2026. Multi-class and ordinal extensions are not yet standardized.
- **Benchmark-of-judges: Exists.** CodeJudgeBench + RubricEval + JRH + JudgeBiasBench are the defensible 2026 stack.
- **Ensemble/jury: Standard for high-stakes.** 3-judge cross-family panel is the convergent recommendation; CyclicJudge round-robin eliminates variance at same cost as single-judge.
- **Ordinal evaluation: Gap.** No LLM-native metric; classical ordinal agreement metrics are the best available and must be adapted rather than invented.

-----

## 3. Selective prediction and abstention

### Confirmations and corrections

|Item                                                 |Status                 |Evidence                                                                                                                                                                                                                                                                                                      |Update                                                                                                                                                                                                                                                                                                                                                           |
|-----------------------------------------------------|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|Conformal prediction for LLMs is research-maturity   |**Confirmed**          |TorchCP (JMLR 2025, arxiv 2402.12683) has native LLM classification support;  MAPIE v1 adding LLM risk-guarantees module in H2 2025;  KnowNo (CoRL 2023) canonical template.                                                                                                                                  |**Achievable**: marginal coverage routinely within 1–2% of target. **Still hard**: conditional coverage (Cherian et al. NeurIPS 2024 is state-of-art), cross-domain shift (Layerwise CP, arxiv 2604.16217). **Calibration cost**: 300–500 examples for marginal, 2–4k for conditional. No published large-scale production LLM deployment of CP as of April 2026.|
|Multi-class abstention literature thinner than binary|**Confirmed**          |Classical theory mature (Ramaswamy 2018,   Cao arxiv 2310.14772 closing the Ni 2019 open problem,  Campagner 2019 three-way).  LLM-era work tests MCQA-5 but evaluates binary abstain/answer.                                                                                                                 |No widely adopted three-way-with-abstain LLM benchmark as of April 2026. Use Cao’s predictor-rejector formulation with cost-parametrized α for your FP≠FN≠abstain case.                                                                                                                                                                                          |
|“Selective accuracy at X% coverage” standard         |**Partially corrected**|Traub et al. (NeurIPS 2024) prove AURC violates monotonicity and over-weights high-confidence failures; propose **AUGRC** (avg risk of undetected failures).   CWSA+ (2505.18622) adds confidence-weighted selective accuracy. Zhou et al. ICML 2025 (2410.15361) show empirical AURC biased on small samples.|Report AURC *and* AUGRC *and* selective-accuracy@{80%, 90%, 100%} *and* a cost-weighted variant. Field hasn’t converged on a single replacement.                                                                                                                                                                                                                 |

### Answered open questions

**A. Three-way classification with abstention — specialized literature?** Answer: **No LLM-specific empirical literature.** Theory exists (Cao 2310.14772, Ramaswamy 1505.04137, Campagner 2019) and is directly usable; LLM practice uses KnowNo-style MCQA-with-abstain,   which trivially extends to three classes. Recommendation: treat {class1, class2, class3, abstain} as 4-option MCQA, compute class-conditional scores, use split conformal or CRC with cost-asymmetric budget. Confidence: **High** that no specialized literature exists; **Medium** on which adaptation is optimal.

**B. Best-practice calibrated confidence source?** Answer: **P(True) > semantic entropy > CoCoA > self-consistency > verbalized numeric.** SECL (arxiv 2604.09624, April 2026): P(True) theoretically lower-bounded by 2× generative error; empirically ECE reductions of 56–78% across Phi/Gemma.  CISC (ACL 2025): P(True) beats self-consistency at up to 53% less compute.  Semantic entropy (Farquhar Nature 2024) still SOTA for hallucination AUROC   but 5–10× sample cost;  semantic entropy probes (SEPs) give near-zero overhead if you have hidden-state access.  CoCoA (Vashurin TACL 2025, arxiv 2510.20460): hybrid aggregation recommended when calibrated confidence needed specifically for abstention.  **Caveat** (Phillips arxiv 2603.21172, Mar 2026): entropy-based uncertainty does not reliably discriminate correct/incorrect for all frontier models  — always validate AUROC ≥ 0.65 on held-out before deploying. Confidence: **High** on the ordering; **High** that verbalized numeric is worst.

**C. Evaluating abstention quality distinct from answer quality?** Answer: **Use AbstentionBench metrics + AUCM.** AbstentionBench (Facebook/Meta 2025, arxiv 2506.09038): abstention precision, recall, F1 as LLM-judge-scored metrics.  AUCM (Madhusudhan COLING 2025, arxiv 2407.16221): 2×2 Answerable-Unanswerable Confusion Matrix — this is the cleanest practitioner-facing metric for your three-way case where abstain-on-answerable and answer-on-unanswerable are different errors. Augment with Effective Reliability Φ_c (ReCoVERR)  and IntroPlan’s exact-set rate + non-compliant-contamination rate.  Confidence: **High.**

**D. Cost-sensitive abstention eval when FP ≠ FN ≠ abstain?** Answer: **Decision-theoretic reformulation — compute expected cost under explicit cost matrix.** Bayesian Orchestration (arxiv 2601.01522, Jan 2026): pick action minimizing Σ_y P(y|x)·C(action, y), with abstention as an explicit action/row. Supplement with cost-weighted risk-coverage curves and Conformal Arbitrage (calibrates single threshold s.t. long-run frequency of undesirable events ≤ α using a few hundred logged examples).  Zellinger et al. (arxiv 2502.09054): early abstention in cascades trades +4.1% abstention for −13% cost and −5% error  — concrete cost-reduction protocol using multi-objective continuous threshold tuning. Confidence: **High** on the framing; **Medium** on which optimization procedure is SOTA.

**E. Standard test sets for abstention / selective prediction?** Answer: **AbstentionBench is current most-comprehensive** (20 datasets, 35k queries,  6 scenarios).  Plus AbstainQA (ACL 2024),  Abstain-QA/AUCM (COLING 2025), UA-Bench (arxiv 2604.17293, April 2026, 3,500 items distinguishing data vs model uncertainty — relevant for multi-class),   MedAbstain (arxiv 2601.12471 with adversarial perturbations + CP integration),  Sufficient-Context autorater dataset (Joren ICLR 2025, RAG-native — directly your use case). Confidence: **High.**

### New findings you didn’t ask about

- **RAG reduces abstention and increases hallucination** relative to no-RAG (Joren ICLR 2025, arxiv 2411.06037): Gemini 1.5 Pro abstention collapsed from 100% to 18.6% when RAG was added.  Your RAG three-way classifier needs abstention-specific eval; you cannot infer it from accuracy gains. Sufficient-context autorater + P(True) combined via logistic regression  achieves 2–10 pp gain in selective accuracy at matched coverage. 
- **AUGRC over AURC.** Traub et al. (NeurIPS 2024, arxiv 2407.01032) formally show AURC fails monotonicity  — switch to AUGRC, at least as a companion metric.
- **Conformal Arbitrage (2025).** Single-threshold risk control wrapping two competing objectives;  maps cleanly onto your acting-vs-escalating-vs-abstaining triangle; requires only a few hundred logged examples. 
- **DiNCo (arxiv 2509.25532):** at 10 inference calls, beats self-consistency at 100 calls via self-generated distractors + generator-validator disagreement.  Relevant if compute-bounded.
- **Layerwise CP (2604.16217):** biggest gains under cross-domain shift,  which is the regime your RAG corpus drift creates — but requires hidden-state access.

### Current state assessment

- **Conformal prediction for LLMs: Research-mature, production-nascent.** Usable via TorchCP for classification; MAPIE LLM module imminent. Works out-of-the-box for marginal coverage; conditional coverage and distribution-shift require more sophisticated methods.
- **Cost-sensitive abstention: Emerging framework.** Decision-theoretic reformulation (Bayesian Orchestration) + cost-weighted risk-coverage curves + Conformal Arbitrage give an end-to-end protocol, but no canonical implementation.
- **Three-way classification literature: Gap.** Classical theory (Cao, Ramaswamy) is ready to bridge. No LLM-specific empirical work.

-----

## 4. Weak supervision and noisy labels

### Confirmations and corrections

|Item                                                                   |Status                        |Evidence                                                                                                                                                                                                  |Update                                                                                                                                                                                                         |
|-----------------------------------------------------------------------|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|LLMs as weak labelers common but no standardized correction methodology|**Corrected — now converging**|Chen et al. 2601.05420, Feng et al. 2601.20913, Lee et al. 2511.21140 v3 (all post-Jan 2026) unify Rogan–Gladen + PPI++ + EIF into single semiparametric-efficient framework. `ppi-py` package deployable.|PPI++ with optimal λ ≡ EIF estimator in bin ary outcome case. Rogan–Gladen is more robust to calibration-test distribution shift; PPI++ is more efficient when shift is small. Choose based on your shift risk.|
|Labeled + unlabeled semi-supervised eval — unclear if LLM-adapted      |**Confirmed and updated**     |PRECISE-PPI (arxiv 2601.18777, 2026) extends PPI to hierarchical metrics (Precision@K, ranking). E-commerce A/B test: 100× unlabeled + 30 gold ≈ 2000× unlabeled performance at 95% cost reduction.       |LLM-adapted. Production-proven.                                                                                                                                                                                |
|“Proxy with 10–15% failure rate → precision lower bound” math          |**Provided**                  |Natarajan (NeurIPS 2013) unbiased loss under class-conditional noise; Rogan–Gladen (1978) prevalence estimator with Lang–Reiczigel CI correction.                                                         |Specific formulas below.                                                                                                                                                                                       |

### The precision lower-bound math you asked for

Let observed precision under noisy proxy = P̂, proxy sensitivity q₁, specificity q₀, FPR ρ₋ = 1−q₀, FNR ρ₊ = 1−q₁.

**Rogan–Gladen point estimate:** P_true = (P̂ + q₀ − 1) / (q₀ + q₁ − 1)

**Natarajan unbiased loss correction / precision lower bound:** P_true ≥ (P̂ − ρ₋) / (1 − ρ₊ − ρ₋)

**Variance inflation (delta method, Youden):** Var(P̂_corrected) ≈ Var(P̂_observed) / (q₀ + q₁ − 1)²

**Your case (ε = 0.125 symmetric):** denominator 0.75; P_true ≈ 1.33·P̂ − 0.167. At P̂ = 0.80, corrected P_true ≈ 0.90 lower bound. CI widens ~1.3–1.4× before accounting for calibration uncertainty (Lang–Reiczigel adds more). For stable q̂₀, q̂₁, need ≥ 100 calibration items (Lee et al. simulation guidance).

### Answered open questions

**A. Eval sets from historical tickets?** Answer: **Concrete recipe now exists** by composing four 2025–2026 components. (1) Stratified sampling (resolution-field value × ticket age × subsystem × resolver team) — document the frame. (2) LLM pre-labeling with KG-grounded Council of Agents (Adjudicator, arxiv 2512.13704: 0.99 F1 vs 0.48 single-LLM baseline on Mozilla Bugzilla — directly your scenario). (3) Active-testing prioritization via GAT (arxiv 2603.19264, Feb 2026): ~40% estimation-error reduction vs random; or Active Evaluation Acquisition (ICML 2025) for ~90% cost reduction. (4) Human adjudication on 5–10% calibration slice following QUEST protocol (κ ≥ 0.7 convergence). (5) Report Rogan–Gladen-corrected estimates + Lang–Reiczigel CI + bootstrap CI. (6) Document excluded fraction as survivorship disclosure. Confidence: **High** on components, **Medium** on exact ordering.

**B. Bounding metrics with documented proxy failure?** Answer: **Rogan–Gladen + Lang–Reiczigel CI** is primary; Natarajan formula for worst-case bound. When judge is weak (q₀+q₁−1 small), EIF/PPI++ is 3–15× more efficient than RG. Confidence: **High.**

**C. Survivorship bias?** Answer: **Field almost entirely ignores this.** Only MacAvaney et al. “On Survivorship Bias in MS MARCO” (arxiv 2204.12852) directly treats it — simulates discard distributions and shows conclusions can flip. Log2NS (arxiv 2105.14149) uses formal methods for non-observed branches in logs. Adapt MS MARCO methodology: (1) document your sample frame; (2) manually label a shadow corpus of non-ticketed events (on-call chats, monitoring auto-resolutions, silent log failures); (3) report metrics separately on ticketed vs shadow; (4) report conservative min(P_ticketed, P_shadow) if divergent. **Critical caveat**: PPI/RG estimators assume calibration and test come from the same distribution — survivorship bias violates this. Lee et al. claim robustness to covariate shift for their plug-in framework specifically; general PPI is not robust. Confidence: **High** that this is a gap; **Medium** on the right fix.

**D. Active learning for eval-set construction?** Answer: **Recognized subfield, called “active testing.”** Berrada/Kossen/Smith/Razzak/Gal/Rainforth 2025 is the flagship. GAT (2603.19264) and Active Evaluation Acquisition (ICML 2025) are current SOTA. Distinct from AL-for-training because the acquisition function must optimize estimator variance (Fisher/influence-function-based) rather than model learning. Production-ready: GAT reports 40% error reduction; AEA reports ~90% cost reduction. Confidence: **High.**

**E. Retrospective root-cause labeling?** Answer: **LLM-assisted re-labeling needs more context than the ticket alone provides.** Roy et al. (FSE 2024, Microsoft, arxiv 2403.04123): 66% of ReAct RCA failures are due to insufficient information in the ticket itself. Adjudicator (2512.13704) is the most complete 2026 protocol: dynamic KG per item (text + metadata + history) + multi-persona LLM council (Policy Expert + Contextual Analyst + Skeptical Adjudicator) + KG-override for structural errors. ALC3 (arxiv 2401.05467) reports iterative human-LLM correction reaches oracle with 17–24% fewer labels. Confidence: **Medium-High.**

### New findings you didn’t ask about

- **Arm-dependent bias is impossibility-proven.** arxiv 2601.21471 proves proxy-only model selection is information-theoretically impossible under arm-dependent bias. If agent variants have differential failure modes, naive audit estimators can be inconsistent — you *must* have human audits. Provides prediction-powered estimator + confidence sequences for adaptive auditing.
- **Best Arm Identification framing.** Recasts comparing agent variants under noisy labels as a multi-armed bandit with audits; fits code review agent A/B exactly.
- **SWE-bench Verified task-selection criteria** (Microsoft + Scale AI, NeurIPS 2025 D&B + updates through Feb 2026) give you a portable recipe for filtering noisy ticket data: (1) unambiguous issue description, (2) reliable tests, (3) clearly defined behavior — exclude rest and report excluded fraction.

### Current state assessment

- **LLM-assisted labeling protocols: Converging.** Adjudicator-style KG-grounded multi-persona council is the current best for high-precision retrospective labeling; Cleanlab/CROWDLAB remains the best for issue detection and audit.
- **Proxy-bounded metrics: Converged.** Rogan–Gladen + Lang–Reiczigel CI (Lee et al.) as robust default; EIF/PPI++ (Chen et al., Feng et al.) as efficient default when distribution shift is small.
- **Survivorship bias treatment: Gap.** MS MARCO methodology is the only directly portable starting point.

-----

## 5. Cross-cutting findings

**Cross-cutting 1 — The post-Jan-2026 statistical template generalizes.** Spans: all three areas. Insight: calibration set + proxy + RG/PPI++/EIF + Lang–Reiczigel CI works identically whether the “proxy” is an LLM judge (area 1), an LLM confidence score for abstention (area 2), or a noisy ticket resolution field (area 3). Design implication: build one shared calibration/estimation library serving all three systems. Chen et al. 2601.05420’s unification proves they’re the same estimator.

**Cross-cutting 2 — Transport audit as a first-class artifact.** Spans: areas 1 and 3. Insight: CJE (2512.11150) and Noisy-but-Valid (2601.20913) both require per-policy residual-mean tests before trusting calibrated estimates; the audit detects distribution shift between calibration and test. Design implication: every eval run on your three systems should emit a transport-audit score; alert if it fails. This is also how you detect calibration drift (area 1) automatically.

**Cross-cutting 3 — P(True) as universal confidence signal.** Spans: areas 1 and 2. Insight: SECL (2604.09624) and CISC (ACL 2025) both favor P(True) over verbalized and self-consistency for calibrated confidence. Design implication: for any system requiring confidence (severity-grading judge output confidence, RAG abstention confidence), elicit via “Is this correct? Reply 0 or 1” and use the single-token probability. Shared elicitation library across all three systems.

**Cross-cutting 4 — Scale choice beats judge choice on alignment.** Spans: areas 1 and 3. Insight: 0–5 scale beats 0–10 and 0–100 for human–LLM alignment (2601.03444); this applies equally to judge severity scoring and to human-adjudicated ticket re-labeling rubrics. Design implication: unify all ordinal rubrics on 4–5 levels. Your critical/high/medium/low (4 levels) is correct; resist adding sub-levels.

**Cross-cutting 5 — Active testing acquisition transcends domain.** Spans: areas 2 and 3. Insight: GAT and Active Evaluation Acquisition both use Fisher-information or uncertainty-sampling acquisition for eval-set selection; same acquisition functions apply to RAG abstention calibration and ticket eval construction. Design implication: shared active-testing module across RAG classifier calibration and planner eval set curation.

**Cross-cutting 6 — Hardt ceiling constrains debiasing economics.** Spans: all three areas. Insight: when your judge/proxy is no more accurate than the judged/labeled model, debiasing cannot save more than 2× labels (arxiv 2410.13341). Design implication: for high-stakes judge deployment on frontier agents, budget for large human calibration sets; don’t expect tenfold savings from bias correction.

-----

## 6. Secondary findings

**Chunking and context assembly (code review, 300–800 LOC / 10K–100K tokens).** Defensible 2026 stack: **cAST AST chunking** (arxiv 2506.15655, productionized Jan 2026 in Supermemory’s `code-chunk` library and Databricks) + **graph-guided retrieval** (LocAgent, RepoGraph: +32.8% on SWE-bench, KGCompass 58.3% on SWE-bench Lite) + **LLM pointwise reranker with batched caching** (Intercom Fin pattern: 5× speedup, statistically significant over BGE cross-encoder; listwise did *not* beat pointwise in their test). Vectara/FloTorch Feb 2026 benchmark: **recursive 512-token splitting beat semantic chunking 69% vs 54% end-to-end accuracy** — semantic chunking produced 43-token fragments. FutureQueryEval (EMNLP 2025, github.com/DataScienceUIBK/llm-reranking-generalization-study): 5–15% reranker degradation on temporally-unseen queries, listwise generalizes best (8% vs 12–15%). Long-context-vs-RAG reality: Gemini 1.5 Pro 99.7% single-needle, ~60% multi-fact at 1M; Claude Opus 4.6 = 76% MRCR at 1M; 1M-token prefill 60s+ — chunking still matters at your sizes.

**Memory system evaluation (agentic planning with feedback loop).** **MemoryAgentBench** (arxiv 2507.05257 v3 Mar 2026) is the paper to build around: 4 competencies framework (accurate retrieval, test-time learning, long-range understanding, **selective forgetting**), and selective forgetting is the conspicuous failure mode across MemGPT, Mem0, Cognee, Zep, MIRIX, MemoryLLM, M+. **LoCoMo-Plus** (arxiv 2602.10715, Feb 2026) adds cue-trigger constraint-consistency scenarios — memory as implicit constraint, not factual recall — exactly your planner feedback-loop shape. **ICRH (in-context reward hacking)** is the failure mode name for planner outputs becoming future memories that subtly optimize a misaligned objective over cycles; requires multi-cycle stress-testing. **Critical epistemic warning**: LoCoMo has documented ground-truth errors (~99 items per dial481 audit; Category 5 unscorable ~23%); Zep’s “Mem0 not SOTA” blog and ATANT v1.1 (arxiv 2604.10981) show none of the popular benchmarks actually measure *continuity*. Treat published memory benchmark numbers as suggestive; run your own evals combining MemoryAgentBench + LoCoMo-Plus + ICRH multi-cycle stress.

-----

## 7. Tier 1 papers (score ≥ 7) — full cards

### [T1-01] How to Correctly Report LLM-as-a-Judge Evaluations

- **Score**: 9/10 | **Profiles**: Judge calibration + weak supervision
- **Published**: 2025-11; v3 2026-02-09
- **URL**: https://arxiv.org/abs/2511.21140
- **Answers**: Standard calibration protocol (Q1-A); proxy-bounded metrics math (Q3-B)
- **Key findings**: Rogan–Gladen + Lang–Reiczigel CI plug-in framework. Adaptive calibration allocation for minimum CI width. Proven unbiased under distribution shift between calibration and test (unlike general PPI). Characterizes regime where bias-corrected LLM judge beats full human-only eval.
- **Methodology**: Plug-in delta method; simulation across calibration sizes and judge accuracy regimes.
- **Limitations**: Binary outcomes only; multi-class extension via Buonaccorsi confusion-matrix inversion is classical but not benchmarked.
- **Relevance**: Direct applicability to all three systems — unified calibration template.

### [T1-02] Efficient Inference for Noisy LLM-as-a-Judge Evaluation

- **Score**: 10/10 | **Profiles**: Weak supervision + judge calibration
- **Published**: 2026-01-08
- **URL**: https://arxiv.org/abs/2601.05420
- **Answers**: Proxy-bounded metrics (Q3-B); unifies RG and PPI++
- **Key findings**: Semiparametric EIF estimator unifies Rogan–Gladen and PPI++. In binary case PPI++ with optimal λ ≡ EIF. RG CIs 3–15× wider than EIF/PPI++ when judge is weak.
- **Methodology**: Semiparametric efficiency theory; simulation + real benchmarks.
- **Limitations**: Binary focus; non-trivial to implement without statistical background.
- **Relevance**: Code review judge severity scoring; RAG classifier abstention confidence; ticket labeling.

### [T1-03] Noisy but Valid: Robust Statistical Evaluation with Imperfect Judges

- **Score**: 10/10 | **Profiles**: Weak supervision
- **Published**: 2026-01-28 (ICLR 2026)
- **URL**: https://arxiv.org/abs/2601.20913
- **Answers**: Certification protocol for “failure rate below threshold” claims
- **Key findings**: Two-dataset framework (small calibration + large judge-labeled); variance-corrected rejection threshold with finite-sample Type-I error control despite calibration uncertainty. Derives regimes where Noisy-HT has higher power than Direct-HT.
- **Methodology**: Hypothesis testing with calibrated plug-in estimators.
- **Limitations**: Still assumes same distribution across calibration/test.
- **Relevance**: Certifying agent reliability for deployment gates.

### [T1-04] Adjudicator: Correcting Noisy Labels with KG-Informed Council of LLM Agents

- **Score**: 10/10 | **Profiles**: Weak supervision + eval-set construction
- **Published**: 2025-12 / 2026
- **URL**: https://arxiv.org/abs/2512.13704
- **Answers**: Historical ticket re-labeling protocol (Q3-A, Q3-E)
- **Key findings**: On Mozilla Bugzilla (BugsRepo, 100K bug reports): **0.99 F1 vs 0.48 single-LLM vs 0.59 non-KG council**. 100% recall on structural errors via KG-override. Purpose-built as golden-dataset generator for evaluation.
- **Methodology**: Dynamic KG per item + adversarial-persona council (Policy Expert + Contextual Analyst + Skeptical Adjudicator) + voting + KG-override.
- **Limitations**: Requires domain taxonomy to bootstrap KG; compute-expensive.
- **Relevance**: Planning system eval set construction from ticketing data — directly on-target.

### [T1-05] CyclicJudge: Mitigating Judge Bias Efficiently

- **Score**: 8/10 | **Profiles**: Judge debiasing
- **Published**: 2026-03
- **URL**: https://arxiv.org/abs/2603.01865
- **Answers**: Debiasing beyond position randomization (Q1-C); jury cost (Q1-2)
- **Key findings**: Round-robin judge-to-scenario assignment is provably optimal for fixed judge-call budget. Eliminates systematic judge bias at same cost as single-judge evaluation.
- **Methodology**: Variance decomposition (scenario + generation + judge + residual); validation on MT-Bench, MindEval.
- **Limitations**: Requires ≥3 judges; correlated biases across judges not corrected.
- **Relevance**: Code review jury — drop-in protocol to keep jury cost equal to single-judge while removing systematic bias.

### [T1-06] Judge Reliability Harness (RAND)

- **Score**: 9/10 | **Profiles**: Judge benchmark + drift
- **Published**: 2026-03-05
- **URL**: https://arxiv.org/abs/2603.05399; https://github.com/RANDCorporation/judge-reliability-harness
- **Answers**: Benchmark-of-judges (Q1-B); ordinal evaluation (Q1-E)
- **Key findings**: Open library generating validation suites: label-flip, formatting invariance, paraphrase invariance, verbosity bias, stochastic stability, **ordinal grading calibration**. Tested 4 SOTA judges × 4 benchmarks. No judge uniformly reliable; formatting perturbations produce larger drops than semantic perturbations; binary-stable judges degrade on ordinal.
- **Methodology**: Perturbation-based stress testing with synthetic-ordinal sample generation.
- **Limitations**: Stress suites not exhaustive; per-domain adaptation required.
- **Relevance**: Monthly drift-monitoring regression suite for code review severity judge.

### [T1-07] CodeJudgeBench: Benchmarking LLM-as-a-Judge for Coding Tasks

- **Score**: 9/10 | **Profiles**: Judge benchmark
- **Published**: 2025-07 (v2 2025-08)
- **URL**: https://arxiv.org/abs/2507.10535
- **Answers**: Domain-appropriate judge benchmark (Q1-B); small-vs-large (Q1-D)
- **Key findings**: 26 judges on code generation/repair/unit-test. Reasoning (“thinking”) models substantially outperform non-thinking. **Small thinking Qwen3-8B outperforms fine-tuned judges up to 70B.** Pair-wise > point-wise for code. All models show substantial position-swap sensitivity.
- **Methodology**: LiveCodeBench-v6 problems (1,055 items, May 2023–Apr 2025 to limit contamination); position-swap evaluation.
- **Limitations**: Benchmark partially saturated by frontier 2026 models.
- **Relevance**: Validate your code review judge choice; confirms smaller reasoning model can replace frontier judge.

### [T1-08] AXIOM — Rule-Based Code Judge with Ordinal Calibration

- **Score**: 9/10 | **Profiles**: Judge benchmark + ordinal
- **Published**: 2025-12
- **URL**: https://arxiv.org/html/2512.20159v1
- **Answers**: Ordinal code judging (Q1-E)
- **Key findings**: Uses ordinal scale “effort to refine to production-readiness.” Krippendorff’s α as primary metric. Baseline ICE-Score reaches α ≈ 0.62 Java DeepSeek. **Complex agentic judges (CodeJudge, CodeVisionary) *decrease* α by 78.2% (down to 0.136) with systematic under-estimation bias (mean 1.33 vs ground-truth 2.45).**
- **Methodology**: Rule-based perturbations generate controlled ordinal variation.
- **Limitations**: Code quality, not vulnerability severity directly; perturbation rules hand-crafted.
- **Relevance**: Template for evaluating code review severity judge; warns that “fancier” judges can be systematically worse on ordinals.

### [T1-09] Grading Scale Impact on LLM-as-a-Judge

- **Score**: 9/10 | **Profiles**: Scale design
- **Published**: 2026-01
- **URL**: https://arxiv.org/abs/2601.03444
- **Answers**: Scale choice for severity ordinals
- **Key findings**: 0–5 scale yields strongest human–LLM alignment. 0–10 weakest. Result stable across temperature 0.1–1.0. Inter-scale self-consistency is imperfect and benchmark-dependent.
- **Methodology**: 5,497 items × 6 judges × 12 human annotators; ICC two-way random-effects.
- **Limitations**: Not specifically code/severity; subjective-quality framing.
- **Relevance**: Validates your 4-level critical/high/medium/low — near optimum; resist 10-point scales.

### [T1-10] Human-Anchored Longitudinal Drift Study (Wiese, PLOS ONE)

- **Score**: 10/10 | **Profiles**: Calibration drift
- **Published**: 2026-02-02
- **URL**: https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0339920
- **Answers**: Calibration drift formally measured (Q1-4)
- **Key findings**: 10-week preregistered tracking of 3 model families. **Uncalibrated judge Kendall τ = 0.38–0.52 (volatile); weekly Bradley-Terry-corrected τ = 0.59–0.68 (stable).** Three divergent trajectories; safety metrics co-vary with drift events.
- **Methodology**: Fixed 240-prompt bank × 6 domains; blinded human raters; PELT/MBIC change-point detection; mixed-effects modeling.
- **Limitations**: Anonymizes model families; doesn’t cover named-API-version transitions.
- **Relevance**: Blueprint for monitoring code review judge over time.

### [T1-11] Bayesian Orchestration of Multi-LLM Agents

- **Score**: 9/10 | **Profiles**: Cost-sensitive abstention
- **Published**: 2026-01
- **URL**: https://arxiv.org/abs/2601.01522
- **Answers**: Cost-sensitive classification when FP ≠ FN ≠ abstain (Q2-D)
- **Key findings**: Threshold-based discriminative LLM approaches are formally inadequate under asymmetric costs. Treat LLMs as likelihood functions + apply Bayes-optimal decision rules. Concrete rule: “interview any candidate with 1.75% qualification probability when FN is 16× FP.”
- **Methodology**: Decision-theoretic reformulation with empirical validation on hiring/screening tasks.
- **Limitations**: Requires likelihood calibration; compute-heavier than threshold.
- **Relevance**: RAG three-way classifier cost-asymmetric decision rule.

### [T1-12] Sufficient Context (Joren et al., ICLR 2025)

- **Score**: 10/10 | **Profiles**: RAG abstention
- **Published**: 2024-11 (ICLR 2025)
- **URL**: https://arxiv.org/abs/2411.06037
- **Answers**: RAG-specific abstention (Q2-C, Q2-D)
- **Key findings**: RAG *reduces* abstention (Gemini 1.5 Pro 100% → 18.6%). Sufficient-context autorater + self-rated confidence (P(True), P(Correct)) via logistic regression achieves **2–10 pp gain in selective accuracy at matched coverage**.
- **Methodology**: Autorater for context sufficiency; intervention model.
- **Limitations**: English-only; knowledge-base QA focus.
- **Relevance**: Direct template for your RAG three-way classifier.

### [T1-13] AbstentionBench (Meta)

- **Score**: 9/10 | **Profiles**: Abstention benchmark
- **Published**: 2025
- **URL**: https://arxiv.org/abs/2506.09038; https://github.com/facebookresearch/AbstentionBench
- **Answers**: Standard test set (Q2-E); abstention-quality metrics (Q2-C)
- **Key findings**: 20 datasets, 35K queries, 6 abstention scenarios. Metrics: abstention precision/recall/F1 via LLM-judge (Llama 3.1 8B, ~88% human-agreement validated). **Scale does not help abstention; reasoning LLMs also fail.**
- **Methodology**: LLM-judge-scored abstention + heldout validation.
- **Limitations**: LLM-judge scoring introduces its own noise; needs recalibration per domain.
- **Relevance**: Metric vocabulary for RAG classifier abstention evaluation.

### [T1-14] P(True) / SECL + CISC (Self-Calibrating Language Models)

- **Score**: 9/10 | **Profiles**: Confidence calibration
- **Published**: SECL 2026-04 (arxiv 2604.09624); CISC ACL 2025
- **URLs**: https://arxiv.org/abs/2604.09624 ; ACL 2025 Findings
- **Answers**: Best calibrated-confidence source (Q2-B)
- **Key findings**: P(True) theoretically lower-bounded by 2× generative error; empirically ECE reductions 56% (Phi) to 78% (Gemma). CISC: P(True)-weighted voting beats self-consistency at up to 53% less compute.
- **Methodology**: Theoretical bound + empirical ECE across Phi/Gemma/GPT models.
- **Limitations**: Requires token logit access; doesn’t fully solve overconfidence in frontier models.
- **Relevance**: Primary confidence signal for RAG classifier.

### [T1-15] Generative Active Testing (GAT)

- **Score**: 9/10 | **Profiles**: Active-testing for eval
- **Published**: 2026-02-26
- **URL**: https://arxiv.org/abs/2603.19264
- **Answers**: Active learning for eval-set construction (Q3-D)
- **Key findings**: LLM-surrogate uncertainty-based ordering of unlabeled candidates. Statement Adaptation Module converts generative QA to pseudo-classification. **~40% reduction in estimation error vs random sampling.**
- **Methodology**: Active testing with LLM surrogate; evaluated on diverse benchmarks.
- **Limitations**: Surrogate-quality-dependent; cost of running LLM on every candidate.
- **Relevance**: Ticket-corpus prioritization for planning-system eval construction.

### [T1-16] AUGRC (Traub et al.)

- **Score**: 9/10 | **Profiles**: Selective prediction metrics
- **Published**: NeurIPS 2024
- **URL**: https://arxiv.org/html/2407.01032
- **Answers**: Selective-prediction reporting (Q2-3)
- **Key findings**: AURC violates monotonicity; over-weights high-confidence failures. AUGRC (avg risk of undetected failures across all predictions) meets all 5 proposed requirements.
- **Methodology**: Formal analysis of metric properties + empirical validation.
- **Limitations**: Field hasn’t fully converged; AURC still dominant.
- **Relevance**: Replace/supplement AURC in your RAG classifier reporting.

### [T1-17] MS MARCO Survivorship Bias

- **Score**: 9/10 | **Profiles**: Eval-set construction
- **Published**: 2022-04
- **URL**: https://arxiv.org/pdf/2204.12852
- **Answers**: Survivorship bias treatment (Q3-C)
- **Key findings**: Queries discarded during MS MARCO construction are majority answerable; simulation shows conclusions can flip had they been included.
- **Methodology**: Simulate subcorpora under different survival filters; measure metric drift.
- **Limitations**: IR-specific; not LLM-specific.
- **Relevance**: Only directly-portable methodology for survivorship-bias treatment in ticket eval.

### [T1-18] PoLL / Panel of LLM Evaluators

- **Score**: 8/10 | **Profiles**: Jury
- **Published**: 2024-04
- **URL**: https://arxiv.org/abs/2404.18796
- **Answers**: Jury magnitude (Q1-2)
- **Key findings**: Diverse panel of smaller judges outperforms single GPT-4 at ~7× lower cost with reduced intra-model bias.
- **Methodology**: Panel aggregation across disjoint families; cost/quality comparison.
- **Limitations**: Requires disjoint-family judge availability.
- **Relevance**: Baseline 3-judge panel for code review.

### [T1-19] RewardBench 2 Empirical Techniques Study

- **Score**: 8/10 | **Profiles**: Judge protocol
- **Published**: 2026
- **URL**: https://arxiv.org/html/2604.13717
- **Answers**: What debiasing techniques actually work (Q1-C)
- **Key findings**: Criteria injection +3.0pp at ~no cost. Ensemble (k=8) +9.8pp at 5× cost. Combined 83.6% vs 71.7% baseline (+11.9pp). **Calibration context anchoring did NOT reliably improve.**
- **Methodology**: Ablation on GPT-5.4 judge across RewardBench 2.
- **Limitations**: Single judge model; benchmark is reward-model-focused.
- **Relevance**: Directly actionable for code review judge construction.

### [T1-20] MemoryAgentBench

- **Score**: 10/10 | **Profiles**: Memory eval (secondary)
- **Published**: 2025-07 (v3 2026-03-17)
- **URL**: https://arxiv.org/abs/2507.05257
- **Answers**: Agent memory evaluation for planning system
- **Key findings**: 4 competencies: accurate retrieval + test-time learning + long-range understanding + **selective forgetting**. Selective forgetting is conspicuous failure mode across MemGPT/Mem0/Cognee/Zep/MIRIX/MemoryLLM/M+.
- **Methodology**: Incremental multi-turn reformatted from long-context datasets.
- **Limitations**: Still primarily conversational.
- **Relevance**: Build your planning-system memory eval around this framework.

-----

## 8. Tier 2 papers — table

|ID   |Title                                          |Score|Area                  |Key finding                                                                                                              |
|-----|-----------------------------------------------|-----|----------------------|-------------------------------------------------------------------------------------------------------------------------|
|T2-01|Causal Judge Evaluation (CJE)                  |8    |Judge                 |Transport audit tests force recalibration or refusal on policy shift; at 5% oracle 99% pairwise ranking at 14× cost ratio|
|T2-02|BT-σ (LLM-as-a-jury)                           |8    |Judge                 |Unsupervised judge-aware Bradley-Terry beats uniform averaging and supervised temperature-scaled BT                      |
|T2-03|FairJudge (SFT→DPO→GRPO)                       |7    |Judge                 |Curriculum training for cross-mode consistency (pointwise ↔ pairwise)                                                    |
|T2-04|JudgeBiasBench                                 |8    |Judge                 |12 bias types × 4 dimensions; bias-aware RL+contrastive training; warns excessive bias-supervision degrades              |
|T2-05|Bias-Bounded Evaluation (A-BB)                 |8    |Judge                 |Formal (τ=0.5, δ=0.01) bias-bounded guarantees; 61–99% correlation retention                                             |
|T2-06|Judge’s Verdict                                |8    |Judge                 |κ 0.801 human-human baseline; correlation alone insufficient; 2-step filter                                              |
|T2-07|JudgeBench                                     |7    |Judge                 |GPT-4o barely above random on coding-judgment hardest subsets                                                            |
|T2-08|RubricEval                                     |8    |Judge                 |Rubric-level meta-evaluation: 3,486 judgment instances                                                                   |
|T2-09|Agent-as-a-Judge                               |7    |Judge                 |Agent-judge outperforms monolithic LLM-judge on DevAI hierarchical requirements                                          |
|T2-10|Trust-or-Escalate                              |7    |Judge                 |Cascaded selective evaluation + simulated annotators; >80% human agreement at ~80% coverage                              |
|T2-11|Hardt et al. theoretical limit                 |8    |Judge                 |No debiasing can save >2× labels when judge ≤ judged model                                                               |
|T2-12|DBG Score (EMNLP 2025)                         |9    |Judge                 |Much “self-preference” is legitimate quality; reframes bias measurement                                                  |
|T2-13|Play Favorites                                 |8    |Judge                 |Family-bias persists beyond self-bias; robust to length control                                                          |
|T2-14|Linear Probes for Judge Uncertainty (Meta FAIR)|8    |Judge                 |Brier-trained hidden-state probe, 10× less compute than multi-generation                                                 |
|T2-15|Prometheus-2                                   |8    |Specialized judge     |Pearson +0.2 over open baselines; halves gap with GPT-4 on pairwise                                                      |
|T2-16|Sage (local/global consistency)                |8    |Judge                 |Panels +15%; self-generated rubrics −16.1%/−11.0% inconsistency; judges degrade ~200% on close-quality pairs             |
|T2-17|RBD (Reasoning-based Bias Detector)            |7    |Judge debiasing       |+18.5% accuracy, +10.9% consistency; +12.8pp over prompting baselines                                                    |
|T2-18|KnowNo                                         |9    |Abstention            |MCQA-with-abstain CP template; directly extends to 3-way + abstain                                                       |
|T2-19|IntroPlan                                      |8    |Abstention            |Exact-set rate + non-compliant-contamination rate as abstention metrics                                                  |
|T2-20|Conformal Abstention (Yadkori)                 |8    |Abstention            |Black-box risk-controlled abstention with LLM self-eval as conformity score                                              |
|T2-21|AbstainQA                                      |8    |Abstention            |Multi-LLM cooperative + competitive probing; +19.3% over baseline                                                        |
|T2-22|Abstain-QA / AUCM                              |8    |Abstention            |2×2 Answerable-Unanswerable Confusion Matrix — cleanest metric for your 3-way                                            |
|T2-23|Early-Abstention Cascades (Zellinger)          |9    |Cost-sensitive        |+4.1% abstention → −13% cost and −5% error; multi-objective threshold tuning                                             |
|T2-24|Conformal Arbitrage                            |9    |Cost-sensitive        |Single-threshold CRC bounds undesirable-event frequency ≤ α with a few hundred examples                                  |
|T2-25|Cao et al. Predictor-Rejector Multi-class      |8    |Multi-class abstention|Bayes-consistent surrogates for multi-class abstention; cost-parametrized α                                              |
|T2-26|Semantic Entropy (Farquhar Nature 2024)        |9    |Confidence            |SOTA AUROC for black-box hallucination; semantic-entropy probes near-zero overhead                                       |
|T2-27|CoCoA (Vashurin TACL 2025)                     |9    |Confidence            |Hybrid aggregation; recommended when calibrated confidence needed for abstention                                         |
|T2-28|DiNCo                                          |8    |Confidence            |10 inference calls beats self-consistency at 100                                                                         |
|T2-29|Phillips et al. entropy warning                |8    |Confidence            |Entropy-based UQ insufficient for safe selective prediction in some frontier models                                      |
|T2-30|ConfTuner                                      |8    |Confidence            |Tokenized Brier fine-tuning: 54.7% ECE improvement, 14.4% AUROC                                                          |
|T2-31|PRECISE-PPI                                    |9    |Weak supervision      |PPI for hierarchical metrics; 100× unlabeled + 30 gold ≈ 2000× unlabeled at 95% cost reduction                           |
|T2-32|Best Arm Identification (arxiv 2601.21471)     |8    |Weak supervision      |Proxy-only selection information-theoretically impossible under arm-dependent bias                                       |
|T2-33|Natarajan (NeurIPS 2013)                       |8    |Weak supervision      |Unbiased loss formula under class-conditional noise (canonical)                                                          |
|T2-34|Cleanlab / CROWDLAB                            |8    |Weak supervision      |Confident-learning tooling for LLM-eval consensus with per-label trust scores                                            |
|T2-35|Ahmed et al. GPT-4 RCA                         |8    |Ticket labeling       |In-context + fine-tuned retrospective root-cause labeling at Microsoft scale                                             |
|T2-36|Roy et al. FSE 2024 RCA                        |8    |Ticket labeling       |66% of ReAct RCA failures from insufficient ticket info; KBA augmentation needed                                         |
|T2-37|SWE-bench Verified criteria                    |10   |Eval curation         |Automated curation pipeline with human-validated 3-criterion filter                                                      |
|T2-38|Berrada/Kossen/Rainforth 2025 “Active testing” |7    |Active testing        |Establishes active-testing as distinct subfield from active-training                                                     |
|T2-39|cAST AST chunking                              |9    |Chunking (sec)        |AST + NWS-weighted greedy windows; productionized in Supermemory code-chunk, Databricks                                  |
|T2-40|LocAgent / RepoGraph / KGCompass               |9    |Chunking (sec)        |Graph-guided code retrieval; +32.8% on SWE-bench, KGCompass 58.3% SWE-bench Lite                                         |
|T2-41|FutureQueryEval (EMNLP 2025)                   |8    |Chunking (sec)        |22 rerankers × 40 variants; 5–15% degradation on temporally-unseen queries; listwise generalizes best                    |
|T2-42|LoCoMo-Plus                                    |9    |Memory (sec)          |Cue-trigger constraint-consistency; memory as implicit constraint not factual recall                                     |
|T2-43|LoCoMo audit (ATANT v1.1, dial481)             |10   |Memory (sec)          |LoCoMo has ~99 ground-truth errors; ~23% unscorable; treat published numbers skeptically                                 |
|T2-44|Chroma context rot (arxiv 2601.11564)          |7    |Chunking (sec)        |Non-linear degradation with KV-cache growth; context discipline > compute                                                |
|T2-45|Cloudflare Agent Memory                        |7    |Memory (sec)          |8-check verifier at ingestion; resolve relative dates to absolutes                                                       |

-----

## 9. Practical recommendations

### For the code review agent judge (severity ordinals)

**Architecture.** 3-judge cross-family panel (e.g., Claude Opus 4.6 + GPT-5.3-Codex + Gemini 3.1 Pro), aggregated via **CyclicJudge round-robin** for systematic-bias elimination at single-judge cost. Use **median** for severity (ordinal-appropriate); if judges disagree by ≥2 levels, escalate to human. For intra-panel calibration, weight judges using BT-σ discriminator parameters.

**Scale.** Keep your 4-level critical/high/medium/low — arxiv 2601.03444 empirically confirms this is near-optimum. Resist 10-point, 100-point, or sub-level additions. Use anchored rubric: each level has concrete positive and negative exemplars.

**Prompt pattern.** **Criteria injection + enforced reasoning-before-severity** (RewardBench 2 study: +3pp near-free; Sage shows self-generated rubrics reduce local inconsistency 16.1%). Format: “Before choosing severity, state (a) exploitability, (b) blast radius, (c) confidence. Each must justify the level.” Do *not* feed the agent’s own chain-of-thought to the judge (adversarial CoT manipulation, arxiv 2601.14691: +20–30pp false-positive inflation). Grade from diff + evidence only.

**Metrics to report.** Primary: **quadratic-weighted Cohen’s κ** (penalizes critical→low 9×). Secondary: **Krippendorff’s α with ordinal distance**. Robustness: **Gwet’s AC2-Q** if severity distribution skewed >3:1 (likely). Rank: **Kendall’s τ-b**. Deployment gates: κ_weighted ≥ 0.75 (block <0.60); ≥90% within ±1 level; ≥70% exact match. Track critical↔low flip rate separately — these are deployment killers.

**Calibration protocol.** 100–200 human-labeled findings as frozen golden set. Apply Rogan–Gladen correction extended to 4-class via Buonaccorsi confusion-matrix inversion. Compute Lang–Reiczigel CI. Re-run weekly AND on any model/prompt change. Apply CJE-style transport audit per severity class; recalibrate or refuse level claims if audit fails.

**Drift monitoring.** Adopt **RAND Judge Reliability Harness** as monthly regression suite. PELT+MBIC change-point detection on aggregate scores (Wiese blueprint). Alert on Hedges g > 0.2 vs baseline or κ drop > 0.05.

**Benchmark your judge.** Run CodeJudgeBench + AXIOM + JudgeBiasBench before deployment. If closed-API judges fail, consider fine-tuned specialized judge (Prometheus-2-style) to eliminate silent API drift.

**Hard ceiling.** If you judge frontier-agent output with a peer frontier judge, Hardt ceiling caps label savings at 2×. Budget for large human calibration accordingly.

### For the RAG three-way classifier with abstention

**Confidence signal.** Primary: **P(True)** extracted as single-token probability after “Is this classification correct? Reply 0 or 1.” Augment with self-consistency (3–5 samples, class-agreement rate) for hard cases only. If open-weights available, add **semantic entropy probe** (near-zero test-time cost). Add **sufficient-context autorater** (Joren) as orthogonal RAG-native signal. Combine via logistic regression trained on 400-item held-out calibration.

**Validate before deploying.** Phillips 2026 warning: compute AUROC of your confidence signal on held-out; require ≥ 0.65 before trusting. RAG reduces abstention (Joren): evaluate abstention specifically, not just accuracy.

**Abstention mechanism.** Treat {class1, class2, class3, abstain} as 4-option MCQA. Use **split conformal risk control** (Angelopoulos 2024 CRC) — calibrate a single threshold τ such that expected per-example cost on accepted items ≤ user budget α. 300–500 calibration examples sufficient for marginal; 2–4k if conditional coverage matters (likely — class prevalences almost certainly differ in deployment).

**Cost-asymmetric decision rule.** Bayesian Orchestration: choose action minimizing Σ_y P(y|x)·C(action, y) with abstain as explicit action. Don’t use threshold-per-class — it’s formally inadequate.

**Evaluation stack.** Primary: **expected cost under your (C_FP, C_FN, C_abstain) matrix** plotted vs coverage. Secondary: **AUGRC** (replaces/supplements AURC). Tertiary: **AUCM** (answerable-unanswerable 2×2) + **abstention precision/recall/F1** (AbstentionBench). Selective-accuracy at {80%, 90%, 100%} coverage for continuity with existing literature.

**Libraries.** TorchCP for CP calibration (native LLM support as of 2025). `facebookresearch/AbstentionBench` for abstention-eval prompts. `hljoren/sufficientcontext` reference implementation. `ppi-py` for PPI/EIF estimation.

**Drift protection.** Stratify calibration set by deployment class prior. Run class-conditional coverage checks monthly; adapt conformal scores via Cherian 2024 conditional CP if any class shows miscoverage >2 pp beyond target.

### For eval set construction from historical tickets

**Labeling protocol (end-to-end).**

1. **Stratified sampling** along (resolution-field value × ticket age × subsystem × resolver team). Document sample frame explicitly.
1. **LLM pre-labeling** via **Adjudicator** architecture: dynamic KG per item (text + metadata + history) + multi-persona council (Policy Expert, Contextual Analyst, Skeptical Adjudicator) + voting + KG-override for structural errors. On BugsRepo this hit 0.99 F1 vs 0.48 single-LLM.
1. **Active-testing prioritization** via GAT (40% error reduction vs random). Order by Fisher-information-based acquisition, not uncertainty sampling.
1. **Human expert adjudication** on 5–10% calibration slice. Use QUEST-style multi-adjudicator protocol until κ ≥ 0.7.
1. **Report Rogan–Gladen-corrected metrics** with Lang–Reiczigel CI + bootstrap CI. Document excluded fraction as survivorship disclosure.

**Proxy-bounded metrics.** Use **Rogan–Gladen** as primary: P_true = (P̂ + q₀ − 1)/(q₀ + q₁ − 1). Use **Natarajan** lower bound for worst-case reporting: P_true ≥ (P̂ − ρ₋)/(1 − ρ₊ − ρ₋). Inflate sample size ~2× for ε = 15%. Require ≥ 100 calibration items for stable q̂₀, q̂₁ estimates.

**Efficiency choice.** If calibration-test distribution shift is a concern (likely with historical tickets), prefer **Lee et al. plug-in** framework (robust to shift). If shift is small/controllable, prefer **EIF/PPI++** (3–15× narrower CIs). Always run CJE-style transport audit to detect shift.

**Survivorship bias.** Explicitly sample **shadow corpus** of non-ticketed events (on-call chats, monitoring auto-resolutions, silent log failures). Label a subset. Report metrics separately on ticketed vs shadow; report conservative **min(P_ticketed, P_shadow)** as survivorship-adjusted bound. Cite MS MARCO methodology as reference.

**Retrospective root-cause labeling.** LLM relabeler needs more context than ticket alone provides (Roy et al.: 66% of RCA failures from insufficient ticket info). Augment with KBA articles, similar-historical-incident retrieval, and diagnostic-tool access. Follow Ahmed et al. Microsoft protocol. Capture uncertainty per relabel.

**Arm-dependent bias warning.** arxiv 2601.21471 proves proxy-only comparison of agent variants is information-theoretically impossible under arm-dependent bias. Always include human audits when comparing agent versions.

### Cross-system eval infrastructure

**Shared components.**

- **Calibration/estimation library** (one implementation serving all three systems): RG correction, PPI++/EIF estimator, Lang–Reiczigel CI, adaptive calibration allocation. Based on Chen et al. 2601.05420 + Lee et al. 2511.21140.
- **Transport-audit module**: per-policy/per-version residual-mean test emitted with every eval run. Alerts on shift.
- **P(True) confidence elicitation library**: shared across severity judge confidence, RAG abstention confidence, and any planner-action confidence.
- **Active-testing acquisition module**: Fisher/influence-function-based selection for RAG calibration set expansion and planner eval set construction.
- **Judge Reliability Harness monthly regression suite**: adapted for each system’s ordinal/categorical output structure.

**Standard metrics.**

- Ordinal outputs: quadratic-weighted κ + Krippendorff’s α (ordinal distance) + Gwet’s AC2-Q (skewed) + Kendall’s τ-b.
- Abstention: AUCM + abstention precision/recall/F1 + AUGRC + cost-weighted risk-coverage.
- All metrics reported with bootstrap 95% CIs and Rogan–Gladen-corrected point estimates.

**Calibration monitoring.**

- Weekly golden-set re-run per system.
- Monthly JRH stress test per system.
- Change-point detection (PELT+MBIC) on aggregate metrics.
- Version-transition drill: on any model/prompt/retriever change, recalibrate + transport audit before releasing.

**Scale discipline.** 4–5-level ordinals across the board. Binary confidence prompts. Resist 10-point scales anywhere.

-----

## 10. What’s still missing

**Named-API-version judge drift study (GPT-4→4o→4.1→5→5.4; Claude 3→3.5→3.7→4→4.5→4.6; Gemini 1.5→2.0→2.5→3.1).** Why unanswered: the field has converged on “drift exists and is large” (Wiese) but not on systematic cross-version quantification. Too new; vendors don’t publish longitudinal behavior. Best available proxy: Wiese PLOS ONE methodology on anonymized families + your own weekly golden-set re-run. Recommended action: **run your own experiment** — maintain 240-prompt fixed bank with human severity labels and track weekly.

**LLM-native ordinal agreement metric.** Why unanswered: field hasn’t converged; classical methods (weighted κ, Krippendorff’s α, Gwet’s AC2) remain best available. Wrong framing may be part of it — ordinal severity is a domain question, not a methods question. Best available proxy: Krippendorff’s α with ordinal distance as primary (AXIOM, clinical-LLM), Gwet’s AC2-Q on skewed distributions. Recommended action: **adopt heuristic and measure** — report multiple metrics, publish your chosen combination as a practice contribution if adopted widely enough.

**Three-way-with-abstention benchmark.** Why unanswered: empirical LLM literature thinner for >2-class. Theory mature (Cao, Ramaswamy). Best available proxy: adapt KnowNo MCQA-with-abstain to 4-option {c1, c2, c3, abstain}. Recommended action: **run your own experiment** — construct a domain-specific three-way-with-abstention test set following AbstentionBench prompt templates; release if general enough.

**Longitudinal specialized-vs-frontier judge comparison.** Why unanswered: specialized judges (Prometheus-2, JudgeLM, Themis) have version-stability by construction but no published 6-month comparison vs API drift. Best available proxy: fine-tune a specialized judge on your severity annotations if drift becomes operationally painful. Recommended action: **wait for field to mature** unless drift exceeds κ-drop 0.10 per quarter, then fine-tune.

**Survivorship bias in LLM-era eval sets.** Why unanswered: field ignores it; MS MARCO is the only portable methodology and is IR-specific. Best available proxy: shadow-corpus sampling of non-ticketed events + conservative metric reporting. Recommended action: **run your own experiment** — sample and label a shadow corpus; treat it as evaluation-methodology contribution if results diverge materially.

**Cost-sensitive abstention canonical implementation.** Why unanswered: framing exists (Bayesian Orchestration, Conformal Arbitrage, Zellinger cascades) but no canonical library. Best available proxy: implement Bayesian decision rule + CRC-based threshold calibration manually. Recommended action: **adopt heuristic and measure** — publish your implementation if stable.

**Memory feedback-loop (ICRH) detection in planning systems.** Why unanswered: ICRH is conceptually mapped but no canonical benchmark. Best available proxy: MemoryAgentBench selective-forgetting subtests + LoCoMo-Plus constraint-consistency + multi-cycle stress runs of your own planner. Recommended action: **run your own experiment** — multi-cycle stress test with output-as-memory feedback is essential; no published benchmark suffices.

**Multi-class calibration-set allocation.** Why unanswered: Lee et al. adaptive allocation is binary-only. Best available proxy: stratify calibration set by true class; within-class allocate by per-class error rate. Recommended action: **adopt heuristic and measure**; extending Lee et al. to multi-class is publishable methods work if you do it carefully.

**Preference-leakage effect sizes for modern frontier models.** Why unanswered: ICLR 2026 paper identifies but doesn’t quantify across current generations. Best available proxy: Play Favorites methodology on Claude 4.6 / GPT-5.x / Gemini 3.x. Recommended action: **run your own experiment** on your code-review domain; report as practice contribution.