#!/usr/bin/env python3
"""Bridge the shared JSON-only post-sim core to the frozen QAdd analyzer.

The shared core deliberately expands only package/attempt/execution identity.
Compile and simulation status therefore come from the immutable evidence files
written by the runner before plugins execute, rather than from unsupported
argv placeholders or inherited environment state.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def read_status(path: Path) -> int:
    text = path.read_text(encoding="ascii").strip()
    value = int(text)
    if value < 0 or value > 255:
        raise ValueError(f"status outside byte range: {path}: {value}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--attempt-root", required=True, type=Path)
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    attempt_root = args.attempt_root.resolve()
    evidence_root = attempt_root / "evidence"
    compile_status = read_status(evidence_root / "compile_exit_status.txt")
    simulation_status = read_status(evidence_root / "simulation_exit_status.txt")
    analyzer = (
        package_root
        / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
    )
    command = [
        sys.executable,
        str(analyzer),
        "analyze",
        "--package-root",
        str(package_root),
        "--evidence-root",
        str(evidence_root),
        "--run-root",
        str(attempt_root),
        "--compile-status",
        str(compile_status),
        "--simulation-status",
        str(simulation_status),
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
