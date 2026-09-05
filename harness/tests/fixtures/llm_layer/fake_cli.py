#!/usr/bin/env python3
"""Exact-envelope subprocess double for the llm-layer adapter tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path


BEHAVIOR = Path("llm-layer-behavior.json")
ARGV = Path("llm-layer-argv.json")
CALL_COUNT = Path("llm-layer-call-count.txt")


def main() -> int:
    behavior = json.loads(BEHAVIOR.read_text())
    ARGV.write_text(json.dumps(sys.argv[1:], separators=(",", ":")) + "\n")
    count = int(CALL_COUNT.read_text()) if CALL_COUNT.exists() else 0
    CALL_COUNT.write_text(f"{count + 1}\n")

    stderr = behavior.get("stderr", "")
    if stderr:
        sys.stderr.write(stderr)

    returncode = behavior.get("returncode", 0)
    if returncode:
        return returncode

    if "stdout_raw" in behavior:
        sys.stdout.write(behavior["stdout_raw"])
    else:
        sys.stdout.write(json.dumps(behavior["envelope"], separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
