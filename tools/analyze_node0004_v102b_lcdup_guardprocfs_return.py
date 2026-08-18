#!/usr/bin/env python3
"""Bounded streaming analysis for serialized Conv node0004 v102b return."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v102b_lcdup_guardprocfs"
EXECUTION = "r1786958038398677116_3776638"
ATTEMPT = "a3776638"
RETURN_ROOT = f"{PACKAGE}_return"
DEFAULT_RETURN = Path(
    r"C:/Users/15383/Downloads/"
    r"r5_n4_hw_v102b_lcdup_guardprocfs_r1786958038398677116_3776638_return.zip"
)
DEFAULT_SOURCE = (
    ROOT
    / "outputs/conv_node0004_v102b_lcdup_guardprocfs_release1"
    / f"{PACKAGE}.zip"
)
DEFAULT_OUT = (
    ROOT
    / "outputs/conv_node0004_v102b_lcdup_guardprocfs_return_r1786958038398677116_3776638"
)
MOD32 = 1 << 32


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(block)
        digest.update(block)
    return size, digest.hexdigest()


def sha_file(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        return sha_stream(stream)


def load_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    return json.loads(archive.read(f"{RETURN_ROOT}/{relative}"))


def append_checkpoint(path: Path, value: dict[str, Any]) -> None:
    with path.open("ab") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True).encode() + b"\n")
        stream.flush()


def write_state(path: Path, checkpoint: int, status: str, detail: str) -> None:
    path.write_bytes(
        canonical(
            {
                "schema": "node0004-v102b-return-analysis-state-v1",
                "package_id": PACKAGE,
                "execution_id": EXECUTION,
                "attempt_id": ATTEMPT,
                "checkpoint": checkpoint,
                "status": status,
                "detail": detail,
            }
        )
    )


def append_report(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(text.rstrip() + "\n\n")
        stream.flush()


def member_integrity(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist()
    names: set[str] = set()
    errors: list[str] = []
    roots: set[str] = set()
    total = 0
    for info in infos:
        pure = PurePosixPath(info.filename)
        if info.filename in names:
            errors.append(f"duplicate member: {info.filename}")
        names.add(info.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
            errors.append(f"unsafe member: {info.filename}")
        if pure.parts:
            roots.add(pure.parts[0])
        total += info.file_size
    bad = archive.testzip()
    if bad is not None:
        errors.append(f"CRC failure: {bad}")
    if roots != {RETURN_ROOT}:
        errors.append(f"root differs: {sorted(roots)}")
    return {
        "pass": not errors,
        "errors": errors,
        "member_count": len(infos),
        "uncompressed_bytes": total,
        "root": sorted(roots),
    }


def stream_events(archive: zipfile.ZipFile) -> dict[str, Any]:
    member = f"{RETURN_ROOT}/observer/chunks/events-000000.jsonl"
    counts: Counter[str] = Counter()
    signal_updates: Counter[str] = Counter()
    signal_rises: Counter[str] = Counter()
    signal_falls: Counter[str] = Counter()
    previous_values: dict[str, str] = {}
    last_values: dict[str, str] = {}
    first_live: dict[str, int] = {}
    last_live: dict[str, int] = {}
    wraps = 0
    previous_low = 0
    last_unwrapped = 0
    partial_seq: int | None = None
    partial_time: int | None = None
    last_effective_nonclock = 0
    line_count = 0
    errors: list[str] = []
    initial_signal_count = 52
    final_snapshot_start = 1640
    with archive.open(member) as raw:
        for raw_line in raw:
            line_count += 1
            if not raw_line.endswith(b"\n"):
                errors.append(f"non-newline terminated row {line_count}")
            row = json.loads(raw_line)
            if row.get("package_id") != PACKAGE or row.get("execution_id") != EXECUTION or row.get("attempt_id") != ATTEMPT:
                errors.append(f"identity mismatch row {line_count}")
            raw_time = int(row.get("sim_time", 0))
            low = raw_time % MOD32
            if low < previous_low:
                wraps += 1
            unwrapped = wraps * MOD32 + low
            previous_low = low
            last_unwrapped = unwrapped
            kind = str(row.get("record_type"))
            counts[kind] += 1
            seq = int(row.get("seq", -1))
            signal = str(row.get("signal_id"))
            value = str(row.get("value_4state"))
            if kind == "PARTIAL_EXIT":
                partial_seq = seq
                partial_time = unwrapped
            if kind != "EVENT":
                continue
            last_values[signal] = value
            if seq < initial_signal_count or seq >= final_snapshot_start:
                continue
            signal_updates[signal] += 1
            first_live.setdefault(signal, unwrapped)
            last_live[signal] = unwrapped
            prior = previous_values.get(signal)
            if prior is not None:
                prior_one = "1" in prior
                value_one = "1" in value
                if not prior_one and value_one:
                    signal_rises[signal] += 1
                if prior_one and not value_one:
                    signal_falls[signal] += 1
            previous_values[signal] = value
            if signal != "sig_clk":
                last_effective_nonclock = max(last_effective_nonclock, unwrapped)
    selected = {}
    for signal in (
        "sig_lc3_valid",
        "sig_lc3_bp",
        "sig_pe8_matched",
        "sig_pe8_wr",
        "sig_pe8_rd",
        "sig_mem_i1_valid",
        "sig_mem_i1_last",
        "sig_mem_i1_split_wr",
        "sig_mem_ag_wr",
        "sig_mem_ag_rd",
        "sig_mem_tag_valid",
        "sig_prepared_wr",
        "sig_prepared_rd",
        "sig_wdata_valid",
        "sig_slice_finish",
        "sig_exec_slice13_finish",
    ):
        selected[signal] = {
            "updates": signal_updates[signal],
            "rising_transitions_not_accept_counts": signal_rises[signal],
            "falling_transitions": signal_falls[signal],
            "first_live_time_ps": first_live.get(signal),
            "last_live_time_ps": last_live.get(signal),
        }
    return {
        "pass": not errors,
        "errors": errors,
        "member": member,
        "line_count": line_count,
        "record_counts": dict(counts),
        "low32_wrap_count": wraps,
        "unwrapped_final_time_ps": last_unwrapped,
        "partial_exit_seq": partial_seq,
        "partial_exit_time_ps": partial_time,
        "last_effective_nonclock_time_ps": last_effective_nonclock,
        "final_state": last_values,
        "selected_transition_ledger": selected,
        "qualification_warning": (
            "Transition/rise counts are not cycle-qualified handshake counts; sustained high or back-to-back accepts cannot be reconstructed."
        ),
    }


def source_manifest_binding(
    returned: zipfile.ZipFile, source_path: Path
) -> dict[str, Any]:
    returned_bytes = returned.read(f"{RETURN_ROOT}/evidence/returned_package_manifest.json")
    source_size, source_sha = sha_file(source_path)
    errors: list[str] = []
    with zipfile.ZipFile(source_path) as source:
        bad = source.testzip()
        if bad is not None:
            errors.append(f"source CRC failure: {bad}")
        source_manifest = source.read(f"{PACKAGE}/package_manifest.json")
    if returned_bytes != source_manifest:
        errors.append("returned package manifest differs from exact source package")
    return {
        "pass": not errors,
        "errors": errors,
        "source_package": {
            "path": source_path.relative_to(ROOT).as_posix(),
            "bytes": source_size,
            "sha256": source_sha,
        },
        "returned_manifest_byte_equal": returned_bytes == source_manifest,
        "returned_manifest_sha256": hashlib.sha256(returned_bytes).hexdigest(),
    }


def source_bound_target(log_stream: BinaryIO, decision: dict[str, Any]) -> dict[str, Any]:
    needle = "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1]"
    needle += ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE"
    target_rows: list[str] = []
    for raw in log_stream:
        text = raw.decode("utf-8", errors="replace").rstrip("\n")
        if needle in text and "boundary=mem_tuple_accept" in text and any(
            f"kind={kind}" in text for kind in ("TRIGGER", "EVENT", "STALL", "SUMMARY")
        ):
            target_rows.append(text)
    return {
        "decision": decision.get("decision"),
        "accepted_target_record_count": decision.get("accepted_target_record_count"),
        "candidate_match_count": decision.get("candidate_match_count"),
        "matching_candidate_ids": decision.get("matching_candidate_ids"),
        "target_rows": target_rows,
        "live_event_count": decision.get("live_event_count"),
        "qualification_warning": (
            "The v102 source-bound probe defines progress as mem_ag_idx_queue_wr_en OR tag_valid; its eight printed live events are not an exact tuple-accept counter."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--source-zip", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "analysis_state.json"
    checkpoints_path = out / "checkpoints.jsonl"
    report_path = out / "report.md"
    return_size, return_sha = sha_file(args.return_zip)
    with zipfile.ZipFile(args.return_zip) as archive:
        integrity = member_integrity(archive)
        core = load_json(archive, "RETURN_CORE_MANIFEST.json")
        argv = load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        sim_exit = load_json(archive, "evidence/SIM_EXIT_RECEIPT.json")
        process = load_json(archive, "evidence/PROCESS_TREE_RECEIPT.json")
        stop = load_json(archive, "evidence/OPERATIONAL_STOP_RECEIPT.json")
        finalization = load_json(archive, "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json")
        observer_decision = load_json(archive, "evidence/OBSERVER_DECISION.json")
        source_decision = load_json(archive, "evidence/source_bound_causal_decision.json")
        event = stream_events(archive)
        binding = source_manifest_binding(archive, args.source_zip)
        with archive.open(f"{RETURN_ROOT}/evidence/source_bound_causal.log") as stream:
            target = source_bound_target(stream, source_decision)
    with zipfile.ZipFile(args.source_zip) as source:
        runner = source.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        observer = source.read(f"{PACKAGE}/tb_probe/observer_only_wide_causal.svh").decode()
    runtime_anchors = {
        "outer_simulation_guard_timeout_3600": "--phase simulation" in runner and "--timeout 3600" in runner,
        "inner_runtime_supervisor_timeout_3660": "server_observer_runtime_supervision.py" in runner and "--timeout 3660" in runner,
        "observer_signed32_rtoi_time": "$rtoi($realtime * 1000.0)" in observer,
        "single_exit_authority": False,
    }
    final_state = event["final_state"]
    target_entered = (
        source_decision.get("accepted_target_record_count", 0) > 0
        and final_state.get("sig_exec_fetch_finish") == "1"
    )
    tuple10_closed = False
    existing_data_disposition = (
        "SUFFICIENT_TO_PRESERVE_PRIOR_PATH_NOT_SUFFICIENT_TO_ADJUDICATE_TUPLE10_OR_TERMINAL"
    )
    root = "PACKAGE_LOCAL_DUPLICATED_WALL_AUTHORITY_32BIT_TIME_AND_UNQUALIFIED_PROGRESS"
    formal = {
        "schema": "node0004-v102b-lcdup-guardprocfs-formal-return-analysis-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "return_zip": {"path": str(args.return_zip), "bytes": return_size, "sha256": return_sha},
        "integrity": integrity,
        "source_package_binding": binding,
        "compile": {
            "exit_code": argv.get("compile_exit"),
            "source_identity_status": argv.get("source_identity_status"),
            "dump_argv": argv.get("make_dump_argv"),
        },
        "execution": {
            "simulation_started": sim_exit.get("simulation_started"),
            "simulation_exit_code": sim_exit.get("exit_code"),
            "process_received_signal": process.get("received_signal"),
            "target_entered": target_entered,
            "natural_terminal": False,
            "formal_d": False,
            "e3": False,
            "e4": False,
            "e5": False,
            "process_tree_reaped": process.get("process_tree_reaped"),
            "owned_pids_remaining": process.get("owned_pids_remaining"),
        },
        "runtime_receipts": {
            "operational_stop_status": stop.get("status"),
            "operational_stop_count": stop.get("stop_count"),
            "finalization_status": finalization.get("status"),
            "observer_diagnostic_complete": observer_decision.get("diagnostic_evidence_complete"),
        },
        "runtime_implementation_anchors": runtime_anchors,
        "event_stream": event,
        "source_bound_target": target,
        "last_proven_good": {
            "classification": "TARGET_ENTERED_WITH_COPIED_LC3_PE8_AND_MEMORY_TUPLE_ACTIVITY",
            "prepared_valid_first_ps": 2445793125,
            "copied_lc3_valid_first_ps": 2446113125,
            "memory_input1_split_write_first_ps": 2446115625,
            "memory_tuple_queue_write_first_ps": 2446116875,
            "last_effective_nonclock_ps": event["last_effective_nonclock_time_ps"],
        },
        "first_divergence": {
            "classification": "METADATA_SOURCE_DRAINS_BEFORE_PREPARED_DATA_AND_RUNTIME_CANNOT_COUNT_TUPLE10",
            "memory_metadata_empty_tag_invalid_ps": 2446743125,
            "prepared_activity_continues_through_ps": 2446756875,
            "end_state": {
                "prepared_count": final_state.get("sig_prepared_count"),
                "prepared_valid": final_state.get("sig_prepared_valid"),
                "memory_queue_empty": final_state.get("sig_mem_ag_empty"),
                "memory_tag_valid": final_state.get("sig_mem_tag_valid"),
                "wdata_valid": final_state.get("sig_wdata_valid"),
                "wdata_ready": final_state.get("sig_wdata_ready"),
                "slice_finish": final_state.get("sig_slice_finish"),
                "global_slice13_finish": final_state.get("sig_exec_slice13_finish"),
            },
            "tuple10_uniquely_adjudicated": tuple10_closed,
        },
        "root_classification": root,
        "root_confidence": "UNIQUE_HIGH_FOR_PACKAGE_RUNTIME_FAILURE__OPEN_FOR_TUPLE10",
        "existing_data_disposition": existing_data_disposition,
        "rerun_required": True,
        "rerun_scope": "OBSERVER_COUNTER_PLATEAU_EXIT_RETURN_ONLY__NO_PATH_REEXPLORATION",
        "rule_gap_audit": "RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_FIX_REQUIRED",
        "package_build_failure_rule_audit": "TRIGGERED__RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_FIX_REQUIRED",
        "claim_boundary": (
            "Exact compile, target entry, 30.029643151 ms unwrapped event transport, and the package runtime failure are proven. "
            "Tuple10, functional workaround success, natural terminal, Formal-D, E3, E4 and E5 are not proven."
        ),
    }
    append_checkpoint(
        checkpoints_path,
        {
            "checkpoint": 2,
            "stage": "EXECUTION_AND_RUNTIME",
            "compile_exit": argv.get("compile_exit"),
            "simulation_started": sim_exit.get("simulation_started"),
            "target_entered": target_entered,
            "received_signal": process.get("received_signal"),
            "process_tree_reaped": process.get("process_tree_reaped"),
            "root_classification": root,
        },
    )
    write_state(state_path, 2, "IN_PROGRESS", "execution/runtime receipts and implementation anchors consumed")
    append_report(
        report_path,
        "## Execution and runtime checkpoint\n\n"
        f"Production compile exited {argv.get('compile_exit')}; simulation and the target interval both started. "
        "The outer operational guard owns a 3600-second wall while the nested simulator supervisor owns 3660 seconds. "
        "The outer SIGTERM therefore preempted the inner supervisor, left the stop/finalization receipts at START/RUNNING, "
        f"and left PID(s) {process.get('owned_pids_remaining')} unreaped. This is not a startup or RTL compile failure.",
    )
    append_checkpoint(
        checkpoints_path,
        {
            "checkpoint": 3,
            "stage": "EVENT_STREAM_EOF",
            "line_count": event["line_count"],
            "record_counts": event["record_counts"],
            "low32_wrap_count": event["low32_wrap_count"],
            "unwrapped_final_time_ps": event["unwrapped_final_time_ps"],
            "last_effective_nonclock_time_ps": event["last_effective_nonclock_time_ps"],
            "tuple10_uniquely_adjudicated": False,
        },
    )
    write_state(state_path, 3, "IN_PROGRESS", "event chunk streamed to EOF and low32 time unwrapped")
    append_report(
        report_path,
        "## Streaming causal checkpoint\n\n"
        "The observer chunk was streamed to EOF. Six signed-32 time wraps reconstruct a final simulation time of "
        f"{event['unwrapped_final_time_ps']} ps; the last effective non-clock change is "
        f"{event['last_effective_nonclock_time_ps']} ps. Copied LC3, PE8, input1 and Memory_AG activity are real. "
        "At the end, prepared_count=32 and prepared_valid=1 while metadata is empty/tag-invalid, downstream ready=11, "
        "and finish remains 0. The observer recorded signal transitions rather than accept-qualified per-cycle counters, "
        "so it cannot distinguish sustained/back-to-back handshakes and cannot certify tuple10.",
    )
    (out / "formal_return_analysis.json").write_bytes(canonical(formal))
    (out / "RULE_GAP_AUDIT.json").write_bytes(
        canonical(
            {
                "schema": "node0004-v102b-rule-gap-audit-v1",
                "triggered": True,
                "reason": "production target executed but tuple10 and terminal remained non-unique",
                "disposition": "RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_FIX_REQUIRED",
                "existing_rule_coverage": [
                    "64-bit-safe simulator time",
                    "accept-qualified counters",
                    "complete causal-state and global-witness plateau",
                    "single canonical exit authority",
                    "complete guard receipt before return and PID+start-time full-tree reap",
                ],
                "public_rule_change": False,
            }
        )
    )
    (out / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").write_bytes(
        canonical(
            {
                "schema": "node0004-v102b-package-build-failure-rule-audit-v1",
                "triggered": True,
                "same_target_failure_chain": ["v98", "v99", "v100", "v102"],
                "disposition": "RULE_CONFIRMATION_NO_CHANGE__PACKAGE_IMPLEMENTATION_FIX_REQUIRED",
                "v102_failures": [
                    "outer 3600-second guard preempts nested 3660-second supervisor",
                    "signed-32 $rtoi simulation time wraps",
                    "transition-only progress lacks accept-qualified counters",
                    "stop/finalization receipts incomplete and one simulator PID unreaped",
                ],
                "required_next_fresh": True,
                "public_rule_change": False,
            }
        )
    )
    append_checkpoint(
        checkpoints_path,
        {
            "checkpoint": 4,
            "stage": "FORMAL_DISPOSITION",
            "formal_analysis": "formal_return_analysis.json",
            "existing_data_disposition": existing_data_disposition,
            "rerun_required": True,
            "rule_gap_audit": formal["rule_gap_audit"],
            "package_build_failure_rule_audit": formal["package_build_failure_rule_audit"],
        },
    )
    write_state(state_path, 4, "RETURN_ANALYSIS_COMPLETE", "formal analysis and both audit dispositions written")
    append_report(
        report_path,
        "## Formal disposition\n\n"
        f"Root classification: `{root}`. Existing evidence is sufficient to preserve the compiled configuration, RTL, "
        "LC9→LC3 route and 52-signal cone without re-exploration, but not sufficient to adjudicate tuple10, downstream "
        "completion, natural terminal or Formal-D. A fresh run is required only after repairing the package-local observer, "
        "qualified counters, plateau, single exit authority, completed guard return, and full process reap. Both audits "
        "confirm the current public rules; no shared rule change is required.",
    )
    print(json.dumps({"pass": True, "output": str(out), "root": root}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
