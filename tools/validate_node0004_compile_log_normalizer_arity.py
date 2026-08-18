#!/usr/bin/env python3
"""Validate the exact runner normalizer arity and its 6-to-5 negative."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import zipfile
from pathlib import Path, PurePosixPath


SCHEMA = "node0004-compile-log-normalizer-arity-validation-v1"
BLOCK = re.compile(
    r"python3 - (?P<args>[^\n]+?) <<'PY'\n"
    r"import pathlib,re,sys\n"
    r"(?P<body>.*?)\nPY",
    re.S,
)
UNPACK = re.compile(
    r"(?P<targets>[A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)"
    r"\s*=\s*map\(pathlib\.Path,sys\.argv\[1:\]\)"
)


def check_runner(text: str) -> dict[str, object]:
    errors: list[str] = []
    matches = list(BLOCK.finditer(text))
    if len(matches) != 1:
        errors.append(f"normalizer block count must be 1, observed {len(matches)}")
        return {"pass": False, "errors": errors, "argument_count": None, "target_count": None}
    match = matches[0]
    try:
        arguments = shlex.split(match.group("args"))
    except ValueError as error:
        errors.append(f"normalizer arguments are not shell-lexable: {error}")
        arguments = []
    unpack = UNPACK.search(match.group("body"))
    targets = (
        [item.strip() for item in unpack.group("targets").split(",")]
        if unpack
        else []
    )
    if not unpack:
        errors.append("normalizer path unpack is absent")
    if len(arguments) != len(targets):
        errors.append(f"normalizer argument/target mismatch: {len(arguments)} != {len(targets)}")
    expected_arguments = [
        "$compile_log", "$compile_driver_log", "$compile_first_error_txt",
        "$compile_log_head_txt", "$compile_log_tail_txt",
    ]
    if arguments != expected_arguments:
        errors.append(f"normalizer exact argument sequence differs: {arguments}")
    if targets != ["s", "d", "f", "h", "t"]:
        errors.append(f"normalizer exact target sequence differs: {targets}")
    if 'compile_log="$compile_full_log"' not in text:
        errors.append("complete compile log alias is absent")
    return {
        "pass": not errors,
        "errors": errors,
        "arguments": arguments,
        "targets": targets,
        "argument_count": len(arguments),
        "target_count": len(targets),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failure")
        roots = {
            PurePosixPath(name).parts[0]
            for name in archive.namelist()
            if PurePosixPath(name).parts
        }
        if len(roots) != 1:
            errors.append(f"single package root required: {sorted(roots)}")
            package_id = ""
            runner = ""
            contract = {}
        else:
            package_id = next(iter(roots))
            runner = archive.read(f"{package_id}/PREPARE_AND_RUN.sh").decode("utf-8")
            contract = json.loads(
                archive.read(
                    f"{package_id}/contracts/compile_log_normalizer_arity_contract.json"
                ).decode("utf-8")
            )
    positive = check_runner(runner)
    defective = runner.replace(
        '"$compile_log_tail_txt" <<\'PY\'',
        '"$compile_log_tail_txt" "$compile_full_log" <<\'PY\'',
        1,
    )
    negative = check_runner(defective)
    checks = {
        "contract_package_identity": contract.get("package_id") == package_id,
        "contract_exact_five_inputs": len(contract.get("input_paths", [])) == 5,
        "contract_exact_five_targets": len(contract.get("python_unpack_targets", [])) == 5,
        "contract_duplicate_absent": contract.get("duplicate_compile_full_log_argument") is False,
        "positive_exact_runner_passes": positive.get("pass") is True,
        "six_to_five_negative_rejected": (
            negative.get("pass") is False
            and any("6 != 5" in item for item in negative.get("errors", []))
        ),
    }
    errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": SCHEMA,
        "package_id": package_id,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "positive": positive,
        "negative_six_arguments_five_targets": negative,
        "zip": {
            "path": str(args.zip),
            "bytes": args.zip.stat().st_size,
            "sha256": hashlib.sha256(args.zip.read_bytes()).hexdigest(),
        },
        "claim_boundary": "Exact package-local normalizer arity only; no production compile, simulation or DUT claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
