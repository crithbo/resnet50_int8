from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_conv_native_four_lane_df23e4d_perf_v1"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_BYTES = 121_996
RETURN_SHA256 = (
    "8166c8dd85aece80714d051c7d88591f181e4bd35c5c74dc91aa90554867fd44"
)
SOURCE_BYTES = 46_027_937
SOURCE_SHA256 = (
    "5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f"
)
SOURCE_MANIFEST_SHA256 = (
    "0fb4fc098d7d7faf46bd70907b9dbec2199437eaa0191d443999097d9da6049f"
)
P4_ZIP_SHA256 = (
    "c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e"
)
P4_AUDIT_SHA256 = (
    "6a4aa8ca2719b16e62ff5c2b6e5a3684c0b3014d6d55fed60df6243d6c1f0a99"
)
CURRENT_SYNC_SHA256 = (
    "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
)
HISTORICAL_COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
CURRENT_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
EXPECTED_HISTORICAL_LEAVES = {
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
CURRENT_CHANGED_LSU_LEAVES = {
    "Array_Request_Manager.sv",
    "Buffer_AG_Idx_Queue.sv",
    "RD_Data_Channel.sv",
    "Neighbor_Out_AG.sv",
}
CANONICAL_MARKER = "N4PERF_CANONICAL_DECISION_V1"
PARSING_RE = re.compile(r"Parsing design file ['\"]([^'\"]+)['\"]")
KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^ ]+)")


