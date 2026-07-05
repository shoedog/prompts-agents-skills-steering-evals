#!/bin/bash
# verify-before-done Stop gate (daily-driver; validated in exp-2, 2026-07-04:
# tests-stronger 12/12 vs unaided Fable on implement tasks).
# Blocks session end until VERIFICATION.md exists at the repo root with the
# required shape — but only when there is real code work to verify.

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" 2>/dev/null || exit 0

# Only gate real git repos with a dirty tree.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
# Tracked changes only: untracked-file clutter (scratch dirs, research
# artifacts) must not trigger the gate in interactive sessions.
CHANGES=$(git status --porcelain 2>/dev/null | grep -v '^??') || true
[ -z "$CHANGES" ] && exit 0

# Docs-only changes need no test verification.
if ! echo "$CHANGES" | awk '{print $NF}' | grep -qvE '\.(md|markdown|txt|rst)$|^docs/|^VERIFICATION\.md$'; then
  exit 0
fi

# Per-session loop guard (max 2 blocks), keyed by session_id from hook input.
INPUT=$(cat)
SID=$(printf '%s' "$INPUT" | python3 -c "import sys,json;print(json.load(sys.stdin).get('session_id','nosid'))" 2>/dev/null || echo nosid)
COUNT_FILE="/tmp/verify-gate-${SID}.count"

V="$ROOT/VERIFICATION.md"
ok=1
if [ ! -s "$V" ]; then ok=0
elif ! grep -qiE '([0-9]+ (tests? )?passed|no test suite)' "$V"; then ok=0
elif ! grep -qi '## Verified' "$V"; then ok=0
elif ! grep -qi '## Not verified' "$V"; then ok=0
fi

if [ "$ok" -eq 1 ]; then
  # keep the gate file out of git status forever (idempotent)
  EX="$(git rev-parse --git-dir)/info/exclude"
  grep -qx '/VERIFICATION.md' "$EX" 2>/dev/null || echo '/VERIFICATION.md' >> "$EX"
  exit 0
fi

blocks=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
[ "$blocks" -ge 2 ] && exit 0
echo $((blocks+1)) > "$COUNT_FILE"

cat << 'JSON'
{"decision": "block", "reason": "Verification gate: before finishing, (1) run the project's full test suite (not just tests you touched) and note the totals; (2) make sure every behavior you added or fixed has a test that would FAIL on the pre-change code, with at least one negative/edge case per new code path — add any missing; (3) write VERIFICATION.md at the repo root with: the exact commands run and their pass totals (or 'no test suite' if none exists), a '## Verified' section, and a '## Not verified' section; (4) if the suite shows a failure outside your task's scope, record it there and report it — do not re-baseline or silently fix it. Then finish."}
JSON
exit 0
