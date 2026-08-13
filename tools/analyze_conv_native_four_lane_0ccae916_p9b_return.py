#!/usr/bin/env python3
"""Validate and classify the formal native-four-lane p9b c0 return."""

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
    r"\msg\file\2026-08\r5_n4_0cc_p9b_tx5_return.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p9b_return_analysis"
    / "report.json"
)
INSTALL_NAME = "r5_n4_0cc_p9b_tx5"
RETURN_ROOT = f"{INSTALL_NAME}_return"
EXPECTED_SOURCE_SHA256 = (
    "d85429b61e8270d0c4108bfdcdf3a66bce44a437b8aab96b0412a5555dffb085"
)
OBSERVED_RETURN_BYTES = 105_219
OBSERVED_RETURN_SHA256 = (
    "96a4d9678b92dd5b74eb010de1fe27303dfc26a856f553623b6a162e999fab0d"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CLOUD_LEAVES = {
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
FEATURE_MARKER = (
    "N4D_FEATURE_ENABLE_V2 feature=NATIVE4_C0_BOUNDARY enabled=1 "
    "heartbeat_cycles=262144 stall_cycles=1048576 slice=0"
)
NATURAL_MARKER = "$finish at simulation time"
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


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def source_zip() -> Path:
    root = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages"
    )
    candidates = [
        root / "pending" / f"{INSTALL_NAME}.zip",
        root
        / "tested/conv_native_four_lane"
        / INSTALL_NAME
        / f"{INSTALL_NAME}.zip",
        root / f"{INSTALL_NAME}.zip",
    ]
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == EXPECTED_SOURCE_SHA256:
            return candidate
    raise FileNotFoundError("exact p9b source ZIP is unavailable")


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    failed_crc = archive.testzip()
    if failed_crc is not None:
        errors.append(f"CRC:{failed_crc}")
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or not pure.parts
            or pure.parts[0] != expected_root
            or info.filename in seen
            or stat.S_ISLNK(mode)
        ):
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


def fields(row: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", row)
    }


def csv_ints(value: str) -> list[int]:
    return [int(item, 0) for item in value.split(",")]


