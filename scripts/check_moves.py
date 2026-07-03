#!/usr/bin/env python3
"""Validate moves.yaml: parses, round-trips, every move fully populated."""
import sys, yaml

REQUIRED = ["id", "name", "classification", "verdict", "eval_shape", "evidence_tier", "notes"]
ENUMS = {
    "classification": {"element", "runtime"},
    "verdict": {"build", "exclude", "test_cheap", "must_test"},
    "eval_shape": {"ablation", "adherence", "triggering", "negative_control"},
    "evidence_tier": {"swe", "general", "human"},
}

def main(path="moves.yaml"):
    raw = open(path).read()
    data = yaml.safe_load(raw)
    errors = []
    moves = data.get("moves") if isinstance(data, dict) else None
    if not isinstance(moves, list) or not moves:
        sys.exit("FAIL: top-level 'moves' list missing or empty")
    ids = set()
    for i, m in enumerate(moves):
        for k in REQUIRED:
            v = m.get(k)
            if v in (None, ""):
                errors.append(f"moves[{i}] ({m.get('id','?')}): missing/empty '{k}'")
            elif k in ENUMS and v not in ENUMS[k]:
                errors.append(f"moves[{i}] ({m.get('id','?')}): {k}={v!r} not in {sorted(ENUMS[k])}")
        if set(m) - set(REQUIRED):
            errors.append(f"moves[{i}]: unexpected keys {sorted(set(m) - set(REQUIRED))}")
        if m.get("id") in ids:
            errors.append(f"duplicate id {m['id']!r}")
        ids.add(m.get("id"))
    if yaml.safe_load(yaml.safe_dump(data)) != data:
        errors.append("round-trip mismatch")
    if errors:
        print("\n".join(errors)); sys.exit(f"FAIL: {len(errors)} error(s)")
    print(f"OK: {len(moves)} moves valid")

if __name__ == "__main__":
    main(*sys.argv[1:])
