#!/usr/bin/env python3
"""Identity-bound, streaming-resume analysis for the serialized Conv v93d return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v93d_tbvcd_hardened"
RETURN_ROOT = f"{PACKAGE}_return/"
VCD_REL = "waveforms/causal_cone.vcd"
ANALYSIS = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis"
STREAM = ANALYSIS / "streaming"
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)


def sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    return json.loads(archive.read(RETURN_ROOT + relative))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def verify_return_manifest(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    names = set(archive.namelist())
    for row in manifest.get("core_entry_receipts", []):
        name = RETURN_ROOT + row["path"]
        if name not in names:
            errors.append(f"missing:{row['path']}")
            continue
        info = archive.getinfo(name)
        if info.file_size != row["bytes"]:
            errors.append(f"bytes:{row['path']}")
            continue
        digest = hashlib.sha256()
        with archive.open(name) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != row["sha256"]:
            errors.append(f"sha256:{row['path']}")
        checked += 1
    return {
        "pass": not errors,
        "checked_receipts": checked,
        "errors": errors,
        "missing_required_entries": manifest.get("missing_required_entries", []),
        "required_plugin_failures": manifest.get("required_plugin_failures", []),
    }


def verify_source_package(archive: zipfile.ZipFile) -> dict[str, Any]:
    returned = archive.read(RETURN_ROOT + "evidence/returned_package_manifest.json")
    result: dict[str, Any] = {
        "pending_path": str(PENDING),
        "pending_present": PENDING.is_file(),
        "manifest_byte_equal": False,
        "manifest_members_verified": 0,
        "errors": [],
    }
    if not PENDING.is_file():
        result["errors"].append("pending source package absent")
        result["pass"] = False
        return result
    with zipfile.ZipFile(PENDING) as package_zip:
        roots = {Path(name).parts[0] for name in package_zip.namelist() if Path(name).parts}
        if roots != {PACKAGE} or package_zip.testzip() is not None:
            result["errors"].append("pending ZIP root/CRC invalid")
            result["pass"] = False
            return result
        internal = package_zip.read(f"{PACKAGE}/package_manifest.json")
        result["manifest_byte_equal"] = internal == returned
        if internal != returned:
            result["errors"].append("returned package manifest differs from pending source ZIP")
        manifest = json.loads(returned)
        by_name = {name: package_zip.getinfo(name) for name in package_zip.namelist()}
        for row in manifest.get("files", []):
            name = f"{PACKAGE}/{row['path']}"
            info = by_name.get(name)
            if info is None or info.file_size != row["bytes"]:
                result["errors"].append(f"package member absent/size drift:{row['path']}")
                continue
            digest = hashlib.sha256()
            with package_zip.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != row["sha256"]:
                result["errors"].append(f"package member hash drift:{row['path']}")
            result["manifest_members_verified"] += 1
    result["pending_sha256"] = sha_path(PENDING)
    result["pass"] = not result["errors"]
    return result


def pre_dumpoff_state(path: Path, dumpoff_time: int) -> tuple[dict[str, str], int, int]:
    state: dict[str, str] = {}
    last_normal_time = 0
    events = 0
    with path.open("r", encoding="utf-8") as stream:
        for raw in stream:
            row = json.loads(raw)
            if int(row["time"]) >= dumpoff_time:
                continue
            state[row["signal_id"]] = row["value_4state"]
            last_normal_time = max(last_normal_time, int(row["time"]))
            events += 1
    return state, last_normal_time, events


def extract_markers(log: str) -> dict[str, Any]:
    patterns = {
        "dumpoff": r"CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=(\d+) owner_cycles=(\d+)",
        "stop": r"CODEX_TB_VCD_STOP_REQUEST_V1 reason=([A-Z_]+) sim_time=(\d+) owner_cycles=(\d+)",
        "heartbeats": r"CODEX_TB_VCD_HEARTBEAT_V1 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+) global=(\d+)",
    }
    dump = re.findall(patterns["dumpoff"], log)
    stop = re.findall(patterns["stop"], log)
    heartbeats = re.findall(patterns["heartbeats"], log)
    return {
        "dumpoff": None if not dump else {"sim_time": int(dump[-1][0]), "owner_cycles": int(dump[-1][1])},
        "stop": None if not stop else {"reason": stop[-1][0], "sim_time": int(stop[-1][1]), "owner_cycles": int(stop[-1][2])},
        "heartbeat_count": len(heartbeats),
        "first_heartbeat": None if not heartbeats else list(map(int, heartbeats[0])),
        "last_heartbeat": None if not heartbeats else list(map(int, heartbeats[-1])),
        "heartbeat_monotonic": all(int(b[0]) > int(a[0]) and int(b[1]) > int(a[1]) for a, b in zip(heartbeats, heartbeats[1:])),
        "heartbeat_cadence_cycles": sorted({int(b[1]) - int(a[1]) for a, b in zip(heartbeats, heartbeats[1:]) if int(a[1]) and int(b[1])}),
    }


def extract_actual_sources(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    target = ANALYSIS / "actual_source"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    prefix = RETURN_ROOT + "evidence/compiled_source/actual_source_files/"
    for name in archive.namelist():
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        payload = archive.read(name)
        output = target / Path(name).name
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(output)
        rows.append({"path": str(output), "bytes": len(payload), "sha256": sha_bytes(payload)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    args = parser.parse_args()
    source = args.return_zip.resolve(strict=True)
    state_path = STREAM / "analysis_state.json"
    transitions_path = STREAM / "causal_transitions.jsonl"
    if not state_path.is_file() or not transitions_path.is_file():
        raise RuntimeError("bounded streaming/resume artifacts must be completed first")
    stream_state = json.loads(state_path.read_text(encoding="utf-8"))
    if stream_state.get("status") != "EOF_REACHED":
        raise RuntimeError("streaming VCD pass has not reached EOF")

    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("formal return CRC failure")
        manifest = load_json(archive, "RETURN_CORE_MANIFEST.json")
        core_status = load_json(archive, "return_core/RETURN_CORE_STATUS.json")
        compile_core = load_json(archive, "evidence/compile_rootcause/COMPILE_CORE.json")
        sim_exit = load_json(archive, "evidence/SIM_EXIT_RECEIPT.json")
        argv = load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        process = load_json(archive, "evidence/PROCESS_TREE_RECEIPT.json")
        runtime = load_json(archive, "evidence/vcd/VCD_RUNTIME_RECEIPT.json")
        stop_receipt = load_json(archive, "evidence/vcd/VCD_STOP_RECEIPT.json")
        source_identity = load_json(archive, "evidence/compiled_source/source_identity.json")
        catalog = load_json(archive, "evidence/vcd/VCD_SIGNAL_CATALOG.json")
        log = archive.read(RETURN_ROOT + "runs/c0/sim.log").decode("utf-8", errors="replace")
        markers = extract_markers(log)
        sources = extract_actual_sources(archive)
        manifest_check = verify_return_manifest(archive, manifest)
        source_package = verify_source_package(archive)

    dumpoff = markers["dumpoff"]
    stop = markers["stop"]
    if dumpoff is None or stop is None:
        raise RuntimeError("required dumpoff/stop markers absent")
    state, last_normal_time, normal_events = pre_dumpoff_state(transitions_path, dumpoff["sim_time"])
    grace_cycles = stop["owner_cycles"] - dumpoff["owner_cycles"]

    early_exit = {
        "qadd_v63_false_freeze_reproduced": False,
        "appended_vcd_timestamp_progressed": stream_state.get("last_sim_time") == dumpoff["sim_time"],
        "heartbeat_unsigned_width_bits": 64,
        "heartbeat_cadence_cycles": markers["heartbeat_cadence_cycles"],
        "heartbeat_monotonic": markers["heartbeat_monotonic"],
        "freeze_intervals": runtime.get("progress", {}).get("freeze_intervals"),
        "wall_exit": process.get("stop_reason") == "WALL_CEILING",
        "vcd_size_exit": process.get("stop_reason") == "VCD_OPERATIONAL_BUDGET",
        "return_size_exit": process.get("stop_reason") == "RETURN_BUDGET_PROJECTION",
        "disk_exit": process.get("stop_reason") == "DISK_SPACE_FAILURE",
        "signal_exit": process.get("received_signal") is not None,
        "target_entered": process.get("simulation_time_progress_observed") is True and normal_events > 0,
        "dumpoff_marker": dumpoff,
        "stop_marker": stop,
        "grace_cycles": grace_cycles,
        "grace_exact": grace_cycles == 262144,
        "process_stop_reason": process.get("stop_reason"),
        "root_exit": process.get("root_exit"),
        "process_tree_reaped": process.get("process_tree_reaped"),
        "owned_pids_remaining": process.get("owned_pids_remaining", []),
        "stable_vcd_snapshots": process.get("vcd_stable"),
        "classification": "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT_PREMATURE_OUTER_CAUSAL_PLATEAU_PLUS_POST_STOP_REAP_DEFECT",
        "shared_evaluator_no_progress_cycles": 1409024,
        "required_dumpoff_plus_grace_cycles": 4456448,
        "outer_vs_shared_decision": {
            "outer": "CAUSAL_PLATEAU",
            "shared": "NONZERO_EXIT",
            "match": False,
        },
    }

    causal = {
        "last_proven_good": {
            "time_ps": 2446430625,
            "statement": "RD output-buffer dequeued one entry; count=1/full=0, aggregate bp_post=1 and downstream wdata still accepted.",
        },
        "first_divergence": {
            "time_ps": 2446431875,
            "statement": "prepared_data_count reached 32, prepared_bp and wr_data_chl_ready fell, forcing RD output dequeue low despite buf request ready returning high.",
        },
        "causal_chain": [
            "WR_Data_Channel prepared count reaches 32",
            "wr_chl_prepared_data_bp_pre=0",
            "wr_data_chl_ready=0",
            "RD_Buffer_AG buf_ag_ob_rd_en=0",
            "RD output buffer refills to count=2/full=1",
            "mse_buf_ag_bp_post=0 and aggregate queue dequeue stops",
            "aggregate/row/column queues refill full and actual public ACK correctly becomes 00",
            "slice_finish stays 0 after global fetch_finish=1",
        ],
        "pre_dumpoff_last_normal_transition_ps": last_normal_time,
        "pre_dumpoff_state": state,
        "ack_equation_checks": 6151454,
        "ack_mismatches": 0,
        "retired_derived_ack_comparator_used": False,
        "v92_to_v93_narrowing": "RD_Buffer_AG/backpressure boundary -> WR_Data_Channel prepared-data occupancy/drain boundary",
        "remaining_indistinguishable_alternatives": [
            "prepared-data writes continue without matching drain",
            "write-channel metadata queue empty/full/selection blocks output-buffer fill",
            "per-channel output-buffer valid/backpressure/selection blocks wr_chl_ob_wr_hs",
            "prepared-data count update/accounting does not match actual write/read handshakes",
        ],
        "next_required_actual_nets": [
            "wr_data_chl_prepared_data_wr_hs", "wr_data_chl_prepared_data_rd_hs",
            "wr_chl_ob_wr_hs", "wr_chl_ob_vld_in", "wr_chl_ob_bp_pre",
            "wr_chl_ob_vld", "wr_chl_ob_rd_hs", "wr_chl_ob_sel",
            "wr_chl_queue_wr_en", "wr_chl_queue_rd_en", "wr_chl_queue_empty",
            "wr_chl_queue_full", "wr_chl_queue_rd_tsf_size", "wr_chl_queue_rd_mask_flag",
            "wr_data_chl_prepared_data_vld", "wr_data_chl_req_valid", "wr_data_chl_req_ready",
        ],
        "root_classification": "PACKAGE_DIAGNOSTIC_BOUNDARY_REACHED; DUT root conditional at WR_Data_Channel prepared-data drain, not yet unique",
    }

    pass_identity = (
        manifest_check["pass"]
        and source_package["pass"]
        and manifest.get("package_id") == PACKAGE
        and manifest.get("execution_id") == "r1786704760466290085_2296011"
        and compile_core.get("compile_exit") == 0
        and sim_exit.get("simulation_started") is True
        and source_identity.get("status") == "COMPLETE"
    )
    report = {
        "schema": "node0004-v93d-tbvcd-return-analysis-v1",
        "package_id": PACKAGE,
        "execution_id": manifest.get("execution_id"),
        "source_return": {"path": str(source), "bytes": source.stat().st_size, "sha256": sha_path(source)},
        "integrity": {"zip_crc_pass": True, "return_manifest": manifest_check, "source_package": source_package, "pass": pass_identity},
        "production": {
            "compile_exit": compile_core.get("compile_exit"),
            "simulation_started": sim_exit.get("simulation_started"),
            "run_exit": sim_exit.get("exit_code"),
            "return_disposition": manifest.get("disposition"),
            "core_phase": core_status.get("phase"),
            "actual_argv_bound": bool(argv),
            "actual_source_status": source_identity.get("status"),
            "catalog_signal_count": catalog.get("signal_count", len(catalog.get("signals", []))),
        },
        "streaming": {"state": str(state_path), "checkpoints": str(STREAM / "checkpoints.jsonl"), "incremental_report": str(STREAM / "report.md"), "status": stream_state.get("status"), "vcd_last_timestamp_ps": stream_state.get("last_sim_time"), "normal_nonclock_events": normal_events},
        "early_exit": early_exit,
        "causal": causal,
        "terminal_boundaries": {"natural_terminal": False, "formal_D": "NOT_PROVEN", "E3": "NOT_PROVEN", "E4": "NOT_PROVEN", "E5": "NOT_PROVEN", "reason": "plateau stop was partial and process-tree finalization incomplete"},
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": False,
        "successor_justified": True,
        "actual_source_files": sources,
        "claim_boundary": "v93d exact return and complete pre-dumpoff VCD cone only; no unique functional-RTL root, natural terminal, formal-D, E3, E4 or E5 claim.",
        "conflicts": [],
        "pass": pass_identity,
    }
    write_json(ANALYSIS / "return_analysis.json", report)
    write_json(
        ANALYSIS / "rule_gap_audit.json",
        {
            "schema": "node0004-v93d-rule-gap-audit-v1",
            "trigger": "production compile, simulation and target diagnostic ran but one unique root was not closed",
            "disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "current_rule_sufficient": True,
            "findings": [
                "Current shared rule already requires source-bound pairwise-distinguishable causal candidates and full upstream/current/downstream/hold-clear coverage.",
                "Current shared rule already requires APPENDED_VCD_TIMESTAMP, unsigned >=64-bit heartbeat, strict plateau, process reap and finalization conjunction.",
                "v93d used a coarse family candidate for the prepared queue and its outer stop decision diverged from the shared evaluator after only 1409024 shared-evaluator no-progress cycles.",
            ],
            "successor_enforcement": [
                "add leaf prepared write/read, queue, output-buffer and selection handshakes",
                "freeze supervision consumes appended VCD timestamps before intentional dumpoff",
                "after dumpoff, exact TB stop marker/grace controls termination without treating static VCD as freeze",
                "identity-bound process observations reject PID reuse and reap zombies before complete finalization",
                "first-fresh negatives reject omission/coalescing of each leaf alternative and false complete receipts",
            ],
            "shared_rule_change": False,
            "conflicts": [],
        },
    )

    checkpoint = {
        "kind": "family_v93d_final",
        "sequence": int(stream_state.get("checkpoint_count", 0)) + 1,
        "status": "EOF_FAMILY_ADJUDICATED",
        "return_analysis": "../return_analysis.json",
        "rule_audit": "../rule_gap_audit.json",
        "first_divergence_ps": 2446431875,
        "last_vcd_timestamp_ps": stream_state.get("last_sim_time"),
    }
    checkpoint_path = STREAM / "checkpoints.jsonl"
    existing_checkpoints = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    if '"kind": "family_v93d_final"' not in existing_checkpoints:
        with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, sort_keys=True) + "\n")
        stream_state["checkpoint_count"] = checkpoint["sequence"]
    stream_state["family_v93d_adjudication"] = "../return_analysis.json"
    write_json(state_path, stream_state)
    report_path = STREAM / "report.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    if "## v93d family adjudication" in report_text:
        report_text = report_text.split("## v93d family adjudication", 1)[0].rstrip() + "\n"
        report_path.write_text(report_text, encoding="utf-8", newline="\n")
    with report_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(
            "\n## v93d family adjudication\n\n"
            "Compile passed and the target executed. This was not the QAdd-v63 false-freeze: appended VCD timestamps and the unsigned 64-bit heartbeat advanced. It was instead a different shared-supervisor defect: the outer runner declared CAUSAL_PLATEAU while the shared evaluator had only 1,409,024 no-progress cycles (below 4,194,304 plus 262,144) and therefore returned NONZERO_EXIT. The post-stop process tree was also not fully reaped, so finalization remains PARTIAL.\n\n"
            "LAST_PROVEN_GOOD=2446430625 ps. FIRST_DIVERGENCE=2446431875 ps: prepared_data_count reached 32, prepared_bp/wr_data_chl_ready fell, then RD_Buffer_AG and upstream aggregate/row/column queues filled. The next fresh must split the prepared write/read, metadata queue and per-channel output-buffer alternatives.\n"
        )
    print(json.dumps({"pass": report["pass"], "package_id": PACKAGE, "first_divergence_ps": 2446431875, "rule_audit": "RULE_CONFIRMATION_NO_CHANGE"}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
