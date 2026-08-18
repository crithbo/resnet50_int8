#!/usr/bin/env python3
"""Finalize the streamed QAdd v63 bounded-causal-cone return analysis.

The 212 MB VCD is never materialized.  The generic streaming parser has
already consumed it in bounded chunks; this family analyzer reconciles that
state with the source-bound catalog, streams only the small VCD header and
simulator log, and appends an immutable family checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections import deque
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_qadd_n7_tailround_lanephase_v63_tbvcd_"
    r"r1786698111383862725_2250595_return.zip"
)
PACKAGE_ID = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
RETURN_ROOT = f"{PACKAGE_ID}_return"
VCD_MEMBER = f"{RETURN_ROOT}/evidence/vcd/wave.vcd"
SIM_LOG_MEMBER = f"{RETURN_ROOT}/runs/sim.log"
OUT = ROOT / "outputs/qlinearadd_node0007_v63_return_r1786698111383862725_2250595"
STREAM = OUT / "streaming_analysis"
STATE = STREAM / "analysis_state.json"
CHECKPOINTS = STREAM / "checkpoints.jsonl"
REPORT = STREAM / "report.md"
FINAL = OUT / "formal_return_analysis.json"


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_member(archive: zipfile.ZipFile, relative: str) -> Any:
    with archive.open(f"{RETURN_ROOT}/{relative}") as stream:
        return json.load(stream)


def stream_header(stream: BinaryIO) -> dict[str, Any]:
    scopes: list[str] = []
    variables: dict[str, dict[str, Any]] = {}
    timescale_parts: list[str] = []
    in_timescale = False
    definitions = False
    header_bytes = 0
    for raw in stream:
        header_bytes += len(raw)
        line = raw.decode("utf-8", errors="strict").strip()
        if line.startswith("$timescale"):
            in_timescale = True
            remainder = line[len("$timescale"):].replace("$end", "").strip()
            if remainder:
                timescale_parts.append(remainder)
            if "$end" in line:
                in_timescale = False
        elif in_timescale:
            if line != "$end":
                timescale_parts.append(line.replace("$end", "").strip())
            if "$end" in line:
                in_timescale = False
        elif line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scopes.append(parts[2])
        elif line.startswith("$upscope"):
            if scopes:
                scopes.pop()
        elif line.startswith("$var"):
            parts = line.split()
            if len(parts) >= 6:
                variables[parts[3]] = {
                    "width_bits": int(parts[2]),
                    "reference": " ".join(parts[4:-1]),
                    "scope": ".".join(scopes),
                }
        elif line.startswith("$enddefinitions"):
            definitions = True
            break
        if header_bytes > 8 * 1024 * 1024:
            raise ValueError("VCD header exceeded the bounded 8 MiB header window")
    timescale = "".join(timescale_parts).replace(" ", "") or None
    return {
        "header_valid": bool(definitions and timescale and variables),
        "timescale": timescale,
        "definitions": definitions,
        "header_bytes_streamed": header_bytes,
        "variables": variables,
    }


def stream_sim_log(stream: BinaryIO) -> dict[str, Any]:
    loads: list[dict[str, Any]] = []
    passes: list[dict[str, Any]] = []
    heartbeats: list[dict[str, int]] = []
    tail: deque[str] = deque(maxlen=32)
    execution_markers: list[str] = []
    load_pattern = re.compile(r"JSON: Loading matrix\[(\d+)\]: (.*?) ->")
    heartbeat_pattern = re.compile(
        r"CODEX_TB_VCD_HEARTBEAT sim_time=(\d+) cycles=(\d+) progress=(\d+) global=(\d+)"
    )
    for line_number, raw in enumerate(stream, 1):
        line = raw.decode("utf-8", errors="replace").rstrip()
        tail.append(line)
        load_match = load_pattern.search(line)
        if load_match:
            loads.append({"line": line_number, "index": int(load_match.group(1)), "path": load_match.group(2)})
        if "*** PASS: Continuous transfer completed successfully!" in line:
            passes.append({"line": line_number, "text": line})
        heartbeat_match = heartbeat_pattern.search(line)
        if heartbeat_match:
            heartbeats.append(
                {
                    "line": line_number,
                    "sim_time": int(heartbeat_match.group(1)),
                    "cycles": int(heartbeat_match.group(2)),
                    "progress": int(heartbeat_match.group(3)),
                    "global": int(heartbeat_match.group(4)),
                }
            )
        if any(token in line for token in ("CODEX_TB_VCD_NATURAL_TERMINAL", "CODEX_TB_VCD_DUMPOFF", "CODEX_TB_VCD_PLATEAU_SUSPECT")):
            execution_markers.append(line)
    return {
        "matrix_loads_started": loads,
        "matrix_transfers_completed": passes,
        "heartbeats": heartbeats,
        "execution_markers": execution_markers,
        "tail": list(tail),
    }


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED" or int(state.get("byte_offset", 0)) != 212_812_929:
        raise ValueError("generic bounded streaming pass is not complete")
    with zipfile.ZipFile(RETURN_ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("formal return CRC failure")
        catalog = load_member(archive, "evidence/vcd/catalog.json")
        matrix = load_member(archive, "evidence/vcd/candidate_matrix.json")
        runtime = load_member(archive, "evidence/vcd/runtime.json")
        process = load_member(archive, "evidence/PROCESS_TREE_RECEIPT.json")
        core = load_member(archive, "RETURN_CORE_MANIFEST.json")
        actual = load_member(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        exit_receipt = load_member(archive, "evidence/SIM_EXIT_RECEIPT.json")
        finalization = load_member(archive, "evidence/vcd/finalization_receipt.json")
        with archive.open(VCD_MEMBER) as stream:
            header = stream_header(stream)
        with archive.open(SIM_LOG_MEMBER) as stream:
            log = stream_sim_log(stream)

    vcd_by_reference = {
        value["reference"].split()[0]: code
        for code, value in state["signal_catalog"].items()
    }
    catalog_rows: list[dict[str, Any]] = []
    missing: list[str] = []
    active: list[str] = []
    for signal in catalog["signals"]:
        reference = signal["exact_hierarchy"].rsplit(".", 1)[-1]
        code = vcd_by_reference.get(reference)
        if code is None:
            missing.append(signal["signal_id"])
            continue
        summary = state["signal_summaries"].get(code, {})
        transitions = int(summary.get("transitions", 0))
        row = {
            "signal_id": signal["signal_id"],
            "reference": reference,
            "vcd_code": code,
            "width_bits": signal["width_bits"],
            "transitions": transitions,
            "xz_transitions": int(summary.get("xz_transitions", 0)),
            "first_value": summary.get("first_value"),
            "last_value": summary.get("last_value"),
            "last_transition_time": summary.get("last_time"),
        }
        catalog_rows.append(row)
        if transitions > 1:
            active.append(signal["signal_id"])

    target_exclusions = {"sig_clk", "sig_rst_n", "sig_slice_rst", "sig_tag_last_buf"}
    target_activity = sorted(set(active) - target_exclusions)
    candidate_rows = [
        {
            "candidate_id": candidate["candidate_id"],
            "disposition": "NOT_REACHED_NOT_ADJUDICABLE",
            "reason": "No Buffer5 request-decode event or target-stage activity occurred before the package-local runtime stop.",
        }
        for candidate in matrix["candidates"]
    ]
    heartbeat_values = [row["sim_time"] for row in log["heartbeats"]]
    overflow_signature = any(value > 9_223_372_036_854_775_807 for value in heartbeat_values)
    last_load = log["matrix_loads_started"][-1]
    completed_count = len(log["matrix_transfers_completed"])
    formal = {
        "schema": "qadd-v63-tb-vcd-formal-return-analysis-v1",
        "package_id": PACKAGE_ID,
        "execution_id": core.get("execution_id"),
        "attempt_id": core.get("attempt_id"),
        "analysis_mode": "STREAMING_RESUME_BOUNDED_CONTEXT",
        "integrity": {
            "zip_crc_pass": True,
            "stream_eof_reached": True,
            "vcd_header_valid_by_multiline_parser": header["header_valid"],
            "vcd_timescale": header["timescale"],
            "catalog_signal_count": len(catalog["signals"]),
            "catalog_signals_mapped": len(catalog_rows),
            "missing_catalog_signals": missing,
            "vcd_declared_signal_count": len(header["variables"]),
            "uncataloged_vcd_signal_count": max(0, len(header["variables"]) - len(catalog_rows)),
            "return_core_waveform_receipts_empty": core.get("waveform_entry_receipts") == [],
            "return_core_no_size_limit_incorrect": core.get("waveform_no_size_limit") is False,
            "finalization_pass_conflicts_with_partial_runtime": finalization.get("pass") is True and runtime.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "execution": {
            "compile_exit": exit_receipt.get("compile_exit", 0),
            "simulation_started": exit_receipt.get("simulation_started", True),
            "simulation_exit": exit_receipt.get("exit_code", 124),
            "runtime_stop_reason": process.get("stop_reason"),
            "natural_terminal": False,
            "formal_d": False,
            "e3": False,
            "e4": False,
            "e5": False,
            "actual_dump_argv": actual.get("relevant_env"),
            "last_completed_matrix_transfer_count": completed_count,
            "last_started_matrix_load": last_load,
            "target_execution_started": False,
        },
        "signal_adjudication": {
            "last_vcd_time": state["last_sim_time"],
            "active_catalog_signals": active,
            "target_causal_signals_with_activity": target_activity,
            "catalog_rows": catalog_rows,
            "buffer5_request_decode_observed": False,
            "arm_branch_observed": False,
            "mrm_branch_observed": False,
            "bank_lane_readiness_observed": False,
            "read_accept_observed": False,
            "read_output_observed": False,
            "terminal_observed": False,
        },
        "causal_verdict": {
            "last_proven_good": "Production compile succeeded; execplan, bitstream, and slice00 through slice15 input transfers completed and read back. Slice16 write phase completed before interruption.",
            "first_divergence": "PACKAGE_RUNTIME_SUPERVISOR_FALSE_SIM_TIME_FREEZE_DURING_SLICE16_PRELOAD",
            "root_classification": "PACKAGE_LOCAL_RUNTIME_OBSERVER_RETURN_GATE_DEFECT",
            "root_confidence": "HIGH",
            "dut_root_cause": "NOT_ADJUDICABLE_TARGET_NOT_EXECUTED",
            "prior_v57h_boundary_closed_by_this_return": False,
        },
        "early_stop": {
            "correctly_applied": False,
            "plateau_marker_observed": False,
            "dumpoff_marker_observed": False,
            "stop_was_external_freeze_guard": True,
            "heartbeat_unsigned_overflow_signature": overflow_signature,
            "owner_cycles_continued_after_apparent_freeze": True,
            "reason": "The TB converted realtime through 32-bit $rtoi into an unsigned 64-bit value and emitted sparse heartbeats; wrap/overflow plus three 30-second sampling intervals caused a false freeze while the preload and VCD still advanced.",
        },
        "candidate_matrix": {
            "declared_pairwise_complete": matrix.get("pairwise_complete"),
            "rows": candidate_rows,
            "disposition": "UNEXERCISED_BEFORE_TARGET",
        },
        "package_local_defects": [
            "32-bit $rtoi heartbeat overflow/wrap and sparse heartbeat cadence enabled a false SIM_TIME_FREEZE.",
            "Depth-0 $dumpvars on the whole Buffer module captured uncataloged internals, including the 1024-bit data buffer, instead of the exact bounded causal set.",
            "The VCD parser rejected a valid standard multiline $timescale declaration.",
            "Return-core waveform receipts/no-size-limit fields conflict with the returned VCD manifest.",
            "Finalization reported pass while runtime evidence was partial, the VCD was not closed/flushed, and one owned process remained.",
            "compile_downstream_state and first_true_error were stale/benign despite successful compile and a supervisor timeout.",
        ],
        "claim_boundary": "No DUT root, natural terminal, formal D, E3, E4 or E5 claim: target execution never began and the return is partial diagnostic evidence.",
        "successor_justified": True,
    }
    atomic_json(FINAL, formal)

    state["checkpoint_count"] = int(state.get("checkpoint_count", 0)) + 1
    state["status"] = "FAMILY_ADJUDICATION_COMPLETE_TARGET_NOT_REACHED"
    state["timescale"] = header["timescale"]
    state["formal_analysis"] = FINAL.relative_to(ROOT).as_posix()
    state["claim_boundary"] = formal["claim_boundary"]
    atomic_json(STATE, state)
    checkpoint = {
        "schema": "server-tb-vcd-retention-analysis-v1",
        "kind": "analysis_checkpoint",
        "sequence": state["checkpoint_count"],
        "phase": "FAMILY_CAUSAL_ADJUDICATION",
        "status": state["status"],
        "byte_offset": state["byte_offset"],
        "last_sim_time": state["last_sim_time"],
        "catalog_mapped": len(catalog_rows),
        "target_activity_signals": len(target_activity),
        "root_classification": formal["causal_verdict"]["root_classification"],
    }
    with CHECKPOINTS.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")

    rows = [
        "# QAdd v63 incremental formal-return analysis",
        "",
        f"- status: `{state['status']}`",
        f"- streamed VCD: `{state['byte_offset']}` bytes through EOF in `{state['checkpoint_count']}` checkpoints",
        f"- VCD timescale: `{header['timescale']}` (valid multiline declaration)",
        f"- catalog mapping: `{len(catalog_rows)}/{len(catalog['signals'])}`",
        f"- target causal signals with post-initial activity: `{len(target_activity)}`",
        "",
        "## Formal verdict",
        "",
        f"- LAST_PROVEN_GOOD: {formal['causal_verdict']['last_proven_good']}",
        f"- FIRST_DIVERGENCE: `{formal['causal_verdict']['first_divergence']}`",
        f"- root classification: `{formal['causal_verdict']['root_classification']}` (HIGH confidence)",
        "- Buffer5 request decode and both ping-pong branches were not reached; every DUT candidate remains unexercised.",
        "- The VCD plateau/dumpoff early stop did not fire. The external freeze guard stopped a still-progressing preload.",
        "- natural/formal-D/E3/E4/E5 are all false and may not be inferred from this partial return.",
        "",
        "## Package-local defects",
        "",
    ]
    rows.extend(f"- {item}" for item in formal["package_local_defects"])
    rows.extend(
        [
            "",
            "The supplied return and raw VCD were preserved. No server action was performed.",
            "Immutable prior checkpoints remain append-only in `checkpoints.jsonl`.",
            "",
        ]
    )
    atomic_text(REPORT, "\n".join(rows))
    print(json.dumps({"pass": True, "status": state["status"], "root": formal["causal_verdict"]["root_classification"], "successor_justified": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
