#!/usr/bin/env bash
# Install the validated global steering onto this machine's ~/.claude/CLAUDE.md.
# Usage: ./install.sh          install (backs up an existing, differing target)
#        ./install.sh --check  diff installed copy vs repo copy (nonzero on drift)
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)/global-CLAUDE.md"
dst="$HOME/.claude/CLAUDE.md"

if [ "${1:-}" = "--check" ]; then
  [ -f "$dst" ] || { echo "not installed: $dst missing"; exit 1; }
  diff -u "$dst" "$src" && echo "in sync"
  exit 0
fi

mkdir -p "$HOME/.claude"
if [ -f "$dst" ] && ! cmp -s "$src" "$dst"; then
  cp "$dst" "$dst.pre-bootstrap.$(date +%Y%m%d%H%M%S)"
  echo "backed up existing $dst"
fi
cp "$src" "$dst"
echo "installed $dst"
