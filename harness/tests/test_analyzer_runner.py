from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, validators

from harness.structured.analyzer import (
    AnalyzerExecutorError,
    AnalyzerMode,
    findings_from_document,
    load_analyzer_config,
    probe_flags,
    run_analyzer_config,
    run_analyzer_item,
)
from harness.structured.asserts.analyzer_match import match_findings
from harness.structured.config import ConfigError
from harness.structured.replay import replay
from harness.structured.taskset import InputRef, TaskItem


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tasksets/structured/prism_fixtures"
SARIF_SCHEMA = Path(__file__).resolve().parent / "fixtures/sarif-schema-2.1.0.json"


class _FixedClock:
    def __init__(self, value: str) -> None:
        self.value = value

    def now(self) -> str:
        return self.value

    def monotonic(self) -> float:
        return 0.0


def _recorded(name: str) -> dict:
    return json.loads((FIXTURE / "recorded" / name).read_text())


def _fake_prism(
    tmp_path: Path,
    *,
    help_text: str,
    document: dict,
    help_exit: int = 0,
    analyze_exit: int = 0,
) -> Path:
    path = tmp_path / "prism"
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"help_text = {help_text!r}\n"
        f"help_exit = {help_exit}\n"
        f"analyze_exit = {analyze_exit}\n"
        f"document = {document!r}\n"
        "log = pathlib.Path(__file__).with_suffix('.calls')\n"
        "with log.open('a') as out: out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:] == ['--help']:\n"
        "    print(help_text)\n"
        "    raise SystemExit(help_exit)\n"
        "if analyze_exit:\n"
        "    print('analyzer failed', file=sys.stderr)\n"
        "    raise SystemExit(analyze_exit)\n"
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
    validators.validator_for(sarif_schema).check_schema(sarif_schema)
    validators.validator_for(sarif_schema)(sarif_schema).validate(
        _recorded("absence-nominal.sarif.json")
    )


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
        AnalyzerMode("absence", "python", "nominal", "nameonly"),
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
    mode = AnalyzerMode("absence", "python", "nominal", "nameonly")
    result = run_analyzer_item(_item(), mode, binary=str(binary), line_tolerance=3)
    assert result.match is not None
    assert (result.match.tp, result.match.fp, result.match.fn) == (1, 0, 0)
    assert result.version_record == {
        "version": "absence/python/nominal/nameonly",
        "algorithm": "absence",
        "language": "python",
        "resolution": "nominal",
        "min_confidence": "nameonly",
    }
    assert result.stage_record["stage"] == "analyzer"
    assert result.stage_record["output_contract"] == "sarif-2.1.0"
    assert result.strata == (
        {"language": "python", "tier": "asserted", "resolution": "nominal", "tp": 1, "fp": 0, "fn": 0},
        {"language": "python", "tier": "candidate", "resolution": "nominal", "tp": 0, "fp": 0, "fn": 0},
    )
    argv = json.loads((tmp_path / "prism.calls").read_text().splitlines()[1])
    assert argv[-6:] == ["--format", "sarif", "--resolution", "nominal", "--min-confidence", "nameonly"]
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
            AnalyzerMode("absence", "python", "nominal", "nameonly"),
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
        AnalyzerMode("absence", "python", "nominal", "nameonly"),
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
    sarif_schema = json.loads(SARIF_SCHEMA.read_text())
    validators.validator_for(sarif_schema)(sarif_schema).validate(document)
    emitted = findings_from_document(document)
    matched = match_findings(
        _item().expected["findings"],
        emitted,
        line_tolerance=3,
        negative_findings=[],
        max_findings=2,
    )
    assert (emitted[0]["line"], matched.tp, matched.fp, matched.fn) == (0, 0, 1, 1)


