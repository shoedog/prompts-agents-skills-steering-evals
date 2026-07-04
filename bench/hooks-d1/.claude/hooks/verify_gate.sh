#!/bin/bash
# EXP-2 verify-before-done Stop gate. Blocks session end until VERIFICATION.md
# exists at the repo root with the required shape. Max 2 blocks (loop guard).
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
COUNT_FILE="$ROOT/.claude/.verify_gate_blocks"
V="$ROOT/VERIFICATION.md"

# No-op path: if the working tree is untouched there is nothing to verify
# (injected treatment files are git-excluded and invisible here).
if [ -z "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]; then
  exit 0
fi

ok=1
if [ ! -s "$V" ]; then ok=0
elif ! grep -qiE '[0-9]+ (tests? )?passed' "$V"; then ok=0
elif ! grep -qi '## Verified' "$V"; then ok=0
elif ! grep -qi '## Not verified' "$V"; then ok=0
fi

if [ "$ok" -eq 1 ]; then exit 0; fi

blocks=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
if [ "$blocks" -ge 2 ]; then
  exit 0  # loop guard: two enforcement rounds max
fi
echo $((blocks+1)) > "$COUNT_FILE"

cat << 'JSON'
{"decision": "block", "reason": "Before finishing you must complete the verification gate: (1) run the FULL test suite (not just the tests the task names) and note the totals you saw; (2) ensure every behavior you added or fixed has a test that would FAIL on the pre-change code, including at least one negative or edge case per new code path — add any that are missing; (3) write VERIFICATION.md at the repository root containing: the exact commands you ran with their pass totals (e.g. '2237 passed'), a '## Verified' section listing what you confirmed, and a '## Not verified' section listing what you did not confirm; (4) if the full suite shows a failure outside your task's scope, record it in VERIFICATION.md and report it — do NOT re-baseline or silently fix it. Then finish."}
JSON
exit 0
