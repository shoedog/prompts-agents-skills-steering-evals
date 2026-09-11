"""Increment the held-out consultation counter selected by an eval config."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def increment(config_path: Path) -> Path:
    config = yaml.safe_load(config_path.read_text())
    if not isinstance(config, dict) or not isinstance(config.get("taskset"), str):
        raise ValueError("config taskset must be a path string")
    taskset = Path(config["taskset"])
    if not taskset.is_absolute():
        taskset = Path.cwd() / taskset
    manifest_path = taskset / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    try:
        consulted = manifest["splits"]["test"]["consulted"]
    except (KeyError, TypeError) as error:
        raise ValueError("manifest must declare splits.test.consulted") from error
    if not isinstance(consulted, int) or isinstance(consulted, bool) or consulted < 0:
        raise ValueError("splits.test.consulted must be a nonnegative integer")
    manifest["splits"]["test"]["consulted"] = consulted + 1
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    print(manifest_path)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    increment(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
