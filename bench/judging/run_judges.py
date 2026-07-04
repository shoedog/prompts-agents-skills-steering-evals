"""Dual-family blind judging over the reference-run pairs.

For each task dir under bench/judging/ containing brief.md + schema.json:
  - codex judge:  gpt-5.5 xhigh via harness.providers.codex_cli.run_codex
                  (read-only sandbox, fresh cwd, --output-schema)
  - claude judge: `claude -p --model claude-sonnet-5 --output-format json`,
                  strict-JSON instruction, lenient extraction + one retry

Writes verdict-codex.json / verdict-claude.json per task (skips ones that
already exist, so the script is re-runnable after partial failures).
Verdicts are validated against the task's schema (required keys present).
"""
import json
import pathlib
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from harness.providers.codex_cli import run_codex  # noqa: E402

J = pathlib.Path(__file__).parent
CLAUDE_JSON_SUFFIX = (
    "\n\n## Output format\nRespond with ONLY a single JSON object matching this JSON Schema "
    "(no prose, no code fences):\n\n{schema}\n"
)


def required_keys_ok(obj: dict, schema: dict) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in schema.get("required", []))


def extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in output")
    return json.loads(m.group(0))


def judge_codex(task_dir: pathlib.Path) -> str:
    out = task_dir / "verdict-codex.json"
    if out.exists():
        return f"{task_dir.name}/codex: cached"
    brief = (task_dir / "brief.md").read_text()
    schema = json.loads((task_dir / "schema.json").read_text())
    last_err = None
    for attempt in (1, 2):
        try:
            # absolute schema path: codex runs in an isolated cwd. That cwd
            # must be a git repo (codex trust check) but stays OUTSIDE this
            # repo so the judge can't stumble on key.json/unblinded files.
            scratch = pathlib.Path("/private/tmp/fable-judge-scratch") / task_dir.name
            scratch.mkdir(parents=True, exist_ok=True)
            if not (scratch / ".git").exists():
                subprocess.run(["git", "init", "-q", str(scratch)], check=True)
            r = run_codex(brief, schema_path=str((task_dir / "schema.json").resolve()),
                          effort="xhigh", timeout=1500, cwd=str(scratch))
            obj = extract_json(r["output"])
            if not required_keys_ok(obj, schema):
                raise ValueError(f"missing required keys: {obj.keys()}")
            out.write_text(json.dumps({"verdict": obj, "tokens_used": r.get("tokens_used")}, indent=1))
            return f"{task_dir.name}/codex: ok (attempt {attempt})"
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(5)
    (task_dir / "verdict-codex.ERROR").write_text(str(last_err))
    return f"{task_dir.name}/codex: ERROR {last_err}"


def judge_claude(task_dir: pathlib.Path) -> str:
    out = task_dir / "verdict-claude.json"
    if out.exists():
        return f"{task_dir.name}/claude: cached"
    schema_text = (task_dir / "schema.json").read_text()
    schema = json.loads(schema_text)
    prompt = (task_dir / "brief.md").read_text() + CLAUDE_JSON_SUFFIX.format(schema=schema_text)
    last_err = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                ["claude", "-p", prompt, "--model", "claude-sonnet-5",
                 "--output-format", "json", "--dangerously-skip-permissions"],
                capture_output=True, text=True, timeout=900,
                cwd=str(task_dir),  # judge cwd isolation: only the brief dir
            )
            if proc.returncode != 0:
                raise RuntimeError(f"claude rc {proc.returncode}: {proc.stderr[-300:]}")
            cli = json.loads(proc.stdout)
            obj = extract_json(cli.get("result", ""))
            if not required_keys_ok(obj, schema):
                raise ValueError(f"missing required keys: {obj.keys()}")
            out.write_text(json.dumps(
                {"verdict": obj, "cost_usd": cli.get("total_cost_usd")}, indent=1))
            return f"{task_dir.name}/claude: ok (attempt {attempt})"
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(5)
    (task_dir / "verdict-claude.ERROR").write_text(str(last_err))
    return f"{task_dir.name}/claude: ERROR {last_err}"


def main():
    tasks = sorted(d for d in J.iterdir() if d.is_dir() and (d / "brief.md").exists())
    jobs = [(judge_codex, d) for d in tasks] + [(judge_claude, d) for d in tasks]
    print(f"[judges] {len(tasks)} tasks x 2 judges = {len(jobs)} calls", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for msg in pool.map(lambda j: j[0](j[1]), jobs):
            print("[judges]", msg, flush=True)
    errors = list(J.glob("*/verdict-*.ERROR"))
    print(f"[judges] done; {len(errors)} errors: {[str(e) for e in errors]}", flush=True)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