def parse_progress(observer_text: str, host_text: str) -> dict[str, Any]:
    progress_rows = [
        row
        for row in observer_text.splitlines()
        if row.startswith("N4D_PROGRESS_V1 ")
    ]
    canonical_rows = [
        row
        for row in observer_text.splitlines()
        if row.startswith("N4D_CANONICAL_V1 ")
    ]
    values = [fields(row) for row in progress_rows]
    decisions: dict[str, int] = {}
    for value in values:
        decision = value.get("decision", "MISSING")
        decisions[decision] = decisions.get(decision, 0) + 1
    last = values[-1] if values else {}
    host_rows = [
        fields(row)
        for row in host_text.splitlines()
        if row.startswith("host_epoch=")
    ]
    host_start = int(host_rows[0]["host_epoch"]) if host_rows else None
    host_end = int(host_rows[-1]["host_epoch"]) if host_rows else None
    observer_sizes = [
        int(value.get("observer_bytes", "0")) for value in host_rows
    ]
    totals = [int(value.get("total", "0")) for value in values]
    samples = [int(value.get("sample_end", "0")) for value in values]
    silent = [int(value.get("silent", "0")) for value in values]
    return {
        "feature_marker_count": observer_text.count(FEATURE_MARKER),
        "progress_record_count": len(progress_rows),
        "canonical_record_count": len(canonical_rows),
        "decision_counts": decisions,
        "max_qualified_total": max(totals, default=0),
        "last_qualified_total": totals[-1] if totals else 0,
        "last_sample_end_cycle": max(samples, default=0),
        "max_silent_windows": max(silent, default=0),
        "exec_start_count": decisions.get("EXEC_START", 0),
        "slice_finish_count": sum(
            "decision=SLICE_FINISH" in row for row in canonical_rows
        ),
        "last": last,
        "last_request_counts": csv_ints(last.get("req", "0,0,0,0,0")),
        "last_rdata_counts": csv_ints(
            last.get("rdata", "0,0,0,0,0")
        ),
        "last_wdata_counts": csv_ints(
            last.get("wdata", "0,0,0,0,0")
        ),
        "last_arm_request_counts": csv_ints(
            last.get("armreq", "0,0,0,0,0,0")
        ),
        "last_arm_response_counts": csv_ints(
            last.get("armresp", "0,0,0,0,0,0")
        ),
        "last_arm_finish_counts": csv_ints(
            last.get("armfin", "0,0,0,0,0,0")
        ),
        "last_sa_input_count": int(last.get("sain", "0")),
        "last_sa_output_count": int(last.get("saout", "0")),
        "last_buffer4_write_count": int(last.get("b4wr", "0")),
        "last_buffer4_read_count": int(last.get("b4rd", "0")),
        "last_buffer5_write_count": int(last.get("b5wr", "0")),
        "last_buffer5_read_count": int(last.get("b5rd", "0")),
        "last_mse4_index_count": int(last.get("m4idx", "0")),
        "last_queue_full_mask": last.get("qfull"),
        "last_queue_empty_mask": last.get("qempty"),
        "last_arm_hold_mask": last.get("armhold"),
        "last_arm_backpressure_mask": last.get("armbp"),
        "host_sample_count": len(host_rows),
        "host_start_epoch": host_start,
        "host_end_epoch": host_end,
        "host_observed_span_seconds": (
            host_end - host_start
            if host_start is not None and host_end is not None
            else None
        ),
        "host_observer_size_monotonic": all(
            right >= left
            for left, right in zip(observer_sizes, observer_sizes[1:])
        ),
        "host_last_observer_bytes": (
            observer_sizes[-1] if observer_sizes else 0
        ),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    exact_source = source_zip()
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "external_transport_receipt": (
            "USER_FORMAL_RETURN_PATH_ATTESTATION; adjacent sidecar absent"
        ),
    }
    source = {
        "path": str(exact_source),
        "size_bytes": exact_source.stat().st_size,
        "sha256": sha256(exact_source),
    }
    with zipfile.ZipFile(return_zip) as archive:
        records, payloads, return_errors = safe_records(
            archive, RETURN_ROOT
        )
    with zipfile.ZipFile(exact_source) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, INSTALL_NAME
        )

    return_manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    result_gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(
        payloads["evidence/production_rtl_identity.json"]
    )
    package_preflight = json.loads(
        payloads["evidence/package_preflight.json"]
    )
    install_preflight = json.loads(
        payloads["evidence/install_preflight.json"]
    )
    observer_precompile = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    source_manifest_bytes = source_payloads["package_manifest.json"]
    returned_manifest_bytes = payloads[
        "source_package/package_manifest.json"
    ]
    source_manifest = json.loads(source_manifest_bytes)
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
    host_text = payloads["runs/c0/host_progress.log"].decode(
        errors="replace"
    )
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
    mismatches = {
        path: {"expected": value, "observed": records.get(path)}
        for path, value in declared.items()
        if records.get(path) != value
    }
    allow_records = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in allowlist["records"]
    }
    allow_expected = set(allow_records) | {"RETURN_ALLOWLIST.json"}
    actual_leaves = {
        name: item["sha256"] for name, item in identity["leaves"].items()
    }
    cloud_mismatches = {
        name: {
            "expected_cloud_raw_sha256": CLOUD_LEAVES.get(name),
            "actual_production_sha256": actual_leaves.get(name),
            "actual_size_bytes": identity["leaves"].get(name, {}).get(
                "size_bytes"
            ),
        }
        for name in sorted(set(CLOUD_LEAVES) | set(actual_leaves))
        if CLOUD_LEAVES.get(name) != actual_leaves.get(name)
    }
    current_receipts = {
        path: sha256(ROOT / path)
        for path in RULE_PATHS
        if (ROOT / path).is_file()
    }
    gate = result_gate["execution_gate"]
    source_files = {
        path: value
        for path, value in source_records.items()
        if path != "package_manifest.json"
    }
    formal_scope_absent_by_design = (
        source_manifest.get("conv_run_ids") == ["c0"]
        and source_manifest.get("tail_run_ids") == []
        and source_manifest.get("formal_readback_count") == 0
        and source_manifest.get("readback_checks") == []
        and gate["formal_D_claimed"] is False
    )
    crossed_old_boundary = (
        progress["exec_start_count"] == 1
        and progress["max_qualified_total"] > 52_859
        and progress["decision_counts"].get("STILL_PROGRESSING", 0) > 0
        and progress["last_sa_output_count"] > 0
        and progress["last_buffer5_write_count"] > 0
        and progress["last_mse4_index_count"] > 0
    )
    did_not_close_c0 = (
        progress["canonical_record_count"] == 0
        and progress["slice_finish_count"] == 0
        and sim_text.count(NATURAL_MARKER) == 0
        and run_status == 125
        and signal_status == "INT"
        and gate["c0_natural_terminal"] is False
        and gate["diagnostic_natural_complete"] is False
    )
    checks = {
        "observed_outer_identity_stable": (
            outer["size_bytes"] == OBSERVED_RETURN_BYTES
            and outer["sha256"] == OBSERVED_RETURN_SHA256
        ),
        "source_identity_exact": (
            source["sha256"] == EXPECTED_SOURCE_SHA256
        ),
        "return_safe_crc": not return_errors,
        "source_safe_crc": not source_errors,
        "return_exact_set": set(records) == expected_set,
        "return_record_hashes_exact": not mismatches,
        "return_allowlist_exact": (
            set(records) == allow_expected
            and all(
                records.get(path) == value
                for path, value in allow_records.items()
            )
        ),
        "source_manifest_binding": (
            returned_manifest_bytes == source_manifest_bytes
            and digest(returned_manifest_bytes)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_manifest_files_exact": (
            source_manifest["files"] == source_files
        ),
        "preflights_valid": (
            package_preflight.get("valid") is True
            and install_preflight.get("valid") is True
            and observer_precompile.get("valid") is True
        ),
        "compile_succeeded": (
            compile_status == 0
            and gate["compile_succeeded"] is True
            and "Compilation completed!" in compile_driver
            and "0 error(s)" in compile_driver
        ),
        "identity_collected_nonblocking": (
            identity.get("collection_valid") is True
            and identity.get("cloud_authority_commit") == CLOUD_COMMIT
            and identity.get("identity_difference_blocks_simulator") is False
            and identity == result_gate["production_rtl_identity"]
            and identity["compile_log_sha256"]
            == digest(payloads["runs/compile/compile_driver.log"])
        ),
        "only_arm_differs_cloud": (
            set(cloud_mismatches) == {"Array_Request_Manager.sv"}
        ),
        "simulator_and_feature_started": (
            sim_text.count(FEATURE_MARKER) == 1
            and progress["feature_marker_count"] == 1
            and "Using SCA cfg file:" in sim_text
            and "Using SCA cfg D file:" in sim_text
        ),
        "tx5_crossed_old_progress_boundary": crossed_old_boundary,
        "c0_not_natural": did_not_close_c0,
        "formal_scope_absent_by_design": formal_scope_absent_by_design,
        "host_receipt_monotonic": (
            progress["host_sample_count"] > 0
            and progress["host_observer_size_monotonic"]
        ),
    }
    valid = all(checks.values())
    return {
        "schema": "conv-native-four-lane-0ccae916-p9b-return-analysis-v1",
        "status": (
            "TX5_CROSSED_OLD_BOUNDARY_C0_TERMINAL_STILL_OPEN"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "DYNAMIC_PROGRESS_WITH_TERMINAL_PROPAGATION_FAILURE"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(records),
            "return_manifest_sha256": records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "source_package_manifest_sha256": digest(
                returned_manifest_bytes
            ),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "exact_set_missing": sorted(expected_set - set(records)),
            "exact_set_extra": sorted(set(records) - expected_set),
            "record_mismatches": mismatches,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile": observer_precompile,
            "production_identity": identity,
            "cloud_leaf_mismatches": cloud_mismatches,
            "progress": progress,
            "feature_binding_receipt": result_gate[
                "feature_binding_receipt"
            ],
            "natural_terminal_receipt": result_gate[
                "natural_terminal_receipt"
            ],
            "formal_D_claimed": gate["formal_D_claimed"],
        },
        "threshold5_adjudication": {
            "old_p8f_last_qualified_total": 52_859,
            "p9b_max_qualified_total": progress["max_qualified_total"],
            "crossed_old_boundary": crossed_old_boundary,
            "c0_slice_finish": False,
            "natural_terminal": False,
            "decision": (
                "PARTIAL_CAUSAL_IMPROVEMENT_NOT_TERMINAL_CLOSURE"
            ),
            "evidence": {
                "sa_input_count": progress["last_sa_input_count"],
                "sa_output_count": progress["last_sa_output_count"],
                "buffer5_write_count": (
                    progress["last_buffer5_write_count"]
                ),
                "buffer5_read_count": (
                    progress["last_buffer5_read_count"]
                ),
                "mse4_index_count": (
                    progress["last_mse4_index_count"]
                ),
            },
        },
        "actual_cloud_arm_causal_risk": {
            "cloud_commit": CLOUD_COMMIT,
            "cloud_raw_sha256": CLOUD_LEAVES[
                "Array_Request_Manager.sv"
            ],
            "actual_production_sha256": actual_leaves[
                "Array_Request_Manager.sv"
            ],
            "actual_production_size_bytes": identity["leaves"][
                "Array_Request_Manager.sv"
            ]["size_bytes"],
            "actual_bytes_returned": False,
            "dynamic_arm_request_counts": progress[
                "last_arm_request_counts"
            ],
            "dynamic_arm_response_counts": progress[
                "last_arm_response_counts"
            ],
            "dynamic_arm_finish_counts": progress[
                "last_arm_finish_counts"
            ],
            "decision": "CAUSAL_RISK_REMAINS_NOT_ROOT_CAUSE_PROVEN",
            "reason": (
                "the only actual/cloud leaf mismatch is in the active "
                "request/terminal cone; p9b records zero ARM finish on every "
                "buffer but did not return the actual source bytes"
            ),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "c0 exec start, memory/request/ARM/SA activity, MSE4 index "
                "activity and Buffer5 activity; tx5 crosses p8f's old freeze"
            ),
            "FIRST_DIVERGENCE": (
                "qualified activity continues but ARM finish remains zero, "
                "SA accepts 28 inputs and only 3 outputs, MSE4 index count "
                "stops at 2, and c0 slice_finish never occurs"
            ),
            "HANG_ROOT_CAUSE": (
                "NOT_UNIQUE: actual ARM terminal semantics, MSE4 "
                "last/index propagation, and SA-output/Buffer5 acceptance "
                "must be discriminated by one always-on triggered profile"
            ),
            "root_cause_uniqueness": (
                "REMAINING_CANDIDATES_REQUIRE_TRIGGERED_CAUSAL_OBSERVABILITY"
            ),
            "observer_escape": (
                "p9b aggregate Buffer write-enable counters can count a "
                "stable level each cycle and therefore cannot alone prove "
                "accepted output transactions"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE4_TRANSOUT5_DID_NOT_CROSS_P8F_BOUNDARY",
                "B_CONV_NATIVE4_SIMULATOR_OR_FEATURE_NOT_STARTED",
            ],
            "preserved": [
                "B_CONV_NATIVE4_ACTUAL_ARRAY_REQUEST_MANAGER_IDENTITY_CAUSAL_RISK",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_TERMINAL_PROPAGATION_UNLOCALIZED",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor_decision": {
            "required": True,
            "identity": "r5_n4_0cc_p10_trig",
            "scope": (
                "C0_ALWAYS_ON_TRIGGERED_CAUSAL_OBSERVABILITY; "
                "config/numeric/W3/golden/address/functional RTL frozen"
            ),
            "full_27_320_now": False,
            "reason": (
                "p9b crossed the old boundary but did not close c0; the "
                "delegated branch requires one always-on triggered profile"
            ),
            "required_boundaries": [
                "exec/config/request and queue conservation",
                "ARM request/response/finish and last metadata",
                "SA input acceptance/compute/output acceptance",
                "MSE4 accepted index/last and Buffer5 accepted write",
                "slice terminal propagation and formal-D collector state",
            ],
            "functional_rtl_change": False,
            "numeric_w3_golden_repeated": False,
        },
        "claim_boundary": {
            "c0_only": True,
            "formal_320d_absent_by_design": True,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
            "server_action_by_analyzer": False,
        },
        "current_rule_receipts": current_receipts,
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
            "rule_delta_proposal": [],
            "claim_boundary": (
                "formal p9b return identity, tx5 boundary crossing, "
                "non-natural c0 terminal failure and successor obligation"
            ),
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
