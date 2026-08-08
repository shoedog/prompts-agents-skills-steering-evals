#!/usr/bin/env bash
# Install the validated global steering + handoff template onto this machine's
# Claude carrier (~/.claude/).
# Usage: ./install.sh          install (backs up an existing, differing target)
#        ./install.sh --check  diff installed copies vs repo copies (nonzero on drift)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

# repo-canonical source -> installed destination
pairs=(
  "$here/global-CLAUDE.md:$HOME/.claude/CLAUDE.md"
  "$here/handoff-template.md:$HOME/.claude/handoff-template.md"
)

if [ "${1:-}" = "--check" ]; then
  rc=0
  for pair in "${pairs[@]}"; do
    src="${pair%%:*}"; dst="${pair##*:}"
    if [ ! -f "$dst" ]; then echo "not installed: $dst missing"; rc=1; continue; fi
    diff -u "$dst" "$src" && echo "in sync: $dst" || rc=1
  done
  exit "$rc"
fi

mkdir -p "$HOME/.claude"
for pair in "${pairs[@]}"; do
  src="${pair%%:*}"; dst="${pair##*:}"
  if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp "$dst" "$dst.pre-bootstrap.$(date +%Y%m%d%H%M%S)"
    echo "backed up existing $dst"
  fi
  cp "$src" "$dst"
  echo "installed $dst"
done