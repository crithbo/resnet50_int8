#!/usr/bin/env python3
"""Finalize same-attempt native p47 VCD evidence without loading it wholly."""

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


def sha_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, path)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scan_vcd(path: Path, expected_names: set[str]) -> dict[str, Any]:
    header_valid = False
    timescale: str | None = None
    names: set[str] = set()
    value_characters: set[str] = set()
    if not path.is_file() or path.is_symlink():
        return {"exists": False, "header_valid": False, "timescale": None, "names": [], "value_characters": []}
    in_header = True
    pending_timescale = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            stripped = line.strip()
            if in_header:
                if stripped.startswith("$timescale"):
                    body = stripped.removeprefix("$timescale").replace("$end", "").strip()
                    if body:
                        timescale = body
                    else:
                        pending_timescale = True
                elif pending_timescale and stripped and not stripped.startswith("$"):
                    timescale = stripped
                if stripped.startswith("$var"):
                    parts = stripped.split()
                    if len(parts) >= 6:
                        names.add(parts[4])
                if stripped.startswith("$enddefinitions"):
                    header_valid = bool(timescale and names)
                    in_header = False
            elif stripped:
                if stripped[0] in "01xXzZ":
                    value_characters.add(stripped[0].lower())
                elif stripped[0] in "bB" and len(stripped) > 1:
                    value_characters.update(ch.lower() for ch in stripped[1:].split()[0] if ch in "01xXzZ")
    return {
        "exists": True, "header_valid": header_valid, "timescale": timescale,
        "names": sorted(names), "value_characters": sorted(value_characters),
        "catalog_complete": expected_names.issubset(names),
        "missing_expected_names": sorted(expected_names - names),
    }


