#!/usr/bin/env python3
"""Validate and classify the formal native-four-lane p8f full return."""

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
    r"\msg\file\2026-08\r5_n4_0cc_p8f_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n4_0cc_p8f.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p8f_return_analysis"
    / "report.json"
)
INSTALL_NAME = "r5_n4_0cc_p8f"
RETURN_ROOT = f"{INSTALL_NAME}_return"
EXPECTED_RETURN_BYTES = 123440
EXPECTED_RETURN_SHA256 = (
    "7a2de4c7551f40ed8ab4c82bd6a6efddd985c8e70a6704e9cdc451d2a4d870b9"
)
EXPECTED_SOURCE_SHA256 = (
    "1e214ba277992d4ab08795dd35f4db3082ccad4e17bebc2aaf6e473b1bc7c224"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
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


def parse_fields(row: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", row)
    }


def parse_progress(observer_text: str, host_text: str) -> dict[str, Any]:
    rows = [
        row
        for row in observer_text.splitlines()
        if row.startswith("N4PERF_CANONICAL_DECISION_V1 ")
    ]
    fields = [parse_fields(row) for row in rows]
    decision_counts: dict[str, int] = {}
    for item in fields:
        decision = item.get("decision", "MISSING")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
    totals = [int(item.get("qualified_total", "0")) for item in fields]
    deltas = [int(item.get("delta", "0")) for item in fields]
    host_rows = [
        parse_fields(row)
        for row in host_text.splitlines()
        if row.startswith("host_epoch=")
    ]
    host_start = int(host_rows[0]["host_epoch"]) if host_rows else None
    host_end = int(host_rows[-1]["host_epoch"]) if host_rows else None
    sizes = [int(item.get("observer_bytes", "0")) for item in host_rows]
    last = fields[-1] if fields else {}
    first_zero_after_progress = next(
        (
            int(item.get("sample_end", "0"))
            for item in fields
            if int(item.get("qualified_total", "0")) > 0
            and int(item.get("delta", "0")) == 0
        ),
        None,
    )
    return {
        "feature_marker_count": observer_text.count(
            "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1"
        ),
        "canonical_record_count": len(rows),
        "decision_counts": decision_counts,
        "first_qualified_total": totals[0] if totals else 0,
        "last_qualified_total": totals[-1] if totals else 0,
        "max_qualified_total": max(totals, default=0),
        "last_sample_end_cycle": int(last.get("sample_end", "0")),
        "first_zero_after_progress_cycle": first_zero_after_progress,
        "nonzero_delta_records": sum(value > 0 for value in deltas),
        "zero_delta_records": sum(value == 0 for value in deltas),
        "last_req_accept": int(last.get("req_accept", "0")),
        "last_rdata_accept": int(last.get("rdata_accept", "0")),
        "last_wdata_accept": int(last.get("wdata_accept", "0")),
        "last_bank_accept": int(last.get("bank_accept", "0")),
        "exec_start": int(last.get("exec_start", "0")),
        "finish": int(last.get("finish", "0")),
        "silent_windows": int(last.get("silent_windows", "0")),
        "host_sample_count": len(host_rows),
        "host_start_epoch": host_start,
        "host_end_epoch": host_end,
        "host_observed_span_seconds": (
            host_end - host_start
            if host_start is not None and host_end is not None
            else None
        ),
        "host_observer_size_monotonic": all(
            right >= left for left, right in zip(sizes, sizes[1:])
        ),
        "host_last_observer_bytes": sizes[-1] if sizes else 0,
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "external_transport_sidecar_optional": True,
    }
    source = {
        "path": str(SOURCE_ZIP),
        "size_bytes": SOURCE_ZIP.stat().st_size,
        "sha256": sha256(SOURCE_ZIP),
    }
    with zipfile.ZipFile(return_zip) as archive:
        records, payloads, return_errors = safe_records(archive, RETURN_ROOT)
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
    source_manifest_bytes = source_payloads["package_manifest.json"]
    returned_manifest_bytes = payloads["source_package/package_manifest.json"]
    source_manifest = json.loads(source_manifest_bytes)
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_driver = payloads[
        "runs/compile/sim_results/compile_driver.log"
    ].decode(errors="replace")
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
            "expected": EXPECTED_CLOUD_LEAVES.get(name),
            "actual": actual_leaves.get(name),
        }
        for name in sorted(set(EXPECTED_CLOUD_LEAVES) | set(actual_leaves))
        if EXPECTED_CLOUD_LEAVES.get(name) != actual_leaves.get(name)
    }
    current_receipts = {
        path: sha256(ROOT / path)
        for path in RULE_PATHS
        if (ROOT / path).is_file()
    }
    gate = result_gate["execution_gate"]
    checks = {
        "outer_transport_identity_exact": (
            outer["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer["sha256"] == EXPECTED_RETURN_SHA256
        ),
        "source_identity_exact": source["sha256"] == EXPECTED_SOURCE_SHA256,
        "return_safe_crc": not return_errors,
        "source_safe_crc": not source_errors,
        "return_exact_set": set(records) == expected_set,
        "return_record_hashes_exact": not mismatches,
        "return_allowlist_exact": (
            set(records) == allow_expected
            and all(records.get(path) == value for path, value in allow_records.items())
        ),
        "source_manifest_binding": (
            returned_manifest_bytes == source_manifest_bytes
            and digest(returned_manifest_bytes)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_manifest_files_exact": source_manifest["files"]
        == {
            path: value
            for path, value in source_records.items()
            if path != "package_manifest.json"
        },
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
            == digest(
                payloads["runs/compile/sim_results/compile_driver.log"]
            )
        ),
        "only_one_cloud_leaf_mismatch": set(cloud_mismatches)
        == {"Array_Request_Manager.sv"},
        "simulation_started_feature_bound": (
            "N4PERF_FEATURE_ENABLE_V1" in observer_text
            and "+RETURN_OBSERVER" in sim_text
            and "Runtime version V-2023.12-SP2_Full64" in sim_text
        ),
        "qualified_progress_then_long_zero_delta": (
            progress["feature_marker_count"] == 1
            and progress["exec_start"] == 1
            and progress["finish"] == 0
            and progress["max_qualified_total"] == 52859
            and progress["nonzero_delta_records"] == 1
            and progress["decision_counts"].get(
                "LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH", 0
            )
            >= 250
            and progress["silent_windows"] >= 250
            and progress["last_sample_end_cycle"] >= 275_000_000
            and progress["host_observer_size_monotonic"]
        ),
        "external_interrupt_after_hang": (
            run_status == 125
            and signal_status == "INT"
            and gate["run_exit_status"] == 125
            and gate["signal_status"] == "INT"
        ),
        "formal_result_fail_closed": (
            gate["natural_terminal_count"] == 0
            and gate["required_natural_terminal_count"] == 27
            and gate["formal_readback_count"] == 320
            and gate["missing_count"] == 320
            and gate["mismatch_byte_count"] == 0
            and gate["conjunction_pass"] is False
            and result_gate["candidate_release"] is False
        ),
    }
    valid = all(checks.values())
    return {
        "schema": "conv-native-four-lane-0ccae916-p8f-return-analysis-v1",
        "status": (
            "LONG_RUNNING_HANG_CONFIG_FIX_SUCCESSOR_REQUIRED"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "FIRST_DYNAMIC_FAILURE_WITH_KNOWN_CONFIG_DEFECT_AND_ARM_IDENTITY_RISK"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(records),
            "return_manifest_sha256": records["RETURN_MANIFEST.json"]["sha256"],
            "return_allowlist_sha256": records["RETURN_ALLOWLIST.json"]["sha256"],
            "source_package_manifest_sha256": digest(returned_manifest_bytes),
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
            "natural_terminal_count": gate["natural_terminal_count"],
            "required_natural_terminal_count": gate[
                "required_natural_terminal_count"
            ],
            "formal_readback_count": gate["formal_readback_count"],
            "formal_present_count": (
                gate["formal_readback_count"] - gate["missing_count"]
            ),
            "formal_missing_count": gate["missing_count"],
            "formal_mismatch_byte_count": gate["mismatch_byte_count"],
            "result_conjunction_pass": gate["conjunction_pass"],
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "c0 exec start plus initial 52,859 qualified public-boundary "
                "events through request/rdata/bank acceptance"
            ),
            "FIRST_DIVERGENCE": (
                "all qualified progress freezes before c0 slice_finish; "
                "no formal D is produced"
            ),
            "HANG_ROOT_CAUSE": (
                "KNOWN_TRANSOUT_THRESHOLD_DEFECT_MUST_BE_REMOVED; "
                "the p8f trace does not itself reach the terminal classifier, "
                "and the sole actual/cloud mismatch is the causal ARM leaf"
            ),
            "root_cause_uniqueness": "TWO_CAUSAL_CANDIDATES_REMAIN",
            "known_static_config_defect": {
                "path": "special_array.transout_last_index",
                "current": 2,
                "required": 5,
                "historical_dynamic_counterexample": (
                    "accepted indices 4/5: threshold2 ignored 256/256; "
                    "threshold5 released 256/256"
                ),
            },
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE4_P8F_COMPILE_OR_SIMULATOR_LAUNCH_UNPROVEN",
                "B_CONV_NATIVE4_P8F_PROGRESSING_ONLY_NOT_HANG",
            ],
            "identified_for_config_fix": [
                "B_CONV_NATIVE4_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL",
            ],
            "preserved": [
                "B_CONV_NATIVE4_ACTUAL_ARRAY_REQUEST_MANAGER_IDENTITY_CAUSAL_RISK",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_MISSING",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor_decision": {
            "required": True,
            "identity": "r5_n4_0cc_p9_tx5",
            "scope": "C0_CONFIG_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS",
            "configuration_change": {
                "path": "special_array.transout_last_index",
                "old": 2,
                "new": 5,
            },
            "observer_source": "byte-equal p7 public-surface observer",
            "run_timeout_seconds": 43200,
            "candidate_matrix": {
                "same_early_public_boundary_freeze": (
                    "actual ARM/source path remains first dynamic divergence"
                ),
                "progress_reaches_sa_output_or_buffer5": (
                    "terminal config repair crosses the old terminal boundary"
                ),
                "natural_c0_terminal": (
                    "advance next fresh successor to full 27/320 target"
                ),
            },
            "functional_rtl_change": False,
            "numeric_w3_golden_repeated": False,
        },
        "claim_boundary": {
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
                "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "rule_delta_proposal": [],
            "claim_boundary": (
                "return identity, c0 hang localization, fail-closed 0/320 "
                "formal result, and fresh config-successor obligation only"
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
