# Provenance note — experiment #1 run

Run executed at commit d14a2b3 (2026-07-03), before two later hardening fixes (028dfbe):

1. **Judge cwd isolation.** At run time the codex judge process inherited the repo root as cwd under a read-only sandbox, so blinding was enforced at the prompt level only (the judge prompt contained solely the normalized findings block + ground truth). No evidence of environmental leakage: judge outputs reference only prompt content, all 40 judgments were manually cross-verified against raw records (37/40 clear agreement, 3 contested items are ground-truth-scope questions, not leakage artifacts). Runs after 028dfbe execute the judge from an isolated scratch cwd.
2. **Stale-results guard.** The results dir was verified fresh for this run (exact 40 calls / 40 judge records, task-id sets complete per arm — reconfirmed by two independent reviews). Runs after 028dfbe refuse non-empty results dirs outright.

Metrics in this directory reproduce byte-identically from the committed records via `scripts/regen_report.py` (verified). Reports remain PROVISIONAL pending the human spot-check (`spotcheck.yaml` → `scripts/check_spotcheck.py`).
