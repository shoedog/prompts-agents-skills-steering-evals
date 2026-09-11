from pathlib import Path


def test_moves_catalog_is_never_opened_by_runtime_modules():
    harness = Path(__file__).resolve().parents[1]
    offenders = []
    for path in sorted(harness.rglob("*.py")):
        if "tests" in path.parts:
            continue
        if "moves.yaml" in path.read_text():
            offenders.append(str(path.relative_to(harness.parent)))
    assert offenders == []
