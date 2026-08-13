#!/usr/bin/env python3
"""Validate and classify the formal p7 cloud-nonblocking c0 return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_n4_0cc_p7_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n4_0cc_p7.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p7_return_analysis"
    / "report.json"
)
INSTALL_NAME = "r5_n4_0cc_p7"
RETURN_ROOT = f"{INSTALL_NAME}_return"
EXPECTED_RETURN_BYTES = 93722
EXPECTED_RETURN_SHA = (
    "71e7feda390934afec933ddfbfded6d6bebfdb633a66fe3ab00dd1817293f05c"
)
EXPECTED_SOURCE_SHA = (
    "4ff473247a7356af3e6b960430b559e90113b774e27478dbcd41151d8507f8a4"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
]
EXPECTED_CLOUD_LEAVES = {
    "Array_Request_Manager.sv": (
        "026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca"
    ),
    "RD_Data_Channel.sv": (
        "449ce3bb75535b7fb9d7d00f5f940e35165ac47929d29b1c654c4755b3c4fcaa"
    ),
    "Neighbor_Out_AG.sv": (
        "05a6b1eadd2d5fb125a6a9e6b01b03dbbf9cd1bddc32423c01b5b6651cced41e"
    ),
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "SA_PE_Mul_Array.v": (
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    if archive.testzip() is not None:
        errors.append("CRC_FAILURE")
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        unsafe = (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or not pure.parts
            or pure.parts[0] != expected_root
            or info.filename in seen
            or stat.S_ISLNK(mode)
        )
        if unsafe:
            errors.append(info.filename)
            continue
        seen.add(info.filename)
        if info.is_dir():
            continue
        payload = archive.read(info)
        relative = PurePosixPath(*pure.parts[1:]).as_posix()
        records[relative] = {
            "size_bytes": len(payload),
            "sha256": digest(payload),
        }
        payloads[relative] = payload
    return records, payloads, errors


def parse_fields(row: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([a-zA-Z0-9_]+)=([^ ]+)", row)
    }


def parse_progress(observer_text: str, host_text: str) -> dict[str, Any]:
    rows = [
        row
        for row in observer_text.splitlines()
        if row.startswith("N4D_PROGRESS_V1 ")
    ]
    parsed = [(row, parse_fields(row)) for row in rows]
    decisions: dict[str, int] = {}
    for _, fields in parsed:
        decision = fields.get("decision", "MISSING")
        decisions[decision] = decisions.get(decision, 0) + 1
    snapshots = [
        (row, fields)
        for row, fields in parsed
        if fields.get("decision") in {"HEARTBEAT", "STILL_PROGRESSING"}
    ]
    first = snapshots[0][1] if snapshots else {}
    last = snapshots[-1][1] if snapshots else {}
    host_rows = [
        parse_fields(row)
        for row in host_text.splitlines()
        if row.startswith("host_epoch=")
    ]
    host_start = int(host_rows[0]["host_epoch"]) if host_rows else None
    host_end = int(host_rows[-1]["host_epoch"]) if host_rows else None
    observer_sizes = [
        int(row["observer_bytes"])
        for row in host_rows
        if "observer_bytes" in row
    ]
    last_b4wr = int(last.get("b4wr", "0"))
    last_b5rd = int(last.get("b5rd", "0"))
    last_cycle = int(last.get("sample_end", "0"))
    first_cycle = int(first.get("sample_end", "0"))
    monotonic_host_growth = all(
        right >= left for left, right in zip(observer_sizes, observer_sizes[1:])
    )
    return {
        "row_count": len(rows),
        "decision_counts": decisions,
        "feature_marker_count": observer_text.count(
            "N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1"
        ),
        "exec_start_count": decisions.get("EXEC_START", 0),
        "slice_finish_count": decisions.get("SLICE_FINISH", 0),
        "still_progressing_count": decisions.get("STILL_PROGRESSING", 0),
        "heartbeat_count": decisions.get("HEARTBEAT", 0),
        "stall_window_count": decisions.get("STALL_WINDOW", 0),
        "last_progress_row": snapshots[-1][0] if snapshots else None,
        "last_sample_end_cycle": last_cycle,
        "last_qualified_total": int(last.get("total", "0")),
        "last_buffer4_write_count": last_b4wr,
        "last_buffer5_read_count": last_b5rd,
        "last_sa_input_count": int(last.get("sain", "0")),
        "last_sa_output_count": int(last.get("saout", "0")),
        "progress_span_cycles": max(0, last_cycle - first_cycle),
        "crossed_historical_2097152_cycle_plateau": (
            last_cycle - int(parsed[0][1].get("sample_start", "0"))
            > 2_097_152
            if parsed
            else False
        ),
        "all_complete_windows_after_initial_are_nonzero": (
            decisions.get("STILL_PROGRESSING", 0) >= 1
            and decisions.get("LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH", 0)
            == 0
        ),
        "host_sample_count": len(host_rows),
        "host_start_epoch": host_start,
        "host_end_epoch": host_end,
        "host_observed_span_seconds": (
            host_end - host_start
            if host_start is not None and host_end is not None
            else None
        ),
        "host_observer_size_monotonic": monotonic_host_growth,
        "host_last_observer_bytes": observer_sizes[-1] if observer_sizes else 0,
        "dynamic_inference": {
            "classification": (
                "CONTINUOUS_QUALIFIED_PROGRESS_BEFORE_RUNNER_TIMEOUT"
            ),
            "not_a_terminal_proof": True,
            "not_a_formal_d_result": True,
            "note": (
                "projected completion time is intentionally not promoted to "
                "evidence; only a longer formal run can establish terminal"
            ),
        },
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "expected_size_bytes": EXPECTED_RETURN_BYTES,
        "expected_sha256": EXPECTED_RETURN_SHA,
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "external_transport_sidecar_optional": True,
    }
    source = {
        "path": str(SOURCE_ZIP),
        "size_bytes": SOURCE_ZIP.stat().st_size,
        "sha256": sha256(SOURCE_ZIP),
        "expected_sha256": EXPECTED_SOURCE_SHA,
    }
    with zipfile.ZipFile(return_zip) as archive:
        return_records, payloads, return_errors = safe_records(
            archive, RETURN_ROOT
        )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, INSTALL_NAME
        )

    return_manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    result_gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_precompile = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    feature_binding = json.loads(payloads["evidence/feature_binding/c0.json"])
    returned_package_manifest = payloads[
        "source_package/package_manifest.json"
    ]
    source_package_manifest = source_payloads["package_manifest.json"]
    source_manifest = json.loads(source_package_manifest)
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_driver = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )
    sim_text = payloads["runs/c0/sim.log"].decode(errors="replace")
    observer_text = payloads["runs/c0/return_observer.log"].decode(
        errors="replace"
    )
    host_text = payloads["runs/c0/host_progress.log"].decode(errors="replace")
    progress = parse_progress(observer_text, host_text)

    declared = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in return_manifest["records_excluding_this_manifest"]
    }
    expected_set = set(declared) | {
        "RETURN_MANIFEST.json",
        "RETURN_ALLOWLIST.json",
    }
    observed_set = set(return_records)
    mismatches = {
        path: {"expected": value, "observed": return_records.get(path)}
        for path, value in declared.items()
        if return_records.get(path) != value
    }
    allowlist_manifest = next(
        item
        for item in allowlist["records"]
        if item["path"] == "RETURN_MANIFEST.json"
    )
    actual_cloud = {
        name: leaf.get("sha256") for name, leaf in identity["leaves"].items()
    }
    current_receipts = {
        path: sha256(ROOT / path) for path in RULE_PATHS if (ROOT / path).is_file()
    }

    checks = {
        "outer_identity_exact": (
            outer["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer["sha256"] == EXPECTED_RETURN_SHA
        ),
        "source_identity_exact": source["sha256"] == EXPECTED_SOURCE_SHA,
        "return_zip_safe_and_crc_valid": not return_errors,
        "source_zip_safe_and_crc_valid": not source_errors,
        "return_exact_set": observed_set == expected_set,
        "return_record_hashes_exact": not mismatches,
        "allowlist_manifest_binding": (
            allowlist_manifest["size_bytes"]
            == return_records["RETURN_MANIFEST.json"]["size_bytes"]
            and allowlist_manifest["sha256"]
            == return_records["RETURN_MANIFEST.json"]["sha256"]
            and allowlist["declared_allowlist"]
            == return_manifest["declared_allowlist"]
        ),
        "source_package_manifest_exact": (
            returned_package_manifest == source_package_manifest
            and digest(returned_package_manifest)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_package_files_exact": (
            source_manifest["files"]
            == {
                path: value
                for path, value in source_records.items()
                if path != "package_manifest.json"
            }
        ),
        "package_preflight_valid": package_preflight.get("valid") is True,
        "install_preflight_valid": install_preflight.get("valid") is True,
        "observer_precompile_valid": observer_precompile.get("valid") is True,
        "compile_succeeded": (
            compile_status == 0
            and result_gate["execution_gate"]["compile_succeeded"] is True
            and "Compilation completed!" in compile_driver
            and "0 error(s)" in compile_driver
        ),
        "actual_identity_exact_cloud": (
            identity.get("collection_valid") is True
            and identity.get("cloud_authority_commit") == CLOUD_COMMIT
            and identity.get("actual_differs_cloud_authority") is False
            and identity.get("identity_difference_blocks_simulator") is False
            and actual_cloud == EXPECTED_CLOUD_LEAVES
            and identity == result_gate["production_rtl_identity"]
            and identity["compile_log_sha256"]
            == digest(payloads["runs/compile/compile_driver.log"])
        ),
        "simulation_started_and_feature_bound": (
            feature_binding.get("valid") is True
            and feature_binding["sim_log_sha256"]
            == digest(payloads["runs/c0/sim.log"])
            and feature_binding["observer_log_sha256"]
            == digest(payloads["runs/c0/return_observer.log"])
            and feature_binding == result_gate["feature_binding_receipt"]
        ),
        "runner_timeout_exact": (
            run_status == 124
            and signal_status == "NONE"
            and result_gate["execution_gate"]["run_exit_status"] == 124
        ),
        "exec_started_slice_finish_absent": (
            progress["exec_start_count"] == 1
            and progress["slice_finish_count"] == 0
            and result_gate["execution_gate"]["c0_natural_terminal"] is False
        ),
        "continuous_qualified_progress": (
            progress["still_progressing_count"] >= 20
            and progress["heartbeat_count"] >= 80
            and progress["last_buffer4_write_count"] > 10_000_000
            and progress["last_buffer5_read_count"] > 10_000_000
            and progress["crossed_historical_2097152_cycle_plateau"]
            and progress["all_complete_windows_after_initial_are_nonzero"]
            and progress["host_observer_size_monotonic"]
        ),
        "no_natural_or_formal_overclaim": (
            "evidence/natural_terminal/c0.json" not in return_records
            and source_manifest["formal_readback_count"] == 0
            and result_gate["execution_gate"]["formal_D_claimed"] is False
            and result_gate["canonical_record_count"] == 0
            and "$finish at simulation time" not in sim_text
        ),
    }
    valid = all(checks.values())
    status = (
        "LONG_RUNNING_PROGRESSING_RUNNER_TIMEOUT_SUCCESSOR_REQUIRED"
        if valid
        else "FAIL"
    )
    return {
        "schema": "conv-native-four-lane-0ccae916-p7-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": (
            "PACKAGE_WALLCLOCK_BUDGET_UNDERPROVISIONED_NOT_FUNCTIONAL_HANG"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(return_records),
            "return_manifest_sha256": return_records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": return_records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "source_package_manifest_sha256": digest(
                returned_package_manifest
            ),
            "return_zip_errors": return_errors,
            "source_zip_errors": source_errors,
            "exact_set_missing": sorted(expected_set - observed_set),
            "exact_set_extra": sorted(observed_set - expected_set),
            "record_mismatches": mismatches,
            "checks": checks,
        },
        "execution": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile": observer_precompile,
            "feature_binding": feature_binding,
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "production_identity": identity,
            "progress": progress,
            "formal_320d_scope_in_package": False,
            "formal_320d_result": "NOT_APPLICABLE_TO_P7_C0_DIAGNOSTIC",
        },
        "failure_localization": {
            "LPG": [
                "exact p7 source and exact formal return",
                "internal exact-set/hash/source-manifest binding",
                "package/install/observer precompile gates",
                "production compile/elaboration/link",
                "actual eight-leaf identity matches current cloud 0cc",
                "c0 simulator launch and exact feature binding",
                "qualified progress well beyond the historical plateau",
            ],
            "FD": (
                "runner-enforced 1h wallclock timeout before the first "
                "c0 slice_finish/natural terminal"
            ),
            "HANG_ROOT_CAUSE": (
                "NOT_A_PROVEN_FUNCTIONAL_HANG_RUNNER_TIMEOUT_WHILE_PROGRESSING"
            ),
            "c0_exec_to_slice_finish": (
                "EXEC_START_REACHED_SLICE_FINISH_NOT_YET_REACHED_AT_TIMEOUT"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8",
                "B_CONV_NATIVE4_OLD_2097152_CYCLE_PROGRESS_PLATEAU",
                "B_CONV_NATIVE4_SIMULATOR_LAUNCH_UNPROVEN",
            ],
            "converted_to_package_fix": [
                "B_P7_ONE_HOUR_RUNNER_WALLCLOCK_UNDERPROVISIONED",
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_NOT_IN_P7_SCOPE",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "release_gate_matrix": {
            "core_package_bootstrap_paths_runtime_d": {
                "disposition": "blocking_applicable",
                "pass": True,
            },
            "runner_compile_finalizer": {
                "disposition": "blocking_applicable",
                "pass": False,
                "blocking_failure": "1h c0 wallclock budget expired",
            },
            "package_local_hdl": {
                "disposition": "blocking_applicable",
                "pass": True,
                "evidence": "production VCS compile and exact feature binding",
            },
            "materialized_config": {
                "disposition": "receipt_reuse",
                "pass": True,
                "reason": "p7 config/address bytes are frozen and unchanged",
            },
            "diagnostic_observer_canonical": {
                "disposition": "blocking_applicable",
                "pass": True,
                "evidence": "exact observer feature binding and monotonic trace",
            },
            "return_result": {
                "disposition": "blocking_applicable",
                "pass": False,
                "reason": "c0 natural terminal absent at runner timeout",
            },
            "numeric_w3_golden": {
                "disposition": "record_only",
                "pass": True,
                "reason": "frozen; not repeated",
            },
            "blocking_failures": [
                "B_P7_ONE_HOUR_RUNNER_WALLCLOCK_UNDERPROVISIONED"
            ],
            "pass": False,
        },
        "successor_decision": {
            "required": True,
            "scope": "FULL_CHAIN_27_NATURAL_TERMINALS_AND_FORMAL_320D",
            "package_fix": "restore 12h per-run wallclock budget",
            "no_additional_c0_only_leaf": True,
            "functional_rtl_change": False,
            "materialized_config_change": False,
            "observer_semantic_change": False,
        },
        "claim_boundary": {
            "c0_natural_terminal_claimed": False,
            "formal_320d_claimed": False,
            "performance_E3_E4_E5_claimed": False,
            "server_action_by_analyzer": False,
        },
        "current_rule_receipts": current_receipts,
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "post-compile actual/cloud identity differences are record-only",
                "a timeout return with increasing qualified trace is not a hang proof",
                "formal D absent by diagnostic design is neither pass nor failure",
                "byte-equal config/address/numeric evidence uses receipt reuse",
            ],
            "rule_delta_proposal": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve())
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
