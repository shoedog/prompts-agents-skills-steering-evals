"""Build conclusion-match briefs for the design-taskset executor arms.

For each DES item x arm: grade the arm's memo against the vindicated outcome
(conclusion + vindication text lifted verbatim from
mining/out/nominations-design.md). Generic schema; the item-specific ground
truth carries the specifics. Dirs: DESA-<item>-<arm>/.
"""
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
J = REPO / "bench" / "judging"
NOM = (REPO / "mining/out/nominations-design.md").read_text()

ITEMS = ["DES-02", "DES-03", "DES-04", "DES-05"]
ARMS = {
    "sonnet": "bench/out-des-sonnet",
    "opus": "bench/out-des-opus",
    "gpt55high": "bench/out-des-gpt55high",
    "gpt55xhigh": "bench/out-des-gpt55xhigh",
}

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "recommendation_matches_vindicated": {"type": "boolean"},
        "load_bearing_caveats_matched": {"type": "boolean"},
        "scope_calibrated": {"type": "boolean"},
        "would_have_prevented_wasted_work": {"type": "boolean"},
        "probe_answer": {"type": "string", "maxLength": 1200},
        "rationale": {"type": "string", "maxLength": 800},
    },
    "required": ["recommendation_matches_vindicated", "load_bearing_caveats_matched",
                 "scope_calibrated", "would_have_prevented_wasted_work",
                 "probe_answer", "rationale"],
}


def nomination_block(item: str) -> str:
    m = re.search(rf"^## {item} .*?(?=^## |\Z)", NOM, re.M | re.S)
    block = m.group(0)
    keep = []
    for para_key in ("- conclusion", "- vindication evidence", "- proposed oracle"):
        pm = re.search(rf"^{re.escape(para_key)}.*?(?=^- |\Z)", block, re.M | re.S)
        if pm:
            keep.append(pm.group(0).rstrip())
    return "\n".join(keep)


import yaml  # noqa: E402

built = 0
for item in ITEMS:
    gt = nomination_block(item)
    spec = yaml.safe_load(open(REPO / f"bench/tasks/{item}.yaml"))
    for arm, out_root in ARMS.items():
        sp = REPO / out_root / item / "summary.json"
        if not sp.exists():
            print(f"SKIP {item}/{arm}: no summary yet")
            continue
        cand = json.loads(sp.read_text()).get("result_text") or ""
        if not cand.strip():
            print(f"SKIP {item}/{arm}: empty deliverable")
            continue
        d = J / f"DESA-{item}-{arm}"
        d.mkdir(exist_ok=True)
        brief = f"""# Conclusion-match grading — {item} (design/architecture), one anonymous arm

An engineer wrote the design memo below in response to the task brief. The
question was later SETTLED by the project's subsequent history. Grade the
memo against the settled outcome. You do not know who wrote it. Judge by
SHAPE and substance, not labels.

## Settled outcome (ground truth: the vindicated conclusion + repo evidence)

{gt}

## Grading fields

- recommendation_matches_vindicated: does the memo's recommended design/option
  match the SHAPE of what was vindicated and landed?
- load_bearing_caveats_matched: does the memo carry the settled outcome's
  load-bearing caveats/constraints (the parts the vindication text calls out
  as decisive — e.g. narrowings, guards, buy-sizing, language scoping)?
- scope_calibrated: is the memo's scope and quantitative sizing consistent
  with what reality delivered (neither materially over- nor under-scoped)?
- would_have_prevented_wasted_work: following the memo as written, would the
  team have avoided the missteps the vindication record shows (if any)?
- probe_answer: 2-4 sentences on what the memo got right and wrong vs the
  settled outcome.

## The task brief the engineer received

{spec['task_prompt']}

## The memo to grade

{cand}
"""
        (d / "brief.md").write_text(brief)
        (d / "schema.json").write_text(json.dumps(SCHEMA, indent=1))
        (d / "key.json").write_text(json.dumps({"mode": "conclusion-match", "candidate": arm, "item": item}))
        built += 1
print(f"built {built} briefs")
