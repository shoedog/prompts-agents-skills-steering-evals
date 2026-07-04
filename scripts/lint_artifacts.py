#!/usr/bin/env python3
"""Fail any element artifact >150 tokens (o200k_base) or trigger >3 non-empty lines."""
import sys, pathlib, tiktoken, yaml

ENC = tiktoken.get_encoding("o200k_base")
CAP = 150
errors = []
root = pathlib.Path("artifacts")

# Completeness: every non-excluded element move needs all 3 forms; every runtime move needs trigger.md
moves = yaml.safe_load(open("moves.yaml"))["moves"]
for m in moves:
    if m["classification"] == "element" and m["verdict"] != "exclude":
        for form in ("prompt.md", "skill.md", "steering.md", "agent.md"):
            if not (root / "elements" / m["id"] / form).is_file():
                errors.append(f"missing artifacts/elements/{m['id']}/{form}")
    if m["classification"] == "runtime":
        if not (root / "runtime" / m["id"] / "trigger.md").is_file():
            errors.append(f"missing artifacts/runtime/{m['id']}/trigger.md")
for form in ("prompt.md", "agent.md"):
    if not (root / "composites/review-shape" / form).is_file():
        errors.append(f"missing artifacts/composites/review-shape/{form}")

for p in sorted(root.glob("elements/*/*.md")) + sorted(root.glob("composites/*/*.md")) + sorted(root.glob("baseline/*.md")):
    n = len(ENC.encode(p.read_text()))
    if n > CAP:
        errors.append(f"{p}: {n} tokens > {CAP}")
for p in sorted(root.glob("runtime/*/trigger.md")):
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    if len(lines) > 3:
        errors.append(f"{p}: {len(lines)} non-empty lines > 3")
if errors:
    print("\n".join(errors)); sys.exit(f"FAIL: {len(errors)} violation(s)")
print("OK: all artifacts present and within budget")
