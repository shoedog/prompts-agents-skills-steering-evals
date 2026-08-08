# Weekly nomination triage — independent evaluation

You are one of two independent evaluators (the other is a different model
family; you cannot see its output). Evaluate each nomination class in the
week's evidence for whether it marks a REAL, OPERATIONALIZABLE gap.

INPUT
- The week's new evidence rows, grouped by nomination class with tallies:
  week-input.md (path given below the prompt).
- Full context: grep mining/out/failure_signatures.jsonl or
  mining/out/success_signatures.jsonl (fields: session, path, line_no,
  snippet) by the truncated session id to get the transcript `path`, then
  read the transcript around `line_no`. Judge from the transcript, not the
  snippet alone.
- Existing coverage to check BEFORE proposing anything new: the
  coverage-snapshot/ directory alongside the week input (steering, codex
  tail, validator list, TRACKER program sections — frozen at run start so a
  concurrent edit cannot color the verdict). ALWAYS compare the coverage
  artifact's git date against the incident dates: coverage NEWER than the
  incidents means the gap was real and has since been closed — report
  "COVERED-SINCE <date>", not ALREADY-COVERED, and recommend an adherence
  check instead of dismissal.

FOR EACH CLASS output exactly:

## <class>
- verdict: REAL-GAP | ALREADY-COVERED | BENIGN | INSUFFICIENT-EVIDENCE
- rationale: at most 3 sentences. ALREADY-COVERED must name the covering
  artifact (steering section / validator / hook). BENIGN means quotation,
  template artifact, or narration about this program — say which.
- evidence: 2-4 citations, each `transcript-path:line` — cite the transcript
  line you actually read, not the inbox row.
- IF REAL-GAP: candidate — form (steering|hook|validator|skill|template),
  draft text of at most 120 words, and the single incident that best
  motivates it.
- priority: HIGH | MED | LOW, from evidence count x session spread x cost of
  the failure (or value of the success practice). Priority ranks the NEED
  FOR ACTION, not the quality of the practice: ALREADY-COVERED and BENIGN
  classes are LOW unless you attach an enforcement-gap candidate.

RULES
- WRONG/SMELL discipline: a gap claim without a concrete incident citation
  is not REAL-GAP.
- Deployed steering that was violated is ALREADY-COVERED plus an
  enforcement-gap note (the candidate is then a hook/validator, never a
  restatement of the steering).
- Evidence admissibility: if you cannot read a cited transcript, say so and
  mark INSUFFICIENT-EVIDENCE — never judge from the snippet alone.
- Be concise. Findings, not narration.
