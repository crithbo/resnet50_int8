from __future__ import annotations

import argparse
import json
import re
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


INSTALL_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "e8c6496c95ae618d6f85c8c89f6ca3a0f17659cbe925857d71c545d5187a84ba"
SOURCE_SHA256 = "af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd"
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
SYNC_REPORT_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"


def event_bits(records: list[dict[str, str]]) -> dict[str, int]:
    names = (
        "row_capture",
        "row_complete",
        "row_out",
        "col_capture",
        "col_complete",
        "col_out",
        "buf_row_accept",
        "buf_col_accept",
        "buf_match_level",
        "buf_push",
        "buf_pop",
        "rd_write",
        "rd_read",
    )
    return {
        name: sum((int(item.get("edge", "0"), 0) >> bit) & 1 for item in records)
        for bit, name in enumerate(names)
    }


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
    sidecar_text = source_sidecar.read_text(encoding="ascii").strip()
    source_sidecar_valid = sidecar_text == f"{source_sha}  {source_zip.name}"
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

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest = entries.get("evidence/returned_package_manifest.json", b"")
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
    sim_log = entries.get("runs/c0/sim.log", b"").decode("utf-8", errors="replace")
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    simulator_argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )

    canonical = parse_kv_record(observer, "CANONICAL_DIAG_DECISION_V1")
    rb_edges = parse_kv_record(observer, "ROWLC4_BUFAG_EDGE_V1")
    rb_boundary = parse_kv_record(observer, "ROWLC4_BUFAG_BOUNDARY_V1")
    old_boundaries = {
        name: len(parse_kv_record(observer, name))
        for name in (
            "MSE4_DESCRIPTOR_BOUNDARY_V1",
            "MSE4_INDEX_BOUNDARY_V1",
            "LC18_PE7_BOUNDARY_V1",
        )
    }
    rb_sums = event_bits(rb_edges)
    full_at = next(
        (i + 1 for i, item in enumerate(rb_edges) if item.get("bufq_full") == "1"),
        None,
    )
    non_match_only = [
        item for item in rb_edges if int(item.get("edge", "0"), 0) != 0x100
    ]
    last_meaningful_n = int(non_match_only[-1]["n"]) if non_match_only else 0
    repeated_match_only = sum(
        int(item.get("edge", "0"), 0) == 0x100 for item in rb_edges
    )
    final_state = rb_edges[-1] if rb_edges else {}
    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    compile_clean = (
        compile_status == 0
        and ("0 error(s)" in compile_log or "0 errors" in compile_log)
        and "elaboration done" in compile_log
    )
    observer_sha = sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
    source_observer = source.get("tb_probe/native_return_observer.svh", b"").decode(
        "utf-8", errors="replace"
    )
    parent_gate_bug = (
        source_observer.count(
            'if (return_obs_fr_enabled && return_obs_fd != 0) begin'
        )
        >= 1
        and "return_obs_write_rowlc4_bufag_state(event_name);" in source_observer
        and len(rb_boundary) == 0
        and all(count == 0 for count in old_boundaries.values())
    )
    level_qualification_bug = (
        "rb_buf_match = "
        in source_observer
        and rb_sums.get("buf_match_level", 0) > 100
        and repeated_match_only > 80
    )
    actual_compile_commit_tokens = sorted(
        set(re.findall(r"\b[0-9a-f]{40}\b", compile_log + "\n" + compile_driver))
    )
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

    dynamic_checks = {
        "return_internal_receipts": (
            not return_errors and exact_set and all(receipts.values()) and return_binding
        ),
        "source_binding": not source_errors and source_exact,
        "compile_run_signal": compile_status == 0 and run_status == 0 and signal == "NONE",
        "compile_elaboration_clean": compile_clean,
        "observer_compile_binding": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
            and f"/{INSTALL_NAME}/tb_probe" in compile_driver
        ),
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_ROWLC4_BUFAG",
                "+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",
            )
        ),
        "feature_binding": feature_binding.get("valid") is True,
        "canonical_unique": len(canonical) == 1,
        "rowlc_edge_budget_filled": len(rb_edges) == 128,
        "row_col_and_buffer_ag_progressed": all(
            rb_sums[key] > 0
            for key in (
                "row_capture",
                "row_complete",
                "row_out",
                "col_capture",
                "col_complete",
                "col_out",
                "buf_row_accept",
                "buf_col_accept",
                "buf_push",
                "buf_pop",
                "rd_write",
            )
        ),
        "rd_buffer_stalled_full_without_read": (
            rb_sums["rd_write"] == 2
            and rb_sums["rd_read"] == 0
            and final_state.get("rd_count") == "2"
            and final_state.get("rd_full") == "1"
            and final_state.get("wr_ready") == "1"
        ),
        "observer_level_qualification_bug": level_qualification_bug,
        "observer_boundary_parent_gate_bug": parent_gate_bug,
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v35 evidence differs")

    sync_report = json.loads(sync_report_path.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "schema": "node0004-v35-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE_WITH_REFINED_DUT_BOUNDARY",
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
            "compile_elaboration_clean": compile_clean,
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
            "canonical": canonical[0] if canonical else {},
            "rowlc4_bufag_raw_record_count": len(rb_edges),
            "rowlc4_bufag_event_sums": rb_sums,
            "first_buf_queue_full_record": full_at,
            "last_meaningful_record": last_meaningful_n,
            "repeated_match_level_only_records": repeated_match_only,
            "final_record": final_state,
            "missing_decision_snapshots": {
                "ROWLC4_BUFAG_BOUNDARY_V1": len(rb_boundary),
                **old_boundaries,
            },
            "dynamic_checks": dynamic_checks,
        },
        "LAST_PROVEN_GOOD": (
            "ROW_LC4_AND_COL_LC4_QUALIFIED_PROGRESS_THROUGH_BUFFER_AG_"
            "QUEUE_PUSH_POP_AND_TWO_RD_BUFFER_AG_WRITES"
        ),
        "FIRST_DIVERGENCE": (
            "RD_BUFFER_AG_REACHES_FULL_AFTER_TWO_WRITES_WITH_ZERO_READ_ACCEPTS_"
            "WHILE_WR_DATA_CHANNEL_READY_REMAINS_HIGH"
        ),
        "HANG_ROOT_CAUSE": {
            "status": (
                "PACKAGE_DIAGNOSTIC_EVENT_QUALIFICATION_AND_SNAPSHOT_GATING_"
                "FAILURE; DUT_ROOT_UNRESOLVED_AT_BUFFER5_READ_READY_BOUNDARY"
            ),
            "package_observer_defects": [
                {
                    "mechanism": (
                        "buf_all_idx_matched is a sustained level but v35 increments "
                        "buf_match and emits an edge record every high cycle"
                    ),
                    "dynamic_witness": {
                        "buf_match_samples": rb_sums["buf_match_level"],
                        "match_only_records": repeated_match_only,
                        "record_budget": len(rb_edges),
                        "last_meaningful_record": last_meaningful_n,
                    },
                    "rule": "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                },
                {
                    "mechanism": (
                        "decision boundary snapshot calls are nested under the "
                        "disabled RETURN_OBS_FINAL_RELEASE feature gate"
                    ),
                    "dynamic_witness": "all four DIAG_DECISION boundary records absent",
                    "rule": "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                },
            ],
            "refined_dut_boundary": (
                "ROW/COL and Buffer_AG have accepted work; RD_Buffer_AG then holds "
                "two entries, becomes full, and never observes a qualified read. "
                "RTL requires buf2mse_rreq_ready && wr_data_chl_ready for that read. "
                "wr_data_chl_ready is observed high, leaving the selected Buffer5 "
                "read-request-ready chain as the first unresolved consumer boundary."
            ),
            "remaining_candidates": [
                "MSE write-buffer ping-pong selector chooses the non-data source",
                "Stream_Engine to Buffer_Manager_Cluster mapping suppresses Buffer5 request",
                "Buffer5 Memory_Req_Manager request decode/ready suppresses acceptance",
                "Buffer5 bank-valid/strb/address readiness refuses the requested row",
                "Buffer5 accepts the read but return-valid does not reach MSE",
            ],
            "functional_rtl_defect_claimed": False,
            "config_fix_claimed": False,
        },
        "candidate_observation_matrix": {
            "WRONG_MSE_PINGPONG_SELECTION": (
                "RD_Buffer_AG request valid, selected buffer=1 constant-ready path, "
                "but Buffer5 request remains absent"
            ),
            "STREAM_ENGINE_CLUSTER_MAPPING": (
                "RD request valid and selected Buffer5, but se2mrm_req_valid[5] absent"
            ),
            "BUFFER5_MRM_DECODE_OR_READY": (
                "se2mrm_req_valid[5] asserted; mrm2buf_req_valid/ready absent"
            ),
            "BUFFER5_VALID_BANK_OR_ADDRESS": (
                "mrm2buf read request asserted; bank-valid readiness remains low"
            ),
            "BUFFER5_READ_RETURN": (
                "request accepted/clear occurs; mrm2se_rvalid or RD_Buffer_AG read absent"
            ),
        },
        "compile_source_identity": {
            "actual_compile_paths_recorded": True,
            "actual_compile_commit_tokens": actual_compile_commit_tokens,
            "actual_compile_commit_recorded": bool(actual_compile_commit_tokens),
            "server_baseline_user_attested_commit": CURRENT_RTL_COMMIT,
            "claim_boundary": (
                "v35 compile logs prove successful source-path compilation but do "
                "not record a Git commit; e1fb0f7 is therefore the user-attested "
                "server baseline, not an E3/E4/E5 substitute"
            ),
        },
        "current_local_rtl_identity": {
            "commit": CURRENT_RTL_COMMIT,
            "sync_report": str(sync_report_path),
            "sync_report_sha256": sync_sha,
            "report_status": sync_report.get("status"),
            "server_run_rtl_identity_formally_bound": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED"
            ],
            "opened": (
                "B_CONV_NODE0004_BUFFER5_READ_REQUEST_READY_AND_RETURN_PATH_UNOBSERVED"
            ),
            "package_diagnostic_blocker": (
                "B_CONV_NODE0004_V35_ROWLC4_OBSERVER_EVENT_AND_SNAPSHOT_BINDING"
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
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            ],
            "evidence": (
                "The event-qualification rule rejects the repeated high-level "
                "match samples, and the causal-slice rule rejects decision "
                "snapshots hidden behind a dropped feature. A rule delta is not "
                "needed; the v35 package implementation was noncompliant."
            ),
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
