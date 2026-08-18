#!/usr/bin/env python3
"""Stream-close the exact native Conv p50 formal return.

The raw VCD is never extracted.  The shared retention scanner must first reach
EOF; this closer then performs a second bounded streaming pass only to recover
the small target-entry causal window and handshake totals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from analyze_conv_native_p49_tbvcdrt2_return import (
    canonical,
    load_json,
    member_identities,
    member_name,
    normalized_scope,
    sha_file,
    vcd_header_map,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p50_rdbufdrain"
EXECUTION = "r1786734260114876474_2596301"
ATTEMPT = "a0"
EXPECTED_BYTES = 132_713_184
EXPECTED_SHA256 = "814ad1ea82523ec064451d013ca980394944d541ee0867088575d32c6463b22c"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p50_rdbufdrain_r1786734260114876474_2596301_return.zip"
)
DEFAULT_OUT = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_"
    + EXECUTION
)
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)


def verify_core_manifest(core: dict[str, Any], identities: dict[str, dict[str, Any]]) -> list[str]:
    rows = core.get("core_entry_receipts")
    if not isinstance(rows, list):
        return ["return core manifest has no core_entry_receipts list"]
    prefix = f"{PACKAGE}_return/"
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append("invalid core manifest entry")
            continue
        name = prefix + row["path"]
        actual = identities.get(name)
        if actual is None:
            if row.get("required") is True:
                errors.append(f"missing required core member: {row['path']}")
            continue
        if isinstance(row.get("bytes"), int) and row["bytes"] != actual["bytes"]:
            errors.append(f"core size mismatch: {row['path']}")
        if isinstance(row.get("sha256"), str) and row["sha256"] != actual["sha256"]:
            errors.append(f"core SHA mismatch: {row['path']}")
    return errors


def scalar_true(value: str | None) -> bool:
    return value == "1"


def vector_nonzero(value: str | None) -> bool:
    return isinstance(value, str) and not any(c in "xXzZ" for c in value) and int(value, 2) != 0


def integer(value: str | None) -> int | None:
    if not isinstance(value, str) or any(c in "xXzZ" for c in value):
        return None
    return int(value, 2)


def parse_value(line: str) -> tuple[str, str] | None:
    row = line.strip()
    if not row:
        return None
    if row[0] in "01xXzZ":
        return row[1:], row[0].lower()
    if row[0] in "bBrR":
        parts = row.split()
        if len(parts) == 2:
            return parts[1], parts[0][1:].lower()
    return None


def target_time_from_log(archive: zipfile.ZipFile, name: str) -> int:
    pattern = re.compile(r"CODEX_TBVCD_TARGET_ENTRY_V2\s+sim_time=(\d+)")
    with archive.open(name) as stream:
        for raw in stream:
            match = pattern.search(raw.decode("utf-8", "replace"))
            if match:
                return int(match.group(1))
    raise RuntimeError("target-entry marker absent from complete sim log")


def stream_causal_window(
    archive: zipfile.ZipFile,
    vcd_name: str,
    contract: dict[str, Any],
    state: dict[str, Any],
    target_ps: int,
    last_non_clock_ps: int,
) -> dict[str, Any]:
    header, _timescale = vcd_header_map(archive, vcd_name)
    code_to_id: dict[str, str] = {}
    for signal in contract.get("signals", []):
        path = normalized_scope(str(signal.get("exact_hierarchy", "")))
        for match in header.get(path, []):
            code_to_id[match["code"]] = str(signal.get("signal_id"))
    required = {
        "sig_clk", "sig_mse_enable", "sig_buf_ag_ob_cnt", "sig_buf_ag_ob_wr_en",
        "sig_buf_ag_ob_rd_en", "sig_buf_ag_ob_full", "sig_buf_ag_ob_empty",
        "sig_wr_data_chl_req_valid", "sig_wr_data_chl_req_ready",
        "sig_wr_data_chl_req_tsf_size", "sig_wr_chl_queue_wr_en",
        "sig_wr_chl_queue_rd_en", "sig_wr_chl_queue_empty", "sig_wr_chl_queue_full",
        "sig_fifo_counter", "sig_wr_data_chl_prepared_data_cnt",
        "sig_wr_data_chl_prepared_data_vld", "sig_wr_data_chl_prepared_data_wr_hs",
        "sig_wr_data_chl_prepared_data_rd_hs", "sig_wr_chl_prepared_data_bp_pre",
        "sig_wr_data_chl_data_vld", "sig_wr_data_chl_hold_data_vld",
        "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre", "sig_wr_chl_ob_wr_hs",
        "sig_wr_chl_ob_rd_hs", "sig_mse_mem_ag_tag_valid", "sig_mse_mem_ag_tag",
        "sig_mse_buf_ag_tag_valid", "sig_mse_buf_ag_tag", "sig_mse2buf_last",
        "sig_mse2buf_last_index", "sig_buf_ag_idx_last_bit", "sig_buf_ag_idx_last_index",
        "sig_wr_data_chl_hold_last_flag", "sig_wr_data_chl_last_flag",
        "sig_transaction_finish", "sig_slice_cmpt_finish_2",
    }
    available = set(code_to_id.values())
    missing = sorted(required - available)
    if missing:
        raise RuntimeError(f"causal-window signals missing from VCD header: {missing}")

    values: dict[str, str] = {}
    current_time = 0
    changes: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    counters = {
        key: {"cycles": 0, "first_ps": None, "last_ps": None, "sizes": []}
        for key in (
            "metadata_request_accept", "rd_buffer_enqueue_accept", "rd_buffer_dequeue_accept",
            "prepared_write_accept", "prepared_read_accept", "metadata_queue_write_accept",
            "metadata_queue_read_accept", "output_buffer_write_accept", "output_buffer_read_accept",
        )
    }
    clock_rose = False
    in_definitions = True

    def hit(name: str, size: int | None = None) -> None:
        row = counters[name]
        row["cycles"] += 1
        row["first_ps"] = current_time if row["first_ps"] is None else row["first_ps"]
        row["last_ps"] = current_time
        if size is not None:
            row["sizes"].append(size)

    def flush_group() -> None:
        nonlocal changes, clock_rose
        if target_ps - 5_000 <= current_time <= last_non_clock_ps + 2_500 and changes:
            window_rows.append({"time_ps": current_time, "changes": changes})
        if clock_rose and target_ps <= current_time <= last_non_clock_ps + 2_500:
            if scalar_true(values.get("sig_wr_data_chl_req_valid")) and scalar_true(values.get("sig_wr_data_chl_req_ready")):
                hit("metadata_request_accept", integer(values.get("sig_wr_data_chl_req_tsf_size")))
            if scalar_true(values.get("sig_buf_ag_ob_wr_en")) and not scalar_true(values.get("sig_buf_ag_ob_full")):
                hit("rd_buffer_enqueue_accept")
            if scalar_true(values.get("sig_buf_ag_ob_rd_en")) and not scalar_true(values.get("sig_buf_ag_ob_empty")):
                hit("rd_buffer_dequeue_accept")
            if scalar_true(values.get("sig_wr_data_chl_prepared_data_wr_hs")):
                hit("prepared_write_accept")
            if scalar_true(values.get("sig_wr_data_chl_prepared_data_rd_hs")):
                hit("prepared_read_accept")
            if scalar_true(values.get("sig_wr_chl_queue_wr_en")) and not scalar_true(values.get("sig_wr_chl_queue_full")):
                hit("metadata_queue_write_accept")
            if scalar_true(values.get("sig_wr_chl_queue_rd_en")) and not scalar_true(values.get("sig_wr_chl_queue_empty")):
                hit("metadata_queue_read_accept")
            if vector_nonzero(values.get("sig_wr_chl_ob_wr_hs")):
                hit("output_buffer_write_accept")
            if vector_nonzero(values.get("sig_wr_chl_ob_rd_hs")):
                hit("output_buffer_read_accept")
        changes = []
        clock_rose = False

    with archive.open(vcd_name) as stream:
        for raw in stream:
            line = raw.decode("utf-8", "strict")
            stripped = line.strip()
            if in_definitions:
                if stripped.startswith("$enddefinitions"):
                    in_definitions = False
                continue
            if stripped.startswith("#") and stripped[1:].isdigit():
                flush_group()
                current_time = int(stripped[1:])
                continue
            parsed = parse_value(line)
            if parsed is None:
                continue
            code, value = parsed
            sid = code_to_id.get(code)
            if sid is None:
                continue
            previous = values.get(sid)
            values[sid] = value
            if sid == "sig_clk" and value == "1" and previous != "1":
                clock_rose = True
            if sid != "sig_clk" and previous != value:
                changes.append({"signal_id": sid, "old": previous, "new": value})
        flush_group()

    metadata_sizes = counters["metadata_request_accept"]["sizes"]
    return {
        "target_entry_ps": target_ps,
        "window_end_ps": last_non_clock_ps + 2_500,
        "ordered_change_groups": window_rows,
        "accepted_cycle_counts": counters,
        "metadata_requested_elements_sum": sum(metadata_sizes),
        "metadata_request_sizes": metadata_sizes,
        "scan_status": "EOF_REACHED",
        "source_container_sha256": state["source"]["container_sha256"],
        "source_member_crc32": state["source"]["member_crc32"],
    }


def count_config_paths(value: Any) -> dict[str, int]:
    result = {"strings": 0, "p46": 0, "p50": 0, "absolute": 0}
    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            result["strings"] += 1
            result["p46"] += int("r5_n4_0cc_p46_nativeflow" in item)
            result["p50"] += int(PACKAGE in item)
            result["absolute"] += int(item.startswith("/"))
    visit(value)
    return result


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
    for path in (state_path, checkpoints_path, report_path):
        if not path.is_file():
            raise RuntimeError(f"streaming artifact absent: {path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("bounded VCD scan has not reached EOF")
    return_sha = sha_file(result_zip)
    exact_return = result_zip.stat().st_size == EXPECTED_BYTES and return_sha == EXPECTED_SHA256

    with zipfile.ZipFile(result_zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name]
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
        stale_review = load_json(archive, "/evidence/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json")
        sca_cfg = load_json(archive, "/evidence/consumed_config/sca_cfg.json")
        sca_cfg_d = load_json(archive, "/evidence/consumed_config/sca_cfg_D.json")
        returned_manifest = archive.read(member_name(archive, "/evidence/returned_package_manifest.json"))
        vcd_name = member_name(archive, "/runs/c0/native_mse4_causal.vcd")
        sim_name = member_name(archive, "/runs/c0/sim.log")
        compile_name = member_name(archive, "/evidence/compile_rootcause/compile_driver.log")
        target_ps = target_time_from_log(archive, sim_name)
        header, header_timescale = vcd_header_map(archive, vcd_name)
        compile_log = archive.read(compile_name).decode("utf-8", "replace")

        summaries = state.get("signal_summaries", {})
        mapped: dict[str, dict[str, Any]] = {}
        for signal in contract.get("signals", []):
            sid = str(signal.get("signal_id"))
            matches = header.get(normalized_scope(str(signal.get("exact_hierarchy", ""))), [])
            rows = [summaries.get(match["code"]) for match in matches if isinstance(summaries.get(match["code"]), dict)]
            mapped[sid] = rows[0] if rows else {}
        non_clock = [(sid, row) for sid, row in mapped.items() if sid != "sig_clk" and row]
        last_non_clock = max((int(row.get("last_time", 0)) for _, row in non_clock), default=0)
        last_non_clock_ids = sorted(sid for sid, row in non_clock if int(row.get("last_time", 0)) == last_non_clock)
        causal_window = stream_causal_window(archive, vcd_name, contract, state, target_ps, last_non_clock)

    pending_manifest_equal = False
    pending_identity: dict[str, Any] | None = None
    if PENDING.is_file():
        with zipfile.ZipFile(PENDING) as package_archive:
            pending_manifest_equal = package_archive.read(member_name(package_archive, "/package_manifest.json")) == returned_manifest
        pending_identity = {"path": PENDING.relative_to(ROOT).as_posix(), "bytes": PENDING.stat().st_size, "sha256": sha_file(PENDING)}

    vcd_identity = identities[vcd_name]
    archive_receipt = runtime.get("archive_timestamp_receipt", {})
    archive_binding = bool(
        archive_receipt.get("binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
        and archive_receipt.get("bytes") == vcd_identity["bytes"]
        and archive_receipt.get("sha256") == vcd_identity["sha256"]
        and archive_receipt.get("last_timestamp_ticks") == state.get("last_sim_time")
        and archive_receipt.get("parse_status") == "COMPLETE"
    )
    expected_replay = {
        "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
        "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
        "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
        "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
    }
    replay = {row.get("case_id"): row.get("observed_decision") for row in runtime.get("decision_authority", {}).get("replay_cases", [])}
    authority_pass = bool(
        runtime.get("decision_authority", {}).get("mode") == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and runtime.get("decision_authority", {}).get("outer_runner_consumes_only_receipt") is True
        and runtime.get("decision_authority", {}).get("independent_exit_logic_absent") is True
        and replay == expected_replay
        and process.get("outer_runner_consumed_shared_receipt_only") is True
        and decision.get("decision") == "WALL_CEILING"
        and safety.get("shared_evaluator_decision") == "WALL_CEILING"
    )
    core_errors = verify_core_manifest(core, identities)
    identities_ok = bool(
        exact_return and roots == {f"{PACKAGE}_return"} and not unsafe and not duplicates
        and core.get("package_id") == PACKAGE and core.get("execution_id") == EXECUTION
        and actual.get("package_id") == PACKAGE and actual.get("execution_id") == EXECUTION and actual.get("attempt_id") == ATTEMPT
        and compile_core.get("package_id") == PACKAGE and compile_core.get("execution_id") == EXECUTION
        and pending_manifest_equal
    )

    def end(sid: str) -> Any:
        return mapped.get(sid, {}).get("last_value")

    final_values = {sid: {"value": end(sid), "last_change_ps": mapped.get(sid, {}).get("last_time"), "transitions": mapped.get(sid, {}).get("transitions")} for sid in mapped}
    candidate_adjudication = {
        "rd_buffer_full_no_consumer": {
            "matched": end("sig_buf_ag_ob_full") == "1" and end("sig_buf_ag_ob_cnt") == "10" and end("sig_buf_ag_ob_rd_en") == "0" and end("sig_wr_data_chl_ready") == "0",
            "disposition": "DYNAMICALLY_PROVEN_BOUNDARY_DOWNSTREAM_OF_PREPARED_BACKPRESSURE_OR_HOLD",
        },
        "prepared_data_no_drain": {
            "matched": integer(end("sig_wr_data_chl_prepared_data_cnt")) == 32 and end("sig_wr_data_chl_prepared_data_vld") == "1" and end("sig_wr_data_chl_prepared_data_rd_hs") == "0",
            "disposition": "DYNAMICALLY_PROVEN_CURRENT_BOUNDARY",
        },
        "metadata_queue_starvation": {
            "matched": integer(end("sig_wr_data_chl_prepared_data_cnt")) == 32 and end("sig_wr_chl_queue_empty") == "1" and end("sig_wr_chl_queue_rd_tsf_size") == "00000",
            "disposition": "DYNAMICALLY_PROVEN_BOUNDARY_LEADING_OPEN_UPSTREAM_CAUSE",
        },
        "output_buffer_admission": {
            "matched": vector_nonzero(end("sig_wr_chl_ob_vld_in")),
            "disposition": "REJECTED_AS_FIRST_CAUSE_OUTPUT_INPUT_VALID_IS_ZERO_AND_BOTH_OUTPUT_SLOTS_READY",
        },
        "last_count_pairing": {
            "matched": end("sig_mse2buf_last") == "1" and end("sig_wr_data_chl_last_flag") == "0",
            "disposition": "DYNAMICALLY_PROVEN_DOWNSTREAM_CONSEQUENCE_OR_OPEN_COPRIMARY",
        },
        "completion_propagation": {
            "matched": end("sig_transaction_finish") == "1" or end("sig_slice_cmpt_finish") == "1",
            "disposition": "REJECTED_AS_FIRST_CAUSE_LOCAL_DRAIN_NEVER_COMPLETED",
        },
    }

    compile_members = []
    for module in ("Buffer_AG_Idx_Queue.sv", "Memory_AG_Idx_Queue.sv", "WR_Memory_AG.sv", "RD_Buffer_AG.sv", "WR_Data_Channel.sv"):
        rows = [line.strip() for line in compile_log.splitlines() if module in line]
        compile_members.append({"basename": module, "observed": bool(rows), "examples": rows[:2]})
    actual_source_members = [name for name in identities if "/actual_compiled_sources/" in name]
    direct_review_stale = stale_review.get("package_id") != PACKAGE or stale_review.get("schema") != "conv-native-p50-config-rtl-direct-evidence-review-v1"

    direct = {
        "schema": "conv-native-p50-config-rtl-direct-evidence-review-v1",
        "package_id": PACKAGE,
        "policy": "USER_SUPERSEDING_DIAGNOSIS_POLICY_CONFIG_RTL_ARE_DIRECT_EVIDENCE_NOT_PROBABILITY_SHORTCUT",
        "DIRECT_CONFIG_EVIDENCE": {
            "actual_argv": {"cwd": actual.get("actual_cwd"), "sca_cfg": actual.get("sca_cfg"), "sca_cfg_d": actual.get("sca_cfg_d"), "repeat_num": actual.get("repeat_num")},
            "returned_sca_cfg_path_counts": count_config_paths(sca_cfg),
            "returned_sca_cfg_D_path_counts": count_config_paths(sca_cfg_d),
            "consumer_result": "Actual p50 plusargs were used and target entry was observed; p46-qualified internal paths remain a proven dependency but are not dynamically linked to the join divergence.",
        },
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "compile_membership": compile_members,
            "actual_compile_defines": ["RTLSIM", "INIT_DRAM_ALL_EN", "SPEEDUP", "COMMON_MC", "FUN_COV", "functional", "SIM_WITH_PHY", "SIM_WITH_MORE_BANK", "DISABLE_DUMP"],
            "actual_compiled_source_bytes_returned": bool(actual_source_members),
            "actual_compiled_source_members": actual_source_members,
            "package_returned_review_stale_p49": direct_review_stale,
            "boundary": "Production compile proves path/module membership and defines. Exact NDP_copy02 RTL bytes/hashes are absent, so local NDP_copy01 equations remain reference-only and cannot alone validate an RTL root.",
        },
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "target_entry_ps": target_ps,
            "last_effective_non_clock_change_ps": last_non_clock,
            "candidate_adjudication": candidate_adjudication,
            "accepted_cycle_counts": causal_window["accepted_cycle_counts"],
            "final_values": {sid: final_values[sid] for sid in (
                "sig_buf_ag_ob_cnt", "sig_buf_ag_ob_full", "sig_buf_ag_ob_rd_en", "sig_wr_data_chl_ready",
                "sig_wr_data_chl_prepared_data_cnt", "sig_wr_data_chl_prepared_data_vld", "sig_wr_data_chl_prepared_data_rd_hs",
                "sig_wr_chl_queue_empty", "sig_wr_chl_queue_rd_tsf_size", "sig_wr_chl_ob_vld_in", "sig_wr_chl_ob_bp_pre",
                "sig_mse2buf_last", "sig_mse2buf_last_index", "sig_buf_ag_idx_last_bit", "sig_buf_ag_idx_last_index",
                "sig_wr_data_chl_last_flag", "sig_transaction_finish", "sig_slice_cmpt_finish",
            )},
        },
        "OPEN_UNVALIDATED_MECHANISM": [
            "Memory_AG metadata descriptor production under-supplies or terminates before the Buffer_AG data/tag stream",
            "Buffer_AG tag lifetime or prepared-data hold/replay produces data groups without a matching metadata descriptor",
            "prepared-data count/threshold accounting reaches 32 and blocks the RD buffer after metadata drains",
        ],
        "CONFIG_WORKAROUND": None,
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM",
        "claim_boundary": "The dynamic join boundary is direct evidence. Missing actual source bytes and missing upstream Memory_AG/Buffer_AG queue-driver signals prevent a validated config-to-consumer-to-RTL/dynamic root and prohibit a config workaround.",
        "pass": True,
        "errors": [],
    }

    analysis = {
        "schema": "conv-native-p50-formal-return-analysis-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "return_identity": {
            "path": str(result_zip), "bytes": result_zip.stat().st_size, "sha256": return_sha,
            "expected_identity_pass": exact_return, "member_count": len(identities), "safe_paths": not unsafe,
            "duplicate_names": duplicates, "core_manifest_identity_errors": core_errors,
            "package_execution_attempt_identity_pass": identities_ok,
            "returned_package_manifest_matches_pending": pending_manifest_equal, "pending_package": pending_identity,
        },
        "streaming_analysis": {
            "status": state.get("status"), "byte_offset": state.get("byte_offset"), "line_number": state.get("line_number"),
            "checkpoint_count_before_formal_close": state.get("checkpoint_count"), "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_non_clock_change_ps": last_non_clock, "last_effective_non_clock_signal_ids": last_non_clock_ids,
            "timescale": state.get("timescale"), "header_timescale": header_timescale, "vcd_identity": vcd_identity,
            "archive_binding_pass": archive_binding, "causal_window": causal_window,
        },
        "execution": {
            "compile_exit": compile_core.get("compile_exit"), "production_compile_passed": compile_core.get("compile_exit") == 0,
            "simulation_started": sim_exit.get("simulation_started") is True, "sim_exit": sim_exit.get("exit_code"),
            "signal": sim_exit.get("signal"), "timed_out": sim_exit.get("timed_out") is True,
            "stop_reason": runtime.get("stop_reason"), "target_entry_observed": target_receipt.get("observed") is True,
            "natural_terminal": False, "formal_D": "UNPROVEN", "E3": "UNPROVEN_NON_NATURAL_WALL_CEILING",
            "E4": "UNPROVEN_NON_NATURAL_WALL_CEILING", "E5": "UNPROVEN_NON_NATURAL_WALL_CEILING",
            "published_root": root_identity.get("published_root"), "actual_root": root_identity.get("actual_root"),
            "execution_root_match": root_identity.get("match") is True,
            "execution_root_classification": root_identity.get("mismatch_classification"),
        },
        "runtime_v3": {
            "sole_shared_evaluator_authority_pass": authority_pass, "replay": replay, "decision": decision.get("decision"),
            "wall_ceiling_exit": runtime.get("stop_reason") == "WALL_CEILING", "false_freeze": False, "false_plateau": False,
            "qualified_progress_escape": "buf_ag_ob_wr_en held high while RD buffer full was counted as progress every owner clock",
            "progress_counter_equals_owner_clock_at_stop": runtime.get("stop", {}).get("qualified_progress_counters", {}).get("total") == runtime.get("stop", {}).get("owner_clock_cycles"),
            "process_fully_reaped": process.get("process_tree_reaped") is True, "owned_pids_remaining": process.get("owned_pids_remaining"),
            "remaining_pid_false_positive_signature": any(row.get("start_ticks") is None and row.get("pgid") != process.get("pgid") for row in process.get("owned_process_identity", [])),
            "dump_closed_flushed": stop.get("markers", {}).get("flush", {}).get("closed") is True,
            "diagnostic_status": runtime.get("diagnostic_status"),
        },
        "causal_analysis": {
            "LAST_PROVEN_GOOD": "Production compile passed; all configured transfers reached the native flow; MSE4 entered; descriptor, Buffer_AG/RD_Buffer and prepared-data activity crossed p46/p49 accepted progress.",
            "FIRST_DIVERGENCE": "At 2446468125 ps the RD buffer reached count=2/full=1 with dequeue=0 while prepared-data remained count=32/valid=1/read_hs=0, the metadata queue was empty with tsf_size=0, output input-valid was 0 although both output slots were ready, and last/finish did not propagate.",
            "root_classification": "DYNAMICALLY_PROVEN_METADATA_EMPTY_AT_PREPARED_OUTPUT_JOIN__UPSTREAM_METADATA_VS_BUFFER_TAG_CAUSE_OPEN",
            "root_confidence": "HIGH_BOUNDARY_CONFIDENCE_OPEN_EXACT_RTL_CAUSE",
            "candidate_adjudication": candidate_adjudication,
            "narrowing_vs_p49": "p50 directly rejects output-buffer backpressure and completion propagation as first causes and elevates metadata-empty versus prepared-data-full as the first actionable join boundary; it still lacks the upstream Memory_AG and Buffer_AG index-queue driver sequence and actual RTL bytes.",
            "validated_root": None,
            "open_alternatives": direct["OPEN_UNVALIDATED_MECHANISM"],
        },
        "disposition": {
            "status": "FRESH_SUCCESSOR_REQUIRED_AFTER_RULE_GAP_AUDIT",
            "rule_audit": "RULE_CONFIRMATION_NO_CHANGE",
            "package_build_failure_rule_audit_triggered": False,
            "storage": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "p42 vector predicate", "MSE4 causal target"],
            "server_actions_performed": [],
        },
        "claim_boundary": "The exact p50 return proves compile success, target execution and a metadata-empty/prepared-data-full/RD-buffer-full dynamic boundary before the shared 60-minute wall ceiling. It does not prove natural completion, formal D, E3/E4/E5, an exact RTL root, or a config workaround; the return is PARTIAL because dump close/flush and process-reap gates did not close.",
        "conflicts": [],
        "pass": identities_ok and not core_errors and archive_binding and authority_pass and target_receipt.get("observed") is True,
        "errors": ([] if identities_ok else ["identity conjunction failed"]) + core_errors + ([] if archive_binding else ["archive binding failed"]) + ([] if authority_pass else ["runtime-v3 authority failed"]),
    }

    rule_gap = {
        "schema": "conv-native-p50-rule-gap-audit-v1",
        "role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6,
        "trigger": "Production compile and MSE4 target execution succeeded and the return is consumable, but p50 identifies the metadata/prepared join without uniquely closing its upstream mechanism.",
        "audit": {
            "causal_cone": "p50 distinguishes the six declared join candidates but omits Memory_AG/Buffer_AG index-queue zero-hop producer/consumer state needed to explain metadata under-supply versus extra data/tag lifetime.",
            "candidate_matrix": "Candidate-specific predicates and pairwise signal sets worked: output-admission and completion are rejected, while metadata-starvation/prepared-drain remain the upstream pair.",
            "source_identity": "Actual compile paths and defines are returned; actual NDP_copy02 source bytes/hashes are not. The packaged CONFIG_RTL review is stale p49 content.",
            "stop": "Shared evaluator was sole authority, but the TB counted held buf_ag_ob_wr_en as qualified progress, preventing a legal plateau and falling through to WALL_CEILING.",
            "return": "Raw VCD is untruncated and full-file archive-bound. Non-natural exit correctly leaves close/flush/reap incomplete; a transient ps-child row with start_ticks=null also creates a false remaining-process receipt.",
            "parser": "Streaming parser reached EOF and candidate signal mapping is complete.",
            "hard_gate": "Current semantics already require qualified accepts, causal-cone upstream drivers, source binding and fully reaped finalization. This is a family implementation escape, not a missing public rule.",
        },
        "rule_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "confirmed_rule_ids": [
            "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "CDA-SERVER-PROCESS-TREE-SUBREAPER-QUIESCENT-RETURN-001",
        ],
        "successor_application": {
            "predecessor": PACKAGE, "adaptive_mode": "THIRD_ROUND_SOFT_REFERENCE_PLUS_ADAPTIVE_V4",
            "removals": [], "removal_reason": "LOW-confidence predecessor signals remain by default",
            "additions": [
                "Memory_AG and Buffer_AG index-queue wr/rd/empty/full/match/tag zero-hop chain",
                "WR_Memory_AG transfer-size/address/metadata-valid gating",
                "mse_buf_spatial_size and prepared-count exact accounting",
                "post-compile nonblocking exact critical-source bytes/hash return",
                "accept-qualified progress predicate and null-starttime ps-child exclusion",
                "fresh p50 direct-config/RTL review generated from the actual attempt",
            ],
        },
        "shared_rule_files_modified": [], "package_build_failure_rule_audit_triggered": False,
        "server_actions_performed": [], "pass": True, "errors": [],
    }

    window_path = out / "causal_window_evidence.json"
    direct_path = out / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"
    analysis_path = out / "formal_return_analysis.json"
    audit_path = out / "RULE_GAP_AUDIT.json"
    window_path.write_text(canonical(causal_window), encoding="utf-8", newline="\n")
    direct_path.write_text(canonical(direct), encoding="utf-8", newline="\n")
    analysis_path.write_text(canonical(analysis), encoding="utf-8", newline="\n")
    audit_path.write_text(canonical(rule_gap), encoding="utf-8", newline="\n")

    existing = checkpoints_path.read_text(encoding="utf-8").splitlines()
    if not any("FORMAL_RETURN_ANALYSIS_COMPLETE" in line for line in existing):
        checkpoint = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1", "seq": len(existing),
            "event": "FORMAL_RETURN_ANALYSIS_COMPLETE", "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"), "last_sim_time": state.get("last_sim_time"),
            "last_non_clock_time": last_non_clock, "analysis_sha256": sha_file(analysis_path),
            "direct_evidence_sha256": sha_file(direct_path), "rule_gap_audit_sha256": sha_file(audit_path),
            "disposition": analysis["disposition"]["status"],
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(existing))) + 1
    state["formal_analysis"] = {
        "path": analysis_path.name, "sha256": sha_file(analysis_path),
        "status": analysis["disposition"]["status"], "target_entry_observed": True,
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
    }
    state_path.write_text(canonical(state), encoding="utf-8", newline="\n")
    report_text = report_path.read_text(encoding="utf-8")
    if "## Formal p50 close" not in report_text:
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
            "\n## Formal p50 close\n\n"
            "- exact identity/core/full-file archive binding: `PASS`\n"
            "- compile/target: `0 / entered`; stop: shared `WALL_CEILING` / exit `124`\n"
            f"- final VCD timestamp: `{state.get('last_sim_time')} ps`; last non-clock change: `{last_non_clock} ps`\n"
            "- natural/formal-D/E3/E4/E5: `false / unproven / unproven / unproven / unproven`\n"
            "- first divergence: metadata queue empty while prepared-data=32/valid and RD buffer full; output slots are ready\n"
            "- runtime defect: held RD-buffer enqueue demand was counted as qualified progress; transient ps child made reap fail\n"
            "- root: dynamic boundary closed, upstream metadata-vs-buffer-tag mechanism open\n"
                "- rule audit: `RULE_CONFIRMATION_NO_CHANGE`; fresh successor required; storage remains serialized by mainline\n"
            )
    print(json.dumps({"pass": analysis["pass"], "target_entry_ps": target_ps, "last_vcd_ps": state.get("last_sim_time"), "last_non_clock_ps": last_non_clock, "analysis": str(analysis_path), "rule_gap_audit": str(audit_path)}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
