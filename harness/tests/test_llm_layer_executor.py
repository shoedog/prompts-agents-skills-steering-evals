from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import Draft202012Validator

from harness.structured.executors import (
    EnvelopeContractError,
    EnvelopeEchoError,
    EnvelopeStdoutError,
    ExecutionRequest,
    ExecutionResult,
    ExecutorError,
    FakeExecutor,
    LlmLayerExecutor,
    LlmRunEnvelope,
    LlmUsage,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "llm_layer"
ENVELOPE_SCHEMA_SHA256 = "1219f167faa80fb65d128f4258c5525904aaa9d7d1c2cec25b587b4861f917c8"
EXPECTED_ENVELOPE_KEYS = {
    "schema_version",
    "invocation_id",
    "task",
    "task_version",
    "provider",
    "model",
    "provider_version",
    "prompt_sha256",
    "escalation_state",
    "first_tier_valid",
    "first_tier_sentinel",
    "final_sentinel",
    "cache_hit",
    "usage",
    "cost_usd",
    "response",
    "log_path",
}


def load_envelope_schema() -> dict:
    return json.loads((REPO_ROOT / "contracts" / "llm_run_envelope.schema.json").read_text())


def load_envelope_fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def write_request(root: Path) -> Path:
    request = root / "request.json"
    request.write_text('{"observation_ref":{"target_id":"eh-py-0042"}}\n')
    return request


def recorded_argv(root: Path) -> list[str]:
    return json.loads((root / "scratch" / "llm-layer-argv.json").read_text())


def configure_envelope(root: Path, envelope: dict) -> None:
    scratch = root / "scratch"
    scratch.mkdir(exist_ok=True)
    (scratch / "llm-layer-behavior.json").write_text(
        json.dumps({"envelope": envelope}, separators=(",", ":")) + "\n"
    )


def configure_exit(binary: Path, returncode: int) -> None:
    (binary.parent / "llm-layer-behavior.json").write_text(
        json.dumps(
            {"returncode": returncode, "stderr": "configured child failure"},
            separators=(",", ":"),
        )
        + "\n"
    )


def execute_one(root: Path, binary: Path) -> ExecutionResult:
    request = write_request(root)
    return LlmLayerExecutor(binary=binary).run(
        ExecutionRequest(
            task="classify_error_handling",
            task_version="2026-09-04.1",
            request_file=request,
            model="fake-model",
            seed=20260904,
            sample=0,
            scratch_dir=root / "scratch",
        )
    )


def json_path_for(error) -> str:
    parts = [str(part) for part in error.path]
    return "$" + "".join(f"[{part}]" if part.isdigit() else f".{part}" for part in parts)


def canonical_request_sha256(path: Path) -> str:
    value = json.loads(path.read_text())
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.fixture
def fake_llm_cli(tmp_path: Path) -> Path:
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    binary = scratch / "llm-layer"
    shutil.copyfile(FIXTURE_ROOT / "fake_cli.py", binary)
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary


def test_vendored_envelope_contract_checksum_and_schema_are_pinned():
    schema_bytes = (REPO_ROOT / "contracts" / "llm_run_envelope.schema.json").read_bytes()
    assert hashlib.sha256(schema_bytes).hexdigest() == ENVELOPE_SCHEMA_SHA256
    Draft202012Validator.check_schema(json.loads(schema_bytes))


def test_llm_usage_and_envelope_typeddicts_are_closed():
    assert LlmUsage.__closed__ is True
    assert LlmRunEnvelope.__closed__ is True
    assert set(LlmUsage.__required_keys__) == {
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    }
    assert set(LlmRunEnvelope.__required_keys__) == EXPECTED_ENVELOPE_KEYS


def test_fake_executor_is_keyed_by_canonical_request_and_records_distinct_samples(tmp_path):
    request_file = write_request(tmp_path)
    expected = load_envelope_fixture("success")
    Draft202012Validator(load_envelope_schema()).validate(expected)
    key = canonical_request_sha256(request_file)
    executor = FakeExecutor({key: expected})
    requests = [
        ExecutionRequest(
            task="classify_error_handling",
            task_version="2026-09-04.1",
            request_file=request_file,
            model="fake-model",
            seed=20260904,
            sample=sample,
            scratch_dir=tmp_path / "scratch",
        )
        for sample in (0, 1)
    ]

    first = executor.run(requests[0])
    repeated = executor.run(requests[0])
    second_sample = executor.run(requests[1])

    canonical_stdout = json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n"
    assert first == repeated == second_sample
    assert first.envelope == expected
    assert first.envelope is not expected
    assert first.raw_stdout == canonical_stdout
    assert first.returncode == 0
    assert executor.requests == (requests[0], requests[0], requests[1])


def test_fake_executor_rejects_an_unconfigured_request_hash(tmp_path):
    request_file = write_request(tmp_path)
    executor = FakeExecutor({})
    request = ExecutionRequest(
        task="classify_error_handling",
        task_version="2026-09-04.1",
        request_file=request_file,
        model="fake-model",
        seed=1,
        sample=0,
        scratch_dir=tmp_path / "scratch",
    )
    with pytest.raises(KeyError, match=canonical_request_sha256(request_file)):
        executor.run(request)
    assert executor.requests == (request,)


def test_llm_layer_argv_and_success_envelope(tmp_path, fake_llm_cli):
    request = write_request(tmp_path)
    expected = load_envelope_fixture("success")
    schema = load_envelope_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(expected)
    configure_envelope(tmp_path, expected)

    with patch(
        "harness.structured.executors.llm_layer.subprocess.run", wraps=subprocess.run
    ) as run:
        result = LlmLayerExecutor(binary=fake_llm_cli, timeout_seconds=17).run(
            ExecutionRequest(
                task="classify_error_handling",
                task_version="2026-09-04.1",
                request_file=request,
                model="fake-model",
                seed=20260904,
                sample=0,
                scratch_dir=tmp_path / "scratch",
            )
        )

    assert recorded_argv(tmp_path) == [
        "run",
        "--task",
        "classify_error_handling",
        "--task-version",
        "2026-09-04.1",
        "--request-file",
        str(request),
        "--model",
        "fake-model",
        "--seed",
        "20260904",
        "--json",
    ]
    assert run.call_args.kwargs == {
        "cwd": tmp_path / "scratch",
        "capture_output": True,
        "text": True,
        "timeout": 17,
        "check": False,
    }
    assert set(result.envelope) == EXPECTED_ENVELOPE_KEYS
    assert result.envelope == expected
    assert result.raw_stdout == json.dumps(expected, separators=(",", ":")) + "\n"
    assert result.returncode == 0
    assert expected["invocation_id"] == "123e4567-e89b-42d3-a456-426614174000"
    assert expected["usage"] == {
        "input_tokens": 12,
        "output_tokens": 7,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


def test_default_binary_is_resolved_through_binpath(tmp_path, fake_llm_cli):
    configure_envelope(tmp_path, load_envelope_fixture("success"))
    with patch(
        "harness.structured.executors.llm_layer.resolve_executable",
        return_value=str(fake_llm_cli),
    ) as resolve:
        result = LlmLayerExecutor().run(
            ExecutionRequest(
                task="classify_error_handling",
                task_version="2026-09-04.1",
                request_file=write_request(tmp_path),
                model="fake-model",
                seed=20260904,
                sample=0,
                scratch_dir=tmp_path / "scratch",
            )
        )
    resolve.assert_called_once_with("llm-layer")
    assert result.returncode == 0


def test_nullable_first_tier_flags_are_contract_valid_and_preserved(tmp_path, fake_llm_cli):
    expected = load_envelope_fixture("nullable-flags")
    Draft202012Validator(load_envelope_schema()).validate(expected)
    configure_envelope(tmp_path, expected)
    result = execute_one(tmp_path, fake_llm_cli)
    assert result.envelope["first_tier_valid"] is None
    assert result.envelope["first_tier_sentinel"] is None


def test_zero_exit_accepts_and_preserves_sentinel_flags(tmp_path, fake_llm_cli):
    expected = load_envelope_fixture("success")
    expected.update(
        first_tier_valid=False,
        first_tier_sentinel=True,
        final_sentinel=True,
        escalation_state="sentinel",
    )
    Draft202012Validator(load_envelope_schema()).validate(expected)
    configure_envelope(tmp_path, expected)
    result = execute_one(tmp_path, fake_llm_cli)
    assert result.envelope == expected


@pytest.mark.parametrize("returncode", [1, 2, 3, 4, 5, 6])
def test_nonzero_llm_exit_is_a_typed_stage_failure(tmp_path, fake_llm_cli, returncode):
    configure_exit(fake_llm_cli, returncode)
    with pytest.raises(ExecutorError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert caught.value.returncode == returncode
    assert caught.value.stderr_tail == "configured child failure"
    assert (tmp_path / "scratch" / "llm-layer-call-count.txt").read_text() == "1\n"


def test_exit_five_with_a_valid_envelope_is_still_an_executor_error(tmp_path):
    envelope = load_envelope_fixture("success")
    stdout = json.dumps(envelope, separators=(",", ":")) + "\n"
    proc = subprocess.CompletedProcess(
        args=["llm-layer"],
        returncode=5,
        stdout=stdout,
        stderr="test split requires --allow-test",
    )
    with patch("harness.structured.executors.llm_layer.subprocess.run", return_value=proc):
        with pytest.raises(ExecutorError) as caught:
            execute_one(tmp_path, Path("llm-layer"))
    assert caught.value.returncode == 5
    assert caught.value.stdout_tail == stdout
    assert caught.value.stderr_tail == "test split requires --allow-test"


@pytest.mark.parametrize(
    "fixture, validator_name, json_path",
    [
        ("bad-uuid", "pattern", "$.invocation_id"),
        ("missing-usage-field", "required", "$.usage"),
        ("extra-envelope-key", "additionalProperties", "$"),
        ("extra-usage-key", "additionalProperties", "$.usage"),
        ("null-final-sentinel", "type", "$.final_sentinel"),
    ],
)
def test_contract_invalid_envelopes_are_rejected_distinctly(
    tmp_path, fake_llm_cli, fixture, validator_name, json_path
):
    envelope = load_envelope_fixture(fixture)
    validator = Draft202012Validator(load_envelope_schema())
    source_errors = sorted(validator.iter_errors(envelope), key=lambda error: list(error.path))
    assert [(error.validator, json_path_for(error)) for error in source_errors] == [
        (validator_name, json_path)
    ]
    configure_envelope(tmp_path, envelope)
    with pytest.raises(EnvelopeContractError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert (caught.value.validator, caught.value.json_path) == (validator_name, json_path)


@pytest.mark.parametrize(
    "field, bad_value, validator_name",
    [
        ("schema_version", "2", "const"),
        ("prompt_sha256", "ABC", "pattern"),
    ],
)
def test_other_contract_errors_remain_typed(
    tmp_path, fake_llm_cli, field, bad_value, validator_name
):
    envelope = load_envelope_fixture("success")
    envelope[field] = bad_value
    configure_envelope(tmp_path, envelope)
    with pytest.raises(EnvelopeContractError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert caught.value.validator == validator_name
    assert caught.value.json_path == f"$.{field}"


@pytest.mark.parametrize("field", ["task", "task_version", "model"])
def test_request_echo_mismatch_is_distinct_from_contract_failure(tmp_path, fake_llm_cli, field):
    envelope = load_envelope_fixture("success")
    envelope[field] = f"wrong-{field}"
    Draft202012Validator(load_envelope_schema()).validate(envelope)
    configure_envelope(tmp_path, envelope)
    with pytest.raises(EnvelopeEchoError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert caught.value.field == field
    assert caught.value.expected != caught.value.actual


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "{}\n{}\n",
        "[]\n",
        '{"schema_version":"1"}\n\n',
        'diagnostic\n{"schema_version":"1"}\n',
    ],
)
def test_stdout_must_be_exactly_one_object_and_one_newline(tmp_path, fake_llm_cli, stdout):
    scratch = tmp_path / "scratch"
    (scratch / "llm-layer-behavior.json").write_text(
        json.dumps({"stdout_raw": stdout, "stderr": "diagnostic detail"}) + "\n"
    )
    with pytest.raises(EnvelopeStdoutError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert caught.value.stdout_tail == stdout
    assert caught.value.stderr_tail == "diagnostic detail"


def test_stdout_rejects_non_json_numeric_constants(tmp_path, fake_llm_cli):
    stdout = (FIXTURE_ROOT / "success.json").read_text().replace(
        '"cost_usd":0.001', '"cost_usd":NaN'
    )
    scratch = tmp_path / "scratch"
    (scratch / "llm-layer-behavior.json").write_text(
        json.dumps({"stdout_raw": stdout}) + "\n"
    )
    with pytest.raises(EnvelopeStdoutError):
        execute_one(tmp_path, fake_llm_cli)


def test_all_typed_errors_bound_stdout_and_stderr_tails(tmp_path, fake_llm_cli):
    envelope = deepcopy(load_envelope_fixture("success"))
    envelope["unexpected"] = True
    stdout = json.dumps(envelope, separators=(",", ":")) + "\n"
    marker = "tail-marker"
    scratch = tmp_path / "scratch"
    (scratch / "llm-layer-behavior.json").write_text(
        json.dumps({"stdout_raw": "x" * 5000 + stdout, "stderr": "y" * 5000 + marker})
        + "\n"
    )
    with pytest.raises(EnvelopeStdoutError) as caught:
        execute_one(tmp_path, fake_llm_cli)
    assert len(caught.value.stdout_tail) <= 4000
    assert len(caught.value.stderr_tail) <= 4000
    assert caught.value.stderr_tail.endswith(marker)


def test_timeout_decodes_and_bounds_captured_byte_tails(tmp_path):
    timeout = subprocess.TimeoutExpired(
        cmd=["llm-layer"],
        timeout=1,
        output=b"x" * 5000 + b"stdout-marker",
        stderr=b"y" * 5000 + b"stderr-marker",
    )
    with patch(
        "harness.structured.executors.llm_layer.subprocess.run", side_effect=timeout
    ):
        with pytest.raises(ExecutorError) as caught:
            LlmLayerExecutor(binary="llm-layer", timeout_seconds=1).run(
                ExecutionRequest(
                    task="classify_error_handling",
                    task_version="2026-09-04.1",
                    request_file=write_request(tmp_path),
                    model="fake-model",
                    seed=1,
                    sample=0,
                    scratch_dir=tmp_path,
                )
            )
    assert caught.value.returncode == -1
    assert isinstance(caught.value.stdout_tail, str)
    assert isinstance(caught.value.stderr_tail, str)
    assert len(caught.value.stdout_tail) <= 4000
    assert len(caught.value.stderr_tail) <= 4000
    assert caught.value.stdout_tail.endswith("stdout-marker")
    assert caught.value.stderr_tail.endswith("stderr-marker")


def test_process_start_error_is_typed_and_does_not_retry(tmp_path):
    with patch(
        "harness.structured.executors.llm_layer.subprocess.run",
        side_effect=FileNotFoundError("missing llm-layer"),
    ) as run:
        with pytest.raises(ExecutorError, match="failed to start") as caught:
            LlmLayerExecutor(binary="missing-llm-layer").run(
                ExecutionRequest(
                    task="classify_error_handling",
                    task_version="2026-09-04.1",
                    request_file=write_request(tmp_path),
                    model="fake-model",
                    seed=1,
                    sample=0,
                    scratch_dir=tmp_path,
                )
            )
    assert caught.value.returncode == -1
    assert caught.value.stdout_tail == ""
    assert caught.value.stderr_tail == ""
    assert run.call_count == 1


@pytest.mark.parametrize(
    "failure_kind, error_type",
    [
        ("contract", EnvelopeContractError),
        ("echo", EnvelopeEchoError),
        ("exit", ExecutorError),
    ],
)
def test_post_process_errors_retain_bounded_output_tails(tmp_path, failure_kind, error_type):
    envelope = load_envelope_fixture("success")
    envelope["log_path"] = "x" * 5000 + "stdout-marker"
    returncode = 0
    if failure_kind == "contract":
        envelope["unexpected"] = True
    elif failure_kind == "echo":
        envelope["task"] = "wrong-task"
    else:
        returncode = 6
    proc = subprocess.CompletedProcess(
        args=["llm-layer"],
        returncode=returncode,
        stdout=json.dumps(envelope, separators=(",", ":")) + "\n",
        stderr="y" * 5000 + "stderr-marker",
    )
    with patch(
        "harness.structured.executors.llm_layer.subprocess.run", return_value=proc
    ):
        with pytest.raises(error_type) as caught:
            LlmLayerExecutor(binary="llm-layer").run(
                ExecutionRequest(
                    task="classify_error_handling",
                    task_version="2026-09-04.1",
                    request_file=write_request(tmp_path),
                    model="fake-model",
                    seed=1,
                    sample=0,
                    scratch_dir=tmp_path,
                )
            )
    assert len(caught.value.stdout_tail) <= 4000
    assert len(caught.value.stderr_tail) <= 4000
    assert "stdout-marker" in caught.value.stdout_tail
    assert caught.value.stderr_tail.endswith("stderr-marker")
