#!/usr/bin/env python3
"""Validate the exact self-described operator server-root command."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--server-root", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        readme_data = archive.read(f"{args.package_id}/README.md")
        runner_data = archive.read(f"{args.package_id}/PREPARE_AND_RUN.sh")
    readme = readme_data.decode("utf-8")
    runner = runner_data.decode("utf-8")
    expected = f"bash PREPARE_AND_RUN.sh {args.server_root}"
    wrong_parent = "bash PREPARE_AND_RUN.sh /home/panqs/ndp\n"
    checks = {
        "exact_command_once": readme.count(expected) == 1,
        "parent_root_command_absent": wrong_parent not in readme,
        "runner_requires_exactly_one_server_root": 'if [ "$#" -ne 1 ]; then' in runner,
        "runner_requires_absolute_server_root": 'server_root must be absolute' in runner,
        "runner_resolves_argument": 'server_root="$(cd "$1"' in runner,
    }
    errors = [name for name, passed in checks.items() if not passed]
    negative_control = readme.replace(expected, "bash PREPARE_AND_RUN.sh /home/panqs/ndp", 1)
    negative_rejected = expected not in negative_control and wrong_parent in negative_control
    if not negative_rejected:
        errors.append("negative_parent_root_control_not_rejected")
    report = {
        "schema": "node0004-fsdb-smoke-operator-command-gate-v1",
        "package_id": args.package_id,
        "pass": not errors,
        "errors": errors,
        "expected_command": expected,
        "server_root": args.server_root,
        "checks": checks,
        "negative_parent_root_control_rejected": negative_rejected,
        "readme": {"bytes": len(readme_data), "sha256": sha(readme_data)},
        "runner": {"bytes": len(runner_data), "sha256": sha(runner_data)},
        "claim_boundary": "Exact package self-description and runner argument binding only; no server filesystem existence or execution claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
