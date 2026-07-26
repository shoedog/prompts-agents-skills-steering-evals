---
task-type: implement
---
# Bridge wedge-watchdog: three-signal liveness detection with verify-before-kill

## Description

Implement the liveness-tradecraft cluster (success-mode catalog v2, Family 7) as a bridge
feature. A long-running worker (implement/run-workflow node) is flagged WEDGED only on the
CONJUNCTION of three signals, none sufficient alone: (1) target-tree file activity stale
≥ N minutes (mtime sweep of the session cwd); (2) worker process at ~0% CPU over a
sampling window; (3) the task's own progress ladder stalled (edits → staged →
.git/A2A_COMMIT_MSG for implement; node-start/node-ok events for workflows). Stale mtime
+ live CPU = thinking. Fresh mtime + 0% CPU = gap between actions. (Evidence:
e92c4a3d:1256, three real incidents in one night.)

On flag: DO NOT kill. Emit a watchdog event + hand-off note; any kill decision first runs
a completeness check against the task's acceptance criteria (the process may have wedged
AFTER finishing) and is scoped to that run's PID group only. Declared patience window per
lane (default from config; reviewer lanes have a documented normal long-review range —
cite the [review] timeout). Also decompose clocks per the A3 finding: watchdog timestamps
separate approval-wait, executor start, first output, yield, and completion so latency is
attributable before anyone blames a component.

## Acceptance Criteria

Conjunctive detector with all three signals + unit tests proving each single signal alone
does NOT flag; integration test with a synthetic wedged worker (all three) that DOES flag;
completeness-check gate exercised (wedged-after-done case emits done-not-dead); kill
scoping test (other processes untouched); clock decomposition present in the watchdog
event payload; config surface for window/thresholds with sane defaults; hermetic verify
green (fmt/clippy/build/test).

## Non-goals

Auto-kill (flag + gate only, operator decides); changes to the convergence contract;
retrofitting old run logs.

## Commit Message

bridge: wedge-watchdog — conjunctive three-signal liveness detection with verify-before-kill gate and clock decomposition (success-mode catalog v2 Family 7)
