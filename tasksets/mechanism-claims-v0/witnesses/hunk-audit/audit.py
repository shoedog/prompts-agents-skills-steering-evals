#!/usr/bin/env python3
"""Hunk-header arithmetic audit for mechanism-claims-v0 diff.patch files.

For every hunk in every item's diff.patch, verifies:
  1. declared old count == (# context lines) + (# deletion lines) in the hunk body
  2. declared new count == (# context lines) + (# addition lines) in the hunk body
  3. every hunk-body line carries a valid prefix (' ', '+', '-', or '\\' marker);
     flags completely empty lines (missing the context-space prefix)
  4. cross-hunk start consistency within a file:
     new_start - old_start == cumulative (adds - dels) of all PRIOR hunks
     (for new files, old side is -0,0 and new_start must be 1)
  5. no stray bytes between hunks / after the last hunk; no CRLF line endings;
     file ends with a newline

Exit 0 iff all checks pass for all patches given on argv.
"""
import re
import sys

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

def audit(path: str) -> bool:
    ok = True
    raw = open(path, "rb").read()
    if b"\r" in raw:
        print(f"  FAIL {path}: CRLF/CR bytes present")
        ok = False
    if not raw.endswith(b"\n"):
        print(f"  FAIL {path}: no trailing newline at EOF")
        ok = False
    lines = raw.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline artifact

    i = 0
    cur_old = cur_new = None  # current file pair
    cum_delta = 0             # cumulative adds-dels for prior hunks of current file
    prev_hunk_old_end = 0     # old-file line after the previous hunk's range
    nfile = 0
    nhunk = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("--- "):
            cur_old = ln[4:]
            if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
                print(f"  FAIL {path}:{i+1}: '---' not followed by '+++'")
                return False
            cur_new = lines[i + 1][4:]
            cum_delta = 0
            prev_hunk_old_end = 0
            nfile += 1
            i += 2
            continue
        m = HUNK_RE.match(ln)
        if m:
            nhunk += 1
            if cur_old is None:
                print(f"  FAIL {path}:{i+1}: hunk before any file header")
                ok = False
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1
            hdr_line = i + 1  # 1-based
            i += 1
            ctx = dels = adds = 0
            empty_ctx_lines = []
            body_start = i
            while i < len(lines) and (ctx + dels < old_count or ctx + adds < new_count):
                b = lines[i]
                if b.startswith("\\"):
                    i += 1  # "\ No newline at end of file" marker: counts nothing
                    continue
                if b == "":
                    # empty line = context line whose leading space was stripped;
                    # tolerated by git/patch but flag it
                    empty_ctx_lines.append(i + 1)
                    ctx += 1
                elif b[0] == " ":
                    ctx += 1
                elif b[0] == "+":
                    adds += 1
                elif b[0] == "-":
                    dels += 1
                else:
                    break  # invalid prefix -> body ends early; counts will mismatch
                i += 1
            actual_old = ctx + dels
            actual_new = ctx + adds
            declared = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
            status = []
            if actual_old != old_count:
                status.append(f"old-count MISMATCH: declared {old_count}, body has {actual_old} (ctx {ctx} + del {dels})")
                ok = False
            if actual_new != new_count:
                status.append(f"new-count MISMATCH: declared {new_count}, body has {actual_new} (ctx {ctx} + add {adds})")
                ok = False
            # cross-hunk start consistency
            eff_old_start = old_start if old_count > 0 else old_start + 1  # -0,0 convention
            eff_new_start = new_start if new_count > 0 else new_start + 1
            if eff_new_start - eff_old_start != cum_delta:
                status.append(
                    f"start-offset MISMATCH: new_start-old_start = {eff_new_start - eff_old_start}, "
                    f"cumulative prior delta = {cum_delta}")
                ok = False
            if old_count > 0 and old_start <= prev_hunk_old_end:
                status.append(f"hunk overlaps/precedes previous hunk (old_start {old_start} <= prev end {prev_hunk_old_end})")
                ok = False
            if empty_ctx_lines:
                status.append(f"note: empty context line(s) missing leading space at patch line(s) {empty_ctx_lines}")
            cum_delta += adds - dels
            prev_hunk_old_end = old_start + old_count - 1 if old_count > 0 else old_start
            verdict = "OK " if not any("MISMATCH" in s or "overlap" in s for s in status) else "FAIL"
            print(f"  {verdict} {cur_new} {declared}  body: ctx={ctx} del={dels} add={adds} "
                  f"-> old={actual_old} new={actual_new}" + ("" if not status else "  [" + "; ".join(status) + "]"))
            continue
        # any other line between structures is stray
        print(f"  FAIL {path}:{i+1}: stray line outside hunk structure: {ln!r}")
        ok = False
        i += 1
    print(f"  summary: {nfile} file section(s), {nhunk} hunk(s), arithmetic {'CONSISTENT' if ok else 'INCONSISTENT'}")
    return ok

def main() -> int:
    all_ok = True
    for path in sys.argv[1:]:
        print(f"== {path}")
        if not audit(path):
            all_ok = False
        print()
    print("HUNK-AUDIT RESULT:", "PASS (all headers arithmetically consistent)" if all_ok else "FAIL")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
