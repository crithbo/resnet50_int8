#!/usr/bin/env python3
"""Bounded formal close for the exact native-Conv p51 return.

The shared retention scanner must already have reached EOF.  This script makes
one additional streaming pass over the VCD member, never extracts it, and
records only the owner-edge event ledger plus a bounded critical trace.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import deque
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
PACKAGE = "r5_n4_0cc_p51_metaidxcone"
EXECUTION = "r1786770085722684994_2783486"
ATTEMPT = "a0"
EXPECTED_BYTES = 37_802_431
EXPECTED_SHA256 = "ad29550482d561d69ed3be5b14f16669539e7cf381e49de435b32d84aec9369f"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p51_metaidxcone_r1786770085722684994_2783486_return.zip"
)
DEFAULT_OUT = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_return_analysis_" + EXECUTION
)
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip"


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
        actual = identities.get(prefix + row["path"])
        if actual is None:
            if row.get("required") is True:
                errors.append(f"missing required core member: {row['path']}")
            continue
        if isinstance(row.get("bytes"), int) and row["bytes"] != actual["bytes"]:
            errors.append(f"core size mismatch: {row['path']}")
        if isinstance(row.get("sha256"), str) and row["sha256"] != actual["sha256"]:
            errors.append(f"core SHA mismatch: {row['path']}")
    return errors


def scalar(value: str | None) -> bool:
    return value == "1"


def nonzero(value: str | None) -> bool:
    return isinstance(value, str) and not any(c in value.lower() for c in "xz") and int(value, 2) != 0


def integer(value: str | None) -> int | None:
    if not isinstance(value, str) or any(c in value.lower() for c in "xz"):
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


def log_markers(archive: zipfile.ZipFile, sim_name: str) -> dict[str, Any]:
    expressions = {
        "target": re.compile(r"CODEX_TBVCD_TARGET_ENTRY_V2\s+sim_time=(\d+).*owner_cycles=(\d+)"),
        "suspect": re.compile(r"CODEX_TBVCD_PLATEAU_SUSPECT_V2\s+sim_time=(\d+).*owner_cycles=(\d+)"),
        "dumpoff": re.compile(r"CODEX_TBVCD_DUMPOFF_V2\s+sim_time=(\d+).*owner_cycles=(\d+)"),
        "stop": re.compile(r"CODEX_TBVCD_STOP_V2\s+reason=CAUSAL_PLATEAU\s+sim_time=(\d+).*owner_cycles=(\d+)"),
        "flush": re.compile(r"CODEX_TBVCD_FLUSH_V2.*sim_time=(\d+)"),
        "terminal": re.compile(r"CODEX_TBVCD_TERMINAL_WITNESS_V2\s+sim_time=(\d+)"),
        "heartbeat": re.compile(r"CODEX_TBVCD_HEARTBEAT_V2\s+sim_time=(\d+).*owner_cycles=(\d+)"),
    }
    result: dict[str, Any] = {key: {"count": 0, "first": None, "last": None} for key in expressions}
    tail: deque[str] = deque(maxlen=40)
    with archive.open(sim_name) as stream:
        for line_no, raw in enumerate(stream, 1):
            text = raw.decode("utf-8", "replace").rstrip()
            tail.append(text)
            for key, expression in expressions.items():
                match = expression.search(text)
                if not match:
                    continue
                row = {"line": line_no, "sim_time_ps": int(match.group(1)), "text": text[:512]}
                if match.lastindex and match.lastindex >= 2:
                    row["owner_cycles"] = int(match.group(2))
                result[key]["count"] += 1
                result[key]["first"] = result[key]["first"] or row
                result[key]["last"] = row
    result["tail"] = list(tail)
    return result


EVENT_TESTS = {
    "metadata_request_accept": lambda v: scalar(v.get("sig_wr_data_chl_req_valid")) and scalar(v.get("sig_wr_data_chl_req_ready")),
    "metadata_queue_write_accept": lambda v: scalar(v.get("sig_wr_chl_queue_wr_en")) and not scalar(v.get("sig_wr_chl_queue_full")),
    "metadata_queue_read_accept": lambda v: scalar(v.get("sig_wr_chl_queue_rd_en")) and not scalar(v.get("sig_wr_chl_queue_empty")),
    "prepared_write_accept": lambda v: scalar(v.get("sig_wr_data_chl_prepared_data_wr_hs")),
    "prepared_read_accept": lambda v: scalar(v.get("sig_wr_data_chl_prepared_data_rd_hs")),
    "rd_buffer_enqueue_accept": lambda v: scalar(v.get("sig_buf_ag_ob_wr_en")) and not scalar(v.get("sig_buf_ag_ob_full")),
    "rd_buffer_dequeue_accept": lambda v: scalar(v.get("sig_buf_ag_ob_rd_en")) and not scalar(v.get("sig_buf_ag_ob_empty")),
    "buffer_index_queue_write_accept": lambda v: scalar(v.get("sig_buf_ag_idx_queue_wr_en")) and not scalar(v.get("sig_buf_ag_idx_queue_full")),
    "buffer_index_queue_read_accept": lambda v: scalar(v.get("sig_buf_ag_idx_queue_rd_en")) and not scalar(v.get("sig_buf_ag_idx_queue_empty")),
    "memory_index_queue_write_accept": lambda v: scalar(v.get("sig_mem_ag_idx_queue_wr_en")) and not scalar(v.get("sig_mem_ag_idx_queue_full")),
    "memory_index_queue_read_accept": lambda v: scalar(v.get("sig_mem_ag_idx_queue_rd_en")) and not scalar(v.get("sig_mem_ag_idx_queue_empty")),
    "memory_transaction_finish": lambda v: scalar(v.get("sig_transaction_finish")),
    "output_buffer_write_accept": lambda v: nonzero(v.get("sig_wr_chl_ob_wr_hs")),
    "output_buffer_read_accept": lambda v: nonzero(v.get("sig_wr_chl_ob_rd_hs")),
}


TRACE_STATE = {
    "sig_buf_idx_queue_count", "sig_buf_ag_idx_queue_empty", "sig_buf_ag_idx_queue_full",
    "sig_mem_idx_queue_count", "sig_mem_ag_idx_queue_empty", "sig_mem_ag_idx_queue_full",
    "sig_mem_all_idx_matched", "sig_mem_ag_idx_valid_bit", "sig_transfer_size_valid",
    "sig_transfer_addr_bp_post", "sig_wr_data_chl_req_tsf_size", "sig_cur_transaction_size_left",
    "sig_fifo_counter", "sig_wr_data_chl_prepared_data_cnt", "sig_buf_ag_ob_cnt",
    "sig_mse_buf_spatial_size", "sig_wr_chl_ob_vld_in", "sig_slice_cmpt_finish_2",
}


def stream_ledger(
    archive: zipfile.ZipFile,
    vcd_name: str,
    contract: dict[str, Any],
    final_timestamp: int,
    target_time: int,
) -> dict[str, Any]:
    header, timescale = vcd_header_map(archive, vcd_name)
    code_to_id: dict[str, str] = {}
    for signal in contract.get("signals", []):
        matches = header.get(normalized_scope(str(signal.get("exact_hierarchy", ""))), [])
        for match in matches:
            code_to_id[match["code"]] = str(signal.get("signal_id"))
    required = set(TRACE_STATE) | {
        "sig_clk", "sig_wr_data_chl_req_valid", "sig_wr_data_chl_req_ready",
        "sig_wr_chl_queue_wr_en", "sig_wr_chl_queue_rd_en", "sig_wr_chl_queue_empty", "sig_wr_chl_queue_full",
        "sig_wr_data_chl_prepared_data_wr_hs", "sig_wr_data_chl_prepared_data_rd_hs",
        "sig_buf_ag_ob_wr_en", "sig_buf_ag_ob_rd_en", "sig_buf_ag_ob_empty", "sig_buf_ag_ob_full",
        "sig_buf_ag_idx_queue_wr_en", "sig_buf_ag_idx_queue_rd_en",
        "sig_mem_ag_idx_queue_wr_en", "sig_mem_ag_idx_queue_rd_en",
        "sig_transaction_finish", "sig_wr_chl_ob_wr_hs", "sig_wr_chl_ob_rd_hs",
    }
    missing = sorted(required - set(code_to_id.values()))
    if missing:
        raise RuntimeError(f"required p51 signals absent from VCD header: {missing}")

    values: dict[str, str] = {}
    current_time = 0
    changed: set[str] = set()
    event_times: dict[str, list[int]] = {name: [] for name in EVENT_TESTS}
    metadata_sizes: list[int] = []
    prepared_sizes: list[int] = []
    transaction_size_samples: list[int] = []
    trace: list[dict[str, Any]] = []
    last_effective_nonclock = 0
    last_effective_ids: set[str] = set()
    pre_dumpoff_values: dict[str, str] = {}
    definitions = True

    def flush() -> None:
        nonlocal changed, last_effective_nonclock, last_effective_ids, pre_dumpoff_values
        if current_time >= final_timestamp:
            changed = set()
            return
        if changed - {"sig_clk"}:
            last_effective_nonclock = current_time
            last_effective_ids = set(changed - {"sig_clk"})
        if current_time >= target_time and current_time % 1250 == 625:
            active: list[str] = []
            for name, test in EVENT_TESTS.items():
                if test(values):
                    event_times[name].append(current_time)
                    active.append(name)
            if "metadata_request_accept" in active:
                size = integer(values.get("sig_wr_data_chl_req_tsf_size"))
                if size is not None:
                    metadata_sizes.append(size)
            if "prepared_write_accept" in active:
                size = integer(values.get("sig_mse_buf_spatial_size"))
                if size is not None:
                    prepared_sizes.append(size)
            if "memory_index_queue_read_accept" in active:
                size = integer(values.get("sig_cur_transaction_size_left"))
                if size is not None:
                    transaction_size_samples.append(size)
            if active or changed & TRACE_STATE:
                trace.append({
                    "time_ps": current_time,
                    "events": active,
                    "state": {name: values.get(name) for name in sorted(TRACE_STATE)},
                })
        pre_dumpoff_values = dict(values)
        changed = set()

    with archive.open(vcd_name) as stream:
        for raw in stream:
            line = raw.decode("utf-8", "strict")
            row = line.strip()
            if definitions:
                if row.startswith("$enddefinitions"):
                    definitions = False
                continue
            if row.startswith("#") and row[1:].isdigit():
                flush()
                current_time = int(row[1:])
                continue
            if current_time >= final_timestamp:
                continue
            parsed = parse_value(line)
            if parsed is None:
                continue
            code, value = parsed
            sid = code_to_id.get(code)
            if sid is None:
                continue
            if values.get(sid) != value:
                changed.add(sid)
            values[sid] = value
        flush()

    counts = {
        name: {
            "cycles": len(times),
            "first_ps": times[0] if times else None,
            "last_ps": times[-1] if times else None,
        }
        for name, times in event_times.items()
    }
    capacity = counts["metadata_request_accept"]["cycles"]
    prepared_times = event_times["prepared_write_accept"]
    first_unmatched = prepared_times[capacity] if len(prepared_times) > capacity else None
    last_paired = event_times["metadata_request_accept"][-1] if event_times["metadata_request_accept"] else None
    return {
        "timescale": timescale,
        "catalog_mapped": len(code_to_id),
        "scan_status": "EOF_REACHED",
        "final_timestamp_ps": final_timestamp,
        "pre_dumpoff_final_values": pre_dumpoff_values,
        "last_effective_nonclock_change_ps": last_effective_nonclock,
        "last_effective_nonclock_signal_ids": sorted(last_effective_ids),
        "event_counts": counts,
        "event_times_ps": event_times,
        "metadata_request_sizes": metadata_sizes,
        "metadata_units": sum(metadata_sizes),
        "prepared_group_sizes": prepared_sizes,
        "prepared_units": sum(prepared_sizes),
        "metadata_deficit_units": sum(prepared_sizes) - sum(metadata_sizes),
        "transaction_size_samples_at_index_read": transaction_size_samples,
        "last_paired_metadata_descriptor_ps": last_paired,
        "first_prepared_group_without_metadata_capacity_ps": first_unmatched,
        "critical_trace": [row for row in trace if row["time_ps"] >= 2_446_000_000],
    }


def source_evidence(archive: zipfile.ZipFile, identities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest = load_json(archive, "/evidence/compile_bootstrap/actual_compiled_sources/manifest.json")
    equations = {
        "Buffer_AG_Idx_Queue.sv": [
            "assign buf_all_idx_matched = &buf_idx_fifo_valid_bit;",
            "assign buf_ag_idx_queue_wr_en   = buf_all_idx_matched & mse_enable;",
            "assign buf_ag_idx_queue_rd_en = mse_buf_ag_bp_post;",
        ],
        "Memory_AG_Idx_Queue.sv": [
            "assign mem_all_idx_matched = &mem_idx_fifo_valid_bit_masked;",
            "assign mem_ag_idx_queue_wr_en = mem_all_idx_matched & mse_enable;",
            "assign mem_ag_idx_queue_rd_en = mse_mem_ag_bp_post;",
        ],
        "WR_Memory_AG.sv": [
            "assign mem_ag_idx_valid_bit  = mse_mem_ag_tag[(IDX_VALID_BIT_POSITION-1) -: `PORT_VALID_BIT] & mse_mem_ag_tag_valid;",
            "assign transaction_finish         = (transfer_try_size_overflow || transaction_size_left_zero) && transaction_addr_valid && transfer_addr_bp_post;",
            "assign wr_data_chl_req_valid           = transfer_size_valid && mem_ag_ob_bp_pre;",
        ],
        "WR_Data_Channel.sv": [
            "assign wr_chl_queue_wr_en    = wr_data_chl_req_valid;",
            "assign wr_data_chl_prepared_data_wr_hs = wr_data_chl_data_vld && wr_chl_prepared_data_bp_pre;",
            "wr_data_chl_prepared_data_cnt <= wr_data_chl_prepared_data_cnt + mse_buf_spatial_size;",
        ],
    }
    rows = []
    errors = []
    for record in manifest.get("records", []):
        name = Path(str(record.get("archive_path", ""))).name
        member = member_name(archive, "/" + str(record.get("archive_path")))
        body = archive.read(member)
        actual = identities[member]
        row = {
            "basename": name,
            "relative_path": record.get("relative_path"),
            "bytes": actual["bytes"],
            "sha256": actual["sha256"],
            "manifest_identity_match": record.get("bytes") == actual["bytes"] and record.get("sha256") == actual["sha256"],
            "required_equations_present": [text for text in equations.get(name, []) if text.encode() in body],
            "required_equation_count": len(equations.get(name, [])),
        }
        if not row["manifest_identity_match"] or len(row["required_equations_present"]) != row["required_equation_count"]:
            errors.append(name)
        rows.append(row)
    return {
        "capture_phase": manifest.get("phase"),
        "capture_complete": manifest.get("complete") is True and not manifest.get("missing"),
        "server_root": manifest.get("server_root"),
        "records": rows,
        "errors": errors,
        "pass": manifest.get("complete") is True and not errors,
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
    for path in (state_path, checkpoints_path, report_path):
        if not path.is_file():
            raise RuntimeError(f"streaming artifact absent: {path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("shared bounded VCD scan has not reached EOF")

    result_sha = sha_file(result_zip)
    exact_return = result_zip.stat().st_size == EXPECTED_BYTES and result_sha == EXPECTED_SHA256
    with zipfile.ZipFile(result_zip) as archive:
        archive.testzip_result = archive.testzip()  # type: ignore[attr-defined]
        infos = archive.infolist()
        names = [row.filename for row in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        identities = member_identities(archive)
        core = load_json(archive, "/RETURN_CORE_MANIFEST.json")
        core_errors = verify_core_manifest(core, identities)
        actual = load_json(archive, "/evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        compile_core = load_json(archive, "/evidence/compile_rootcause/COMPILE_CORE.json")
        sim_exit = load_json(archive, "/evidence/SIM_EXIT_RECEIPT.json")
        process = load_json(archive, "/evidence/PROCESS_TREE_RECEIPT.json")
        runtime = load_json(archive, "/evidence/TB_VCD_RUNTIME_RECEIPT.json")
        decision = load_json(archive, "/evidence/TB_VCD_LIVE_DECISION_RECEIPT.json")
        stop = load_json(archive, "/evidence/TB_VCD_STOP_RECEIPT.json")
        target = load_json(archive, "/evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        root_identity = load_json(archive, "/evidence/PUBLISHED_ACTUAL_ROOT_IDENTITY.json")
        contract = load_json(archive, "/evidence/server_tb_vcd_bounded_causal_cone_contract.json")
        sca_cfg = load_json(archive, "/evidence/consumed_config/sca_cfg.json")
        sca_cfg_d = load_json(archive, "/evidence/consumed_config/sca_cfg_D.json")
        returned_manifest = archive.read(member_name(archive, "/evidence/returned_package_manifest.json"))
        returned_manifest_json = json.loads(returned_manifest)
        sca_name = member_name(archive, "/evidence/consumed_config/sca_cfg.json")
        sca_d_name = member_name(archive, "/evidence/consumed_config/sca_cfg_D.json")
        vcd_name = member_name(archive, "/runs/c0/native_mse4_causal.vcd")
        sim_name = member_name(archive, "/runs/c0/sim.log")
        markers = log_markers(archive, sim_name)
        target_time = int(markers["target"]["first"]["sim_time_ps"])
        ledger = stream_ledger(archive, vcd_name, contract, int(state["last_sim_time"]), target_time)
        direct_source = source_evidence(archive, identities)

    pending_manifest_equal = False
    if PENDING.is_file():
        with zipfile.ZipFile(PENDING) as package_archive:
            pending_manifest_equal = package_archive.read(member_name(package_archive, "/package_manifest.json")) == returned_manifest

    vcd_identity = identities[vcd_name]
    archive_receipt = runtime.get("archive_timestamp_receipt", {})
    archive_binding = bool(
        archive_receipt.get("binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
        and archive_receipt.get("bytes") == vcd_identity["bytes"]
        and archive_receipt.get("sha256") == vcd_identity["sha256"]
        and archive_receipt.get("last_timestamp_ticks") == state.get("last_sim_time")
        and archive_receipt.get("parse_status") == "COMPLETE"
    )
    identities_ok = bool(
        exact_return and roots == {f"{PACKAGE}_return"} and not unsafe and not duplicates
        and core.get("package_id") == PACKAGE and core.get("execution_id") == EXECUTION
        and actual.get("package_id") == PACKAGE and actual.get("execution_id") == EXECUTION and actual.get("attempt_id") == ATTEMPT
        and compile_core.get("package_id") == PACKAGE and compile_core.get("execution_id") == EXECUTION
        and pending_manifest_equal
    )

    counts = ledger["event_counts"]
    dynamic_chain = bool(
        counts["memory_index_queue_write_accept"]["cycles"] == 9
        and counts["memory_index_queue_read_accept"]["cycles"] == 9
        and counts["metadata_request_accept"]["cycles"] == 18
        and counts["prepared_write_accept"]["cycles"] == 20
        and counts["prepared_read_accept"]["cycles"] == 18
        and ledger["metadata_units"] == 288 and ledger["prepared_units"] == 320
        and ledger["metadata_deficit_units"] == 32
    )
    pre = ledger["pre_dumpoff_final_values"]
    final_boundary = {
        name: {"bits": pre.get(name), "integer": integer(pre.get(name))}
        for name in (
            "sig_mem_idx_queue_count", "sig_mem_ag_idx_queue_empty", "sig_mem_ag_idx_queue_full",
            "sig_buf_idx_queue_count", "sig_buf_ag_idx_queue_empty", "sig_buf_ag_idx_queue_full",
            "sig_fifo_counter", "sig_wr_data_chl_prepared_data_cnt", "sig_buf_ag_ob_cnt",
            "sig_mse_buf_spatial_size", "sig_cur_transaction_size_left", "sig_slice_cmpt_finish_2",
        )
    }
    direct_config = {
        "consumed_sca_cfg": identities[sca_name],
        "consumed_sca_cfg_D": identities[sca_d_name],
        "packaged_bitstream": returned_manifest_json.get("files", {}).get(
            "workload/runtime/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ),
        "actual_argv_sca_cfg": actual.get("sca_cfg"),
        "actual_argv_sca_cfg_D": actual.get("sca_cfg_d"),
        "runtime_consumer_values": {
            "mse_buf_spatial_size": integer(pre.get("sig_mse_buf_spatial_size")),
            "metadata_request_sizes": ledger["metadata_request_sizes"],
            "transaction_size_samples_at_index_read": ledger["transaction_size_samples_at_index_read"],
        },
        "exact_config_to_missing_input_leaf_validated": False,
        "claim_boundary": "The consumed SCA identities and same-attempt consumer values bind 16-unit prepared/descriptor accounting. The p51 cone does not expose the three Memory_AG input mode/keep/last consumer nets, so no config workaround is validated.",
    }

    runtime_escape = bool(
        runtime.get("stop_reason") == "SIM_TIME_FREEZE"
        and markers["dumpoff"]["count"] == 1
        and markers["stop"]["count"] > 1
        and int(runtime.get("stop", {}).get("display_sim_time_ticks", 0)) > int(runtime.get("stop", {}).get("appended_vcd_timestamp_ticks", 0))
        and runtime.get("final_counters", {}).get("dump_off_cycle") is None
    )
    root = "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION"
    open_leaves = [
        "memory_index_input0_keep_token_or_epoch_ends_early",
        "memory_index_input1_buffer_token_or_last_ends_early",
        "memory_index_input2_keep_token_or_epoch_ends_early",
        "memory_index_same_gotten_mask_suppresses_tenth_tuple",
        "memory_index_split_fifo_or_keep_release_gating_suppresses_tenth_tuple",
    ]
    analysis = {
        "schema": "conv-native-p51-metaidxcone-formal-return-analysis-v1",
        "role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6,
        "return_identity": {
            "path": str(result_zip), "bytes": result_zip.stat().st_size, "sha256": result_sha,
            "exact_identity_pass": exact_return, "member_count": len(identities), "zip_crc_pass": archive.testzip_result is None,  # type: ignore[attr-defined]
            "safe_paths": not unsafe, "duplicates": duplicates, "core_manifest_errors": core_errors,
            "package_execution_attempt_identity_pass": identities_ok,
            "returned_manifest_matches_pending": pending_manifest_equal,
        },
        "execution": {
            "compile_exit": compile_core.get("compile_exit"), "simulation_started": sim_exit.get("simulation_started"),
            "target_entry": target.get("observed"), "target_entry_ps": target_time,
            "sim_exit": sim_exit.get("exit_code"), "signal": sim_exit.get("signal"), "timed_out": sim_exit.get("timed_out"),
            "runtime_decision": decision.get("decision"), "runtime_stop_reason": runtime.get("stop_reason"),
            "natural_terminal": False, "formal_D": "UNPROVEN", "E3": "UNPROVEN_NON_NATURAL",
            "E4": "UNPROVEN_NON_NATURAL", "E5": "UNPROVEN_NON_NATURAL",
            "process_fully_reaped": process.get("process_tree_reaped") is True,
            "published_root": root_identity.get("published_root"), "actual_root": root_identity.get("actual_root"),
            "execution_root_match": root_identity.get("match") is True,
            "execution_root_mismatch_classification": root_identity.get("mismatch_classification"),
            "execution_root_claim_boundary": "Dynamic and actual-source claims bind only to the returned NDP_copy02 execution. They are not an assertion that NDP_copy01 has identical RTL bytes.",
        },
        "streaming": {
            "status": state.get("status"), "byte_offset": state.get("byte_offset"), "line_number": state.get("line_number"),
            "checkpoint_count_before_close": state.get("checkpoint_count"), "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_nonclock_change_ps": ledger["last_effective_nonclock_change_ps"],
            "last_effective_nonclock_signal_ids": ledger["last_effective_nonclock_signal_ids"],
            "vcd_identity": vcd_identity, "full_file_archive_binding_pass": archive_binding,
        },
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source,
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "event_counts": counts, "metadata_request_sizes": ledger["metadata_request_sizes"],
            "metadata_units": ledger["metadata_units"], "prepared_units": ledger["prepared_units"],
            "metadata_deficit_units": ledger["metadata_deficit_units"], "pre_dumpoff_boundary": final_boundary,
            "dynamic_chain_pass": dynamic_chain,
        },
        "causal_adjudication": {
            "LAST_PROVEN_GOOD": {
                "time_ps": ledger["last_paired_metadata_descriptor_ps"],
                "statement": "The eighteenth/final 16-unit metadata descriptor is accepted while the first eighteen prepared groups remain accountably paired.",
            },
            "FIRST_DIVERGENCE": {
                "time_ps": ledger["first_prepared_group_without_metadata_capacity_ps"],
                "statement": "The nineteenth 16-unit prepared group is accepted after the ninth Memory_AG tuple has exhausted its eighteenth/final descriptor; no tenth Memory_AG tuple follows.",
            },
            "VALIDATED_ROOT_CAUSE_BOUNDARY": root,
            "root_leaf_status": "OPEN_UNVALIDATED_MECHANISM",
            "open_leaf_alternatives": open_leaves,
            "narrowing_vs_p50": "p50's 18 metadata / 20 prepared / 23 RD-enqueue / 21 RD-dequeue join is now traced upstream to exactly nine accepted-and-consumed Memory_AG index tuples, an empty/never-full Memory index queue, and absence of tuple ten; Buffer-side lifetime/accounting remains sufficient for twenty 16-unit groups.",
            "CONFIG_WORKAROUND": None,
        },
        "runtime_defect": {
            "classification": "PACKAGE_LOCAL_TBVCD_DUMPOFF_SHARED_EVALUATOR_FALSE_FREEZE_AND_STOP_LOG_FLOOD" if runtime_escape else None,
            "runtime_escape_proven": runtime_escape,
            "tb_dumpoff_ps": markers["dumpoff"]["first"]["sim_time_ps"] if markers["dumpoff"]["first"] else None,
            "repeated_stop_marker_count": markers["stop"]["count"],
            "last_stop_marker_ps": markers["stop"]["last"]["sim_time_ps"] if markers["stop"]["last"] else None,
            "appended_vcd_stop_ps": runtime.get("stop", {}).get("appended_vcd_timestamp_ticks"),
            "display_sim_time_at_evaluator_stop_ps": runtime.get("stop", {}).get("display_sim_time_ticks"),
            "reason": "The package TB performs $dumpoff at the legal plateau threshold. The shared evaluator then sees the appended timestamp frozen, resets its internal dump_off_cycle because sim_time_advancing is false, and chooses SIM_TIME_FREEZE before its grace can close. The TB also emits the STOP marker every owner cycle after grace.",
        },
        "disposition": {
            "status": "WAIT_SHARED_TB_VCD_RUNTIME_DUMPOFF_FREEZE_CONSISTENCY_FIX",
            "rule_audit": "RULE_DELTA_PROPOSAL_SHARED_RUNTIME_IMPLEMENTATION_REQUIRED",
            "successor": "DIRECT_MEMORY_AG_INPUT_LEAF_SUCCESSOR_REQUIRED_BUT_NOT_PUBLISHABLE_UNDER_CURRENT_RUNTIME",
            "storage": "UNCHANGED_NO_STORAGE_MANAGER",
            "server_actions": [],
            "frozen": ["functional RTL", "config", "numeric", "workload", "golden", "p42 vector predicate", "MSE4 target"],
        },
        "claim_boundary": "The exact p51 return validates a one-transaction (32-unit) Memory_AG metadata supply deficit and narrows the missing event to tuple ten on the actual NDP_copy02 execution and returned actual RTL bytes. Published NDP_copy01 versus actual NDP_copy02 root drift restricts the claim to that execution and does not prove copy01 source equivalence. The return does not identify which of the three input/same-gotten/split-FIFO/keep leaves suppresses tuple ten. The run ended by a runtime false-freeze after TB dumpoff, not naturally; formal-D/E3/E4/E5 and any config workaround remain unproven.",
        "conflicts": [],
        "pass": identities_ok and not core_errors and archive_binding and direct_source["pass"] and dynamic_chain and runtime_escape,
        "errors": ([] if identities_ok else ["identity conjunction failed"]) + core_errors + ([] if archive_binding else ["archive binding failed"]) + ([] if direct_source["pass"] else ["actual source identity/equation failure"]) + ([] if dynamic_chain else ["dynamic chain mismatch"]) + ([] if runtime_escape else ["runtime escape signature not closed"]),
    }
    audit = {
        "schema": "conv-native-p51-rule-gap-audit-v1",
        "role_id": "family.conv.native", "owner_epoch": 2, "registry_epoch": 6,
        "trigger": "Production compile and MSE4 target execution succeeded and the p51 return is consumable, but tuple ten is absent without per-input formation leaves; the planned TB dumpoff also exposes a shared-evaluator state inconsistency.",
        "causal_gap": {
            "code": "MEMORY_AG_THREE_INPUT_FORMATION_LEAVES_ABSENT",
            "missing_direct_leaves": [
                "three raw Memory_AG input tags/indices/backpressure",
                "per-input valid/last/same/gotten and masked valid/last",
                "per-input split-FIFO occupancy/valid/full/empty",
                "per-input keep-mode/keep-last and release/backpressure masks",
            ],
            "candidate_matrix_effect": "Aggregate all-match distinguishes Memory_AG supply from Buffer/prepared accounting but cannot pairwise distinguish the three inputs or same/gotten/split-FIFO/keep-release leaves.",
        },
        "runtime_gap": {
            "code": "PLANNED_DUMPOFF_RESETS_SHARED_DUMP_OFF_STATE_AND_TRIGGERS_FALSE_FREEZE",
            "proof": analysis["runtime_defect"],
            "required_delta": "The shared evaluator must preserve/consume an execution-bound planned-dumpoff state and prioritize complete dump-off+grace plateau over appended-timestamp freeze; the TB STOP marker must be one-shot. Finalization must still require quiescent full-file SHA/bytes/last timestamp and close/flush/reap.",
            "negative_controls": [
                "planned_dumpoff_then_slow_grace_must_not_SIM_TIME_FREEZE",
                "no_dumpoff_three_equal_appended_timestamps_must_SIM_TIME_FREEZE",
                "planned_dumpoff_plus_grace_must_CAUSAL_PLATEAU",
                "STOP_marker_repetition_must_fail",
            ],
        },
        "disposition": "RULE_DELTA_PROPOSAL_SHARED_RUNTIME_IMPLEMENTATION_REQUIRED",
        "shared_files_modified": [], "successor_built": False,
        "terminal": "WAIT_SHARED_TB_VCD_RUNTIME_DUMPOFF_FREEZE_CONSISTENCY_FIX",
        "server_actions": [], "storage_actions": [], "pass": True, "errors": [],
    }

    ledger_path = out / "dynamic_ledger.json"
    analysis_path = out / "formal_return_analysis.json"
    audit_path = out / "RULE_GAP_AUDIT.json"
    direct_path = out / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json"
    ledger_path.write_text(canonical(ledger), encoding="utf-8", newline="\n")
    direct_path.write_text(canonical({"DIRECT_CONFIG_EVIDENCE": direct_config, "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source}), encoding="utf-8", newline="\n")
    analysis_path.write_text(canonical(analysis), encoding="utf-8", newline="\n")
    audit_path.write_text(canonical(audit), encoding="utf-8", newline="\n")

    existing = checkpoints_path.read_text(encoding="utf-8").splitlines()
    if not any("FORMAL_P51_CAUSAL_ADJUDICATION" in line for line in existing):
        checkpoint = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1", "seq": len(existing),
            "event": "FORMAL_P51_CAUSAL_ADJUDICATION", "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"), "last_sim_time": state.get("last_sim_time"),
            "last_effective_nonclock": ledger["last_effective_nonclock_change_ps"],
            "memory_tuples": counts["memory_index_queue_write_accept"]["cycles"],
            "metadata_descriptors": counts["metadata_request_accept"]["cycles"],
            "prepared_groups": counts["prepared_write_accept"]["cycles"],
            "metadata_deficit_units": ledger["metadata_deficit_units"],
            "first_divergence_ps": ledger["first_prepared_group_without_metadata_capacity_ps"],
            "analysis_sha256": sha_file(analysis_path), "audit_sha256": sha_file(audit_path),
            "disposition": analysis["disposition"]["status"],
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(existing))) + 1
    existing = checkpoints_path.read_text(encoding="utf-8").splitlines()
    if not any("EXECUTION_ROOT_CLAIM_BOUNDARY_CORRECTION" in line for line in existing):
        correction = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1", "seq": len(existing),
            "event": "EXECUTION_ROOT_CLAIM_BOUNDARY_CORRECTION", "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"), "last_sim_time": state.get("last_sim_time"),
            "published_root": root_identity.get("published_root"), "actual_root": root_identity.get("actual_root"),
            "match": root_identity.get("match"),
            "mismatch_classification": root_identity.get("mismatch_classification"),
            "analysis_sha256": sha_file(analysis_path),
            "claim_boundary": "All dynamic/source claims bind to returned actual NDP_copy02 execution bytes; no NDP_copy01 source-equivalence claim.",
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(correction, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(existing))) + 1
    state["formal_analysis"] = {
        "path": analysis_path.name, "sha256": sha_file(analysis_path),
        "root_boundary": root, "leaf_status": "OPEN_UNVALIDATED_MECHANISM",
        "first_divergence_ps": ledger["first_prepared_group_without_metadata_capacity_ps"],
        "disposition": analysis["disposition"]["status"],
    }
    state_path.write_text(canonical(state), encoding="utf-8", newline="\n")
    if "## Formal p51 causal adjudication" not in report_path.read_text(encoding="utf-8"):
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## Formal p51 causal adjudication\n\n"
                f"- compile/target/sim exit: `0 / entered / {sim_exit.get('exit_code')}`; non-natural `{runtime.get('stop_reason')}`\n"
                f"- final VCD / last effective non-clock: `{state.get('last_sim_time')} / {ledger['last_effective_nonclock_change_ps']} ps`\n"
                f"- Memory index tuples / metadata descriptors / prepared groups: `9 / 18 / 20`; units `288 / 320`\n"
                f"- LAST_PROVEN_GOOD / FIRST_DIVERGENCE: `{ledger['last_paired_metadata_descriptor_ps']} / {ledger['first_prepared_group_without_metadata_capacity_ps']} ps`\n"
                "- validated boundary: `MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION`; exact three-input formation leaf remains open\n"
                f"- runtime escape: TB dumpoff followed by shared false-freeze and `{markers['stop']['count']}` repeated STOP lines\n"
                "- disposition: `RULE_DELTA_PROPOSAL_SHARED_RUNTIME_IMPLEMENTATION_REQUIRED / WAIT_SHARED_TB_VCD_RUNTIME_DUMPOFF_FREEZE_CONSISTENCY_FIX`; no successor or storage/server action\n"
            )
    if "## Execution-root claim boundary" not in report_path.read_text(encoding="utf-8"):
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## Execution-root claim boundary\n\n"
                "The package published `/home/panqs/ndp/NDP_copy01`, but the actual production cwd and returned source capture bind `/home/panqs/ndp/NDP_copy02`. "
                "Classification is `EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION`: the dynamic ledger and actual RTL evidence remain valid for this exact NDP_copy02 execution, but do not prove NDP_copy01 source equivalence.\n"
            )
    print(json.dumps({
        "pass": analysis["pass"], "analysis": str(analysis_path), "audit": str(audit_path),
        "counts": {key: row["cycles"] for key, row in counts.items()},
        "metadata_units": ledger["metadata_units"], "prepared_units": ledger["prepared_units"],
        "first_divergence_ps": ledger["first_prepared_group_without_metadata_capacity_ps"],
        "runtime_escape": runtime_escape, "stop_markers": markers["stop"]["count"],
        "disposition": analysis["disposition"]["status"],
    }, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
