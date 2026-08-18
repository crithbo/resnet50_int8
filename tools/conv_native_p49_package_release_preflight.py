#!/usr/bin/env python3
"""Read-only package-specific release preflight for native Conv p49."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PACKAGE = "r5_n4_0cc_p49_tbvcdrt2"
READY = "PACKAGE_READY_NOT_RUN"
MARKER = "package claim boundary differs"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def preflight(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    errors: list[str] = []
    pointer = load(root / "TEST_PACKAGE_MANIFEST.json")
    manifest = load(root / "package_manifest.json")
    contract = load(root / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    selector = load(root / "contracts/server_diagnostic_mode_selector.json")
    request = load(root / "contracts/server_post_sim_return_request.json")
    if pointer.get("package_identity") != PACKAGE or manifest.get("package_identity") != PACKAGE:
        errors.append(f"{MARKER}: package identity differs")
    if pointer.get("status") != READY or manifest.get("status") != READY:
        errors.append(f"{MARKER}: embedded status is not {READY}")
    if selector.get("selected_mode") != "TB_VCD_BOUNDED_CAUSAL_CONE":
        errors.append("diagnostic mode selector differs")
    execution = contract.get("execution", {})
    if execution.get("dump_argv") != {
        "DUMP_VCD": "0",
        "DUMP_FSDB": "0",
        "TB_DUMP_FSDB": "0",
    }:
        errors.append("actual dump argv differs")
    targeting = execution.get("dump_targeting", {})
    signals = contract.get("signals", [])
    signal_ids = [row.get("signal_id") for row in signals if isinstance(row, dict)]
    if not (
        targeting.get("mode") == "EXACT_CATALOG_SIGNALS"
        and targeting.get("module_scope_dump") is False
        and targeting.get("dumpvars_depth") == 0
        and sorted(targeting.get("signal_ids", [])) == sorted(signal_ids)
    ):
        errors.append("exact signal dump targeting differs")
    runtime = contract.get("runtime_policy", {})
    if not (
        runtime.get("heartbeat_source") == "APPENDED_VCD_TIMESTAMP"
        and runtime.get("heartbeat_width_bits", 0) >= 64
        and runtime.get("heartbeat_signed") is False
        and runtime.get("heartbeat_cadence_cycles") == 16_384
        and runtime.get("decision_authority") == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and runtime.get("outer_runner_independent_exit_logic") is False
        and runtime.get("required_replay_cases") == [
            "ADVANCING_VCD_TIMESTAMP",
            "PLATEAU_SUSPECTED_ONLY",
            "PLATEAU_DUMP_OFF_PLUS_GRACE",
            "THREE_INTERVAL_TRUE_FREEZE",
        ]
        and runtime.get("archive_timestamp_binding")
        == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
    ):
        errors.append("runtime-v3 decision/heartbeat/archive contract differs")
    tb_path = root / str(execution.get("tb_source_path", ""))
    if not tb_path.is_file() or sha(tb_path) != execution.get("tb_source_sha256"):
        errors.append("TB source identity differs")
    else:
        text = tb_path.read_text(encoding="utf-8")
        targets = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", text)
        expected = [str(row.get("exact_hierarchy")) for row in signals if isinstance(row, dict)]
        if len(targets) != len(expected) or sorted(item.strip() for item in targets) != sorted(expected):
            errors.append("TB exact dump target union differs")
        for token in (
            "CODEX_TBVCD_HEARTBEAT_V2",
            "64'h3fff",
            "CODEX_TBVCD_TARGET_ENTRY_V2",
            "$dumpflush",
        ):
            if token not in text:
                errors.append(f"TB runtime-v3 token absent: {token}")
        if "$finish;" in text:
            errors.append("TB retains an independent plateau exit")
    runner = (root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
    forbidden_dump_tokens = [f"{key}={1}" for key in ("DUMP_VCD", "DUMP_FSDB", "TB_DUMP_FSDB")]
    if any(token in runner for token in forbidden_dump_tokens):
        errors.append("runner enables forbidden Make waveform")
    for token in (
        "--runtime-evaluator",
        "server_tb_vcd_runtime_supervision.py",
        "--decision-receipt",
        "TB_VCD_LIVE_DECISION_RECEIPT.json",
    ):
        if token not in runner:
            errors.append(f"shared evaluator handoff token absent: {token}")
    required_archives = {
        "evidence/TB_VCD_RETURN_EXACT_SET.json",
        "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json",
        "evidence/TB_VCD_RUNTIME_RECEIPT.json",
        "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json",
        "evidence/PROCESS_TREE_RECEIPT.json",
        "runs/c0/native_mse4_causal.vcd",
    }
    actual_archives = {
        row.get("archive")
        for row in request.get("core_entries", [])
        if isinstance(row, dict) and row.get("required") is True
    }
    if not required_archives.issubset(actual_archives):
        errors.append("formal return exact core set differs")
    if not (root / "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").is_file():
        errors.append("mandatory package-build-failure audit absent")
    declared = manifest.get("files", {})
    actual = {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }
    if declared != actual:
        errors.append("embedded package file map differs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight",))
    parser.add_argument("--package-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        errors = preflight(args.package_root)
    except Exception as exc:  # fail closed with bounded diagnostic text
        errors = [str(exc)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 3
    print(json.dumps({"package_id": PACKAGE, "status": READY, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
