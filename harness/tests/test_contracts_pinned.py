import hashlib, json
from pathlib import Path
import pytest
REPO = Path(__file__).resolve().parents[2]
TOOLS = Path.home() / "code" / "tools" / "contracts"
PINNED = {"classify_error_handling.schema.json": "dd66c9a202cbc3fb3b544ea885407b4e041263edb5c7ea34d54b31f4ee9d505b"}

def test_classify_schema_sha_is_pinned():
    for name, sha in PINNED.items():
        assert hashlib.sha256((REPO / "contracts" / name).read_bytes()).hexdigest() == sha

@pytest.mark.skipif(not TOOLS.is_dir(), reason="upstream contracts directory not present")
def test_classify_request_subschema_equals_tools():
    ours = json.loads((REPO / "contracts/classify_error_handling.schema.json").read_text())["$defs"]["request"]
    tools = json.loads((TOOLS / "classify_error_handling.schema.json").read_text())["$defs"]["request"]
    assert json.dumps(ours, sort_keys=True) == json.dumps(tools, sort_keys=True)
