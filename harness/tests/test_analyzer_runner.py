from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from harness.structured.analyzer import (
    AnalyzerExecutorError,
    AnalyzerMode,
    findings_from_document,
    probe_flags,
    run_analyzer_item,
)
from harness.structured.asserts.analyzer_match import match_findings
from harness.structured.taskset import InputRef, TaskItem


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tasksets/structured/prism_fixtures"
SARIF_SCHEMA = Path(__file__).resolve().parent / "fixtures/sarif-schema-2.1.0.json"


def _recorded(name: str) -> dict:
    return json.loads((FIXTURE / "recorded" / name).read_text())


def _fake_prism(tmp_path: Path, *, help_text: str, document: dict, help_exit: int = 0) -> Path:
    path = tmp_path / "prism"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"help_text = {help_text!r}\n"
        f"help_exit = {help_exit}\n"
        f"document = {document!r}\n"
        "log = pathlib.Path(__file__).with_suffix('.calls')\n"
        "with log.open('a') as out: out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:] == ['--help']:\n"
        "    print(help_text)\n"
        "    raise SystemExit(help_exit)\n"
        "print(json.dumps(document))\n"
    )
    path.chmod(0o755)
    return path


def _item() -> TaskItem:
    root = FIXTURE / "inputs/px-py-absence-0001"
    return TaskItem(
        id="px-py-absence-0001",
        task="prism_analyzer",
        split="dev",
        expected={
            "findings": [
                {"category": "missing_error_handling", "file": "src/client.py", "line": 4, "tier": "asserted"}
            ],
            "negative_findings": [],
            "max_findings": 2,
        },
        inputs={
            "repo": InputRef("repo", root / "repo", "0" * 64),
            "diff": InputRef("diff", root / "change.patch", "0" * 64),
        },
        input_values={},
        raw={"language": "python", "algorithm": "absence"},
    )


def test_recorded_prism_documents_validate_against_their_contracts():
    targets_schema = json.loads((REPO_ROOT / "contracts/targets.schema.json").read_text())
    sarif_schema = json.loads(SARIF_SCHEMA.read_text())
    Draft202012Validator(targets_schema).validate(_recorded("absence-nominal.targets.json"))
    Draft202012Validator(sarif_schema).validate(_recorded("absence-nominal.sarif.json"))


@pytest.mark.parametrize("name", ["absence-nominal.targets.json", "absence-nominal.sarif.json"])
def test_findings_are_projected_from_both_prism_documents(name):
    assert findings_from_document(_recorded(name)) == (
        {"category": "missing_error_handling", "file": "src/client.py", "line": 4, "tier": "asserted"},
    )


def test_unavailable_resolution_flag_skips_without_analyze_invocation(tmp_path):
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --repo --algorithm --diff --format --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    result = run_analyzer_item(
        _item(),
        AnalyzerMode("absence", "python", "nominal", "nominal"),
        binary=str(binary),
        line_tolerance=3,
    )
    assert result.version_record["skipped"] == "flag_unavailable(--resolution)"
    calls = (tmp_path / "prism.calls").read_text().splitlines()
    assert [json.loads(call) for call in calls] == [["--help"]]
    assert result.stage_record is None


def test_help_probe_nonzero_is_executor_error(tmp_path):
    binary = _fake_prism(tmp_path, help_text="broken", document={}, help_exit=7)
    with pytest.raises(AnalyzerExecutorError, match="help probe.*code 7"):
        probe_flags(str(binary))


def test_mode_run_matches_recorded_sarif_and_emits_strata(tmp_path):
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --repo --algorithm --diff --format --resolution --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    mode = AnalyzerMode("absence", "python", "nominal", "nominal")
    result = run_analyzer_item(_item(), mode, binary=str(binary), line_tolerance=3)
    assert result.match is not None
    assert (result.match.tp, result.match.fp, result.match.fn) == (1, 0, 0)
    assert result.version_record == {
        "version": "absence/python/nominal/nominal",
        "algorithm": "absence",
        "language": "python",
        "resolution": "nominal",
        "min_confidence": "nominal",
    }
    assert result.stage_record["stage"] == "analyzer"
    assert result.stage_record["output_contract"] == "sarif-2.1.0"
    assert result.strata == (
        {"language": "python", "tier": "asserted", "resolution": "nominal", "tp": 1, "fp": 0, "fn": 0},
        {"language": "python", "tier": "candidate", "resolution": "nominal", "tp": 0, "fp": 0, "fn": 0},
    )
    argv = json.loads((tmp_path / "prism.calls").read_text().splitlines()[1])
    assert argv[-6:] == ["--format", "sarif", "--resolution", "nominal", "--min-confidence", "nominal"]
    assert "callers" not in argv


def test_reported_resolution_must_match_requested_mode(tmp_path):
    document = _recorded("absence-nominal.sarif.json")
    document["runs"][0]["properties"]["resolution_mode"] = "scoped"
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=document,
    )
    with pytest.raises(AnalyzerExecutorError, match="resolution mismatch"):
        run_analyzer_item(
            _item(),
            AnalyzerMode("absence", "python", "nominal", "nominal"),
            binary=str(binary),
            line_tolerance=3,
        )


def test_tier_demotion_moves_the_stratified_counts_without_becoming_a_miss(tmp_path):
    document = _recorded("absence-nominal.sarif.json")
    document["runs"][0]["results"][0]["properties"]["tier"] = "candidate"
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=document,
    )
    result = run_analyzer_item(
        _item(),
        AnalyzerMode("absence", "python", "nominal", "nominal"),
        binary=str(binary),
        line_tolerance=3,
    )
    assert result.match is not None and result.match.tp == 1
    assert [(row["tier"], row["tp"], row["fp"], row["fn"]) for row in result.strata] == [
        ("asserted", 0, 0, 1),
        ("candidate", 0, 1, 0),
    ]


def test_valid_sarif_line_zero_without_region_is_an_unmatched_emission():
    document = _recorded("absence-nominal.sarif.json")
    del document["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    Draft202012Validator(json.loads(SARIF_SCHEMA.read_text())).validate(document)
    emitted = findings_from_document(document)
    matched = match_findings(
        _item().expected["findings"],
        emitted,
        line_tolerance=3,
        negative_findings=[],
        max_findings=2,
    )
    assert (emitted[0]["line"], matched.tp, matched.fp, matched.fn) == (0, 0, 1, 1)
