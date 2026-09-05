from pathlib import Path


STRUCTURED = Path(__file__).resolve().parents[1] / "structured"
MAX_MODULE_LINES = 300


def test_all_structured_modules_stay_within_size_cap():
    modules = sorted(STRUCTURED.glob("*.py"))
    offenders = {
        path.name: len(path.read_text().splitlines())
        for path in modules
        if len(path.read_text().splitlines()) > MAX_MODULE_LINES
    }

    assert offenders == {}
