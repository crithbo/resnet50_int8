from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    parse_kv_record,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_n4_hw_v33_lc18_pe7_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "82c1cc545d1df6a9e0359be6902c064af30d7e9631d50fcc4182177eb904105e"
SOURCE_SHA256 = "5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90"
CURRENT_RTL_COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
SYNC_REPORT_SHA256 = "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"


def one(records: list[dict[str, str]], name: str, errors: list[str]) -> dict[str, str]:
    if len(records) != 1:
        errors.append(f"{name} count differs: {len(records)}")
        return {}
    return records[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--sync-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    source_sidecar = args.source_sidecar.resolve()
    sync_report_path = args.sync_report.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    sync_sha = sha256_file(sync_report_path)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    if sync_sha != SYNC_REPORT_SHA256:
        errors.append("current RTL sync report SHA mismatch")
    source_sidecar_valid = source_sidecar.read_text(encoding="ascii").strip() == (
        f"{source_sha}  {source_zip.name}"
    )
    if not source_sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors += return_errors + source_errors
    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipts: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipts[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipts[path]:
            errors.append(f"return receipt differs: {path}")
    exact_set = set(entries) == expected
    if not exact_set:
        errors.append("return exact-set differs")

    returned_manifest = entries.get("evidence/returned_package_manifest.json", b"")
    source_manifest_payload = source.get("package_manifest.json", b"")
    return_binding = (
        return_manifest.get("install_name") == INSTALL_NAME
        and return_manifest.get("records") == records
        and returned_manifest == source_manifest_payload
    )
    if not return_binding:
        errors.append("return/source manifest binding differs")
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
        errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(entries, "evidence/diagnostic_feature_binding.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    observer = entries.get("runs/c0/return_observer.log", b"").decode(
        "utf-8", errors="replace"
    )
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    simulator_argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )

    canonical = one(
        parse_kv_record(observer, "CANONICAL_DIAG_DECISION_V1"),
        "canonical",
        errors,
    )
    dwrite = one(
        [
            item
            for item in parse_kv_record(observer, "DWRITE_PATH_BOUNDARY_V1")
            if item.get("event") == "DIAG_DECISION"
        ],
        "D-write boundary",
        errors,
    )
    descriptor = one(
        [
            item
            for item in parse_kv_record(observer, "MSE4_DESCRIPTOR_BOUNDARY_V1")
            if item.get("event") == "DIAG_DECISION"
        ],
        "MSE4 descriptor boundary",
        errors,
    )
    index = one(
        [
            item
            for item in parse_kv_record(observer, "MSE4_INDEX_BOUNDARY_V1")
            if item.get("event") == "DIAG_DECISION"
        ],
        "MSE4 index boundary",
        errors,
    )
    lcpe = one(
        [
            item
            for item in parse_kv_record(observer, "LC18_PE7_BOUNDARY_V1")
            if item.get("event") == "DIAG_DECISION"
        ],
        "LC18/PE7 boundary",
        errors,
    )
    lcpe_edges = parse_kv_record(observer, "LC18_PE7_EDGE_V1")
    progress = parse_kv_record(observer, "PROGRESS_WINDOW")
    time0 = parse_kv_record(observer, "DIAGNOSTIC_FEATURE_ENABLE_V1")

    lc18_bp = int(lcpe.get("lc18_bp", "0"), 0)
    lc18_bp_missing = [
        bit for bit in range(33) if ((lc18_bp >> bit) & 1) == 0
    ]
    edge_sums = {
        key: sum((int(item.get("edge", "0"), 0) >> bit) & 1 for item in lcpe_edges)
        for bit, key in enumerate(
            (
                "lc17_out",
                "lc18_parent",
                "lc18_out",
                "pe7_in0",
                "pe7_in2",
                "pe7_write",
                "pe7_read",
                "mse_input1",
            )
        )
    }
    dynamic_checks = {
        "compile_run_signal": (
            compile_status == 0 and run_status == 0 and signal == "NONE"
        ),
        "compile_elaboration_clean": (
            ("0 error(s)" in compile_log or "0 errors" in compile_log)
            and "elaboration done" in compile_log
        ),
        "observer_compile_binding": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
            and f"/{INSTALL_NAME}/tb_probe" in compile_driver
        ),
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_LC18_PE7",
                "+RETURN_OBS_LC18_PE7_LIMIT=96",
            )
        ),
        "feature_time0_binding": (
            feature_binding.get("valid") is True
            and len(feature_binding.get("features", [])) == 9
            and len(time0) == 9
        ),
        "canonical_stall": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and canonical.get("no_progress_windows") == "4"
        ),
        "prepared_descriptor_delta_two": (
            descriptor.get("prepared_wr") == "16"
            and descriptor.get("prepared_rd") == "14"
            and descriptor.get("desc_hs") == "14"
        ),
        "seven_index_transactions": (
            index.get("accept1") == "7"
            and index.get("match") == "7"
            and index.get("push") == "7"
            and index.get("pop") == "7"
            and index.get("finish") == "7"
            and index.get("desc") == "14"
        ),
        "pe7_path_conserves_all_seven": (
            lcpe.get("pe7_in2") == "7"
            and lcpe.get("pe7_write") == "7"
            and lcpe.get("pe7_read") == "7"
            and lcpe.get("mse_input1") == "7"
            and edge_sums["pe7_in2"] == 7
            and edge_sums["pe7_write"] == 7
            and edge_sums["pe7_read"] == 7
            and edge_sums["mse_input1"] == 7
        ),
        "lc18_global_release_stops_at_six": (
            lcpe.get("lc18_out") == "6" and edge_sums["lc18_out"] == 6
        ),
        "only_physical_row_lc4_fanout_not_ready": (
            lc18_bp_missing == [10]
            and lcpe.get("pe7_in_bp") == "0x6"
            and lcpe.get("mse_in1_bp") == "1"
        ),
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v33 evidence differs")

    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and natural_terminal
        and formal_claimed
        and len(formal_members) == 320
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )
    observer_sha = sha256_bytes(
        source.get("tb_probe/native_return_observer.svh", b"")
    )
    sync_report = json.loads(sync_report_path.read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "schema": "node0004-v33-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LONG_RUNNING_HANG_REFINED_TO_LC18_TO_ROW_LC4_FANOUT_BACKPRESSURE",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_bytes": source_sidecar.stat().st_size,
                "sidecar_sha256": sha256_file(source_sidecar),
                "sidecar_valid": source_sidecar_valid,
            },
            "return_crc_path_root_duplicate_symlink_valid": not return_errors,
            "return_meta": return_meta,
            "return_exact_set_allowlist_valid": exact_set and all(receipts.values()),
            "return_manifest_source_binding_valid": return_binding,
            "source_crc_path_root_valid": not source_errors,
            "source_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "install_preflight_valid": install_preflight.get("valid") is True,
            "runtime_d_initially_absent": (
                install_preflight.get("runtime_d_initially_absent") is True
            ),
            "observer_identity_valid": (
                observer_preflight.get("valid") is True
                and observer_preflight.get("identity_match") is True
                and observer_preflight.get("observed_sha256") == observer_sha
            ),
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "simulation_started": "[RETURN_OBSERVER] enabled" in sim_log,
            "diagnostic_finish_observed": "$finish" in sim_log,
            "natural_terminal": natural_terminal,
            "formal_d_expected": 320,
            "formal_d_present": len(formal_members),
            "formal_d_missing": 320 - len(formal_members),
            "formal_d_mismatch": 0,
            "joint_result_gate": joint_gate,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "qualified_evidence": {
            "canonical": canonical,
            "progress_windows": progress,
            "dwrite_boundary": dwrite,
            "mse4_descriptor_boundary": descriptor,
            "mse4_index_boundary": index,
            "lc18_pe7_boundary": lcpe,
            "lc18_pe7_edge_count": len(lcpe_edges),
            "lc18_pe7_edge_sums": edge_sums,
            "lc18_bp_missing_bits": lc18_bp_missing,
            "dynamic_checks": dynamic_checks,
        },
        "LAST_PROVEN_GOOD": (
            "PHYSICAL_LC18_VALUE6_ACCEPTED_BY_PE7_AND_CONSERVED_THROUGH_"
            "PE7_WRITE_READ_TO_MSE4_SEVENTH_INPUT1_ACCEPT"
        ),
        "FIRST_DIVERGENCE": (
            "PHYSICAL_LC18_VALUE6_GLOBAL_FANOUT_RELEASE_BLOCKED_ONLY_BY_"
            "PHYSICAL_ROW_LC4_BACKPRESSURE_BIT10"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_BELOW_UNIQUE_ROW_LC4_FANOUT_BOUNDARY",
            "unique_first_stop": (
                "Physical LC18 fans logical LC9 to PE7 and ROW_LC4. PE7 accepts "
                "seven values and every accepted value is conserved through "
                "PE7 write/read and MSE4 input1. LC18 itself globally releases "
                "only six values because its final fanout vector is all ones "
                "except bit10; the static interconnect maps bit10 exactly to "
                "ROW_LC4. The missing eighth MSE4 index is therefore downstream "
                "of ROW_LC4 backpressure, not the PE7/MSE index path."
            ),
            "excluded": [
                "LC18 to PE7 inport2 loss for any of the seven accepted values",
                "PE7 match/write/read loss",
                "PE7 to MSE4 input1 same/gotten loss",
                "Memory_AG_Idx_Queue or WR_Memory_AG loss after input1 accept",
                "descriptor loss after WR_Memory_AG",
                "old SA outbuffer occupancy claim",
            ],
            "not_yet_distinguished": [
                "ROW_LC4 selected-source inbuffer refuses the held LC18 value",
                "ROW_LC4 counter/outbuffer or COL_LC4 fanout cannot release",
                "WRITE_STREAM0 row-buffer input blocks ROW_LC4 because Buffer5 is full or not reusable",
                "a cyclic eligibility dependency between the final two prepared D groups and the next PE7 index",
            ],
            "why_no_config_fix": (
                "v33 records only the aggregate LC18 fanout vector and PE7 path. "
                "It uniquely names ROW_LC4 as the blocking consumer but does not "
                "observe ROW_LC4 selected input, counter/output, COL_LC4, "
                "WRITE_STREAM0 row input, or Buffer5 reuse/clear state. Changing "
                "an end/last/keep/lifetime leaf would therefore be speculative."
            ),
            "functional_rtl_defect_claimed": False,
            "next_required_boundary": (
                "one information-gain diagnostic covering LC18 per-sink accept, "
                "ROW_LC4 selected input/same/gotten and counter write/read/last, "
                "COL_LC4 accept/output, WRITE_STREAM0 row accept, and Buffer5 "
                "full/clear/reuse/prepare eligibility"
            ),
        },
        "candidate_observation_matrix": {
            "ROW_LC4_SOURCE_SELECTION_OR_SAME_GOTTEN": (
                "LC18 bit10 low; selected input valid but no fresh ROW_LC4 input capture"
            ),
            "ROW_LC4_COUNTER_OR_OUTPUT_RELEASE": (
                "fresh ROW_LC4 input capture occurs; no qualified ROW_LC4 output"
            ),
            "COL_LC4_FANOUT": (
                "ROW_LC4 output occurs; COL_LC4 input/output does not advance"
            ),
            "WRITE_STREAM0_ROW_BUFFER_OR_BUFFER5_REUSE": (
                "COL_LC4/ROW_LC4 data presented; row-buffer accept remains low "
                "with Buffer5 full/not-cleared/not-reusable"
            ),
            "CYCLIC_FINAL_FLUSH_ELIGIBILITY": (
                "two prepared groups remain, PE7/MSE index path idle, and the "
                "only blocked ROW_LC4 consumer requires those descriptors to free"
            ),
        },
        "current_local_rtl_identity": {
            "commit": CURRENT_RTL_COMMIT,
            "sync_report": str(sync_report_path),
            "sync_report_sha256": sync_sha,
            "report_valid": (
                sync_report.get("status")
                == "SOURCE_SYNC_AND_DIRECTED_EXACT_CANCELLATION_REVALIDATION_PASS"
            ),
            "server_run_rtl_identity_bound": False,
            "claim_boundary": (
                "successor local source binding only; v33 server execution "
                "retains its returned source evidence"
            ),
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_PHYSICAL_LC18_PE7_TO_MSE4_EIGHTH_BUFFER_INDEX_ACCEPT_UNOBSERVED"
            ],
            "opened": (
                "B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED"
            ),
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "rule_ids": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            ],
            "evidence": (
                "Qualified PE7/MSE events and the static LC18 fanout bit mapping "
                "move the boundary to ROW_LC4 without treating level state as a "
                "transaction. The new optimization rule directly requires the "
                "remaining low-cost discriminators to be combined into one package."
            ),
            "claim_boundary": "serialized node0004 diagnostic closure only",
        },
        "scope": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_analysis_repeated": False,
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
