#!/usr/bin/env python3
"""Validate next-fresh observer operational-boundary package and return surfaces."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = Path(__file__).resolve().with_name("server_observer_operational_attempt_boundary.py")
GUARD_RUNTIME_PATH = Path(__file__).resolve().with_name("server_observer_operational_guard_v2.py")
SPEC = importlib.util.spec_from_file_location("observer_operational_runtime", RUNTIME_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load operational runtime")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)
GUARD_SPEC = importlib.util.spec_from_file_location("observer_operational_guard_v2_validation", GUARD_RUNTIME_PATH)
if GUARD_SPEC is None or GUARD_SPEC.loader is None:
    raise RuntimeError("cannot load operational guard v2")
GUARD_RUNTIME = importlib.util.module_from_spec(GUARD_SPEC)
GUARD_SPEC.loader.exec_module(GUARD_RUNTIME)

REPORT_SCHEMA = "server-observer-operational-attempt-boundary-validation-v1"
CONTRACT_MEMBER = "contracts/observer_operational_attempt_boundary.json"
HELPER_MEMBER = "package_tools/server_observer_operational_attempt_boundary.py"
GUARD_HELPER_MEMBER = "package_tools/server_observer_operational_guard_v2.py"
GUARD_RECEIPT_SCHEMA_MEMBER = "schemas/server_observer_operational_guard_receipt_v2.schema.json"
GUARD_POLICY_SCHEMA_MEMBER = "schemas/server_observer_operational_live_tree_policy_v2.schema.json"
REQUIRED_RETURN_MEMBERS = (
    "OPERATIONAL_PREFLIGHT_RECEIPT.json",
    "OPERATIONAL_PHASE_SAMPLES.jsonl",
    "OPERATIONAL_STOP_RECEIPT.json",
    "DURABLE_RETURN_RECEIPT.json",
    "POST_DURABLE_CLEANUP_RECEIPT.json",
    "OPERATIONAL_GUARD_STDERR.log",
)
RUNNER_TOKENS = (
    "server_observer_operational_attempt_boundary.py preflight",
    "supervise-phase --phase compile",
    "supervise-phase --phase simulation",
    "supervise-phase --phase finalization",
    "cleanup-after-durable-return",
    "--execution-id",
    "--attempt-id",
    "--guard-log",
)
FORBIDDEN_RUNNER = (
    re.compile(r"\bhead\s+-c\b"), re.compile(r"\btail\s+-c\b"),
    re.compile(r"\btruncate\b"), re.compile(r"\bsplit\s+-b\b"),
    re.compile(r"\b(?:rm|del)\b[^\n]*(?:observer|events|chunks)", re.IGNORECASE),
)


class ValidationError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        if name.startswith("/") or "\\" in name or ".." in pure.parts or name in seen:
            raise ValidationError(f"unsafe or duplicate ZIP member: {name}")
        seen.add(name)
        names.append(name)
    return names


def single_root(names: list[str]) -> str:
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if len(roots) != 1:
        raise ValidationError(f"exact ZIP must have one package root, found {sorted(roots)}")
    return next(iter(roots))


def validate_contract(contract: Any) -> dict[str, Any]:
    report = RUNTIME.validate_contract(contract)
    return {
        "schema": REPORT_SCHEMA,
        "phase": "contract",
        "package_id": contract.get("package_id") if isinstance(contract, dict) else None,
        "errors": report["errors"],
        "pass": report["pass"],
        "claim_boundary": "Operational attempt safety only; no DUT result claim.",
    }


def validate_final_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    contract: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = safe_names(archive)
            root = single_root(names)
            contract_name = f"{root}/{CONTRACT_MEMBER}"
            helper_name = f"{root}/{HELPER_MEMBER}"
            guard_helper_name = f"{root}/{GUARD_HELPER_MEMBER}"
            guard_receipt_schema_name = f"{root}/{GUARD_RECEIPT_SCHEMA_MEMBER}"
            guard_policy_schema_name = f"{root}/{GUARD_POLICY_SCHEMA_MEMBER}"
            runner_name = f"{root}/PREPARE_AND_RUN.sh"
            allow_name = f"{root}/RETURN_ALLOWLIST.json"
            for name in (
                contract_name, helper_name, guard_helper_name, guard_receipt_schema_name,
                guard_policy_schema_name, runner_name, allow_name,
            ):
                if name not in names:
                    errors.append(f"required operational package member is absent: {name}")
            if contract_name in names:
                try:
                    raw = archive.read(contract_name)
                    contract = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid embedded operational contract: {exc}")
                else:
                    if raw != canonical_bytes(contract):
                        errors.append("embedded operational contract is not canonical JSON")
                    errors.extend(RUNTIME.validate_contract(contract)["errors"])
                    if contract.get("package_id") != root:
                        errors.append("operational contract package_id must match exact ZIP root")
                    source = contract.get("threshold_source", {})
                    source_name = f"{root}/{source.get('path', '')}"
                    if source_name not in names:
                        errors.append("threshold source receipt is absent from exact ZIP")
                    elif sha256_bytes(archive.read(source_name)) != source.get("sha256"):
                        errors.append("threshold source receipt SHA does not match contract")
                    policy = contract.get("live_tree_policy", {})
                    policy_name = f"{root}/{policy.get('path', '')}"
                    if policy_name not in names:
                        errors.append("content-bound live-tree policy v2 is absent from exact ZIP")
                    else:
                        policy_bytes = archive.read(policy_name)
                        if sha256_bytes(policy_bytes) != policy.get("sha256"):
                            errors.append("live-tree policy SHA does not match contract")
                        try:
                            policy_document = json.loads(policy_bytes.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                            errors.append(f"invalid live-tree policy JSON: {exc}")
                        else:
                            expected_policy = json.loads((ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_live_tree_policy.json").read_text(encoding="utf-8"))
                            if policy_document != expected_policy:
                                errors.append("live-tree policy differs from canonical v2 policy")
            if helper_name in names and archive.read(helper_name) != RUNTIME_PATH.read_bytes():
                errors.append("packaged operational helper is not byte-exact canonical runtime")
            if guard_helper_name in names and archive.read(guard_helper_name) != GUARD_RUNTIME_PATH.read_bytes():
                errors.append("packaged operational guard v2 is not byte-exact canonical runtime")
            schema_pairs = (
                (guard_receipt_schema_name, ROOT / GUARD_RECEIPT_SCHEMA_MEMBER),
                (guard_policy_schema_name, ROOT / GUARD_POLICY_SCHEMA_MEMBER),
            )
            for packaged_name, canonical_path in schema_pairs:
                if packaged_name in names and archive.read(packaged_name) != canonical_path.read_bytes():
                    errors.append(f"packaged operational v2 schema drift: {packaged_name}")
            if runner_name in names:
                runner = archive.read(runner_name).decode("utf-8", errors="replace")
                for token in RUNNER_TOKENS:
                    if token not in runner:
                        errors.append(f"runner lacks operational lifecycle token: {token}")
                for pattern in FORBIDDEN_RUNNER:
                    if pattern.search(runner):
                        errors.append(f"runner contains evidence truncation/deletion mechanism: {pattern.pattern}")
                if runner.find("cleanup-after-durable-return") < runner.find("DURABLE_RETURN_RECEIPT"):
                    errors.append("runner cleanup is not ordered after durable return receipt")
            if allow_name in names:
                try:
                    allow = json.loads(archive.read(allow_name).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid return allowlist: {exc}")
                else:
                    blob = json.dumps(allow, sort_keys=True)
                    for member in REQUIRED_RETURN_MEMBERS:
                        if member not in blob:
                            errors.append(f"return allowlist lacks operational receipt: {member}")
    except (OSError, zipfile.BadZipFile, ValidationError) as exc:
        errors.append(str(exc))
    return {
        "schema": REPORT_SCHEMA,
        "phase": "final_zip",
        "package_id": contract.get("package_id"),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "sha256": sha256_bytes(zip_path.read_bytes()) if zip_path.exists() else None,
        },
        "errors": sorted(set(errors)),
        "warnings": warnings,
        "pass": not errors,
        "claim_boundary": "Exact final-ZIP operational safety only; no production execution or DUT claim.",
    }


def read_json_member(archive: zipfile.ZipFile, name: str, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid required return member {name}: {exc}")
        return {}


def validate_return(zip_path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors = list(RUNTIME.validate_contract(contract)["errors"])
    stopped = False
    diagnostic_status = "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = safe_names(archive)
            stop_name = next((name for name in names if name.endswith("/OPERATIONAL_STOP_RECEIPT.json") or name == "OPERATIONAL_STOP_RECEIPT.json"), None)
            if stop_name is None:
                errors.append("operational stop receipt is absent")
            else:
                receipt = read_json_member(archive, stop_name, errors)
                receipt_report = (
                    GUARD_RUNTIME.validate_receipt(receipt)
                    if receipt.get("schema") == GUARD_RUNTIME.SCHEMA
                    else RUNTIME.validate_receipt(receipt)
                )
                errors.extend(receipt_report["errors"])
                stopped = receipt.get("stop_count") == 1
                diagnostic_status = receipt.get("diagnostic_status")
                if stopped:
                    if not any(name.endswith("PARTIAL_EXIT.json") or name.endswith("PARTIAL_EXIT.jsonl") for name in names):
                        errors.append("operationally stopped return lacks live PARTIAL_EXIT marker")
                    if diagnostic_status != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
                        errors.append("operationally stopped return was upgraded above DIAGNOSTIC_EVIDENCE_INCOMPLETE")
            compile_core_name = next((name for name in names if name.endswith("/COMPILE_CORE.json") or name == "COMPILE_CORE.json"), None)
            if compile_core_name is not None:
                compile_core = read_json_member(archive, compile_core_name, errors)
                compile_exit = compile_core.get("compile_exit", compile_core.get("exit"))
                if compile_exit == 2 and stop_name is None:
                    errors.append("exit 2 without guard receipt is GUARD_RECEIPT_MISSING_INFRASTRUCTURE_FAILURE, not production compile error")
            durable_name = next((name for name in names if name.endswith("/DURABLE_RETURN_RECEIPT.json") or name == "DURABLE_RETURN_RECEIPT.json"), None)
            if durable_name is None:
                errors.append("durable return receipt is absent")
            else:
                durable = read_json_member(archive, durable_name, errors)
                for key in ("zip_crc_verified", "exact_member_set_verified", "sidecar_bytes_sha256_verified", "atomic_unique_publication"):
                    if durable.get(key) is not True:
                        errors.append(f"durable return receipt lacks {key}")
    except (OSError, zipfile.BadZipFile, ValidationError) as exc:
        errors.append(str(exc))
    return {
        "schema": REPORT_SCHEMA,
        "phase": "return",
        "package_id": contract.get("package_id"),
        "operationally_stopped": stopped,
        "diagnostic_status": diagnostic_status,
        "errors": sorted(set(errors)),
        "pass": not errors,
        "claim_boundary": "Operational return completeness only; no natural terminal, formal-D, E4 or E5 claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    contract_parser = sub.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)
    zip_parser = sub.add_parser("validate-final-zip")
    zip_parser.add_argument("--zip", type=Path, required=True)
    return_parser = sub.add_parser("validate-return")
    return_parser.add_argument("--zip", type=Path, required=True)
    return_parser.add_argument("--contract", type=Path, required=True)
    for item in (contract_parser, zip_parser, return_parser):
        item.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "validate-contract":
        report = validate_contract(json.loads(args.contract.read_text(encoding="utf-8")))
    elif args.command == "validate-final-zip":
        report = validate_final_zip(args.zip)
    else:
        report = validate_return(args.zip, json.loads(args.contract.read_text(encoding="utf-8")))
    payload = canonical_bytes(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    else:
        sys.stdout.buffer.write(payload)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
