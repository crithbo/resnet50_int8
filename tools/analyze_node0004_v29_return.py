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


INSTALL_NAME = "r5_n4_hw_v29_datahub_drain_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069"
SOURCE_SHA256 = "4537f98ea18b281aa0f42f8355d7961594bbe0d3cd5991e906d708d9273173bc"
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
    progress = parse_kv_record(observer, "PROGRESS_WINDOW")
    time0 = parse_kv_record(observer, "DIAGNOSTIC_FEATURE_ENABLE_V1")

    dynamic_checks = {
        "compile_run_signal": compile_status == 0 and run_status == 0 and signal == "NONE",
        "compile_elaboration_clean": ("0 error(s)" in compile_log or "0 errors" in compile_log) and "elaboration done" in compile_log,
        "observer_compile_binding": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver and f"/{INSTALL_NAME}/tb_probe" in compile_driver,
        "observer_runtime_binding": all(token in simulator_argv for token in ("+RETURN_OBSERVER", "+RETURN_HANG_DIAG", "+RETURN_OBS_DWRITE_PATH", "+RETURN_OBS_DATAHUB_DRAIN")),
        "feature_time0_binding": feature_binding.get("valid") is True and len(feature_binding.get("features", [])) == 6 and len(time0) == 6,
        "canonical_stall": canonical.get("decision") == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH" and canonical.get("no_progress_windows") == "4",
        "source_two_groups_stranded": dwrite.get("prepare_accept") == "16" and dwrite.get("ob_write_accept") == "14" and dwrite.get("queue_count") == "2" and dwrite.get("queue_full") == "1" and dwrite.get("wr_ready") == "0" and dwrite.get("prepared_count") == "32" and dwrite.get("slice_finish") == "0",
        "datahub_fully_drained": datahub.get("addr_in8") == "7" and datahub.get("data_in8") == "7" and datahub.get("crossbar_accept8") == "7" and datahub.get("addr_in9") == "7" and datahub.get("data_in9") == "7" and datahub.get("crossbar_accept9") == "7" and datahub.get("head_x") == "0" and datahub.get("no_bank_match") == "0" and datahub.get("queue_full8") == "0" and datahub.get("queue_full9") == "0",
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v29 evidence differs")

    formal_members = [path for path in entries if "/D/" in path or "matrix_D_" in path]
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    joint_gate = compile_status == 0 and run_status == 0 and signal == "NONE" and natural_terminal and formal_claimed and len(formal_members) == 320 and gate.get("e4_claimed") is True and gate.get("e5_claimed") is True
    observer_sha = sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
    sync_report = json.loads(sync_report_path.read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "schema": "node0004-v29-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LONG_RUNNING_HANG_REFINED_TO_MSE4_DESCRIPTOR_TO_WR_DATA_CHANNEL_BOUNDARY",
            "return_zip": {"path": str(return_zip), "bytes": return_zip.stat().st_size, "sha256": return_sha},
            "external_sidecar": {"present": False, "blocker": False, "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"},
            "source_zip": {"path": str(source_zip), "bytes": source_zip.stat().st_size, "sha256": source_sha, "sidecar_bytes": source_sidecar.stat().st_size, "sidecar_sha256": sha256_file(source_sidecar), "sidecar_valid": source_sidecar_valid},
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
            "observer_identity_valid": observer_preflight.get("valid") is True and observer_preflight.get("identity_match") is True and observer_preflight.get("observed_sha256") == observer_sha,
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
        "qualified_evidence": {"canonical": canonical, "progress_windows": progress, "dwrite_boundary": dwrite, "datahub_boundary": datahub, "dynamic_checks": dynamic_checks},
        "LAST_PROVEN_GOOD": "MSE4_DATAHUB_LOCAL_CHANNELS_8_9_EACH_ACCEPTED_ALL_7_ADDRESS_DATA_PAIRS_THROUGH_BANK_CROSSBAR_AND_DRAINED",
        "FIRST_DIVERGENCE": "MSE4_WR_MEMORY_DESCRIPTOR_TO_WR_DATA_CHANNEL_RELEASE_OF_FINAL_TWO_PREPARED_GROUPS",
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_EXHAUSTIVE_V29_BOUNDARY",
            "excluded": ["DataHub local queue ingress imbalance", "DataHub head X address", "DataHub bank-match absence", "DataHub crossbar-ready starvation", "DataHub residual queue-full", "old SA outbuffer occupancy claim", "transout terminal-ignore threshold"],
            "evidence": "16 qualified prepared groups, 14 WR_Data_Channel output writes, 14 sink accepts, two prepared groups resident with prepared_count=32 and RD_Buffer_AG queue_count=2/full=1",
            "missing_unique_boundary": "WR_Memory_AG transfer descriptor handshake -> WR_Data_Channel descriptor FIFO push/pop/head -> prepared-data eligibility -> output-buffer write/read",
            "candidate_causes": ["WR_Memory_AG stops issuing descriptors before the final two prepared groups", "descriptor FIFO loses or consumes a descriptor without a matching output write", "descriptor exists but prepared-data or alternating output-buffer eligibility blocks release"],
            "functional_rtl_defect_claimed": False,
        },
        "current_local_rtl_identity": {
            "commit": CURRENT_RTL_COMMIT,
            "sync_report": str(sync_report_path),
            "sync_report_sha256": sync_sha,
            "report_valid": sync_report.get("status") == "SOURCE_SYNC_PASS_FUNCTIONAL_REPAIR_NOT_CLOSED",
            "server_run_rtl_identity_bound": False,
            "claim_boundary": "successor local source binding only; v29 server execution retains its returned unbound RTL evidence",
        },
        "BLOCKER_DELTA": {
            "closed": ["B_CONV_NODE0004_DATAHUB_LOCAL_WRITE_QUEUE_TO_BANK_DRAIN_UNOBSERVED"],
            "opened": "B_CONV_NODE0004_MSE4_DESCRIPTOR_TO_WR_DATA_CHANNEL_FINAL_TWO_GROUPS_UNOBSERVED",
            "preserved": ["B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL", "B_CONV_NODE0004_FORMAL_D_320"],
            "invalidated_not_reopened": "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED",
        },
        "scope": {"numeric_analysis_repeated": False, "node0004_workload_rebuilt": False, "configuration_analysis_repeated": False, "functional_rtl_modified": False, "server_action": False},
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
