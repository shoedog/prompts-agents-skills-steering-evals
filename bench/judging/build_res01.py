"""Build the RES-01 single-arm rubric brief.

RES-01 cannot be judged as a blind A/B pair: the '7 confirmed drift findings'
checklist was derived FROM the reference deliverable, so the reference scores
perfectly by construction. Instead the judge grades the candidate doc against
the ground-truth doc directly: finding recall + false-drift precision +
deliverable-format compliance.
"""
import json
import pathlib

J = pathlib.Path(__file__).parent
cand = pathlib.Path("bench/out/RES-01/fable-untracked/doc-cleanup-task/README.md").read_text()
gt = pathlib.Path("bench/fixtures/RES-01/ground-truth/README.md").read_text()

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "gt_findings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"finding": {"type": "string", "maxLength": 200},
                           "covered_by_candidate": {"type": "boolean"}},
            "required": ["finding", "covered_by_candidate"]}},
        "candidate_extra_findings_correct": {"type": "array", "items": {"type": "string", "maxLength": 200}},
        "candidate_false_or_unsupported": {"type": "array", "items": {"type": "string", "maxLength": 200}},
        "format_ok": {"type": "boolean"},
        "candidate_materially_better": {"type": "boolean"},
        "ground_truth_materially_better": {"type": "boolean"},
        "rationale": {"type": "string", "maxLength": 800},
    },
    "required": ["gt_findings", "candidate_extra_findings_correct",
                 "candidate_false_or_unsupported", "format_ok",
                 "candidate_materially_better", "ground_truth_materially_better",
                 "rationale"],
}

task_prompt = pathlib.Path("bench/tasks/RES-01.yaml").read_text().split("task_prompt: |")[1].split("success_evidence:")[0]

brief = f"""# Docs-drift audit grading — task RES-01

Two engineers independently performed the SAME documentation audit of a Rust
repo and wrote a cleanup/handoff doc. The GROUND-TRUTH doc below was verified
correct (its drift findings were code-confirmed). Grade the CANDIDATE doc
against it. You do not know who wrote either.

Method:
1. Enumerate each distinct code-vs-docs DRIFT FINDING asserted in the
   ground-truth doc (a concrete factual mismatch, not a style suggestion).
2. For each, judge whether the candidate doc independently identifies the
   same drift (different wording fine; the same underlying mismatch).
3. List candidate findings NOT in the ground truth that look correct
   (plausible, internally consistent, concrete).
4. List candidate claims that look FALSE or unsupported.
5. format_ok: is the candidate a usable delegation handoff doc (actionable
   tasks, verifiable claims)?
6. materially_better flags: not both true; both false = parity.

## The audit task both received

{task_prompt}

## GROUND-TRUTH doc

{gt}

## CANDIDATE doc

{cand}
"""
d = J / "RES-01"
d.mkdir(exist_ok=True)
(d / "brief.md").write_text(brief)
(d / "schema.json").write_text(json.dumps(SCHEMA, indent=1))
(d / "key.json").write_text(json.dumps({"mode": "single-arm-rubric", "candidate": "fable"}))
print(f"RES-01 rubric brief: {len(brief)}B")
