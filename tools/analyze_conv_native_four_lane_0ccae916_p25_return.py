#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p25 return."""

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
PACKAGE_ID = "r5_n4_0cc_p25_pe7src13"
EXECUTION_ID = "r1786206206960470201_4177943"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p25_pe7src13_"
    r"r1786206206960470201_4177943_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_016_259
RETURN_SHA256 = "41f74570a7455c855a56ada6318e5cce6a47f6ba0d128acb4c61be41d05c572b"
SOURCE_BYTES = 5_882_004
SOURCE_SHA256 = "d2c0e853391f012273e6d6bb2e07c6e3bcbee0d895db5b866c77526c580390e6"
OBSERVER = "tb_probe/native_return_observer.svh"
EXPECTED_OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p25_return_analysis/report.json"
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
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


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
    feature = json.loads(payloads["evidence/feature_binding/c0.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    publication = json.loads(payloads["evidence/publication_preflight.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
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
        path: row for path, row in source_records.items()
        if path != "package_manifest.json"
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
        and observer_text.count("p25 PE7_SOURCE13_BEGIN") == 1
        and observer_text.count("p23 EPOCH_FLOW_ACTUAL_CONSUMER_BEGIN") == 1
    )
    simulation_started = (
        "+RETURN_OBS_SELECT_PORT" in simulator_argv
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and "feature=RETURN_OBS_SELECT_PORT enabled=1" in observer_log
        and feature.get("valid") is True
    )
    rows = [
        kv(line.split("|", 2)[-1])
        for line in observer_log.splitlines()
        if "PUBLIC_PE7_SOURCE13_V2 | kind=" in line
    ]
    qualified = [row for row in rows if row["kind"] == "1"]
    state = [row for row in rows if row["kind"] == "2"]
    all_class = [
        row for row in qualified
        if int(row["event_mask"], 16) == 7
        and int(row["src_id"], 0) == 13
        and int(row["src_is_pe7"], 0) == 1
        and int(row["pe7_valid"], 0) == int(row["pe7_bp"], 0) == 1
        and int(row["connect_valid"], 0) == int(row["connect_bp"], 0) == 1
        and int(row["memory_valid"], 0) == int(row["memory_bp"], 0) == 1
        and int(row["connect_idx"], 16) == int(row["memory_idx"], 16) == 8
        and int(row["select_eq"], 0) == int(row["port_eq"], 0) == 1
    ]
    selected = collections.Counter(int(row["src_id"], 0) for row in rows)
    public_chain_pass = (
        len(rows) == 3 and len(qualified) == 1 and len(state) == 2
        and len(all_class) == 1 and selected == collections.Counter({13: 3})
        and all(int(row["port_eq"], 0) == int(row["select_eq"], 0) == 1 for row in rows)
    )
    epoch_flow_present_but_disabled = (
        "RETURN_OBS_EPOCH_FLOW" in observer_text
        and "+RETURN_OBS_EPOCH_FLOW" not in simulator_argv
        and "feature=RETURN_OBS_EPOCH_FLOW enabled=1" not in observer_log
        and not any("EPOCH_FLOW_V1 |" in line for line in observer_log.splitlines())
    )
    leaves = identity.get("leaves", {})
    iga = leaves.get("IGA_Interconnect.sv", {})
    connect = leaves.get("Stream_Engine_Connect.sv", {})
    wr = leaves.get("Memory_WR_Stream_Engine.sv", {})
    memory_ag = leaves.get("Memory_AG_Idx_Queue.sv", {})
    actual_public_cone = (
        identity.get("collection_valid") is True
        and iga.get("sha256") == "f46f68b1eb1edc2a4ff85ce6894b8f549727512f9d3e6527d6954d7bb352c82e"
        and connect.get("sha256") == "0ca375c4af56f7f6fe9e7055a39ac7370d91e6048b2aa9f3ae0a4910deae5425"
        and wr.get("sha256") == "c97a5b4a3587384d5b57b2a5db288a44b2166584c236307c69d26bb04f389127"
        and all(row.get("matches_cloud_authority") is True for row in (iga, connect, wr))
    )
    memory_ag_risk = (
        memory_ag.get("sha256") == "2f534813b8d73ff19961541b910c03b417f401d73ae98b2e446e728f384a7b3e"
        and memory_ag.get("matches_cloud_authority") is False
    )
    interrupted = run_status == 125 and signal_status == "INT"
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    qualified_stall = (
        buffer5.get("valid") is True
        and int(buffer5["last"]["sa_accept"]) == 5
        and int(buffer5["last"]["blocked_cycles"]) > 700_000
        and triggered.get("valid") is True
        and triggered["observer"]["natural_slice_finish_observed"] is False
    )

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
            payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"]
            and manifest["source_package_manifest_sha256"] == common.digest(source_payloads["package_manifest.json"])
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
        "p25_production_compile_pass": compile_success,
        "simulation_and_public_feature_started": simulation_started,
        "external_int_after_qualified_stall": interrupted and qualified_stall,
        "source13_pe7_connect_memory_chain_pass": public_chain_pass,
        "actual_iga_connect_memorywr_identity_exact": actual_public_cone,
        "actual_memory_ag_identity_risk_recorded_nonblocking": memory_ag_risk,
        "epoch_flow_present_but_runtime_disabled": epoch_flow_present_but_disabled,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p25-return-analysis-v1",
        "status": "P25_SOURCE13_PUBLIC_CHAIN_PASS_MEMORY_AG_CONSUMER_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_QUALIFIED_PE7_SOURCE13_TO_MEMORY_WR_ACCEPT" if valid else "RETURN_VALIDATION_FAILED",
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
            "dut_simulation_started": simulation_started, "external_interruption": interrupted,
            "natural_terminal": False, "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "iga_interconnect": iga, "stream_engine_connect": connect,
            "memory_wr_stream_engine": wr, "memory_ag_idx_queue": memory_ag,
            "causal_cone_adjudication": (
                "Actual IGA, Connect and Memory-WR bytes match the bound authority and the dynamic public chain. "
                "Actual Memory_AG differs from the package cloud receipt, so its observed runtime handshake is authoritative and required next."
            ),
        },
        "public_pe7_source13_ledger": {
            "record_count": len(rows), "qualified_record_count": len(qualified),
            "state_record_count": len(state), "configured_src_id_counts": dict(selected),
            "all_class_event_mask7_count": len(all_class),
            "qualified_index": int(all_class[0]["memory_idx"], 16) if all_class else None,
            "adjudication": (
                "One edge-qualified event_mask=0x7 record proves source13 is PE7 and is accepted in the same sample "
                "as the byte-equal Connect output and Memory-WR public input carrying index 8. State rows are not counted as progress."
            ),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "production compile/simulation; actual IGA/Connect/Memory-WR identity; configured source13=PE7; "
                "same-sample source13, Connect and Memory-WR qualified index8 acceptance"
            ),
            "FIRST_DIVERGENCE": (
                "after Memory-WR public input accepts index8 and before the actual Memory_AG input-match/all-match/queue-write decision"
            ),
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_MEMORY_AG_INDEX8_MATCH_TO_QUEUE_WRITE",
                "classification": "ACTUAL_MEMORY_AG_CONSUMER_BOUNDARY_UNOBSERVED_IN_P25",
                "remaining_observational_equivalents": [
                    "another Memory_AG input, mode, keep or same/gotten predicate prevents all-match",
                    "all-match is true but actual Memory_AG queue write does not occur",
                    "queue write occurs but downstream queue read/WR Memory_AG consumption is blocked",
                ],
                "authorized_config_fix": None,
                "functional_rtl_root_cause_proven": False,
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
                "B_CONV_NATIVE_ACTUAL_IGA_INTERCONNECT_IDENTITY_UNCOLLECTED",
                "B_CONV_NATIVE_ACTUAL_PE7_SOURCE13_TO_CONNECT_EDGE_UNRESOLVED",
                "B_CONV_NATIVE_CONNECT_TO_MEMORY_WR_INDEX8_ACCEPT_UNPROVEN",
            ],
            "opened": ["B_CONV_NATIVE_P25_EPOCH_FLOW_OBSERVER_PRESENT_BUT_RUNTIME_DISABLED"],
            "preserved": [
                "B_CONV_NATIVE_ACTUAL_MEMORY_AG_INDEX8_MATCH_TO_QUEUE_WRITE_UNRESOLVED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": (
                "reuse exact p25 observer bytes and simultaneously enable RETURN_OBS_SELECT_PORT and the already compiled "
                "RETURN_OBS_EPOCH_FLOW ledger, exposing Memory_AG input masks, all-match, queue write and queue read in one run"
            ),
            "frozen": "numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/observer/timeout/RTL",
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
                "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
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
