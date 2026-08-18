#!/usr/bin/env python3
"""Fail closed on v103 frozen surfaces and observer/runtime regressions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


OLD = "r5_n4_hw_v102b_lcdup_guardprocfs"
NEW = "r5_n4_hw_v103b_lcdup_obsfix"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def files(archive: zipfile.ZipFile, root: str) -> dict[str, bytes]:
    return {
        PurePosixPath(name).relative_to(root).as_posix(): archive.read(name)
        for name in archive.namelist()
        if name.startswith(root + "/") and not name.endswith("/")
    }


def normalized(value: bytes) -> bytes:
    try:
        text = value.decode("utf-8").replace(NEW, OLD)
        text = re.sub(r"(?m)^// plan_semantic_sha256=[0-9a-f]{64}\r?$", "// plan_semantic_sha256=<IDENTITY_BOUND>", text)
        return text.encode("utf-8")
    except UnicodeDecodeError:
        return value


def check(observer: str, runner: str, parser: str, bridge: str, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for token in ("`timescale 1ps/1ps", "codex_counter_time_ps = $time", "cnt_lc3_accept", "cnt_pe_tuple_wr", "cnt_input1_accept", "cnt_mem_tuple_wr", "cnt_metadata_emit", "cnt_prepared_wr", "cnt_prepared_rd", "cnt_wdata0_accept", "cnt_wdata1_accept", "codex_causal_state", "codex_global_witness", "$isunknown", "16383", "1048576", "PLANNED_PLATEAU_STOP"):
        if token not in observer:
            errors.append(f"observer token absent: {token}")
    for token in ("$rtoi", "$realtime"):
        if token in observer:
            errors.append(f"32-bit-prone observer time token remains: {token}")
    if "sig_lc3_valid && !sig_lc3_bp" not in observer:
        errors.append("LC3 counter is not ready/valid qualified")
    if "sig_wdata_valid[0] && sig_wdata_ready[0]" not in observer or "sig_wdata_valid[1] && sig_wdata_ready[1]" not in observer:
        errors.append("downstream lane counters are not valid/ready qualified")
    if "cnt_metadata_emit = cnt_metadata_emit + 2" not in observer:
        errors.append("metadata count is not derived from accepted Memory_AG tuples")
    if "if (sig_mem_tag_valid) begin cnt_metadata_emit" in observer:
        errors.append("held metadata-valid level is still counted as repeated progress")
    if runner.count("supervise-phase --phase simulation") != 1:
        errors.append("simulation exit authority is not exactly one")
    simulation_line = next((line for line in runner.splitlines() if "supervise-phase --phase simulation" in line), "")
    if "server_observer_runtime_supervision.py" in simulation_line or "--timeout 3660" not in simulation_line:
        errors.append("simulation authority still nests a second supervisor or uses a different wall")
    if "--timeout 3600" in runner:
        errors.append("stale 3600-second outer wall remains")
    for token in ("node0004_observer_counter_guard_bridge.py", "+CODEX_COUNTER_CHUNK=$counter_chunk", "PLANNED_STOP_RECEIPT.json", "PROCESS_TREE_RECEIPT.json"):
        if token not in runner:
            errors.append(f"runner counter/return token absent: {token}")
    for token in ("planned_stop", "not planned_stop", "sig_slice_finish", "sig_exec_slice13_finish"):
        if token not in parser:
            errors.append(f"parser terminal qualification token absent: {token}")
    for token in ("process_fully_reaped", "owned_process_identities_remaining", "complete_state_width", "one_shot", "simulation_time_progress_observed"):
        if token not in bridge:
            errors.append(f"guard/counter bridge token absent: {token}")
    signals = contract.get("signals", [])
    if len(signals) != 52 or sum(int(item.get("width_bits", 0)) for item in signals if item.get("signal_id") != "sig_clk") != 256:
        errors.append("exact 52-signal/256-nonclock-bit cone differs")
    plateau = contract.get("package_local_counter_plateau", {})
    if plateau.get("required_plateau_cycles") != 1048576 or plateau.get("complete_causal_state_bits") != 256 or plateau.get("xz_resets_plateau") is not True:
        errors.append("contract plateau conjunction differs")
    return errors


def synthetic_bridge(bridge_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    controls: list[dict[str, Any]] = []
    errors: list[str] = []
    identity = (NEW, "rsynthetic", "asynthetic")
    with tempfile.TemporaryDirectory(prefix="node0004-v103-bridge-") as tmp_name:
        tmp = Path(tmp_name)
        guard = {
            "pass": True, "process_fully_reaped": True, "child_exit": 0,
            "termination": {"process_tree_reaped": True, "owned_pids_remaining": [], "owned_process_identities_remaining": [], "root_exit": 0},
        }
        (tmp / "guard.json").write_text(json.dumps(guard), encoding="utf-8")
        base = {"package_id": identity[0], "execution_id": identity[1], "attempt_id": identity[2], "timescale": "1ps", "state_width": 256, "state_4state": "0" * 256, "global_witness_4state": "0" * 771, "state_has_xz": 0, "target_active": 1, "plateau_cycles": 0, "lc3_accept": 10, "pe_tuple_wr": 10, "pe_tuple_rd": 10, "input1_accept": 10, "memory_tuple_wr": 10, "memory_tuple_rd": 10, "metadata_emit": 20, "prepared_wr": 20, "prepared_rd": 20, "wdata0_accept": 20, "wdata1_accept": 20, "terminal_witness": 0}
        rows = []
        for seq, (kind, sim_time, cycle, plateau) in enumerate((("TARGET_ENTRY", 5_000_000_000, 2_000_000, 0), ("COUNTER_HEARTBEAT", 5_040_960_000, 2_016_384, 16_384), ("PLANNED_PLATEAU_STOP", 7_621_440_000, 3_048_576, 1_048_576), ("FINAL", 7_621_440_000, 3_048_576, 1_048_576))):
            rows.append({**base, "record_type": kind, "seq": seq, "sim_time": sim_time, "owner_cycle": cycle, "plateau_cycles": plateau})
        counter = tmp / "counter.jsonl"
        counter.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        command = [sys.executable, str(bridge_path), "--guard", str(tmp / "guard.json"), "--counter", str(counter), "--package-id", identity[0], "--execution-id", identity[1], "--attempt-id", identity[2], "--output-dir", str(tmp / "out")]
        positive = subprocess.run(command, capture_output=True, text=True, check=False)
        positive_ok = positive.returncode == 0 and json.loads((tmp / "out/PROCESS_TREE_RECEIPT.json").read_text()).get("process_tree_reaped") is True and json.loads((tmp / "out/PLANNED_STOP_RECEIPT.json").read_text()).get("planned_stop") is True
        controls.append({"control": "qualified_planned_plateau_positive", "pass": positive_ok, "exit_code": positive.returncode, "stderr": positive.stderr[-2048:]})
        bad_rows = json.loads(json.dumps(rows)); bad_rows[1]["state_4state"] = "0" * 255
        counter.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in bad_rows), encoding="utf-8")
        bad_state = subprocess.run(command, capture_output=True, text=True, check=False)
        controls.append({"control": "incomplete_state_negative", "pass": bad_state.returncode != 0, "exit_code": bad_state.returncode})
        guard["termination"]["owned_process_identities_remaining"] = [{"pid": 99, "start_time_ticks": 1}]
        (tmp / "guard.json").write_text(json.dumps(guard), encoding="utf-8")
        counter.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
        bad_reap = subprocess.run(command, capture_output=True, text=True, check=False)
        controls.append({"control": "remaining_pid_identity_negative", "pass": bad_reap.returncode != 0, "exit_code": bad_reap.returncode})
    if not all(item["pass"] for item in controls):
        errors.append("one or more synthetic bridge controls did not fail closed")
    return controls, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--fresh-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    frozen_rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(args.source_zip) as old_archive, zipfile.ZipFile(args.fresh_zip) as new_archive:
        old = files(old_archive, OLD); new = files(new_archive, NEW)
        required = sorted([path for path in old if path.startswith("workload/")] + [
            "provenance/lc_branch_duplication_mapper_ab_report.json",
            "provenance/B_duplicate_lc_branch_config.json",
            "diagnostics/source_bound_probe_catalog.json",
            "diagnostics/source_bound_probe_plan.json",
            "diagnostics/source_bound_exact_instance_identity.json",
            "tb_probe/source_bound_causal_observer.svh",
        ])
        for path in required:
            equal = path in new and normalized(old[path]) == normalized(new[path])
            frozen_rows.append({"path": path, "normalized_equal": equal, "old_sha256": sha(old.get(path, b"")), "new_sha256": sha(new.get(path, b""))})
            if not equal: errors.append(f"frozen member differs: {path}")
        old_contract = json.loads(old["contracts/observer_only_wide_causal_contract.json"])
        contract = json.loads(new["contracts/observer_only_wide_causal_contract.json"])
        old_signal_axes = [(row["signal_id"], row["width_bits"], row.get("hierarchy")) for row in old_contract["signals"]]
        new_signal_axes = [(row["signal_id"], row["width_bits"], row.get("hierarchy")) for row in contract["signals"]]
        if old_signal_axes != new_signal_axes: errors.append("52-signal IDs/widths/hierarchies differ from v102")
        if old_contract["candidates"] != contract["candidates"] or old_contract["boundary_observations"] != contract["boundary_observations"]:
            errors.append("candidate/boundary matrix differs from v102")
        observer = new["tb_probe/observer_only_wide_causal.svh"].decode("utf-8")
        runner = new["PREPARE_AND_RUN.sh"].decode("utf-8")
        event_parser = new["package_tools/node0004_observerwide_event_parser.py"].decode("utf-8")
        bridge = new["package_tools/node0004_observer_counter_guard_bridge.py"].decode("utf-8")
        errors.extend(check(observer, runner, event_parser, bridge, contract))
    controls, control_errors = synthetic_bridge(Path(__file__).resolve().parents[1] / "outputs/conv_node0004_v103b_lcdup_obsfix_release1/build" / NEW / "package_tools/node0004_observer_counter_guard_bridge.py")
    errors.extend(control_errors)
    report = {
        "schema": "node0004-v103b-lcdup-obsfix-validation-v1", "package_id": NEW,
        "pass": not errors, "errors": errors, "frozen_rows": frozen_rows,
        "frozen_surface": ["config", "functional RTL", "workload", "numeric", "golden", "LC9-to-LC3 mapper semantics", "52-signal causal cone"],
        "changed_surface": ["fresh identity", "observer 64-bit time", "qualified counters", "complete-state/global-witness plateau", "single simulation authority", "guard/counter/process return bridge"],
        "negative_controls": controls,
        "claim_boundary": "Exact source/fresh ZIP and synthetic package-local observer/runtime gates only; no production VCS, tuple10, natural terminal or Formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
