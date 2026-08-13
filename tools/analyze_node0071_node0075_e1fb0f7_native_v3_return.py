#!/usr/bin/env python3
"""Validate and adjudicate the formal node0071 -> node0075 v3 return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_e1f_native_v3.zip"
)
SOURCE_SIDECAR = Path(str(SOURCE_ZIP) + ".sha256")
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-ordering-v3-return-analysis/"
    "report.json"
)
RETURN_ROOT = "r5_n71_n75_e1f_native_v3_return"
SOURCE_ROOT = "r5_n71_n75_e1f_native_v3"
EXPECTED_RETURN_BYTES = 42083
EXPECTED_RETURN_SHA256 = (
    "56e2a60ed7edfdea381cb1b72d528e922aaeac19d4a1d938cc6bb1ab555ece31"
)
EXPECTED_SOURCE_SHA256 = (
    "cfd37a380bc862a6a3c2d22bff01d0fe9b2ec2a25c04e9bae2bd7982971efae6"
)
EXPECTED_MANIFEST_SHA256 = (
    "098589160058aaab8f9936de0030d802b790e485d6fba29756518363aa1a44c9"
)


class AnalysisError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise AnalysisError(f"cannot parse {label}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{label} root is not an object")
    return value


def safe_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    entries: dict[str, bytes] = {}
    roots: set[str] = set()
    unsafe: list[str] = []
    duplicates: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        crc_error = archive.testzip()
        seen: set[str] = set()
        for info in archive.infolist():
            raw = info.filename
            pure = PurePosixPath(raw)
            windows = PureWindowsPath(raw)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or windows.is_absolute()
                or bool(windows.anchor)
                or "\\" in raw
                or ".." in pure.parts
            ):
                unsafe.append(raw)
            if raw in seen:
                duplicates.append(raw)
            seen.add(raw)
            if mode and stat.S_ISLNK(mode):
                symlinks.append(raw)
            if info.is_dir():
                continue
            if not raw.startswith(expected_root + "/"):
                unsafe.append(raw)
                continue
            relative = pure.relative_to(expected_root).as_posix()
            entries[relative] = archive.read(info)
    receipt = {
        "crc_valid": crc_error is None,
        "single_root": roots == {expected_root},
        "path_safe": not unsafe,
        "duplicate_free": not duplicates,
        "symlink_free": not symlinks,
        "roots": sorted(roots),
        "unsafe": unsafe,
        "duplicates": duplicates,
        "symlinks": symlinks,
        "file_count": len(entries),
    }
    return entries, receipt


def manifest_records(
    entries: dict[str, bytes],
    excluded: set[str],
) -> list[dict[str, Any]]:
    return [
        {
            "path": name,
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for name, payload in sorted(entries.items())
        if name not in excluded
    ]


def text(entries: dict[str, bytes], name: str) -> str:
    if name not in entries:
        raise AnalysisError(f"missing return member: {name}")
    return entries[name].decode("utf-8", errors="replace")


def integer_status(entries: dict[str, bytes], name: str) -> int:
    try:
        return int(text(entries, name).strip())
    except Exception as exc:
        raise AnalysisError(f"invalid status member: {name}") from exc


def validate(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    return_entries, return_zip_receipt = safe_zip(return_zip, RETURN_ROOT)
    source_entries, source_zip_receipt = safe_zip(source_zip, SOURCE_ROOT)
    errors: list[str] = []

    return_identity = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "external_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "transport_identity_basis":
            "USER_ATTESTED_PATH_SIZE_SHA256_NO_ADJACENT_SIDECAR",
    }
    source_identity = {
        "path": str(source_zip),
        "size_bytes": source_zip.stat().st_size,
        "sha256": sha256(source_zip),
    }
    if return_identity["size_bytes"] != EXPECTED_RETURN_BYTES:
        errors.append("return_size")
    if return_identity["sha256"] != EXPECTED_RETURN_SHA256:
        errors.append("return_sha256")
    if source_identity["sha256"] != EXPECTED_SOURCE_SHA256:
        errors.append("source_sha256")
    for label, receipt in (
        ("return_zip", return_zip_receipt),
        ("source_zip", source_zip_receipt),
    ):
        for key in (
            "crc_valid",
            "single_root",
            "path_safe",
            "duplicate_free",
            "symlink_free",
        ):
            if not receipt[key]:
                errors.append(f"{label}:{key}")

    return_manifest = load_json_bytes(
        return_entries["RETURN_MANIFEST.json"], "RETURN_MANIFEST.json"
    )
    return_allowlist = load_json_bytes(
        return_entries["RETURN_ALLOWLIST.json"], "RETURN_ALLOWLIST.json"
    )
    returned_source_manifest = return_entries["src/TEST_PACKAGE_MANIFEST.json"]
    local_source_manifest = source_entries["TEST_PACKAGE_MANIFEST.json"]
    source_manifest = load_json_bytes(
        local_source_manifest, "source TEST_PACKAGE_MANIFEST.json"
    )
    source_manifest_sha = sha256_bytes(local_source_manifest)
    returned_source_manifest_sha = sha256_bytes(returned_source_manifest)
    if source_manifest_sha != EXPECTED_MANIFEST_SHA256:
        errors.append("local_source_manifest_sha")
    if returned_source_manifest != local_source_manifest:
        errors.append("returned_source_manifest_bytes")
    if (
        return_manifest.get("source_package_manifest_sha256")
        != EXPECTED_MANIFEST_SHA256
    ):
        errors.append("return_manifest_source_binding")

    declared_return_records = return_manifest.get("files")
    actual_return_records = manifest_records(
        return_entries, {"RETURN_MANIFEST.json"}
    )
    return_manifest_exact = declared_return_records == actual_return_records
    if not return_manifest_exact:
        errors.append("return_manifest_exact_set")

    copied = return_allowlist.get("copied_exact_set")
    actual_copied = sorted(
        set(return_entries)
        - {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    )
    copied_exact = copied == actual_copied
    if not copied_exact:
        errors.append("return_allowlist_copied_exact_set")

    source_contract = source_manifest.get("return_allowlist", {})
    contract_records = source_contract.get("records", [])
    contract_by_destination = {
        str(item.get("destination")): item
        for item in contract_records
        if isinstance(item, dict)
    }
    if len(contract_records) != 162 or len(contract_by_destination) != 162:
        errors.append("source_return_allowlist_contract")
    returned_not_allowlisted = sorted(set(actual_copied) - set(contract_by_destination))
    required_missing = sorted(
        destination
        for destination, item in contract_by_destination.items()
        if item.get("required") is True and destination not in actual_copied
    )
    optional_missing = sorted(set(contract_by_destination) - set(actual_copied))
    if returned_not_allowlisted:
        errors.append("returned_member_not_allowlisted")
    if required_missing:
        errors.append("required_allowlist_member_missing")

    source_sca_exact = (
        return_entries["src/sca_cfg.json"]
        == source_entries["workload/sca_cfg.json"]
    )
    source_sca_d_exact = (
        return_entries["src/sca_cfg_D.json"]
        == source_entries["workload/sca_cfg_D.json"]
    )
    if not source_sca_exact:
        errors.append("returned_sca_bytes")
    if not source_sca_d_exact:
        errors.append("returned_sca_d_bytes")

    source_sidecar_valid = (
        SOURCE_SIDECAR.is_file()
        and SOURCE_SIDECAR.read_text(encoding="ascii")
        == f"{source_identity['sha256']}  {source_zip.name}\n"
    )
    if not source_sidecar_valid:
        errors.append("source_sidecar")

    gate = load_json_bytes(
        return_entries["e/SERVER_RESULT_GATE.json"],
        "SERVER_RESULT_GATE.json",
    )
    package_preflight = load_json_bytes(
        return_entries["e/package_preflight.json"], "package_preflight.json"
    )
    install_preflight = load_json_bytes(
        return_entries["e/install_preflight.json"], "install_preflight.json"
    )
    runtime_d_absent = load_json_bytes(
        return_entries["e/runtime_d_absent.json"], "runtime_d_absent.json"
    )
    compile_status = integer_status(
        return_entries, "e/compile_exit_status.txt"
    )
    run_status = integer_status(return_entries, "e/run_exit_status.txt")
    runner_status = integer_status(
        return_entries, "e/runner_exit_status.txt"
    )
    signal = text(return_entries, "e/signal_status.txt").strip()
    compile_argv = text(return_entries, "e/compile_argv.txt").strip()
    compile_log = text(return_entries, "log/compile.head_tail.log")
    compile_lines = compile_log.splitlines()
    error_lines = [
        {"line": index + 1, "text": line}
        for index, line in enumerate(compile_lines)
        if re.search(r"Error-\[IND\]|Identifier '.*' has not been declared", line)
    ]
    exact_leafs = {
        "clk_sg": {
            "observer_line": 211,
            "vcs_log_line": next(
                (
                    item["line"]
                    for item in error_lines
                    if "clk_sg" in item["text"]
                ),
                None,
            ),
        },
        "rst_n_sg": {
            "observer_line": 218,
            "vcs_log_line": next(
                (
                    item["line"]
                    for item in error_lines
                    if "rst_n_sg" in item["text"]
                ),
                None,
            ),
        },
    }
    compile_root_cause_proven = (
        compile_status == 2
        and runner_status == 2
        and run_status == 125
        and signal == "NONE"
        and "native_return_observer.svh, 211" in compile_log
        and "native_return_observer.svh, 218" in compile_log
        and "Identifier 'clk_sg' has not been declared" in compile_log
        and "Identifier 'rst_n_sg' has not been declared" in compile_log
        and "2 errors" in compile_log
    )
    if not compile_root_cause_proven:
        errors.append("compile_root_cause_not_unique")

    preflight_valid = (
        package_preflight.get("status") == "PACKAGE_PREFLIGHT_PASS"
        and package_preflight.get("package_manifest_sha256")
        == EXPECTED_MANIFEST_SHA256
        and package_preflight.get("a_preload_count") == 0
        and package_preflight.get("formal_readback_count") == 144
        and install_preflight.get("status")
        == "INSTALLED_WORKLOAD_PREFLIGHT_PASS"
        and install_preflight.get("installed_exact_tree") is True
        and runtime_d_absent.get("status")
        == "RUNTIME_D_ABSENT_PRE_SIM_PASS"
        and runtime_d_absent.get("all_absent") is True
        and runtime_d_absent.get("target_count") == 144
    )
    if not preflight_valid:
        errors.append("preflight_receipts")

    dynamic_not_started = (
        compile_status != 0
        and run_status == 125
        and "e/simulator_argv.txt" in optional_missing
        and "log/sim.head_tail.log" in optional_missing
        and "log/return_observer.log" in optional_missing
        and gate.get("formal_readback_actual_count") == 0
        and gate.get("formal_readback_expected_count") == 144
        and gate.get("canonical_record_count") == 0
        and gate.get("a_consumer_actual_acceptance", {}).get("event_count") == 0
    )
    if not dynamic_not_started:
        errors.append("dynamic_not_started_consistency")

    forbidden_markers = {
        "csrc",
        "simv",
        "simv.daidir",
        "waveform",
        ".zip",
    }
    forbidden_members = sorted(
        name
        for name in return_entries
        if any(part in forbidden_markers for part in PurePosixPath(name).parts)
    )
    if forbidden_members:
        errors.append("forbidden_return_member")

    integrity_passed = not errors
    return {
        "schema":
            "node0071-node0075-e1fb0f7-native-ordering-v3-return-analysis-v1",
        "status":
            "RETURN_VALID_COMPILE_FAIL_SUCCESSOR_REQUIRED"
            if integrity_passed
            else "RETURN_RECEIPT_INVALID",
        "valid": integrity_passed,
        "return_receipt": {
            "return": return_identity,
            "source_package": source_identity,
            "source_sidecar_valid": source_sidecar_valid,
            "zip_receipts": {
                "return": return_zip_receipt,
                "source": source_zip_receipt,
            },
            "return_manifest_exact": return_manifest_exact,
            "copied_allowlist_exact": copied_exact,
            "returned_not_allowlisted": returned_not_allowlisted,
            "required_missing": required_missing,
            "optional_missing_count": len(optional_missing),
            "optional_missing": optional_missing,
            "source_manifest_sha256": source_manifest_sha,
            "returned_source_manifest_sha256": returned_source_manifest_sha,
            "source_manifest_byte_equal": (
                returned_source_manifest == local_source_manifest
            ),
            "source_sca_byte_equal": source_sca_exact,
            "source_sca_d_byte_equal": source_sca_d_exact,
            "forbidden_members": forbidden_members,
        },
        "actual_compile_identity": {
            "compile_argv": compile_argv,
            "server_root": "/home/panqs/ndp/NDP_copy02",
            "package_root": "/home/panqs/ndp/r5_n71_n75_e1f_native_v3",
            "package_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "package_local_observer_sha256":
                source_manifest["observer"]["sha256"],
            "server_source_identity_bound": gate.get(
                "server_source_identity_bound"
            ),
            "production_rtl_identity_claim": False,
            "claim_boundary":
                "Actual compile argv and exact package-local observer are bound; "
                "the return does not hash or bind the server RTL tree.",
        },
        "execution_status": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "runtime_d_absent": runtime_d_absent,
            "compile_exit_status": compile_status,
            "runner_exit_status": runner_status,
            "run_exit_status": run_status,
            "signal_status": signal,
            "simulation_started": False,
            "dynamic_attempt_counted": False,
            "natural_terminal": False,
            "e3": False,
            "e4": False,
            "e5": False,
        },
        "return_analysis": {
            "classification": "PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE",
            "last_proven_good": (
                "Package/install exact-tree preflight and 144-target runtime-D "
                "absence passed; VCS parsed the active server design/TB and "
                "entered the exact package-local observer include."
            ),
            "first_divergence": (
                "VCS package-local observer name resolution at "
                "native_return_observer.svh:211: bare clk_sg is undeclared; "
                "line 218 independently repeats the defect for bare rst_n_sg."
            ),
            "hang_root_cause": (
                "NOT_A_HANG_SIMULATION_NOT_STARTED; compile failure is uniquely "
                "caused by package-local observer TB-scope clock/reset binding."
            ),
            "compile_root_cause_unique": compile_root_cause_proven,
            "exact_leafs": exact_leafs,
            "compile_error_receipt": error_lines,
        },
        "producer_consumer_ordering": {
            "adjudication": "NOT_REACHED_UNOBSERVED",
            "producer_downstream_hub_acceptance_actual": None,
            "node0075_pass00_first_actual_read": None,
            "ordered_success_claim": False,
            "opcode110_barrier_claim": False,
            "rtl_fault_claim": False,
        },
        "a_eight_pass_actual_acceptance": {
            "adjudication": "NOT_REACHED_UNOBSERVED",
            "configured_pass_count": 8,
            "configured_occurrences": 8192,
            "configured_traffic_bytes": 262144,
            "actual_event_count": None,
            "actual_accepted_traffic_bytes": None,
            "actual_pass_slice_hashes_adjudicated": False,
            "zero_in_generated_gate_is_not_actual_zero_traffic": True,
        },
        "formal_d": {
            "expected_count": 144,
            "node0071_expected": 16,
            "node0075_expected": 128,
            "actual_count": 0,
            "missing_count": 144,
            "mismatch_count": 0,
            "adjudication": "NOT_PRODUCED_SIMULATION_NOT_STARTED",
            "formal_d_pass": False,
        },
        "blocker_delta": {
            "new_closed_by_successor_build_required": [
                "B_MATMUL_NODE0075_V3_PACKAGE_LOCAL_OBSERVER_TB_SCOPE_"
                "CLOCK_RESET_UNRESOLVED"
            ],
            "remain_open": [
                "B_MATMUL_NODE0075_SERVER_NATURAL_TERMINAL",
                "B_MATMUL_NODE0075_FORMAL_D",
                "B_MATMUL_NODE0075_PRODUCER_ACCEPT_TO_PASS00_FIRST_READ_ORDERING",
                "B_MATMUL_NODE0075_ACTUAL_A_READS_8192_AND_HASH",
            ],
            "not_reopened": [
                "node0075 arithmetic/recurrence",
                "handler/registry/materializer/config-bound E2",
            ],
        },
        "successor_decision": {
            "required": True,
            "identity": "r5_n71_n75_e1f_native_v4",
            "repair_scope": (
                "Fresh package-local observer clock/reset scope binding and "
                "final-audit positive/negative coverage only."
            ),
            "workload_config_execplan_sca_golden_change": False,
            "functional_rtl_change": False,
            "diagnostic_only": True,
            "candidate_release": False,
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": (
                "The current rules already require exact final-HDL name "
                "resolution and continuous fresh-successor closure. The v3 "
                "focused harness implemented that rule incorrectly by inventing "
                "bare TB-scope clock/reset declarations."
            ),
            "claim_boundary": (
                "Package-local observer delivery and result-gate behavior only; "
                "no node0071/node0075 functional or RTL adjudication."
            ),
            "rule_delta_proposal": [],
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = validate(args.return_zip.resolve(), args.source_zip.resolve())
    except Exception as exc:
        report = {
            "schema":
                "node0071-node0075-e1fb0f7-native-ordering-v3-return-analysis-v1",
            "status": "RETURN_ANALYSIS_EXCEPTION",
            "valid": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "valid": report.get("valid"),
                "status": report.get("status"),
                "errors": report.get("errors"),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
