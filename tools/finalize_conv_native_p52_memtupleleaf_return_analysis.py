#!/usr/bin/env python3
"""Close the exact native-Conv p52 return from bounded streaming artifacts.

The large VCD has already been consumed by the shared resumable scanner and by
the p52 direct-leaf ledger.  This finalizer performs an independent streaming
identity pass over every ZIP member, verifies the return core and source/config
bindings, and adjudicates the five p52 leaf candidates without extracting the
VCD or loading it into memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from analyze_conv_native_p49_tbvcdrt2_return import (  # noqa: E402
    canonical,
    load_json,
    member_identities,
    member_name,
    sha_file,
)
from analyze_conv_native_p51_metaidxcone_return import (  # noqa: E402
    log_markers,
)


PACKAGE = "r5_n4_0cc_p52_memtupleleaf"
EXECUTION = "r1786793357121273848_2914398"
ATTEMPT = "a0"
EXPECTED_BYTES = 124_528_356
EXPECTED_SHA256 = "3dbec1a4a0bfcb04d0c95bece9b0e2c1b274dcbdc90f7a54f53b45fc48e04331"
EXPECTED_PACKAGE_BYTES = 6_013_257
EXPECTED_PACKAGE_SHA256 = "fcb8a7b61fcd02be90ddf53b637b00259f208239a8c392cc38a2685da765d22f"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p52_memtupleleaf_r1786793357121273848_2914398_return.zip"
)
DEFAULT_OUT = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_return_analysis_" + EXECUTION
)
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)
RELEASE = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release"
    / f"{PACKAGE}.zip"
)


def identity(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, canonical(value))


def known_integer(row: Any) -> int | None:
    if isinstance(row, dict):
        value = row.get("integer")
        return value if isinstance(value, int) else None
    if not isinstance(row, str) or any(char in row.lower() for char in "xz"):
        return None
    return int(row, 2)


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


def package_manifest_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(member_name(archive, "/package_manifest.json"))
    return raw, json.loads(raw)


def source_evidence(
    archive: zipfile.ZipFile,
    identities: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    manifest = load_json(archive, "/evidence/compile_bootstrap/actual_compiled_sources/manifest.json")
    required_equations = {
        "Memory_AG_Idx_Queue.sv": [
            "assign mse_mem_idx_buffer_mode[INPORT_IDX] = !mse_mem_idx_mode[INPORT_IDX][1] & mse_mem_idx_mode[INPORT_IDX][0];",
            "assign mse_mem_idx_keep_mode[INPORT_IDX]   = mse_mem_idx_mode[INPORT_IDX][1] & !mse_mem_idx_mode[INPORT_IDX][0];",
            "assign mem_idx_same_gotten_mask[INPORT_IDX]         = !(mem_idx_gotten_bit[INPORT_IDX] && mem_idx_same_bit_masked[INPORT_IDX]);",
            "assign mem_idx_valid_bit_masked[INPORT_IDX]         = mem_idx_valid_bit_unmasked[INPORT_IDX] && mem_idx_same_gotten_mask[INPORT_IDX];",
            "assign mem_idx_split_fifo_wr_en[INPORT_IDX] = mem_idx_valid_bit_masked[INPORT_IDX] && (^mse_mem_idx_mode[INPORT_IDX]);",
            "assign mem_idx_fifo_valid_bit[INPORT_IDX]         = !idx_split_fifo_empty[INPORT_IDX];",
            "assign mem_all_idx_matched = &mem_idx_fifo_valid_bit_masked;",
            "assign mem_idx_bp_pre_keep_mask[INPORT_IDX] = (!(mem_buffer_idx_last_index > mse_mem_idx_keep_last_index[INPORT_IDX]) && mem_buffer_idx_last_bit) || (mse_mem_idx_buffer_mode[INPORT_IDX]);",
            "assign mem_idx_queue_bp_pre[INPORT_IDX]     = (!mem_ag_idx_queue_full && mem_idx_bp_pre_mask[INPORT_IDX]);",
            "assign mem_ag_idx_queue_wr_en = mem_all_idx_matched & mse_enable;",
        ],
        "WR_Memory_AG.sv": [
            "assign wr_data_chl_req_valid           = transfer_size_valid && mem_ag_ob_bp_pre;",
        ],
        "WR_Data_Channel.sv": [
            "assign wr_data_chl_prepared_data_wr_hs = wr_data_chl_data_vld && wr_chl_prepared_data_bp_pre;",
        ],
    }
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    memory_source_lines: list[dict[str, Any]] = []
    for record in manifest.get("records", []):
        archive_path = str(record.get("archive_path", ""))
        name = Path(archive_path).name
        member = member_name(archive, "/" + archive_path)
        body = archive.read(member)
        actual = identities[member]
        decoded = body.decode("utf-8", "strict")
        equations = required_equations.get(name, [])
        present = [equation for equation in equations if equation in decoded]
        if name == "Memory_AG_Idx_Queue.sv":
            for line_number, line in enumerate(decoded.splitlines(), 1):
                if any(equation in line for equation in equations):
                    memory_source_lines.append({"line": line_number, "text": line.strip()})
        row = {
            "basename": name,
            "relative_path": record.get("relative_path"),
            "bytes": actual["bytes"],
            "sha256": actual["sha256"],
            "manifest_identity_match": (
                record.get("bytes") == actual["bytes"]
                and record.get("sha256") == actual["sha256"]
            ),
            "required_equations_present": present,
            "required_equation_count": len(equations),
        }
        if not row["manifest_identity_match"] or len(present) != len(equations):
            errors.append(name)
        rows.append(row)
    return {
        "capture_phase": manifest.get("phase"),
        "capture_complete": manifest.get("complete") is True and not manifest.get("missing"),
        "server_root": manifest.get("server_root"),
        "records": rows,
        "memory_ag_idx_queue_equation_lines": memory_source_lines,
        "direct_conclusion": (
            "The actual compiled Memory_AG source enqueues each XOR-mode raw token into its split FIFO, "
            "defines tuple availability as all three masked split FIFOs valid, allows the buffer-mode input "
            "to release regardless of keep-last comparison, and writes one Memory_AG tuple only when all "
            "three inputs are present."
        ),
        "errors": errors,
        "pass": manifest.get("complete") is True and not manifest.get("missing") and not errors,
    }


def append_checkpoint(path: Path, event: str, payload: dict[str, Any]) -> bool:
    rows = path.read_text(encoding="utf-8").splitlines()
    if any(f'"event": "{event}"' in row for row in rows):
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
    ledger_path = out / "direct_leaf_ledger.json"
    for path in (state_path, checkpoints_path, report_path, ledger_path):
        if not path.is_file():
            raise RuntimeError(f"required bounded-streaming artifact absent: {path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED" or ledger.get("scan_status") != "EOF_REACHED":
        raise RuntimeError("bounded streaming/VCD leaf scan has not reached EOF")

    result_sha = sha_file(result_zip)
    exact_return = result_zip.stat().st_size == EXPECTED_BYTES and result_sha == EXPECTED_SHA256
    with zipfile.ZipFile(result_zip) as archive:
        names = [row.filename for row in archive.infolist()]
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        unsafe = [
            name for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        # Streaming hashes over every member also force ZipExtFile CRC checking
        # at EOF.  In particular, the 796 MB VCD is never materialized.
        identities = member_identities(archive)
        core = load_json(archive, "/RETURN_CORE_MANIFEST.json")
        core_status = load_json(archive, "/return_core/RETURN_CORE_STATUS.json")
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
        sca_name = member_name(archive, "/evidence/consumed_config/sca_cfg.json")
        sca_d_name = member_name(archive, "/evidence/consumed_config/sca_cfg_D.json")
        returned_manifest_name = member_name(archive, "/evidence/returned_package_manifest.json")
        returned_manifest = archive.read(returned_manifest_name)
        returned_manifest_json = json.loads(returned_manifest)
        vcd_name = member_name(archive, "/runs/c0/native_mse4_causal.vcd")
        sim_name = member_name(archive, "/runs/c0/sim.log")
        markers = log_markers(archive, sim_name)
        direct_source = source_evidence(archive, identities)

    package_candidates = [path for path in (PENDING, RELEASE) if path.is_file()]
    package_checks: list[dict[str, Any]] = []
    for package_path in package_candidates:
        package_raw, package_manifest = package_manifest_bytes(package_path)
        row = identity(package_path)
        row.update({
            "expected_package_identity": (
                row["bytes"] == EXPECTED_PACKAGE_BYTES
                and row["sha256"] == EXPECTED_PACKAGE_SHA256
            ),
            "returned_manifest_equal": package_raw == returned_manifest,
            "sca_cfg_identity": package_manifest.get("files", {}).get(
                "workload/runtime/runs/c0/sca_cfg.json"
            ),
            "sca_cfg_D_identity": package_manifest.get("files", {}).get(
                "workload/runtime/runs/c0/sca_cfg_D.json"
            ),
            "bitstream_identity": package_manifest.get("files", {}).get(
                "workload/runtime/runs/c0/install/cfg_pkg/"
                "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
            ),
        })
        package_checks.append(row)

    package_identity_pass = bool(
        package_checks
        and all(row["expected_package_identity"] and row["returned_manifest_equal"] for row in package_checks)
    )
    manifest_files = returned_manifest_json.get("files", {})
    packaged_sca = manifest_files.get("workload/runtime/runs/c0/sca_cfg.json", {})
    packaged_sca_d = manifest_files.get("workload/runtime/runs/c0/sca_cfg_D.json", {})
    config_identity_pass = bool(
        packaged_sca.get("size_bytes") == identities[sca_name]["bytes"]
        and packaged_sca.get("sha256") == identities[sca_name]["sha256"]
        and packaged_sca_d.get("size_bytes") == identities[sca_d_name]["bytes"]
        and packaged_sca_d.get("sha256") == identities[sca_d_name]["sha256"]
    )

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
        exact_return
        and roots == {f"{PACKAGE}_return"}
        and not unsafe
        and not duplicates
        and core.get("package_id") == PACKAGE
        and core.get("execution_id") == EXECUTION
        and actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
        and compile_core.get("package_id") == PACKAGE
        and compile_core.get("execution_id") == EXECUTION
        and package_identity_pass
        and config_identity_pass
    )

    counts = ledger.get("event_counts", {})
    times = ledger.get("event_times_ps", {})
    final_leaf = ledger.get("final_leaf_state", {})
    transition_summary = ledger.get("leaf_transition_summary", {})
    split_rows = ledger.get("split_snapshots", [])
    tuple_rows = ledger.get("tuple_snapshots", [])
    input1_rows = [row["ports"]["1"] | {"time_ps": row["time_ps"]} for row in split_rows if row["ports"]["1"]["write"] or row["ports"]["1"]["read"]]
    input1_writes = [row for row in input1_rows if row["write"]]
    input1_reads = [row for row in input1_rows if row["read"]]
    input1_last_writes = [row for row in input1_writes if row["raw_last"] == 1]
    input1_post_last_writes = [
        row for row in input1_writes
        if input1_last_writes and row["time_ps"] > input1_last_writes[-1]["time_ps"]
    ]
    owner_hist = lambda signal: transition_summary.get(signal, {}).get("value_histogram_at_owner_edges_after_target", {})
    no_full = owner_hist("sig_idx_split_fifo_full") == {"000": 3376}
    input1_path_lossless = bool(
        counts.get("split1_write") == 9
        and counts.get("split1_read") == 9
        and len(input1_writes) == 9
        and len(input1_reads) == 9
        and all(row["same_gotten_mask"] == 1 for row in input1_rows)
        and all(row["keep_release"] == 1 for row in input1_rows)
        and all(row["queue_ready"] == 1 for row in input1_rows)
        and no_full
    )
    exact_leaf_chain = bool(
        counts.get("split0_write") == 5
        and counts.get("split2_write") == 2
        and counts.get("memory_tuple_write") == 9
        and counts.get("memory_tuple_read") == 9
        and counts.get("metadata_request_accept") == 18
        and counts.get("prepared_write_accept") == 20
        and counts.get("prepared_read_accept") == 18
        and input1_path_lossless
        and len(input1_last_writes) == 1
        and len(input1_post_last_writes) == 1
        and known_integer(final_leaf.get("sig_mem_idx_split_fifo0_count")) == 5
        and known_integer(final_leaf.get("sig_mem_idx_split_fifo1_count")) == 0
        and known_integer(final_leaf.get("sig_mem_idx_split_fifo2_count")) == 2
        and known_integer(final_leaf.get("sig_idx_split_fifo_empty")) == 2
        and known_integer(final_leaf.get("sig_mem_idx_fifo_valid_bit_masked")) == 5
        and known_integer(final_leaf.get("sig_mem_idx_bp_pre_keep_mask")) == 2
        and known_integer(final_leaf.get("sig_mem_idx_same_gotten_mask")) == 6
        and known_integer(final_leaf.get("sig_mse_mem_idx_buffer_mode")) == 2
        and known_integer(final_leaf.get("sig_mse_mem_idx_keep_mode")) == 5
        and known_integer(final_leaf.get("sig_mse_mem_idx_enable")) == 7
    )

    last_good = max(times.get("metadata_request_accept", []))
    first_divergence = times.get("prepared_write_accept", [])[18]
    target_time = markers["target"]["first"]["sim_time_ps"]
    actual_compile_argv = actual.get("compile_argv") or actual.get("actual_compile_argv")
    actual_sim_argv = actual.get("sim_argv") or actual.get("actual_sim_argv")
    dump_profile_text = json.dumps({"compile": actual_compile_argv, "sim": actual_sim_argv}, sort_keys=True)
    dump_zero = all(token in dump_profile_text for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"))

    direct_config = {
        "consumed_sca_cfg": identities[sca_name],
        "consumed_sca_cfg_D": identities[sca_d_name],
        "packaged_config_identity_match": config_identity_pass,
        "packaged_bitstream": manifest_files.get(
            "workload/runtime/runs/c0/install/cfg_pkg/"
            "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ),
        "same_attempt_runtime_consumers": {
            "mse_mem_idx_mode": final_leaf.get("sig_mse_mem_idx_mode"),
            "mse_mem_idx_enable": final_leaf.get("sig_mse_mem_idx_enable"),
            "mse_mem_idx_buffer_mode": final_leaf.get("sig_mse_mem_idx_buffer_mode"),
            "mse_mem_idx_keep_mode": final_leaf.get("sig_mse_mem_idx_keep_mode"),
            "mse_mem_idx_cons_mode": final_leaf.get("sig_mse_mem_idx_cons_mode"),
            "mse_mem_idx_keep_last_index": final_leaf.get("sig_mse_mem_idx_keep_last_index"),
        },
        "direct_conclusion": (
            "The exact consumed config identities reach runtime consumer encoding mode=100110, "
            "enable=111, buffer_mode=010 and keep_mode=101.  Thus port 1 is the unique buffer-mode "
            "leaf and ports 0/2 are keep-mode leaves for this execution."
        ),
        "validated_config_to_upstream_tag_generator": False,
        "CONFIG_WORKAROUND": None,
        "claim_boundary": (
            "The returned SCA/bitstream and same-attempt consumer nets validate selection of input 1, "
            "but the actual upstream producer/config-field encoding that generated mse_mem_queue_tag[1] "
            "was not returned.  No config workaround is validated or recommended."
        ),
    }

    candidates = {
        "input0_keep_epoch_ends_early": {
            "disposition": "EXCLUDED_AS_TUPLE_BLOCKER",
            "evidence": "five accepted tokens remain resident; port0 final occupancy=5 and valid=1",
        },
        "input1_buffer_tag_supply_ends_after_nine": {
            "disposition": "VALIDATED_ROOT_LEAF",
            "evidence": (
                "exactly nine input1 tokens are accepted and all nine are losslessly dequeued; "
                "the eighth accepted token asserts last, one additional non-last token follows, "
                "then input1 remains empty/ready with no tenth token"
            ),
        },
        "input2_keep_epoch_ends_early": {
            "disposition": "EXCLUDED_AS_TUPLE_BLOCKER",
            "evidence": "two accepted tokens remain resident; port2 final occupancy=2 and valid=1",
        },
        "same_gotten_masks_tenth_tuple": {
            "disposition": "EXCLUDED",
            "evidence": "input1 same_gotten_mask is 1 on every input1 write/read activity and final mask is 110",
        },
        "split_fifo_or_keep_release_drops_tenth_tuple": {
            "disposition": "EXCLUDED",
            "evidence": "input1 has 9 writes/9 reads, never-full split FIFOs, queue_ready=1 and keep_release=1",
        },
    }

    root = "MSE4_MEMORY_AG_INPUT1_BUFFER_TAG_STREAM_UNDERSUPPLIES_ONE_TUPLE"
    validated_root = bool(
        identities_ok
        and not core_errors
        and archive_binding
        and direct_source["pass"]
        and exact_leaf_chain
    )
    execution = {
        "compile_exit": compile_core.get("compile_exit"),
        "simulation_started": sim_exit.get("simulation_started"),
        "target_entry": target.get("observed"),
        "target_entry_ps": target_time,
        "sim_exit": sim_exit.get("exit_code"),
        "signal": sim_exit.get("signal"),
        "timed_out": sim_exit.get("timed_out"),
        "runtime_decision": decision.get("decision"),
        "runtime_stop_reason": runtime.get("stop_reason"),
        "natural_terminal": False,
        "formal_D": "UNPROVEN",
        "E3": "UNPROVEN_NON_NATURAL",
        "E4": "UNPROVEN_NON_NATURAL",
        "E5": "UNPROVEN_NON_NATURAL",
        "core_status": core_status.get("disposition"),
        "process_fully_reaped": process.get("process_tree_reaped") is True,
        "process_finalizer_all_reaped": runtime.get("process_tree", {}).get("all_reaped") is True,
        "vcd_dumpoff": runtime.get("flush", {}).get("dumpoff"),
        "vcd_dumpflush": runtime.get("flush", {}).get("dumpflush"),
        "vcd_closed": runtime.get("flush", {}).get("closed"),
        "published_root": root_identity.get("published_root"),
        "actual_root": root_identity.get("actual_root"),
        "execution_root_match": root_identity.get("match") is True,
        "execution_root_mismatch_classification": root_identity.get("mismatch_classification"),
        "actual_dump_argv_zero_profile": dump_zero,
        "phase_semantic_version": 5,
        "phase_semantic_evidence": {
            "planned_dumpoff": runtime.get("dump_control", {}).get("planned_dumpoff_observed"),
            "state_monotonic": runtime.get("dump_control", {}).get("state_monotonic"),
            "stop_marker_one_shot": runtime.get("dump_control", {}).get("stop_marker_one_shot"),
            "shared_evaluator_only": runtime.get("decision_authority", {}).get("outer_runner_consumes_only_receipt"),
        },
    }
    analysis = {
        "schema": "conv-native-p52-memtupleleaf-formal-return-analysis-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "return_identity": {
            "path": str(result_zip),
            "bytes": result_zip.stat().st_size,
            "sha256": result_sha,
            "exact_identity_pass": exact_return,
            "member_count": len(identities),
            "streaming_crc_pass": True,
            "safe_paths": not unsafe,
            "duplicates": duplicates,
            "core_manifest_errors": core_errors,
            "package_execution_attempt_config_identity_pass": identities_ok,
            "package_checks": package_checks,
        },
        "execution": execution,
        "streaming": {
            "status": state.get("status"),
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "checkpoint_count_before_close": state.get("checkpoint_count"),
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_nonclock_change_ps": ledger.get("last_effective_nonclock_change_ps"),
            "last_effective_nonclock_signal_ids": ledger.get("last_effective_nonclock_signal_ids"),
            "vcd_identity": vcd_identity,
            "full_file_archive_binding_pass": archive_binding,
            "transport": "UNTRUNCATED_UNSAMPLED_FULL_MEMBER_STREAM",
        },
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source,
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "event_counts": counts,
            "event_times_ps": times,
            "input1_activity": input1_rows,
            "input1_path_lossless": input1_path_lossless,
            "input1_last_marked_write_ps": input1_last_writes[0]["time_ps"],
            "input1_post_last_nonlast_write_ps": input1_post_last_writes[0]["time_ps"],
            "final_leaf_state": final_leaf,
            "exact_leaf_chain_pass": exact_leaf_chain,
        },
        "causal_adjudication": {
            "LAST_PROVEN_GOOD": {
                "time_ps": last_good,
                "statement": (
                    "The eighteenth/final metadata descriptor is accepted; all nine Memory_AG tuples and "
                    "their two-descriptor expansion remain losslessly accounted."
                ),
            },
            "FIRST_DIVERGENCE": {
                "time_ps": first_divergence,
                "statement": (
                    "The nineteenth prepared 16-unit group is accepted after input1 has supplied and "
                    "Memory_AG has consumed only nine buffer tags; input1 is empty, preventing tuple ten."
                ),
            },
            "candidate_matrix": candidates,
            "VALIDATED_ROOT_CAUSE": root if validated_root else None,
            "root_classification": "UPSTREAM_INPUT1_TAG_GENERATION_OR_EPOCH_LAST_ACCOUNTING",
            "root_status": "VALIDATED_ROOT_CAUSE" if validated_root else "OPEN_UNVALIDATED_MECHANISM",
            "mechanism": (
                "Memory_AG input1 supplies nine accepted buffer tags although the prepared-data side needs "
                "ten tuples for twenty 16-unit groups.  The eighth input1 tag is last-marked and a ninth "
                "non-last tag follows.  Actual Memory_AG logic accepts/dequeues every input1 token and has no "
                "full, same/gotten or keep-release loss; when input1 becomes empty, all-match drops and tuple "
                "ten cannot be formed.  Nine tuples produce eighteen metadata descriptors, leaving one "
                "32-unit transaction absent."
            ),
            "narrowing_vs_p51": (
                "p51 left five direct leaves open.  p52 uniquely selects the input1 buffer-tag source and "
                "excludes input0, input2, same/gotten, split-FIFO and keep-release mechanisms."
            ),
            "CONFIG_WORKAROUND": None,
        },
        "runtime_terminal_boundary": {
            "classification": "NON_NATURAL_WALL_CEILING_AFTER_TARGET",
            "stop_reason": runtime.get("stop_reason"),
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "last_effective_nonclock_change_ps": ledger.get("last_effective_nonclock_change_ps"),
            "target_completed_for_diagnostic_leaf": True,
            "natural_completion": False,
            "formal_D_E3_E4_E5": "UNPROVEN",
            "partial_evidence_status": runtime.get("diagnostic_status"),
            "archive_binding_pass": archive_binding,
            "process_reaped": process.get("process_tree_reaped") is True,
            "claim_boundary": (
                "The early same-attempt leaf transaction sequence is consumable and closes the p52 causal "
                "question.  The wall-ceiling exit, absent dumpoff/flush/close and lack of a terminal witness "
                "forbid natural-terminal, formal-D, E3, E4 or E5 claims."
            ),
        },
        "rule_audit_disposition": {
            "RULE_GAP_AUDIT_triggered": False,
            "PACKAGE_BUILD_FAILURE_RULE_AUDIT_triggered": False,
            "disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "reason": (
                "Production compile and target execution succeeded, the semantic-v5 runtime correctly "
                "classified the wall ceiling as partial, and the p52 direct-leaf cone pairwise distinguished "
                "all five remaining candidates in one return."
            ),
        },
        "disposition": {
            "status": "VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION",
            "successor": None,
            "successor_reason": (
                "The dispatched exact leaf is closed; further package-only expansion would not improve the "
                "validated boundary.  Repair belongs to the actual upstream owner of mse_mem_queue_tag[1]/idx[1] "
                "and its epoch/last accounting, whose functional RTL/config was not authorized for change."
            ),
            "fix_authorization_boundary": (
                "Read-only evidence permits review of the actual upstream tag producer and exact config-to-"
                "consumer mapping.  Any functional RTL/config repair or workaround requires separate user "
                "authorization and an actual-source/config identity proof; no workaround is presently validated."
            ),
            "storage": "UNCHANGED_NO_STORAGE_MANAGER",
            "server_actions": [],
            "frozen": [
                "functional RTL", "config", "numeric", "workload", "golden",
                "p42 vector predicate", "MSE4 target",
            ],
        },
        "claim_boundary": (
            "The validated root binds the exact p52 package/return, consumed config identities, returned actual "
            "Memory_AG RTL bytes and same-attempt NDP_copy02 dynamics.  It proves the upstream input1 buffer-tag "
            "stream under-supplies one tuple and violates expected epoch/last ordering at the Memory_AG boundary; "
            "it does not yet identify the upstream producer source line or validate a config workaround.  "
            "Published NDP_copy01 versus actual NDP_copy02 root drift prevents any source-equivalence claim for "
            "copy01.  The non-natural wall exit leaves natural/formal-D/E3/E4/E5 unproven."
        ),
        "conflicts": [],
        "pass": validated_root,
        "errors": (
            ([] if identities_ok else ["identity conjunction failed"])
            + core_errors
            + ([] if archive_binding else ["archive binding failed"])
            + ([] if direct_source["pass"] else ["actual source identity/equation failure"])
            + ([] if exact_leaf_chain else ["direct leaf chain mismatch"])
        ),
    }

    direct_review = {
        "schema": "conv-native-p52-direct-config-actual-rtl-dynamic-evidence-v1",
        "role_id": "family.conv.native",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "DIRECT_CONFIG_EVIDENCE": direct_config,
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_source,
        "DYNAMIC_EXECUTION_EVIDENCE": analysis["DYNAMIC_EXECUTION_EVIDENCE"],
        "VALIDATED_ROOT_CAUSE": analysis["causal_adjudication"]["VALIDATED_ROOT_CAUSE"],
        "CONFIG_WORKAROUND": None,
        "claim_boundary": analysis["claim_boundary"],
        "pass": validated_root,
        "errors": analysis["errors"],
    }
    audit_disposition = {
        "schema": "conv-native-p52-rule-audit-disposition-v1",
        "role_id": "family.conv.native",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        **analysis["rule_audit_disposition"],
        "successor_built": False,
        "storage_actions": [],
        "server_actions": [],
        "pass": True,
        "errors": [],
    }

    analysis_path = out / "formal_return_analysis.json"
    direct_path = out / "DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json"
    audit_path = out / "RULE_AUDIT_DISPOSITION.json"
    atomic_json(direct_path, direct_review)
    atomic_json(audit_path, audit_disposition)
    atomic_json(analysis_path, analysis)

    checkpoint_payload = {
        "byte_offset": state.get("byte_offset"),
        "line_number": state.get("line_number"),
        "last_sim_time": state.get("last_sim_time"),
        "last_effective_nonclock": ledger.get("last_effective_nonclock_change_ps"),
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "root": root,
        "analysis_sha256": sha_file(analysis_path),
        "direct_evidence_sha256": sha_file(direct_path),
        "disposition": analysis["disposition"]["status"],
    }
    added = append_checkpoint(
        checkpoints_path,
        "FORMAL_P52_DIRECT_LEAF_ROOT_ADJUDICATION",
        checkpoint_payload,
    )
    correction_added = append_checkpoint(
        checkpoints_path,
        "P52_EXECUTION_ROOT_CLAIM_BOUNDARY",
        {
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "published_root": root_identity.get("published_root"),
            "actual_root": root_identity.get("actual_root"),
            "match": root_identity.get("match"),
            "mismatch_classification": root_identity.get("mismatch_classification"),
            "analysis_sha256": sha_file(analysis_path),
            "claim_boundary": "Claims bind only to returned actual NDP_copy02 execution bytes.",
        },
    )
    state["checkpoint_count"] = len(checkpoints_path.read_text(encoding="utf-8").splitlines())
    state["formal_analysis"] = {
        "path": analysis_path.name,
        "sha256": sha_file(analysis_path),
        "root_status": analysis["causal_adjudication"]["root_status"],
        "root": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "disposition": analysis["disposition"]["status"],
    }
    atomic_json(state_path, state)

    report = report_path.read_text(encoding="utf-8")
    if "## Formal p52 direct-leaf adjudication" not in report:
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## Formal p52 direct-leaf adjudication\n\n"
                f"- compile / target / sim: `0 / entered@{target_time} ps / 124 (WALL_CEILING)`\n"
                f"- final VCD / last effective non-clock: `{state.get('last_sim_time')} / {ledger.get('last_effective_nonclock_change_ps')} ps`\n"
                "- three split inputs: writes `[5, 9, 2]`, reads `[0, 9, 0]`; split FIFOs never full\n"
                "- input1: all nine accepted tokens are dequeued; token 8 asserts last, token 9 is post-last and non-last, then supply stops\n"
                "- tuple / metadata / prepared: `9 / 18 / 20`; the tenth tuple and one 32-unit metadata transaction are absent\n"
                f"- LAST_PROVEN_GOOD / FIRST_DIVERGENCE: `{last_good} / {first_divergence} ps`\n"
                f"- validated root: `{root}`\n"
                "- p51's five leaf candidates are pairwise closed: input1 supply validated; input0/input2, same-gotten and split/keep loss excluded\n"
                "- terminal boundary: non-natural wall ceiling; no dumpoff/flush/close or natural/formal-D/E3-E5 claim\n"
                "- disposition: `RULE_CONFIRMATION_NO_CHANGE / VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION`; no successor, storage, or server action\n"
            )
    if "## p52 execution-root claim boundary" not in report_path.read_text(encoding="utf-8"):
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
                "\n## p52 execution-root claim boundary\n\n"
                "The package published `/home/panqs/ndp/NDP_copy01`, while actual cwd, config consumption and returned source capture bind `/home/panqs/ndp/NDP_copy02`. "
                "The exact root is valid for this NDP_copy02 execution; no NDP_copy01 source-equivalence claim is made.\n"
            )

    receipt = {
        "schema": "conv-native-p52-mainline-return-receipt-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "dispatch_mainline_thread": "019ff027-e7db-72a3-b282-cfad8708da05",
        "return": identity(result_zip),
        "analysis": identity(analysis_path),
        "direct_evidence": identity(direct_path),
        "rule_audit_disposition": identity(audit_path),
        "analysis_state": identity(state_path),
        "checkpoints": identity(checkpoints_path),
        "incremental_report": identity(report_path),
        "previous_boundary": "p51 validated a one-transaction 32-unit Memory_AG metadata supply deficit; p52 added direct tuple/same-gotten/split-FIFO/keep-release leaves.",
        "current_result": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "terminal": "NON_NATURAL_WALL_CEILING_AFTER_TARGET",
        "formal_D_E3_E4_E5": "UNPROVEN",
        "rule_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "successor": None,
        "status": "VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION",
        "storage_actions": [],
        "server_actions": [],
        "claim_boundary": analysis["claim_boundary"],
        "pass": analysis["pass"],
        "errors": analysis["errors"],
    }
    receipt_path = out / "mainline_return_receipt.json"
    atomic_json(receipt_path, receipt)

    correction_added = append_checkpoint(
        checkpoints_path,
        "P52_FORMAL_ANALYSIS_CORRECTED_CORE_PREFIX",
        {
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "correction": "core manifest was recomputed with the p52 return-root prefix",
            "core_manifest_errors": core_errors,
            "analysis_sha256": sha_file(analysis_path),
            "mainline_receipt_sha256": sha_file(receipt_path),
            "pass": analysis["pass"],
        },
    )

    # Make the last append-only checkpoint bind the final receipt as well.
    receipt_added = append_checkpoint(
        checkpoints_path,
        "P52_MAINLINE_RECEIPT_READY",
        {
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "mainline_receipt_sha256": sha_file(receipt_path),
            "status": receipt["status"],
        },
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["checkpoint_count"] = len(checkpoints_path.read_text(encoding="utf-8").splitlines())
    # Keep the resumable state independent of the receipt so the receipt can
    # bind the final immutable state/checkpoint/report identities without a
    # circular state -> receipt -> state hash dependency.
    state.pop("mainline_receipt", None)
    atomic_json(state_path, state)
    receipt["analysis_state"] = identity(state_path)
    receipt["checkpoints"] = identity(checkpoints_path)
    receipt["incremental_report"] = identity(report_path)
    receipt["streaming_artifact_binding"] = "FINAL_AFTER_FORMAL_CHECKPOINTS_NO_CIRCULAR_SELF_REFERENCE"
    atomic_json(receipt_path, receipt)

    print(json.dumps({
        "pass": analysis["pass"],
        "analysis": str(analysis_path),
        "receipt": str(receipt_path),
        "root": root,
        "last_proven_good_ps": last_good,
        "first_divergence_ps": first_divergence,
        "input1_writes_reads": [len(input1_writes), len(input1_reads)],
        "input1_last_then_post_last": [
            input1_last_writes[0]["time_ps"], input1_post_last_writes[0]["time_ps"]
        ],
        "terminal": analysis["runtime_terminal_boundary"]["classification"],
        "disposition": analysis["disposition"]["status"],
        "checkpoints_added": [added, correction_added, receipt_added],
        "storage_actions": [],
        "server_actions": [],
    }, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