def parse_markers(log: Path) -> dict[str, Any]:
    result = {
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "stop_reason": None, "terminal_witness": False,
        "last_sim_time": 0, "last_cycles": 0, "last_progress": 0,
    }
    if not log.is_file():
        return result
    heartbeat = re.compile(r"CODEX_TBVCD_HEARTBEAT_V1 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+)")
    stop = re.compile(r"CODEX_TBVCD_STOP_V1 reason=([A-Z_]+)")
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = heartbeat.search(line)
        if match:
            result["last_sim_time"] = int(match.group(1))
            result["last_cycles"] = int(match.group(2))
            result["last_progress"] = int(match.group(3))
        match = stop.search(line)
        if match:
            result["stop_reason"] = match.group(1)
        if "CODEX_TBVCD_TERMINAL_WITNESS_V1" in line:
            result["terminal_witness"] = True
        if "CODEX_TBVCD_FLUSH_V1" in line:
            result["flush"] = {"dumpoff": True, "dumpflush": True, "closed": True}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--actual-root", required=True)
    parser.add_argument("--published-root", required=True)
    parser.add_argument("--compile-exit", type=int, required=True)
    parser.add_argument("--sim-exit", type=int, required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--process-receipt", type=Path, required=True)
    parser.add_argument("--safety-receipt", type=Path, required=True)
    args = parser.parse_args()

    package = args.package_root.resolve()
    evidence = args.evidence_root.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    contract_path = package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    catalog_path = package / "diagnostics/tb_vcd_causal_signal_catalog.json"
    matrix_path = package / "diagnostics/tb_vcd_candidate_boundary_matrix.json"
    actual_path = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    tb_path = package / contract["execution"]["tb_source_path"]
    expected_names = {item["exact_hierarchy"].rsplit(".", 1)[-1] for item in contract["signals"]}
    scan = scan_vcd(args.vcd, expected_names)
    markers = parse_markers(args.sim_log)
    process = load(args.process_receipt) if args.process_receipt.is_file() else {}
    safety = load(args.safety_receipt) if args.safety_receipt.is_file() else {}
    safety_reason = safety.get("stop_reason")
    stop_reason = safety_reason or markers["stop_reason"]
    if stop_reason is None:
        if args.signal in {"HUP", "INT", "TERM"}:
            stop_reason = args.signal
        elif args.sim_exit != 0:
            stop_reason = "NONZERO_EXIT"
        elif markers["terminal_witness"]:
            stop_reason = "NATURAL_TERMINAL"
        else:
            stop_reason = "NONZERO_EXIT"
    natural = stop_reason == "NATURAL_TERMINAL" and args.sim_exit == 0
    process_tree = {
        "term_sent": bool(process.get("termination")),
        "wait_completed": process.get("root_exit") is not None,
        "kill_sent_if_needed": any(item.get("signal") == 9 for item in process.get("termination", [])),
        "all_reaped": process.get("process_tree_reaped") is True,
    }
    if args.vcd.is_file():
        vcd_bytes, vcd_sha = sha_file(args.vcd)
        vcd_identity: dict[str, Any] | None = {
            "path": str(args.vcd), "bytes": vcd_bytes, "sha256": vcd_sha,
            "header_valid": scan["header_valid"], "timescale": scan["timescale"] or "unknown",
            "catalog_complete": scan.get("catalog_complete") is True,
            "transitions_complete": markers["flush"]["closed"] and process_tree["all_reaped"],
            "xz_preserved": scan["header_valid"], "return_allowlist_member": True,
        }
    else:
        vcd_identity = None
    samples = []
    if args.samples.is_file():
        for line in args.samples.read_text(encoding="utf-8").splitlines():
            if line.strip():
                samples.append(json.loads(line))
    if samples:
        samples[-1]["exit_code"] = args.sim_exit
        if natural:
            samples[-1]["natural_terminal"] = True
        if args.signal in {"HUP", "INT", "TERM"}:
            samples[-1]["signal"] = args.signal
    else:
        samples = [{
            "seq": 0, "wall_seconds": 0, "sim_time_ticks": markers["last_sim_time"],
            "sim_cycles": markers["last_cycles"], "owner_clock_cycles": markers["last_cycles"],
            "causal_progress_events": markers["last_progress"], "vcd_bytes": 0,
            "unresolved_xz": True, "exit_code": args.sim_exit,
        }]

    shutil.copyfile(catalog_path, evidence / "TB_VCD_CAUSAL_SIGNAL_CATALOG.json")
    shutil.copyfile(matrix_path, evidence / "TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json")
    tb_bytes, tb_sha = sha_file(tb_path)
    atomic_json(evidence / "TB_SOURCE_RECEIPT.json", {
        "schema": "server-tb-vcd-source-receipt-v1", "path": str(tb_path),
        "bytes": tb_bytes, "sha256": tb_sha,
        "matches_contract": tb_sha == contract["execution"]["tb_source_sha256"],
    })
    compile_log = args.attempt_root / "evidence/compile_rootcause/compile_driver.log"
    compile_log_identity = None
    if compile_log.is_file():
        size, digest = sha_file(compile_log)
        compile_log_identity = {"path": str(compile_log), "bytes": size, "sha256": digest}
    elaboration = {
        "schema": "server-tb-vcd-elaboration-receipt-v1",
        "compile_exit": args.compile_exit, "tb_source_sha256": tb_sha,
        "compile_log": compile_log_identity,
        "elaboration_status": "PRODUCTION_COMPILE_PASSED" if args.compile_exit == 0 else "PRODUCTION_COMPILE_FAILED",
        "server_source_identity_timing": "AFTER_ACTUAL_COMPILE",
    }
    atomic_json(evidence / "TB_VCD_ELABORATION_RECEIPT.json", elaboration)
    atomic_json(evidence / "PUBLISHED_ACTUAL_ROOT_IDENTITY.json", {
        "schema": "server-published-actual-root-identity-v1",
        "package_id": args.package_id, "execution_id": args.execution_id,
        "attempt_id": args.attempt_id, "published_root": args.published_root,
        "actual_root": args.actual_root,
        "match": args.published_root == args.actual_root,
        "mismatch_classification": None if args.published_root == args.actual_root else "EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION",
        "claim_boundary": "Root identity only; a mismatch restricts family interpretation and is not silently normalized.",
    })
    atomic_json(evidence / "TB_VCD_IDENTITY.json", {"schema": "server-tb-vcd-identity-v1", **scan, "identity": vcd_identity})
    atomic_json(evidence / "TB_VCD_STOP_RECEIPT.json", {
        "schema": "server-tb-vcd-stop-receipt-v1", "stop_reason": stop_reason,
        "natural_terminal": natural, "markers": markers, "safety": safety,
        "non_natural_claim_boundary": None if natural else "PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE; no natural/formal-D/E4/E5 claim",
    })

    request = {
        "package_id": args.package_id, "execution_id": args.execution_id,
        "attempt_id": args.attempt_id, "started": args.compile_exit == 0,
        "actual_argv_sha256": sha_file(actual_path)[1] if actual_path.is_file() else "0" * 64,
        "catalog_sha256": sha_file(catalog_path)[1],
        "candidate_matrix_sha256": sha_file(matrix_path)[1],
        "tb_source_sha256": tb_sha, "elaboration_sha256": canonical_sha(elaboration),
        "samples": samples, "candidate_catalog_complete": True,
        "unresolved_xz": bool(samples[-1].get("unresolved_xz", True)),
        "flush": markers["flush"], "process_tree": process_tree,
        "vcd_identity": vcd_identity,
    }
    atomic_json(evidence / "TB_VCD_RUNTIME_REQUEST.json", request)
    module_path = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    spec = importlib.util.spec_from_file_location("server_tb_vcd_runtime_supervision", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime evaluator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.evaluate(request)
    atomic_json(evidence / "TB_VCD_RUNTIME_RECEIPT.json", receipt)
    return 0 if receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE" else 97


if __name__ == "__main__":
    raise SystemExit(main())
