#!/usr/bin/env python3
"""Exercise the exact QAdd v61 parser and formal-return gate locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_qadd_n7_tailround_lanephase_v61_obswide"


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def event(identity: tuple[str, str, str], seq: int, sim_time: int, signal_id: str, width: int, value: str, kind: str = "EVENT") -> dict[str, object]:
    return {
        "record_type": kind, "package_id": identity[0], "execution_id": identity[1],
        "attempt_id": identity[2], "seq": seq, "sim_time": sim_time,
        "timescale": "1ps", "signal_id": signal_id, "width_bits": width,
        "value_4state": value,
    }


def make_return(tree: Path, contract: dict[str, object], output: Path, malformed: bool) -> tuple[int, str]:
    identity = (PACKAGE, "synthetic-execution", "synthetic-attempt")
    parser = tree / "package_tools/qadd_observer_event_parser.py"
    with tempfile.TemporaryDirectory(prefix="qadd-v61-return-") as temporary:
        root = Path(temporary)
        evidence = root / "evidence"
        chunk = evidence / "observer/chunks/events-000000.jsonl"
        chunk.parent.mkdir(parents=True)
        rows = []
        alphabet = "01xz"
        for index, signal in enumerate(contract["signals"]):
            width = signal["width_bits"]
            value = "".join(alphabet[(index + bit) % len(alphabet)] for bit in range(width))
            if malformed and index == 0:
                value += "0"
            rows.append(event(identity, len(rows), 0, signal["signal_id"], width, value))
        rows.append(event(identity, len(rows), 10, "__heartbeat__", 1, "0", "HEARTBEAT"))
        rows.append(event(identity, len(rows), 20, "sig_clk", 1, "1"))
        chunk.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
        process = evidence / "PROCESS_TREE_RECEIPT.json"
        heartbeat = evidence / "supervisor_heartbeat.jsonl"
        actual = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
        write(process, {
            "schema": "server-observer-runtime-supervision-v1", "package_id": identity[0],
            "execution_id": identity[1], "attempt_id": identity[2],
            "process_tree_reaped": True, "owned_pids_remaining": [],
            "simulation_time_progress_observed": True,
        })
        heartbeat.write_text(
            json.dumps({"sequence": 0, "host_time_ns": 1, "simulation_time": 0}) + "\n" +
            json.dumps({"sequence": 1, "host_time_ns": 2, "simulation_time": 20}) + "\n",
            encoding="utf-8",
        )
        write(actual, {
            "schema": "server-observer-actual-argv-v1", "package_id": identity[0],
            "execution_id": identity[1], "attempt_id": identity[2],
            "source_identity_status": "COMPLETE",
            "compile_argv": ["make", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
        })
        command = [
            sys.executable, str(parser), "--contract", str(tree / "contracts/server_observer_only_wide_causal_contract.json"),
            "--chunk", str(chunk), "--package-id", identity[0], "--execution-id", identity[1],
            "--attempt-id", identity[2], "--exit-code", "0", "--signal", "NONE",
            "--timed-out", "false", "--simulation-started", "true", "--process-receipt", str(process),
            "--heartbeat-log", str(heartbeat), "--actual-argv", str(actual), "--output-dir", str(evidence),
        ]
        parsed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        if malformed:
            return parsed.returncode, parsed.stderr[-4096:]
        if parsed.returncode != 0:
            return parsed.returncode, parsed.stderr[-4096:]
        prefix = root / f"{PACKAGE}_return"
        (prefix / "evidence").mkdir(parents=True)
        (prefix / "observer/chunks").mkdir(parents=True)
        for name in (
            "ACTUAL_COMPILE_SIM_ARGV.json", "PROCESS_TREE_RECEIPT.json", "SIM_TIME_HEARTBEAT.json",
            "SIM_EXIT_RECEIPT.json", "OBSERVER_SIGNAL_CATALOG.json", "OBSERVER_EVENT_INDEX.json",
            "OBSERVER_DECISION.json",
        ):
            shutil.copyfile(evidence / name, prefix / "evidence" / name)
        shutil.copyfile(chunk, prefix / "observer/chunks/events-000000.jsonl")
        manifest_path = prefix / "RETURN_CORE_MANIFEST.json"
        members = sorted(
            f"{PACKAGE}_return/{path.relative_to(prefix).as_posix()}"
            for path in prefix.rglob("*") if path.is_file() and path != manifest_path
        )
        write(manifest_path, {
            "schema": "server-post-sim-return-core-manifest-v1", "package_id": identity[0],
            "execution_id": identity[1], "attempt_id": identity[2], "members": members,
            "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        })
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for path in sorted(prefix.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{PACKAGE}_return/{path.relative_to(prefix).as_posix()}")
    return 0, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-zip", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qadd-v61-package-") as temporary:
        extract = Path(temporary)
        with zipfile.ZipFile(args.package_zip) as archive:
            archive.extractall(extract)
        tree = extract / PACKAGE
        contract_path = tree / "contracts/server_observer_only_wide_causal_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        positive_zip = args.output.with_name("synthetic_observer_return.zip")
        positive_rc, positive_err = make_return(tree, contract, positive_zip, False)
        negative_rc, negative_err = make_return(tree, contract, args.output.with_name("negative_unused.zip"), True)
        if positive_rc != 0:
            errors.append(f"exact_parser_positive_failed:{positive_err}")
        if negative_rc == 0:
            errors.append("exact_parser_width_negative_not_rejected")
        gate_report = args.output.with_name("synthetic_observer_return_gate.json")
        gate = subprocess.run(
            [sys.executable, str(args.workspace_root / "tools/validate_server_observer_only_wide_causal.py"),
             "validate-return", "--zip", str(positive_zip), "--contract", str(contract_path),
             "--output", str(gate_report)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if gate.returncode != 0:
            errors.append(f"formal_return_gate_failed:{gate.stderr[-2048:]}")
        gate_value = json.loads(gate_report.read_text(encoding="utf-8")) if gate_report.is_file() else {}
    report = {
        "schema": "qadd-node0007-v61-observer-return-fixture-v1", "package_id": PACKAGE,
        "pass": not errors, "errors": errors,
        "positive_parser_exit": positive_rc, "width_negative_parser_exit": negative_rc,
        "formal_return_gate_pass": gate_value.get("pass") is True,
        "synthetic_return": {"path": str(positive_zip), "bytes": positive_zip.stat().st_size,
                             "sha256": hashlib.sha256(positive_zip.read_bytes()).hexdigest()},
        "claim_boundary": "Local exact-parser and synthetic formal-return integrity only; no DUT execution or signal verdict.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