def test_analyzer_config_expands_modes_and_probes_once_before_skipping(tmp_path):
    cfg = load_analyzer_config(REPO_ROOT / "experiments/structured/an-smoke.yaml")
    assert [mode.version for mode in cfg.modes] == ["absence/python/nominal/nameonly"]
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --repo --algorithm --diff --format --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    results = run_analyzer_config(cfg, binary=str(binary))
    assert len(results) == 1
    assert results[0].version_record["skipped"] == "flag_unavailable(--resolution)"
    assert (tmp_path / "prism.calls").read_text().splitlines() == ['["--help"]']


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"baseline_version": "missing"}, "baseline_version"),
        ({"modes": {"algorithm": []}}, "modes must declare"),
        ({"match": {"rule": "function", "line_tolerance": 3}}, "match.rule"),
        ({"prism_bin": "/tmp/prism"}, "prism_bin"),
    ],
)
def test_analyzer_config_rejects_invalid_mode_policy(tmp_path, mutation, message):
    (tmp_path / "taskset").mkdir()
    value = {
        "kind": "analyzer",
        "id": "an-fixture",
        "taskset": "taskset",
        "split": "dev",
        "modes": {
            "algorithm": ["absence"],
            "language": ["python"],
            "resolution": ["nominal"],
            "min_confidence": ["nameonly"],
        },
        "baseline_version": "absence/python/nominal/nameonly",
        "match": {"rule": "category_file_line", "line_tolerance": 3},
        "asserts": [{"type": "analyzer_match"}],
        "stats": {"bootstrap_resamples": 20, "seed": 20260904},
        "token_budget": {"max_items": 1},
    }
    if "modes" in mutation:
        value["modes"].update(mutation["modes"])
    else:
        value.update(mutation)
    path = tmp_path / "an.yaml"
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(ConfigError, match=message):
        load_analyzer_config(path, root=tmp_path)


@pytest.mark.parametrize(
    "axis, value, message",
    [
        ("min_confidence", "nominal", "min_confidence"),
        ("resolution", "approximate", "resolution"),
    ],
)
def test_analyzer_config_rejects_values_outside_closed_mode_vocabularies(
    tmp_path, axis, value, message
):
    (tmp_path / "taskset").mkdir()
    config = {
        "kind": "analyzer",
        "id": "an-fixture",
        "taskset": "taskset",
        "split": "dev",
        "modes": {
            "algorithm": ["absence"],
            "language": ["python"],
            "resolution": ["nominal"],
            "min_confidence": ["nameonly"],
        },
        "baseline_version": "absence/python/nominal/nameonly",
        "match": {"rule": "category_file_line", "line_tolerance": 3},
        "asserts": [{"type": "analyzer_match"}],
        "stats": {"bootstrap_resamples": 20, "seed": 20260904},
        "token_budget": {"max_items": 1},
    }
    config["modes"][axis] = [value]
    config["baseline_version"] = f"absence/python/{config['modes']['resolution'][0]}/{config['modes']['min_confidence'][0]}"
    path = tmp_path / "an.yaml"
    path.write_text(yaml.safe_dump(config))

    with pytest.raises(ConfigError, match=message):
        load_analyzer_config(path, root=tmp_path)


def test_projectable_sarif_missing_required_tool_is_rejected_before_matching(tmp_path):
    document = _recorded("absence-nominal.sarif.json")
    del document["runs"][0]["tool"]
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=document,
    )

    with pytest.raises(
        AnalyzerExecutorError, match=r"SARIF schema validation failed at runs/0:.*tool"
    ):
        run_analyzer_item(
            _item(),
            AnalyzerMode("absence", "python", "nominal", "nameonly"),
            binary=str(binary),
            line_tolerance=3,
        )


def _copy_analyzer_smoke_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "contracts", root / "contracts")
    (root / "harness/tests/fixtures").mkdir(parents=True)
    shutil.copy2(SARIF_SCHEMA, root / "harness/tests/fixtures")
    shutil.copytree(FIXTURE, root / "tasksets/structured/prism_fixtures")
    (root / "experiments/structured").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "experiments/structured/an-smoke.yaml",
        root / "experiments/structured/an-smoke.yaml",
    )
    return root


