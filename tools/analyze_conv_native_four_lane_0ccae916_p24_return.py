#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p24 return."""

from __future__ import annotations

import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p24_selport"
EXECUTION_ID = "r1786203016970364534_4152336"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p24_selport_"
    r"r1786203016970364534_4152336_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_067_865
RETURN_SHA256 = "8420a8bc99daca2bd0aabbc425826b8dcb01b7560ddbf164c3339d7da9fff5bf"
SOURCE_BYTES = 5_880_634
SOURCE_SHA256 = "4690da16077c60c91d7de7c5fd1042f17bdb8db844d59ae4169528a6ba318c28"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p24_return_analysis/report.json"
OBSERVER = "tb_probe/native_return_observer.svh"
EXPECTED_OBSERVER_SHA256 = "d00fb679950323deca8843c4813915f28b3e0ad7c2eed856b08a473a577d5986"
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


class AnalysisError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {"size_bytes": item["size_bytes"], "sha256": item["sha256"]}
        for item in value[key]
    }


def kv(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")

    with zipfile.ZipFile(RETURN_ZIP) as archive:
        records, payloads, return_errors = common.safe_records(
            archive, f"{PACKAGE_ID}_return"
        )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = common.safe_records(
            archive, PACKAGE_ID
        )

    manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    local_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    publication = json.loads(payloads["evidence/publication_preflight.json"])
    public = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    returned_source_manifest = payloads["source_package/package_manifest.json"]
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    sim_log = payloads["runs/c0/sim.log"].decode(errors="replace")
    observer_log = payloads["runs/c0/return_observer.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()

    declared = record_map(manifest, "records_excluding_this_manifest")
    expected = set(declared) | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    allowed = record_map(allowlist, "records")
    allowed_set = set(allowed) | {"RETURN_ALLOWLIST.json"}
    declared_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in declared.items() if records.get(path) != row
    }
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items() if records.get(path) != row
    }
    source_files = {
        path: row for path, row in source_records.items() if path != "package_manifest.json"
    }
    unique_return = (
        RETURN_ZIP.name == f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
    )

    observer_text = source_payloads[OBSERVER].decode()
    compile_success = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[IND]" not in compile_log
        and "Error-[XMRE]" not in compile_log
        and common.digest(source_payloads[OBSERVER]) == EXPECTED_OBSERVER_SHA256
        and "p24 PUBLIC_SELECT_PORT_BEGIN" in observer_text
    )
    simulation_started = (
        "+RETURN_OBS_SELECT_PORT" in simulator_argv
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and "feature=RETURN_OBS_SELECT_PORT enabled=1" in observer_log
    )
    select_rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines()
        if "PUBLIC_SELECT_PORT_V1 | kind=" in line
    ]
    if not select_rows:
        raise AnalysisError("p24 public select-port ledger is absent")
    qualified_rows = [row for row in select_rows if row["kind"] == "1"]
    state_rows = [row for row in select_rows if row["kind"] == "2"]
    idx8_rows = [
        row for row in qualified_rows
        if int(row["connect_idx"], 16) == 8 and int(row["memory_idx"], 16) == 8
    ]
    selected_id = collections.Counter(int(row["src_id"], 0) for row in select_rows)
    source7_rows = [row for row in select_rows if int(row["event_mask"], 16) & 1]
    public_boundary = (
        selected_id == collections.Counter({13: len(select_rows)})
        and len(qualified_rows) == 128
        and len(state_rows) == 2
        and all(int(row["port_eq"], 0) == 1 for row in select_rows)
        and any(
            int(row["event_mask"], 16) & 0x6 == 0x6
            and int(row["connect_valid"], 0) == int(row["connect_bp"], 0) == 1
            and int(row["memory_valid"], 0) == int(row["memory_bp"], 0) == 1
            for row in idx8_rows
        )
    )
    observer_mapping_escape = (
        "mse_mem_idx_src_id[4][1] == 7" in observer_text
        and observer_text.count("iga2se_mem_inport[4][7]") >= 1
        and all(int(row["src_is_pe7"], 0) == 0 and int(row["select_eq"], 0) == 0 for row in select_rows)
        and len(source7_rows) == 128
    )
    current_mapping_formula = (
        12 + 1 == 13
        and "`define MSE_SRC_LC_NUM                     12"
        in (ROOT / "NDP_copy01/rtl/includes/NDP_Parameters.svh").read_text(encoding="utf-8")
        and "localparam int SRC_PE_IDX = 2*(MSE_IDX + SRC_PE_OFFSET[SRC_PE_OFFSET_IDX])"
        in (ROOT / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv").read_text(encoding="utf-8")
    )
    interrupted = run_status == 125 and signal_status == "INT"
    qualified_stall = (
        public.get("valid") is True
        and public.get("status") == "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
        and public["observer"]["event_counts"]
        == {"SA_IN_ACCEPT": 30, "SA_OUT_ACCEPT": 5, "MSE4_INDEX_ACCEPT": 3}
        and buffer5.get("valid") is True
        and int(buffer5["last"]["sa_accept"]) == 5
        and int(buffer5["last"]["blocked_cycles"]) > 1_000_000
        and triggered.get("valid") is True
        and triggered["observer"]["natural_slice_finish_observed"] is False
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    memory_leaf = identity.get("leaves", {}).get("Memory_AG_Idx_Queue.sv", {})
    connect_leaf = identity.get("leaves", {}).get("Stream_Engine_Connect.sv", {})

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and sha256(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_root_path_safe": not return_errors,
        "source_crc_root_path_safe": not source_errors,
        "return_exact_set": set(records) == expected,
        "return_manifest_records_exact": not declared_mismatch,
        "return_allowlist_exact": set(records) == allowed_set and not allowed_mismatch,
        "source_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": (
            returned_source_manifest == source_payloads["package_manifest.json"]
            and manifest["source_package_manifest_sha256"] == common.digest(returned_source_manifest)
        ),
        "per_execution_unique_return_valid": unique_return,
        "package_install_observer_preflights_valid": (
            package_preflight["valid"] is True and install_preflight["valid"] is True
            and observer_preflight["valid"] is True and path_budget["valid"] is True
            and path_budget["longest_projected_relative_path_chars"]
            == len(path_budget["longest_projected_relative_path"])
            == path_budget["max_projected_relative_path_chars"]
        ),
        "install_only_root_gate_valid": (
            root_gate["valid"] is True and root_gate["ndp_root_toplevel_unchanged"] is True
            and layout["all_package_owned_paths_under_install"] is True
            and layout["root_exact_set_unchanged"] is True
            and layout["unknown_items_deleted_or_overwritten"] is False
        ),
        "p24_production_compile_pass": compile_success,
        "simulation_and_select_port_started": simulation_started,
        "external_int_after_qualified_stall": interrupted and qualified_stall,
        "configured_src13_and_connect_memory_boundary": public_boundary,
        "p24_observer_src7_mapping_escape_reproduced": observer_mapping_escape,
        "current_static_pe7_source_formula_is_13": current_mapping_formula,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p24-return-analysis-v1",
        "status": "P24_PUBLIC_BOUNDARY_PASS_OBSERVER_SOURCE_MAPPING_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_QUALIFIED_PUBLIC_BOUNDARY_WITH_PACKAGE_LOCAL_OBSERVER_MAPPING_ESCAPE" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP), "execution_identity": EXECUTION_ID,
            "unique_per_execution_basename_valid": unique_return,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
            "source_manifest_sha256": common.digest(source_payloads["package_manifest.json"]),
            "observer_sha256": common.digest(source_payloads[OBSERVER]),
        },
        "internal_receipt": {
            "return_file_count": len(records), "source_file_count": len(source_records),
            "return_errors": return_errors, "source_errors": source_errors,
            "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected),
            "manifest_record_mismatches": declared_mismatch,
            "allowlist_record_mismatches": allowed_mismatch, "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status, "run_exit_status": run_status,
            "signal_status": signal_status, "compile_succeeded": compile_success,
            "dut_simulation_started": simulation_started,
            "reported_preflight_stage": local_status["preflight_stage"],
            "external_interruption": interrupted, "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "stream_engine_connect": connect_leaf,
            "memory_ag_idx_queue": memory_leaf,
            "iga_interconnect_collected": "IGA_Interconnect.sv" in identity.get("leaves", {}),
            "causal_cone_adjudication": "identity differences are nonblocking for simulation; actual IGA interconnect identity remains required before treating the current static source formula as production proof",
        },
        "public_select_port_ledger": {
            "record_count": len(select_rows), "qualified_record_count": len(qualified_rows),
            "state_record_count": len(state_rows), "configured_src_id_counts": dict(selected_id),
            "connect_memory_idx8_accept_count": len(idx8_rows),
            "connect_memory_port_equal_all_rows": all(int(row["port_eq"], 0) == 1 for row in select_rows),
            "p24_monitored_source_id": 7, "current_formula_pe7_source_id": 13,
            "source7_rows_counted_as_progress": len(source7_rows),
            "adjudication": (
                "Configuration selects source 13. Stream_Engine_Connect and the public Memory-WR input are byte-equal, "
                "and a valid/backpressure-qualified index-8 transfer reaches that boundary. p24 nevertheless compares "
                "the selected word against unselected source 7, so select_eq=0 and its source-side progress count are not functional evidence."
            ),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "production compile/simulation pass; configured src_id=13; Connect output equals Memory-WR public input on every row and transfers index 8 once",
            "FIRST_DIVERGENCE": "p24 package-local observer hardcodes PE7 as source 7 although the current MSE4 formula maps PE7 to source 12+1=13",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_ACTUAL_PE7_SOURCE13_TO_CONNECT_EDGE",
                "classification": "PACKAGE_LOCAL_OBSERVER_SOURCE_ID_FORMULA_ESCAPE",
                "remaining_observational_equivalents": [
                    "actual production IGA_Interconnect source13 differs from current formula",
                    "source13 carries PE7 index8 but timing/qualification does not align with Connect acceptance",
                    "source13 and Connect align, localizing the unresolved stall inside actual Memory_AG consumer semantics",
                ],
                "authorized_config_fix": None, "functional_rtl_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": compile_success, "simulator_started": simulation_started,
            "c0_slice_finish": False, "natural_terminal_27_of_27": False,
            "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False, "performance_claimed": False,
            "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_MSE4_CONFIGURED_SOURCE_ID_UNKNOWN",
                "B_CONV_NATIVE_CONNECT_TO_MEMORY_WR_PUBLIC_BINDING_UNPROVEN",
                "B_CONV_NATIVE_CONNECT_INDEX8_QUALIFIED_TRANSFER_UNPROVEN",
            ],
            "opened": [
                "B_CONV_NATIVE_P24_OBSERVER_ASSUMED_PE7_SOURCE7_INSTEAD_OF_SOURCE13",
                "B_CONV_NATIVE_ACTUAL_IGA_INTERCONNECT_IDENTITY_UNCOLLECTED",
            ],
            "preserved": [
                "B_CONV_NATIVE_ACTUAL_PE7_SOURCE13_TO_CONNECT_EDGE_UNRESOLVED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": (
                "correct the public observer to source13, collect actual IGA_Interconnect identity, and retain one "
                "all-class event-mask row so PE7/source13, Connect and Memory-WR qualified edges cannot be lost"
            ),
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": sha256(ROOT / path)}
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001",
                "CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "delta": None,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
