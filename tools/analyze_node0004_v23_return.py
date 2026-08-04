from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True

RETURN_SHA256 = "e8efef64b095f5d6cc2b5e4d734b6d1a94a14741d3b608dfc008ef6894905842"
SOURCE_SHA256 = "9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27"
SOURCE_SIDECAR_SHA256 = (
    "6050f268a34b6902c011a159f94ae8a2299f607a1efc253bcb5151ec9b3706c7"
)
INSTALL_NAME = "r5_n4_hw_v23_final_release_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = "3ecc3f0e0f276a5d4cfa9ca8267cedcad2a0b1198929217f99046595524e8723"
UNDECLARED_IDENTIFIER = "return_obs_buf45_wr_edge_count"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_entries(
    path: Path, expected_root: str
) -> tuple[dict[str, bytes], list[str], dict[str, Any]]:
    errors: list[str] = []
    entries: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    symlinks: list[str] = []
    uncompressed = 0
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                errors.append(f"unsafe or duplicate member: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(info.filename)
                errors.append(f"symlink member: {info.filename}")
                continue
            if info.is_dir():
                continue
            uncompressed += info.file_size
            if pure.parts[0] != expected_root or len(pure.parts) < 2:
                errors.append(f"unexpected root: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    if roots != {expected_root}:
        errors.append(f"root set differs: {sorted(roots)}")
    return entries, errors, {
        "root_set": sorted(roots),
        "symlink_members": symlinks,
        "entry_count": len(entries),
        "uncompressed_bytes": uncompressed,
    }


def integer_entry(entries: dict[str, bytes], path: str, fallback: int) -> int:
    try:
        return int(entries.get(path, str(fallback).encode()).strip())
    except ValueError:
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--source-sidecar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    source_sidecar = args.source_sidecar.resolve()
    errors: list[str] = []

    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    sidecar_sha = sha256_file(source_sidecar)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    if sidecar_sha != SOURCE_SIDECAR_SHA256:
        errors.append("source sidecar file SHA mismatch")
    sidecar_valid = (
        source_sidecar.read_text(encoding="ascii").strip()
        == f"{source_sha}  {source_zip.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar content mismatch")

    entries, zip_errors, zip_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)

    allowlist = json.loads(entries.get("RETURN_ALLOWLIST.json", b"{}"))
    records = allowlist.get("records", [])
    record_checks: dict[str, bool] = {}
    expected_set = {"RETURN_ALLOWLIST.json"}
    if not isinstance(records, list):
        errors.append("return allowlist records invalid")
        records = []
    for record in records:
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append("return allowlist path invalid")
            continue
        expected_set.add(relative)
        payload = entries.get(relative)
        passed = (
            payload is not None
            and len(payload) == record.get("size_bytes")
            and sha256_bytes(payload) == record.get("sha256")
        )
        record_checks[relative] = passed
        if not passed:
            errors.append(f"allowlist receipt differs: {relative}")
    exact_set_valid = expected_set == set(entries)
    if not exact_set_valid:
        errors.append("return exact-set differs from RETURN_ALLOWLIST")

    source_manifest = json.loads(source.get("package_manifest.json", b"{}"))
    source_files = source_manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source package manifest exact-set differs")
    observer = source.get(OBSERVER_RELATIVE, b"")
    observer_text = observer.decode("utf-8", errors="replace")
    observer_sha = sha256_bytes(observer)

    gate = json.loads(entries.get("evidence/SERVER_RESULT_GATE.json", b"{}"))
    package_preflight = json.loads(
        entries.get("evidence/package_preflight.json", b"{}")
    )
    install_preflight = json.loads(
        entries.get("evidence/install_preflight.json", b"{}")
    )
    observer_preflight = json.loads(
        entries.get("evidence/observer_precompile.json", b"{}")
    )
    feature_binding = json.loads(
        entries.get("evidence/diagnostic_feature_binding.json", b"{}")
    )
    compile_status = integer_entry(
        entries, "evidence/compile_exit_status.txt", 125
    )
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal_status = entries.get(
        "evidence/signal_status.txt", b"MISSING"
    ).decode("ascii", errors="replace").strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")

    error_lines = [
        line
        for line in compile_log.splitlines()
        if "Error-[" in line or "Identifier '" in line
    ]
    compile_root_cause = (
        compile_status == 2
        and "Error-[IND] Identifier not declared" in compile_log
        and UNDECLARED_IDENTIFIER in compile_log
        and "native_return_observer.svh, 3926" in compile_log
        and observer_text.count(UNDECLARED_IDENTIFIER) == 1
        and not re.search(
            rf"\b(?:logic|wire|reg|integer|longint)\b[^;]*\b{UNDECLARED_IDENTIFIER}\b",
            observer_text,
        )
        and observer_sha == OBSERVER_SHA256
    )
    if not compile_root_cause:
        errors.append("package-local observer compile root cause did not close")

    compile_argv_bound = (
        "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
        and f"+incdir+/home/panqs/ndp/{INSTALL_NAME}/tb_probe"
        in compile_driver
    )
    if not compile_argv_bound:
        errors.append("actual compile argv observer binding differs")

    return_manifest_present = "RETURN_MANIFEST.json" in entries
    returned_package_manifest_present = (
        "evidence/returned_package_manifest.json" in entries
        or "package_manifest.json" in entries
    )
    formal_receipt_complete = (
        return_manifest_present and returned_package_manifest_present
    )

    source_sca = sorted(
        path
        for path in source
        if path.endswith("sca_cfg.json") or path.endswith("sca_cfg_D.json")
    )
    source_sca_receipts = {
        path: {
            "bytes": len(source[path]),
            "sha256": sha256_bytes(source[path]),
            "manifest_match": source_files.get(path)
            == sha256_bytes(source[path]),
        }
        for path in source_sca
    }
    runtime_started = compile_status == 0 and run_status != 125
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_d = gate.get("formal_readback_claimed") is True
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and natural_terminal
        and formal_d
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )

    report: dict[str, Any] = {
        "schema": "node0004-v23-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "return_analysis": {
            "status": "PACKAGE_LOCAL_OBSERVER_COMPILE_FAILURE",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "policy": "user-attested transport; analysis SHA recomputed",
                "rule_id": (
                    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
                ),
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_path": str(source_sidecar),
                "sidecar_sha256": sidecar_sha,
                "sidecar_valid": sidecar_valid,
            },
            "zip_crc_path_root_duplicate_symlink_valid": not zip_errors,
            "zip_meta": zip_meta,
            "return_allowlist_install_name": allowlist.get("install_name"),
            "return_allowlist_exact_set_valid": exact_set_valid,
            "return_allowlist_record_count": len(records),
            "all_per_file_receipts_match": all(record_checks.values()),
            "per_file_receipts": record_checks,
            "return_manifest_present": return_manifest_present,
            "returned_package_manifest_present": (
                returned_package_manifest_present
            ),
            "formal_return_identity_receipt_complete": formal_receipt_complete,
            "formal_return_identity_receipt_gap": [
                name
                for name, present in (
                    ("RETURN_MANIFEST.json", return_manifest_present),
                    (
                        "returned package manifest identity",
                        returned_package_manifest_present,
                    ),
                )
                if not present
            ],
            "source_crc_path_root_valid": not source_errors,
            "source_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
            "source_install_name": source_manifest.get("install_name"),
            "source_observer_sha256": observer_sha,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "install_preflight_valid": install_preflight.get("valid") is True,
            "runtime_d_initially_absent": (
                install_preflight.get("runtime_d_initially_absent") is True
            ),
            "observer_precompile_valid": (
                observer_preflight.get("valid") is True
            ),
            "observer_identity_match": (
                observer_preflight.get("identity_match") is True
                and observer_preflight.get("observed_sha256") == observer_sha
            ),
            "observer_xmr_static_gate": observer_preflight.get(
                "xmr_static_gate"
            ),
            "actual_compile_argv_bound": compile_argv_bound,
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": runtime_started,
            "simulator_argv_present": "runs/c0/simulator_argv.txt" in entries,
            "time_zero_marker_present": False,
            "feature_binding_status": feature_binding.get("status"),
            "feature_binding_valid": feature_binding.get("valid") is True,
            "natural_terminal": natural_terminal,
            "formal_d_claimed": formal_d,
            "formal_d_present": 0,
            "formal_d_missing": 320,
            "joint_result_gate": joint_gate,
            "source_sca_sca_d_receipts": source_sca_receipts,
        },
        "first_divergence": {
            "last_proven_good_this_return": (
                "PACKAGE_INSTALL_AND_OBSERVER_STATIC_PREFLIGHT_PASS"
            ),
            "first_divergence_this_return": (
                "VCS_PARSE_PACKAGE_LOCAL_OBSERVER_UNDECLARED_IDENTIFIER"
            ),
            "frozen_conv_dataflow_last_proven_good": (
                "SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE"
            ),
            "frozen_conv_dataflow_first_divergence": (
                "SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID"
            ),
            "conv_dataflow_advanced_by_v23": False,
        },
        "hang_root_cause": {
            "classification": "NOT_A_RUNTIME_HANG_SIMULATION_NOT_STARTED",
            "root_cause": "PACKAGE_LOCAL_OBSERVER_UNDECLARED_IDENTIFIER",
            "file": f"{INSTALL_NAME}/{OBSERVER_RELATIVE}",
            "line": 3926,
            "leaf_sha256": observer_sha,
            "identifier": UNDECLARED_IDENTIFIER,
            "mechanism": (
                "FINAL_RELEASE_BOUNDARY_V1 references an edge counter that "
                "was never declared or updated; VCS stops before elaboration "
                "and before simulator argv/time0/qualified evidence."
            ),
            "compile_error_lines": error_lines,
            "minimal_legal_fix": (
                "declare/reset/update the intended qualified Buffer5 write "
                "rising-edge counter and preserve the existing boundary "
                "reference; also add lexical negative coverage"
            ),
        },
        "evidence_levels": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "compile failed before simulation and formal D",
        },
        "blocker_delta": {
            "preserved_invalidated": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
            "closed": [],
            "opened": [
                "B_CONV_NODE0004_V23_PACKAGE_OBSERVER_UNDECLARED_IDENTIFIER",
                "B_CONV_NODE0004_RETURN_MANIFEST_IDENTITY_RECEIPT_MISSING",
            ],
            "preserved": [
                "B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED",
                "B_CONV_NODE0004_DYNAMIC_TERMINAL_AND_FORMAL_D",
            ],
            "successor_required": True,
            "successor_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        },
        "scope": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
