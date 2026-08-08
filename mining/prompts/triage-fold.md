# Weekly triage fold — one readable report

Two independent evaluations of the same week's nomination evidence sit in
the working directory: opus-eval.md (Claude Opus) and sol-eval.md (codex
sol). Either may be missing or truncated — if so, say which in the report
header and fold what exists.

Produce triage-report.md: plain and readable, no jargon — written for the
owner reading on a phone. Spell out shorthand the evaluators used.

STRUCTURE
1. Header: week, evidence volume, which evaluator lanes ran.
2. AGREED REAL GAPS (both said REAL-GAP): one short paragraph each — what
   keeps happening in plain words, the strongest single incident (one
   sentence plus transcript-path:line), and the candidate: pick the
   better-written draft, tighten it to at most 80 words, label its form
   (steering/hook/validator/skill/template).
3. DISAGREEMENTS (one says REAL-GAP, the other does not): both positions in
   one sentence each, what reading of the evidence decides it, and a
   recommended side.
4. COVERED-BUT-VIOLATED (steering exists and was ignored): name the rule and
   the incident; flag these as enforcement candidates (hook/validator).
5. SKIP LIST: one line per benign/insufficient class, reason in at most
   8 words.
6. SIGN-OFF QUEUE: numbered, priority-ordered, one line per candidate
   awaiting the owner's decision.

Keep the whole report under ~150 lines. Never invent a verdict absent from
both inputs. Where you compress, preserve the citations.
