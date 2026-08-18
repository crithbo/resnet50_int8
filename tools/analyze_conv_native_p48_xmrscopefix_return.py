#!/usr/bin/env python3
"""Consume the exact native-Conv p48 formal return without extracting its VCD.

The bulk waveform is parsed by ``server_tb_vcd_retention_analysis.py``.  This
companion closes identity/runtime/target-entry claims from the completed
streaming state and appends a final immutable analysis checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p48_xmrscopefix"
EXECUTION = "r1786704774390782459_2297616"
ATTEMPT = "a0"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p48_xmrscopefix_r1786704774390782459_2297616_return.zip"
)
OUT = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_return_analysis_"
    + EXECUTION
)
PENDING = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE}.zip"
)


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    names = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(names) != 1:
        raise RuntimeError(f"expected one {suffix}, found {names}")
    value = json.loads(archive.read(names[0]))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {suffix}")
    return value


def member_name(archive: zipfile.ZipFile, suffix: str) -> str:
    names = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(names) != 1:
        raise RuntimeError(f"expected one {suffix}, found {names}")
    return names[0]


def member_identities(archive: zipfile.ZipFile) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        digest = hashlib.sha256()
        size = 0
        with archive.open(info) as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        result[info.filename] = {
            "path": info.filename,
            "bytes": size,
            "sha256": digest.hexdigest(),
            "crc32": f"{info.CRC:08x}",
        }
    return result


def normalized_scope(text: str) -> str:
    # VCD escaped identifiers keep a leading backslash and optional trailing
    # whitespace.  Catalog paths use the source spelling.
    return ".".join(part.lstrip("\\").strip() for part in text.split("."))


def vcd_header_map(
    archive: zipfile.ZipFile, vcd_name: str
) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    scopes: list[str] = []
    by_path: dict[str, list[dict[str, Any]]] = {}
    timescale: str | None = None
    pending_timescale = False
    timescale_rows: list[str] = []
    with archive.open(vcd_name) as stream:
        for raw in stream:
            line = raw.decode("utf-8", "replace").strip()
            if pending_timescale:
                if line == "$end":
                    timescale = " ".join(timescale_rows).strip()
                    pending_timescale = False
                elif line:
                    timescale_rows.append(line)
                continue
            if line.startswith("$timescale"):
                body = line.removeprefix("$timescale").replace("$end", "").strip()
                if body:
                    timescale = body
                else:
                    pending_timescale = True
                    timescale_rows = []
            elif line.startswith("$scope "):
                fields = line.split()
                if len(fields) >= 4:
                    scopes.append(fields[2])
            elif line.startswith("$upscope"):
                if scopes:
                    scopes.pop()
            elif line.startswith("$var "):
                fields = line.split()
                if len(fields) >= 6:
                    reference = " ".join(fields[4:-1])
                    path = normalized_scope(".".join([*scopes, reference]))
                    by_path.setdefault(path, []).append(
                        {
                            "code": fields[3],
                            "width_bits": int(fields[2]),
                            "reference": reference,
                        }
                    )
            elif line.startswith("$enddefinitions"):
                break
    return by_path, timescale


def manifest_entry_errors(
    core: dict[str, Any], identities: dict[str, dict[str, Any]]
) -> list[str]:
    entries = core.get("core_entry_receipts")
    if not isinstance(entries, list):
        entries = core.get("entries")
    if not isinstance(entries, list):
        entries = core.get("core_entries")
    if not isinstance(entries, list):
        return ["return core manifest has no entries list"]
    errors: list[str] = []
    root = f"{PACKAGE}_return/"
    for row in entries:
        if not isinstance(row, dict):
            errors.append("non-object core entry")
            continue
        relative = row.get("archive") or row.get("path")
        if not isinstance(relative, str):
            continue
        name = relative if relative.startswith(root) else root + relative
        actual = identities.get(name)
        if row.get("required") is True and actual is None:
            errors.append(f"missing required core member: {relative}")
            continue
        if actual is None:
            continue
        expected_size = row.get("bytes") or row.get("size_bytes")
        expected_sha = row.get("sha256")
        if isinstance(expected_size, int) and actual["bytes"] != expected_size:
            errors.append(f"core size mismatch: {relative}")
        if isinstance(expected_sha, str) and actual["sha256"] != expected_sha:
            errors.append(f"core SHA mismatch: {relative}")
    return errors


def target_signal_summary(
    state: dict[str, Any], header: dict[str, list[dict[str, Any]]], contract: dict[str, Any]
) -> dict[str, Any]:
    summaries = state.get("signal_summaries", {})
    rows: dict[str, Any] = {}
    for signal in contract.get("signals", []):
        if not isinstance(signal, dict):
            continue
        sid = signal.get("signal_id")
        hierarchy = normalized_scope(str(signal.get("exact_hierarchy", "")))
        matches = header.get(hierarchy, [])
        rows[str(sid)] = {
            "exact_hierarchy": signal.get("exact_hierarchy"),
            "header_matches": matches,
            "summaries": [summaries.get(item["code"]) for item in matches],
        }
    return rows


def contains_one(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    for key in ("first_value", "last_value"):
        value = summary.get(key)
        if isinstance(value, str) and "1" in value.lower():
            return True
    return int(summary.get("transitions", 0)) > 1 and not bool(summary.get("xz_transitions"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--analysis-dir", type=Path, default=OUT)
    args = parser.parse_args()
    result_zip = args.return_zip.resolve()
    out = args.analysis_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "analysis_state.json"
    checkpoints_path = out / "checkpoints.jsonl"
    report_path = out / "report.md"
    if not state_path.is_file() or not checkpoints_path.is_file() or not report_path.is_file():
        raise RuntimeError("bounded streaming/resume artifacts are incomplete")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "EOF_REACHED":
        raise RuntimeError("streaming VCD scan has not reached EOF")

    with zipfile.ZipFile(result_zip) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        duplicate_names = sorted({name for name in names if names.count(name) > 1})
        identities = member_identities(archive)
        core = load_json(archive, "/RETURN_CORE_MANIFEST.json")
        core_status = load_json(archive, "/return_core/RETURN_CORE_STATUS.json")
        actual = load_json(archive, "/evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        compile_core = load_json(archive, "/evidence/compile_rootcause/COMPILE_CORE.json")
        sim_exit = load_json(archive, "/evidence/SIM_EXIT_RECEIPT.json")
        process = load_json(archive, "/evidence/PROCESS_TREE_RECEIPT.json")
        runtime = load_json(archive, "/evidence/TB_VCD_RUNTIME_RECEIPT.json")
        runtime_request = load_json(archive, "/evidence/TB_VCD_RUNTIME_REQUEST.json")
        safety = load_json(archive, "/evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json")
        stop = load_json(archive, "/evidence/TB_VCD_STOP_RECEIPT.json")
        vcd_identity = load_json(archive, "/evidence/TB_VCD_IDENTITY.json")
        root_identity = load_json(archive, "/evidence/PUBLISHED_ACTUAL_ROOT_IDENTITY.json")
        contract = load_json(archive, "/evidence/server_tb_vcd_bounded_causal_cone_contract.json")
        returned_manifest_name = member_name(archive, "/evidence/returned_package_manifest.json")
        returned_manifest = archive.read(returned_manifest_name)
        vcd_name = member_name(archive, "/runs/c0/native_mse4_causal.vcd")
        sim_name = member_name(archive, "/runs/c0/sim.log")
        header, header_timescale = vcd_header_map(archive, vcd_name)
        sim_text = archive.read(sim_name).decode("utf-8", "replace")

    pending_manifest_equal = False
    pending_identity: dict[str, Any] | None = None
    if PENDING.is_file():
        with zipfile.ZipFile(PENDING) as package_archive:
            package_manifest_name = member_name(package_archive, "/package_manifest.json")
            pending_manifest_equal = package_archive.read(package_manifest_name) == returned_manifest
        pending_identity = {
            "path": PENDING.relative_to(ROOT).as_posix(),
            "bytes": PENDING.stat().st_size,
            "sha256": sha_file(PENDING),
        }

    signal_rows = target_signal_summary(state, header, contract)
    key_ids = [
        "sig_mse_enable",
        "sig_wr_data_chl_req_valid",
        "sig_mse2mem_request_valid",
        "sig_mse2mem_wdata_valid",
        "sig_mem_ag_ob_chl_vld",
        "sig_wr_chl_ob_vld",
        "sig_transaction_finish",
        "sig_slice_cmpt_finish",
        "sig_sem_cs",
    ]
    key_activity: dict[str, Any] = {}
    for sid in key_ids:
        row = signal_rows.get(sid, {})
        summaries = [item for item in row.get("summaries", []) if isinstance(item, dict)]
        key_activity[sid] = {
            "header_match_count": len(row.get("header_matches", [])),
            "observed_one": any(contains_one(item) for item in summaries),
            "summaries": summaries,
        }

    target_entry = any(
        key_activity.get(sid, {}).get("observed_one") is True
        for sid in (
            "sig_mse_enable",
            "sig_wr_data_chl_req_valid",
            "sig_mse2mem_request_valid",
            "sig_mse2mem_wdata_valid",
            "sig_mem_ag_ob_chl_vld",
            "sig_wr_chl_ob_vld",
        )
    )
    pass_transfers = len(re.findall(r"\*\*\* PASS: Continuous transfer completed successfully!", sim_text))
    matrix_loads = [int(value) for value in re.findall(r"JSON: Loading matrix\[(\d+)\]", sim_text)]
    write_bursts_last = [int(value) for value in re.findall(r"\[Write Burst (\d+)\].*", sim_text)]
    vcd_info = identities[vcd_name]
    runtime_samples = runtime_request.get("samples", [])
    sample_projection = [
        {
            "seq": row.get("seq"),
            "wall_seconds": row.get("wall_seconds"),
            "sim_time_ticks": row.get("sim_time_ticks"),
            "vcd_bytes": row.get("vcd_bytes"),
            "disk_space_ok": row.get("disk_space_ok"),
            "write_ok": row.get("write_ok"),
            "quota_ok": row.get("quota_ok"),
            "exit_code": row.get("exit_code"),
        }
        for row in runtime_samples
        if isinstance(row, dict)
    ]
    identities_ok = bool(
        roots == {f"{PACKAGE}_return"}
        and not unsafe
        and not duplicate_names
        and core.get("package_id") == PACKAGE
        and core.get("execution_id") == EXECUTION
        and core.get("attempt_id") in (None, ATTEMPT)
        and actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
        and compile_core.get("package_id") == PACKAGE
        and compile_core.get("execution_id") == EXECUTION
        and pending_manifest_equal
    )
    core_errors = manifest_entry_errors(core, identities)
    runtime_false_freeze = bool(
        safety.get("stop_reason") == "SIM_TIME_FREEZE"
        and state.get("last_sim_time") == 303_783_125
        and len(runtime_samples) >= 4
        and all(
            int(runtime_samples[index].get("vcd_bytes", 0))
            > int(runtime_samples[index - 1].get("vcd_bytes", 0))
            for index in range(1, 4)
        )
        and all(
            runtime_samples[index].get("sim_time_ticks")
            == runtime_samples[index - 1].get("sim_time_ticks")
            for index in range(2, 4)
        )
    )
    qadd_like = bool(
        compile_core.get("compile_exit") == 0
        and sim_exit.get("simulation_started") is True
        and sim_exit.get("exit_code") == 124
        and runtime_false_freeze
        and not target_entry
        and stop.get("natural_terminal") is False
    )
    incomplete_finalization = bool(
        process.get("process_tree_reaped") is not True
        or stop.get("markers", {}).get("flush", {}).get("closed") is not True
        or runtime.get("diagnostic_status") != "DIAGNOSTIC_EVIDENCE_COMPLETE"
    )

    analysis = {
        "schema": "conv-native-p48-formal-return-analysis-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "return_identity": {
            "path": str(result_zip),
            "bytes": result_zip.stat().st_size,
            "sha256": sha_file(result_zip),
            "member_count": len(identities),
            "root": next(iter(roots)) if len(roots) == 1 else None,
            "safe_paths": not unsafe,
            "duplicate_names": duplicate_names,
            "core_manifest_identity_errors": core_errors,
            "package_execution_attempt_identity_pass": identities_ok,
            "returned_package_manifest_matches_pending": pending_manifest_equal,
            "pending_package": pending_identity,
        },
        "streaming_analysis": {
            "status": state.get("status"),
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_vcd_timestamp_ticks": state.get("last_sim_time"),
            "timescale": state.get("timescale"),
            "header_timescale": header_timescale,
            "checkpoint_count_before_formal_close": state.get("checkpoint_count"),
            "vcd_identity": vcd_info,
        },
        "execution": {
            "compile_exit": compile_core.get("compile_exit"),
            "production_compile_passed": compile_core.get("compile_exit") == 0,
            "simulation_started": sim_exit.get("simulation_started") is True,
            "sim_exit": sim_exit.get("exit_code"),
            "timed_out": sim_exit.get("timed_out") is True,
            "target_entry_observed": target_entry,
            "natural_terminal": stop.get("natural_terminal") is True,
            "formal_D": "UNPROVEN",
            "E3": "UNPROVEN_TARGET_NOT_ENTERED",
            "E4": "UNPROVEN_NON_NATURAL_PARTIAL_RETURN",
            "E5": "UNPROVEN_NON_NATURAL_PARTIAL_RETURN",
            "published_root": root_identity.get("published_root"),
            "actual_root": root_identity.get("actual_root"),
            "execution_root_match": root_identity.get("match") is True,
            "execution_root_classification": root_identity.get("mismatch_classification"),
        },
        "mid_run_exit_audit": {
            "qadd_v63_like_false_exit": qadd_like,
            "classification": "PACKAGE_LOCAL_TBVCD_FALSE_FREEZE_RUNTIME_ESCAPE",
            "appended_vcd_timestamp_progressed": state.get("last_sim_time", 0) > 0,
            "display_heartbeat_stale": all(
                row.get("sim_time_ticks") == 625 for row in runtime_samples[1:]
            ),
            "runtime_samples": sample_projection,
            "freeze_watchdog_used_non_authoritative_display_time": runtime_false_freeze,
            "wall_exit": False,
            "vcd_size_exit": False,
            "return_projection_exit": False,
            "disk_exit": False,
            "write_exit": False,
            "quota_exit": False,
            "external_signal_exit": process.get("received_signal") is not None,
            "dump_closed_flushed": stop.get("markers", {}).get("flush", {}).get("closed") is True,
            "process_tree_reaped": process.get("process_tree_reaped") is True,
            "finalization_incomplete": incomplete_finalization,
        },
        "causal_analysis": {
            "pre_target_preload_transfers_completed": pass_transfers,
            "highest_matrix_load_index_started": max(matrix_loads) if matrix_loads else None,
            "last_visible_write_burst_index": write_bursts_last[-1] if write_bursts_last else None,
            "target_signal_activity": key_activity,
            "LAST_PROVEN_GOOD": (
                "Production compile passed the p47 XMR repair; simulation and VCD advanced through "
                "303783125 ps, completing 32 preload transfers and starting matrix[33]."
            ),
            "FIRST_DIVERGENCE": (
                "The package-local watchdog declared SIM_TIME_FREEZE from stale display time=625 "
                "while appended VCD timestamps and bytes were still advancing; MSE4 target entry had not occurred."
            ),
            "root_classification": "PACKAGE_RUNTIME_DIAGNOSTIC_IMPLEMENTATION_ERROR",
            "narrowing_vs_p46": (
                "No additional DUT-root narrowing beyond p46: p48 never reached p46's accepted descriptor/buffer/"
                "MemAG/wdata region. It only proves production compile beyond p47's three XMR sites and identifies "
                "the package-local false-freeze/reap/flush defect."
            ),
            "fifo_outstanding_last_fsm_drain_finish_disposition": "NOT_EXECUTED_IN_P48",
        },
        "disposition": {
            "status": "FRESH_SUCCESSOR_REQUIRED",
            "successor_scope": [
                "fresh identity",
                "exact catalog signal-only dump",
                "appended VCD timestamp supervision",
                "unsigned 64-bit 16384-cycle heartbeat",
                "partial/flush/reap/exact-set return hardening",
            ],
            "frozen": [
                "config",
                "numeric",
                "workload",
                "golden",
                "functional RTL",
                "p42 vector predicate",
                "MSE4 causal target",
            ],
            "server_actions_performed": [],
        },
        "claim_boundary": (
            "The exact return proves compile success, simulation/VCD progress and a package-local false freeze before "
            "target entry. It does not establish a native Conv DUT root, natural terminal, formal-D, E3, E4 or E5."
        ),
        "conflicts": [],
        "pass": identities_ok and not core_errors and qadd_like,
        "errors": ([] if identities_ok else ["identity conjunction failed"])
        + core_errors
        + ([] if qadd_like else ["false-freeze classification conjunction failed"]),
    }

    audit = {
        "schema": "conv-native-package-build-failure-rule-audit-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "trigger": (
            "Two consecutive fresh server attempts failed to execute the frozen target: p47 package-local dump XMR "
            "compile failure, then p48 package-local stale-heartbeat false freeze before MSE4 entry."
        ),
        "attempts": [
            {
                "package_id": "r5_n4_0cc_p47_tbvcdcone",
                "failure": "three nonexistent dump-only MSE_INST[5..7] XMRE references",
                "target_executed": False,
                "current_gate_coverage": "exact catalog signal-only dump plus full HDL/scope negative control",
            },
            {
                "package_id": PACKAGE,
                "failure": "display-heartbeat false freeze while appended VCD timestamp advanced",
                "target_executed": False,
                "current_gate_coverage": (
                    "package-release-admission-and-tbvcd-runtime-v2 requires appended timestamps, unsigned 64-bit "
                    "16384-cycle heartbeat, exact dump set, target-entry binding and partial/flush/reap fail-closed"
                ),
            },
        ],
        "current_rules_sufficient": True,
        "rule_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "shared_rule_change_required": False,
        "successor_requirements": [
            "apply every current runtime-v2 requirement",
            "run exact-final-ZIP and current-epoch first-fresh negative controls",
            "bind this audit before third server attempt",
        ],
        "server_actions_performed": [],
        "claim_boundary": (
            "Audit confirms current-disk gates cover both isolated package implementation errors; it does not claim "
            "successor production execution or any DUT result."
        ),
        "pass": True,
        "errors": [],
    }

    analysis_path = out / "formal_return_analysis.json"
    audit_path = out / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    analysis_path.write_text(canonical(analysis), encoding="utf-8", newline="\n")
    audit_path.write_text(canonical(audit), encoding="utf-8", newline="\n")

    existing = checkpoints_path.read_text(encoding="utf-8").splitlines()
    event = "FORMAL_RETURN_ANALYSIS_COMPLETE"
    if not any(f'"event": "{event}"' in line or f'"event":"{event}"' in line for line in existing):
        checkpoint = {
            "schema": "server-tb-vcd-retention-analysis-checkpoint-v1",
            "seq": len(existing),
            "event": event,
            "byte_offset": state.get("byte_offset"),
            "line_number": state.get("line_number"),
            "last_sim_time": state.get("last_sim_time"),
            "analysis_sha256": sha_file(analysis_path),
            "disposition": analysis["disposition"]["status"],
        }
        with checkpoints_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, ensure_ascii=False, sort_keys=True) + "\n")
        state["checkpoint_count"] = int(state.get("checkpoint_count", len(existing))) + 1
    state["formal_analysis"] = {
        "path": analysis_path.name,
        "sha256": sha_file(analysis_path),
        "status": analysis["disposition"]["status"],
        "target_entry_observed": target_entry,
        "rule_audit_disposition": audit["rule_disposition"],
    }
    state_path.write_text(canonical(state), encoding="utf-8", newline="\n")
    current_report = report_path.read_text(encoding="utf-8")
    if "## Formal p48 close" not in current_report:
        with report_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(
            "\n## Formal p48 close\n\n"
            "- identity/core integrity: `PASS`\n"
            "- compile: `0`; simulation started: `true`; simulator/supervisor exit: `124`\n"
            "- appended VCD time: `303783125 ps`; target entry: `false`\n"
            "- classification: `PACKAGE_LOCAL_TBVCD_FALSE_FREEZE_RUNTIME_ESCAPE`\n"
            "- finalization: `PARTIAL / DIAGNOSTIC_EVIDENCE_INCOMPLETE` (not flushed/closed and not fully reaped)\n"
            "- root narrowing versus p46: none; p48 stopped during matrix preload before MSE4 execution\n"
            "- audit: `PACKAGE_BUILD_FAILURE_RULE_AUDIT = RULE_CONFIRMATION_NO_CHANGE`\n"
                "- disposition: `FRESH_SUCCESSOR_REQUIRED`\n"
            )
    print(
        json.dumps(
            {
                "pass": analysis["pass"],
                "target_entry": target_entry,
                "qadd_v63_like": qadd_like,
                "analysis": str(analysis_path),
                "audit": str(audit_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
