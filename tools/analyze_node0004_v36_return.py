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


INSTALL_NAME = "r5_n4_hw_v36_b5rd_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "f98d448113aafb78c80cbab6cd002e8b783325082a79ae98cf265ffebc38bca5"
SOURCE_SHA256 = "08a7d79c50896c18665d551c32522fc39f0f90f4802a8797caa024f4ac474bc2"
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
SYNC_REPORT_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"


def q_sums(records: list[dict[str, str]], names: tuple[str, ...]) -> dict[str, int]:
    return {
        name: sum((int(item.get("q", "0"), 0) >> bit) & 1 for item in records)
        for bit, name in enumerate(names)
    }


def edge_sums(records: list[dict[str, str]]) -> dict[str, int]:
    names = (
        "row_capture",
        "row_complete",
        "row_out",
        "col_capture",
        "col_complete",
        "col_out",
        "buf_row_accept",
        "buf_col_accept",
        "buf_match_rise",
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
    sync_report = args.sync_report.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    sync_sha = sha256_file(sync_report)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    if sync_sha != SYNC_REPORT_SHA256:
        errors.append("RTL sync report SHA mismatch")
    sidecar_valid = (
        source_sidecar.read_text(encoding="ascii").strip()
        == f"{source_sha}  {source_zip.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors += return_errors + source_errors
    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
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
    return_exact = set(entries) == expected
    if not return_exact:
        errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    return_binding = (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
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

    canonical = parse_kv_record(observer, "CANONICAL_DIAG_DECISION_V1")
    row_edges = parse_kv_record(observer, "ROWLC4_BUFAG_EDGE_V1")
    row_boundary = parse_kv_record(observer, "ROWLC4_BUFAG_BOUNDARY_V1")
    b5_edges = parse_kv_record(observer, "B5RD_EDGE_V1")
    b5_boundary = parse_kv_record(observer, "B5RD_BOUNDARY_V1")
    row_counts = edge_sums(row_edges)
    b5_counts = q_sums(
        b5_edges,
        (
            "rd_request_accept",
            "cluster_accept",
            "buffer_accept",
            "rvalid_rise",
            "rd_buffer_pop",
        ),
    )
    row_final = row_boundary[0] if len(row_boundary) == 1 else {}
    b5_final = b5_boundary[0] if len(b5_boundary) == 1 else {}
    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    compile_clean = (
        compile_status == 0
        and ("0 error(s)" in compile_log or "0 errors" in compile_log)
        and "elaboration done" in compile_log
    )
    source_observer = source.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    observer_sha = sha256_bytes(
        source.get("tb_probe/native_return_observer.svh", b"")
    )
    old_qualification_fixed = all(
        token in source_observer
        for token in (
            "return_obs_rb_buf_match_prev",
            "!return_obs_rb_buf_match_prev",
        )
    )
    snapshot_gate_fixed = (
        source_observer.count(
            'return_obs_write_rowlc4_bufag_state("DIAG_DECISION");'
        )
        == 1
        and source_observer.count(
            'return_obs_write_b5rd_state("DIAG_DECISION");'
        )
        == 1
        and len(row_boundary) == 1
        and len(b5_boundary) == 1
    )
    five_candidates_closed = (
        int(b5_final.get("rd_req_accept", "0")) == 35
        and int(b5_final.get("cluster_accept", "0")) == 35
        and int(b5_final.get("buffer_accept", "0")) == 35
        and int(b5_final.get("rd_pop", "0")) == 35
        and int(b5_final.get("rvalid_rise", "0")) == 1
        and len(b5_edges) < 96
    )
    prepared_stall = (
        row_final.get("prepared_count") == "32"
        and row_final.get("prepared_vld") == "1"
        and row_final.get("prepared_bp") == "0"
        and row_final.get("wr_ready") == "0"
        and row_final.get("rd_count") == "2"
        and row_final.get("rd_full") == "1"
    )
    actual_compile_commit_tokens = sorted(
        set(re.findall(r"\b[0-9a-f]{40}\b", compile_log + "\n" + compile_driver))
    )
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and natural_terminal
        and gate.get("formal_readback_claimed") is True
        and len(formal_members) == 320
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )
    checks = {
        "return_crc_path_root": not return_errors,
        "return_exact_set_allowlist_receipts": (
            return_exact and all(receipts.values())
        ),
        "return_source_manifest_binding": return_binding,
        "source_crc_path_root": not source_errors,
        "source_manifest_exact_set": source_exact,
        "package_preflight": package_preflight.get("valid") is True,
        "install_preflight": install_preflight.get("valid") is True,
        "runtime_d_absent": (
            install_preflight.get("runtime_d_initially_absent") is True
        ),
        "observer_identity": (
            observer_preflight.get("valid") is True
            and observer_preflight.get("identity_match") is True
            and observer_preflight.get("observed_sha256") == observer_sha
        ),
        "compile_run_signal": (
            compile_status == 0 and run_status == 0 and signal == "NONE"
        ),
        "compile_elaboration_clean": compile_clean,
        "observer_compile_binding": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
            and f"/{INSTALL_NAME}/tb_probe" in compile_driver
        ),
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_OBS_ROWLC4_BUFAG",
                "+RETURN_OBS_B5RD",
                "+RETURN_OBS_B5RD_LIMIT=96",
            )
        ),
        "feature_binding": feature_binding.get("valid") is True,
        "canonical_unique": len(canonical) == 1,
        "v35_event_qualification_fixed": old_qualification_fixed,
        "v35_snapshot_gate_fixed": snapshot_gate_fixed,
        "five_candidate_path_fully_accepted": five_candidates_closed,
        "prepared_data_drain_stall": prepared_stall,
    }
    if not all(checks.values()):
        errors.append("qualified v36 evidence differs")

    report: dict[str, Any] = {
        "schema": "node0004-v36-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "V35_OBSERVER_DEFECTS_CLOSED_DUT_BOUNDARY_ADVANCED",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": (
                    "CDA-SERVER-RETURN-TRANSPORT-"
                    "USER-ATTESTED-NO-SIDECAR-001"
                ),
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_sha256": sha256_file(source_sidecar),
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": return_meta,
            "source_meta": source_meta,
            "checks": checks,
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
            "rowlc4_edge_records": len(row_edges),
            "rowlc4_edge_sums": row_counts,
            "rowlc4_final": row_final,
            "b5rd_edge_records": len(b5_edges),
            "b5rd_edge_sums": b5_counts,
            "b5rd_final": b5_final,
            "evidence_dominance": (
                "mrm2se_rvalid has one rising edge because it remains asserted "
                "through the burst; 35 qualified RD_Buffer_AG pops prove 35 "
                "returned data transactions and dominate rise-count state."
            ),
        },
        "v35_observer_defect_closure": {
            "level_as_transaction": "CLOSED",
            "canonical_snapshot_parent_gate": "CLOSED",
            "evidence": {
                "buf_match_qualified_rises": int(
                    row_final.get("buf_match", "0")
                ),
                "rowlc4_boundary_records": len(row_boundary),
                "b5rd_boundary_records": len(b5_boundary),
            },
        },
        "candidate_adjudication": {
            "WRONG_MSE_PINGPONG_SELECTION": "FALSE_BY_DOWNSTREAM_ACCEPT",
            "STREAM_ENGINE_CLUSTER_MAPPING": "FALSE_35_CLUSTER_ACCEPTS",
            "BUFFER5_MRM_DECODE_OR_READY": "FALSE_35_BUFFER_ACCEPTS",
            "BUFFER5_VALID_BANK_OR_ADDRESS": (
                "FALSE_35_ACCEPTS_WITH_READY_BANKS_AND_ADVANCING_ADDRESSES"
            ),
            "BUFFER5_READ_RETURN": (
                "FALSE_35_QUALIFIED_RD_BUFFER_POPS_AFTER_RETURN_VALID"
            ),
        },
        "LAST_PROVEN_GOOD": (
            "BUFFER5_SELECTED_READ_REQUEST_ACCEPTED_THROUGH_CLUSTER_MRM_BANK_"
            "AND_RETURNED_TO_MSE_WITH_35_QUALIFIED_RD_BUFFER_POPS"
        ),
        "FIRST_DIVERGENCE": (
            "WR_DATA_CHANNEL_PREPARED_FIFO_REACHES_COUNT32_BACKPRESSURE_WITH_"
            "NO_OBSERVED_PREPARED_TO_OUTPUT_DRAIN_CAUSE"
        ),
        "HANG_ROOT_CAUSE": {
            "status": (
                "UNRESOLVED_AFTER_V36_FIVE_CANDIDATES_EXCLUDED;"
                " NEXT_BOUNDARY_IS_WR_DATA_PREPARED_TO_OUTPUT_AND_DATAHUB_DRAIN"
            ),
            "refined_boundary": (
                "Buffer5 request, bank accept, return and RD_Buffer_AG pop all "
                "work. Prepared data then accumulates to 32, deasserts "
                "wr_chl_prepared_data_bp_pre and wr_data_chl_ready, and refills "
                "RD_Buffer_AG to full. v36 does not enable the DWRITE_PATH or "
                "DATAHUB_DRAIN features needed to distinguish descriptor queue, "
                "mask dependency, output-buffer selection/backpressure and hub "
                "write acceptance."
            ),
            "remaining_candidates": [
                "WR descriptor queue empty or descriptor/data count mismatch",
                "masked-write old-data dependency not available",
                "selected WR output channel not writable or selector stale",
                "WR output buffer full because DataHub write-data ready is low",
                "DataHub head/grant/bank match prevents write-data acceptance",
            ],
            "functional_rtl_defect_claimed": False,
            "configuration_fix_claimed": False,
        },
        "compile_source_identity": {
            "actual_compile_paths_recorded": True,
            "actual_compile_commit_tokens": actual_compile_commit_tokens,
            "actual_compile_commit_recorded": bool(
                actual_compile_commit_tokens
            ),
            "server_baseline_user_attested_commit": CURRENT_RTL_COMMIT,
            "claim_boundary": (
                "The return proves successful compilation of recorded paths but "
                "does not record a Git commit. e1fb0f7 remains the user-attested "
                "server baseline and cannot substitute for E3/E4/E5."
            ),
        },
        "current_local_rtl_identity": {
            "commit": CURRENT_RTL_COMMIT,
            "sync_report": str(sync_report),
            "sync_report_sha256": sync_sha,
            "server_run_rtl_identity_formally_bound": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V35_ROWLC4_OBSERVER_EVENT_AND_SNAPSHOT_BINDING",
                "B_CONV_NODE0004_BUFFER5_READ_REQUEST_READY_AND_RETURN_PATH_UNOBSERVED",
            ],
            "opened": (
                "B_CONV_NODE0004_WR_DATA_PREPARED_TO_OUTPUT_AND_DATAHUB_DRAIN_UNOBSERVED"
            ),
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "successor_requirement": {
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "required_features": [
                "RETURN_OBS_DWRITE_PATH",
                "RETURN_OBS_DATAHUB_DRAIN",
                "qualified prepared/descriptor/output selector state",
            ],
            "execution_slice": (
                "retain frozen cumulative c0 prefix; no approved checkpoint can "
                "recreate prepared-data/full state"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "rule_ids": [
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": (
                "Qualified downstream accepts close all five v36 candidates; "
                "rise-only state does not override 35 accepted pops. Existing "
                "rules require one successor to cover all remaining prepared/"
                "output/DataHub candidates."
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
