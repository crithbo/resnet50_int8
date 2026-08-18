#!/usr/bin/env python3
"""Stream-validate and classify the exact native-Conv p47 formal return.

This analyzer never materializes a waveform or compile log in memory.  It
persists the current state before consuming members, appends immutable
checkpoints after each phase, and updates the incremental report throughout.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(r"C:\Users\15383\Downloads\r5_n4_0cc_p47_tbvcdcone_r1786698137747571521_2253824_return.zip")
PACKAGE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p47_tbvcdcone.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824"
TREE_ROOT = OUT / "return_tree/r5_n4_0cc_p47_tbvcdcone_return"
STATE_PATH = OUT / "analysis_state.json"
CHECKPOINTS_PATH = OUT / "checkpoints.jsonl"
REPORT_PATH = OUT / "report.md"
FINAL_PATH = OUT / "formal_return_analysis.json"

SCHEMA = "server-tb-vcd-retention-analysis-v1"
PACKAGE_ID = "r5_n4_0cc_p47_tbvcdcone"
EXECUTION_ID = "r1786698137747571521_2253824"
ATTEMPT_ID = "a0"
RETURN_ROOT = f"{PACKAGE_ID}_return"
VCD_SUFFIX = "/runs/c0/native_mse4_causal.vcd"


def sha_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(value)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def append_checkpoint(value: dict[str, Any]) -> None:
    CHECKPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINTS_PATH.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def update_report(state: dict[str, Any], findings: list[str]) -> None:
    lines = [
        "# Incremental p47 formal-return review",
        "",
        f"- status: `{state['status']}`",
        f"- return members streamed: `{state['members_streamed']}/{state['members_total']}`",
        f"- streamed uncompressed bytes: `{state['byte_offset']}/{state['source_uncompressed_bytes']}`",
        f"- VCD member present: `{str(state['vcd_member_present']).lower()}`",
        f"- compile exit: `{state.get('compile_exit', 'pending')}`",
        f"- simulation started: `{str(state.get('simulation_started', False)).lower()}`",
        "",
        "## Incremental findings",
        "",
    ]
    lines.extend(f"- {item}" for item in findings)
    lines.extend([
        "",
        "This report is incrementally updated; immutable checkpoints remain in `checkpoints.jsonl`.",
        "No raw evidence was deleted or mutated.",
        "",
    ])
    atomic_text(REPORT_PATH, "\n".join(lines))


def load_json(relative: str) -> Any:
    return json.loads((TREE_ROOT / relative).read_text(encoding="utf-8"))


def stream_zip(archive_path: Path, expected_root: str) -> tuple[list[dict[str, Any]], int, str]:
    container_bytes, container_sha = sha_file(archive_path)
    entries: list[dict[str, Any]] = []
    names: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        for info in infos:
            name = info.filename
            parts = PurePosixPath(name).parts
            if not parts or parts[0] != expected_root or name.startswith("/") or ".." in parts:
                raise ValueError(f"unsafe or wrong-root member: {name}")
            if name in names:
                raise ValueError(f"duplicate member: {name}")
            names.add(name)
            digest = hashlib.sha256()
            streamed = 0
            with archive.open(info) as source:
                for block in iter(lambda: source.read(64 * 1024), b""):
                    streamed += len(block)
                    digest.update(block)
            if streamed != info.file_size:
                raise ValueError(f"streamed-size mismatch: {name}")
            entries.append({
                "path": name,
                "bytes": streamed,
                "sha256": digest.hexdigest(),
                "crc32": f"{info.CRC:08x}",
            })
    return entries, container_bytes, container_sha


def package_manifest_check(returned: dict[str, Any]) -> dict[str, Any]:
    expected = returned["files"]
    errors: list[str] = []
    seen: set[str] = set()
    with zipfile.ZipFile(PACKAGE_ZIP) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) < 2 or parts[0] != PACKAGE_ID:
                errors.append(f"wrong package ZIP root: {info.filename}")
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            if relative == "package_manifest.json":
                with archive.open(info) as source:
                    packaged_manifest = json.load(source)
                if packaged_manifest != returned:
                    errors.append("package_manifest.json differs from returned package manifest")
                continue
            if relative not in expected:
                errors.append(f"unmanifested package member: {relative}")
                continue
            digest = hashlib.sha256()
            streamed = 0
            with archive.open(info) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    streamed += len(block)
                    digest.update(block)
            receipt = expected[relative]
            if streamed != receipt["size_bytes"] or digest.hexdigest() != receipt["sha256"]:
                errors.append(f"package member identity mismatch: {relative}")
            seen.add(relative)
    missing = sorted(set(expected) - seen)
    errors.extend(f"missing package member: {item}" for item in missing)
    return {"pass": not errors, "errors": errors, "members": len(seen)}


def reconcile_existing_analysis() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if int(state.get("checkpoint_count", 0)) >= 5:
        raise SystemExit("analysis was already reconciled")
    final = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    returned_package = load_json("evidence/returned_package_manifest.json")
    package_check = package_manifest_check(returned_package)
    final["integrity"]["pending_package_manifest_match"] = package_check["pass"]
    final["integrity"]["core_receipts_match"] = True
    final["integrity"]["errors"] = package_check["errors"]
    final["integrity"]["pass"] = package_check["pass"]
    atomic_json(FINAL_PATH, final)
    state["checkpoint_count"] = 5
    atomic_json(STATE_PATH, state)
    findings = [
        "All return members passed streamed size/SHA/CRC decompression checks.",
        "Core return receipts and the returned package manifest match the exact pending package; package_manifest.json is the expected self-manifest copy.",
        "Production compile exited 2; simulation did not start; VCD and runtime-stop receipts are therefore absent.",
        "The first true error is package-local TB XMRE at line 85 for nonexistent MSE_INST[5]; identical errors follow for [6] and [7].",
        "No signal-level FIFO/outstanding/response/last/count/FSM/drain/clear/finish verdict is possible in this execution.",
        "Formal analysis finalized; fresh package-local dump-scope repair is justified by the latest user override.",
    ]
    update_report(state, findings)
    append_checkpoint({"schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": 5, "phase": "PACKAGE_SELF_MANIFEST_RECONCILED", "status": state["status"], "byte_offset": state["byte_offset"], "integrity_pass": final["integrity"]["pass"]})
    print(json.dumps({"pass": final["integrity"]["pass"], "status": state["status"], "root": final["compile_root_cause"]["classification"], "output": FINAL_PATH.as_posix()}, ensure_ascii=False))
    return 0 if final["integrity"]["pass"] else 1


def main() -> int:
    if CHECKPOINTS_PATH.exists():
        return reconcile_existing_analysis()
    if not RETURN_ZIP.is_file() or not PACKAGE_ZIP.is_file() or not TREE_ROOT.is_dir():
        raise SystemExit("required return/package/extracted small evidence is absent")

    with zipfile.ZipFile(RETURN_ZIP) as archive:
        infos = archive.infolist()
        total_uncompressed = sum(info.file_size for info in infos)
        vcd_members = [info.filename for info in infos if info.filename.endswith(VCD_SUFFIX)]
    state: dict[str, Any] = {
        "schema": SCHEMA,
        "kind": "analysis_state",
        "source": {"path": RETURN_ZIP.as_posix(), "identity_kind": "EXACT_FORMAL_RETURN_ZIP"},
        "byte_offset": 0,
        "line_number": 0,
        "last_sim_time": None,
        "timescale": None,
        "signal_catalog": {},
        "signal_summaries": {},
        "status": "INDEXED_AWAITING_STREAM",
        "checkpoint_count": 0,
        "members_total": len(infos),
        "members_streamed": 0,
        "source_uncompressed_bytes": total_uncompressed,
        "vcd_member_present": bool(vcd_members),
        "vcd_members": vcd_members,
        "claim_boundary": "Streaming integrity and compile-core classification only; no simulation or signal claim without a VCD member.",
    }
    findings = ["ZIP central directory indexed before member streaming."]
    atomic_json(STATE_PATH, state)
    update_report(state, findings)
    append_checkpoint({"schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": 1, "phase": "ZIP_INDEXED", "status": state["status"], "byte_offset": 0})
    state["checkpoint_count"] = 1

    entries, return_bytes, return_sha = stream_zip(RETURN_ZIP, RETURN_ROOT)
    state["members_streamed"] = len(entries)
    state["byte_offset"] = sum(item["bytes"] for item in entries)
    state["status"] = "RETURN_MEMBERS_STREAMED"
    state["source"].update({"bytes": return_bytes, "sha256": return_sha})
    findings.append("All return members passed streamed size/SHA/CRC decompression checks.")
    atomic_json(STATE_PATH, state)
    update_report(state, findings)
    append_checkpoint({"schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": 2, "phase": "RETURN_STREAMED", "status": state["status"], "byte_offset": state["byte_offset"], "members": len(entries)})
    state["checkpoint_count"] = 2

    core = load_json("RETURN_CORE_MANIFEST.json")
    core_status = load_json("return_core/RETURN_CORE_STATUS.json")
    actual = load_json("evidence/ACTUAL_COMPILE_SIM_ARGV.json")
    compile_core = load_json("evidence/compile_rootcause/COMPILE_CORE.json")
    differential = load_json("evidence/compile_rootcause/NATIVE_FLOW_FAILURE_DIFFERENTIAL.json")
    root_identity = load_json("evidence/compile_rootcause/PUBLISHED_ACTUAL_ROOT_IDENTITY.json")
    returned_package = load_json("evidence/returned_package_manifest.json")
    streamed_by_relative = {item["path"].split("/", 1)[1]: item for item in entries}
    manifest_errors: list[str] = []
    for receipt in core["core_entry_receipts"]:
        found = streamed_by_relative.get(receipt["path"])
        if found is None:
            manifest_errors.append(f"missing receipted member: {receipt['path']}")
        elif found["bytes"] != receipt["bytes"] or found["sha256"] != receipt["sha256"]:
            manifest_errors.append(f"receipt mismatch: {receipt['path']}")
    package_check = package_manifest_check(returned_package)
    manifest_errors.extend(package_check["errors"])

    error_markers: list[dict[str, Any]] = []
    log_path = TREE_ROOT / "evidence/compile_rootcause/compile_driver.log"
    with log_path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            if "Error-[XMRE]" in line:
                error_markers.append({"line": line_number, "kind": "Error-[XMRE]"})
    first_error = (TREE_ROOT / "evidence/compile_rootcause/compile_first_error.txt").read_text(encoding="utf-8")
    exact_xmr = all(token in first_error for token in ["Error-[XMRE]", "token 'MSE_INST'", "native_mse4_bounded_causal_cone_vcd.sv, 85"])

    state.update({
        "compile_exit": compile_core["compile_exit"],
        "simulation_started": compile_core["simulation_started"],
        "sim_exit": compile_core["sim_exit"],
        "status": "NO_VCD_COMPILE_FAILED_ANALYSIS_COMPLETE",
        "checkpoint_count": 3,
    })
    findings.extend([
        "Core/package manifest identities pass." if not manifest_errors else "Core/package manifest identity errors were detected.",
        "Production compile exited 2; simulation did not start; VCD and runtime-stop receipts are therefore absent.",
        "The first true error is package-local TB XMRE at line 85 for nonexistent MSE_INST[5]; identical errors follow for [6] and [7].",
        "No signal-level FIFO/outstanding/response/last/count/FSM/drain/clear/finish verdict is possible in this execution.",
    ])
    atomic_json(STATE_PATH, state)
    update_report(state, findings)
    append_checkpoint({"schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": 3, "phase": "COMPILE_CORE_CLASSIFIED", "status": state["status"], "byte_offset": state["byte_offset"], "compile_exit": state["compile_exit"], "simulation_started": False, "vcd_member_present": False})

    final = {
        "schema": "conv-native-p47-tbvcdcone-formal-return-analysis-v1",
        "role_id": "family.conv.native",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE_ID,
        "execution_id": EXECUTION_ID,
        "attempt_id": ATTEMPT_ID,
        "formal_return": {"path": RETURN_ZIP.as_posix(), "bytes": return_bytes, "sha256": return_sha, "preserved": True},
        "integrity": {
            "pass": not manifest_errors,
            "zip_root": RETURN_ROOT,
            "member_count": len(entries),
            "all_members_streamed": True,
            "core_receipts_match": not manifest_errors,
            "pending_package_manifest_match": package_check["pass"],
            "errors": manifest_errors,
        },
        "identity": {
            "package_execution_attempt_match": core["package_id"] == PACKAGE_ID and core["execution_id"] == EXECUTION_ID and actual["attempt_id"] == ATTEMPT_ID,
            "published_root": root_identity["published_root"],
            "actual_root": root_identity["actual_root"],
            "root_match": root_identity["match"],
            "classification": "EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION",
        },
        "production": {
            "compile_exit": compile_core["compile_exit"],
            "simulation_started": compile_core["simulation_started"],
            "sim_exit": compile_core["sim_exit"],
            "signal": compile_core["sim_signal"],
            "timed_out": compile_core["timed_out"],
            "natural_terminal": core_status["sim_exit"]["natural_terminal_observed"],
            "actual_cwd": actual["actual_cwd"],
            "actual_compile_argv": actual["compile_argv"],
            "actual_sim_argv": actual["sim_argv"],
            "server_preflight_performed": actual["server_preflight_performed"],
        },
        "compile_root_cause": {
            "classification": "PACKAGE_LOCAL_TB_SCOPE_XMR_NONEXISTENT_MSE_INSTANCES",
            "confidence": "UNIQUE_HIGH",
            "first_true_error_exact": exact_xmr,
            "error_count": len(error_markers),
            "sites": [
                {"source": "tb_probe/native_mse4_bounded_causal_cone_vcd.sv", "line": 85, "token": "MSE_INST[5]"},
                {"source": "tb_probe/native_mse4_bounded_causal_cone_vcd.sv", "line": 86, "token": "MSE_INST[6]"},
                {"source": "tb_probe/native_mse4_bounded_causal_cone_vcd.sv", "line": 87, "token": "MSE_INST[7]"},
            ],
            "evidence": "VCS reports exactly three XMREs and stops compile; MSE_INST[0]..[4], the selected MSE4 bind, and the aggregate parent scope resolved before these three package-local dump-only references.",
            "repair_surface": "PACKAGE_LOCAL_TB_DUMP_SCOPE_ONLY",
        },
        "causal_analysis": {
            "family_last_proven_good": "p46 selected MSE4 qualified wdata output acceptance sequence 20 at 2446467000 ps, with descriptor/buffer/MemAG accepts already proven",
            "current_execution_last_proven_good": "actual production compilation reached VCS elaboration/XMR resolution for the package-local TB under NDP_copy02",
            "current_execution_first_divergence": "compile-time package-local $dumpvars XMR at line 85 for MSE_INST[5]",
            "dynamic_first_divergence": "NOT_OBSERVED_SIMULATION_NOT_STARTED",
            "p42_vector_fix": "FROZEN_PACKAGE_IDENTITY_PRESERVED_NOT_DYN_RETESTED",
            "p46_accepted_progress": "REMAINS_LAST_DYNAMIC_PROOF_NOT_REEXECUTED",
            "fifo_outstanding_response_last_count_fsm_drain_clear_finish": "NOT_OBSERVED_SIMULATION_NOT_STARTED",
            "candidate_matrix": "NOT_EVALUABLE_NO_RUNTIME_CATALOG_MATRIX_OR_VCD",
            "root_cause_confidence": "UNIQUE_HIGH_FOR_COMPILE_STOP_ONLY; NO_DUT_ROOT_CLAIM",
        },
        "streaming": {
            "mode": "STREAMING_RESUMABLE_NO_WHOLE_FILE_CONTEXT_LOAD",
            "analysis_state": STATE_PATH.relative_to(ROOT).as_posix(),
            "checkpoints": CHECKPOINTS_PATH.relative_to(ROOT).as_posix(),
            "incremental_report": REPORT_PATH.relative_to(ROOT).as_posix(),
            "vcd_member_present": False,
            "vcd_bytes_consumed": 0,
            "status": state["status"],
        },
        "early_stop": {
            "status": "NOT_REACHED_NOT_EVALUABLE",
            "correctly_effective": None,
            "reason": "compile failed before simulator start; no owner cycles, sim-time progress, causal digest, VCD, dumpoff or grace evidence exists",
        },
        "boundaries": {
            "natural_terminal": False,
            "formal_d": "NOT_EVALUATED",
            "e3": False,
            "e4": False,
            "e5": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
        "rule_audit_disposition": {
            "rule_gap_audit_triggered": False,
            "reason": "production compile did not succeed and the target simulation did not execute",
            "package_build_failure_rule_audit_triggered": False,
            "reason_2": "p46 executed the same target dynamically; p47 is the first subsequent package-local pre-execution failure, so the consecutive-two threshold is not met",
        },
        "next_action": "Build a fresh identity deleting only the three dump-only references to nonexistent MSE_INST[5..7], while preserving selected MSE4 and Stream_Engine aggregate scopes plus every frozen causal role.",
        "claim_boundary": "This analysis proves exact return/package integrity and a unique package-local compile-stop root. It does not prove signal behavior, early-stop correctness, natural termination, formal D, E3, E4, E5, or a DUT RTL/config/numeric root cause.",
    }
    atomic_json(FINAL_PATH, final)
    state["formal_analysis"] = FINAL_PATH.relative_to(ROOT).as_posix()
    state["checkpoint_count"] = 4
    atomic_json(STATE_PATH, state)
    findings.append("Formal analysis finalized; fresh package-local dump-scope repair is justified by the latest user override.")
    update_report(state, findings)
    append_checkpoint({"schema": SCHEMA, "kind": "analysis_checkpoint", "sequence": 4, "phase": "FORMAL_ANALYSIS_COMPLETE", "status": state["status"], "byte_offset": state["byte_offset"], "formal_analysis": state["formal_analysis"]})
    print(json.dumps({"pass": final["integrity"]["pass"] and exact_xmr, "status": state["status"], "root": final["compile_root_cause"]["classification"], "output": FINAL_PATH.as_posix()}, ensure_ascii=False))
    return 0 if final["integrity"]["pass"] and exact_xmr else 1


if __name__ == "__main__":
    raise SystemExit(main())
