#!/bin/bash
# verify-before-done Stop gate — codex port (claude original validated in
# exp-2: tests-stronger 12/12 vs unaided Fable). Codex Stop semantics:
# exit 0 + no output = allow; JSON {"decision":"block","reason":...} =
# continuation prompt. stop_hook_active guards against repeat blocks.

ROOT="$(pwd)"
INPUT=$(cat)
ACTIVE=$(printf '%s' "$INPUT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('stop_hook_active',False))" 2>/dev/null || echo False)
[ "$ACTIVE" = "True" ] && exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
CHANGES=$(git status --porcelain 2>/dev/null | grep -v '^??') || true
[ -z "$CHANGES" ] && exit 0
if ! echo "$CHANGES" | awk '{print $NF}' | grep -qvE '\.(md|markdown|txt|rst)$|^docs/|^VERIFICATION\.md$'; then
  exit 0
fi

V="$ROOT/VERIFICATION.md"
ok=1
if [ ! -s "$V" ]; then ok=0
elif ! grep -qiE '([0-9]+ (tests? )?passed|no test suite)' "$V"; then ok=0
elif ! grep -qi '## Verified' "$V"; then ok=0
elif ! grep -qi '## Not verified' "$V"; then ok=0
fi

if [ "$ok" -eq 1 ]; then
  EX="$(git rev-parse --git-dir)/info/exclude"
  grep -qx '/VERIFICATION.md' "$EX" 2>/dev/null || echo '/VERIFICATION.md' >> "$EX"
  exit 0
fi

cat << 'JSON'
{"decision": "block", "reason": "Verification gate: before finishing, (1) run the project's full test suite (not just tests you touched) and note the totals; (2) make sure every behavior you added or fixed has a test that would FAIL on the pre-change code, with at least one negative/edge case per new code path - add any missing; (3) write VERIFICATION.md at the repo root with: the exact commands run and their pass totals (or 'no test suite' if none exists), a '## Verified' section, and a '## Not verified' section; (4) if the suite shows a failure outside your task's scope, record it there and report it - do not re-baseline or silently fix it. Then finish."}
JSON
exit 0
