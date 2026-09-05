from pathlib import Path


STRUCTURED = Path(__file__).resolve().parents[1] / "structured"
MAX_MODULE_LINES = 350


def test_runner_and_report_seams_stay_near_the_plan_size():
    modules = sorted(
        set(STRUCTURED.glob("*runner*.py")) | set(STRUCTURED.glob("*report*.py"))
    )
    offenders = {
        path.name: len(path.read_text().splitlines())
        for path in modules
        if len(path.read_text().splitlines()) > MAX_MODULE_LINES
    }

    assert offenders == {}
