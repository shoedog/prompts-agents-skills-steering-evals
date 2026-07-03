# Human-Moves Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A minimal runnable eval harness that tests whether each structural move from the Structural-Moves Catalog — encoded as a prompt, skill, or steering element — measurably improves a weaker executor on SWE tasks vs a strong-simple baseline, and at what total token cost.

**Architecture:** promptfoo runs the arms (two prompt variants × one task set) through a custom Python provider that shells out to `claude -p` (weak executor = Haiku 4.5) and logs per-call usage/cost. A blind binary judge (`codex exec`, gpt-5.5 — different model family) grades only the executor's final findings block against ground truth via a JSON output schema. ~100 lines of custom metrics compute pass rates, deltas, total-token-cost deltas, adherence, and TP/FP/TN/FN-with-base-rate, with hard per-model-tier separation. Opik traces when configured, JSONL fallback otherwise. DeepEval wraps a 5-task smoke run as the CI gate.

**Tech Stack:** Python 3.12 (uv venv), promptfoo (pinned, local npm), deepeval, opik, pyyaml, tiktoken, pytest; `claude` CLI (executor transport), `codex` CLI (judge + reviews).

## Global Constraints

- The catalog doc `Reasoning-Capture Formats for SWE Tasks_ Element-Level Evidence Triage and Structural Moves Catalog.md` (repo root) is the SOLE source of truth for the per-move classifications, verdicts, and evidence tiers recorded in `moves.yaml` (moves metadata only — the harness design itself is governed by this plan's constraints). Where the user's summary and the doc differ on moves metadata, the doc governs.
- Binary verdicts ONLY at every judgment point. No Likert scales, no 1-10 scores, anywhere — including judge rubrics, deepeval metrics, and report tables.
- Every element artifact snippet ≤ 150 tokens (tiktoken `o200k_base`). Every runtime trigger ≤ 3 non-empty lines. `scripts/lint_artifacts.py` MUST fail any violation.
- No narrative repository overviews / architecture prose in any generated steering, skill, or context artifact — EXCEPT the quarantined negative control at `artifacts/negative_control/narrative_overview.md`, which must never be composed into a baseline.
- One experiment varies exactly ONE treatment artifact. `varied_element` must resolve to exactly one artifact FILE — either an element deployment form (`artifacts/elements/<move-id>/<form>.md`) or a settled composite (`artifacts/composites/<id>/<form>.md`; the review shape is a composite of settled moves, deliberately varied as one unit to validate true-positive detection). `harness/config.py` MUST reject lists or any treatment composing >1 artifact file over baseline.
- Arm identity is hard-coded, never inferred: the runner generates TWO one-arm promptfoo configs (baseline, treatment) and runs them sequentially; `arm` is a mandatory field in every per-call record and every judge record.
- Per-call records are one JSON file per call (`calls/<arm>-<task_id>.json`, `judge/<arm>-<task_id>.json`) — no shared-file concurrent appends. Each executor call gets its own sandbox subdir.
- The judge receives a NORMALIZED findings block: deterministically re-rendered as `VERDICT: <APPROVE|REJECT>` + numbered finding sentences only, all other prose dropped — so treatment style cannot leak to the judge.
- Repeated invalid judge JSON (after one retry) is a HARNESS failure: record `judge_error: true` on the row; the run exits nonzero if any judge_error exists.
- Estimand caveat (report must state it): both arms share the binary output format, so experiment #1 measures the review PROCEDURE conditional on a shared binary output format; the treatment's literal workspace labels are instrumentation, not part of the claimed effect.
- Results are stored per executor tier: `results/<exp-id>/<tier>/…`. No function may aggregate metrics across tiers; mixing tiers raises `TierMixError`.
- The judge sees ONLY the executor's extracted final findings block and the ground truth — never the executor's reasoning, prompt, or arm label.
- Every experiment config declares: baseline prompt path, the single varied element, task set path, judge (provider+model) + rubric path, token budget.
- All artifacts compact and imperative. When in doubt, cut.
- Weak executor model id: `claude-haiku-4-5-20251001` (tier name `weak`). Judge: `codex exec --model gpt-5.5` with `-c model_reasoning_effort="medium"`.
- Executor `claude -p` calls run with cwd set to an empty per-run sandbox dir and flags `--output-format json --max-turns 1 --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disallowedTools "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Glob,Grep,Read,Task"`. If the CLI rejects a flag, drop only the rejected flag and report which.
- Do NOT run experiments 2–4 in this session. Experiment #1 (review shape) only, plus the 5-task smoke set.
- Python via the project venv `.venv` (uv, Python 3.12). promptfoo pinned in `package.json`, invoked as `npx promptfoo`. Set `PROMPTFOO_PYTHON` to the venv python when invoking promptfoo.

## File Map

```
moves.yaml                         # Task 2
scripts/check_moves.py             # Task 2
scripts/lint_artifacts.py          # Task 3
scripts/check_taskset.py           # Task 5
artifacts/baseline/review.md       # Task 3 — strong-simple review baseline
artifacts/baseline/output_format.md# Task 3 — shared FINDINGS block spec (both arms)
artifacts/elements/<move-id>/{prompt.md,skill.md,steering.md}   # Task 3
artifacts/composites/review-shape/prompt.md                     # Task 3 — exp #1 treatment
artifacts/runtime/<move-id>/trigger.md                          # Task 3
artifacts/negative_control/narrative_overview.md                # Task 3
tasksets/smoke/{manifest.yaml,items/<id>/…}                     # Task 5 (5 items)
tasksets/review-seeded/{manifest.yaml,items/<id>/…}             # Task 5 (20 items)
harness/{__init__.py,config.py,judge.py,metrics.py,report.py,tracing.py,run.py,gen_promptfoo.py}  # Task 6
harness/providers/{claude_cli.py,codex_cli.py,promptfoo_claude.py}  # Task 4
harness/asserts/judge_assert.py    # Task 6
harness/rubrics/{review_judge.md,review_judge.schema.json}      # Task 4
experiments/{smoke.yaml,exp1-review-shape.yaml}                 # Task 6
ci/test_smoke.py                   # Task 7
results/<exp-id>/<tier>/{prompts/,promptfoo-<arm>.yaml,promptfoo-<arm>.json,calls/,judge/,metrics.json,report.md,spotcheck.md,spotcheck.yaml}
pyproject.toml, package.json, .gitignore, README.md             # Task 1
```

---

## Task 1: Environment and repo scaffold

**Files:**
- Create: `pyproject.toml`, `package.json`, `.gitignore`, `README.md`, empty dir tree per File Map (use `.gitkeep` where needed)

**Interfaces:**
- Produces: `.venv` with Python 3.12 and deps importable (`yaml`, `tiktoken`, `deepeval`, `opik`, `pytest`); `node_modules/.bin/promptfoo` pinned.

- [ ] **Step 1: Python env.** Run `uv venv --python 3.12 .venv`. Create `pyproject.toml`:

```toml
[project]
name = "human-moves-eval"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pyyaml>=6.0", "tiktoken>=0.8", "deepeval>=3.0", "opik>=1.7", "pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["ci", "harness"]
```

Install: `uv pip install -e .` (with `VIRTUAL_ENV=$PWD/.venv`). Verify: `.venv/bin/python -c "import yaml, tiktoken, deepeval, opik, pytest; print('ok')"` prints `ok`. If a dep's floor is unsatisfiable, install the latest available and record the actual version in the report; do not silently downgrade Python.

- [ ] **Step 2: Node env.** Run `npm init -y` then `npm install --save-dev promptfoo@0.121.17`. Edit `package.json`: set `"name": "human-moves-eval"`, `"private": true`. Verify: `npx promptfoo --version` prints `0.121.17`.

- [ ] **Step 3: .gitignore + README.** `.gitignore`: `.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, `.promptfoo/`, `results/**/sandbox/`, `.superpowers/`. `README.md`: ≤30 lines — one-paragraph purpose, dir map, `how to run: .venv/bin/python -m harness.run experiments/smoke.yaml`. No narrative architecture prose.

- [ ] **Step 4: Dir tree.** Create all directories from the File Map with `.gitkeep`. Verify: `git status --short` shows only intended files.

- [ ] **Step 5: Commit** `chore: scaffold env (uv venv py3.12, promptfoo pinned, dir tree)`.

## Task 2: moves.yaml from the catalog (source of truth)

**Files:**
- Create: `moves.yaml`, `scripts/check_moves.py`
- Read: `Reasoning-Capture Formats for SWE Tasks_ Element-Level Evidence Triage and Structural Moves Catalog.md` — especially “THE ELEMENT × EVIDENCE TRIAGE TABLE” (line ~89), “THE STRUCTURAL-MOVES CATALOG” (~119), “What to build vs. what to test” (~165), “Gaps” (~193).

**Interfaces:**
- Produces: `moves.yaml` top-level key `moves:` — list of mappings, each with EXACTLY these keys: `id` (kebab-case slug), `name`, `classification` (`element`|`runtime`), `verdict` (`build`|`exclude`|`test_cheap`|`must_test`), `eval_shape` (`ablation`|`adherence`|`triggering`|`negative_control`), `evidence_tier` (`swe`|`general`|`human`), `notes` (1–2 sentences, verbatim-faithful to the doc's triage language). Task 3 keys artifact dirs by these `id` values.

- [ ] **Step 1: Write the failing check.** Create `scripts/check_moves.py` (complete file):

```python
#!/usr/bin/env python3
"""Validate moves.yaml: parses, round-trips, every move fully populated."""
import sys, yaml

REQUIRED = ["id", "name", "classification", "verdict", "eval_shape", "evidence_tier", "notes"]
ENUMS = {
    "classification": {"element", "runtime"},
    "verdict": {"build", "exclude", "test_cheap", "must_test"},
    "eval_shape": {"ablation", "adherence", "triggering", "negative_control"},
    "evidence_tier": {"swe", "general", "human"},
}

def main(path="moves.yaml"):
    raw = open(path).read()
    data = yaml.safe_load(raw)
    errors = []
    moves = data.get("moves") if isinstance(data, dict) else None
    if not isinstance(moves, list) or not moves:
        sys.exit("FAIL: top-level 'moves' list missing or empty")
    ids = set()
    for i, m in enumerate(moves):
        for k in REQUIRED:
            v = m.get(k)
            if v in (None, ""):
                errors.append(f"moves[{i}] ({m.get('id','?')}): missing/empty '{k}'")
            elif k in ENUMS and v not in ENUMS[k]:
                errors.append(f"moves[{i}] ({m.get('id','?')}): {k}={v!r} not in {sorted(ENUMS[k])}")
        if set(m) - set(REQUIRED):
            errors.append(f"moves[{i}]: unexpected keys {sorted(set(m) - set(REQUIRED))}")
        if m.get("id") in ids:
            errors.append(f"duplicate id {m['id']!r}")
        ids.add(m.get("id"))
    if yaml.safe_load(yaml.safe_dump(data)) != data:
        errors.append("round-trip mismatch")
    if errors:
        print("\n".join(errors)); sys.exit(f"FAIL: {len(errors)} error(s)")
    print(f"OK: {len(moves)} moves valid")

if __name__ == "__main__":
    main(*sys.argv[1:])
```

Run `.venv/bin/python scripts/check_moves.py` — expect FAIL (no moves.yaml).

- [ ] **Step 2: Extract the moves from the catalog doc.** Read the doc sections listed above. Populate `moves.yaml` with EVERY structural move the catalog defines (the user's summary says 18; trust the doc's own enumeration — if the doc yields a different count, populate what the doc defines and flag the discrepancy in your report rather than forcing 18). `classification`, `verdict`, and `evidence_tier` must be taken verbatim from the doc's triage table / build-vs-test matrix, mapped onto the enums (e.g. doc says “build into baseline, don’t test” → `build`; “exclude / negative control” → `exclude`; “test if cheap” → `test_cheap`; “must test” → `must_test`). `eval_shape`: elements→`ablation`, runtime strategies→`adherence`, skill-deployment triggering questions→`triggering`, the excluded narrative-overview move→`negative_control`; if the doc explicitly assigns a different shape for a move, follow the doc. Header comment in moves.yaml: `# Source of truth: <doc filename>. Do not edit without re-checking the catalog.`

- [ ] **Step 3: Run `.venv/bin/python scripts/check_moves.py`** — expect `OK: N moves valid`.

- [ ] **Step 4: Commit** `feat: moves.yaml encoding structural-moves catalog + check script`.

## Task 3: Artifact library + token-budget lint

**Files:**
- Create: `scripts/lint_artifacts.py`; `artifacts/baseline/review.md`; `artifacts/baseline/output_format.md`; for each `classification: element` move in `moves.yaml` with verdict ≠ `exclude`: `artifacts/elements/<id>/prompt.md`, `skill.md`, `steering.md`; for each `classification: runtime` move: `artifacts/runtime/<id>/trigger.md`; `artifacts/composites/review-shape/prompt.md` (the settled review-shape composite — exp #1's treatment; NOT a moves.yaml entry, it composes several settled moves as one unit); `artifacts/negative_control/narrative_overview.md`.
- Read: `moves.yaml` (ids and notes), catalog doc sections “Per-type capture shapes” (~line 71) and “THE STRUCTURAL-MOVES CATALOG” (~119) for what each move's content looks like.

**Interfaces:**
- Consumes: `moves.yaml` ids.
- Produces: artifact paths consumed by `harness/gen_promptfoo.py` (Task 6). `artifacts/composites/review-shape/prompt.md` is experiment #1's treatment. `artifacts/baseline/review.md` + `artifacts/baseline/output_format.md` compose the baseline arm.

- [ ] **Step 1: Write the lint (complete file `scripts/lint_artifacts.py`):**

```python
#!/usr/bin/env python3
"""Fail any element artifact >150 tokens (o200k_base) or trigger >3 non-empty lines."""
import sys, pathlib, tiktoken

ENC = tiktoken.get_encoding("o200k_base")
CAP = 150
errors = []
root = pathlib.Path("artifacts")

# Completeness: every non-excluded element move needs all 3 forms; every runtime move needs trigger.md
moves = yaml.safe_load(open("moves.yaml"))["moves"]
for m in moves:
    if m["classification"] == "element" and m["verdict"] != "exclude":
        for form in ("prompt.md", "skill.md", "steering.md"):
            if not (root / "elements" / m["id"] / form).is_file():
                errors.append(f"missing artifacts/elements/{m['id']}/{form}")
    if m["classification"] == "runtime":
        if not (root / "runtime" / m["id"] / "trigger.md").is_file():
            errors.append(f"missing artifacts/runtime/{m['id']}/trigger.md")
if not (root / "composites/review-shape/prompt.md").is_file():
    errors.append("missing artifacts/composites/review-shape/prompt.md")

for p in sorted(root.glob("elements/*/*.md")) + sorted(root.glob("composites/*/*.md")) + sorted(root.glob("baseline/*.md")):
    n = len(ENC.encode(p.read_text()))
    if n > CAP:
        errors.append(f"{p}: {n} tokens > {CAP}")
for p in sorted(root.glob("runtime/*/trigger.md")):
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    if len(lines) > 3:
        errors.append(f"{p}: {len(lines)} non-empty lines > 3")
if errors:
    print("\n".join(errors)); sys.exit(f"FAIL: {len(errors)} violation(s)")
print("OK: all artifacts present and within budget")
```

(add `import yaml` to the imports)

Note: `artifacts/negative_control/` is deliberately NOT linted for the cap (it exists to be bloated) — but keep it ≤600 tokens so future experiment 2 stays cheap.

- [ ] **Step 2: Baseline review prompt** (`artifacts/baseline/review.md`) — the strong-simple baseline. It embeds the settled positives EXCEPT the review shape (that's the treatment): goal restatement, compact imperative form, explicit stop criterion. It must NOT contain: criteria checklist, disconfirm-first instruction, default-REJECT stance, or a separate verification stage. Exact content:

```markdown
Review the code change below. Goal: decide whether this diff is safe to merge, and report any defects it introduces.

Read the context, then the diff. Report every defect you find with its location and why it is wrong. If you find no defects, say so.

Stop when you have examined the whole diff once and reported your conclusion.
```

- [ ] **Step 3: Shared output format** (`artifacts/baseline/output_format.md`) — appended to BOTH arms so parseability is not a confound. Exact content:

```markdown
End your response with exactly this block:

## FINDINGS
VERDICT: APPROVE or REJECT
1. <file>:<line> — <one-sentence defect description>
(number each finding; write "No findings." instead of a list if none)

Everything above the ## FINDINGS block is your workspace; only the block is graded.
```

- [ ] **Step 4: Element artifacts + the review-shape composite.** For each element move: `prompt.md` (imperative section for a task prompt), `skill.md` (same content shaped as a SKILL.md section with a one-line `when to use`), `steering.md` (CLAUDE.md-style standing directive). Each ≤150 tokens, imperative, no meta-commentary. Separately, `artifacts/composites/review-shape/prompt.md` must contain exactly these four moves and nothing else (this is exp #1's treatment):

```markdown
Review procedure — follow in order:
1. Walk this checklist against the diff, one item at a time: correctness of boundary conditions; error/exception paths; resource lifecycle (open/close, acquire/release); state mutation and aliasing; API-contract conformance with the surrounding code.
2. Disconfirm first: for each candidate finding, actively look for evidence it is NOT a bug before accepting it.
3. Default-REJECT: approve only if you completed the checklist and found no defect.
4. Verify separately: after drafting findings, re-derive each one from the diff alone; drop any you cannot re-derive.
Label these workspace sections literally: CHECKLIST, DISCONFIRM, VERIFY.
```

If the lint reports >150 tokens, compress the checklist items (not the four moves or the three literal labels — the adherence detector in Task 6 matches those labels exactly).

- [ ] **Step 5: Runtime triggers.** For each runtime move: `trigger.md`, 1–3 imperative lines instructing the executor to PERFORM the move (e.g. disconfirmation: `Before accepting any hypothesis, state one observation that would falsify it and check for that observation. Reject the hypothesis if the falsifier is present.`). No explanations.

- [ ] **Step 6: Negative control** (`artifacts/negative_control/narrative_overview.md`): a plausible ~400–600-token narrative repository overview (“This repository follows a layered architecture…”) of a generic Python service — prose, zero actionable directives. Header comment: `<!-- NEGATIVE CONTROL. Never compose into a baseline. Expected: no success gain, token inflation. -->`

- [ ] **Step 7: Run `.venv/bin/python scripts/lint_artifacts.py`** — expect `OK`. Also run `scripts/check_moves.py` still OK.

- [ ] **Step 8: Commit** `feat: artifact library (elements x3 forms, runtime triggers, baselines, negative control) + lint`.

## Task 4: Model providers + judge rubric

**Files:**
- Create: `harness/__init__.py`, `harness/providers/__init__.py`, `harness/providers/claude_cli.py`, `harness/providers/codex_cli.py`, `harness/rubrics/review_judge.md`, `harness/rubrics/review_judge.schema.json`, `harness/tests/test_providers.py`

**Interfaces:**
- Produces:
  - `claude_cli.run_claude(prompt: str, model: str, cwd: str, timeout: int = 300) -> dict` returning `{"output": str, "input_tokens": int, "output_tokens": int, "cost_usd": float, "duration_ms": int, "raw": dict}`. `input_tokens` = usage input_tokens + cache_creation_input_tokens + cache_read_input_tokens (total tokens processed; note in docstring that CLI overhead is constant across arms so deltas isolate the artifact).
  - `codex_cli.run_codex(prompt: str, schema_path: str | None = None, model: str = "gpt-5.5", effort: str = "medium", timeout: int = 300) -> dict` returning `{"output": str, "tokens_used": int | None}`.
- Consumed by: Task 6's promptfoo provider shim and judge.

- [ ] **Step 1: Failing tests** (`harness/tests/test_providers.py`): mock `subprocess.run` to return a canned claude JSON (use the real shape: `{"type":"result","result":"OK","total_cost_usd":0.019,"usage":{"input_tokens":9,"cache_creation_input_tokens":8269,"cache_read_input_tokens":17209,"output_tokens":210},"duration_ms":3759}`) and assert the parsed dict; canned codex last-message file; assert timeout raises; assert claude flag list contains `--output-format json` and `--disallowedTools`. Run: expect FAIL (module missing).

- [ ] **Step 2: Implement `claude_cli.py`.** Build argv: `claude -p <prompt> --model <model> --output-format json --max-turns 1 --strict-mcp-config --mcp-config {"mcpServers":{}} --disallowedTools Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Glob,Grep,Read,Task`. `subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)`. Parse stdout JSON; on `is_error` or nonzero returncode raise `ProviderError` with stderr tail. Implement `codex_cli.py`: write prompt to stdin, use `codex exec --sandbox read-only --model <model> -c model_reasoning_effort="<effort>" -o <tmpfile> [--output-schema <schema_path>] -`; read `<tmpfile>` as output; parse `tokens used\n<n>` from stdout if present else None.

- [ ] **Step 3: Judge rubric** (`harness/rubrics/review_judge.md`, complete content):

```markdown
You are grading a code-review finding list against ground truth. You see ONLY the findings block and the ground truth. Answer with JSON per the schema. Binary judgments only.

For each ground-truth defect: found=true iff some finding identifies the same underlying defect (same root cause; line numbers may be approximate; wording may differ). Paraphrase is fine; a vague "something wrong in this function" does NOT count. When the ground truth provides acceptable_match or reject_if guidance for a defect, follow it exactly.
false_findings: count of findings that do not correspond to any ground-truth defect. Style nits and true statements that are not defects count as false findings. For clean items the ground truth may list known tempting non-defects — a finding matching one of those is a false finding.
verdict_flagged: true iff the block's VERDICT is REJECT.
If the findings block is missing or unparseable, set parse_ok=false and every found=false.
```

`review_judge.schema.json`:

```json
{
  "type": "object",
  "properties": {
    "parse_ok": {"type": "boolean"},
    "defects": {"type": "array", "items": {"type": "object", "properties": {"defect_id": {"type": "string"}, "found": {"type": "boolean"}}, "required": ["defect_id", "found"], "additionalProperties": false}},
    "false_findings": {"type": "integer"},
    "verdict_flagged": {"type": "boolean"}
  },
  "required": ["parse_ok", "defects", "false_findings", "verdict_flagged"],
  "additionalProperties": false
}
```

- [ ] **Step 4: Live smoke (one call each).** `.venv/bin/python -c` snippet calling `run_claude("Reply with exactly: OK", "claude-haiku-4-5-20251001", cwd="/tmp")` and `run_codex("Reply with exactly: OK")`; both return output containing `OK`. If a claude flag is rejected, drop only that flag and note it in the task report.

- [ ] **Step 5: Run tests** `.venv/bin/pytest harness/tests/test_providers.py -v` — PASS. **Commit** `feat: claude/codex CLI providers + blind binary judge rubric`.

## Task 5: Task sets — smoke (5) and review-seeded (20)

**Files:**
- Create: `tasksets/review-seeded/manifest.yaml`, `tasksets/review-seeded/items/<id>/{context.md,diff.patch,truth.yaml}` ×20; `tasksets/smoke/…` ×5 (same format); `scripts/check_taskset.py`

**Interfaces:**
- Produces: manifest format consumed by Task 6:

```yaml
# tasksets/review-seeded/manifest.yaml
taskset: review-seeded
task_family: review
items:
  - {id: rs-01, seeded: true}
  - {id: rs-02, seeded: false}
  # …
```

Item format: `context.md` (≤25 lines: what the function/module is for, its contract — imperative, no narrative filler); `diff.patch` (unified diff, 20–120 lines, realistic Python); `truth.yaml`:

```yaml
seeded: true
defects:
  - id: rs-01-d1
    defect_class: boundary            # one of the 8+ classes from Step 2
    location: "orders.py:42"
    hunk_lines: "38-47"               # line range of the changed hunk containing it
    description: "uses > instead of >= so the last page is dropped"
    root_cause: "strict inequality excludes the final page index"
    bad_behavior: "requests for the last page return an empty list"
    minimal_trigger: "total_items exactly divisible by page_size, request last page"
    acceptable_match: "any finding naming the >/>= comparison or the dropped last page"
    reject_if: "generic 'pagination looks wrong' without naming the comparison or symptom"
# clean items:
# seeded: false
# defects: []
# clean_rationale: "retry loop bounds are correct: range(1, n+1) is intentional"
# tempting_non_defects:
#   - "the bare except at line 30 re-raises, so it does not swallow errors"
```

- [ ] **Step 1: Write `scripts/check_taskset.py`** — validates: manifest parses; every item dir exists with all 3 files; every `seeded: true` item has 1–2 defects each carrying ALL fields shown in the truth.yaml example (defect_class, location, hunk_lines, description, root_cause, bad_behavior, minimal_trigger, acceptable_match, reject_if); every `seeded: false` has 0 defects plus `clean_rationale` and `tempting_non_defects` (list, may note why each tempting spot is fine); diff applies-shaped (`--- `/`+++ ` hunks present); ids unique; prints seeded/clean counts and base rate. ~50 lines, same style as check_moves.py. Run — FAIL (nothing exists).

- [ ] **Step 2: Build `review-seeded`: 20 items, 14 seeded / 6 clean (base rate 0.7).** Each seeded item injects 1–2 SUBTLE real defects into an otherwise-correct realistic function (do not use famous textbook bugs verbatim). Cover at least 8 distinct defect classes across the set: off-by-one/boundary, inverted condition, wrong dict key/attr, mutable default argument, resource leak on error path, swallowed exception, timezone/UTC confusion, wrong operator precedence, stale cache/invalidations, unicode/bytes mix. Clean items must be genuinely clean but non-trivial (a competent reviewer could be tempted — e.g. code that LOOKS like an off-by-one but is correct). Domains: vary (pagination, billing, retry logic, parsing, caching, file I/O, date math, validation). Defect descriptions in truth.yaml must be specific enough for a blind judge to match findings against.

- [ ] **Step 3: Build `smoke`: 5 items (3 seeded / 2 clean), same format,** smaller diffs (≤40 lines) so the smoke run is fast. May reuse defect classes.

- [ ] **Step 4: Run `.venv/bin/python scripts/check_taskset.py tasksets/review-seeded` and `… tasksets/smoke`** — both OK with expected counts.

- [ ] **Step 5: Self-check pass:** for every seeded item, re-read the diff and confirm the defect is real and the truth description matches the actual line. For every clean item, confirm no unintended defect slipped in (mentally execute edge cases). Fix anything found.

- [ ] **Step 6: Commit** `feat: review-seeded (20) and smoke (5) task sets + validator`.

## Task 6: Harness core — config, runner, judge assert, metrics, report

**Files:**
- Create: `harness/config.py`, `harness/gen_promptfoo.py`, `harness/asserts/judge_assert.py`, `harness/judge.py`, `harness/metrics.py`, `harness/report.py`, `harness/tracing.py`, `harness/run.py`, `harness/providers/promptfoo_claude.py`, `experiments/smoke.yaml`, `experiments/exp1-review-shape.yaml`, `harness/tests/test_config.py`, `harness/tests/test_metrics.py`

**Interfaces:**
- Consumes: providers (Task 4 signatures), artifact paths (Task 3), manifest/truth format (Task 5).
- Produces: `python -m harness.run experiments/<exp>.yaml` executes end-to-end and writes `results/<exp-id>/<tier>/{prompts/,promptfoo-<arm>.yaml,promptfoo-<arm>.json,calls/*.json,judge/*.json,metrics.json,report.md,spotcheck.md,spotcheck.yaml}`.

**Experiment config schema** (`experiments/exp1-review-shape.yaml`, complete):

```yaml
id: exp1-review-shape
task_family: review
eval_shape: ablation               # ablation|adherence|triggering (validation only for now)
baseline_prompt: [artifacts/baseline/review.md, artifacts/baseline/output_format.md]
varied_element: composites/review-shape   # SINGULAR; resolves to artifacts/<value>/<form>.md — exactly one file. config.py rejects lists.
varied_element_form: prompt        # prompt|skill|steering — which deployment form to compose
taskset: tasksets/review-seeded
executor: {model: claude-haiku-4-5-20251001, tier: weak}
judge: {provider: codex, model: gpt-5.5, effort: medium, rubric: harness/rubrics/review_judge.md, schema: harness/rubrics/review_judge.schema.json}
token_budget: {max_cost_usd: 10.0, max_items: 20}
negative_control: false            # smoke.yaml: same but taskset: tasksets/smoke, max_items: 5
```

- [ ] **Step 1: Failing tests.** `test_config.py`: valid config loads; `varied_element: [a, b]` raises `ConfigError("one element per experiment")`; `varied_element` not resolving to exactly one existing artifact file raises; missing any required key raises; `negative_control` defaults false. `test_metrics.py` (synthetic rows, no model calls): pass-rate + Wilson 95% CI math on a known case (7/10 → CI ≈ (0.397, 0.892)); token totals/delta computation incl. the fresh/cache_creation/cache_read/output breakdown; confusion matrix from item rows (assert TP/FP/TN/FN and base rate on a hand-built 6-row case); paired flip table joins on task_id across arms; `TierMixError` raised when rows carry two tiers; cost-adjusted-verdict flag set when win && token delta >20%; harness-broken flag when `negative_control && treatment_win`; `composite_floored` flag when both arms' item-pass rate < 0.15; `triggering_metrics` precision/recall/base-rate on a synthetic 10-row case; rows with `judge_error: true` are excluded from pass rates but counted in a `judge_errors` field. Run — FAIL.

- [ ] **Step 2: `config.py`** — dataclass + loader + validation per the schema above (paths must exist; exactly one varied element; budget keys required).

- [ ] **Step 3: promptfoo layer — TWO one-arm configs, arm hard-coded everywhere.** `gen_promptfoo.py`: given a config, for each arm in (`baseline`, `treatment`): (a) compose the arm prompt file under `results/<id>/<tier>/prompts/<arm>.txt` — baseline = concat of `baseline_prompt` files + `\n\n{{task_input}}`; treatment = same + the single artifact `artifacts/<varied_element>/<form>.md` inserted after the baseline prompt files (before the task input); GUARD: after composition, if the treatment prompt still contains an unfilled `<…>` template slot, raise `ConfigError` ("task-specific element requires per-task instantiation — not supported yet") — several element artifacts are deliberately templated and must not reach an executor raw (exp #1's composite is fully concrete); (b) emit `results/<id>/<tier>/promptfoo-<arm>.yaml`:

```yaml
prompts:
  - {id: file://…/prompts/<arm>.txt, label: <arm>}
providers:
  - id: file://harness/providers/promptfoo_claude.py
    config: {model: <executor.model>, tier: <executor.tier>, arm: <arm>, exp_id: …, results_dir: <abs results dir>}
tests:
  # one per item:
  - vars: {task_id: rs-01, seeded: true, arm: <arm>, task_input: <context.md + diff.patch contents>, truth_path: <abs path>, results_dir: <abs>, exp_id: …, tier: weak, judge_json: <json-encoded judge config>}
    assert: [{type: python, value: file://harness/asserts/judge_assert.py}]
```

`promptfoo_claude.py`: `call_api(prompt, options, context)` → arm/exp/tier from `options["config"]`, task_id from `context["vars"]`; calls `run_claude` with per-call sandbox cwd `results_dir/sandbox/<arm>-<task_id>/` (created fresh); writes `results_dir/calls/<arm>-<task_id>.json` — one JSON object with MANDATORY keys `{exp_id, arm, task_id, tier, model, fresh_input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens, input_tokens_logical (sum of first three), cost_usd, duration_ms}`; returns `{"output": out["output"], "tokenUsage": {"prompt": logical_in, "completion": out_toks, "total": sum}, "cost": cost}`.

`judge_assert.py`: `get_assert(output, context)` → (1) extract from last `## FINDINGS` to end; (2) NORMALIZE deterministically: regex out the `VERDICT: APPROVE|REJECT` line and the numbered finding lines (or `No findings.`), re-render as a canonical block, drop all other prose — this is the ONLY text the judge sees besides ground truth (no treatment style can leak); unparseable verdict → `parse_ok=false`, item fails, no judge call; (3) compute `adherence_labels` LOCALLY by regex on the workspace (text before `## FINDINGS`) for the literal labels CHECKLIST/DISCONFIRM/VERIFY — never sent to the judge; (4) call `harness.judge.judge_review(normalized_block, truth, judge_cfg)`; retry once on invalid JSON; a second failure → `judge_error: true` (harness failure, item excluded from pass metrics, run will exit nonzero); (5) write `results_dir/judge/<arm>-<task_id>.json` with `{exp_id, arm, task_id, tier, seeded, parse_ok, defects: […], false_findings, verdict_flagged, item_pass, judge_error, adherence_labels: {checklist, disconfirm, verify}}`; (6) return `{"pass": item_pass, "score": 1.0 if item_pass else 0.0, "reason": …}`. Item pass rule: seeded → all defects found AND false_findings==0 AND verdict_flagged; clean → false_findings==0 AND not verdict_flagged.

- [ ] **Step 4: `judge.py`** — builds the judge prompt: rubric text + `GROUND TRUTH:\n<truth.yaml defects rendered as id: description>` + `FINDINGS BLOCK:\n<extracted block>`; calls `run_codex(prompt, schema_path=…)`; parses/validates JSON (retry once on invalid JSON); returns dict. NEVER include executor reasoning, prompt text, or arm label in the judge prompt.

- [ ] **Step 5: `metrics.py` (the ~100 custom lines).** Input: globbed `calls/*.json` + `judge/*.json` rows for ONE results dir. Functions: `pass_rate(rows, arm)` (excludes judge_error rows; returns k, n, rate, wilson_ci); `wilson_ci(k, n)`; `token_totals(calls, arm)` → dict {fresh_input, cache_creation, cache_read, output, logical_total, cost_usd} — logical tokens and USD reported SEPARATELY (cache warming is arm-order dependent; USD does not isolate the artifact); `delta(a, b)`; `confusion(rows, arm)` → item-level TP/FP/TN/FN + base rate (TP = seeded & verdict_flagged; FN = seeded & !flagged; FP = clean & flagged; TN = clean & !flagged) + defect-level recall (found defects / all seeded defects) + finding-level false-finding count; `paired_flips(rows)` → join arms on task_id → {both_pass, both_fail, only_baseline, only_treatment}; `adherence(rows)` → treatment-arm per-directive rates keyed by directive id (`review-shape.checklist`, `review-shape.disconfirm`, `review-shape.verify`) plus all-three rate — structured as `{directive_id: rate}` so adherence-battery experiments can cross compliance × outcome later; `triggering_metrics(rows)` → from rows `{should_trigger: bool, did_trigger: bool}` compute precision, recall, TP/FP/TN/FN, and base rate — never bare accuracy (shape (c) support; unit-tested with synthetic rows, no live triggering experiment this session); `flags(...)` → `cost_adjusted_verdict` (treatment pass-rate > baseline AND logical token delta > +20%), `harness_broken` (config.negative_control AND treatment beats baseline), `composite_floored` (both arms' item-pass < 0.15 → report must lead with defect-level recall + verdict confusion and mark the composite metric inconclusive), `judge_errors` count. Every metric function asserts single-tier input and raises `TierMixError` otherwise.
- [ ] **Step 6: `report.py` + `tracing.py` + `run.py`.** `report.py`: renders `report.md` — PROVISIONAL banner at top (“pending human judge spot-check — fill spotcheck.yaml, then run scripts/check_spotcheck.py”); estimand statement (“review procedure conditional on shared binary output format; workspace labels are instrumentation”); experiment header (config echo incl. the single varied element); per-arm table: n, pass k/n, pass rate + Wilson CI, token breakdown (fresh/cache_creation/cache_read/output/logical total), total cost USD; deltas row (logical tokens and USD separately); confusion matrix + base rate; defect-level recall; paired flip table; per-directive adherence; flags section (prints HARNESS BROKEN banner / cost-adjusted verdict / composite-floored notice when set); judge parse-failure and judge_error counts; “Not aggregated across tiers” footer. Also emit `spotcheck.md` (human-readable: up to 20 sampled judged items — normalized findings block + ground truth + judge verdict) and `spotcheck.yaml` (same rows with an empty `agree:` field per row for the human to fill). `tracing.py`: `trace_call(kind, payload)` → if opik configured (`OPIK_API_KEY` or local server reachable) log via opik SDK; else append to `results_dir/trace.jsonl`; never raise. `run.py`: load config → gen_promptfoo → run baseline arm: `npx promptfoo eval -c <dir>/promptfoo-baseline.yaml --output <dir>/promptfoo-baseline.json --no-cache -j 4` with `PROMPTFOO_PYTHON=<abs .venv python>` → budget check: if baseline arm cost × 2 > `max_cost_usd`, abort with clear error before the treatment arm → run treatment arm likewise → metrics → report; exit nonzero if `harness_broken` or any `judge_error`.

- [ ] **Step 7: Run unit tests** `.venv/bin/pytest harness/tests -v` — all PASS. **Commit** `feat: harness core (config, promptfoo runner, blind judge, metrics, report, tracing)`.

## Task 7: DeepEval CI gate + live smoke run

**Files:**
- Create: `ci/test_smoke.py`, `scripts/check_spotcheck.py`
- Modify: none (fix bugs surfaced by the live run wherever they live)

**Interfaces:**
- Consumes: `python -m harness.run experiments/smoke.yaml` end-to-end.

- [ ] **Step 1: Write `ci/test_smoke.py`.** Pytest module: (a) `test_moves_check`, `test_artifact_lint`, `test_taskset_check` — subprocess the three scripts, assert exit 0; (b) `test_smoke_run` — runs `harness.run experiments/smoke.yaml` (marked `@pytest.mark.live`; skipped unless `RUN_LIVE=1`), then wraps the result in a deepeval `assert_test`: define `class HarnessIntegrityMetric(BaseMetric)` whose `measure` returns binary success iff the smoke results dir contains report.md, metrics.json, spotcheck.yaml and both promptfoo-<arm>.json files; `calls/` has exactly n_items×2 files each with nonzero output_tokens and a valid `arm`; `judge/` has n_items×2 files each with binary `item_pass` and `judge_error: false`; and metrics.json parses with all step-6 metric keys present (`pass_rate`, `delta`, `token_totals`, `confusion`, `base_rate`, `adherence`, `paired_flips`, `flags`, `judge_errors`). Threshold 1.0, binary. Also write `scripts/check_spotcheck.py`: reads a results dir's `spotcheck.yaml`; if no `agree:` fields are filled, print `PROVISIONAL: human spot-check not yet recorded` and exit 0; if filled, compute disagreement rate; >20% → print STOP-and-recalibrate message, exit 1; else print agreement rate, exit 0.
- [ ] **Step 2: Live smoke run.** `RUN_LIVE=1 .venv/bin/pytest ci/test_smoke.py -v -m live` (5 items × 2 arms = 10 haiku calls + 10 judge calls; expect < $2, < 15 min). Debug until green — this is the harness's first end-to-end contact with reality; expected failure points: promptfoo python provider env, arm-label plumbing, findings-block extraction, codex schema output. Fix in place.
- [ ] **Step 3: Full gate.** `RUN_LIVE=1 .venv/bin/pytest ci -v` all green. **Commit** `feat: deepeval CI gate + green 5-task smoke run`.

## Task 8: Experiment #1 — review shape vs plain review prompt

**Files:**
- Create: `results/exp1-review-shape/weak/…` (run outputs), committed.

**Interfaces:**
- Consumes: everything.

- [ ] **Step 1: Preflight.** `experiments/exp1-review-shape.yaml` validates; `varied_element` resolves to the review-shape move id in moves.yaml and `artifacts/elements/<id>/prompt.md` exists; budget `max_cost_usd: 10.0`.
- [ ] **Step 2: Run** `.venv/bin/python -m harness.run experiments/exp1-review-shape.yaml` (20 items × 2 arms = 40 haiku calls + 40 judge calls; ~30–60 min). Monitor `calls/` file count; on crash, fix and re-run (a re-run restarts cleanly — delete the partial results dir first).
- [ ] **Step 3: Verify the report** contains ALL of: per-arm pass rates + CIs, delta, total token cost (input+output) per arm + delta, adherence rate (treatment), TP/FP/TN/FN + base rate 0.7, defect-level recall, paired flips, flags section, per-tier path, judge parse failures. Check no failure signature fired (esp. token delta >20% with a win → the report must carry the cost-adjusted verdict, not a clean win).
- [ ] **Step 4: Commit** `feat: experiment 1 (review shape vs plain) results + report`.

---

## Explicitly out of scope this session

Experiments 2 (negative control), 3 (failure signatures/debugging), 4 (rejected-alternatives/design) — propose in the final summary with estimated task-set construction effort each. MBPP-style dev task sets and reproducible-failing-test debugging sets (needed for experiments 3+; format = same manifest/truth pattern). Live adherence-battery and triggering experiments (metrics support ships in Task 6; scenario/query sets are future work). Opik server/UI setup beyond graceful SDK fallback. Any second executor tier.
