# Success-mode experiment queue (designs; tasksets pending curation)

## exp-s1 — warm-specialist reuse (S6 causal claim)
Arms: warm-continue (SendMessage to a context-loaded diagnosis agent) vs fresh-dispatch,
on matched container/topology diagnosis tasks. Metrics: wall-clock, tokens,
probes-to-root-cause, wrong-attribution rate. Needs: ~10-item reproducible diagnosis
taskset (exp-3-shaped curation); the W2d/W2a-2/W2c incident family is the seed material.

## exp-s2 — convergence-discipline steering text (S1/S8)
Does the promoted rule text change fix-vs-redispatch choices on synthetic REJECT
scenarios? Harness: mechanism-claims shape (single-turn executor + codex judge), arms
with/without the rule in context. Items: REJECT verdicts with closed vs open findings;
truth = the S1 classification. Rides the exp-w3a harness once its citation-bar run lands.

## exp-s3 — reader+reasoner vs reasoner-alone (S11 counterfactual)
Arms: reasoner-alone vs reader-mines-cites→reasoner-adjudicates on code-tracing tasks
with known ground truth. Metrics: wrong-assertion rate, citation validity
(check_citations.py is the instrument), tokens, wall-clock. Trial 2026-07-26 validated
OUTPUT quality (zero fabrication, 17/17 evaluable); this exp supplies the counterfactual.
Instrument note: executor children must run isolated (harness patch 0c873a5) — the
superpowers-injection contamination would otherwise confound the reader arm.