def test_analyzer_cli_writes_complete_results_tree_with_fake_prism(tmp_path, monkeypatch):
    from harness.structured import run as run_module

    root = _copy_analyzer_smoke_root(tmp_path)
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("PRISM_BIN", str(binary))
    monkeypatch.setattr(run_module, "_CLOCK", _FixedClock("2026-09-05T12:00:00Z"))

    assert run_module.main([str(root / "experiments/structured/an-smoke.yaml")]) == 0
    run_dir = next((root / "results/an-smoke").iterdir())
    stage = json.loads(next((run_dir / "stages").glob("*.json")).read_text())
    call = json.loads(next((run_dir / "calls").glob("*.json")).read_text())
    assertion = json.loads(next((run_dir / "asserts").glob("*.json")).read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert (stage["stage"], stage["status"]) == ("analyzer", "ok")
    assert call.get("stage_error") is None
    assert assertion["asserts"][0]["name"] == "analyzer_match"
    assert metrics["versions"]["absence/python/nominal/nameonly"]["n_items"] == 1
    assert metrics["versions"]["absence/python/nominal/nameonly"]["micro"]["f1"] == 1.0


def test_analyzer_replay_uses_finding_reducer_without_executor(tmp_path, monkeypatch):
    from harness.structured import run as run_module

    root = _copy_analyzer_smoke_root(tmp_path)
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    monkeypatch.setenv("PRISM_BIN", str(binary))
    monkeypatch.setattr(run_module, "_CLOCK", _FixedClock("2026-09-05T12:00:00Z"))
    assert run_module.main([str(root / "experiments/structured/an-smoke.yaml")]) == 0
    run_dir = next((root / "results/an-smoke").iterdir())
    before_calls = binary.with_suffix(".calls").read_bytes()
    expected = json.loads((run_dir / "metrics.json").read_text())

    result = replay(run_dir)

    assert result.executor_calls == 0
    assert result.metrics == expected
    assert binary.with_suffix(".calls").read_bytes() == before_calls


def test_analyzer_cli_records_missing_prism_and_excludes_item(tmp_path, monkeypatch):
    from harness.structured import run as run_module

    root = _copy_analyzer_smoke_root(tmp_path)
    monkeypatch.delenv("PRISM_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(run_module, "_CLOCK", _FixedClock("2026-09-05T12:00:00Z"))

    assert run_module.main([str(root / "experiments/structured/an-smoke.yaml")]) == 0
    run_dir = next((root / "results/an-smoke").iterdir())
    stage = json.loads(next((run_dir / "stages").glob("*.json")).read_text())
    call = json.loads(next((run_dir / "calls").glob("*.json")).read_text())
    assertion = json.loads(next((run_dir / "asserts").glob("*.json")).read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert stage["status"] == "error"
    assert call["stage_error"] == "analyzer"
    assert "prism" in call["stage_error_detail"]["message"]
    assert assertion == {
        "item_id": "px-py-absence-0001",
        "version": "absence/python/nominal/nameonly",
        "sample": 0,
        "stage_error": "analyzer",
        "asserts": [],
    }
    version = metrics["versions"]["absence/python/nominal/nameonly"]
    assert version["n_items"] == 0
    assert version["stage_errors"] == {
        "calls": 1,
        "item_ids": ["px-py-absence-0001"],
    }


def test_analyzer_cli_records_flag_unavailable_as_skip(tmp_path, monkeypatch):
    from harness.structured import run as run_module

    root = _copy_analyzer_smoke_root(tmp_path)
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --min-confidence",
        document=_recorded("absence-nominal.sarif.json"),
    )
    monkeypatch.setenv("PRISM_BIN", str(binary))
    monkeypatch.setattr(run_module, "_CLOCK", _FixedClock("2026-09-05T12:00:00Z"))

    assert run_module.main([str(root / "experiments/structured/an-smoke.yaml")]) == 0
    run_dir = next((root / "results/an-smoke").iterdir())
    stage = json.loads(next((run_dir / "stages").glob("*.json")).read_text())
    call = json.loads(next((run_dir / "calls").glob("*.json")).read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert stage["status"] == "skipped"
    assert call["skipped"] == "flag_unavailable(--resolution)"
    assert "stage_error" not in call
    version = metrics["versions"]["absence/python/nominal/nameonly"]
    assert version["n_items"] == 0
    assert version["stage_errors"] == {"calls": 0, "item_ids": []}
    assert version["skipped"]["reasons"] == ["flag_unavailable(--resolution)"]


@pytest.mark.parametrize(
    "failure, expected_reason",
    [("nonzero", "exited with code 7"), ("invalid_document", "schema validation failed")],
)
def test_analyzer_cli_records_execution_and_document_failures_as_stage_errors(
    tmp_path, monkeypatch, failure, expected_reason
):
    from harness.structured import run as run_module

    root = _copy_analyzer_smoke_root(tmp_path)
    document = _recorded("absence-nominal.sarif.json")
    if failure == "invalid_document":
        del document["runs"][0]["tool"]
    binary = _fake_prism(
        tmp_path,
        help_text="Usage: prism --resolution --min-confidence",
        document=document,
        analyze_exit=7 if failure == "nonzero" else 0,
    )
    monkeypatch.setenv("PRISM_BIN", str(binary))
    monkeypatch.setattr(run_module, "_CLOCK", _FixedClock("2026-09-05T12:00:00Z"))

    assert run_module.main([str(root / "experiments/structured/an-smoke.yaml")]) == 0
    run_dir = next((root / "results/an-smoke").iterdir())
    call = json.loads(next((run_dir / "calls").glob("*.json")).read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert call["stage_error"] == "analyzer"
    assert expected_reason in call["stage_error_detail"]["message"]
    version = metrics["versions"]["absence/python/nominal/nameonly"]
    assert version["n_items"] == 0
    assert version["stage_errors"]["item_ids"] == ["px-py-absence-0001"]
