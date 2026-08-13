#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p26 return."""

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
PACKAGE_ID = "r5_n4_0cc_p26_memag"
EXECUTION_ID = "r1786210539149535582_21324"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p26_memag_"
    r"r1786210539149535582_21324_return.zip"
)
SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_049_486
RETURN_SHA256 = "7e8ff498b52821d5f1bd9300bc232a18a93dd10d77916f3b144e635eff4c0937"
SOURCE_BYTES = 5_881_902
SOURCE_SHA256 = "844360af973a6687fe9b0e202e169cfe176df42000859fbd88a15b559b3cce25"
OBSERVER = "tb_probe/native_return_observer.svh"
EXPECTED_OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p26_return_analysis/report.json"
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


def timestamp(line: str) -> int:
    return int(line.split("|", 1)[0].strip())


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
    public_order = json.loads(payloads["evidence/public_order_summary.json"])
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
        and "+RETURN_OBS_EPOCH_FLOW" in simulator_argv
        and "feature=RETURN_OBS_SELECT_PORT enabled=1" in observer_log
        and "feature=RETURN_OBS_EPOCH_FLOW enabled=1" in observer_log
        and "[RETURN_OBSERVER] enabled N4D_FEATURE_ENABLE_V2" in sim_log
        and feature.get("valid") is True
    )
    public_lines = [
        line for line in observer_log.splitlines()
        if "PUBLIC_PE7_SOURCE13_V2 | kind=" in line
    ]
    public_rows = [kv(line.split("|", 2)[-1]) for line in public_lines]
    qualified = [row for row in public_rows if row["kind"] == "1"]
    state = [row for row in public_rows if row["kind"] == "2"]
    public_idx8 = [
        (timestamp(line), row)
        for line, row in zip(public_lines, public_rows)
        if row["kind"] == "1"
        and int(row["event_mask"], 16) == 7
        and int(row["src_id"], 0) == 13
        and int(row["src_is_pe7"], 0) == 1
        and int(row["connect_idx"], 16) == int(row["memory_idx"], 16) == 8
        and int(row["select_eq"], 0) == int(row["port_eq"], 0) == 1
    ]
    selected = collections.Counter(int(row["src_id"], 0) for row in public_rows)
    public_chain_pass = (
        len(public_rows) == 3 and len(qualified) == 1 and len(state) == 2
        and len(public_idx8) == 1 and selected == collections.Counter({13: 3})
    )

    epoch_lines = [
        line for line in observer_log.splitlines() if "EPOCH_FLOW_V1 |" in line
    ]
    epoch_rows = [(timestamp(line), kv(line.split("|", 2)[-1])) for line in epoch_lines]
    epoch_counts = collections.Counter(row["event"] for _, row in epoch_rows)
    qwrite = [(time, row) for time, row in epoch_rows if row["event"] == "QUEUE_WRITE"]
    qread = [(time, row) for time, row in epoch_rows if row["event"] == "QUEUE_READ"]
    buf_accept = [(time, row) for time, row in epoch_rows if row["event"] == "BUFFER_ACCEPT"]
    public_time = public_idx8[0][0] if public_idx8 else None
    memory_ag_chain_pass = bool(
        public_time is not None
        and len(qwrite) == 1 and len(qread) == 1 and len(buf_accept) >= 1
        and public_time < qwrite[0][0] < qread[0][0] < buf_accept[0][0]
        and int(qwrite[0][1]["match"], 0) == 1
        and int(qwrite[0][1]["qwr"], 0) == 1
        and int(qwrite[0][1]["qfull"], 0) == 0
        and int(qread[0][1]["qrd"], 0) == 1
        and int(qread[0][1]["qempty"], 0) == 0
        and not any(
            row["kind"] == "1" and public_time < time < qwrite[0][0]
            for time, row in zip(map(timestamp, public_lines), public_rows)
        )
    )

    leaves = identity.get("leaves", {})
    memory_ag = leaves.get("Memory_AG_Idx_Queue.sv", {})
    actual_memory_ag_bound = (
        identity.get("collection_valid") is True
        and memory_ag.get("sha256") == "2f534813b8d73ff19961541b910c03b417f401d73ae98b2e446e728f384a7b3e"
        and memory_ag.get("matches_cloud_authority") is False
    )
    interrupted = run_status == 125 and signal_status == "INT"
    buffer5_stall = (
        buffer5.get("valid") is True
        and buffer5.get("last", {}).get("arm_valid") == "0xff"
        and buffer5.get("last", {}).get("arm_ready") == "0"
        and buffer5.get("last", {}).get("sa_raw_valid") == "1"
        and buffer5.get("last", {}).get("sa_ready") == "0"
        and buffer5.get("last", {}).get("mrm_valid") == "0x0"
        and int(buffer5["last"]["blocked_cycles"]) >= 3_000_000
        and public_order.get("observer", {}).get("event_counts", {}).get("SA_OUT_ACCEPT") == 5
        and triggered.get("observer", {}).get("natural_slice_finish_observed") is False
    )
    no_formal = (
        source_manifest.get("formal_readback_count") == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
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
        "p26_production_compile_pass": compile_success,
        "simulation_both_features_started": simulation_started,
        "external_int_after_qualified_progress": interrupted and buffer5_stall,
        "source13_pe7_public_idx8_chain_pass": public_chain_pass,
        "actual_memory_ag_queue_write_read_after_idx8_pass": memory_ag_chain_pass,
        "actual_memory_ag_identity_recorded_nonblocking": actual_memory_ag_bound,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p26-return-analysis-v1",
        "status": "P26_ACTUAL_MEMORY_AG_FLOW_PASS_BUFFER5_RELEASE_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_ACTUAL_MEMORY_AG_QUEUE_WRITE_READ_WITH_BUFFER5_STALL" if valid else "RETURN_VALIDATION_FAILED",
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
            "memory_ag_idx_queue": memory_ag,
            "causal_cone_adjudication": (
                "The actual Memory_AG leaf differs from package cloud provenance, but production compile and simulation succeeded. "
                "The dynamic queue-write/read evidence therefore binds to the actual compiled leaf and remains consumable."
            ),
        },
        "qualified_d_flow": {
            "public_record_count": len(public_rows),
            "public_qualified_count": len(qualified),
            "public_state_count": len(state),
            "configured_src_id_counts": dict(selected),
            "idx8_qualified_time": public_time,
            "epoch_record_count": len(epoch_rows),
            "epoch_event_counts": dict(epoch_counts),
            "queue_write_time": qwrite[0][0] if qwrite else None,
            "queue_read_time": qread[0][0] if qread else None,
            "first_buffer_ag_accept_time": buf_accept[0][0] if buf_accept else None,
            "queue_write_snapshot": qwrite[0][1] if qwrite else None,
            "queue_read_snapshot": qread[0][1] if qread else None,
            "adjudication": (
                "The sole qualified public input event carries PE7/source13 index8 through Connect into Memory-WR. "
                "With no intervening qualified public input, the actual Memory_AG then asserts all-match/queue-write, "
                "dequeues the entry, and the downstream Buffer-AG chain accepts data. Held/state rows are not counted as progress."
            ),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "production compile/simulation; PE7 source13 index8 public acceptance; actual Memory_AG all-match queue write, "
                "queue read and downstream Buffer-AG acceptance"
            ),
            "FIRST_DIVERGENCE": (
                "after actual Memory_AG/Buffer-AG delivery and before Buffer5 frees the selected occupied row for further SA output acceptance"
            ),
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_BUFFER5_ROW_RELEASE_CHAIN",
                "classification": "BUFFER5_OCCUPIED_ROW_WITH_NO_MEMORY_REQUEST_MANAGER_READ_VISIBLE",
                "observed_final_state": buffer5["last"],
                "remaining_observational_equivalents": [
                    "Buffer5 selected-row byte-valid ownership never produces a qualified MRM read request",
                    "MRM address/mask/lifetime eligibility selects a different row or byte-set than the blocked SA write",
                    "a qualified MRM read/clear occurs but Buffer5 ready recomputation does not release the row",
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
                "B_CONV_NATIVE_P25_EPOCH_FLOW_OBSERVER_PRESENT_BUT_RUNTIME_DISABLED",
                "B_CONV_NATIVE_ACTUAL_MEMORY_AG_INDEX8_MATCH_TO_QUEUE_WRITE_UNRESOLVED",
                "B_CONV_NATIVE_ACTUAL_MEMORY_AG_QUEUE_READ_UNPROVEN",
            ],
            "opened": ["B_CONV_NATIVE_BUFFER5_SELECTED_ROW_RELEASE_CHAIN_UNRESOLVED"],
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": (
                "source-bound generated monitor over Buffer5/Buffer_Manager/Memory_Req_Manager public or module-local declarations: "
                "selected-row SA write qualification, byte-valid ownership, MRM read request/accept, clear and ready recomputation, "
                "with distinct candidate signatures and no config/numeric/RTL changes"
            ),
            "new_required_rule": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
            "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/RTL",
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
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
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
