#!/usr/bin/env bash
# Weekly model-in-the-loop triage: opus + sol evaluate independently IN
# PARALLEL, sonnet folds into one readable report. Cron: Sunday 07:30, after
# the 07:10 delta. No `set -e`: a lane may fail; the fold discloses missing
# lanes (honest degraded path) instead of the whole run dying silently.
set -u
REPO=/Users/wesleyjinks/code/prompts-skills-steering
OUT=$REPO/mining/out
WEEK=$(date +%F)
DIR=$OUT/triage-weekly/$WEEK
mkdir -p "$DIR"
exec >>"$DIR/run.log" 2>&1
echo "=== weekly_triage $WEEK start $(date) ==="

# 1. Week input: inbox delta sections from the last 7 days.
python3 - "$OUT/triage-inbox.md" "$DIR/week-input.md" <<'PY'
import re, sys, datetime
src, dst = sys.argv[1], sys.argv[2]
cutoff = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
out, keep = [], False
for line in open(src):
    m = re.match(r"^# (\d{4}-\d{2}-\d{2}) — triage delta", line)
    if m:
        keep = m.group(1) >= cutoff
    if keep:
        out.append(line)
open(dst, "w").writelines(out)
print(f"week-input: {len(out)} lines since {cutoff}")
PY
if [ ! -s "$DIR/week-input.md" ]; then
  echo "no evidence in the last 7 days; stopping"
  exit 0
fi

EVAL_PROMPT=$(cat "$REPO/mining/prompts/triage-eval.md")

# 2. Evaluator lanes — independent, so they run in PARALLEL.
# 2a. Opus lane — Claude headless, read-only tools, settings severed so no
# plugin/memory injection colors the evaluation. Prompt via stdin (a
# positional prompt combined with empty --setting-sources mis-parses).
(cd "$DIR" && printf '%s\n\nRepo root: %s. Week input: %s/week-input.md. Output your full evaluation as your final message.\n' \
  "$EVAL_PROMPT" "$REPO" "$DIR" \
  | claude -p --model claude-opus-5 --setting-sources "" \
      --allowedTools "Read,Grep,Glob" > opus-eval.md) &
OPUS_PID=$!

# 2b. Sol lane — codex, workspace-write scoped to $DIR; sol writes its own
# file (the -o final-message clobber gotcha; see codex-cli-invocation memory).
{
  echo "$EVAL_PROMPT"
  echo
  echo "Repo root: $REPO. Week input: ./week-input.md."
  echo "Write your COMPLETE evaluation to ./sol-eval.md (create it). Touch no other file."
} > "$DIR/sol-request.md"
(cd "$DIR" && codex exec --sandbox workspace-write \
  -c model_reasoning_effort='"high"' - < sol-request.md) &
SOL_PID=$!

wait "$OPUS_PID"
wait "$SOL_PID"
[ -s "$DIR/opus-eval.md" ] && echo "opus lane ok ($(wc -l < "$DIR/opus-eval.md") lines)" || echo "opus lane EMPTY"
[ -s "$DIR/sol-eval.md" ] && echo "sol lane ok ($(wc -l < "$DIR/sol-eval.md") lines)" || echo "sol lane EMPTY/degraded"

# 3. Sonnet fold — readable report for the owner.
(cd "$DIR" && { cat "$REPO/mining/prompts/triage-fold.md"; \
  printf '\nWorking directory: %s. Write the final report to %s/triage-report.md.\n' "$DIR" "$DIR"; } \
  | claude -p --model claude-sonnet-5 --setting-sources "" \
      --allowedTools "Read,Grep,Glob,Write")
if [ -s "$DIR/triage-report.md" ]; then
  mkdir -p "$HOME/Documents/triage-reports"
  cp "$DIR/triage-report.md" "$HOME/Documents/triage-reports/$WEEK.md"
  echo "report -> ~/Documents/triage-reports/$WEEK.md"
else
  echo "FOLD FAILED — raw lane outputs remain in $DIR"
fi
echo "=== weekly_triage $WEEK end $(date) ==="
