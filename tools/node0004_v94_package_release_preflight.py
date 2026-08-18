#!/usr/bin/env python3
"""Read-only package-specific release preflight for serialized Conv v94b."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PACKAGE = "r5_n4_hw_v94b_tbvcd_wrdrain"
READY = "PACKAGE_READY_NOT_RUN"
MARKER = "package claim boundary differs"
REPLAY = [
    "ADVANCING_VCD_TIMESTAMP",
    "PLATEAU_SUSPECTED_ONLY",
    "PLATEAU_DUMP_OFF_PLUS_GRACE",
    "THREE_INTERVAL_TRUE_FREEZE",
]


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
    manifest = load(root / "package_manifest.json")
    contract = load(root / "contracts/tb_vcd_bounded_causal_cone_contract.json")
    selector = load(root / "contracts/diagnostic_mode_selector.json")
    request = load(root / "contracts/server_post_sim_return_request.json")
    if manifest.get("package_id") != PACKAGE or root.name != PACKAGE:
        errors.append(f"{MARKER}: package identity differs")
    if manifest.get("status") != READY:
        errors.append(f"{MARKER}: embedded status is not {READY}")
    if selector.get("selected_mode") != "TB_VCD_BOUNDED_CAUSAL_CONE":
        errors.append("diagnostic mode selector differs")
    execution = contract.get("execution", {})
    if execution.get("dump_argv") != {
        "DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"
    }:
        errors.append("actual dump argv differs")
    signals = contract.get("signals", [])
    ids = [row.get("signal_id") for row in signals if isinstance(row, dict)]
    targeting = execution.get("dump_targeting", {})
    if not (
        targeting.get("mode") == "EXACT_CATALOG_SIGNALS"
        and targeting.get("module_scope_dump") is False
        and targeting.get("dumpvars_depth") == 0
        and sorted(targeting.get("signal_ids", [])) == sorted(ids)
    ):
        errors.append("exact signal dump targeting differs")
    runtime = contract.get("runtime_policy", {})
    if not (
        runtime.get("heartbeat_source") == "APPENDED_VCD_TIMESTAMP"
        and runtime.get("heartbeat_width_bits") == 64
        and runtime.get("heartbeat_signed") is False
        and runtime.get("heartbeat_cadence_cycles") == 16_384
        and runtime.get("decision_authority") == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and runtime.get("outer_runner_independent_exit_logic") is False
        and runtime.get("required_replay_cases") == REPLAY
        and runtime.get("archive_timestamp_binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"
    ):
        errors.append("runtime-v3 decision/heartbeat/archive contract differs")
    tb_path = root / str(execution.get("tb_source_path", ""))
    if not tb_path.is_file() or sha(tb_path) != execution.get("tb_source_sha256"):
        errors.append("TB source identity differs")
    else:
        text = tb_path.read_text(encoding="utf-8")
        targets = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", text)
        exact = [str(row.get("exact_hierarchy")) for row in signals if isinstance(row, dict)]
        if len(targets) != len(exact) or sorted(item.strip() for item in targets) != sorted(exact):
            errors.append("TB exact dump target union differs")
        if "CODEX_VCD_CONTROL_PATH" not in text or "$dumpoff; $dumpflush" not in text:
            errors.append("shared-decision TB close/flush handshake differs")
    runner = (root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
    if "--runtime-evaluator" not in runner or "+CODEX_VCD_CONTROL_PATH=" not in runner:
        errors.append("runner does not delegate stop authority to shared evaluator")
    required = {
        "evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json",
        "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json",
        "evidence/vcd/VCD_RUNTIME_RECEIPT.json",
        "evidence/PROCESS_TREE_RECEIPT.json",
        "waveforms/causal_cone.vcd",
    }
    archives = {
        row.get("archive") for row in request.get("core_entries", [])
        if isinstance(row, dict)
    }
    if not required.issubset(archives):
        errors.append("formal return runtime/VCD core set differs")
    declared = manifest.get("files", [])
    actual = [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]
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
    except Exception as exc:
        errors = [str(exc)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 19 if any(MARKER in item for item in errors) else 3
    print(json.dumps({"package_id": PACKAGE, "status": READY, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
