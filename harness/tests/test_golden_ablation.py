"""Golden-run guards for review-ablation and structured replay paths.

This test exists to make the review path EXPENSIVE TO BREAK and FREE TO KEEP
WORKING. It pins the whole no-model-call surface of `experiments/smoke.yaml` —
config -> composed prompt text -> promptfoo YAML (generation leg), and frozen
per-item records -> metrics/report/spot-check (reduction leg) — byte for byte.
Neither leg spends a cent: the generation leg never runs promptfoo, and the
reduction leg replays call/judge records checked in under `golden/smoke/records/`
instead of calling an executor or a judge.

A golden diff is a BUILD BREAK, not a re-baseline. If a change is genuinely
meant to alter the emitted YAML, prompt text, metrics or report, regenerate with

    PYTHONPATH=. .venv/bin/python harness/tests/test_golden_ablation.py --regen

and say in the commit message WHY the output changed. Regenerating to make a red
test green, without that justification, defeats the entire point of the guard.

Normalisations applied before comparison — deliberately only two, both for
values that cannot be stable across machines or runs:

  <REPO>    The repo root (`harness.config.REPO_ROOT`, derived from this file's
            own location). `gen_promptfoo` embeds it in `file://` provider /
            prompt / assert URLs, in each test's `truth_path`, and inside the
            `judge_json` blob (rubric + schema paths). It differs between any
            two checkouts of the same commit — a worktree, a CI clone, another
            developer's machine — so a golden holding it literally asserts
            "this repo lives at exactly one path on earth". That is not a
            hypothetical: `test_codex_executor.py`'s
            `test_claude_provider_yaml_unchanged_regression` bakes in the
            literal `/Users/wesleyjinks/code/prompts-skills-steering` and
            therefore fails in every other checkout, including this worktree.
  <TMPDIR>  The pytest `tmp_path` the harness is told to write into. It is a
            fresh per-run directory by construction (`pytest-of-<user>/pytest-N/
            <test-name>0`), so it is not merely machine-specific but changes on
            every invocation on one machine.

NOT normalised, on purpose: token counts, USD costs, durations, pass rates,
Wilson bounds, McNemar p, prompt text, task inputs, judge verdicts, the file
set each stage writes, and key order in every emitted document. All of it is
compared literally.

No timestamp normalisation is needed or applied: neither `gen_promptfoo` nor
`report.render` writes a clock value into any file it produces (verified by
reading both modules and by the goldens themselves, which contain no date).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from harness import config, report
from harness.config import REPO_ROOT
from harness.gen_promptfoo import gen_promptfoo
from harness.structured.replay import LoadedRun, replay as replay_structured

CONFIG_PATH = "experiments/smoke.yaml"

GOLDEN = Path(__file__).resolve().parent / "golden" / "smoke"
RECORDS = GOLDEN / "records"
STRUCTURED_GOLDEN = Path(__file__).resolve().parent / "golden" / "structured"
STRUCTURED_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures/structured/results/st-fixture/20260905T120000Z-fixture"
)
STRUCTURED_FILES = ("report.md", "metrics.json")

REPO_PLACEHOLDER = "<REPO>"
TMP_PLACEHOLDER = "<TMPDIR>"

# Everything `gen_promptfoo` writes (harness/gen_promptfoo.py:182-199): one
# prompt file and one promptfoo config per arm in ARMS.
GEN_FILES = (
    "promptfoo-baseline.yaml",
    "promptfoo-treatment.yaml",
    "prompts/baseline.txt",
    "prompts/treatment.txt",
)
# `gen_promptfoo` also mkdirs these two, empty, for the run to fill.
GEN_DIRS = ("calls", "judge", "prompts")

# Everything `report.render` writes (harness/report.py:507-520). The spec's §3
# list names three; the renderer in fact writes four — `spotcheck.md` too — so
# all four are pinned.
REDUCE_FILES = (
    "metrics.json",
    "report.md",
    "spotcheck.md",
    "spotcheck.yaml",
)


def _scrub(text: str, tmp: Path) -> str:
    """Replace the two machine-specific absolute paths with stable placeholders.

    tmp is substituted BEFORE the repo root so that a `--basetemp` pointed
    inside the checkout still normalises to <TMPDIR> rather than half-resolving
    to <REPO>/... first.
    """
    return text.replace(str(tmp), TMP_PLACEHOLDER).replace(str(REPO_ROOT), REPO_PLACEHOLDER)


def _materialize_records(dest: Path) -> None:
    """Copy the frozen calls/ + judge/ record sets into `dest`.

    `calls/*.json` are copied byte for byte — they hold no paths at all. In
    `judge/*.json` the single `truth_path` field is an absolute path to the
    item's `truth.yaml`, which `report.render_spotcheck` actually opens
    (harness/report.py:462 -> harness/judge.py:82). It is stored in the golden
    records as `<REPO>/tasksets/...` and re-pointed at THIS checkout here, so
    the reduction leg reads its ground truth from the tree under test rather
    than from whichever checkout happened to produce the original run.
    """
    shutil.copytree(RECORDS / "calls", dest / "calls")
    (dest / "judge").mkdir()
    for src in sorted((RECORDS / "judge").glob("*.json")):
        text = src.read_text().replace(REPO_PLACEHOLDER, str(REPO_ROOT))
        (dest / "judge" / src.name).write_text(text)


def _assert_matches_golden(rel: str, produced: Path, tmp: Path) -> None:
    got = _scrub(produced.read_text(), tmp)
    want = (GOLDEN / rel).read_text()
    assert got == want, (
        f"{rel} no longer matches its golden. This is a BUILD BREAK: the review "
        f"ablation's output changed. Do not re-baseline to go green — establish "
        f"why the output changed first (see this module's docstring)."
    )


def _materialize_structured_run(dest: Path) -> LoadedRun:
    run_path = dest / "results/st-fixture/20260905T120000Z-fixture"
    shutil.copytree(STRUCTURED_FIXTURE, run_path)
    return LoadedRun.load(run_path)


def _assert_structured_matches_golden(
    name: str, produced_run: Path, golden: Path = STRUCTURED_GOLDEN
) -> None:
    assert (produced_run / name).read_bytes() == (golden / name).read_bytes(), (
        f"{name} no longer matches its structured golden. This is a BUILD BREAK: "
        "establish why the replay output changed before updating the golden."
    )


def test_generation_leg_matches_golden(tmp_path):
    """config -> composed prompts -> both arms' promptfoo YAML, byte-identical."""
    cfg = config.load(CONFIG_PATH)
    out = gen_promptfoo(cfg, tmp_path)

    assert set(out) == {"baseline", "treatment"}
    # The file set itself is part of the contract: a new emitted file, or a
    # dropped one, is a change to the review path even if every pinned file
    # still matches.
    produced = {
        str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file()
    }
    assert produced == set(GEN_FILES)
    assert {p.name for p in tmp_path.iterdir() if p.is_dir()} == set(GEN_DIRS)

    for rel in GEN_FILES:
        _assert_matches_golden(rel, tmp_path / rel, tmp_path)


