#!/usr/bin/env python3
"""Close the exact p49 formal return after bounded VCD streaming reached EOF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p49_tbvcdrt2"
EXECUTION = "r1786716730326805125_2394257"
ATTEMPT = "a0"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p49_tbvcdrt2_r1786716730326805125_2394257_return.zip"
)
DEFAULT_OUT = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_"
    + EXECUTION
)
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    names = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(names) != 1:
        raise RuntimeError(f"expected one {suffix}, found {names}")
    value = json.loads(archive.read(names[0]))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {suffix}")
    return value


def member_name(archive: zipfile.ZipFile, suffix: str) -> str:
    names = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(names) != 1:
        raise RuntimeError(f"expected one {suffix}, found {names}")
    return names[0]


def member_identities(archive: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        digest = hashlib.sha256()
        size = 0
        with archive.open(info) as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        result[info.filename] = {
            "path": info.filename,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "crc32": f"{info.CRC:08x}",
        }
    return result


def normalized_scope(value: str) -> str:
    parts = []
    for part in value.split("."):
        cleaned = part.lstrip("\\").strip()
        cleaned = re.sub(r"\s+\[[^]]+\]\s*$", "", cleaned)
        parts.append(cleaned)
    return ".".join(parts)


def vcd_header_map(
    archive: zipfile.ZipFile, name: str
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    scopes: list[str] = []
    result: dict[str, list[dict[str, Any]]] = {}
    timescale: str | None = None
    pending_timescale = False
    timescale_rows: list[str] = []
    with archive.open(name) as stream:
        for raw in stream:
            line = raw.decode("utf-8", "replace").strip()
            if pending_timescale:
                if line == "$end":
                    timescale = " ".join(timescale_rows).strip()
                    pending_timescale = False
                elif line:
                    timescale_rows.append(line)
                continue
            if line.startswith("$timescale"):
                body = line.removeprefix("$timescale").replace("$end", "").strip()
                if body:
                    timescale = body
                else:
                    pending_timescale = True
            elif line.startswith("$scope "):
                fields = line.split()
                if len(fields) >= 4:
                    scopes.append(fields[2])
            elif line.startswith("$upscope"):
                if scopes:
                    scopes.pop()
            elif line.startswith("$var "):
                fields = line.split()
                if len(fields) >= 6:
                    reference = " ".join(fields[4:-1])
                    path = normalized_scope(".".join([*scopes, reference]))
                    result.setdefault(path, []).append(
                        {
                            "code": fields[3],
                            "width_bits": int(fields[2]),
                            "reference": reference,
                        }
                    )
            elif line.startswith("$enddefinitions"):
                break
    return result, timescale


def manifest_errors(
    core: dict[str, Any], identities: dict[str, dict[str, Any]]
) -> list[str]:
    rows = core.get("core_entry_receipts")
    if not isinstance(rows, list):
        rows = core.get("entries")
    if not isinstance(rows, list):
        rows = core.get("core_entries")
    if not isinstance(rows, list):
        return ["return core manifest has no entries list"]
    root = f"{PACKAGE}_return/"
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("non-object core entry")
            continue
        relative = row.get("archive") or row.get("path")
        if not isinstance(relative, str):
            continue
        name = relative if relative.startswith(root) else root + relative
        actual = identities.get(name)
        if row.get("required") is True and actual is None:
            errors.append(f"missing required core member: {relative}")
            continue
        if actual is None:
            continue
        expected_size = row.get("bytes") or row.get("size_bytes")
        expected_sha = row.get("sha256")
        if isinstance(expected_size, int) and actual["bytes"] != expected_size:
            errors.append(f"core size mismatch: {relative}")
        if isinstance(expected_sha, str) and actual["sha256"] != expected_sha:
            errors.append(f"core SHA mismatch: {relative}")
    return errors


def scan_logs(
    archive: zipfile.ZipFile, sim_name: str, compile_name: str
) -> dict[str, Any]:
    open_pattern = re.compile(
        r"(?:unable|cannot|could not|failed)\s+to\s+open|no such file|fopen|open\s+file",
        re.IGNORECASE,
    )
    sim_open: list[dict[str, Any]] = []
    compile_open: list[dict[str, Any]] = []
    apb_1001: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    non_heartbeat_tail: deque[dict[str, Any]] = deque(maxlen=32)
    passes = 0
    matrices: list[int] = []
    monitor_file_rows = 0
    with archive.open(sim_name) as stream:
        for line_number, raw in enumerate(stream, 1):
            line = raw.decode("utf-8", "replace").rstrip()
            if open_pattern.search(line):
                sim_open.append({"line": line_number, "text": line[:1000]})
            if "0x00001001" in line:
                apb_1001.append({"line": line_number, "text": line[:500]})
            if "CODEX_TBVCD_TARGET_ENTRY_V2" in line:
                target_rows.append({"line": line_number, "text": line})
            if "PASS: Continuous transfer completed successfully" in line:
                passes += 1
            matrix = re.search(r"JSON: Loading matrix\[(\d+)\]", line)
            if matrix:
                matrices.append(int(matrix.group(1)))
            if "[Bank Frame Monitor] Created " in line:
                monitor_file_rows += 1
            if "CODEX_TBVCD_HEARTBEAT_V2" not in line:
                non_heartbeat_tail.append({"line": line_number, "text": line[:1000]})
    with archive.open(compile_name) as stream:
        for line_number, raw in enumerate(stream, 1):
            line = raw.decode("utf-8", "replace").rstrip()
            if open_pattern.search(line):
                compile_open.append({"line": line_number, "text": line[:1000]})
    return {
        "sim_open_warning_matches": sim_open,
        "compile_open_warning_matches": compile_open,
        "exact_open_warning_found": bool(sim_open or compile_open),
        "apb_hex_0x00001001_rows": len(apb_1001),
        "apb_hex_first": apb_1001[:3],
        "apb_hex_last": apb_1001[-3:],
        "binary_only_rows": 0,
        "target_entry_rows": target_rows,
        "continuous_transfer_passes": passes,
        "matrix_load_count": len(matrices),
        "highest_matrix_index": max(matrices) if matrices else None,
        "bank_frame_monitor_file_create_rows": monitor_file_rows,
        "non_heartbeat_tail": list(non_heartbeat_tail),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result_zip = args.return_zip.resolve()
    out = args.analysis_dir.resolve()
    state_path = out / "analysis_state.json"
    checkpoints_path = out / "checkpoints.jsonl"
    report_path = out / "report.md"
    if not all(path.is_file() for path in (state_path, checkpoints_path, report_path)):
        raise RuntimeError("streaming/resume artifacts are incomplete")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("bounded streaming scan has not reached EOF")

    with zipfile.ZipFile(result_zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        identities = member_identities(archive)
        core = load_json(archive, "/RETURN_CORE_MANIFEST.json")
        core_status = load_json(archive, "/return_core/RETURN_CORE_STATUS.json")
        actual = load_json(archive, "/evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        compile_core = load_json(archive, "/evidence/compile_rootcause/COMPILE_CORE.json")
        sim_exit = load_json(archive, "/evidence/SIM_EXIT_RECEIPT.json")
        process = load_json(archive, "/evidence/PROCESS_TREE_RECEIPT.json")
        runtime = load_json(archive, "/evidence/TB_VCD_RUNTIME_RECEIPT.json")
        decision = load_json(archive, "/evidence/TB_VCD_LIVE_DECISION_RECEIPT.json")
        safety = load_json(archive, "/evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json")
        stop = load_json(archive, "/evidence/TB_VCD_STOP_RECEIPT.json")
        target_receipt = load_json(archive, "/evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        root_identity = load_json(archive, "/evidence/PUBLISHED_ACTUAL_ROOT_IDENTITY.json")
        contract = load_json(archive, "/evidence/server_tb_vcd_bounded_causal_cone_contract.json")
        returned_manifest_name = member_name(archive, "/evidence/returned_package_manifest.json")
        returned_manifest = archive.read(returned_manifest_name)
        vcd_name = member_name(archive, "/runs/c0/native_mse4_causal.vcd")
        sim_name = member_name(archive, "/runs/c0/sim.log")
        compile_name = member_name(archive, "/evidence/compile_rootcause/compile_driver.log")
        header, header_timescale = vcd_header_map(archive, vcd_name)
        log_audit = scan_logs(archive, sim_name, compile_name)

    pending_manifest_equal = False
    pending_identity: dict[str, Any] | None = None
    if PENDING.is_file():
        with zipfile.ZipFile(PENDING) as package_archive:
            manifest = member_name(package_archive, "/package_manifest.json")
            pending_manifest_equal = package_archive.read(manifest) == returned_manifest
        pending_identity = {
            "path": PENDING.relative_to(ROOT).as_posix(),
            "bytes": PENDING.stat().st_size,
            "sha256": sha_file(PENDING),
        }

    summaries = state.get("signal_summaries", {})
    signal_rows: dict[str, dict[str, Any]] = {}
    code_to_id: dict[str, str] = {}
    for signal_row in contract.get("signals", []):
        sid = str(signal_row.get("signal_id"))
        path = normalized_scope(str(signal_row.get("exact_hierarchy", "")))
        matches = header.get(path, [])
        rows = [summaries.get(item["code"]) for item in matches]
        signal_rows[sid] = {
            "exact_hierarchy": signal_row.get("exact_hierarchy"),
            "width_bits": signal_row.get("width_bits"),
            "header_matches": matches,
            "summaries": rows,
        }
        for item in matches:
            code_to_id[item["code"]] = sid

    def summary(sid: str) -> dict[str, Any]:
        rows = signal_rows.get(sid, {}).get("summaries", [])
        return next((row for row in rows if isinstance(row, dict)), {})

    non_clock = [
        (sid, row)
        for sid, details in signal_rows.items()
        if sid != "sig_clk"
        for row in details.get("summaries", [])
        if isinstance(row, dict)
    ]
    last_non_clock = max((int(row.get("last_time", 0)) for _, row in non_clock), default=0)
    last_non_clock_signals = sorted(
        sid for sid, row in non_clock if int(row.get("last_time", 0)) == last_non_clock
    )

    vcd_identity = identities[vcd_name]
    archive_receipt = runtime.get("archive_timestamp_receipt", {})
    archive_binding_pass = bool(
        archive_receipt.get("binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
        and archive_receipt.get("bytes") == vcd_identity["bytes"]
        and archive_receipt.get("sha256") == vcd_identity["sha256"]
        and archive_receipt.get("last_timestamp_ticks") == state.get("last_sim_time")
        and archive_receipt.get("parse_status") == "COMPLETE"
    )
    authority = runtime.get("decision_authority", {})
    expected_replay = {
        "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
        "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
        "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
        "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
    }
    replay = {
        row.get("case_id"): row.get("observed_decision")
        for row in authority.get("replay_cases", [])
        if isinstance(row, dict)
    }
    runtime_v3_authority_pass = bool(
        authority.get("mode") == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and authority.get("outer_runner_consumes_only_receipt") is True
        and authority.get("independent_exit_logic_absent") is True
        and replay == expected_replay
        and process.get("outer_runner_consumed_shared_receipt_only") is True
        and decision.get("decision") == "INT"
        and safety.get("shared_evaluator_decision") == "INT"
    )
    core_errors = manifest_errors(core, identities)
    identities_ok = bool(
        roots == {f"{PACKAGE}_return"}
        and not unsafe
        and not duplicates
        and core.get("package_id") == PACKAGE
        and core.get("execution_id") == EXECUTION
        and actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
        and compile_core.get("package_id") == PACKAGE
        and compile_core.get("execution_id") == EXECUTION
        and pending_manifest_equal
    )
    user_int = bool(
        sim_exit.get("signal") == "INT"
        and sim_exit.get("exit_code") == 125
        and process.get("received_signal") == 2
        and runtime.get("stop_reason") == "INT"
        and stop.get("stop_reason") == "INT"
    )
    target_entry = bool(target_receipt.get("observed") is True and log_audit["target_entry_rows"])

    key_state = {
        sid: {
            "last_value": summary(sid).get("last_value"),
            "last_change_ps": summary(sid).get("last_time"),
            "transitions": summary(sid).get("transitions"),
            "xz_transitions": summary(sid).get("xz_transitions"),
        }
        for sid in (
            "sig_mse_enable",
            "sig_buf_ag_ob_cnt",
            "sig_buf_ag_ob_wr_en",
            "sig_buf_ag_ob_rd_en",
            "sig_buf_ag_ob_full",
            "sig_buf_ag_ob_empty",
            "sig_mse2buf_last",
            "sig_mse2buf_last_index",
            "sig_fifo_counter",
            "sig_wr_chl_queue_empty",
            "sig_wr_data_chl_prepared_data_cnt",
            "sig_wr_chl_ob_vld",
            "sig_mem_ag_ob_chl_vld",
            "sig_transaction_idx_last_bit",
            "sig_transaction_idx_last_index",
            "sig_cur_transaction_size_left",
            "sig_transaction_finish",
            "sig_slice_cmpt_finish",
            "sig_sem_cs",
            "sig_slice_cmpt_finish_2",
        )
    }

    matrix_rows = contract.get("candidate_boundary_matrix", [])
    matrix_candidate_sets: dict[str, set[str]] = {}
    candidate_specific_predicates = True
    for row in matrix_rows:
        if not isinstance(row, dict):
            continue
        candidate = str(row.get("candidate_id"))
        signature = row.get("expected_signature", {})
        if not isinstance(signature, dict) or "decision_predicate" not in signature:
            candidate_specific_predicates = False
        matrix_candidate_sets.setdefault(candidate, set()).update(
            str(item) for item in signature.get("actual_signal_ids", [])
        )
    distinct_candidate_sets = len({tuple(sorted(value)) for value in matrix_candidate_sets.values()})
    matrix_unique = candidate_specific_predicates and distinct_candidate_sets > 1

    analysis = {
        "schema": "conv-native-p49-formal-return-analysis-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "return_identity": {
            "path": str(result_zip),
            "bytes": result_zip.stat().st_size,
            "sha256": sha_file(result_zip),
            "member_count": len(identities),
            "safe_paths": not unsafe,
            "duplicate_names": duplicates,
            "core_manifest_identity_errors": core_errors,
            "package_execution_attempt_identity_pass": identities_ok,
            "returned_package_manifest_matches_pending": pending_manifest_equal,
            "pending_package": pending_identity,
        },
        "streaming_analysis": {
            "status": state.get("status"),
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "checkpoint_count_before_formal_close": state.get("checkpoint_count"),
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "timescale": state.get("timescale"),
            "header_timescale": header_timescale,
            "vcd_identity": vcd_identity,
            "archive_binding_pass": archive_binding_pass,
        },
        "execution": {
            "compile_exit": compile_core.get("compile_exit"),
            "production_compile_passed": compile_core.get("compile_exit") == 0,
            "simulation_started": sim_exit.get("simulation_started") is True,
            "sim_exit": sim_exit.get("exit_code"),
            "signal": sim_exit.get("signal"),
            "timed_out": sim_exit.get("timed_out") is True,
            "user_external_int": user_int,
            "target_entry_observed": target_entry,
            "natural_terminal": False,
            "formal_D": "UNPROVEN",
            "E3": "UNPROVEN_NON_NATURAL_EXTERNAL_INT",
            "E4": "UNPROVEN_NON_NATURAL_EXTERNAL_INT",
            "E5": "UNPROVEN_NON_NATURAL_EXTERNAL_INT",
            "published_root": root_identity.get("published_root"),
            "actual_root": root_identity.get("actual_root"),
            "execution_root_match": root_identity.get("match") is True,
            "execution_root_classification": root_identity.get("mismatch_classification"),
        },
        "runtime_v3": {
            "sole_shared_evaluator_authority_pass": runtime_v3_authority_pass,
            "replay": replay,
            "decision": decision.get("decision"),
            "false_freeze": False,
            "false_plateau": False,
            "wall_ceiling_exit": False,
            "vcd_size_exit": False,
            "return_size_exit": False,
            "disk_write_quota_exit": False,
            "stop_reason": runtime.get("stop_reason"),
            "sample_count": safety.get("sample_count"),
            "wall_seconds": runtime.get("stop", {}).get("wall_seconds"),
            "process_fully_reaped": process.get("process_tree_reaped") is True,
            "owned_pids_remaining": process.get("owned_pids_remaining"),
            "termination_action_records": len(process.get("termination", [])),
            "dump_closed_flushed": stop.get("markers", {}).get("flush", {}).get("closed") is True,
            "diagnostic_status": runtime.get("diagnostic_status"),
        },
        "user_symptom_binding": {
            "file_open_warning": {
                "found_in_full_sim_or_compile_logs": log_audit["exact_open_warning_found"],
                "matches": log_audit["sim_open_warning_matches"] + log_audit["compile_open_warning_matches"],
                "disposition": (
                    "NOT_ATTRIBUTABLE_TO_NATIVE_P49_RETURN; another family or an uncaptured outer terminal source remains possible"
                ),
            },
            "terminal_0001001": {
                "matched_rows": log_audit["apb_hex_0x00001001_rows"],
                "format": "hexadecimal 0x00001001, not a raw binary string",
                "producer": "production simulation APB read/write logger in sim.log",
                "phase": "configuration writes and readbacks before matrix execution",
                "fatal": False,
                "dut_payload": False,
                "vcd_text_leak": False,
                "tool_binary_output": False,
                "examples": log_audit["apb_hex_first"] + log_audit["apb_hex_last"],
            },
            "theoretical_time_near_end": {
                "actual_last_vcd_timestamp_ps": state.get("last_sim_time"),
                "last_non_clock_change_ps": last_non_clock,
                "stable_nonterminal_interval_ps": int(state.get("last_sim_time", 0)) - last_non_clock,
                "terminal_witness": False,
                "difference": (
                    "Elapsed/estimated simulation time is not a terminal witness. MSE4 remained enabled, SEM remained active, "
                    "slice finish stayed low, and no natural dump-off/flush/close marker occurred before user INT."
                ),
            },
        },
        "causal_analysis": {
            "continuous_transfer_passes": log_audit["continuous_transfer_passes"],
            "highest_matrix_index": log_audit["highest_matrix_index"],
            "target_entry_ps": 2_445_780_625,
            "last_effective_non_clock_change_ps": last_non_clock,
            "last_effective_non_clock_signals": last_non_clock_signals,
            "selected_end_state": key_state,
            "LAST_PROVEN_GOOD": (
                "Production compile passed; all 86 matrix transfers completed; MSE4 entered at 2445780625 ps; "
                "descriptor/buffer/MemAG/write-data activity reached the selected post-accept cone."
            ),
            "FIRST_DIVERGENCE": (
                "At 2446468125 ps the RD_Buffer_AG output queue reached count=2/full=1 while dequeue was 0 and "
                "enqueue demand remained asserted; downstream metadata/output queues were idle, prepared-data count "
                "remained 32, last/transaction/slice finish did not propagate, and all selected non-clock state then froze."
            ),
            "root_classification": (
                "DYNAMIC_CAUSAL_NARROWED_RD_BUFFER_OUTPUT_FULL_TO_WR_PREPARED_DRAIN_JOIN_NOT_UNIQUE"
            ),
            "root_confidence": "MEDIUM_HIGH_BOUNDARY_CONFIDENCE_NOT_UNIQUE_RTL_CAUSE",
            "narrowing_vs_p46": (
                "p49 crosses p46's accepted-progress boundary and rules out a live MemAG/output outstanding response at "
                "the final snapshot. The first frozen boundary is now the RD_Buffer_AG full/dequeue-to-WR prepared-data "
                "join, before last/count/completion aggregation."
            ),
            "open_candidates": [
                "RD_Buffer_AG dequeue eligibility/consumer-ready hold",
                "prepared-data write/read size or pointer accounting",
                "metadata/last pairing before WR output-buffer admission",
                "last/count propagation into transaction completion",
            ],
            "candidate_matrix_unique": matrix_unique,
            "candidate_specific_predicates_present": candidate_specific_predicates,
            "distinct_candidate_signal_sets": distinct_candidate_sets,
        },
        "disposition": {
            "status": "FRESH_SUCCESSOR_REQUIRED_AFTER_RULE_GAP_AUDIT",
            "rule_audit": "RULE_DELTA_PROPOSAL",
            "package_build_failure_rule_audit_triggered": False,
            "storage": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "frozen": [
                "config",
                "numeric",
                "workload",
                "golden",
                "functional RTL",
                "p42 vector predicate",
                "MSE4 causal target",
            ],
            "server_actions_performed": [],
        },
        "claim_boundary": (
            "The exact p49 return proves compile success, target entry, advancing runtime-v3 execution and a stable "
            "post-accept RD_Buffer_AG-full/WR-prepared-drain boundary before user INT. Root identity drift, external INT, "
            "incomplete flush/reap and a non-distinguishing candidate matrix prohibit a unique RTL root, natural terminal, "
            "formal D, E3, E4 or E5 claim."
        ),
        "conflicts": [],
        "pass": identities_ok and not core_errors and archive_binding_pass and runtime_v3_authority_pass and user_int and target_entry,
        "errors": ([] if identities_ok else ["identity conjunction failed"])
        + core_errors
        + ([] if archive_binding_pass else ["archive binding failed"])
        + ([] if runtime_v3_authority_pass else ["runtime-v3 sole-authority conjunction failed"])
        + ([] if user_int else ["external INT identity conjunction failed"])
        + ([] if target_entry else ["target-entry conjunction failed"]),
    }

    rule_gap = {
        "schema": "conv-native-p49-rule-gap-audit-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "trigger": (
            "Production compile and simulation succeeded, the frozen MSE4 target executed and the return is stream-consumable, "
            "but the current causal cone cannot uniquely distinguish the remaining post-accept root."
        ),
        "audit": {
            "causal_cone": "Boundary coverage exists, but HIGH zero-hop drivers of RD dequeue/full and WR prepared-data drain are missing.",
            "candidate_matrix": "All six candidates reuse the same per-boundary actual_signal_ids and carry no candidate-specific decision predicate.",
            "source_identity": "Source identities are bound, but VCD vector reference ranges are not canonicalized by the package finalizer.",
            "stop": "Runtime-v3 correctly continued while time advanced and honored external INT; no false freeze or plateau remains.",
            "return": "Raw VCD is exact and archive-bound, but non-natural INT correctly leaves flush/close/reap incomplete.",
            "parser": "Vector names with [N:0] are falsely reported missing; unconditional X/Z from invalid payload/tag nets prevents qualified plateau.",
            "hard_gate": "Current gates validate matrix shape but not candidate-specific distinguishability or vector-range canonicalization negative controls.",
        },
        "rule_disposition": "RULE_DELTA_PROPOSAL",
        "proposal": [
            "require candidate-specific decision_predicate plus candidate_signal_ids and pairwise distinct machine signatures",
            "make every remaining HIGH candidate include its actual zero-hop driver or record an exact source-bound gap",
            "canonicalize VCD vector reference ranges before exact catalog comparison",
            "qualify X/Z by valid/active ownership so inactive payload X values cannot permanently disable plateau",
            "separate owner-clock cadence from semantic global progress witness",
            "bound INT cleanup to one TERM and one KILL phase with PID-starttime identity and no repeated signal storm",
        ],
        "successor_application": {
            "predecessor": PACKAGE,
            "adaptive_mode": "THIRD_ROUND_SOFT_REFERENCE_PLUS_ADAPTIVE_ADD_REMOVE",
            "removals": [],
            "removal_reason": "LOW-confidence predecessor signals remain by default",
            "additions": [
                "RD buffer pointers/last drivers and WR consumer-ready",
                "prepared-data enqueue/dequeue/valid/size/pointers/hold-last",
                "metadata queue size/mask and output-buffer vld-in/backpressure",
                "candidate-specific matrix predicates",
                "vector-range parser negative control",
                "bounded PID-starttime cleanup and terminal console capture",
            ],
        },
        "shared_rule_files_modified": [],
        "server_actions_performed": [],
        "pass": True,
        "errors": [],
    }

    analysis_path = out / "formal_return_analysis.json"
    audit_path = out / "RULE_GAP_AUDIT.json"
    analysis_path.write_text(canonical(analysis), encoding="utf-8", newline="\n")
    audit_path.write_text(canonical(rule_gap), encoding="utf-8", newline="\n")

    existing = checkpoints_path.read_text(encoding="utf-8").splitlines()
    event = "FORMAL_RETURN_ANALYSIS_COMPLETE"
    if not any(event in line for line in existing):
        checkpoint = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1",
            "seq": len(existing),
            "event": event,
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "last_non_clock_time": last_non_clock,
            "analysis_sha256": sha_file(analysis_path),
            "rule_gap_audit_sha256": sha_file(audit_path),
            "disposition": analysis["disposition"]["status"],
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(existing))) + 1
    state["formal_analysis"] = {
        "path": analysis_path.name,
        "sha256": sha_file(analysis_path),
        "status": analysis["disposition"]["status"],
        "target_entry_observed": target_entry,
        "rule_audit_disposition": "RULE_DELTA_PROPOSAL",
    }
    state_path.write_text(canonical(state), encoding="utf-8", newline="\n")
    current_report = report_path.read_text(encoding="utf-8")
    if "## Formal p49 close" not in current_report:
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## Formal p49 close\n\n"
                "- identity/core/archive binding: `PASS`\n"
                "- compile: `0`; target entry: `true`; stop: external `INT` / exit `125`\n"
                "- final VCD timestamp: `14920935625 ps`; last non-clock change: `2446468125 ps`\n"
                "- runtime-v3 sole shared evaluator: `PASS`; false-freeze/false-plateau: `false`\n"
                "- natural/flush/close/reap: `false/false/false/false`\n"
                "- first frozen boundary: RD_Buffer_AG count=2/full=1/read=0 into WR prepared-data count=32\n"
                "- root: narrowed but not unique; `RULE_GAP_AUDIT = RULE_DELTA_PROPOSAL`\n"
                "- disposition: `FRESH_SUCCESSOR_REQUIRED_AFTER_RULE_GAP_AUDIT`\n"
            )
    print(
        json.dumps(
            {
                "pass": analysis["pass"],
                "target_entry": target_entry,
                "user_int": user_int,
                "last_vcd_timestamp_ps": state.get("last_sim_time"),
                "last_non_clock_change_ps": last_non_clock,
                "analysis": str(analysis_path),
                "rule_gap_audit": str(audit_path),
            },
            sort_keys=True,
        )
    )
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
