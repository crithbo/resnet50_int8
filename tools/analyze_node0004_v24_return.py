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

RETURN_SHA256 = "e403d08c5ea0b6dd252f72d4378e78b8f15c68165153d304dde7c1834fde0999"
SOURCE_SHA256 = "3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc"
INSTALL_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
RETURN_ROOT = f"{INSTALL_NAME}_return"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = "0c81d8fb6d2c1e33ab6600c711d7b1a143cef370c99cb71f5df3db3fa78c995f"


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


def load_json(entries: dict[str, bytes], path: str) -> dict[str, Any]:
    return json.loads(entries.get(path, b"{}"))


def integer_entry(entries: dict[str, bytes], path: str, fallback: int) -> int:
    try:
        return int(entries.get(path, str(fallback).encode()).strip())
    except ValueError:
        return fallback


def parse_kv_record(text: str, prefix: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for line in text.splitlines():
        if f"| {prefix} |" not in line:
            continue
        fields: dict[str, str] = {}
        for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line):
            fields[key] = value
        fields["_line"] = line
        result.append(fields)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--source-sidecar", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    errors: list[str] = []

    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")

    source_sidecar: dict[str, Any] = {"present": False}
    if args.source_sidecar is not None:
        sidecar = args.source_sidecar.resolve()
        declared = sidecar.read_text(encoding="ascii").strip()
        source_sidecar = {
            "present": True,
            "path": str(sidecar),
            "bytes": sidecar.stat().st_size,
            "sha256": sha256_file(sidecar),
            "content_valid": declared == f"{source_sha}  {source_zip.name}",
        }
        if not source_sidecar["content_valid"]:
            errors.append("source sidecar content mismatch")

    entries, zip_errors, zip_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected_set = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    record_checks: dict[str, bool] = {}
    if not isinstance(records, list):
        records = []
        errors.append("RETURN_ALLOWLIST records invalid")
    for record in records:
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append("RETURN_ALLOWLIST path invalid")
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

    manifest_records_match = return_manifest.get("records") == records
    allow_receipt = return_manifest.get("return_allowlist", {})
    allow_receipt_valid = (
        allow_receipt.get("path") == "RETURN_ALLOWLIST.json"
        and allow_receipt.get("size_bytes")
        == len(entries.get("RETURN_ALLOWLIST.json", b""))
        and allow_receipt.get("sha256")
        == sha256_bytes(entries.get("RETURN_ALLOWLIST.json", b""))
    )
    returned_manifest = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    source_manifest_payload = source.get("package_manifest.json", b"")
    package_receipt = return_manifest.get("source_package_manifest", {})
    package_receipt_valid = (
        package_receipt.get("returned_path")
        == "evidence/returned_package_manifest.json"
        and package_receipt.get("size_bytes") == len(returned_manifest)
        and package_receipt.get("sha256") == sha256_bytes(returned_manifest)
        and returned_manifest == source_manifest_payload
    )
    if (
        return_manifest.get("schema") != "node0004-return-manifest-v24"
        or return_manifest.get("install_name") != INSTALL_NAME
        or not manifest_records_match
        or not allow_receipt_valid
        or not package_receipt_valid
    ):
        errors.append("RETURN_MANIFEST/source binding differs")

    source_manifest = json.loads(source_manifest_payload or b"{}")
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
    observer_sha = sha256_bytes(observer)
    if observer_sha != OBSERVER_SHA256:
        errors.append("source observer SHA differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(
        entries, "evidence/observer_precompile.json"
    )
    feature_binding = load_json(
        entries, "evidence/diagnostic_feature_binding.json"
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
    simulator_argv = entries.get(
        "runs/c0/simulator_argv.txt", b""
    ).decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    observer_log = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")

    compile_argv_bound = (
        "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
        and f"/{INSTALL_NAME}/tb_probe" in compile_driver
    )
    runtime_argv_bound = all(
        token in simulator_argv
        for token in (
            "+RETURN_OBSERVER",
            "+RETURN_HANG_DIAG",
            "+RETURN_OBS_DEEP",
            "+RETURN_OBS_ABPE",
            "+RETURN_OBS_FINAL_RELEASE",
        )
    )
    time0_markers = parse_kv_record(
        observer_log, "DIAGNOSTIC_FEATURE_ENABLE_V1"
    )
    canonical = parse_kv_record(observer_log, "CANONICAL_DIAG_DECISION_V1")
    final_release = parse_kv_record(
        observer_log, "FINAL_RELEASE_BOUNDARY_V1"
    )
    abpe = parse_kv_record(observer_log, "ABPE_BOUNDARY_V1")
    progress = parse_kv_record(observer_log, "PROGRESS_WINDOW")

    final = final_release[-1] if final_release else {}
    abpe_final = abpe[-1] if abpe else {}
    dynamic_expected = {
        "canonical_exactly_one": len(canonical) == 1,
        "progress_windows_five": len(progress) == 5,
        "final_release_present": bool(final_release),
        "input_terminal_edges_256": final.get("input_terminal_edges") == "256",
        "input_matched_edges_zero": final.get("input_matched_edges") == "0",
        "input_out_edges_zero": final.get("input_out_edges") == "0",
        "alu_terminal_writes_zero": final.get("alu_terminal_writes") == "0",
        "ready_set_edges_zero": final.get("ready_set_edges") == "0",
        "output_ptr_changes_zero": final.get("output_ptr_changes") == "0",
        "pe_accepts_zero": final.get("pe_accepts") == "0",
        "buffer5_write_edge_zero": final.get("buffer5_write_edge") == "0",
        "abpe_a_group_accept_16": abpe_final.get("a_group_accept") == "16",
        "abpe_b_group_accept_16": abpe_final.get("b_group_accept") == "16",
        "abpe_c_group_accept_8": abpe_final.get("c_group_accept") == "8",
        "abpe_pe_out_accept_zero": abpe_final.get("pe_out_accept") == "0",
    }
    if not all(dynamic_expected.values()):
        errors.append("qualified v24 diagnostic record differs")

    feature_valid = (
        feature_binding.get("valid") is True
        and all(item.get("valid") is True for item in feature_binding.get("features", []))
        and len(time0_markers) == 4
    )
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_d = gate.get("formal_readback_claimed") is True
    formal_d_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and natural_terminal
        and formal_d
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )

    report: dict[str, Any] = {
        "schema": "node0004-v24-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "return_analysis": {
            "status": "LONG_RUNNING_HANG_AT_SA_TERMINAL_MATCH_GATE",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_return_sidecar": {
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
                "sidecar": source_sidecar,
            },
            "return_crc_path_root_duplicate_symlink_valid": not zip_errors,
            "return_zip_meta": zip_meta,
            "return_allowlist_exact_set_valid": exact_set_valid,
            "all_per_file_receipts_match": all(record_checks.values()),
            "return_manifest_records_match": manifest_records_match,
            "return_manifest_allowlist_receipt_valid": allow_receipt_valid,
            "returned_package_manifest_source_bound": package_receipt_valid,
            "source_crc_path_root_valid": not source_errors,
            "source_zip_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
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
            "actual_compile_argv_bound": compile_argv_bound,
            "runtime_argv_bound": runtime_argv_bound,
            "feature_binding_valid": feature_valid,
            "compile_exit_status": compile_status,
            "compile_elaboration_zero_errors": (
                compile_status == 0
                and (
                    "0 error(s)" in compile_log
                    or "0 errors" in compile_log
                )
                and "elaboration done" in compile_log
            ),
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": "[RETURN_OBSERVER] enabled" in sim_log,
            "diagnostic_finish_observed": "$finish" in sim_log,
            "natural_terminal": natural_terminal,
            "formal_d_claimed": formal_d,
            "formal_d_present": len(formal_d_members),
            "formal_d_missing": 320,
            "formal_d_mismatch": 0,
            "joint_result_gate": joint_gate,
        },
        "qualified_dynamic_evidence": {
            "canonical_decision": canonical[0] if canonical else None,
            "progress_windows": progress,
            "abpe_boundary": abpe_final,
            "final_release_boundary": final,
            "checks": dynamic_expected,
            "interpretation": (
                "A/B/C ingress and nonterminal ALU accumulation advanced, "
                "but no qualified terminal match/out, terminal ALU write, "
                "ready-set, output-pointer move, PE accept, or Buffer5 write "
                "occurred before four zero-delta windows."
            ),
            "state_only_not_progress": [
                "outbuffer_group_count",
                "outbuffer_group_empty",
                "raw Buffer4/Buffer5 enable levels",
            ],
        },
        "first_divergence": {
            "last_proven_good": (
                "SA_NONTERMINAL_OPERAND_ACCEPT_AND_ALU_OUTBUFFER_UPDATE"
            ),
            "first_divergence": (
                "RAW_INPUT_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_OR_OUT"
            ),
            "previous_frozen_last_proven_good_preserved": (
                "SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE"
            ),
            "previous_occupancy_root_cause_invalidated": True,
        },
        "hang_root_cause": {
            "classification": "UNRESOLVED_AFTER_V24_NARROW_DIAGNOSTIC",
            "root_interval": (
                "SA_PE_CONTROL_RAW_LAST_AND_INDEX_TO_ALL_OPERANDS_MATCHED_"
                "AND_TRANSOUT_LAST_CLASSIFICATION"
            ),
            "rtl_leaf": (
                "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
                "SA_PE_Control_Block.sv"
            ),
            "rtl_lines": [116, 118, 122, 132, 133, 134, 161, 162, 163, 164, 166, 167],
            "config_leaf": "special_array.transout_last_index",
            "materialized_value": 2,
            "why_not_unique_yet": (
                "v24 counts a rising edge of the OR-reduced masked A/B last "
                "signal, but does not return the individual A/B raw/masked "
                "valid/last/index values, all_operands_matched and pipeline "
                "accept on that same cycle, nor the transout diff. Therefore "
                "it cannot distinguish an index/config mismatch from a last "
                "arriving without a qualified two-operand accept."
            ),
            "not_yet_proven": [
                "configuration/tag terminal mismatch",
                "same/gotten masking suppressed the terminal operand",
                "control-block transout classification failure",
                "downstream final-release RTL defect",
            ],
        },
        "evidence_levels": {
            "E3": False,
            "E4": False,
            "E5": False,
            "diagnostic_runtime_evidence_consumable": True,
            "reason": (
                "compile/run and diagnostic finish passed, but natural DUT "
                "terminal and all 320 formal D readbacks are absent"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NODE0004_V23_PACKAGE_OBSERVER_UNDECLARED_IDENTIFIER",
                "B_CONV_NODE0004_RETURN_MANIFEST_IDENTITY_RECEIPT_MISSING",
            ],
            "replaced": {
                "B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED": (
                    "B_CONV_NODE0004_SA_TERMINAL_MATCH_INPUTS_UNOBSERVED"
                )
            },
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_TERMINAL_AND_FORMAL_D",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
            "successor_required": True,
            "successor_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        },
        "scope": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
            "reused_assets": [
                "frozen v24 source package",
                "frozen node0004 workload/config/bitstream/execplan/SCA/golden",
                "v24 returned qualified diagnostics",
            ],
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