def test_reduction_leg_matches_golden(tmp_path):
    """frozen calls/ + judge/ -> metrics.json, report.md, spotcheck.*, byte-identical."""
    cfg = config.load(CONFIG_PATH)
    _materialize_records(tmp_path)

    report.render(cfg, tmp_path)

    produced = {p.name for p in tmp_path.iterdir() if p.is_file()}
    assert produced == set(REDUCE_FILES)

    for rel in REDUCE_FILES:
        _assert_matches_golden(rel, tmp_path / rel, tmp_path)


def test_structured_replay_matches_goldens_byte_identically(tmp_path):
    run = _materialize_structured_run(tmp_path)

    result = replay_structured(run.path)

    assert result.executor_calls == 0
    for name in STRUCTURED_FILES:
        _assert_structured_matches_golden(name, run.path)


@pytest.mark.parametrize("name", STRUCTURED_FILES)
def test_structured_golden_perturbation_is_detected(tmp_path, name):
    run = _materialize_structured_run(tmp_path)
    replay_structured(run.path)
    perturbed = tmp_path / "perturbed-structured-golden"
    shutil.copytree(STRUCTURED_GOLDEN, perturbed)
    path = perturbed / name
    path.write_bytes(path.read_bytes() + b"\nperturbed\n")

    with pytest.raises(AssertionError, match="structured golden"):
        _assert_structured_matches_golden(name, run.path, perturbed)


# --------------------------------------------------------------------------- #
# Golden regeneration — never run by pytest (this block is `__main__`-only).
# --------------------------------------------------------------------------- #
def _regen() -> None:
    import tempfile

    src_run = REPO_ROOT / "results" / "smoke" / "weak"
    if not src_run.is_dir():
        raise SystemExit(f"no real smoke run to seed records from: {src_run}")

    # Records: seeded ONCE from the real on-disk run, with truth_path made
    # checkout-relative. Re-seeding them would replace real judged output with
    # whatever is on disk today, so this is skipped if they already exist.
    if not RECORDS.exists():
        (RECORDS / "calls").mkdir(parents=True)
        (RECORDS / "judge").mkdir(parents=True)
        for src in sorted((src_run / "calls").glob("*.json")):
            shutil.copyfile(src, RECORDS / "calls" / src.name)
        for src in sorted((src_run / "judge").glob("*.json")):
            text = src.read_text()
            head, sep, tail = text.partition("/tasksets/")
            if sep:
                # Cut the recorded absolute prefix back to the opening quote and
                # replace it with the placeholder.
                text = head[: head.rindex('"') + 1] + REPO_PLACEHOLDER + sep + tail
            (RECORDS / "judge" / src.name).write_text(text)
        print(f"seeded records from {src_run}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cfg = config.load(CONFIG_PATH)
        gen_promptfoo(cfg, tmp)
        for rel in GEN_FILES:
            dest = GOLDEN / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(_scrub((tmp / rel).read_text(), tmp))
            print(f"wrote {dest.relative_to(REPO_ROOT)}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _materialize_records(tmp)
        report.render(config.load(CONFIG_PATH), tmp)
        for rel in REDUCE_FILES:
            dest = GOLDEN / rel
            dest.write_text(_scrub((tmp / rel).read_text(), tmp))
            print(f"wrote {dest.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    if "--regen" not in sys.argv[1:]:
        raise SystemExit("refusing to regenerate goldens without --regen")
    _regen()
