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


INSTALL_NAME = "r5_n4_hw_v30_mse4_descriptor_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "cad26c94a8f16ee290b8dfd519f4eabad76873b933f3193e281fedd0b061b94f"
SOURCE_SHA256 = "0c358f254cac4128a7a320a4201a50f266f1620105fd9b859cf26ac84aa6ad81"
CURRENT_RTL_COMMIT = "d0aa87f682880a260fb792aaac88f70a23aba414"
SYNC_REPORT_SHA256 = "fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771"


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
        errors.append("RTL sync report SHA mismatch")
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
    receipt_valid: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipt_valid[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipt_valid[path]:
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
        and all(path in source and sha256_bytes(source[path]) == digest for path, digest in source_files.items())
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
    observer = entries.get("runs/c0/return_observer.log", b"").decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode("utf-8", errors="replace")
    compile_log = entries.get("runs/compile/sim_results/compile.log", b"").decode("utf-8", errors="replace")
    compile_driver = entries.get("runs/compile/sim_results/compile_driver.log", b"").decode("utf-8", errors="replace")
    simulator_argv = entries.get("runs/c0/simulator_argv.txt", b"").decode("utf-8", errors="replace")

    canonical = one(parse_kv_record(observer, "CANONICAL_DIAG_DECISION_V1"), "canonical", errors)
    dwrite = one(
        [r for r in parse_kv_record(observer, "DWRITE_PATH_BOUNDARY_V1") if r.get("event") == "DIAG_DECISION"],
        "D-write boundary",
        errors,
    )
    datahub = one(
        [r for r in parse_kv_record(observer, "DATAHUB_DRAIN_BOUNDARY_V1") if r.get("event") == "DIAG_DECISION"],
        "DataHub boundary",
        errors,
    )
    mse4 = one(
        [r for r in parse_kv_record(observer, "MSE4_DESCRIPTOR_BOUNDARY_V1") if r.get("event") == "DIAG_DECISION"],
        "MSE4 descriptor boundary",
        errors,
    )
    progress = parse_kv_record(observer, "PROGRESS_WINDOW")
    time0 = parse_kv_record(observer, "DIAGNOSTIC_FEATURE_ENABLE_V1")

    dynamic_checks = {
        "compile_run_signal": compile_status == 0 and run_status == 0 and signal == "NONE",
        "compile_elaboration_clean": ("0 error(s)" in compile_log or "0 errors" in compile_log) and "elaboration done" in compile_log,
        "observer_compile_binding": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver and f"/{INSTALL_NAME}/tb_probe" in compile_driver,
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_DWRITE_PATH",
                "+RETURN_OBS_DATAHUB_DRAIN",
                "+RETURN_OBS_MSE4_DESCRIPTOR",
            )
        ),
        "feature_time0_binding": feature_binding.get("valid") is True and len(feature_binding.get("features", [])) == 7 and len(time0) == 7,
        "canonical_stall": canonical.get("decision") == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH" and canonical.get("no_progress_windows") == "4",
        "prepared_vs_descriptor_delta_two": mse4.get("prepared_wr") == "16" and mse4.get("prepared_rd") == "14" and mse4.get("desc_hs") == "14",
        "descriptor_fifo_conserves_all_generated": mse4.get("fifo_push") == "14" and mse4.get("fifo_pop") == "14" and mse4.get("desc_count") == "0" and mse4.get("desc_empty") == "1",
        "descriptor_to_memory_and_output_conserves": mse4.get("mem_req0") == "14" and mse4.get("mem_req1") == "14" and mse4.get("ob_wr0") == "7" and mse4.get("ob_wr1") == "7" and mse4.get("ob_rd0") == "7" and mse4.get("ob_rd1") == "7",
        "prepared_full_descriptor_pipeline_idle": mse4.get("prepared_count") == "32" and mse4.get("prepared_vld") == "1" and mse4.get("prepared_bp") == "0" and mse4.get("trans_valid") == "0" and mse4.get("ob_vld") == "0x0" and mse4.get("wr_ready") == "0",
        "datahub_fully_drained": datahub.get("crossbar_accept8") == "7" and datahub.get("crossbar_accept9") == "7" and datahub.get("queue_full8") == "0" and datahub.get("queue_full9") == "0",
        "dwrite_correlates": dwrite.get("prepare_accept") == "16" and dwrite.get("ob_write_accept") == "14" and dwrite.get("wdata_accept") == "16" and dwrite.get("queue_count") == "2",
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v30 evidence differs")

    formal_members = [path for path in entries if "/D/" in path or "matrix_D_" in path]
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
    observer_sha = sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
    sync_report = json.loads(sync_report_path.read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "schema": "node0004-v30-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LONG_RUNNING_HANG_REFINED_TO_MSE4_MEMORY_INDEX_TO_DESCRIPTOR_GENERATION_BOUNDARY",
            "return_zip": {"path": str(return_zip), "bytes": return_zip.stat().st_size, "sha256": return_sha},
            "external_sidecar": {"present": False, "blocker": False, "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"},
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
            "return_exact_set_allowlist_valid": exact_set and all(receipt_valid.values()),
            "return_manifest_source_binding_valid": return_binding,
            "source_crc_path_root_valid": not source_errors,
            "source_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "install_preflight_valid": install_preflight.get("valid") is True,
            "runtime_d_initially_absent": install_preflight.get("runtime_d_initially_absent") is True,
            "observer_identity_valid": observer_preflight.get("valid") is True
            and observer_preflight.get("identity_match") is True
            and observer_preflight.get("observed_sha256") == observer_sha,
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
            "datahub_boundary": datahub,
            "mse4_descriptor_boundary": mse4,
            "dynamic_checks": dynamic_checks,
        },
        "LAST_PROVEN_GOOD": "MSE4_ALL_14_GENERATED_DESCRIPTORS_PUSHED_POPPED_AND_CONSERVED_THROUGH_BOTH_MEMORY_REQUESTS_AND_ALTERNATING_OUTPUT_BUFFERS",
        "FIRST_DIVERGENCE": "MSE4_MEMORY_INDEX_MATCH_QUEUE_TO_WR_MEMORY_AG_GENERATION_OF_FINAL_TWO_DESCRIPTORS_FOR_ALREADY_PREPARED_GROUPS",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_EXHAUSTIVE_V30_BOUNDARY",
            "excluded": [
                "WR descriptor FIFO loss",
                "WR descriptor premature pop without matching output write",
                "prepared-data eligibility for an existing descriptor",
                "alternating output-buffer eligibility for an existing descriptor",
                "DataHub channel drain",
                "old SA outbuffer occupancy claim",
                "transout terminal-ignore threshold",
            ],
            "evidence": "16 prepared groups entered WR_Data_Channel, but WR_Memory_AG emitted only 14 descriptors; all 14 were conserved one-for-one through FIFO, two memory requests, prepared reads, and alternating output-buffer writes/reads; final descriptor pipeline and FIFO are empty while two prepared groups remain.",
            "static_risk": "The frozen configuration derives stream4 memory index PE1 and buffer GROUP4 from the same LC15->LC9 chain, while RTL fanout uses AND-backpressure. A full prepared path can therefore stop the shared loop source before the descriptor path catches up. v30 did not observe Memory_AG_Idx_Queue ingress/match/push/pop or WR_Memory_AG pipeline stages, so source starvation versus queue/pipeline loss is not yet uniquely dynamic.",
            "missing_unique_boundary": "Memory_AG_Idx_Queue per-input accepted/matched/push/pop plus WR_Memory_AG transaction-bias/transaction/finish stages and shared LC9/PE1/buffer backpressure",
            "candidate_causes": [
                "shared LC9/LC15 backpressure starves PE1 memory-index output after prepared path reaches its threshold",
                "Memory_AG_Idx_Queue fails to match or enqueue the final two address tuples",
                "WR_Memory_AG drops/stalls final matched tuples before descriptor handshake",
            ],
            "functional_rtl_defect_claimed": False,
        },
        "current_local_rtl_identity": {
            "commit": CURRENT_RTL_COMMIT,
            "sync_report": str(sync_report_path),
            "sync_report_sha256": sync_sha,
            "report_valid": sync_report.get("status") == "SOURCE_SYNC_PASS_FUNCTIONAL_REPAIR_NOT_CLOSED",
            "server_run_rtl_identity_bound": False,
            "claim_boundary": "successor local source binding only; v30 server execution retains its returned unbound RTL evidence",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_MSE4_DESCRIPTOR_TO_WR_DATA_FINAL_TWO_GROUPS_UNOBSERVED"],
            "opened": "B_CONV_NODE0004_MSE4_MEMORY_INDEX_TO_DESCRIPTOR_FINAL_TWO_GROUPS_UNOBSERVED",
            "preserved": ["B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL", "B_CONV_NODE0004_FORMAL_D_320"],
            "invalidated_not_reopened": "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED",
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
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
