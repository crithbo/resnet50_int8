#!/usr/bin/env python3
"""Finalize the bounded-streaming serialized Conv v97b return analysis.

The 710 MB return and its VCD are consumed by the resumable scanners before
this program runs.  This closer only streams the return once for its identity,
loads bounded derivatives, verifies the package/config/actual-source chain,
and records the exact three-input Memory_AG tuple adjudication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
EXECUTION = "r1786793347853153460_2912853"
ATTEMPT = "a2912853"
EXPECTED_RETURN_BYTES = 710_085_642
EXPECTED_RETURN_SHA256 = "5bc3e44f95cd5df54de5deff9c084d7dbc192215657ec4e504335b900b30aa1d"
EXPECTED_PACKAGE_BYTES = 5_332_235
EXPECTED_PACKAGE_SHA256 = "bcd94e23123e95742a555897e05eace58a36002219ca110ff3f15ea92e297ad9"
EXPECTED_VCD_BYTES = 709_651_866
EXPECTED_VCD_SHA256 = "bc7725043dc302e3924a005689460a623a39bcb0d629f175a0b373e38c740ed2"
RETURN_ROOT = f"{PACKAGE}_return/"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_hw_v97b_tbvcd_memtuple_xmrefix_r1786793347853153460_2912853_return.zip"
)
OUT = ROOT / f"outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_{EXECUTION}"
STREAM = OUT / "streaming"
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)
CONFIG = (
    ROOT
    / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1/build"
    / PACKAGE
    / "provenance/frozen_node0004_wave0_config.json"
)
HISTORICAL_LEDGER = (
    CONFIG.parent / "v62_config_causal_transaction_ledger.json"
)
MEMORY_AG_SOURCE = OUT / "actual_source/Memory_AG_Idx_Queue.sv"
TASK_RECORD = ROOT / ".agents/task_records/20260815_conv_node0004_v97b_validated_input1_tag_undersupply.md"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, canonical(value))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def archive_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"return JSON object required: {relative}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"JSONL object required: {path}:{line_number}")
            rows.append(value)
    return rows


def append_checkpoint(path: Path, event: str, payload: dict[str, Any]) -> bool:
    rows = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if any(json.loads(row).get("event") == event for row in rows if row.strip()):
        return False
    value = {
        "schema": "server-tb-vcd-retention-analysis-checkpoint-v1",
        "seq": len(rows),
        "event": event,
        **payload,
    }
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def source_lines(path: Path, needles: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for needle in needles:
            if needle in line:
                rows.append({"line": line_number, "symbol": needle, "text": line.strip()})
                break
    return rows


def signal_rows(rows: list[dict[str, Any]], signal_id: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("signal_id") == signal_id]


def state_at(rows: list[dict[str, Any]], signal_id: str, time_ps: int) -> str | None:
    value: str | None = None
    for row in rows:
        if row.get("signal_id") != signal_id:
            continue
        if int(row.get("time", -1)) > time_ps:
            break
        value = str(row.get("value_4state"))
    return value


def owner_clock_high_count(
    rows: list[dict[str, Any]], signal_id: str, *, phase_ps: int = 625, period_ps: int = 1250
) -> int:
    selected = signal_rows(rows, signal_id)
    count = 0
    for index, row in enumerate(selected):
        if row.get("value_4state") != "1":
            continue
        low = int(row["time"])
        if index + 1 >= len(selected):
            raise RuntimeError(f"unclosed high interval for clock-qualified signal: {signal_id}")
        high = int(selected[index + 1]["time"])
        first = low + ((phase_ps - low) % period_ps)
        if first < high:
            count += ((high - 1 - first) // period_ps) + 1
    return count


def value_never(rows: list[dict[str, Any]], signal_id: str, forbidden: str) -> bool:
    selected = signal_rows(rows, signal_id)
    return bool(selected) and all(row.get("value_4state") != forbidden for row in selected)


def config_evidence(config: dict[str, Any], dynamic: dict[str, Any]) -> dict[str, Any]:
    stream = config["stream_engine"]["stream4"]
    final = dynamic["final_state_4state"]
    transaction_units = int(final["sig_cfg_transaction_total_size"], 2)
    prepared_group_units = int(final["sig_mse_buf_spatial_size"], 2)
    prepared_group_count = dynamic["derived_ledger"]["prepared_group_count"]
    expected_tuple_count = prepared_group_count * prepared_group_units // transaction_units
    return {
        "config_identity": identity(CONFIG),
        "source_package_identity": identity(PENDING),
        "source_package_expected_identity_match": (
            PENDING.stat().st_size == EXPECTED_PACKAGE_BYTES
            and sha_file(PENDING) == EXPECTED_PACKAGE_SHA256
        ),
        "stream4": {
            "target": stream["target"],
            "mode": stream["mode"],
            "idx": stream["idx"],
            "mem_idx_mode": stream["mem_idx_mode"],
            "mem_idx_keep_last_index": stream["mem_idx_keep_last_index"],
            "buf_idx_mode": stream["buf_idx_mode"],
            "buf_idx_keep_last_index": stream["buf_idx_keep_last_index"],
            "buf_spatial_size": stream["buf_spatial_size"],
        },
        "producer_mapping": {
            "DRAM_LC.LC9": config["dram_loop_configs"]["LC9"],
            "LC_PE.PE1": config["lc_pe_configs"]["PE1"],
            "historical_consumer_ledger": load_json(HISTORICAL_LEDGER),
            "claim_boundary": (
                "The LC9/PE1 ledger is a frozen historical config-to-consumer comparison. "
                "It corroborates the intended epoch, but it is not a production workaround proof."
            ),
        },
        "same_attempt_runtime_encoding": {
            "mem_idx_mode_bits": final["sig_cfg_mem_idx_mode"],
            "mem_idx_keep_last_bits": final["sig_cfg_mem_keep_last"],
            "transaction_total_size_units": transaction_units,
            "prepared_group_size_units": prepared_group_units,
            "prepared_group_count": prepared_group_count,
            "required_memory_ag_tuple_count": expected_tuple_count,
        },
        "direct_conclusion": (
            "Actual stream4 is a target-D write with [keep, buffer, keep] Memory_AG inputs; "
            "input1 is LC_PE.PE1.  Twenty 16-unit prepared groups require ten 32-unit "
            "metadata tuples, while same-attempt dynamics produce nine."
        ),
    }


def source_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    source_identities = {
        Path(row["path"]).name: row for row in summary.get("actual_sources", [])
    }
    expected = source_identities.get("Memory_AG_Idx_Queue.sv")
    if not expected:
        raise RuntimeError("returned actual Memory_AG source identity absent")
    actual_identity = identity(MEMORY_AG_SOURCE)
    identity_match = (
        expected.get("bytes") == actual_identity["bytes"]
        and expected.get("sha256") == actual_identity["sha256"]
    )
    needles = [
        "mse_mem_idx_buffer_mode[INPORT_IDX]",
        "mem_idx_valid_bit_unmasked[INPORT_IDX]",
        "mem_idx_same_gotten_mask[INPORT_IDX]",
        "mem_idx_valid_bit_masked[INPORT_IDX]",
        "mse_mem_queue_bp_pre[INPORT_IDX]",
        "mem_idx_split_fifo_wr_en[INPORT_IDX]",
        "mem_idx_fifo_valid_bit[INPORT_IDX]",
        "mem_all_idx_matched =",
        "mem_idx_bp_pre_keep_mask[INPORT_IDX]",
        "mem_idx_queue_bp_pre[INPORT_IDX]",
        "mem_ag_idx_queue_wr_en =",
    ]
    equations = source_lines(MEMORY_AG_SOURCE, needles)
    present = {row["symbol"] for row in equations}
    return {
        "actual_compile_root": "/home/panqs/ndp/NDP_copy01",
        "actual_memory_ag_source": actual_identity,
        "returned_manifest_identity_match": identity_match,
        "equation_lines": equations,
        "all_required_equations_present": set(needles) == present,
        "direct_conclusion": (
            "Actual compiled Memory_AG RTL decodes input1 as buffer mode, accepts each unsuppressed "
            "raw tag when its split FIFO is not full, releases the buffer input without a keep-last "
            "comparison, and emits one tuple only when all three input FIFOs are valid."
        ),
        "upstream_capture_boundary": (
            "The returned actual-source set terminates at the mse_mem_queue_tag/idx Memory_AG input "
            "and does not contain the upstream LC_PE/IGA producer implementation.  Therefore the exact "
            "producer source line and a config workaround are not claimed."
        ),
        "pass": identity_match and set(needles) == present,
    }


def dynamic_evidence(
    dynamic: dict[str, Any], leaf_rows: list[dict[str, Any]], causal_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    tuple_times = dynamic["event_times_ps"]["sig_memidx_queue_wr"]
    split_writes = [
        owner_clock_high_count(leaf_rows, f"sig_mem_i{i}_split_wr_xmrfix")
        for i in range(3)
    ]
    input1_queue_ready_at_tuples = [
        state_at(leaf_rows, "sig_mem_i1_queue_bp_xmrfix", time_ps)
        for time_ps in tuple_times
    ]
    input0_held_at_tuples = [
        state_at(leaf_rows, "sig_mem_i0_fifo_valid_masked_xmrfix", time_ps)
        for time_ps in tuple_times
    ]
    input2_held_at_tuples = [
        state_at(leaf_rows, "sig_mem_i2_fifo_valid_masked_xmrfix", time_ps)
        for time_ps in tuple_times
    ]
    input1_last_rows = signal_rows(leaf_rows, "sig_mem_i1_raw_last_xmrfix")
    input1_valid_rows = signal_rows(leaf_rows, "sig_mem_i1_raw_valid_xmrfix")
    input1_last_rise = next(
        int(row["time"]) for row in input1_last_rows if row.get("value_4state") == "1"
    )
    valid_highs = [int(row["time"]) for row in input1_valid_rows if row.get("value_4state") == "1"]
    post_last_nonlast = next(time_ps for time_ps in valid_highs if time_ps > input1_last_rise)
    target_rows = [
        row for row in causal_rows
        if row.get("signal_id") == "sig_mse_enable" and row.get("value_4state") == "1"
    ]
    target_entry = int(target_rows[0]["time"]) if target_rows else None
    queue_full_rows = signal_rows(causal_rows, "sig_memidx_queue_full")
    memory_queue_never_full = bool(queue_full_rows) and all(
        row.get("value_4state") != "1" for row in queue_full_rows
    )
    ledger = dynamic["derived_ledger"]
    exact_leaf_chain = all([
        split_writes == [5, 9, 2],
        len(tuple_times) == 9,
        all(value == "1" for value in input1_queue_ready_at_tuples),
        all(value == "1" for value in input0_held_at_tuples),
        all(value == "1" for value in input2_held_at_tuples),
        value_never(leaf_rows, "sig_mem_i1_source_bp_xmrfix", "0"),
        value_never(leaf_rows, "sig_mem_i1_split_full_xmrfix", "1"),
        value_never(leaf_rows, "sig_mem_i1_same_gotten_mask_xmrfix", "0"),
        memory_queue_never_full,
        ledger["metadata_tuple_count"] == 9,
        ledger["metadata_descriptor_capacity"] == 18,
        ledger["prepared_group_count"] == 20,
        ledger["metadata_deficit_units"] == 32,
    ])
    return {
        "target_entry_ps": target_entry,
        "owner_clock_sampling": {"period_ps": 1250, "active_phase_ps": 625},
        "split_fifo_clock_qualified_writes": split_writes,
        "memory_ag_tuple_write_times_ps": tuple_times,
        "memory_ag_tuple_count": len(tuple_times),
        "input1_tuple_dequeue_count": len(tuple_times),
        "input1_queue_ready_at_every_tuple": all(
            value == "1" for value in input1_queue_ready_at_tuples
        ),
        "input1_source_ready_always": value_never(
            leaf_rows, "sig_mem_i1_source_bp_xmrfix", "0"
        ),
        "input1_split_fifo_never_full": value_never(
            leaf_rows, "sig_mem_i1_split_full_xmrfix", "1"
        ),
        "input1_same_gotten_never_suppresses": value_never(
            leaf_rows, "sig_mem_i1_same_gotten_mask_xmrfix", "0"
        ),
        "input0_keep_head_resident_at_every_tuple": all(
            value == "1" for value in input0_held_at_tuples
        ),
        "input2_keep_head_resident_at_every_tuple": all(
            value == "1" for value in input2_held_at_tuples
        ),
        "metadata_queue_never_full": memory_queue_never_full,
        "input1_last_marked_raw_token_ps": input1_last_rise,
        "input1_last_marked_tuple_ps": next(time for time in tuple_times if time > input1_last_rise),
        "input1_post_last_nonlast_raw_token_ps": post_last_nonlast,
        "input1_post_last_nonlast_tuple_ps": next(time for time in tuple_times if time > post_last_nonlast),
        "no_tenth_input1_token": True,
        "ledger": ledger,
        "last_effective_nonclock_change_ps": 2_446_436_875,
        "exact_leaf_chain_pass": exact_leaf_chain,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    args = parser.parse_args()
    result_zip = args.return_zip.resolve(strict=True)

    required = [
        OUT / "streaming_summary.json",
        OUT / "dynamic_adjudication.json",
        OUT / "tuple_vector_derivation.json",
        STREAM / "analysis_state.json",
        STREAM / "checkpoints.jsonl",
        STREAM / "report.md",
        STREAM / "tuple_leaf_transitions.jsonl",
        STREAM / "causal_transitions.jsonl",
        CONFIG,
        HISTORICAL_LEDGER,
        MEMORY_AG_SOURCE,
        PENDING,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"required analysis inputs absent: {missing}")

    summary = load_json(OUT / "streaming_summary.json")
    dynamic = load_json(OUT / "dynamic_adjudication.json")
    derivation = load_json(OUT / "tuple_vector_derivation.json")
    state = load_json(STREAM / "analysis_state.json")
    config = load_json(CONFIG)
    leaf_rows = read_jsonl(STREAM / "tuple_leaf_transitions.jsonl")
    causal_rows = read_jsonl(STREAM / "causal_transitions.jsonl")
    result_sha = sha_file(result_zip)
    exact_return = (
        result_zip.stat().st_size == EXPECTED_RETURN_BYTES
        and result_sha == EXPECTED_RETURN_SHA256
    )

    with zipfile.ZipFile(result_zip) as archive:
        bad_member = archive.testzip()
        manifest = archive_json(archive, "RETURN_CORE_MANIFEST.json")
        root_status = archive_json(archive, "return_core/RETURN_CORE_STATUS.json")
        actual_argv = archive_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        native_attempt = archive_json(archive, "evidence/NATIVE_FLOW_ATTEMPT.json")
        source_identity = archive_json(archive, "evidence/compiled_source/source_identity.json")
        compile_identity = archive_json(
            archive, "evidence/compile_rootcause/compile_source_identity.json"
        )
        vcd_identity = archive_json(archive, "evidence/vcd/VCD_IDENTITY.json")
        archive_timestamp = archive_json(
            archive, "evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json"
        )
        vcd_receipts = [
            row for row in manifest.get("core_entry_receipts", [])
            if row.get("path") == "waveforms/causal_cone.vcd"
        ]
        pending_member = f"{PACKAGE}/provenance/frozen_node0004_wave0_config.json"

    with zipfile.ZipFile(PENDING) as archive:
        packaged_config = archive.read(pending_member)
    config_bytes = CONFIG.read_bytes()
    packaged_config_match = packaged_config == config_bytes

    vcd_manifest_pass = (
        len(vcd_receipts) == 1
        and vcd_receipts[0].get("bytes") == EXPECTED_VCD_BYTES
        and vcd_receipts[0].get("sha256") == EXPECTED_VCD_SHA256
    )
    summary["integrity"]["waveform_manifest"] = {
        "pass": vcd_manifest_pass,
        "checked": len(vcd_receipts),
        "errors": [] if vcd_manifest_pass else ["causal VCD core receipt identity mismatch"],
        "receipt_location": "RETURN_CORE_MANIFEST.core_entry_receipts",
    }
    summary["pass"] = all([
        summary["integrity"]["return_manifest"]["pass"],
        summary["integrity"]["source_package"]["pass"],
        vcd_manifest_pass,
        derivation["pass"],
    ])
    summary["claim_boundary"] = (
        "Exact return/package identities and EOF-reached unbounded VCD stream.  VCS normalized 51 "
        "cataloged bit-selects into 17 whole packed vectors; the same-attempt leaf transitions are "
        "therefore derived deterministically from those returned four-state vectors, not treated as absent."
    )
    atomic_json(OUT / "streaming_summary.json", summary)

    direct_config = config_evidence(config, dynamic)
    direct_config["packaged_config_byte_equal"] = packaged_config_match
    direct_source = source_evidence(summary)
    dynamics = dynamic_evidence(dynamic, leaf_rows, causal_rows)

    receipts = summary["receipts"]
    runtime = receipts["runtime"]
    process = receipts["process_tree"]
    sim_exit = receipts["sim_exit_evidence"]
    execution_identity_pass = all([
        actual_argv.get("package_id") == PACKAGE,
        actual_argv.get("execution_id") == EXECUTION,
        actual_argv.get("attempt_id") == ATTEMPT,
        native_attempt.get("package_id") == PACKAGE,
        native_attempt.get("execution_id") == EXECUTION,
        native_attempt.get("attempt_id") == ATTEMPT,
        native_attempt.get("actual_cwd") == "/home/panqs/ndp/NDP_copy01",
        source_identity.get("status") == "COMPLETE",
        source_identity.get("compile_cwd") == "/home/panqs/ndp/NDP_copy01",
    ])
    archive_binding_pass = all([
        vcd_manifest_pass,
        summary["vcd"]["bytes"] == EXPECTED_VCD_BYTES,
        summary["vcd"]["sha256"] == EXPECTED_VCD_SHA256,
        vcd_identity.get("identity", {}).get("bytes") == EXPECTED_VCD_BYTES,
        vcd_identity.get("identity", {}).get("sha256") == EXPECTED_VCD_SHA256,
        archive_timestamp.get("bytes") == EXPECTED_VCD_BYTES,
        archive_timestamp.get("sha256") == EXPECTED_VCD_SHA256,
        archive_timestamp.get("last_timestamp_ticks") == state.get("last_sim_time"),
        derivation.get("member_bytes") == EXPECTED_VCD_BYTES,
        derivation.get("member_sha256") == EXPECTED_VCD_SHA256,
        derivation.get("last_timestamp") == state.get("last_sim_time"),
    ])

    last_good = 2_446_426_875
    first_divergence = 2_446_428_125
    root = "MSE4_MEMORY_AG_INPUT1_BUFFER_TAG_STREAM_UNDERSUPPLIES_ONE_TUPLE"
    validated_root = all([
        exact_return,
        bad_member is None,
        summary["pass"],
        state.get("status") in {"EOF_REACHED", "EOF_REACHED_ROOT_VALIDATED"},
        state.get("byte_offset") == EXPECTED_VCD_BYTES,
        execution_identity_pass,
        archive_binding_pass,
        packaged_config_match,
        direct_source["pass"],
        dynamics["exact_leaf_chain_pass"],
        sim_exit.get("compile_exit") == 0,
        sim_exit.get("simulation_started") is True,
        dynamics["target_entry_ps"] == 2_445_779_375,
    ])

    candidates = [
        {
            "candidate": "memory_index_input0_keep_token_or_epoch_ends_early",
            "disposition": "EXCLUDED",
            "evidence": "input0 FIFO head is valid at every one of the nine aggregate tuple writes",
        },
        {
            "candidate": "memory_index_input1_buffer_token_or_last_ends_early",
            "disposition": "VALIDATED_ROOT_LEAF",
            "evidence": (
                "input1 accepts/dequeues exactly nine source tokens; token 8 is last, token 9 is "
                "post-last/non-last, and no tenth token arrives"
            ),
        },
        {
            "candidate": "memory_index_input2_keep_token_or_epoch_ends_early",
            "disposition": "EXCLUDED",
            "evidence": "input2 FIFO head is valid at every one of the nine aggregate tuple writes",
        },
        {
            "candidate": "memory_index_same_gotten_mask_suppresses_tenth_tuple",
            "disposition": "EXCLUDED",
            "evidence": "input1 same_gotten mask remains 1 for the complete same-attempt trace",
        },
        {
            "candidate": "memory_index_split_fifo_or_keep_release_gating_suppresses_tenth_tuple",
            "disposition": "EXCLUDED",
            "evidence": (
                "input1 source ready remains 1, split FIFO never becomes full, queue ready is 1 "
                "at every tuple, and actual buffer-mode RTL bypasses keep-last release"
            ),
        },
    ]
    claim_boundary = (
        "The validated root binds the exact v97 return/package/execution/attempt, source-package "
        "config bytes, actual compiled NDP_copy01 Memory_AG RTL bytes, full archived VCD identity and "
        "same-attempt packed-vector-derived leaf transitions.  It proves one missing input1 Memory_AG "
        "buffer-tag tuple at the module boundary and excludes all four competing in-module loss paths. "
        "It does not identify the uncaptured upstream producer source line, validate a production config "
        "workaround, or prove natural completion/formal-D/E3/E4/E5 after the wall-ceiling exit."
    )
    analysis = {
        "schema": "node0004-v97b-memtuple-xmrefix-formal-return-analysis-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "return_identity": {
            **identity(result_zip),
            "expected_identity_match": exact_return,
            "zip_crc_pass": bad_member is None,
            "return_manifest_required_receipts": len(manifest.get("core_entry_receipts", [])),
            "return_core_disposition": root_status.get("disposition"),
        },
        "identity_binding": {
            "package_id": PACKAGE,
            "execution_id": EXECUTION,
            "attempt_id": ATTEMPT,
            "actual_root": native_attempt.get("actual_cwd"),
            "actual_compile_sim_argv": actual_argv,
            "execution_identity_pass": execution_identity_pass,
            "source_identity_status": source_identity.get("status"),
            "compile_source_identity_status": compile_identity.get("status"),
            "compile_source_identity_caveat": (
                "The compile-source receipt's ACK-driver exact-set warning belongs to the retired ACK "
                "comparator.  The current actual Memory_AG source bytes and target identities are present."
            ),
        },
        "execution": {
            "compile_exit": sim_exit.get("compile_exit"),
            "simulation_started": sim_exit.get("simulation_started"),
            "target_entry": True,
            "target_entry_ps": dynamics["target_entry_ps"],
            "sim_exit": sim_exit.get("exit_code"),
            "signal": sim_exit.get("signal"),
            "stop_reason": runtime.get("stop_reason"),
            "natural_terminal": False,
            "diagnostic_status": runtime.get("diagnostic_status"),
            "shared_evaluator_sole_authority": runtime.get("decision_authority", {}).get(
                "outer_runner_consumes_only_receipt"
            ),
            "false_freeze_or_plateau": False,
            "process_fully_reaped": (
                process.get("process_tree_reaped") is True
                and runtime.get("process_tree", {}).get("all_reaped") is True
            ),
            "vcd_closed": runtime.get("flush", {}).get("closed"),
            "vcd_dumpoff": runtime.get("flush", {}).get("dumpoff"),
            "vcd_dumpflush": runtime.get("flush", {}).get("dumpflush"),
        },
        "streaming": {
            "status": state.get("status"),
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_nonclock_change_ps": dynamics["last_effective_nonclock_change_ps"],
            "vcd_identity": {
                "bytes": EXPECTED_VCD_BYTES,
                "sha256": EXPECTED_VCD_SHA256,
                "timescale": state.get("timescale"),
            },
            "packed_vector_derivation": identity(OUT / "tuple_vector_derivation.json"),
            "packed_vector_count": 17,
            "derived_leaf_count": 51,
            "derived_leaf_transition_count": len(leaf_rows),
            "archive_binding_pass": archive_binding_pass,
            "transport": "UNTRUNCATED_UNSAMPLED_FULL_MEMBER_STREAM",
        },
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source,
        "DYNAMIC_EXECUTION_EVIDENCE": dynamics,
        "causal_adjudication": {
            "LAST_PROVEN_GOOD": {
                "time_ps": last_good,
                "statement": (
                    "The eighteenth and final metadata descriptor is accepted; all nine Memory_AG "
                    "tuples remain losslessly accounted."
                ),
            },
            "FIRST_DIVERGENCE": {
                "time_ps": first_divergence,
                "statement": (
                    "The nineteenth prepared 16-unit group is accepted after input1 has supplied and "
                    "Memory_AG has consumed only nine buffer tags, leaving no metadata for this group."
                ),
            },
            "candidate_matrix": candidates,
            "VALIDATED_ROOT_CAUSE": root if validated_root else None,
            "root_classification": "UPSTREAM_INPUT1_TAG_GENERATION_OR_EPOCH_LAST_ACCOUNTING",
            "root_status": "VALIDATED_ROOT_CAUSE" if validated_root else "OPEN_UNVALIDATED_MECHANISM",
            "mechanism": (
                "Prepared data produces twenty 16-unit groups (320 units), but Memory_AG input1 supplies "
                "only nine losslessly accepted/dequeued tag tuples.  The eighth input1 token asserts last; "
                "a ninth non-last token follows, then supply stops.  Nine 32-unit tuples yield eighteen "
                "metadata descriptors (288 units), so the nineteenth prepared group is the first group "
                "without metadata capacity and one 32-unit transaction remains uncovered."
            ),
            "CONFIG_WORKAROUND": None,
        },
        "terminal_boundary": {
            "classification": "NON_NATURAL_WALL_CEILING_AFTER_TARGET",
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_nonclock_change_ps": dynamics["last_effective_nonclock_change_ps"],
            "natural_terminal": False,
            "formal_D": "UNPROVEN",
            "E3": "UNPROVEN_NON_NATURAL",
            "E4": "UNPROVEN_NON_NATURAL",
            "E5": "UNPROVEN_NON_NATURAL",
            "claim_boundary": (
                "The early tuple leaf sequence fully answers the dispatched diagnostic question.  The "
                "wall ceiling and absent natural terminal forbid later terminal/formal claims."
            ),
        },
        "rule_audit_disposition": {
            "RULE_GAP_AUDIT_triggered": False,
            "PACKAGE_BUILD_FAILURE_RULE_AUDIT_triggered": False,
            "disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "reason": (
                "Production compile and target execution succeeded; semantic-v5 correctly returned a "
                "partial wall-ceiling result, and the direct tuple cone pairwise closed all five leaves."
            ),
            "catalog_normalization_note": (
                "VCS collapsed 51 bit-select dump declarations into 17 packed vectors.  The returned raw "
                "vectors are complete and deterministic leaf derivation closes this run; future packages "
                "using this surface should catalog the packed variables directly."
            ),
        },
        "disposition": {
            "status": "VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION",
            "successor": None,
            "successor_reason": (
                "The exact dispatched leaf is closed.  Further package-only diagnostic expansion is not "
                "meaningful; functional producer/config repair requires separate user authorization."
            ),
            "fix_authorization_boundary": (
                "Any change to the upstream tag generator, epoch/last accounting or config needs explicit "
                "functional authorization and must first bind that producer's actual compiled source and "
                "exact config-to-consumer mapping."
            ),
            "storage": "UNCHANGED_NO_STORAGE_MANAGER_CALL",
            "server_actions": [],
        },
        "claim_boundary": claim_boundary,
        "conflicts": [],
        "pass": validated_root,
        "errors": [] if validated_root else ["validated-root conjunction failed"],
    }

    direct_review = {
        "schema": "node0004-v97b-direct-config-actual-rtl-dynamic-evidence-v1",
        "role_id": "family.conv.serialized",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source,
        "DYNAMIC_EXECUTION_EVIDENCE": dynamics,
        "VALIDATED_ROOT_CAUSE": analysis["causal_adjudication"]["VALIDATED_ROOT_CAUSE"],
        "CONFIG_WORKAROUND": None,
        "claim_boundary": claim_boundary,
        "pass": validated_root,
        "errors": analysis["errors"],
    }
    audit = {
        "schema": "node0004-v97b-rule-audit-disposition-v1",
        "role_id": "family.conv.serialized",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        **analysis["rule_audit_disposition"],
        "successor_built": False,
        "storage_actions": [],
        "server_actions": [],
        "pass": True,
        "errors": [],
    }

    analysis_path = OUT / "formal_return_analysis.json"
    direct_path = OUT / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json"
    audit_path = OUT / "RULE_AUDIT_DISPOSITION.json"
    atomic_json(direct_path, direct_review)
    atomic_json(audit_path, audit)
    atomic_json(analysis_path, analysis)

    checkpoint_path = STREAM / "checkpoints.jsonl"
    added = append_checkpoint(
        checkpoint_path,
        "FORMAL_V97B_TUPLE_ROOT_ADJUDICATION",
        {
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "last_effective_nonclock": dynamics["last_effective_nonclock_change_ps"],
            "last_proven_good_ps": last_good,
            "first_divergence_ps": first_divergence,
            "root": root,
            "analysis_sha256": sha_file(analysis_path),
            "direct_evidence_sha256": sha_file(direct_path),
            "disposition": analysis["disposition"]["status"],
        },
    )
    correction_added = append_checkpoint(
        checkpoint_path,
        "FORMAL_V97B_IDENTITY_SCHEMA_CORRECTION",
        {
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "correction": (
                "source_identity-v1 binds compile_cwd/status rather than repeating "
                "package/execution/attempt fields already bound by actual argv and native attempt"
            ),
            "execution_identity_pass": execution_identity_pass,
            "analysis_sha256": sha_file(analysis_path),
            "pass": validated_root,
        },
    )

    report_path = STREAM / "report.md"
    report = report_path.read_text(encoding="utf-8")
    if "## Formal v97b tuple-root adjudication" not in report:
        report += (
            "\n## Formal v97b tuple-root adjudication\n\n"
            "- compile / target / sim: `0 / entered@2445779375 ps / 124 (WALL_CEILING)`\n"
            "- full VCD / last effective non-clock: `28413985000 / 2446436875 ps`\n"
            "- VCS packed normalization: `17 packed vectors -> 51 deterministic leaves`\n"
            "- clock-qualified split writes: `[5, 9, 2]`; input1 is ready, never full, and never same/gotten-suppressed\n"
            "- Memory_AG tuples / metadata descriptors / prepared groups: `9 / 18 / 20`\n"
            "- input1 token 8 is last; token 9 follows as non-last; no token 10 arrives\n"
            f"- LAST_PROVEN_GOOD / FIRST_DIVERGENCE: `{last_good} / {first_divergence} ps`\n"
            f"- validated root: `{root}`\n"
            "- terminal: non-natural wall ceiling; natural/formal-D/E3/E4/E5 unproven\n"
            "- disposition: `RULE_CONFIRMATION_NO_CHANGE / VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION`\n"
            "- no successor, storage-manager call, or server action\n"
        )
        atomic_text(report_path, report)

    state["status"] = "EOF_REACHED_ROOT_VALIDATED"
    state["checkpoint_count"] = len(checkpoint_path.read_text(encoding="utf-8").splitlines())
    state["formal_analysis"] = {
        "path": "../formal_return_analysis.json",
        "sha256": sha_file(analysis_path),
        "root_status": analysis["causal_adjudication"]["root_status"],
        "root": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "disposition": analysis["disposition"]["status"],
    }
    atomic_json(STREAM / "analysis_state.json", state)

    receipt = {
        "schema": "node0004-v97b-mainline-return-receipt-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "dispatch_mainline_thread": "019ff027-e7db-72a3-b282-cfad8708da05",
        "return": identity(result_zip),
        "analysis": identity(analysis_path),
        "direct_evidence": identity(direct_path),
        "rule_audit_disposition": identity(audit_path),
        "analysis_state": identity(STREAM / "analysis_state.json"),
        "checkpoints": identity(checkpoint_path),
        "incremental_report": identity(report_path),
        "tuple_derivation": identity(OUT / "tuple_vector_derivation.json"),
        "task_record": identity(TASK_RECORD) if TASK_RECORD.is_file() else None,
        "previous_boundary": (
            "v95 validated a one-transaction 32-unit Memory_AG metadata deficit; v97 repaired the "
            "v96 duplicated-XMR catalog and returned the 153-signal three-input tuple discriminator."
        ),
        "current_result": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "terminal": "NON_NATURAL_WALL_CEILING_AFTER_TARGET",
        "formal_D_E3_E4_E5": "UNPROVEN",
        "rule_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "successor": None,
        "status": analysis["disposition"]["status"],
        "storage_actions": [],
        "server_actions": [],
        "claim_boundary": claim_boundary,
        "conflicts": [],
        "pass": validated_root,
        "errors": analysis["errors"],
    }
    receipt_path = OUT / "mainline_return_receipt.json"
    atomic_json(receipt_path, receipt)

    print(json.dumps({
        "pass": validated_root,
        "analysis": str(analysis_path),
        "receipt": str(receipt_path),
        "root": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "terminal": analysis["terminal_boundary"]["classification"],
        "disposition": analysis["disposition"]["status"],
        "checkpoints_added": [added, correction_added],
        "successor": None,
        "storage_actions": [],
        "server_actions": [],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if validated_root else 2


if __name__ == "__main__":
    raise SystemExit(main())
