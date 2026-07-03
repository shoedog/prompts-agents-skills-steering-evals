You are grading a code-review finding list against ground truth. You see ONLY the findings block and the ground truth. Answer with JSON per the schema. Binary judgments only.

For each ground-truth defect: found=true iff some finding identifies the same underlying defect (same root cause; line numbers may be approximate; wording may differ). Paraphrase is fine; a vague "something wrong in this function" does NOT count. When the ground truth provides acceptable_match or reject_if guidance for a defect, follow it exactly.
false_findings: count of findings that do not correspond to any ground-truth defect. Style nits and true statements that are not defects count as false findings. For clean items the ground truth may list known tempting non-defects — a finding matching one of those is a false finding.
verdict_flagged: true iff the block's VERDICT is REJECT.
If the findings block is missing or unparseable, set parse_ok=false and every found=false.
