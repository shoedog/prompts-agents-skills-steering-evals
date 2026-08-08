"""triage_delta must exclude scrubbed store rows from tallies while still
using their keys to suppress resurfacing (sign-off item 2, 2026-08-08)."""
import json

import triage_delta as td


NOMS = """# Failure-signature triage queue

## claude.admission — 3 total, showing 2

- [ ] 2026-08-08T09:00 `s3` L10 (m @ /x): fresh admission today
- [ ] 2026-07-22T19:32 `s2` L289 (m @ /x): copied admission (already scrubbed)
"""

STORE_ROWS = [
    # counted: clean prior evidence
    {"key": "failure|claude.admission|s1|L100", "source": "failure",
     "class": "claude.admission", "ts": "2026-07-20T10:00", "session": "s1",
     "line": 100, "row": "- [ ] 2026-07-20T10:00 `s1` L100 (m @ /x): earlier admission",
     "first_seen": "2026-07-21"},
    # scrubbed lineage dupe: must not count, must still suppress resurfacing
    {"key": "failure|claude.admission|s2|L289", "source": "failure",
     "class": "claude.admission", "ts": "2026-07-22T19:32", "session": "s2",
     "line": 289, "row": "- [ ] 2026-07-22T19:32 `s2` L289 (m @ /x): copied admission (already scrubbed)",
     "first_seen": "2026-07-23", "excluded": "lineage-dupe",
     "dupe_of": "failure|claude.admission|s1|L100"},
]


def run_delta(tmp_path, monkeypatch):
    store = tmp_path / "triage_evidence.jsonl"
    store.write_text("\n".join(json.dumps(r) for r in STORE_ROWS) + "\n")
    noms = tmp_path / "failure_nominations.md"
    noms.write_text(NOMS)
    inbox = tmp_path / "triage-inbox.md"
    monkeypatch.setattr(td, "SOURCES", {"failure": noms})
    monkeypatch.setattr(td, "STORE", store)
    monkeypatch.setattr(td, "INBOX", inbox)
    td.main()
    return store, inbox


def test_excluded_rows_do_not_count_but_still_suppress(tmp_path, monkeypatch):
    store, inbox = run_delta(tmp_path, monkeypatch)
    text = inbox.read_text()
    # Only the fresh s3 row is new; the scrubbed s2 row must not resurface.
    assert "fresh admission today" in text
    assert text.count("copied admission") == 0
    # Tally counts s1 (clean, prior) + s3 (new) = 2 across 2 sessions — NOT 3/3.
    assert "+1 new · 2 in store across 2 sessions" in text
    # The scrubbed row stays in the store (key retention), still marked.
    kept = [json.loads(l) for l in store.read_text().splitlines()]
    assert any(r.get("excluded") == "lineage-dupe" for r in kept)
