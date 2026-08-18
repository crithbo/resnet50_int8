#!/usr/bin/env python3
"""Exact-package operational-safety gate and required negative controls for v99."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Mapping


PACKAGE = "r5_n4_hw_v99b_lcdup_guarded"
THRESHOLDS = {
    "attempt_runtime_growth_stop_bytes": 800000000,
    "compile_attempt_growth_stop_bytes": 8000000000,
    "minimum_disk_free_bytes": 20000000000,
    "observer_file_rlimit_bytes": 500000000,
    "observer_stop_bytes": 400000000,
    "simulation_log_stop_bytes": 200000000,
    "compile_log_stop_bytes": 200000000,
    "simulation_wall_seconds": 3600,
    "finalization_growth_stop_bytes": 2000000000,
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(members: Mapping[str, bytes]) -> list[str]:
    errors: list[str] = []

    def text(relative: str) -> str:
        key = f"{PACKAGE}/{relative}"
        if key not in members:
            errors.append(f"missing member: {relative}")
            return ""
        try:
            return members[key].decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF8 member: {relative}")
            return ""

    try:
        guard = json.loads(text("contracts/observer_operational_guard_contract.json"))
    except json.JSONDecodeError:
        guard = {}
        errors.append("guard contract is invalid JSON")
    if guard.get("package_id") != PACKAGE or guard.get("thresholds") != THRESHOLDS:
        errors.append("guard identity or thresholds differ")
    stop = guard.get("stop_semantics", {})
    required_stop = {
        "stop_entire_simulation": True,
        "truncate_existing_rows": False,
        "sample_nonclock_causal_events": False,
        "delete_evidence_for_size": False,
        "partial_return": True,
        "diagnostic_status_on_guard": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "term_wait_kill_reap": True,
        "one_shot": True,
    }
    if stop != required_stop:
        errors.append("fail-closed stop semantics differ")

    runner = text("PREPARE_AND_RUN.sh")
    required_runner = (
        "--min-free-bytes 20000000000",
        "--growth-limit-bytes 800000000",
        "--growth-limit-bytes 2000000000",
        'observer=$observer_chunk=400000000',
        'sim_log=$run_root/c0/sim.log=200000000',
        'compile_log=$compile_log=200000000',
        "--file-size-limit-bytes 500000000",
        "--timeout 3600",
        "--timeout 900",
        '--owned-root "$bootstrap_root"',
        "server_observer_runtime_supervision_base.py",
        "publish_minimal_return",
        "server_package_attempt_cleanup.py",
        "filter_source_bound_log.py",
    )
    for token in required_runner:
        if token not in runner:
            errors.append(f"runner safety token absent: {token}")
    if runner.count("--min-free-bytes 20000000000") != 3:
        errors.append("compile/simulation/finalization disk-reserve guard cardinality differs")
    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
    if 'cp -f "$run_root/c0/sim.log" "$source_bound_log"' in runner:
        errors.append("full simulation log duplication remains reachable")

    observer = text("tb_probe/observer_only_wide_causal.svh")
    if "always @(sig_clk or" in observer or "force_all || sig_clk !== prev_sig_clk" in observer:
        errors.append("redundant every-clock-edge JSONL transport is reachable")
    if "CODEX_OBSERVER_SIM_TIME_V1" not in observer or "(codex_clock_count & 262143) == 0" not in observer:
        errors.append("periodic exact sim-time/owner-cycle heartbeat is absent")
    if "buf_idx_queue_bp_pre" in observer:
        errors.append("retired ACK comparator was reintroduced")

    wrapper = text("package_tools/server_observer_runtime_supervision.py")
    for token in ("RLIMIT_FSIZE", "DISK_FREE_RESERVE", "ATTEMPT_GROWTH_LIMIT", "WATCH_FILE_LIMIT", "SIGTERM", "SIGKILL", "reap_children", "GUARD_EXIT = 122"):
        if token not in wrapper:
            errors.append(f"operational supervisor primitive absent: {token}")
    parser = text("package_tools/node0004_observerwide_event_parser.py")
    if "args.chunk.read_text" in parser or ".splitlines()" in parser:
        errors.append("observer parser loads the complete chunk")
    if 'args.chunk.open("ab")' not in parser:
        errors.append("observer parser does not append close records in streaming mode")
    cleanup = text("package_tools/server_package_attempt_cleanup.py")
    for token in ("cleanup path identity differs", ".codex_owner.", ".codex_bootstrap_owner.json", "return_zip.resolve(strict=True)", "finalization_guard_receipt", "foreign_siblings_preserved"):
        if token not in cleanup:
            errors.append(f"cleanup identity guard absent: {token}")

    try:
        request = json.loads(text("contracts/server_post_sim_return_request.json"))
    except json.JSONDecodeError:
        request = {}
        errors.append("post-sim request is invalid JSON")
    entries = request.get("core_entries", [])
    archives = {item.get("archive") for item in entries if isinstance(item, dict)}
    for archive in (
        "evidence/OPERATIONAL_GUARD_RECEIPT.json",
        "evidence/COMPILE_OPERATIONAL_GUARD_RECEIPT.json",
        "evidence/observer_operational_guard_contract.json",
    ):
        if archive not in archives:
            errors.append(f"guard return member absent: {archive}")
    return errors


def negative_controls(members: dict[str, bytes]) -> list[dict[str, object]]:
    controls: list[tuple[str, str, bytes, bytes]] = [
        (
            "every_clock_edge_reintroduced",
            f"{PACKAGE}/tb_probe/observer_only_wide_causal.svh",
            b"always @(sig_rst_n or",
            b"always @(sig_clk or sig_rst_n or",
        ),
        (
            "disk_reserve_removed",
            f"{PACKAGE}/PREPARE_AND_RUN.sh",
            b"--min-free-bytes 20000000000",
            b"--min-free-bytes 0",
        ),
        (
            "observer_stop_raised",
            f"{PACKAGE}/PREPARE_AND_RUN.sh",
            b"observer=$observer_chunk=400000000",
            b"observer=$observer_chunk=50000000000",
        ),
        (
            "compile_log_guard_removed",
            f"{PACKAGE}/PREPARE_AND_RUN.sh",
            b"compile_log=$compile_log=200000000",
            b"compile_log=$compile_log=50000000000",
        ),
        (
            "whole_chunk_parser_reintroduced",
            f"{PACKAGE}/package_tools/node0004_observerwide_event_parser.py",
            b"with args.chunk.open(\"rb\") as stream:",
            b"rows = args.chunk.read_text(encoding=\"utf-8\").splitlines()\n    with args.chunk.open(\"rb\") as stream:",
        ),
        (
            "cleanup_removed",
            f"{PACKAGE}/PREPARE_AND_RUN.sh",
            b"server_package_attempt_cleanup.py",
            b"server_package_attempt_cleanup_DISABLED.py",
        ),
    ]
    rows: list[dict[str, object]] = []
    for control_id, key, old, new in controls:
        mutated = dict(members)
        source = mutated[key]
        if old not in source:
            rows.append({"control_id": control_id, "pass": False, "error": "mutation anchor absent"})
            continue
        mutated[key] = source.replace(old, new, 1)
        found = validate(mutated)
        rows.append({"control_id": control_id, "pass": bool(found), "rejected_errors": found})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        with zipfile.ZipFile(args.zip) as archive:
            roots = {PurePosixPath(name).parts[0] for name in archive.namelist() if PurePosixPath(name).parts}
            if roots != {PACKAGE} or archive.testzip() is not None:
                errors.append("ZIP root/CRC differs")
            members = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        members = {}
        errors.append(str(error))
    errors.extend(validate(members))
    negatives = negative_controls(members) if not errors else []
    if any(row.get("pass") is not True for row in negatives):
        errors.append("one or more negative controls were not rejected")
    report = {
        "schema": "node0004-v99b-operational-guard-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "negative_controls": negatives,
        "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip.read_bytes())},
        "expected_maximum_persistent_install_codex_runs_bytes_after_return": 0,
        "maximum_transient_growth_over_initial_bytes": 10800000000,
        "transient_bounds": THRESHOLDS,
        "claim_boundary": "Exact local package safety/negative-control validation only; remote disk residue and production execution remain unproven without a formal return.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
