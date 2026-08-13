#!/usr/bin/env python3
"""Validate exact runner nounset ordering and compile-failure core evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/server_runner_return_resilience_v1.schema.json"
VAR_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
ASSIGN_RE = re.compile(
    r"^\s*(?:(?:export|readonly|local|declare)(?:\s+-[A-Za-z]+)?\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*="
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_contract(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    try:
        import jsonschema

        jsonschema.validate(value, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    except ImportError:
        pass
    return value


def _first_token_line(lines: list[str], tokens: list[str]) -> int | None:
    return next(
        (index for index, line in enumerate(lines, 1) if any(token in line for token in tokens)),
        None,
    )


def validate_runner(contract: dict[str, Any], runner: bytes) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    text = runner.decode("utf-8", errors="replace")
    lines = text.splitlines()
    actual_sha = sha256_bytes(runner)
    if actual_sha != contract.get("runner_sha256"):
        errors.append("exact runner sha256 mismatch")
    if not re.search(r"(?:set\s+[^\n]*u|set\s+-o\s+nounset)", text):
        errors.append("exact runner does not enable nounset")

    variables = contract.get("package_owned_variables", [])
    first_definition: dict[str, int] = {}
    unsafe_uses: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        assignment = ASSIGN_RE.match(line)
        assigned_name = assignment.group(1) if assignment else None
        for match in VAR_RE.finditer(line):
            name = match.group(1) or match.group(3)
            suffix = match.group(2) or ""
            if name not in variables:
                continue
            if suffix.startswith((":-", ":=", "-", "=")):
                continue
            if name not in first_definition:
                unsafe_uses.append(
                    {"variable": name, "line": line_number, "source": line.strip()}
                )
        if assigned_name in variables and assigned_name not in first_definition:
            first_definition[assigned_name] = line_number

    for item in unsafe_uses:
        errors.append(
            f"definition-before-use: {item['variable']} first unsafe expansion at line {item['line']}"
        )
    for name in variables:
        if name not in first_definition:
            errors.append(f"package-owned variable has no assignment: {name}")

    bootstrap = contract.get("bootstrap_root_variable")
    bootstrap_line = first_definition.get(bootstrap)
    fallible_line = _first_token_line(lines, contract.get("first_fallible_tokens", []))
    arm_line = _first_token_line(lines, contract.get("finalizer_arm_tokens", []))
    if bootstrap_line is None:
        errors.append("bootstrap root is not assigned")
    elif fallible_line is not None and bootstrap_line >= fallible_line:
        errors.append("bootstrap root is assigned after first fallible action")
    if arm_line is None:
        errors.append("finalizer arm token is absent")
    elif fallible_line is not None and arm_line >= fallible_line:
        errors.append("finalizer is armed after first fallible action")

    evidence = contract.get("compile_evidence_tokens", {})
    for key, token in evidence.items():
        if token not in text:
            errors.append(f"compile evidence token absent: {key}={token}")
    for token in contract.get("return_allowlist_tokens", []):
        if token not in text:
            errors.append(f"return allowlist token absent from exact runner: {token}")

    bootstrap_tokens = [
        evidence.get("argv", ""),
        evidence.get("source_identity", ""),
        evidence.get("exit_code", ""),
        evidence.get("driver_log", ""),
        evidence.get("first_error", ""),
    ]
    for token in filter(None, bootstrap_tokens):
        token_line = _first_token_line(lines, [token])
        if bootstrap_line is not None and token_line is not None:
            source = lines[token_line - 1]
            if f"${bootstrap}" not in source and f"${{{bootstrap}}}" not in source:
                errors.append(f"compile evidence is not bootstrap-rooted: {token}")

    return {
        "schema": "server-runner-return-resilience-validation-v1",
        "package_id": contract.get("package_id"),
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "runner": {
            "path": contract.get("runner_path"),
            "bytes": len(runner),
            "sha256": actual_sha,
            "nounset": bool(re.search(r"(?:set\s+[^\n]*u|set\s+-o\s+nounset)", text)),
        },
        "definition_before_use": {
            "first_definition_lines": first_definition,
            "unsafe_uses": unsafe_uses,
        },
        "bootstrap": {
            "variable": bootstrap,
            "assignment_line": bootstrap_line,
            "finalizer_arm_line": arm_line,
            "first_fallible_line": fallible_line,
        },
        "causal_mapping": ["server_start", "return"],
        "claim_boundary": "Static exact-runner/core-return contract only; no production compile, simulation, E4/E5 or server claim.",
    }


def validate_tree(root: Path, contract_path: Path) -> dict[str, Any]:
    contract = _load_contract(contract_path.read_bytes())
    runner_path = (root / contract["runner_path"]).resolve()
    runner_path.relative_to(root.resolve())
    return validate_runner(contract, runner_path.read_bytes())


def validate_zip(zip_path: Path, contract_member: str) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if contract_member not in names:
            raise ValueError(f"contract member absent: {contract_member}")
        contract = _load_contract(archive.read(contract_member))
        base = PurePosixPath(contract_member).parent
        runner_member = (base / contract["runner_path"]).as_posix()
        if runner_member not in names:
            runner_member = contract["runner_path"]
        if runner_member not in names:
            raise ValueError(f"runner member absent: {runner_member}")
        report = validate_runner(contract, archive.read(runner_member))
        report["zip"] = {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": sha256_bytes(zip_path.read_bytes()),
            "contract_member": contract_member,
            "runner_member": runner_member,
        }
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    tree = sub.add_parser("validate-tree")
    tree.add_argument("--root", required=True, type=Path)
    tree.add_argument("--contract", required=True, type=Path)
    final_zip = sub.add_parser("validate-final-zip")
    final_zip.add_argument("--zip", required=True, type=Path)
    final_zip.add_argument("--contract-member", required=True)
    for command in (tree, final_zip):
        command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate-tree":
            report = validate_tree(args.root, args.contract)
        else:
            report = validate_zip(args.zip, args.contract_member)
    except Exception as exc:
        report = {
            "schema": "server-runner-return-resilience-validation-v1",
            "pass": False,
            "errors": [str(exc)],
            "warnings": [],
            "causal_mapping": ["server_start", "return"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report.get("pass") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

