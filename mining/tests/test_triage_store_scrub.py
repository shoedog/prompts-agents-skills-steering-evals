"""triage_store_scrub marks (never deletes) store rows that the fixed
detectors would no longer emit: sandbox-corpus contamination and lineage
duplicates (sign-off items 2+3, 2026-08-08)."""
import json

import triage_store_scrub as scrub


def make_store(tmp_path, rows):
    store = tmp_path / "triage_evidence.jsonl"
    store.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return store


def make_signatures(tmp_path, fork_pairs):
    sig = tmp_path / "failure_signatures.jsonl"
    rows = [{"corpus": "claude", "detector": "lineage_dupe", "bucket": "lineage_dupe",
             "path": f"~/p/{child}", "session": child.removesuffix(".jsonl"),
             "line_no": 1, "ts": None, "model": None, "cwd": "-p", "sidechain": False,
             "snippet": f"first content line of {child} found at line 3364 of {parent}"}
            for child, parent in fork_pairs]
    sig.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return sig


PARENT = "608a7a2a-cff7-4ddf-bfe5-9cf650c457b0"
FORK = "9aea8b01-4ba8-4372-bfe1-fd229c310b60"


def base_rows():
    return [
        {"key": f"failure|claude.refutation|{PARENT[:24]}|L3724", "source": "failure",
         "class": "claude.refutation", "ts": "2026-07-22T19:32",
         "session": PARENT[:24], "line": 3724,
         "row": f"- [ ] 2026-07-22T19:32 `{PARENT[:24]}` L3724 (m @ /Users/x/code/ssot): refuted",
         "first_seen": "2026-08-01"},
        {"key": f"failure|claude.refutation|{FORK[:24]}|L289", "source": "failure",
         "class": "claude.refutation", "ts": "2026-07-22T19:32",
         "session": FORK[:24], "line": 289,
         "row": f"- [ ] 2026-07-22T19:32 `{FORK[:24]}` L289 (m @ /Users/x/code/ssot): refuted",
         "first_seen": "2026-08-01"},
        {"key": "failure|claude.user_correction|sandbox01|L5", "source": "failure",
         "class": "claude.user_correction", "ts": "2026-08-02T01:00",
         "session": "sandbox01", "line": 5,
         # the sandbox cwd must lie under THIS checkout's results/ dir (that is
         # what scrub matches on), so build it from the module constant rather
         # than a developer's absolute path
         "row": "- [ ] 2026-08-02T01:00 `sandbox01` L5 (m @ "
                f"{scrub.REPO_RESULTS_DIR}exp-w3a-cite-or-label/sandbox/treatment-mc-01): "
                "re-read the diff",
         "first_seen": "2026-08-02"},
        {"key": "failure|claude.admission|clean01|L7", "source": "failure",
         "class": "claude.admission", "ts": "2026-08-03T01:00",
         "session": "clean01", "line": 7,
         "row": "- [ ] 2026-08-03T01:00 `clean01` L7 (m @ /Users/x/code/proj): I was wrong",
         "first_seen": "2026-08-03"},
    ]


def test_scrub_marks_sandbox_and_lineage_rows(tmp_path):
    store = make_store(tmp_path, base_rows())
    sig = make_signatures(tmp_path, [(f"{FORK}.jsonl", f"{PARENT}.jsonl")])
    n = scrub.scrub(store, sig)
    assert n == 2
    rows = {r["key"]: r for r in map(json.loads, store.read_text().splitlines())}
    assert len(rows) == 4  # nothing deleted
    assert rows[f"failure|claude.refutation|{FORK[:24]}|L289"]["excluded"] == "lineage-dupe"
    assert rows[f"failure|claude.refutation|{FORK[:24]}|L289"]["dupe_of"] == \
        f"failure|claude.refutation|{PARENT[:24]}|L3724"
    # the parent copy and clean rows stay unmarked
    assert "excluded" not in rows[f"failure|claude.refutation|{PARENT[:24]}|L3724"]
    assert rows["failure|claude.user_correction|sandbox01|L5"]["excluded"] == "sandbox-corpus"
    assert "excluded" not in rows["failure|claude.admission|clean01|L7"]


def test_scrub_is_idempotent(tmp_path):
    store = make_store(tmp_path, base_rows())
    sig = make_signatures(tmp_path, [(f"{FORK}.jsonl", f"{PARENT}.jsonl")])
    assert scrub.scrub(store, sig) == 2
    assert scrub.scrub(store, sig) == 0


def test_scrub_without_matching_parent_leaves_row_alone(tmp_path):
    # A fork row with no same-(class, ts) parent row is NOT provably a copy.
    rows = [r for r in base_rows() if PARENT[:24] not in r["key"]]
    store = make_store(tmp_path, rows)
    sig = make_signatures(tmp_path, [(f"{FORK}.jsonl", f"{PARENT}.jsonl")])
    n = scrub.scrub(store, sig)
    assert n == 1  # only the sandbox row
    kept = {r["key"]: r for r in map(json.loads, store.read_text().splitlines())}
    assert "excluded" not in kept[f"failure|claude.refutation|{FORK[:24]}|L289"]
