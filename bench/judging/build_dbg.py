"""Build exp-3 debug judging briefs.

DBG-01: conclusion-match per arm (diagnosis quality vs the known root cause;
several arms produced no diff). Others: blind pairs — within-model D2
contrast + each arm vs the Fable reference diff.
Dirs: DBG1CM-<arm>/, DBGW-<task>-<model>/, DBGF-<task>-<arm>/.
"""
import json
import pathlib
import random
import subprocess

import yaml

random.seed(20260708)
REPO = pathlib.Path(__file__).resolve().parents[2]
J = REPO / "bench" / "judging"

ARMS = {
    "sonnet-base": ("bench/out-dbg-sonnet-base", "/private/tmp/dbg-base-ws"),
    "sonnet-d2": ("bench/out-dbg-sonnet-d2hook", "/private/tmp/dbg-d2h-ws"),
    "opus-base": ("bench/out-dbg-opus-base", "/private/tmp/dbg-opus-ws"),
    "opus-d2": ("bench/out-dbg-opus-d2hook", "/private/tmp/dbg-opusd2-ws"),
    "gpt55-base": ("bench/out-dbg-gpt55-base", "/private/tmp/dbg-g5-ws"),
    "gpt55-d2": ("bench/out-dbg-gpt55-d2", "/private/tmp/dbg-g5d2-ws"),
}
TASKS = ["DBG-02", "DBG-03", "INFRA-01"]

PAIR_SCHEMA = json.loads((J / "IMPL-01" / "schema.json").read_text())
PROBE = {
    "DBG-02": "Root-cause quality: does each arm make materialized-receiver suppression work even when the type is poisoned (state 'local binding found' distinct from 'type resolved'), with scope-aware recovery? Do its regression tests reproduce both false-Exact cases and would they fail pre-fix?",
    "DBG-03": "Does each arm remove the per-param ordinal collision at the root (single ordered binding pass) and add a regression test that fails on the buggy code? Is the fix inert beyond the repair?",
    "INFRA-01": "Is the diagnosis the gawk 'load' builtin collision, is the fix minimal and confined to the DB-host script, and is test/hooks.js untouched?",
}

CM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "root_cause_match": {"type": "boolean"},
        "fmt_issue_identified": {"type": "boolean"},
        "fix_attempted": {"type": "boolean"},
        "fix_shape_match": {"type": "boolean"},
        "probe_answer": {"type": "string", "maxLength": 1000},
        "rationale": {"type": "string", "maxLength": 600},
    },
    "required": ["root_cause_match", "fmt_issue_identified", "fix_attempted",
                 "fix_shape_match", "probe_answer", "rationale"],
}

DBG1_GT = """Ground truth (verified against the repository's actual history):
- Root cause of the test failure: commit 04c6b0b ("expand workspace member
  globs to concrete dirs") records only directories with a parsed [package],
  which DROPS declared non-glob members whose manifests are malformed —
  breaking malformed_member_manifest_does_not_discard_valid_sibling_manifest.
- Independent second failure: a rustfmt violation on a long assert! in the
  same commit (the CI format check).
- The landed fix (16faa4e, "keep non-glob workspace members") UNIONS the
  parsed-package dirs with the declared non-glob members, preserving the
  original glob-expansion fix.
Grading: root_cause_match = names the non-glob-member drop mechanism;
fmt_issue_identified = separately identifies the rustfmt violation;
fix_attempted = the arm changed code (vs diagnosis-only report);
fix_shape_match = if a fix exists, it unions/preserves both behaviors (false
when no fix was attempted)."""


def write_brief(dirname, brief, schema, key):
    d = J / dirname
    d.mkdir(exist_ok=True)
    (d / "brief.md").write_text(brief)
    (d / "schema.json").write_text(json.dumps(schema, indent=1))
    (d / "key.json").write_text(json.dumps(key))


def arm_diff(arm, task):
    out_root, ws_root = ARMS[arm]
    p = REPO / out_root / task / "arm.diff"
    if not p.exists():
        spec = yaml.safe_load(open(REPO / f"bench/tasks/{task}.yaml"))
        pre = spec.get("pre_sha") or spec["pre_tag"]
        d = subprocess.run(["git", "-C", f"{ws_root}/{task}", "diff", pre],
                           capture_output=True, text=True).stdout
        p.write_text(d)
    return p.read_text()


n = 0
# --- DBG-01 conclusion-match: 6 arms + the fable reference ---
spec01 = yaml.safe_load(open(REPO / "bench/tasks/DBG-01.yaml"))
sources = {arm: json.loads((REPO / root / "DBG-01" / "summary.json").read_text()).get("result_text") or ""
           for arm, (root, _) in ARMS.items()}
sources["fable-ref"] = json.loads((REPO / "bench/out/DBG-01/summary.json").read_text()).get("result_text") or ""
for arm, report in sources.items():
    diff = "" if arm == "fable-ref" else arm_diff(arm, "DBG-01")
    artifact = report + ("\n\n## The arm's diff\n\n```diff\n" + diff + "\n```" if diff.strip() else "\n\n(The arm made no code changes.)")
    brief = f"""# Debug diagnosis grading — DBG-01, one anonymous arm

An engineer was given the terse task below in a repo whose CI failed. Grade
their final report (and diff, if any) against the settled ground truth. You
do not know who the engineer is.

{DBG1_GT}

## The task (verbatim)

{spec01['task_prompt']}

## The engineer's final report

{artifact}
"""
    write_brief(f"DBG1CM-{arm}", brief, CM_SCHEMA, {"mode": "conclusion-match", "candidate": arm, "item": "DBG-01"})
    n += 1

# --- pairwise for DBG-02/03/INFRA-01 ---
def build_pair(dirname, task, a_name, a_text, b_name, b_text):
    global n
    spec = yaml.safe_load(open(REPO / f"bench/tasks/{task}.yaml"))
    flip = random.random() < 0.5
    (an, at), (bn, bt) = ((a_name, a_text), (b_name, b_text)) if flip else ((b_name, b_text), (a_name, a_text))
    brief = f"""# Blind pairwise code-review judgment — {dirname}

Two different engineers (Arm A, Arm B) independently completed the SAME
debugging task from the same starting commit. Judge only the work; process
environments may differ. Ignore any VERIFICATION.md in a diff.
a_materially_better/b_materially_better may not both be true; both false =
parity.

## Task brief (verbatim)

{spec['task_prompt']}

## Probe question (answer in `probe_answer`, per arm)

{PROBE[task]}

## Arm A diff

```diff
{at}
```

## Arm B diff

```diff
{bt}
```
"""
    write_brief(dirname, brief, PAIR_SCHEMA, {"A": an, "B": bn})
    n += 1


for task in TASKS:
    fable = (REPO / f"bench/out/{task}/fable.diff").read_text()
    diffs = {arm: arm_diff(arm, task) for arm in ARMS}
    for model in ["sonnet", "opus", "gpt55"]:
        build_pair(f"DBGW-{task}-{model}", task,
                   f"{model}-base", diffs[f"{model}-base"],
                   f"{model}-d2", diffs[f"{model}-d2"])
    for arm in ARMS:
        build_pair(f"DBGF-{task}-{arm}", task, arm, diffs[arm], "fable", fable)

print(f"built {n} briefs")
