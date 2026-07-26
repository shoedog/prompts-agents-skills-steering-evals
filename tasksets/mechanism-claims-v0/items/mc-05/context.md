# ci/run-suite.sh: the workspace CI gate script

Single entry point the CI system runs for every push; the CI step passes or
fails on this script's exit status alone. Nothing downstream re-checks the
suite — a green step is treated as "the workspace suite passed" by the
merge gate and by reviewers reading the checks list.

Contract:
- The script must fail exactly when a check it runs fails.
- Comments in the script are operator documentation: on-call engineers
  debug red/green CI from what the header comment promises.
- The diff adds the script (new file).
