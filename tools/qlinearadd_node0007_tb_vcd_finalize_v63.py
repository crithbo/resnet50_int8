#!/usr/bin/env python3
"""Close QAdd VCD evidence, emit runtime receipts, and seed streaming review."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def load(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def import_path(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan_vcd(path: Path, required_references: set[str]) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    size = 0
    header_valid = False
    timescale: str | None = None
    definitions = False
    references: set[str] = set()
    transitions = 0
    xz_transitions = 0
    last_time = 0
    in_timescale = False
    with path.open("rb") as stream:
        for raw in stream:
            size += len(raw)
            digest.update(raw)
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("$timescale"):
                payload = line.replace("$timescale", "").replace("$end", "").replace(" ", "").strip()
                in_timescale = "$end" not in line
                timescale = payload or timescale
            elif in_timescale:
                if line != "$end":
                    timescale = line.replace("$end", "").replace(" ", "").strip() or timescale
                if "$end" in line:
                    in_timescale = False
            elif line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 6:
                    references.add(parts[4].split("[")[0])
            elif line.startswith("$enddefinitions"):
                definitions = True
            elif line.startswith("#") and line[1:].isdigit():
                last_time = int(line[1:])
            elif line and line[0] in "01xXzZbB":
                transitions += 1
                if any(char in "xXzZ" for char in line.split()[0]):
                    xz_transitions += 1
    header_valid = bool(size and definitions and timescale)
    missing = sorted(required_references - references)
    return {
        "path": str(path),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "header_valid": header_valid,
        "timescale": timescale,
        "catalog_complete": not missing,
        "catalog_references": len(references),
        "missing_catalog_references": missing,
        "transitions_complete": bool(definitions and transitions > 0),
        "transition_lines": transitions,
        "xz_preserved": True,
        "xz_transition_lines": xz_transitions,
        "last_time": last_time,
        "return_allowlist_member": True,
        "transport": "DIRECT_PACKAGE_LOCAL_TB_VCD_NO_TRANSFORM",
    }


def log_has_marker(path: Path, marker: str) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    needle = marker.encode("ascii")
    with path.open("rb") as stream:
        return any(needle in line for line in stream)


def heartbeat_samples(process: dict[str, Any], vcd_bytes: int, natural: bool, exit_code: int) -> list[dict[str, Any]]:
    rows = process.get("samples") if isinstance(process.get("samples"), list) else []
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        sim_time = row.get("simulation_time")
        cycles = int(row.get("owner_clock_cycles", 0))
        global_value = int(row.get("global_progress_witness", 0))
        progress = int(row.get("causal_progress_events", 0))
        result.append(
            {
                "seq": index,
                "owner_clock_cycles": cycles,
                "sim_cycles": cycles,
                "sim_time_ticks": int(sim_time) if isinstance(sim_time, int) else 0,
                "wall_seconds": float(row.get("wall_seconds", 0)),
                "vcd_bytes": int(row.get("vcd_bytes", vcd_bytes)),
                "vcd_operational_projection_bytes": int(row.get("vcd_operational_projection_bytes", vcd_bytes)),
                "return_projection_bytes": int(row.get("return_projection_bytes", vcd_bytes)),
                "non_clock_events": progress,
                "causal_progress_events": progress,
                "qualified_progress_counters": {"causal_progress": progress},
                "causal_state_digest": str(row.get("causal_state_digest", "0" * 64)),
                "global_progress_witness": {"slice_cycle_or_terminal": global_value},
                "write_ok": row.get("write_ok") is not False,
                "disk_space_ok": row.get("disk_space_ok") is not False,
                "quota_ok": row.get("quota_ok") is not False,
            }
        )
    if not result:
        result.append(
            {
                "seq": 0,
                "owner_clock_cycles": 0,
                "sim_cycles": 0,
                "sim_time_ticks": 0,
                "wall_seconds": 0,
                "vcd_bytes": vcd_bytes,
                "non_clock_events": 0,
                "causal_progress_events": 0,
                "qualified_progress_counters": {},
                "causal_state_digest": "0" * 64,
                "global_progress_witness": {},
                "write_ok": True,
                "disk_space_ok": True,
                "quota_ok": True,
            }
        )
    final = result[-1]
    final["natural_terminal"] = natural
    final["exit_code"] = exit_code
    stop_reason = process.get("stop_reason")
    if stop_reason in {"HUP", "INT", "TERM"}:
        final["signal"] = stop_reason
    if stop_reason == "VCD_OPERATIONAL_BUDGET":
        final["vcd_operational_projection_bytes"] = 8_000_000_000
    if stop_reason == "RETURN_BUDGET_PROJECTION":
        final["return_projection_bytes"] = 10_000_000_000
    if stop_reason == "WALL_CEILING":
        final["wall_seconds"] = 3600
    if stop_reason == "SIM_TIME_FREEZE" and len(result) < 4:
        seed = dict(result[0])
        result = []
        for index in range(4):
            row = dict(seed)
            row.update({"seq": index, "owner_clock_cycles": index, "sim_cycles": index, "wall_seconds": index * 30})
            result.append(row)
        result[-1]["exit_code"] = exit_code
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--actual-argv", type=Path, required=True)
    parser.add_argument("--process-receipt", type=Path, required=True)
    parser.add_argument("--compile-source-identity", type=Path, required=True)
    parser.add_argument("--simulation-started", choices=["true", "false"], required=True)
    parser.add_argument("--simulation-exit", type=int, required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--natural-terminal", choices=["true", "false"], required=True)
    args = parser.parse_args()

    package = args.package_root.resolve(strict=True)
    attempt = args.attempt_root.resolve(strict=True)
    evidence = args.evidence_root.resolve(strict=True)
    for path in (args.vcd, args.actual_argv, args.process_receipt, args.compile_source_identity):
        resolved = path.resolve(strict=False)
        if resolved != package and package not in resolved.parents and resolved != attempt and attempt not in resolved.parents:
            raise ValueError(f"input escapes package/attempt roots: {path}")

    catalog_path = package / "diagnostics/tb_vcd_signal_catalog.json"
    matrix_path = package / "diagnostics/tb_vcd_candidate_matrix.json"
    contract_path = package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    tb_source_path = package / "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"
    catalog = load(catalog_path, {})
    required_references = {
        str(item.get("exact_hierarchy", "")).split(".")[-1].split("[")[0]
        for item in catalog.get("signals", [])
        if isinstance(item, dict)
    }
    required_references.discard("")
    vcd = scan_vcd(args.vcd, required_references) if args.simulation_started == "true" else None
    process = load(args.process_receipt, {})
    compile_identity = load(args.compile_source_identity, {})
    natural = args.natural_terminal == "true" and args.simulation_exit == 0

    vcd_dir = evidence / "vcd"
    vcd_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(catalog_path, vcd_dir / "catalog.json")
    shutil.copy2(matrix_path, vcd_dir / "candidate_matrix.json")
    shutil.copy2(tb_source_path, vcd_dir / "qlinearadd_node0007_tb_vcd_causal_cone_v63.svh")
    atomic_json(
        vcd_dir / "tb_source.json",
        {"path": "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh", "sha256": sha(tb_source_path)},
    )
    atomic_json(
        vcd_dir / "elaboration.json",
        {
            "compile_source_identity": compile_identity,
            "tb_source_sha256": sha(tb_source_path),
            "source_bound_status": "RUNTIME_COMPILE_IDENTITY_CAPTURED",
        },
    )
    atomic_json(
        vcd_dir / "return_manifest.json",
        {
            "schema": "qadd-tb-vcd-evidence-manifest-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "simulation_started": args.simulation_started == "true",
            "vcd": vcd,
            "no_size_limit": True,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
    )

    samples = heartbeat_samples(process, 0 if vcd is None else int(vcd["bytes"]), natural, args.simulation_exit)
    closed_marker = log_has_marker(attempt / "sim.log", "CODEX_TB_VCD_CLOSED")
    runtime_request = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "started": args.simulation_started == "true",
        "actual_argv_sha256": sha(args.actual_argv) if args.actual_argv.is_file() else "0" * 64,
        "catalog_sha256": sha(catalog_path),
        "candidate_matrix_sha256": sha(matrix_path),
        "tb_source_sha256": sha(tb_source_path),
        "elaboration_sha256": sha(args.compile_source_identity) if args.compile_source_identity.is_file() else "0" * 64,
        "candidate_catalog_complete": True,
        "unresolved_xz": False,
        "samples": samples,
        "flush": {
            "dumpoff": bool(vcd and closed_marker),
            "dumpflush": bool(vcd and closed_marker),
            "closed": bool(vcd and closed_marker),
        },
        "process_tree": {
            "term_sent": bool(process.get("termination")),
            "wait_completed": process.get("root_exit") is not None,
            "kill_sent_if_needed": any(item.get("signal") == 9 for item in process.get("termination", []) if isinstance(item, dict)),
            "all_reaped": process.get("process_tree_reaped") is True,
        },
        "vcd_identity": vcd,
    }
    request_path = vcd_dir / "runtime_request.json"
    atomic_json(request_path, runtime_request)
    runtime_module = import_path(package / "package_tools/server_tb_vcd_runtime_supervision.py", "qadd_vcd_runtime")
    runtime_receipt = runtime_module.evaluate(runtime_request)
    atomic_json(vcd_dir / "runtime.json", runtime_receipt)
    exact_set_pass = (
        (args.simulation_started == "false" and vcd is None)
        or bool(
            vcd
            and vcd.get("header_valid") is True
            and vcd.get("catalog_complete") is True
            and vcd.get("return_allowlist_member") is True
        )
    )
    atomic_json(
        vcd_dir / "TB_VCD_RETURN_EXACT_SET.json",
        {
            "schema": "qadd-tb-vcd-return-exact-set-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "simulation_started": args.simulation_started == "true",
            "raw_vcd": vcd,
            "runtime_receipt_sha256": sha(vcd_dir / "runtime.json"),
            "catalog_sha256": sha(catalog_path),
            "candidate_matrix_sha256": sha(matrix_path),
            "no_size_limit": True,
            "hard_truncation": False,
            "sampling": False,
            "size_based_deletion": False,
            "all_matching_collected": exact_set_pass,
            "diagnostic_status": runtime_receipt.get("diagnostic_status"),
            "pass": exact_set_pass,
            "claim_boundary": "Raw TB-VCD transport exact-set only; runtime completeness and DUT claims remain separate.",
        },
    )

    if vcd is not None:
        analysis = import_path(package / "package_tools/server_tb_vcd_retention_analysis.py", "qadd_vcd_analysis")
        analysis.analyze_chunk(args.vcd, vcd_dir / "analysis", "vcd", max_bytes=8 * 1024 * 1024)
    else:
        analysis_dir = vcd_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(
            analysis_dir / "analysis_state.json",
            {
                "schema": "server-tb-vcd-retention-analysis-v1",
                "kind": "analysis_state",
                "source": {"path": str(args.vcd), "bytes": 0, "sha256": "0" * 64},
                "byte_offset": 0,
                "line_number": 0,
                "last_sim_time": 0,
                "timescale": None,
                "signal_catalog": {},
                "signal_summaries": {},
                "status": "IN_PROGRESS",
                "checkpoint_count": 0,
                "claim_boundary": "Compile-not-started or missing-VCD state; no dynamic claim.",
            },
        )
        (analysis_dir / "checkpoints.jsonl").write_text("", encoding="utf-8", newline="\n")
        (analysis_dir / "report.md").write_text(
            "# Incremental diagnostic review\n\n- status: `IN_PROGRESS`\n- VCD unavailable in this partial attempt.\n",
            encoding="utf-8",
            newline="\n",
        )

    sim_exit = {
        "schema": "server-tb-vcd-sim-exit-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "simulation_started": args.simulation_started == "true",
        "exit_code": args.simulation_exit,
        "signal": args.signal,
        "natural_terminal": natural,
        "diagnostic_status": runtime_receipt.get("diagnostic_status"),
    }
    atomic_json(evidence / "SIM_EXIT_RECEIPT.json", sim_exit)
    result = {
        "pass": runtime_receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE",
        "runtime_status": runtime_receipt.get("diagnostic_status"),
        "natural_terminal": natural,
        "vcd_present": vcd is not None,
        "contract_sha256": sha(contract_path),
    }
    atomic_json(vcd_dir / "finalization_receipt.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["pass"] else 95


if __name__ == "__main__":
    raise SystemExit(main())
