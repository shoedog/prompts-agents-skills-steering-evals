# Provenance note — experiment #1 RESCORE (neutral-findings scope)

This directory is a **rescore of `results/exp1-review-shape/weak`'s executor
outputs**, produced by `scripts/rejudge.py` (2026-07-03) — NOT a fresh
experiment run.

- **Executor evidence is shared verbatim**: every `calls/*.json` is a byte
  copy of the source run's record (verified with `diff -r`); costs/tokens are
  identical by construction. No executor call was re-made.
- **Only the judge was re-run** (40 live codex calls, 0 judge errors): each
  source judge record's `normalized_block` — the exact graded surface from the
  original run — was re-judged against the CURRENT truth + rubric + schema,
  after the neutral-findings scoring-scope change:
  - `neutral_findings` (OPTIONAL, seeded-only truth field): a finding matching
    an entry is NEITHER credited as a defect NOR counted as a false finding;
    the judge reports the count as `neutral_matched`.
  - Truth updates for the three contested exp1 items: rs-06 (import-visibility
    "time not imported" → neutral), rs-07 (has_expiry/AttributeError secondary
    concern → neutral), rs-17 (CLEAN — rollback-masking rationale added to
    `tempting_non_defects`; still a false finding, clean items stay strict).
- **Item-pass rule unchanged** (seeded: all defects found AND false_findings==0
  AND flagged; clean: false_findings==0 AND not flagged). Neutral matches never
  block or grant a pass. Seeded/adherence/verdict fields carried over from the
  source records (the truth edits do not affect them).

Report remains PROVISIONAL pending the human spot-check (`spotcheck.yaml` →
`scripts/check_spotcheck.py`).
