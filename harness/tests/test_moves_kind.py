import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def run_check(tmp_path: Path, kind: str | None) -> subprocess.CompletedProcess[str]:
    move = {
        "id": "x",
        "name": "x",
        "classification": "element",
        "verdict": "build",
        "eval_shape": "ablation",
        "evidence_tier": "swe",
        "notes": "x",
    }
    if kind is not None:
        move["kind"] = kind
    path = tmp_path / "moves.yaml"
    path.write_text(yaml.safe_dump({"moves": [move]}, sort_keys=False))
    return subprocess.run(
        [sys.executable, "scripts/check_moves.py", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_kind_is_optional_and_defaults_to_review_ablation(tmp_path):
    assert run_check(tmp_path, None).returncode == 0


def test_structured_kinds_are_accepted(tmp_path):
    for kind in ("review_ablation", "structured_task", "analyzer", "pipeline"):
        assert run_check(tmp_path, kind).returncode == 0


def test_unknown_kind_is_rejected(tmp_path):
    proc = run_check(tmp_path, "free_form")
    assert proc.returncode != 0
    assert "kind='free_form'" in proc.stdout + proc.stderr
