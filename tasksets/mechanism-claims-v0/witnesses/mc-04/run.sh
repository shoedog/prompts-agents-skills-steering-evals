#!/usr/bin/env bash
# mc-04 witness runner (mechanism-claims-v0 v0->v1 verification, 2026-07-25).
# Re-runnable: applies items/mc-04/diff.patch (new file src/pathfold.ts),
# type-checks it with tsc --strict, compiles pathfold + a trigger harness to
# JS, and runs the truth.yaml minimal_trigger under node.
#
# SHIMS: trigger.ts harness only. src/pathfold.ts comes ONLY from diff.patch.
#
# HYPOTHESIS under test (truth.yaml mc-04-d1): the doc comment promises '.'
# and '..' are "preserved verbatim in the output" (purely lexical,
# non-resolving), but the loop skips '.' and pops on '..' -- so
# foldSegments("a/./b/../c") returns ["a","c"], not ["a",".","b","..","c"].
# FALSIFIER: the returned array preserves the dot segments.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITEM_DIR="${ITEM_DIR:-$SCRIPT_DIR/../../items/mc-04}"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
echo "=== mc-04 witness run: $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="
echo "item dir : $ITEM_DIR"
echo "build dir: $BUILD_DIR"
echo "toolchain: node $(node --version); tsc $(tsc --version); $(git --version); patch: $(patch --version 2>&1 | head -1)"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR" || exit 70
git init -q .

echo
echo "--- step 1: materialize shim harness ---"
cat > trigger.ts <<'SHIM_EOF'
// minimal_trigger harness for mc-04 (truth.yaml mc-04-d1).
import { foldSegments, foldsUnder } from "./src/pathfold";

const input = "a/./b/../c";
const actual = foldSegments(input);
const docPromise = ["a", ".", "b", "..", "c"]; // doc: "preserved verbatim in the output"
console.log(`foldSegments(${JSON.stringify(input)})            =`, JSON.stringify(actual));
console.log("doc-comment promise ('preserved verbatim') =", JSON.stringify(docPromise));
const contradiction = JSON.stringify(actual) !== JSON.stringify(docPromise);
console.log("doc contradicted (dot segments RESOLVED, not preserved):", contradiction);

const esc = foldSegments("../../shared/x");
const inside = foldSegments("shared/x");
console.log('foldSegments("../../shared/x") =', JSON.stringify(esc));
console.log('foldSegments("shared/x")       =', JSON.stringify(inside));
console.log(
  "leading '..' vanish entirely (pop on empty array is a no-op):",
  JSON.stringify(esc) === JSON.stringify(inside)
);
console.log(
  'foldsUnder("shared", "../../shared/x") =',
  foldsUnder("shared", "../../shared/x"),
  " <- a path that escapes the root is scoped as if inside it"
);

if (!contradiction) {
  // throwing (rather than process.exit) keeps the harness free of node-only
  // globals so it type-checks without @types/node
  throw new Error("LABEL REFUTED: the code preserves dot segments as the doc claims");
}
console.log(
  "\nVERDICT: foldSegments() skips '.' and pops on '..' (src/pathfold.ts loop) --"
);
console.log(
  "the 'purely lexical and non-resolving / preserved verbatim' doc claim is FALSE."
);
SHIM_EOF
echo "base files:"
find . -type f -not -path './.git/*' | sort

echo
echo "--- step 2: git apply --check ---"
git apply --check "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2b: patch -p1 --dry-run (cross-check) ---"
patch -p1 --dry-run -i "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "--- step 2c: apply for real (git apply) ---"
git apply "$ITEM_DIR/diff.patch" 2>&1
echo "exit=$?"
echo "post-apply tree:"
find . -type f -not -path './.git/*' | sort

echo
echo "--- step 3: tsc --strict --noEmit type/parse check of the diff's file alone ---"
tsc --strict --noEmit --target es2022 src/pathfold.ts 2>&1
echo "exit=$?"

echo
echo "--- step 3b: compile pathfold + trigger to JS ---"
tsc --strict --target es2022 --module commonjs --outDir build src/pathfold.ts trigger.ts 2>&1
echo "exit=$?"
echo "compiled files:"
find build -type f | sort

echo
echo "--- step 4: minimal_trigger run ---"
node build/trigger.js 2>&1
echo "exit=$?"
