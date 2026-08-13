#!/usr/bin/env python3
"""Validate and classify the formal native-four-lane p15 return."""

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
    r"C:\Users\15383\Downloads\r5_n4_0cc_p15_installonly_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n4_0cc_p15_installonly.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p15_return_analysis"
    / "report.json"
)
PACKAGE_ID = "r5_n4_0cc_p15_installonly"
RETURN_ROOT = f"{PACKAGE_ID}_return"
EXPECTED_RETURN_BYTES = 1_882_697
EXPECTED_RETURN_SHA256 = (
    "530964b1ea2da55e9f43aaa7224a285fb32159d6da3a2e15646deceb507a4a61"
)
EXPECTED_SOURCE_BYTES = 45_918_261
EXPECTED_SOURCE_SHA256 = (
    "e323e3394124c9b8b655037ac916cc3e3510360cb0097f1f91f60bfb9508c9b8"
)
OBSERVER_SHA256 = (
    "9c9c11f51f495b7b4b0a3ea453bf607dd1a74a0727cac091a2b7c626cc83e500"
)
STALE_OBSERVER_SOURCE_SHA256 = (
    "ec03472885f2264c2caa72f1f7aa047646033bc81d8885ca165de623befb2e86"
)
CURRENT_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CURRENT_LEAVES = {
    "Array_Request_Manager.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "RD_Data_Channel.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
    "Neighbor_Out_AG.sv": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
        "Neighbor_Stream_Engine/Neighbor_Out_AG.sv"
    ),
    "SA_PE_Float_CSA.v": (
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_CSA.v"
    ),
    "SA_PE_Float_Control.v": (
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_Control.v"
    ),
    "SA_PE_Mul_Array.v": (
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Mul_Array.v"
    ),
    "SA_ALU.v": (
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v"
    ),
    "Buffer.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
    ),
    "Buffer_Manager.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv"
    ),
    "Memory_Req_Manager.sv": (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Memory_Req_Manager.sv"
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


class AnalysisError(RuntimeError):
    pass


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
    bad = archive.testzip()
    if bad is not None:
        errors.append(f"CRC:{bad}")
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            not pure.parts
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
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


def ints(value: str) -> list[int]:
    return [int(item, 0) for item in value.split(",")]


def parse_triggered(text: str) -> dict[str, Any]:
    rows = [
        fields(line)
        for line in text.splitlines()
        if line.startswith("N4T_TRIGGER_V1 ")
    ]
    markers = [
        fields(line)
        for line in text.splitlines()
        if line.startswith("N4T_FEATURE_ENABLE_V1 ")
    ]
    no_progress = [
        row for row in rows if row.get("trigger") == "NO_PROGRESS_WINDOW"
    ]
    last = rows[-1] if rows else {}
    keys = [int(row.get("key_total", "0"), 0) for row in no_progress]
    return {
        "feature_markers": markers,
        "record_count": len(rows),
        "trigger_counts": {
            name: sum(row.get("trigger") == name for row in rows)
            for name in sorted({row.get("trigger", "") for row in rows})
        },
        "records": rows,
        "no_progress_window_count": len(no_progress),
        "no_progress_key_totals": keys,
        "no_progress_digests": [
            row.get("digest") or row.get("state_digest") for row in no_progress
        ],
        "last_cycle": int(last.get("sg_cycle", "0"), 0),
        "snapshot": {
            "key_total": int(last.get("key_total", "0"), 0),
            "request_counts": ints(last.get("req", "0,0,0,0,0")),
            "arm_request_counts": ints(
                last.get("armreq", "0,0,0,0,0,0")
            ),
            "arm_response_counts": ints(
                last.get("armresp", "0,0,0,0,0,0")
            ),
            "arm_finish_counts": ints(
                last.get("armfin", "0,0,0,0,0,0")
            ),
            "sa_input_accepted": int(last.get("sain", "0"), 0),
            "sa_output_accepted": int(last.get("saout", "0"), 0),
            "mse4_index_accepted": int(last.get("mse4", "0"), 0),
            "buffer5_active_cycles": int(last.get("b5_active", "0"), 0),
            "buffer5_rising_edges": int(last.get("b5_rise", "0"), 0),
            "buffer5_mask": last.get("b5_mask"),
        },
        "two_identical_no_progress_windows": (
            len(keys) >= 2
            and keys[-2:] == [314, 314]
            and len(
                set(
                    row.get("digest") or row.get("state_digest")
                    for row in no_progress[-2:]
                )
            )
            == 1
        ),
    }


def current_identity(actual: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, relative in CURRENT_LEAVES.items():
        path = ROOT / relative
        if not path.is_file():
            raise AnalysisError(f"current RTL leaf is absent: {relative}")
        observed = sha256(path)
        actual_leaf = actual.get("leaves", {}).get(name)
        rows[name] = {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": observed,
            "actual_compile_sha256": (
                actual_leaf.get("sha256") if actual_leaf else None
            ),
            "actual_matches_current_disk": (
                actual_leaf.get("sha256") == observed if actual_leaf else None
            ),
        }
    return {
        "commit": CURRENT_COMMIT,
        "source": "current clean NDP_copy01/rtl synchronized disk receipt",
        "leaves": rows,
        "actual_mismatches": sorted(
            name
            for name, row in rows.items()
            if row["actual_matches_current_disk"] is False
        ),
        "actual_uncollected_causal_leaves": sorted(
            name
            for name, row in rows.items()
            if row["actual_compile_sha256"] is None
        ),
    }


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "transport": "USER_FORMAL_DISPATCH_WITH_EXTERNAL_SIDECAR_WAIVER",
    }
    source = {
        "path": str(source_zip),
        "size_bytes": source_zip.stat().st_size,
        "sha256": sha256(source_zip),
    }
    with zipfile.ZipFile(return_zip) as archive:
        records, payloads, return_errors = safe_records(archive, RETURN_ROOT)
    with zipfile.ZipFile(source_zip) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, PACKAGE_ID
        )

    return_manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_preflight = json.loads(
        payloads["evidence/package_preflight.json"]
    )
    install_preflight = json.loads(
        payloads["evidence/install_preflight.json"]
    )
    observer_preflight = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    local_status = json.loads(
        payloads["evidence/package_local_preflight_status.json"]
    )
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    public = json.loads(payloads["evidence/public_order_summary.json"])
    triggered_summary = json.loads(
        payloads["evidence/triggered_causal_summary.json"]
    )
    source_manifest_bytes = source_payloads["package_manifest.json"]
    returned_manifest_bytes = payloads[
        "source_package/package_manifest.json"
    ]
    source_manifest = json.loads(source_manifest_bytes)
    returned_manifest = json.loads(returned_manifest_bytes)
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    sim_text = payloads["runs/c0/sim.log"].decode(errors="replace")
    trigger = parse_triggered(
        payloads["runs/c0/triggered_observer.log"].decode(errors="replace")
    )

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
    record_mismatches = {
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
    allow_set = set(allow_records) | {"RETURN_ALLOWLIST.json"}
    source_files = {
        path: value
        for path, value in source_records.items()
        if path != "package_manifest.json"
    }
    hotfixed = source_manifest_bytes.replace(
        STALE_OBSERVER_SOURCE_SHA256.encode(),
        OBSERVER_SHA256.encode(),
        1,
    )
    one_leaf_hotfix = (
        source_manifest_bytes.count(STALE_OBSERVER_SOURCE_SHA256.encode()) == 1
        and returned_manifest_bytes == hotfixed
        and returned_manifest.get("observer_binding", {}).get("source_sha256")
        == OBSERVER_SHA256
    )
    actual_current = current_identity(identity)
    snapshot = trigger["snapshot"]
    formal_absent = (
        source_manifest.get("conv_run_ids") == ["c0"]
        and source_manifest.get("tail_run_ids") == []
        and source_manifest.get("formal_readback_count") == 0
        and source_manifest.get("readback_checks") == []
        and gate["execution_gate"]["formal_D_claimed"] is False
    )
    exact_source_binding = returned_manifest_bytes == source_manifest_bytes
    dynamic_stall = (
        compile_status == 0
        and run_status == 125
        and signal_status == "INT"
        and identity.get("collection_valid") is True
        and trigger["two_identical_no_progress_windows"]
        and public.get("valid") is True
        and public.get("status") == "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
        and public["observer"]["event_counts"]
        == {
            "SA_IN_ACCEPT": 30,
            "SA_OUT_ACCEPT": 3,
            "MSE4_INDEX_ACCEPT": 1,
        }
        and snapshot["arm_finish_counts"] == [0, 0, 0, 0, 0, 0]
        and snapshot["buffer5_mask"] == "0xff"
        and "$finish at simulation time" not in sim_text
    )
    checks = {
        "outer_identity_exact": (
            outer["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer["sha256"] == EXPECTED_RETURN_SHA256
        ),
        "source_identity_exact": (
            source["size_bytes"] == EXPECTED_SOURCE_BYTES
            and source["sha256"] == EXPECTED_SOURCE_SHA256
        ),
        "return_safe_crc_root": not return_errors,
        "source_safe_crc_root": not source_errors,
        "return_exact_set": set(records) == expected_set,
        "return_records_exact": not record_mismatches,
        "return_allowlist_exact": (
            set(records) == allow_set
            and all(records.get(path) == row for path, row in allow_records.items())
        ),
        "source_file_map_exact": source_manifest.get("files") == source_files,
        "source_manifest_exact_binding": exact_source_binding,
        "one_leaf_delivery_hotfix_exact": one_leaf_hotfix,
        "preflight_chain_pass": (
            package_preflight.get("valid") is True
            and install_preflight.get("valid") is True
            and observer_preflight.get("valid") is True
            and local_status.get("path_budget_exit_status") == 0
            and local_status.get("package_preflight_exit_status") == 0
            and local_status.get("install_preflight_exit_status") == 0
            and local_status.get("observer_preflight_exit_status") == 0
        ),
        "root_and_layout_pass": (
            root_gate.get("valid") is True
            and root_gate.get("ndp_root_toplevel_unchanged") is True
            and layout.get("root_exact_set_unchanged") is True
            and layout.get("all_package_owned_paths_under_install") is True
            and layout.get("unknown_items_deleted_or_overwritten") is False
        ),
        "compile_and_simulator_started": (
            compile_status == 0
            and identity.get("collection_valid") is True
            and triggered_summary.get("valid") is True
            and trigger["feature_markers"]
        ),
        "qualified_stall_before_int": dynamic_stall,
        "formal_320d_absent_by_design": formal_absent,
    }
    structural_valid = all(
        value
        for name, value in checks.items()
        if name not in {
            "source_manifest_exact_binding",
        }
    )
    if not structural_valid:
        status = "RETURN_VALIDATION_FAILED"
    elif exact_source_binding:
        status = "QUALIFIED_C0_BUFFER5_STALL_SUCCESSOR_REQUIRED"
    else:
        status = (
            "P15_PLUS_ONE_LEAF_HOTFIX_C0_BUFFER5_STALL_SUCCESSOR_REQUIRED"
        )
    return {
        "schema": "conv-native-four-lane-0ccae916-p15-return-analysis-v1",
        "status": status,
        "analysis_valid": structural_valid,
        "exact_p15_source_consumable": structural_valid and exact_source_binding,
        "p15_plus_one_leaf_hotfix_diagnostic_consumable": (
            structural_valid and one_leaf_hotfix
        ),
        "exact_release_gate": False,
        "classification": (
            "LONG_RUNNING_C0_BACKPRESSURE_STALL_CONFIRMED_BEFORE_EXTERNAL_INT"
            if structural_valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "record_count": len(records),
            "return_manifest_sha256": records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected_set - set(records)),
            "extra": sorted(set(records) - expected_set),
            "record_mismatches": record_mismatches,
            "checks": checks,
        },
        "source_binding_adjudication": {
            "exact_source_manifest_sha256": digest(source_manifest_bytes),
            "returned_source_manifest_sha256": digest(returned_manifest_bytes),
            "return_declared_source_manifest_sha256": return_manifest[
                "source_package_manifest_sha256"
            ],
            "exact_byte_equal": exact_source_binding,
            "one_leaf_hotfix_exact": one_leaf_hotfix,
            "changed_json_path": "observer_binding.source_sha256",
            "old_value": STALE_OBSERVER_SOURCE_SHA256,
            "new_value": OBSERVER_SHA256,
            "p15_original_escape": (
                "PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE: the exact final "
                "ZIP's manifest bound the observer source to a stale SHA; "
                "the prior local positive control did not execute the exact "
                "guard-to-compile chain"
            ),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "compile_succeeded": True,
            "simulator_feature_started": True,
            "natural_terminal": False,
            "external_int_after_confirmed_stall": True,
            "partial_interrupted": False,
            "result_gate": gate,
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_preflight": observer_preflight,
            "package_local_preflight_status": local_status,
            "root_gate": root_gate,
            "runtime_layout_receipt": layout,
        },
        "production_rtl_identity": {
            "actual": identity,
            "current_disk_authority": actual_current,
            "identity_difference_blocks_simulator": False,
            "causal_risk": (
                "Actual ARM, Buffer_AG queue and SA control differ from "
                "current clean 0cc disk; Buffer/Buffer_Manager/MRM actual "
                "leaf identities were not collected by p15. This does not "
                "invalidate a compile-successful diagnostic, but prevents "
                "assigning the stall to a current-0cc functional leaf."
            ),
        },
        "qualified_causal_evidence": {
            "triggered": trigger,
            "triggered_summary": triggered_summary,
            "public_order_summary": public,
            "held_level_is_transaction": False,
            "two_identical_qualified_no_progress_windows": True,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "c0 exec with 314 qualified events: request counts "
                "[16,16,16,140,32], ARM request [8,7,10,7,6,3], ARM "
                "response [0,3,8,3,4,0], 30 SA input accepts, 3 SA output "
                "accepts and 1 MSE4 index accept"
            ),
            "FIRST_DIVERGENCE": (
                "the fourth SA output and later remain raw-valid with "
                "Buffer5-facing ready low; Buffer5 write mask remains 0xff "
                "and all six ARM finish counters remain zero"
            ),
            "HANG_ROOT_CAUSE": (
                "BUFFER5_WRITE_BACKPRESSURE_AT_PUBLIC_BOUNDARY; deeper leaf "
                "is not unique between producer-row occupancy, MSE4/MRM "
                "consumer drain/clear starvation and actual-vs-0cc Buffer/"
                "ARM causal semantics"
            ),
        },
        "result_conjunction": {
            "compile": True,
            "simulator_started": True,
            "c0_natural_terminal": False,
            "formal_D_payload_present": False,
            "formal_D_expected_count": 0,
            "formal_D_pass_count": 0,
            "mismatch_zero_claim": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
            "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE4_SIMULATOR_NOT_STARTED",
                "B_CONV_NATIVE4_INTERRUPTED_WHILE_QUALIFIED_PROGRESS",
                "B_CONV_NATIVE4_PUBLIC_ORDER_FIRST_DIVERGENCE_UNKNOWN",
            ],
            "opened": [
                "B_CONV_NATIVE4_P15_EXACT_SOURCE_OBSERVER_BINDING_ESCAPE",
            ],
            "preserved": [
                "B_CONV_NATIVE4_BUFFER5_BACKPRESSURE_DEEP_CAUSAL_LEAF",
                "B_CONV_NATIVE4_ACTUAL_BUFFER_MRM_IDENTITY_UNCOLLECTED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor_decision": {
            "required": structural_valid,
            "rerun_exact_p15": False,
            "identity": "r5_n4_0cc_p16_b5port",
            "scope": (
                "fresh exact observer binding plus public-port-only Buffer5 "
                "ARM-producer/MRM-consumer request, address, ready, clear "
                "and accepted-event matrix; collect actual Buffer, "
                "Buffer_Manager and Memory_Req_Manager leaf identities"
            ),
            "frozen": (
                "workload/config/mapping/bitstream/execplan/SCA/numeric/W3/"
                "golden/timeout/functional RTL/ISA/hardware"
            ),
            "functional_rtl_change": False,
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {
                "size_bytes": (ROOT / path).stat().st_size,
                "sha256": sha256(ROOT / path),
            }
            for path in RULE_PATHS
            if (ROOT / path).is_file()
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            ],
            "delta": (
                "No non-synonymous RULE_DELTA. The p15 escape is an "
                "implementation/test omission already covered by exact "
                "source binding and exact final-runner positive-control rules."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN_ZIP)
    parser.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    write_json(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "analysis_valid": result["analysis_valid"],
                "exact_p15_source_consumable": result[
                    "exact_p15_source_consumable"
                ],
                "diagnostic_consumable": result[
                    "p15_plus_one_leaf_hotfix_diagnostic_consumable"
                ],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
