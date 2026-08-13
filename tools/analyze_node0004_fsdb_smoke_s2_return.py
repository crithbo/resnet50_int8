#!/usr/bin/env python3
"""Identity-bound analysis of the interrupted serialized Conv FSDB smoke s2 return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s2"
SUCCESSOR_ID = "r5_n4_hw_fsdbsmoke_s3"
RETURN_ROOT = f"{PACKAGE_ID}_return"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_identity(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"path": path.resolve().as_posix(), "bytes": size, "sha256": digest.hexdigest()}


def member_identity(zf: zipfile.ZipFile, member: str) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with zf.open(member) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def read_json(zf: zipfile.ZipFile, relative: str) -> dict[str, object]:
    return json.loads(zf.read(f"{RETURN_ROOT}/{relative}"))


def safe_member_errors(names: list[str]) -> list[str]:
    errors: list[str] = []
    if len(names) != len(set(names)):
        errors.append("duplicate_zip_member")
    for name in names:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            errors.append(f"unsafe_zip_member:{name}")
    roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    if roots != {RETURN_ROOT}:
        errors.append(f"return_root_mismatch:{sorted(roots)}")
    return errors


def normalized_runtime_bytes(path: Path, package_id: str) -> bytes:
    return path.read_bytes().replace(package_id.encode(), b"PACKAGE_ID")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", type=Path, required=True)
    ap.add_argument("--source-package-zip", type=Path, required=True)
    ap.add_argument("--s2-build-root", type=Path, required=True)
    ap.add_argument("--s3-build-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    integrity_errors: list[str] = []
    checks: dict[str, bool] = {}
    cached_member_identity: dict[str, dict[str, object]] = {}

    with zipfile.ZipFile(args.return_zip) as rz:
        names = rz.namelist()
        integrity_errors.extend(safe_member_errors(names))
        bad_crc = rz.testzip()
        checks["return_zip_crc_clean"] = bad_crc is None
        if bad_crc:
            integrity_errors.append(f"return_crc_failure:{bad_crc}")

        core_manifest = read_json(rz, "RETURN_CORE_MANIFEST.json")
        core_status = read_json(rz, "return_core/RETURN_CORE_STATUS.json")
        sim_exit = read_json(rz, "return_core/SIM_EXIT_RECEIPT.json")
        actual_sim_argv = read_json(rz, "evidence/actual_sim_argv.json")
        compile_argv = read_json(rz, "evidence/compile_rootcause/compile_argv.json")
        compile_sources = read_json(rz, "evidence/compile_rootcause/compile_source_identity.json")
        returned_manifest = read_json(rz, "evidence/returned_package_manifest.json")
        diagnostic = read_json(rz, "evidence/fsdb_smoke/DIAGNOSTIC_STATUS.json")
        query_binding = read_json(rz, "evidence/fsdb_smoke/FSDB_QUERY_BINDING.json")
        signal_query = read_json(rz, "evidence/fsdb_smoke/SIGNAL_QUERY_RECEIPT.json")
        time_progress = read_json(rz, "evidence/fsdb_smoke/TIME_PROGRESS_RECEIPT.json")
        waveform_receipt = read_json(rz, "waveforms/WAVEFORM_RUNTIME_RECEIPT.json")
        dump_tcl = rz.read(f"{RETURN_ROOT}/runs/c0/dump_waveform.tcl").decode("utf-8", "replace")
        sim_log = rz.read(f"{RETURN_ROOT}/runs/c0/sim.log").decode("utf-8", "replace")
        host_progress = rz.read(f"{RETURN_ROOT}/runs/c0/host_progress.log").decode("utf-8", "replace")
        compile_exit = int(rz.read(f"{RETURN_ROOT}/evidence/compile_exit_status.txt").strip())
        run_exit = int(rz.read(f"{RETURN_ROOT}/evidence/run_exit_status.txt").strip())
        signal_status = rz.read(f"{RETURN_ROOT}/evidence/signal_status.txt").decode().strip()

        receipt_mismatches: list[str] = []
        for row in core_manifest.get("core_entry_receipts", []):
            member = f"{RETURN_ROOT}/{row['path']}"
            if member not in names:
                receipt_mismatches.append(f"missing:{row['path']}")
                continue
            actual = cached_member_identity.setdefault(member, member_identity(rz, member))
            if actual["bytes"] != row.get("bytes") or actual["sha256"] != row.get("sha256"):
                receipt_mismatches.append(f"identity:{row['path']}")
        checks["all_core_and_archived_waveform_receipts_identity_match"] = not receipt_mismatches
        integrity_errors.extend(f"core_receipt_{item}" for item in receipt_mismatches)

        basename_match = re.fullmatch(
            rf"{re.escape(PACKAGE_ID)}_(r\d+_\d+)_return\.zip", args.return_zip.name
        )
        execution_id = str(sim_exit.get("execution_id", ""))
        checks["basename_execution_identity_match"] = bool(
            basename_match and basename_match.group(1) == execution_id
        )
        checks["package_execution_identity_consistent"] = all(
            item.get("package_id") == PACKAGE_ID and item.get("execution_id") == execution_id
            for item in (core_manifest, core_status, sim_exit, waveform_receipt, query_binding, signal_query, time_progress)
        )

        manifest_rows = {row.get("path"): row for row in returned_manifest.get("files", [])}
        source_rows = {row.get("path"): row for row in compile_sources.get("selected_sources", [])}

        archive_wave_rows = {
            row["path"].removeprefix("waveforms/"): row
            for row in core_manifest.get("waveform_entry_receipts", [])
            if row.get("kind") == "waveform_fsdb"
        }
        declared_wave_rows = {row["source_path"]: row for row in waveform_receipt.get("waveforms", [])}
        waveform_identity_drift: list[dict[str, object]] = []
        for path in sorted(set(archive_wave_rows) | set(declared_wave_rows)):
            declared = declared_wave_rows.get(path)
            archived = archive_wave_rows.get(path)
            if (
                declared is None
                or archived is None
                or declared.get("bytes") != archived.get("bytes")
                or declared.get("sha256") != archived.get("sha256")
            ):
                waveform_identity_drift.append(
                    {
                        "path": path,
                        "declared_bytes": None if declared is None else declared.get("bytes"),
                        "declared_sha256": None if declared is None else declared.get("sha256"),
                        "archived_bytes": None if archived is None else archived.get("bytes"),
                        "archived_sha256": None if archived is None else archived.get("sha256"),
                    }
                )

    with zipfile.ZipFile(args.source_package_zip) as pz:
        source_names = set(pz.namelist())
        checks["source_package_zip_crc_clean"] = pz.testzip() is None
        package_manifest_mismatches: list[str] = []
        for relative, row in manifest_rows.items():
            member = f"{PACKAGE_ID}/{relative}"
            if member not in source_names:
                package_manifest_mismatches.append(f"missing:{relative}")
                continue
            actual = member_identity(pz, member)
            if actual["bytes"] != row.get("bytes") or actual["sha256"] != row.get("sha256"):
                package_manifest_mismatches.append(f"identity:{relative}")
        checks["returned_package_manifest_matches_exact_s2_source_zip"] = not package_manifest_mismatches
        integrity_errors.extend(f"package_manifest_{item}" for item in package_manifest_mismatches)

        probe_member = f"{PACKAGE_ID}/tb_probe/fsdb_smoke_event_probe.svh"
        dump_member = f"{PACKAGE_ID}/package_tools/dump_waveform.tcl"
        probe_ident = member_identity(pz, probe_member)
        dump_ident = member_identity(pz, dump_member)
        returned_probe = source_rows.get(
            f"/home/panqs/ndp/{PACKAGE_ID}/tb_probe/fsdb_smoke_event_probe.svh", {}
        )
        returned_dump = source_rows.get(
            f"/home/panqs/ndp/{PACKAGE_ID}/package_tools/dump_waveform.tcl", {}
        )
        checks["production_compile_source_matches_exact_s2_probe"] = (
            returned_probe.get("bytes") == probe_ident["bytes"]
            and returned_probe.get("sha256") == probe_ident["sha256"]
        )
        checks["production_compile_dump_source_matches_exact_s2_package"] = (
            returned_dump.get("bytes") == dump_ident["bytes"]
            and returned_dump.get("sha256") == dump_ident["sha256"]
        )

    sim_argv = list(actual_sim_argv.get("argv", []))
    sim_argv_text = " ".join(str(token) for token in sim_argv)
    compile_tokens = list(compile_argv.get("argv", []))
    checks["production_compile_passed"] = compile_exit == 0
    checks["fsdb_only_profile_actual"] = all(
        token in sim_argv for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0")
    ) and all(token in compile_tokens for token in ("DUMP_VCD=0", "DUMP_FSDB=1", "TB_DUMP_FSDB=0"))
    checks["actual_run_used_exact_NDP_copy01_root"] = (
        "/home/panqs/ndp/NDP_copy01/install/codex_runs/" in sim_argv_text
        and "/home/panqs/ndp/NDP_copy01/install/cfg_pkg/" in sim_argv_text
    )
    checks["one_package_owned_full_hierarchy_fsdb_writer"] = (
        dump_tcl.count("fsdbDumpfile") == 1
        and "fsdbDumpvars 0 tb_NDP_Top_new_phy" in dump_tcl
        and "fsdbDumpMDA 0 tb_NDP_Top_new_phy" in dump_tcl
    )
    checks["interrupted_partial_execution_status_consistent"] = (
        run_exit == 125
        and signal_status == "INT"
        and sim_exit.get("signal") == "INT"
        and sim_exit.get("sim_started") is True
        and sim_exit.get("natural_terminal_observed") is False
        and core_manifest.get("disposition") == "PARTIAL_EXECUTION_RETURN"
    )

    events = list(signal_query.get("events", []))
    event_sequences = [row.get("sequence") for row in events]
    checks["registered_event_rows_contiguous"] = event_sequences == list(range(len(events)))
    checks["time_zero_and_time_greater_than_zero_observed"] = (
        time_progress.get("time_zero_marker") is True
        and time_progress.get("time_greater_than_zero") is True
        and any(int(row.get("time_tick", 0)) > 0 for row in events)
    )
    checks["query_and_fsdb_correctly_fail_closed"] = (
        signal_query.get("completeness") == "PARTIAL"
        and signal_query.get("capture", {}).get("flush_complete") is False
        and query_binding.get("pass") is False
        and time_progress.get("pass") is False
        and waveform_receipt.get("pass") is False
        and diagnostic.get("status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    )

    timed_lines: list[tuple[int, str]] = []
    for line in sim_log.splitlines():
        match = re.match(r"^\[(\d+)\]", line)
        if match:
            timed_lines.append((int(match.group(1)), line))
    max_tick = max((tick for tick, _ in timed_lines), default=None)
    max_tick_lines = [line for tick, line in timed_lines if tick == max_tick][-8:]
    checks["workload_loaded_and_execution_started"] = (
        "JSON config: 86 matrices loaded" in sim_log
        and "Exec_Length=69" in sim_log
        and "Reg Started." in sim_log
        and "INFO: slice start" in sim_log
    )

    progress_rows: list[dict[str, int]] = []
    for line in host_progress.splitlines():
        match = re.search(r"host_epoch=(\d+).*sim_log_bytes=(\d+)", line)
        if match:
            progress_rows.append({"host_epoch": int(match.group(1)), "sim_log_bytes": int(match.group(2))})
    last_change_index = 0
    for index in range(1, len(progress_rows)):
        if progress_rows[index]["sim_log_bytes"] != progress_rows[index - 1]["sim_log_bytes"]:
            last_change_index = index
    plateau_seconds = (
        progress_rows[-1]["host_epoch"] - progress_rows[last_change_index]["host_epoch"]
        if progress_rows else None
    )
    checks["host_log_plateau_at_least_40_minutes"] = plateau_seconds is not None and plateau_seconds >= 2400

    runtime_relatives = [
        "PREPARE_AND_RUN.sh",
        "package_tools/dump_waveform.tcl",
        "package_tools/fsdb_smoke_runtime.py",
        "package_tools/fsdb_smoke_event_parser.py",
        "tb_probe/fsdb_smoke_event_probe.svh",
    ]
    s2_s3_runtime_comparison: dict[str, bool] = {}
    for relative in runtime_relatives:
        s2_s3_runtime_comparison[relative] = normalized_runtime_bytes(
            args.s2_build_root / relative, PACKAGE_ID
        ) == normalized_runtime_bytes(args.s3_build_root / relative, SUCCESSOR_ID)
    checks["s3_runtime_is_s2_identity_normalized_equivalent"] = all(s2_s3_runtime_comparison.values())

    checks["archived_fsdb_set_present"] = len(archive_wave_rows) == 14 and "run/sim_results/wave.fsdb" in archive_wave_rows
    checks["fsdb_changed_during_interrupted_finalization"] = bool(waveform_identity_drift)
    checks["empty_lock_race_reported"] = any("wave.fsdb.lock" in str(item) for item in core_manifest.get("waveform_errors", []))

    for name, passed in checks.items():
        if not passed:
            integrity_errors.append(f"check_failed:{name}")

    report = {
        "schema": "node0004-fsdb-smoke-s2-formal-return-analysis-v1",
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE_ID,
        "execution_id": execution_id,
        "previous_version_progress": "Smoke s1 reached production VCS parsing and failed on the package-local reserved identifier; s2 corrected that compiler defect.",
        "current_version_purpose": "Determine whether s2 compiled, advanced time, produced FSDB/query evidence, and whether the observed plateau came from the actual project root or runtime/termination behavior.",
        "return_identity": file_identity(args.return_zip),
        "source_package_identity": file_identity(args.source_package_zip),
        "integrity_pass": not integrity_errors,
        "integrity_errors": integrity_errors,
        "checks": checks,
        "dynamic_result": {
            "compile_exit": compile_exit,
            "run_exit_sentinel": run_exit,
            "signal": signal_status,
            "simulation_started": sim_exit.get("sim_started"),
            "natural_terminal_observed": sim_exit.get("natural_terminal_observed"),
            "return_disposition": core_manifest.get("disposition"),
            "actual_project_root": "/home/panqs/ndp/NDP_copy01",
            "maximum_logged_simulation_tick_ps": max_tick,
            "maximum_logged_simulation_tick_lines": max_tick_lines,
            "host_progress_samples": len(progress_rows),
            "host_sim_log_plateau_seconds": plateau_seconds,
            "classification": "HIGH_CPU_ZERO_OBSERVED_SIM_TIME_PROGRESS_OR_INTERNAL_RUNTIME_STALL_AFTER_SLICE_START",
            "hard_deadlock_proven": False,
            "root_command_issue_caused_this_run": False,
        },
        "last_proven_progress": {
            "compile": "Production compile/elaboration completed with exit 0 using the exact shipped s2 probe and dump-control sources.",
            "runtime": "Simulation advanced through reset, loaded 86 matrices, programmed Exec_Length=69, started execution, issued slice start, and created the final slice27/bank3 monitor log at tick 2446091000 ps.",
            "waveform": "The package-owned full-hierarchy FSDB writer created the main wave.fsdb plus 13 returned shards, and registered events include reset deassertion at 100000 ps.",
        },
        "first_divergence": "After tick 2446091000 ps, the returned sim log contains no later simulator-time event; host_progress shows no sim-log growth for 2520 seconds before interruption, while the user's contemporaneous ps sample showed the actual simv CPU-active. This is the first observed plateau boundary, not a proven causal root.",
        "fsdb_and_query_adjudication": {
            "writer_started": True,
            "time_greater_than_zero": True,
            "registered_event_generation_and_parsing_started": True,
            "registered_event_rows": len(events),
            "registered_event_max_tick_ps": max((int(row.get("time_tick", 0)) for row in events), default=None),
            "raw_fsdb_complete": False,
            "query_complete": False,
            "binding_pass": False,
            "diagnostic_status": diagnostic.get("status"),
            "waveform_identity_drift_between_runtime_snapshot_and_archive": waveform_identity_drift,
            "boundary": "The archive is ZIP-integrity-clean and its archived bytes are bound by RETURN_CORE_MANIFEST, but it is an interrupted, mutating FSDB snapshot and does not prove a stable or semantically complete FSDB/query return.",
        },
        "publication_vs_process": {
            "return_zip_published": True,
            "server_simv_termination_proven_by_return": False,
            "reason": "The INT handler signals the timeout wrapper and immediately finalizes without waiting for the simulator process tree or FSDB writer to quiesce. Waveform identity drift during collection is direct evidence of that race.",
            "current_server_process_state": "UNKNOWN_FROM_RETURN_ZIP; requires a contemporaneous read-only process check.",
        },
        "s2_vs_s3": {
            "runtime_identity_normalized_equivalence": s2_s3_runtime_comparison,
            "s3_readme_root_correction_affects_this_s2_execution": False,
            "reason": "The actual s2 argv already used /home/panqs/ndp/NDP_copy01. s3 changes package identity/self-description but its runner, dump, runtime, parser, and probe are identity-normalized equivalent to s2.",
            "s3_required_for_current_gate": True,
            "s3_safe_to_treat_as_stall_fix": False,
            "adjudication": "The official s3 first and second clean executions remain unproven. Do not count this interrupted s2 return as either one, and do not expect the s3 README correction alone to change the plateau.",
        },
        "terminal_state": "EVIDENCE_INCOMPLETE_INTERRUPTED_RUNTIME_PLATEAU",
        "fresh_package_built": False,
        "remaining_blockers": [
            "No natural terminal or clean simulator exit.",
            "No stable complete FSDB set or complete registered-event summary/query receipt.",
            "No second sequential execution/distinct return proof.",
            "The current return cannot distinguish FSDB overhead/internal FSDB work from zero-time DUT/TB/monitor event churn after slice start.",
            "The return does not prove whether an orphaned server simv remained alive after atomic return publication.",
        ],
        "minimum_closure": [
            "Confirm no s2 simv process remains using a contemporaneous read-only process listing.",
            "Before spending another long run, mainline must adjudicate whether to add signal-handler process-tree quiescence/stable-snapshot handling and a periodic simulation-time heartbeat; s3's README-only correction does not supply either.",
            "Then obtain two clean sequential official smoke executions with stable complete FSDB/query receipts and distinct non-overwriting returns.",
        ],
        "frozen": {"functional_rtl": True, "config": True, "numeric": True, "workload": True, "golden": True},
        "server_actions_performed": [],
        "claim_boundary": "This report analyzes only the exact interrupted s2 return and package-local runtime evidence. It does not prove a hard DUT deadlock, a functional RTL defect, complete FSDB decodability, a natural terminal, or the current live state of the remote process.",
        "conflicts": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "integrity_pass": report["integrity_pass"], "terminal_state": report["terminal_state"], "output": args.output.as_posix()}, sort_keys=True))
    return 0 if report["integrity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
