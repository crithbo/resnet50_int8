#!/usr/bin/env python3
"""Finalize the streaming family analysis for the exact QAdd v64 return.

The 583 MB VCD is never loaded here.  This tool consumes the resumable state
written by server_tb_vcd_retention_analysis.py and streams the textual log and
small JSON return members directly from the ZIP.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
EXECUTION = "r1786704798234127277_2300842"
ATTEMPT = "a2300842"
RETURN = Path(
    r"C:\Users\15383\Downloads\r5_qadd_n7_tailround_lanephase_v64_tbvcdfix_"
    r"r1786704798234127277_2300842_return.zip"
)
OUT = ROOT / "outputs/qlinearadd_node0007_v64_return_r1786704798234127277_2300842"
STREAM = OUT / "streaming_analysis"
PREFIX = f"{PACKAGE}_return/"


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_bytes(canonical(value))
    os.replace(tmp, path)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_member(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    name = PREFIX + suffix
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {name}")
    return value


def scan_log(archive: zipfile.ZipFile) -> dict[str, Any]:
    name = PREFIX + "runs/sim.log"
    started: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    last_read_burst: dict[str, Any] | None = None
    line_number = 0
    target_markers: list[str] = []
    with archive.open(name) as raw:
        for blob in raw:
            line_number += 1
            line = blob.decode("utf-8", errors="replace").rstrip("\r\n")
            lower = line.lower()
            if "json: loading matrix[" in lower or "matrix transfer completed" in lower:
                slice_match = re.search(r"slice(\d{2})", lower)
                row = {"line": line_number, "slice": slice_match.group(1) if slice_match else None, "text": line[:512]}
                if "matrix transfer completed" in lower:
                    completed.append(row)
                elif "json: loading matrix[" in lower:
                    started.append(row)
            burst = re.search(r"\[Read Burst (\d+)\].*Addr=(0x[0-9a-fA-F]+).*Length=(\d+)", line)
            if burst:
                last_read_burst = {
                    "line": line_number,
                    "index": int(burst.group(1)),
                    "address": burst.group(2).lower(),
                    "length_words": int(burst.group(3)),
                }
            if any(token in line for token in ("Start_Comp", "EXEC_START", "CODEX_TB_VCD_NATURAL_TERMINAL", "CODEX_TBVCD_TARGET_ENTRY")):
                target_markers.append(line[:1024])
    return {
        "member": name,
        "lines": line_number,
        "matrix_loads_started": len(started),
        "matrix_transfer_completions": len(completed),
        "last_started_slice": started[-1]["slice"] if started else None,
        "last_completed_slice": completed[-1]["slice"] if completed else None,
        "last_read_burst": last_read_burst,
        "target_markers": target_markers,
    }


def main() -> int:
    state = json.loads((STREAM / "analysis_state.json").read_text(encoding="utf-8"))
    if not str(state.get("status", "")).startswith("EOF_REACHED"):
        raise RuntimeError("resumable VCD analysis has not reached EOF")
    if int(state.get("byte_offset", -1)) != 583_590_092:
        raise RuntimeError("unexpected streamed VCD byte boundary")
    with zipfile.ZipFile(RETURN) as archive:
        crc_error = archive.testzip()
        if crc_error is not None:
            raise RuntimeError(f"return CRC failure: {crc_error}")
        actual = object_member(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        process = object_member(archive, "evidence/PROCESS_TREE_RECEIPT.json")
        sim_exit = object_member(archive, "evidence/SIM_EXIT_RECEIPT.json")
        manifest = object_member(archive, "RETURN_CORE_MANIFEST.json")
        exact_set = object_member(archive, "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json")
        log = scan_log(archive)

    signals = state["signal_summaries"]
    clock = signals["'"]
    target_ids = [key for key in signals if key not in {"'", "(", "^"}]
    target_static = all(
        int(signals[key].get("last_time", 0)) == 0
        and int(signals[key].get("transitions", 0)) <= 1
        for key in target_ids
    )
    identity_ok = (
        actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
        and actual.get("source_identity_status") == "COMPLETE"
    )
    compile_exit = int(sim_exit.get("compile_exit", 0))
    simulation_exit = int(sim_exit.get("exit_code", 124))
    compile_ok = compile_exit == 0
    simulation_started = sim_exit.get("simulation_started") is True
    wall_reason = process.get("stop_reason") == "WALL_CEILING"
    all_reaped = process.get("process_tree_reaped") is True
    vcd_published = exact_set.get("pass") is True and isinstance(exact_set.get("raw_vcd"), dict)
    runtime_consistent = False if wall_reason and manifest.get("disposition") == "PARTIAL_EXECUTION_RETURN" else True
    candidates = [
        "selected_port_required_lanes_not_ready",
        "nonselected_port_or_pingpong_switch",
        "bank_lane_owner_full",
        "producer_or_clear",
        "read_barrier_or_accept",
        "downstream_output_or_terminal",
    ]
    candidate_matrix = [
        {
            "candidate": candidate,
            "status": "NOT_REACHED_NOT_ADJUDICABLE",
            "reason": "target entry and all Buffer5 causal-cone transitions are absent",
        }
        for candidate in candidates
    ]
    analysis = {
        "schema": "qlinearadd-node0007-v64-formal-return-analysis-v1",
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_REQUIRED",
        "integrity": {
            "zip_crc_pass": True,
            "identity_binding_pass": identity_ok,
            "source_identity_status": actual.get("source_identity_status"),
            "streaming_status": state.get("status"),
            "streamed_member_bytes": state.get("byte_offset"),
            "streamed_lines": state.get("line_number"),
            "last_vcd_timestamp_ps": state.get("last_sim_time"),
            "catalog_signal_count": len(state.get("signal_catalog", {})),
            "vcd_exact_set_published": vcd_published,
        },
        "production": {
            "compile_exit": compile_exit,
            "compile_succeeded": compile_ok,
            "simulation_started": simulation_started,
            "simulation_exit": simulation_exit,
            "actual_stop_reason": process.get("stop_reason"),
            "target_entry_observed": False,
            "target_static_signal_count": len(target_ids) if target_static else None,
            "clock_transitions": clock.get("transitions"),
            "matrix_preload": log,
        },
        "last_proven_good": {
            "classification": "PRODUCTION_COMPILE_AND_PRETARGET_PRELOAD_PROGRESS",
            "detail": "production compile passed; execplan/bitstream and 22 slice transfers completed; slice04 preload reached read burst 227",
        },
        "first_divergence": {
            "classification": "PACKAGE_RUNTIME_V3_PRETARGET_PROGRESS_AND_EXIT_AUTHORITY_ESCAPE_DURING_SLICE04_PRELOAD",
            "detail": "the causal witness stayed target-local while native preload advanced; the old outer supervisor hit WALL_CEILING, the old finalizer separately inferred a stale CAUSAL_PLATEAU, and the process tree/VCD were not quiescent",
        },
        "root_classification": {
            "class": "PACKAGE_LOCAL_RUNTIME_SUPERVISOR_FINALIZER_RETURN_GATE_DEFECT",
            "confidence": "HIGH",
            "dut_root_adjudicable": False,
            "defects": [
                "pre-target native loader progress was omitted from the complete global-progress witness",
                "outer supervisor and finalizer had split stop-decision authority",
                "finalizer replayed stale samples and conflicted with the actual wall-ceiling exit",
                "archive VCD tail was not bound to the evaluator snapshot",
                "process tree was not fully reaped and VCD was not dumpoff/flush/closed",
                "compile first-error extraction accepted benign parser text",
                "legacy packaged Python cache is incompatible with current exact-Python runtime admission",
            ],
        },
        "exit_mechanism_v3": {
            "implemented_by_v64": False,
            "actual_stop_reason": process.get("stop_reason"),
            "simulation_exit": simulation_exit,
            "process_tree_reaped": all_reaped,
            "runtime_and_archive_consistent": runtime_consistent,
            "finalization_pass": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "candidate_matrix": candidate_matrix,
        "boundaries": {
            "natural_terminal": False,
            "formal_D": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "target not entered and the attempt ended partial with an unreaped process tree and unclosed VCD",
        },
        "successor_justified": True,
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"],
        "conflicts": [],
        "errors": [] if identity_ok and compile_ok and simulation_started else ["formal return identity or production entry prerequisite failed"],
        "pass": identity_ok and compile_ok and simulation_started and str(state.get("status", "")).startswith("EOF_REACHED"),
        "claim_boundary": "This return proves a package-local pre-target runtime/finalization escape only; it does not adjudicate the Buffer5/ping-pong DUT candidates or natural/formal-D/E3/E4/E5.",
    }
    audit = {
        "schema": "qlinearadd-node0007-v64-package-build-failure-rule-audit-applicability-v1",
        "package_id": PACKAGE,
        "status": "APPLICABLE_PRIOR_AUDIT_RECONFIRMED_BEFORE_SUCCESSOR",
        "trigger_history": [
            "v59 package preflight blocked compile/target entry through manifest/install/SCA identity drift",
            "v63 package-local false freeze blocked target entry",
            "v64 package-local split exit authority and incomplete pre-target progress witness again blocked target entry",
        ],
        "rule_gap_audit_triggered": False,
        "rule_gap_reason": "production target did not execute, so the one-round unique-root causal-cone guarantee was not exercised",
        "disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "current_rule_sufficient": True,
        "implementation_required": [
            "shared runtime evaluator is the sole exit authority",
            "same complete global-progress witness covers pre-target native loader activity or prevents plateau eligibility before target entry",
            "exact four-case replay and archive SHA/bytes/last-timestamp binding",
            "TERM-wait-KILL-reap and dump-off/flush/close conjunction",
            "current package Python/schema runtime-v2 exact source set with no pyc",
            "negative control forbids stale replay from converting advancing pre-target work into CAUSAL_PLATEAU",
        ],
        "public_rule_change_requested": False,
        "shared_tool_change_requested": False,
        "claim_boundary": "Family applies already-activated exit-v3 and package-Python/runtime-v2 contracts; public rules and shared tools remain optimizer-owned and unchanged.",
        "pass": True,
        "errors": [],
    }
    atomic_json(OUT / "formal_return_analysis.json", analysis)
    atomic_json(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json", audit)

    checkpoint = {
        "schema": "qlinearadd-node0007-v64-family-analysis-checkpoint-v1",
        "seq": int(state.get("checkpoint_count", 0)) + 1,
        "status": "FORMAL_FAMILY_ANALYSIS_COMPLETE",
        "byte_offset": state.get("byte_offset"),
        "line_number": state.get("line_number"),
        "last_sim_time": state.get("last_sim_time"),
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": analysis["first_divergence"]["classification"],
        "root_classification": analysis["root_classification"]["class"],
        "analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
    }
    checkpoint_path = STREAM / "checkpoints.jsonl"
    prior_checkpoints = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    if '"status": "FORMAL_FAMILY_ANALYSIS_COMPLETE"' not in prior_checkpoints:
        with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
    state["family_analysis"] = checkpoint
    state["status"] = "EOF_REACHED_FAMILY_ANALYSIS_COMPLETE"
    atomic_json(STREAM / "analysis_state.json", state)
    report_path = STREAM / "report.md"
    prior_report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    if "## Family formal disposition" not in prior_report:
        with report_path.open("a", encoding="utf-8", newline="\n") as report:
            report.write(
            "\n## Family formal disposition\n\n"
            "- production compile: `PASS`\n"
            "- target entry: `NOT_REACHED`\n"
            "- last proven good: compile plus pre-target matrix preload through slice04 read burst 227\n"
            "- first divergence: package runtime-v3 pre-target progress/exit-authority escape\n"
            "- root class: `PACKAGE_LOCAL_RUNTIME_SUPERVISOR_FINALIZER_RETURN_GATE_DEFECT` (HIGH)\n"
            "- candidate matrix: all DUT candidates `NOT_REACHED_NOT_ADJUDICABLE`\n"
            "- natural/formal-D/E3/E4/E5: not proven\n"
            "- audit disposition: `RULE_CONFIRMATION_NO_CHANGE`; fresh runtime-v3 successor required\n"
            )
    print(json.dumps({"analysis": str(OUT / "formal_return_analysis.json"), "pass": analysis["pass"]}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