def _parse_canonical(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith(CANONICAL_MARKER):
            continue
        fields = {key: value for key, value in KV_RE.findall(line)}
        fields["_line"] = line
        records.append(fields)
    return records


def _parse_host_progress(text: str) -> list[dict[str, int | str]]:
    records: list[dict[str, int | str]] = []
    for line in text.splitlines():
        fields = {key: value for key, value in KV_RE.findall(line)}
        try:
            records.append(
                {
                    "host_epoch": int(fields["host_epoch"]),
                    "run": fields["run"],
                    "observer_bytes": int(fields["observer_bytes"]),
                }
            )
        except (KeyError, ValueError):
            continue
    return records


def _record_receipt(
    entries: dict[str, bytes], record: dict[str, Any]
) -> bool:
    path = record.get("path")
    if not isinstance(path, str):
        return False
    payload = entries.get(path)
    return (
        payload is not None
        and len(payload) == record.get("size_bytes")
        and sha256_bytes(payload) == record.get("sha256")
    )


def analyze(
    return_zip: Path,
    source_zip: Path,
    p4_audit_path: Path,
    current_sync_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    return_zip = return_zip.resolve()
    source_zip = source_zip.resolve()
    p4_audit_path = p4_audit_path.resolve()
    current_sync_path = current_sync_path.resolve()

    identities = {
        "return": {
            "path": str(return_zip),
            "bytes": return_zip.stat().st_size,
            "sha256": sha256_file(return_zip),
            "expected_bytes": RETURN_BYTES,
            "expected_sha256": RETURN_SHA256,
        },
        "source_v1": {
            "path": str(source_zip),
            "bytes": source_zip.stat().st_size,
            "sha256": sha256_file(source_zip),
            "expected_bytes": SOURCE_BYTES,
            "expected_sha256": SOURCE_SHA256,
        },
        "p4_audit": {
            "path": str(p4_audit_path),
            "bytes": p4_audit_path.stat().st_size,
            "sha256": sha256_file(p4_audit_path),
            "expected_sha256": P4_AUDIT_SHA256,
        },
        "current_rtl_sync": {
            "path": str(current_sync_path),
            "bytes": current_sync_path.stat().st_size,
            "sha256": sha256_file(current_sync_path),
            "expected_sha256": CURRENT_SYNC_SHA256,
        },
    }
    for name, identity in identities.items():
        if identity["sha256"] != identity["expected_sha256"]:
            errors.append(f"{name} SHA256 differs")
    if identities["return"]["bytes"] != RETURN_BYTES:
        errors.append("return byte count differs")
    if identities["source_v1"]["bytes"] != SOURCE_BYTES:
        errors.append("source v1 byte count differs")

    entries, return_zip_errors, return_zip_meta = safe_entries(
        return_zip, RETURN_ROOT
    )
    source, source_zip_errors, source_zip_meta = safe_entries(
        source_zip, INSTALL_NAME
    )
    errors.extend(return_zip_errors)
    errors.extend(source_zip_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    if not isinstance(records, list):
        records = []
        errors.append("RETURN_ALLOWLIST records are not a list")
    allowlist_paths = [
        item.get("path") for item in records if isinstance(item.get("path"), str)
    ]
    duplicate_allowlist_paths = sorted(
        path for path, count in Counter(allowlist_paths).items() if count != 1
    )
    expected_return_set = {"RETURN_ALLOWLIST.json", *allowlist_paths}
    return_exact_set = set(entries) == expected_return_set
    allowlist_receipts = {
        str(record.get("path")): _record_receipt(entries, record)
        for record in records
    }
    if duplicate_allowlist_paths:
        errors.append("RETURN_ALLOWLIST contains duplicate paths")
    if not return_exact_set:
        errors.append("return exact-set differs from RETURN_ALLOWLIST")
    if not all(allowlist_receipts.values()):
        errors.append("one or more return allowlist receipts differ")

    records_excluding_manifest = return_manifest.get(
        "records_excluding_this_manifest", []
    )
    if not isinstance(records_excluding_manifest, list):
        records_excluding_manifest = []
        errors.append("RETURN_MANIFEST records are not a list")
    manifest_record_paths = {
        str(item.get("path")) for item in records_excluding_manifest
    }
    expected_manifest_record_paths = set(allowlist_paths) - {
        "RETURN_MANIFEST.json"
    }
    return_manifest_records_exact = (
        manifest_record_paths == expected_manifest_record_paths
        and all(_record_receipt(entries, item) for item in records_excluding_manifest)
    )
    if not return_manifest_records_exact:
        errors.append("RETURN_MANIFEST record set or receipts differ")

    returned_source_manifest = entries.get(
        "source_package/package_manifest.json", b""
    )
    source_manifest_payload = source.get("package_manifest.json", b"")
    source_manifest = json.loads(source_manifest_payload or b"{}")
    source_file_records = source_manifest.get("files", {})
    if not isinstance(source_file_records, dict):
        source_file_records = {}
        errors.append("source package files record is not an object")
    source_exact_set = set(source_file_records) == (
        set(source) - {"package_manifest.json"}
    )
    source_receipts_valid = source_exact_set and all(
        isinstance(record, dict)
        and path in source
        and len(source[path]) == record.get("size_bytes")
        and sha256_bytes(source[path]) == record.get("sha256")
        for path, record in source_file_records.items()
    )
    source_manifest_binding = (
        returned_source_manifest == source_manifest_payload
        and sha256_bytes(source_manifest_payload) == SOURCE_MANIFEST_SHA256
        and return_manifest.get("source_package_manifest_sha256")
        == SOURCE_MANIFEST_SHA256
    )
    if not source_receipts_valid:
        errors.append("source v1 exact-set or manifest receipts differ")
    if not source_manifest_binding:
        errors.append("returned source manifest is not byte-bound to source v1")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    execution_gate = gate.get("execution_gate", {})
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_precompile = load_json(
        entries, "evidence/observer_precompile.json"
    )
    identity = load_json(entries, "evidence/production_rtl_identity.json")
    compile_status = integer_entry(
        entries, "evidence/compile_exit_status.txt", 125
    )
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal_status = entries.get(
        "evidence/signal_status.txt", b"MISSING"
    ).decode("ascii", errors="replace").strip()
    compile_driver_payload = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    )
    compile_driver = compile_driver_payload.decode(
        "utf-8", errors="replace"
    )
    parsed_sources = [
        Path(match.group(1)) for match in PARSING_RE.finditer(compile_driver)
    ]
    compiled_leaf_paths: dict[str, list[str]] = {}
    independent_compile_parse_valid = True
    for basename in EXPECTED_HISTORICAL_LEAVES:
        unique = sorted(
            {str(path) for path in parsed_sources if path.name == basename}
        )
        compiled_leaf_paths[basename] = unique
        if len(unique) != 1:
            independent_compile_parse_valid = False

    identity_leaves = identity.get("leaves", {})
    identity_leaf_valid = (
        identity.get("valid") is True
        and identity.get("expected_commit") == HISTORICAL_COMMIT
        and identity.get("identity_source")
        == "actual VCS parsing receipts followed by post-compile leaf hashing"
        and identity.get("precompile_server_source_preflight") is False
        and identity.get("compile_log_sha256")
        == sha256_bytes(compile_driver_payload)
        and set(identity_leaves) == set(EXPECTED_HISTORICAL_LEAVES)
        and all(
            identity_leaves[name].get("sha256") == digest
            and identity_leaves[name].get("expected_sha256") == digest
            and identity_leaves[name].get("match") is True
            and Path(identity_leaves[name].get("compiled_path", "")).name
            == name
            for name, digest in EXPECTED_HISTORICAL_LEAVES.items()
        )
    )
    if compile_status != 0:
        errors.append("compile did not exit zero")
    if not independent_compile_parse_valid:
        errors.append("compile log does not uniquely parse all historical leaves")
    if not identity_leaf_valid:
        errors.append("actual compiled production leaf receipt differs")

    observer_text = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")
    sim_text = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    host_text = entries.get("runs/c0/host_progress.log", b"").decode(
        "utf-8", errors="replace"
    )
    simulator_argv = entries.get(
        "runs/c0/simulator_argv.txt", b""
    ).decode("utf-8", errors="replace")
    canonical = _parse_canonical(observer_text)
    host_progress = _parse_host_progress(host_text)
    progressing = [
        item for item in canonical if item.get("decision") == "STILL_PROGRESSING"
    ]
    zero_delta = [item for item in canonical if item.get("delta") == "0"]
    hang = [
        item
        for item in canonical
        if item.get("decision")
        == "LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH"
    ]
    decision_counts = dict(
        sorted(Counter(item.get("decision", "MISSING") for item in canonical).items())
    )
    last = canonical[-1] if canonical else {}
    host_elapsed_seconds = (
        int(host_progress[-1]["host_epoch"])
        - int(host_progress[0]["host_epoch"])
        if len(host_progress) >= 2
        else None
    )
    observer_binding_valid = (
        observer_precompile.get("valid") is True
        and observer_precompile.get("identity_match") is True
        and observer_precompile.get("package_tree_written") is False
        and observer_precompile.get("server_source_inspected") is False
        and observer_precompile.get("functional_rtl_modified") is False
        and "+RETURN_OBSERVER" in simulator_argv
        and "+RETURN_OBS_EXPECTED_STAGES=1" in simulator_argv
        and observer_text.count(
            "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1"
        )
        == 1
    )
    c0_stall_witness_valid = (
        len(canonical) == 1207
        and len(progressing) == 1
        and len(hang) == 301
        and bool(zero_delta)
        and last.get("boundary") == "exec_to_slice_finish"
        and last.get("qualified_total") == "52259"
        and last.get("cfg_start") == "1"
        and last.get("cfg_finish") == "1"
        and last.get("exec_start") == "1"
        and last.get("finish") == "0"
        and last.get("req_accept") == "128"
        and last.get("rdata_accept") == "118"
        and last.get("wdata_accept") == "0"
        and last.get("bank_accept") == "52010"
        and last.get("silent_windows") == "301"
    )
    if not observer_binding_valid:
        errors.append("c0 observer compile/runtime binding differs")
    if not c0_stall_witness_valid:
        errors.append("c0 canonical stall witness differs")

    run_ids = [
        *source_manifest.get("conv_run_ids", []),
        *source_manifest.get("tail_run_ids", []),
    ]
    returned_run_ids = sorted(
        {
            path.split("/")[1]
            for path in entries
            if path.startswith("runs/") and len(path.split("/")) >= 3
            and path.split("/")[1] != "compile"
        }
    )
    natural_marker_count = sim_text.count("$finish at simulation time")
    readback_members = sorted(
        path for path in entries if path.startswith("readbacks/")
    )
    formal_checks = gate.get("checks", [])
    formal_status_counts = (
        dict(sorted(Counter(item.get("status") for item in formal_checks).items()))
        if isinstance(formal_checks, list)
        else {}
    )
    result_gate_valid_failure = (
        compile_status == 0
        and run_status == 124
        and signal_status == "NONE"
        and execution_gate.get("compile_succeeded") is True
        and execution_gate.get("all_simulations_exited_zero") is False
        and execution_gate.get("natural_terminal_count") == 0
        and execution_gate.get("required_natural_terminal_count") == 27
        and execution_gate.get("all_natural_terminals") is False
        and execution_gate.get("production_rtl_identity_match") is True
        and execution_gate.get("formal_readback_count") == 320
        and execution_gate.get("missing_count") == 320
        and execution_gate.get("mismatch_byte_count") == 0
        and execution_gate.get("conjunction_pass") is False
        and gate.get("status") == "CONV_NATIVE_FOUR_LANE_SERVER_FAILURE"
        and gate.get("candidate_release") is False
        and len(run_ids) == 27
        and returned_run_ids == ["c0"]
        and natural_marker_count == 0
        and len(readback_members) == 0
        and len(formal_checks) == 320
        and formal_status_counts == {"missing": 320}
    )
    if not result_gate_valid_failure:
        errors.append("server result conjunction or failure receipt differs")

    preflight_valid = (
        package_preflight.get("valid") is True
        and package_preflight.get("file_count") == 832
        and package_preflight.get("readback_target_count") == 320
        and package_preflight.get("preloaded_readback_target_count") == 0
        and package_preflight.get("candidate_release") is False
        and package_preflight.get("formal_readback_count") == 320
        and install_preflight.get("valid") is True
        and install_preflight.get("file_count") == 503
        and install_preflight.get("preloaded_readback_target_count") == 0
    )
    if not preflight_valid:
        errors.append("package/install preflight receipt differs")

    p4_audit = json.loads(p4_audit_path.read_text(encoding="utf-8"))
    workload_identity = p4_audit.get("v1_v2_workload_identity", {})
    p4_content_neutral = (
        p4_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True
        and p4_audit.get("status") == "PACKAGE_READY_NOT_RUN"
        and p4_audit.get("zip_sha256") == P4_ZIP_SHA256
        and p4_audit.get("delivery_successor_checks", {}).get(
            "v1_v2_workload_byte_identity"
        )
        is True
        and workload_identity.get("valid") is True
        and workload_identity.get("source_zip_sha256") == SOURCE_SHA256
        and workload_identity.get("file_count") == 503
        and workload_identity.get("byte_identical_count") == 449
        and workload_identity.get("install_identity_normalized_json_count")
        == 54
        and workload_identity.get("missing") == []
        and workload_identity.get("extra") == []
        and workload_identity.get("changed") == []
    )
    if not p4_content_neutral:
        errors.append("p4 content-neutral delivery relation differs")

    current_sync = json.loads(current_sync_path.read_text(encoding="utf-8"))
    current_source_baseline_valid = (
        current_sync.get("status")
        == "DIRECT_CHECKOUT_AND_NDP_COPY_SYNC_PASS"
        and current_sync.get("source_repository", {}).get("head")
        == CURRENT_COMMIT
        and current_sync.get("source_repository", {}).get("origin_master")
        == CURRENT_COMMIT
        and current_sync.get("ndp_copy_sync", {}).get("exact_match") is True
        and current_sync.get("server_identity", {}).get(
            "actual_compile_receipt_collected"
        )
        is False
    )
    if not current_source_baseline_valid:
        errors.append("current e1fb0f7 source-baseline receipt differs")

    return_integrity_pass = not errors
    report = {
        "schema": (
            "conv-native-four-lane-df23e4d-v1-formal-return-analysis-v1"
        ),
        "status": (
            "HISTORICAL_V1_DYNAMIC_FAILURE_CONSUMABLE"
            if return_integrity_pass
            else "RETURN_ANALYSIS_INVALID"
        ),
        "valid": return_integrity_pass,
        "errors": errors,
        "return_analysis": {
            "classification": (
                "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE"
                if return_integrity_pass
                else "INVALID_RETURN"
            ),
            "historical_v1_evidence_consumable": return_integrity_pass,
            "success_claim": False,
            "candidate_release": False,
            "evidence_ceiling": {
                "E2_local": True,
                "server_package_and_install_preflight": preflight_valid,
                "actual_compile_identity": identity_leaf_valid,
                "E3_natural_terminal": False,
                "E4_formal_D": False,
                "E5_independent_rerun": False,
            },
        },
        "identity": identities,
        "zip_safety": {
            "return": return_zip_meta,
            "source_v1": source_zip_meta,
            "return_allowlist_schema": allowlist.get("schema"),
            "return_manifest_schema": return_manifest.get("schema"),
            "return_exact_set": return_exact_set,
            "return_allowlist_record_count": len(records),
            "duplicate_allowlist_paths": duplicate_allowlist_paths,
            "allowlist_receipts": allowlist_receipts,
            "return_manifest_records_exact": return_manifest_records_exact,
            "source_exact_set_and_receipts": source_receipts_valid,
            "returned_source_manifest_byte_binding": source_manifest_binding,
            "external_return_sidecar": {
                "present": False,
                "waiver_scope": "external transfer receipt only",
                "internal_receipts_waived": False,
            },
        },
        "package_install_identity": {
            "install_name": source_manifest.get("install_name"),
            "run_namespace": source_manifest.get("run_namespace"),
            "return_name": source_manifest.get("return_name"),
            "candidate_class": source_manifest.get("candidate_class"),
            "candidate_release": source_manifest.get("candidate_release"),
            "run_ids": run_ids,
            "run_count": len(run_ids),
            "formal_D_count": len(source_manifest.get("readback_checks", [])),
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "preflight_valid": preflight_valid,
        },
        "actual_compile_identity": {
            "compile_exit_status": compile_status,
            "historical_expected_commit": HISTORICAL_COMMIT,
            "receipt": identity,
            "receipt_valid": identity_leaf_valid,
            "independent_compile_log_parse_valid": independent_compile_parse_valid,
            "compiled_leaf_paths": compiled_leaf_paths,
            "actual_binding": (
                "historical df23e4d production SA leaf set from the actual "
                "VCS parse log and post-compile hashes"
            ),
            "current_e1fb0f7_is_not_substituted": True,
        },
        "server_execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "returned_run_ids": returned_run_ids,
            "required_run_count": len(run_ids),
            "natural_terminal_count": natural_marker_count,
            "formal_D": {
                "expected": 320,
                "returned": len(readback_members),
                "missing": execution_gate.get("missing_count"),
                "mismatch_byte_count": execution_gate.get(
                    "mismatch_byte_count"
                ),
                "status_counts": formal_status_counts,
                "mismatch_zero_is_vacuous": True,
            },
            "joint_gate_pass": False,
            "gate_receipt_valid_failure": result_gate_valid_failure,
        },
        "c0_progress": {
            "observer_binding_valid": observer_binding_valid,
            "canonical_record_count": len(canonical),
            "decision_counts": decision_counts,
            "first_progress": progressing[0] if progressing else None,
            "first_zero_delta": zero_delta[0] if zero_delta else None,
            "first_hang_decision": hang[0] if hang else None,
            "last_canonical": last,
            "host_progress_record_count": len(host_progress),
            "host_first": host_progress[0] if host_progress else None,
            "host_last": host_progress[-1] if host_progress else None,
            "host_elapsed_seconds": host_elapsed_seconds,
            "host_elapsed_hms": (
                f"{host_elapsed_seconds // 3600:02d}:"
                f"{(host_elapsed_seconds % 3600) // 60:02d}:"
                f"{host_elapsed_seconds % 60:02d}"
                if host_elapsed_seconds is not None
                else None
            ),
            "sim_natural_terminal_marker_count": natural_marker_count,
            "stall_witness_valid": c0_stall_witness_valid,
        },
        "last_proven_good": {
            "run_id": "c0",
            "boundary": (
                "package/install preflight -> actual VCS compile -> cfg "
                "start/finish -> exec start -> first qualified window"
            ),
            "first_window": progressing[0] if progressing else None,
            "facts": {
                "cfg_start": 1,
                "cfg_finish": 1,
                "exec_start": 1,
                "slice_finish": 0,
                "local_req_accept": 128,
                "local_rdata_accept": 118,
                "local_wdata_accept": 0,
                "bank_frame_accept": 52010,
                "qualified_total": 52259,
            },
        },
        "first_divergence": {
            "boundary": "c0 exec_start -> slice_finish",
            "first_observed_zero_delta_window": (
                zero_delta[0] if zero_delta else None
            ),
            "first_canonical_hang": hang[0] if hang else None,
            "persistent_final_state": last,
            "claim_boundary": (
                "the existing aggregate observer does not identify which "
                "MSE/channel, RD-data consumer, buffer/SA boundary, or "
                "terminal consumer stopped; 128-118 must not be treated as "
                "ten outstanding reads without per-engine protocol evidence"
            ),
        },
        "hang_root_cause": {
            "status": "UNRESOLVED_AFTER_EXHAUSTIVE_RETURN_AUDIT",
            "bounded_interval": "c0 exec_start -> slice_finish",
            "excluded": [
                "package exact-set or extraction contamination",
                "package/install preflight failure",
                "compile failure",
                "observer disabled or unbound",
                "configuration never started or never finished",
                "execution never started",
                "external signal interruption",
                "natural completion with return-collection loss",
            ],
            "remaining_candidates": [
                "per-MSE request/read-data imbalance or response starvation",
                "RD_Data_Channel metadata/inbuffer/prepared-data blockage",
                "Buffer_AG/Array_Request_Manager queue or hold backpressure",
                "SA/buffer consumer starvation before output write",
                "MSE4 output request/write-data or finish propagation blockage",
            ],
        },
        "p4_adjudication": {
            "content_neutral_delivery_successor": p4_content_neutral,
            "workload_identity": workload_identity,
            "historical_dynamic_evidence_replaced": False,
            "reason": (
                "p4 replaces v1 delivery/extraction identity only. It keeps "
                "the same workload and aggregate observer, so it neither "
                "erases this actual df23e4d run nor resolves its first "
                "divergence."
            ),
        },
        "current_rtl_boundary": {
            "source_baseline": CURRENT_COMMIT,
            "source_baseline_receipt_valid": current_source_baseline_valid,
            "actual_compile_receipt_for_a_future_run": False,
            "changed_lsu_leaf_names_relevant_to_bounded_interval": sorted(
                CURRENT_CHANGED_LSU_LEAVES
            ),
            "historical_return_actual_compile_commit": HISTORICAL_COMMIT,
            "claim_boundary": (
                "the current e1fb0f7 source sync is not actual compile "
                "evidence for this historical v1 return or any future p4 run"
            ),
        },
        "successor_adjudication": {
            "fresh_successor_required": True,
            "existing_p4_sufficient_as_return_driven_diagnostic": False,
            "reason": (
                "p4 predates and preserves the coarse observer; it cannot "
                "distinguish the remaining candidates or bind the four "
                "e1fb0f7 LSU leaves changed after df23e4d"
            ),
            "required_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "required_causal_slice": "c0 only, frozen byte-for-byte",
            "required_actual_compile_identity_additions": sorted(
                CURRENT_CHANGED_LSU_LEAVES
            ),
            "required_observation": [
                "per-MSE/per-channel req, rdata and wdata handshakes",
                "all read-MSE metadata, inbuffer, prepared-data and buffer handoffs",
                "Array_Request_Manager/Buffer_AG hold, queue and backpressure",
                "SA input/output and buffer4/5 accepted events",
                "MSE4 index, request, write-data and finish propagation",
            ],
        },
        "blocker_delta": {
            "closed": [],
            "preserved": [
                "B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL",
                "B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320",
                "B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY",
            ],
            "new_diagnostic_boundary": (
                "B_CONV_NATIVE_FOUR_LANE_C0_EXEC_TO_SLICE_FINISH_STALL"
            ),
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "result": "CONFIRMED_SUFFICIENT_NO_RULE_DELTA",
            "rule_ids": [
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
                "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            ],
            "claim_boundary": (
                "historical v1 external transfer sidecar waiver, internal "
                "identity and exact-set validation, timeout adjudication, "
                "and mandatory fresh return-driven diagnostic successor"
            ),
        },
    }
    return report


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--p4-audit", required=True, type=Path)
    parser.add_argument("--current-sync-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = analyze(
            args.return_zip,
            args.source_zip,
            args.p4_audit,
            args.current_sync_report,
        )
    except Exception as error:
        print(f"return analysis failed: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
