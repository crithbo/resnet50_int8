#!/usr/bin/env python3
"""Bounded/resumable analysis of the exact QAdd v69 formal return.

The supplied return, sidecar, and source-package ZIPs are read-only. ZIP
members are consumed one at a time; large text is streamed line-by-line.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v69_pfc"
RETURN_ROOT = f"{PACKAGE}_return/"
EXECUTION = "r1786886207604661595_3464688"
ATTEMPT = "a3464688"
EXPECTED_RETURN_SHA = "ee300f555f596400ff756a4f446154cdf1fd4ca203d6e7f8ded9fd7f4c076ae4"
EXPECTED_RETURN_BYTES = 125_161
EXPECTED_PACKAGE_SHA = "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597"
EXPECTED_PACKAGE_BYTES = 108_735_727
GOOD_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
BAD_BITSTREAM = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
OUT = ROOT / f"outputs/qlinearadd_node0007_v69_return_{EXECUTION}"
STREAM = OUT / "streaming_analysis"
CHUNKS = STREAM / "chunks"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1 << 16), b""):
        size += len(block)
        digest.update(block)
    return size, digest.hexdigest()


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_bytes(canonical(value))
    os.replace(temp, path)


def immutable(path: Path, value: Any) -> None:
    payload = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"immutable chunk drift: {path}")
        return
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_bytes(payload)
    os.replace(temp, path)


def checkpoint(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"checkpoint_id": "{value["checkpoint_id"]}"'
    if path.exists() and marker in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def report(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and heading in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"\n{heading}\n\n{body.rstrip()}\n")


def jmember(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"object required: {relative}")
    return value


def tmember(archive: zipfile.ZipFile, relative: str) -> list[str]:
    rows: list[str] = []
    with archive.open(RETURN_ROOT + relative) as stream:
        for raw in stream:
            rows.append(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    return rows


def package_member(package_zip: Path, relative: str) -> dict[str, Any]:
    with zipfile.ZipFile(package_zip) as archive:
        with archive.open(f"{PACKAGE}/{relative}") as stream:
            size, digest = sha_stream(stream)
    return {"path": relative, "bytes": size, "sha256": digest}


def safe_zip(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist()
    names = [row.filename for row in infos]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    unsafe = []
    symlinks = []
    for row in infos:
        pure = PurePosixPath(row.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename:
            unsafe.append(row.filename)
        if stat.S_ISLNK(row.external_attr >> 16):
            symlinks.append(row.filename)
    bad = archive.testzip()
    roots = sorted({name.split("/", 1)[0] for name in names})
    return {
        "member_count": len(infos),
        "uncompressed_bytes": sum(row.file_size for row in infos),
        "duplicates": duplicates,
        "unsafe": unsafe,
        "symlinks": symlinks,
        "crc_bad_member": bad,
        "roots": roots,
        "pass": not duplicates and not unsafe and not symlinks and bad is None and roots == [PACKAGE + "_return"],
    }


def receipt_check(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for declared in manifest.get("core_entry_receipts", []):
        relative = declared["path"]
        try:
            with archive.open(RETURN_ROOT + relative) as stream:
                size, digest = sha_stream(stream)
            match = size == declared.get("bytes") and digest == declared.get("sha256")
            rows.append({"path": relative, "bytes": size, "sha256": digest, "match": match})
        except KeyError:
            rows.append({"path": relative, "match": False, "error": "absent"})
    return {"entries": rows, "pass": all(row["match"] for row in rows)}


def supervisor_defect(package_zip: Path) -> dict[str, Any]:
    relative = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v69.py"
    with zipfile.ZipFile(package_zip) as archive:
        source = archive.read(f"{PACKAGE}/{relative}").decode("utf-8")
    tree = ast.parse(source)
    match: dict[str, Any] | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "known":
            match = {
                "line": node.lineno,
                "annotation": ast.unparse(node.annotation),
                "initializer_ast": type(node.value).__name__,
                "initializer": ast.unparse(node.value) if node.value is not None else None,
            }
            break
    return {
        "member": package_member(package_zip, relative),
        "declaration": match,
        "unique_defect": bool(match and match["initializer_ast"] == "Set"),
        "failure_path": "owned() calls known.items(); a set has no items(), so the supervisor exits after Popen and before ownership receipts",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--package-zip", type=Path, required=True)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    sidecar = args.sidecar.resolve()
    package_zip = args.package_zip.resolve()
    side_fields = sidecar.read_text(encoding="utf-8-sig").strip().split()
    if return_zip.stat().st_size != EXPECTED_RETURN_BYTES or sha_file(return_zip) != EXPECTED_RETURN_SHA:
        raise RuntimeError("return identity mismatch")
    if side_fields != [EXPECTED_RETURN_SHA, return_zip.name]:
        raise RuntimeError("sidecar mismatch")
    if package_zip.stat().st_size != EXPECTED_PACKAGE_BYTES or sha_file(package_zip) != EXPECTED_PACKAGE_SHA:
        raise RuntimeError("source package identity mismatch")

    state_path = STREAM / "analysis_state.json"
    checks_path = STREAM / "checkpoints.jsonl"
    report_path = STREAM / "report.md"
    initial = {
        "schema": "qadd-v69-bounded-streaming-analysis-state-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "IDENTITY_VERIFIED",
        "return_zip": {"path": str(return_zip), "bytes": EXPECTED_RETURN_BYTES, "sha256": EXPECTED_RETURN_SHA},
        "sidecar": {"path": str(sidecar), "sha256": sha_file(sidecar)},
        "source_package_zip": {"path": str(package_zip), "bytes": EXPECTED_PACKAGE_BYTES, "sha256": EXPECTED_PACKAGE_SHA},
        "bounded_policy": "one member at a time; text line-by-line; no extraction",
        "resume": {"next_sequence": 2, "return_member_offset": 0},
    }
    atomic(state_path, initial)
    checkpoint(checks_path, {"schema": "qadd-v69-stream-checkpoint-v1", "checkpoint_id": "001_identity", "sequence": 1, "status": "IDENTITY_VERIFIED"})
    report(report_path, "# QAdd v69 formal return analysis", "Exact return/sidecar/source package identities are verified. The inputs remain read-only; analysis is bounded and resumable.")

    with zipfile.ZipFile(return_zip) as archive:
        safety = safe_zip(archive)
        manifest = jmember(archive, "RETURN_CORE_MANIFEST.json")
        core = jmember(archive, "return_core/RETURN_CORE_STATUS.json")
        sim_exit = jmember(archive, "return_core/SIM_EXIT_RECEIPT.json")
        attempt = jmember(archive, "evidence/NATIVE_FAILURE_ATTEMPT.json")
        preflight = jmember(archive, "evidence/PACKAGE_PREFLIGHT_EXECUTION.json")
        stage = jmember(archive, "evidence/RUNNER_STAGE_RECEIPT.json")
        actual = jmember(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        source_identity = jmember(archive, "evidence/compile_source_identity.json")
        target = jmember(archive, "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        vcd = jmember(archive, "evidence/TB_VCD_IDENTITY.json")
        stop = jmember(archive, "evidence/TB_VCD_STOP_RECEIPT.json")
        lineage = jmember(archive, "source_package/CONFIG_LINEAGE_CONTRACT.json")
        config = jmember(archive, "source_package/op_tail_round_4_2.json")
        source_manifest = jmember(archive, "source_package/TEST_PACKAGE_MANIFEST.json")
        acceptance = jmember(archive, "source_package/qadd_config42_dynamic_acceptance.json")
        sim_log = tmember(archive, "runs/sim.log")
        samples = tmember(archive, "evidence/vcd/supervisor_samples.jsonl")
        receipts = receipt_check(archive, manifest)

    identity_values = [manifest.get("package_id"), core.get("package_id"), attempt.get("package_id"), preflight.get("package_id"), actual.get("package_id"), target.get("package_id"), source_manifest.get("package_id"), source_manifest.get("install_name")]
    execution_values = [manifest.get("execution_id"), core.get("execution_id"), attempt.get("execution_id"), preflight.get("execution_id"), actual.get("execution_id"), target.get("execution_id")]
    attempt_values = [attempt.get("attempt_id"), preflight.get("attempt_id"), actual.get("attempt_id"), target.get("attempt_id")]
    returned_manifest = next(row for row in receipts["entries"] if row["path"] == "source_package/TEST_PACKAGE_MANIFEST.json")
    local_manifest = package_member(package_zip, "TEST_PACKAGE_MANIFEST.json")
    integrity = {
        "schema": "qadd-v69-stream-chunk-v1", "sequence": 2, "kind": "INTEGRITY_IDENTITY",
        "archive": safety, "core_receipts": receipts,
        "sidecar_match": True,
        "package_binding": all(value == PACKAGE for value in identity_values),
        "execution_binding": all(value == EXECUTION for value in execution_values),
        "attempt_binding": all(value == ATTEMPT for value in attempt_values),
        "returned_source_manifest_matches_local_package": returned_manifest["sha256"] == local_manifest["sha256"],
    }
    immutable(CHUNKS / "002_integrity_identity.json", integrity)
    checkpoint(checks_path, {"schema": "qadd-v69-stream-checkpoint-v1", "checkpoint_id": "002_integrity", "sequence": 2, "status": "RETURN_INTEGRITY_VERIFIED", "members": safety["member_count"]})
    report(report_path, "## Integrity and identity", f"The ZIP has {safety['member_count']} safe unique members, CRC passes, every declared core receipt matches, and package/execution/attempt bind to `{PACKAGE}` / `{EXECUTION}` / `{ATTEMPT}`.")

    defect = supervisor_defect(package_zip)
    compile_ok = attempt.get("compile_exit") == 0 and int(tmember(zipfile.ZipFile(return_zip), "evidence/compile_exit.txt")[0]) == 0
    preflight_ok = preflight.get("exit_code") == 0 and stage.get("stage_exit") == 0
    launch = {
        "schema": "qadd-v69-stream-chunk-v1", "sequence": 3, "kind": "PRODUCTION_BOUNDARY",
        "package_preflight": {"pass": preflight_ok, "receipt": preflight},
        "compile": {"pass": compile_ok, "actual_argv": actual.get("compile_argv"), "source_identity": source_identity},
        "simulator": {"wrapper_flag": attempt.get("simulation_started"), "exit": attempt.get("simulation_exit"), "sim_exit_receipt": sim_exit, "sim_log": sim_log},
        "process_ownership_receipt_present": not any("PROCESS_TREE_RECEIPT.json" in row for row in core.get("optional_entry_errors", [])),
        "vcd_exists": vcd.get("exists"), "target_entry": target.get("observed"), "stop": stop,
        "supervisor_samples": samples,
        "unique_package_local_root": defect,
        "last_proven_good": "PRODUCTION_COMPILE_COMPLETED_AND_SIMV_POPEN_WAS_ISSUED",
        "first_divergence": "PACKAGE_LOCAL_SUPERVISOR_FIRST_OWNED_PROCESS_ENUMERATION_AFTER_POPEN",
    }
    immutable(CHUNKS / "003_production_boundary.json", launch)
    checkpoint(checks_path, {"schema": "qadd-v69-stream-checkpoint-v1", "checkpoint_id": "003_boundary", "sequence": 3, "status": "UNIQUE_PACKAGE_RUNTIME_ROOT", "first_divergence": launch["first_divergence"]})
    report(report_path, "## Compile, launch, and process ownership", "Package preflight and production compile both completed. The runner then set its launch flag and the supervisor called `Popen`, but the exact supervisor initialized `known: dict[...]` with a set. Its first `known.items()` call therefore exits before process/safety receipts; `sim.log` remains `# SIMULATION_NOT_STARTED`, VCD is absent, and target entry is false. The launch flag is not dynamic target execution. An orphaned simulator is possible and cannot be closed from this return.")

    col = config["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    bitstream = package_member(package_zip, "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    lineage_exact = col.get("end") == 4 and col.get("stride") == 2 and lineage.get("pass") is True and bitstream["sha256"] == GOOD_BITSTREAM and lineage.get("rejected_bad_bitstream", {}).get("sha256") == BAD_BITSTREAM
    direct = {
        "schema": "qadd-v69-stream-chunk-v1", "sequence": 4, "kind": "DIRECT_EVIDENCE",
        "DIRECT_CONFIG_EVIDENCE": {"end": col.get("end"), "stride": col.get("stride"), "lineage_exact": lineage_exact, "bitstream": bitstream, "same_attempt_sca_paths": [actual.get("sca_cfg"), actual.get("sca_cfg_d")]},
        "DIRECT_ACTUAL_RTL_EVIDENCE": {"production_compile_succeeded": compile_ok, "makefile": source_identity.get("makefile"), "package_tb": source_identity.get("explicit_package_source"), "target_runtime_state_reached": False},
        "DYNAMIC_EXECUTION_EVIDENCE": {"target_entry": False, "ordered_3333_cccc": False, "two_accepts": False, "two_clears": False, "alias_exclusion": None, "output": False, "natural_terminal": False, "formal_D": False, "status": "NOT_EXECUTED"},
        "acceptance_contract": acceptance,
        "root_status": "VALIDATED_PACKAGE_LOCAL_RUNTIME_ROOT; VALIDATED_4_2_FUNCTIONAL_REPAIR_REMAINS_DYNAMICALLY_OPEN",
    }
    immutable(CHUNKS / "004_direct_evidence.json", direct)
    checkpoint(checks_path, {"schema": "qadd-v69-stream-checkpoint-v1", "checkpoint_id": "004_direct", "sequence": 4, "status": "DIRECT_EVIDENCE_LAYERED", "lineage_exact": lineage_exact, "dynamic_target": False})
    report(report_path, "## Direct evidence", "DIRECT_CONFIG_EVIDENCE binds the exact authorized 4/2 JSON and corrected bitstream. DIRECT_ACTUAL_RTL_EVIDENCE proves the production compile and package TB identity, but no target runtime state. DYNAMIC_EXECUTION_EVIDENCE is absent: neither request sequence, accept/clear, alias exclusion, output, natural terminal nor Formal-D can be adjudicated.")

    audit = {
        "schema": "qadd-v69-package-build-failure-rule-audit-v1",
        "role_id": "family.qlinearadd", "package_id": PACKAGE, "execution_id": EXECUTION,
        "trigger": "RECURRING_PRETARGET_PACKAGE_LOCAL_RUNTIME_ESCAPE_AFTER_EXISTING_AUDIT",
        "adjudication": {
            "class": "EXISTING_RULE_IMPLEMENTATION_AND_NEGATIVE_CONTROL_ESCAPE",
            "public_rule_gap": False,
            "rule_disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "unique_root": defect,
            "current_rules_already_require": ["generic child-subreaper ownership", "complete process-tree receipt", "partial-return evidence", "runner/compile-core and process-tree negative controls"],
            "package_gate_gap": ["exact supervisor was not exercised through the first owned() enumeration", "supervisor stdout/stderr was not captured in the formal return"],
        },
        "required_fresh_controls": [
            "initialize tracked PID/start-time state as a dict and prove first owned() enumeration",
            "run exact supervisor with a short child and verify process/safety/decision receipts",
            "negative-control the historical set initializer",
            "capture supervisor stdout/stderr/exit as required partial-return members",
            "prove TERM/wait/KILL/reap exact ownership and no surviving descendant",
        ],
        "rule_gap_audit": "NOT_TRIGGERED_TARGET_CAUSAL_INTERVAL_NOT_EXECUTED",
        "pass": defect["unique_defect"], "errors": [],
        "claim_boundary": "Package-local runtime root only; no functional repair/terminal/E3-E5 claim.",
    }
    atomic(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", audit)
    analysis = {
        "schema": "qadd-v69-formal-return-analysis-v1",
        "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6,
        "package_id": PACKAGE, "execution_id": EXECUTION, "attempt_id": ATTEMPT,
        "status": "PACKAGE_LOCAL_SUPERVISOR_ROOT_VALIDATED_FRESH_FIX_REQUIRED",
        "previous_version_progress": "v68 preserved exact authorized 4/2 lineage but stopped at opaque package preflight before compile.",
        "current_version_purpose": "v69 added preflight/core capture so the frozen 4/2 tail-round target could proceed into production compile and simulation.",
        "v69_legal_identity": "Fresh identity over v68; exact 4/2 config/bitstream, workload, numeric/golden, functional RTL absence, 64-signal causal cone and candidate matrix are preserved; only precompile/core-return surfaces changed.",
        "integrity": integrity,
        "last_proven_good": launch["last_proven_good"], "first_divergence": launch["first_divergence"],
        "validated_root_cause": "QADD_V69_SUPERVISOR_TRACKED_PID_MAP_INITIALIZED_AS_SET_CAUSES_POST_POPEN_PRETARGET_ESCAPE",
        "root_classification": "PACKAGE_LOCAL_RUNNER_SUPERVISOR_IMPLEMENTATION_DEFECT",
        "DIRECT_CONFIG_EVIDENCE": direct["DIRECT_CONFIG_EVIDENCE"],
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct["DIRECT_ACTUAL_RTL_EVIDENCE"],
        "DYNAMIC_EXECUTION_EVIDENCE": direct["DYNAMIC_EXECUTION_EVIDENCE"],
        "VALIDATED_ROOT_CAUSE": "package-local supervisor defect above",
        "OPEN_UNVALIDATED_MECHANISM": "authorized 4/2 functional repair remains dynamically unvalidated",
        "boundaries": {"package_preflight": True, "production_compile": True, "simv_popen_issued": True, "simulation_time_progress": False, "target_entry": False, "natural_terminal": False, "formal_D": False, "E3": False, "E4": False, "E5": False},
        "return_completeness": "PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "process_ownership": "NOT_CLOSED; orphan risk is possible because Popen preceded the supervisor exception and no process receipt exists",
        "audit_disposition": "PACKAGE_BUILD_FAILURE_RULE_AUDIT / RULE_CONFIRMATION_NO_CHANGE",
        "successor_disposition": "FRESH_RUNNER_SUPERVISOR_RETURN_ONLY_FIX_WARRANTED",
        "frozen_surfaces": ["validated 4/2 config lineage", "numeric", "workload", "golden", "functional RTL", "tail-round target", "64-signal causal cone", "candidate matrix"],
        "storage_manager_called": False, "server_actions_performed": [], "conflicts": [],
        "pass": all([safety["pass"], receipts["pass"], integrity["package_binding"], integrity["execution_binding"], integrity["attempt_binding"], preflight_ok, compile_ok, lineage_exact, defect["unique_defect"]]),
        "errors": [],
        "claim_boundary": "The return proves exact v69 identity, package preflight, production compile, and a unique post-Popen package-supervisor escape. It does not prove simulation-time progress, target execution, 4/2 dynamic repair, natural terminal, Formal-D, or E3-E5.",
    }
    atomic(OUT / "formal_return_analysis.json", analysis)
    atomic(OUT / "RULE_AUDIT_DISPOSITION.json", {"schema": "qadd-v69-rule-audit-disposition-v1", "package_id": PACKAGE, "execution_id": EXECUTION, "package_build_failure_rule_audit": "TRIGGERED", "rule_gap_audit": "NOT_TRIGGERED_TARGET_NOT_EXECUTED", "shared_rule_disposition": "RULE_CONFIRMATION_NO_CHANGE", "fresh_successor": "REQUIRED", "pass": True, "errors": []})
    immutable(CHUNKS / "005_disposition.json", {"schema": "qadd-v69-stream-chunk-v1", "sequence": 5, "kind": "DISPOSITION", "last_proven_good": analysis["last_proven_good"], "first_divergence": analysis["first_divergence"], "validated_root_cause": analysis["validated_root_cause"], "claim_boundary": analysis["claim_boundary"]})
    checkpoint(checks_path, {"schema": "qadd-v69-stream-checkpoint-v1", "checkpoint_id": "005_disposition", "sequence": 5, "status": analysis["status"], "analysis_sha256": sha_file(OUT / "formal_return_analysis.json")})
    report(report_path, "## Disposition", "- LAST_PROVEN_GOOD: production compile completed and the supervisor issued `Popen` for simv.\n- FIRST_DIVERGENCE: first owned-process enumeration after `Popen`.\n- VALIDATED_ROOT_CAUSE: the exact package supervisor declared a dict but initialized a set.\n- 4/2 functional repair: still dynamically open.\n- RULE_GAP_AUDIT: not triggered because target did not execute.\n- PACKAGE_BUILD_FAILURE_RULE_AUDIT: triggered; current public rule is sufficient, but exact negative controls missed this implementation.\n- Fresh runner/supervisor/return-only fix: required.\n- Natural terminal/Formal-D/E3-E5: not proven.")

    chunks = [{"path": path.relative_to(STREAM).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)} for path in sorted(CHUNKS.glob("*.json"))]
    atomic(STREAM / "review_index.json", {"schema": "qadd-v69-stream-review-index-v1", "return_sha256": EXPECTED_RETURN_SHA, "revision": 5, "next_sequence": 6, "chunks": chunks, "terminal_status": "ROOT_CAUSE_UNIQUE_STOP_PACKAGE_RUNTIME", "final_pointer": "../formal_return_analysis.json"})
    final = dict(initial)
    final.update({"status": "EOF_REACHED_FAMILY_ANALYSIS_COMPLETE", "resume": {"next_sequence": 6, "return_member_offset": safety["member_count"]}, "last_proven_good": analysis["last_proven_good"], "first_divergence": analysis["first_divergence"], "formal_analysis_sha256": sha_file(OUT / "formal_return_analysis.json"), "audit_sha256": sha_file(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")})
    atomic(state_path, final)
    atomic(OUT / "formal_return_consumption_receipt.json", {"schema": "qadd-v69-formal-return-consumption-receipt-v1", "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6, "package_id": PACKAGE, "execution_id": EXECUTION, "attempt_id": ATTEMPT, "return_zip": initial["return_zip"], "sidecar": initial["sidecar"], "source_package_zip": initial["source_package_zip"], "analysis": {"path": "formal_return_analysis.json", "bytes": (OUT / "formal_return_analysis.json").stat().st_size, "sha256": sha_file(OUT / "formal_return_analysis.json")}, "audit": {"path": "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "bytes": (OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").stat().st_size, "sha256": sha_file(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")}, "return_preserved": True, "storage_manager_called": False, "server_actions_performed": [], "conflicts": [], "pass": analysis["pass"], "errors": analysis["errors"], "claim_boundary": analysis["claim_boundary"]})
    print(json.dumps({"analysis": str(OUT / "formal_return_analysis.json"), "pass": analysis["pass"]}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
