#!/usr/bin/env python3
"""Bounded, resumable analysis of the exact QAdd v68 formal return.

The supplied return and source package ZIPs are read-only.  ZIP members are
hashed one at a time, text evidence is streamed line-by-line, and every phase
publishes a durable state/checkpoint/report update before the next phase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
RETURN_ROOT = f"{PACKAGE}_return/"
EXECUTION = "r1786853531805017272_3183291"
ATTEMPT = "a3183291"
EXPECTED_RETURN_BYTES = 69_744
EXPECTED_RETURN_SHA = "2519d6c5d54a048c6d62ff90bdcd35c003fb4d29d77e2f144d07db0c9052e285"
EXPECTED_PACKAGE_BYTES = 108_709_836
EXPECTED_PACKAGE_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"
CORRECT_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
REJECTED_BITSTREAM = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
OUT = ROOT / f"outputs/qlinearadd_node0007_v68_return_{EXECUTION}"
STREAM = OUT / "streaming_analysis"
CHUNKS = STREAM / "chunks"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    for block in iter(lambda: stream.read(1 << 16), b""):
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def immutable_json(path: Path, value: Any) -> None:
    payload = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"immutable analysis chunk drifted: {path}")
        return
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def append_checkpoint(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = f'"checkpoint_id": "{value["checkpoint_id"]}"'
    if path.is_file() and marker in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def append_report(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and heading in path.read_text(encoding="utf-8"):
        return
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"\n{heading}\n\n{body.rstrip()}\n")


def member_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {relative}")
    return value


def text_lines(archive: zipfile.ZipFile, relative: str) -> Iterator[str]:
    with archive.open(RETURN_ROOT + relative) as stream:
        for row in stream:
            yield row.decode("utf-8", errors="replace").rstrip("\r\n")


def safe_archive(archive: zipfile.ZipFile) -> dict[str, Any]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    roots = sorted({name.split("/", 1)[0] for name in names if name})
    unsafe: list[str] = []
    symlinks: list[str] = []
    for info in infos:
        pure = PurePosixPath(info.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
            unsafe.append(info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            symlinks.append(info.filename)
    bad = archive.testzip()
    passed = not duplicates and roots == [RETURN_ROOT.rstrip("/")] and not unsafe and not symlinks and bad is None
    return {
        "member_count": len(infos),
        "uncompressed_bytes": sum(info.file_size for info in infos),
        "duplicates": duplicates,
        "roots": roots,
        "unsafe_members": unsafe,
        "symlink_members": symlinks,
        "crc_bad_member": bad,
        "pass": passed,
    }


def manifest_receipt_check(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    actual: dict[str, dict[str, Any]] = {}
    for row in manifest.get("core_entry_receipts", []):
        relative = row["path"]
        member = RETURN_ROOT + relative
        try:
            with archive.open(member) as stream:
                size, digest = sha_stream(stream)
            actual[relative] = {
                "declared_bytes": row.get("bytes"),
                "actual_bytes": size,
                "declared_sha256": row.get("sha256"),
                "actual_sha256": digest,
                "match": size == row.get("bytes") and digest == row.get("sha256"),
            }
        except KeyError:
            actual[relative] = {"match": False, "error": "member absent"}
    errors = [path for path, row in actual.items() if not row.get("match")]
    return {"receipts": actual, "errors": errors, "pass": not errors}


def package_member_identity(package_zip: Path, relative: str) -> dict[str, Any]:
    member = f"{PACKAGE}/{relative}"
    with zipfile.ZipFile(package_zip) as archive:
        info = archive.getinfo(member)
        with archive.open(info) as stream:
            size, digest = sha_stream(stream)
    return {"path": relative, "bytes": size, "sha256": digest}


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--package-zip", type=Path, required=True)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    package_zip = args.package_zip.resolve()
    if return_zip.stat().st_size != EXPECTED_RETURN_BYTES or sha_file(return_zip) != EXPECTED_RETURN_SHA:
        raise RuntimeError("exact formal return identity mismatch")
    if package_zip.stat().st_size != EXPECTED_PACKAGE_BYTES or sha_file(package_zip) != EXPECTED_PACKAGE_SHA:
        raise RuntimeError("exact source package identity mismatch")

    STREAM.mkdir(parents=True, exist_ok=True)
    checkpoint_path = STREAM / "checkpoints.jsonl"
    state_path = STREAM / "analysis_state.json"
    report_path = STREAM / "report.md"
    initial = {
        "schema": "qadd-v68-bounded-streaming-analysis-state-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "IDENTITY_VERIFIED",
        "return_zip": {"bytes": EXPECTED_RETURN_BYTES, "sha256": EXPECTED_RETURN_SHA},
        "source_package_zip": {"bytes": EXPECTED_PACKAGE_BYTES, "sha256": EXPECTED_PACKAGE_SHA},
        "resume": {"next_sequence": 1, "return_member_offset": 0},
        "bounded_policy": "One ZIP member at a time; text streams line-by-line; no archive extraction.",
    }
    atomic_json(state_path, initial)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v68-stream-checkpoint-v1", "checkpoint_id": "001_identity",
        "sequence": 1, "status": "IDENTITY_VERIFIED", "return_sha256": EXPECTED_RETURN_SHA,
    })
    append_report(report_path, "# QAdd v68 formal return analysis", "Exact return and pending source-package identities are verified. Analysis is bounded and resumable; both ZIPs remain read-only.")

    with zipfile.ZipFile(return_zip) as archive:
        archive_safety = safe_archive(archive)
        if not archive_safety["pass"]:
            raise RuntimeError(f"unsafe or corrupt formal return: {archive_safety}")
        manifest = member_json(archive, "RETURN_CORE_MANIFEST.json")
        core = member_json(archive, "return_core/RETURN_CORE_STATUS.json")
        attempt = member_json(archive, "evidence/NATIVE_FAILURE_ATTEMPT.json")
        sim_exit = member_json(archive, "return_core/SIM_EXIT_RECEIPT.json")
        target = member_json(archive, "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        vcd_identity = member_json(archive, "evidence/TB_VCD_IDENTITY.json")
        dump = member_json(archive, "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json")
        stop = member_json(archive, "evidence/TB_VCD_STOP_RECEIPT.json")
        breadth = member_json(archive, "evidence/TB_VCD_BREADTH_EVOLUTION.json")
        lineage = member_json(archive, "source_package/CONFIG_LINEAGE_CONTRACT.json")
        config = member_json(archive, "source_package/op_tail_round_4_2.json")
        source_manifest = member_json(archive, "source_package/TEST_PACKAGE_MANIFEST.json")
        acceptance = member_json(archive, "source_package/qadd_config42_dynamic_acceptance.json")
        matrix = member_json(archive, "source_package/tb_vcd_candidate_matrix.json")
        prior_audit = member_json(archive, "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
        receipt_check = manifest_receipt_check(archive, manifest)
        sim_rows = list(text_lines(archive, "runs/sim.log"))

    package_manifest_identity = package_member_identity(package_zip, "TEST_PACKAGE_MANIFEST.json")
    bitstream_identity = package_member_identity(
        package_zip,
        "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin",
    )
    integrity_chunk = {
        "schema": "qadd-v68-stream-chunk-v1", "sequence": 2, "kind": "RETURN_INTEGRITY",
        "archive": archive_safety,
        "core_receipts": receipt_check,
        "package_manifest_member": package_manifest_identity,
        "returned_source_manifest_match": package_manifest_identity["sha256"] == next(
            row["sha256"] for row in manifest["core_entry_receipts"] if row["path"] == "source_package/TEST_PACKAGE_MANIFEST.json"
        ),
        "identity_binding": {
            "package": all(value == PACKAGE for value in (manifest.get("package_id"), core.get("package_id"), attempt.get("package_id"), target.get("package_id"), source_manifest.get("package_id"), source_manifest.get("install_name"))),
            "execution": all(value == EXECUTION for value in (manifest.get("execution_id"), core.get("execution_id"), attempt.get("execution_id"), target.get("execution_id"))),
            "attempt": attempt.get("attempt_id") == ATTEMPT and target.get("attempt_id") == ATTEMPT,
        },
    }
    immutable_json(CHUNKS / "002_return_integrity.json", integrity_chunk)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v68-stream-checkpoint-v1", "checkpoint_id": "002_return_integrity",
        "sequence": 2, "status": "RETURN_MEMBERS_STREAMED", "member_count": archive_safety["member_count"],
        "crc_pass": archive_safety["crc_bad_member"] is None, "receipt_exact": receipt_check["pass"],
    })
    append_report(report_path, "## Integrity and identity", f"The archive has {archive_safety['member_count']} safe, unique members and passes CRC. Every declared core-entry receipt matches its member. Package/execution/attempt identities bind to `{PACKAGE}` / `{EXECUTION}` / `{ATTEMPT}`.")

    compile_exit = int(attempt.get("compile_exit", -1))
    sim_code = int(attempt.get("simulation_exit", -1))
    required_missing = list(core.get("missing_required_entries", []))
    first_boundary = "PACKAGE_RUNTIME_PREFLIGHT_BEFORE_PACKAGE_MANIFEST_COPY"
    launch_chunk = {
        "schema": "qadd-v68-stream-chunk-v1", "sequence": 3, "kind": "PRODUCTION_LAUNCH_BOUNDARY",
        "compile_exit_sentinel": compile_exit,
        "simulation_exit_sentinel": sim_code,
        "simulation_started": attempt.get("simulation_started"),
        "actual_compile_argv": attempt.get("actual_compile_argv"),
        "actual_sim_argv": attempt.get("actual_sim_argv"),
        "sim_log_lines": sim_rows,
        "package_manifest_attempt_member_present": not any("evidence/PACKAGE_MANIFEST.json" in row for row in required_missing),
        "compile_start_member_present": not any("evidence/compile_argv.json" in row for row in required_missing),
        "vcd_exists": vcd_identity.get("exists"),
        "target_entered": target.get("observed"),
        "process_tree_receipt_present": not any("evidence/PROCESS_TREE_RECEIPT.json" in row for row in core.get("optional_entry_errors", [])),
        "first_divergence": first_boundary,
        "adjudication": "The exact runner creates the placeholder sim.log immediately before package-owned runtime preflight and copies evidence/PACKAGE_MANIFEST.json only after that preflight succeeds. The placeholder exists while PACKAGE_MANIFEST, compile argv/source/log and actual argv are absent, bounding the stop to that preflight interval. The inner exception/exit is not recoverable because its stderr/stdout/exit and runner-stage receipt were omitted.",
        "open_alternatives": [
            "package exact-set changed on the server extraction",
            "package preflight interpreter/runtime exception",
            "preflight interrupted while hashing the package tree",
        ],
    }
    immutable_json(CHUNKS / "003_production_launch_boundary.json", launch_chunk)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v68-stream-checkpoint-v1", "checkpoint_id": "003_launch_boundary",
        "sequence": 3, "status": "PRECOMPILE_BOUNDARY_ADJUDICATED", "first_divergence": first_boundary,
        "compile_started": False, "simulation_started": False, "target_entered": False,
    })
    append_report(report_path, "## Production launch and semantic-v5", "`compile_exit=125` is the runner's not-started sentinel, not a production compiler exit. Both actual argv arrays are empty; simulation and target entry are false; no VCD or process-tree receipt exists. The attempt stopped inside the package-runtime-preflight interval, before production compile. semantic-v5, PID+start-time ownership, planned dumpoff and STOP behavior were therefore not exercised.")

    group2_col_lc = config["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    config42 = group2_col_lc.get("end") == 4 and group2_col_lc.get("stride") == 2
    lineage_exact = (
        lineage.get("pass") is True
        and config42
        and lineage.get("packaged_bitstream_sha256") == CORRECT_BITSTREAM
        and bitstream_identity["sha256"] == CORRECT_BITSTREAM
        and lineage.get("rejected_bad_bitstream") == {"rejected": True, "sha256": REJECTED_BITSTREAM}
        and source_manifest.get("package_id") == PACKAGE
        and source_manifest.get("package_identity") == PACKAGE
        and source_manifest.get("install_name") == PACKAGE
    )
    direct_chunk = {
        "schema": "qadd-v68-stream-chunk-v1", "sequence": 4, "kind": "DIRECT_EVIDENCE",
        "DIRECT_CONFIG_EVIDENCE": {
            "group2_col_lc": {"end": group2_col_lc.get("end"), "stride": group2_col_lc.get("stride")},
            "lineage_contract_pass": lineage.get("pass"),
            "corrected_bitstream": bitstream_identity,
            "rejected_bad_bitstream_sha256": REJECTED_BITSTREAM,
            "positive_checks": lineage.get("positive_checks"),
            "negative_controls": lineage.get("negative_controls"),
            "package_lineage_exact": lineage_exact,
            "same_attempt_consumption": False,
        },
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "compile_source_identity_returned": False,
            "production_compile_started": False,
            "historical_consumer_sources": lineage.get("actual_rtl_consumer_sources"),
            "same_attempt_actual_compiled_rtl_claim": "NOT_AVAILABLE",
        },
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "target_entry": False,
            "request_0x33333333": False,
            "first_accept": False,
            "first_clear": False,
            "request_0xcccccccc": False,
            "second_accept": False,
            "second_clear": False,
            "repeated_first_alias_absent": None,
            "output": False,
            "natural_terminal": False,
            "formal_D": False,
            "status": "NOT_EXERCISED",
        },
    }
    immutable_json(CHUNKS / "004_direct_evidence.json", direct_chunk)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v68-stream-checkpoint-v1", "checkpoint_id": "004_direct_evidence",
        "sequence": 4, "status": "DIRECT_EVIDENCE_LAYERED", "package_lineage_exact": lineage_exact,
        "same_attempt_actual_rtl": False, "dynamic_acceptance_exercised": False,
    })
    append_report(report_path, "## Direct evidence layers", "DIRECT_CONFIG_EVIDENCE confirms the pending package contains exact 4/2 JSON and the corrected deterministic bitstream while rejecting the old 32/16 bitstream. DIRECT_ACTUAL_RTL_EVIDENCE is absent for this attempt because compile never started and compile_source_identity was not returned. DYNAMIC_EXECUTION_EVIDENCE is not exercised: neither complementary request, accept/clear, alias exclusion, output, terminal nor Formal-D can be adjudicated.")

    candidates = [row.get("candidate_id") for row in matrix.get("candidates", [])]
    audit = {
        "schema": "qadd-v68-package-build-failure-rule-audit-recurring-escape-v1",
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "trigger": "THIRD_CONSECUTIVE_PRETARGET_PACKAGE_RUNTIME_ESCAPE",
        "prior_audit": {
            "schema": prior_audit.get("schema"),
            "disposition": prior_audit.get("disposition"),
            "public_rule_delta_proposed": prior_audit.get("public_rule_delta_proposed"),
        },
        "adjudication": {
            "class": "EXISTING_RULE_IMPLEMENTATION_ESCAPE",
            "public_rule_gap": False,
            "violated_current_gates": [
                "package_release_admission_runtime_preflight semantic_version=2",
                "runtime_layout semantic_version=4",
                "runner_return_resilience semantic_version=1",
            ],
            "reason": "Current gates already require precompile failure stdout/stderr/exit and early-runner stderr visibility. The exact v68 runner dropped package-preflight stderr and did not return a stage/exit receipt, so the real first error is missing.",
        },
        "recurrence_prevention_required_next_fresh": [
            "capture package-runtime-preflight stdout, stderr and exit before branching",
            "write an execution-bound runner-stage receipt before and after the preflight",
            "copy the first nonempty preflight stderr line into compile_first_error for a compile-not-started core",
            "return the capture artifacts as required exact members",
            "negative-control a package-preflight failure and prove the exact return retains stage/stdout/stderr/exit/first-error",
            "preserve direct production launch with no server-owned inventory/probe",
        ],
        "rule_gap_audit_triggered": False,
        "rule_gap_reason": "Production compile, simulation and the target causal interval did not execute.",
        "pass": True,
        "errors": [],
        "claim_boundary": "This audit admits only a fresh package-local runner/return repair. It does not authorize server or storage action, config/RTL change, or functional root/terminal claims.",
    }
    atomic_json(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json", audit)
    escalation = {
        "schema": "qadd-shared-rule-audit-escalation-v1",
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "disposition": "RULE_CONFIRMATION_EXISTING_GATE_IMPLEMENTATION_ESCAPE",
        "affected_shared_gate_semantics": {
            "package_release_admission_runtime_preflight": "2",
            "runtime_layout": "4",
            "runner_return_resilience": "1",
        },
        "missing_exact_return_evidence": [
            "package preflight stdout",
            "package preflight stderr",
            "package preflight exit",
            "runner stage receipt",
            "true first error",
        ],
        "family_next_fresh_control": audit["recurrence_prevention_required_next_fresh"],
        "public_rule_delta_proposed": False,
        "pass": True,
        "errors": [],
    }
    atomic_json(OUT / "SHARED_RULE_AUDIT_ESCALATION.json", escalation)

    analysis = {
        "schema": "qlinearadd-node0007-v68-cfg42-t2-formal-return-analysis-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "RETURN_ANALYSIS_COMPLETE_FRESH_RUNNER_RETURN_REPAIR_REQUIRED",
        "integrity": {
            "return_identity_exact": True,
            "source_package_identity_exact": True,
            "zip_safety": archive_safety,
            "declared_core_receipts_exact": receipt_check["pass"],
            "identity_binding": integrity_chunk["identity_binding"],
            "return_disposition": core.get("disposition"),
        },
        "production": {
            "compile_started": False,
            "compile_exit_sentinel": compile_exit,
            "actual_compile_argv": attempt.get("actual_compile_argv"),
            "simulation_started": False,
            "simulation_exit_sentinel": sim_code,
            "target_entry": False,
            "first_true_error": attempt.get("first_true_error"),
            "required_entries_missing": required_missing,
        },
        "semantic_v5_and_process": {
            "exercised": False,
            "planned_dumpoff": dump.get("planned_dumpoff_observed"),
            "stop_marker_count": dump.get("stop_marker_count"),
            "process_tree_receipt": "ABSENT",
            "adjudication": "NOT_REACHED",
        },
        "DIRECT_CONFIG_EVIDENCE": direct_chunk["DIRECT_CONFIG_EVIDENCE"],
        "DIRECT_ACTUAL_RTL_EVIDENCE": direct_chunk["DIRECT_ACTUAL_RTL_EVIDENCE"],
        "DYNAMIC_EXECUTION_EVIDENCE": direct_chunk["DYNAMIC_EXECUTION_EVIDENCE"],
        "VALIDATED_ROOT_CAUSE": {
            "historical_root": lineage.get("validated_root_cause"),
            "package_repair_materialized": lineage_exact,
            "dynamic_repair_validation": "NOT_EXERCISED",
        },
        "OPEN_UNVALIDATED_MECHANISM": {
            "current_attempt_failure_boundary": first_boundary,
            "underlying_preflight_error": "UNRECOVERABLE_FROM_RETURN",
            "open_alternatives": launch_chunk["open_alternatives"],
        },
        "last_proven_good": {
            "classification": "EXACT_V68_PACKAGE_AND_4_2_LINEAGE_REACHED_PACKAGE_RUNTIME_PREFLIGHT",
            "detail": "The source package/return identities and exact 4/2 packaged lineage are proven, and the runner created its attempt layout and placeholder sim.log.",
        },
        "first_divergence": {
            "classification": first_boundary,
            "detail": launch_chunk["adjudication"],
        },
        "dynamic_contract": {
            "required_order": acceptance.get("required_ordered_sequence"),
            "observed": direct_chunk["DYNAMIC_EXECUTION_EVIDENCE"],
        },
        "candidate_matrix": {
            "pairwise_complete_in_package": matrix.get("pairwise_complete"),
            "breadth_source": breadth,
            "rows": [{"candidate_id": candidate, "status": "NOT_REACHED_NOT_ADJUDICABLE"} for candidate in candidates],
        },
        "boundaries": {
            "natural_terminal": False,
            "formal_D": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "Production compile and simulation did not start; no target dynamics or formal readback exist.",
        },
        "audit_disposition": "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE / RULE_CONFIRMATION_EXISTING_GATE_IMPLEMENTATION_ESCAPE",
        "successor_disposition": "FRESH_RUNNER_RETURN_ONLY_SUCCESSOR_WARRANTED",
        "frozen_surfaces": ["validated_config42", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix"],
        "conflicts": [],
        "pass": integrity_chunk["identity_binding"]["package"] and integrity_chunk["identity_binding"]["execution"] and receipt_check["pass"] and lineage_exact and compile_exit == 125 and attempt.get("simulation_started") is False,
        "errors": [],
        "claim_boundary": "This return proves exact v68/4-2 package identity and a precompile package-runtime-preflight boundary only. It does not prove production compile, actual compiled RTL, target dynamics, repair success, natural terminal, Formal-D or E3-E5.",
    }
    atomic_json(OUT / "formal_return_analysis.json", analysis)
    atomic_json(OUT / "RULE_AUDIT_DISPOSITION.json", {
        "schema": "qadd-v68-rule-audit-disposition-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "rule_gap_audit": "NOT_TRIGGERED_TARGET_NOT_EXECUTED",
        "package_build_failure_rule_audit": "TRIGGERED_RECURRING_EXISTING_GATE_IMPLEMENTATION_ESCAPE",
        "shared_rule_disposition": "RULE_CONFIRMATION_NO_PUBLIC_RULE_DELTA",
        "fresh_successor": "REQUIRED_TO_CAPTURE_PRECOMPILE_TRUE_ERROR_AND_RETRY_FROZEN_TARGET",
        "pass": True,
        "errors": [],
    })
    immutable_json(CHUNKS / "005_family_disposition.json", {
        "schema": "qadd-v68-stream-chunk-v1", "sequence": 5, "kind": "FAMILY_DISPOSITION",
        "last_proven_good": analysis["last_proven_good"],
        "first_divergence": analysis["first_divergence"],
        "audit_disposition": analysis["audit_disposition"],
        "claim_boundary": analysis["claim_boundary"],
    })
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v68-stream-checkpoint-v1", "checkpoint_id": "005_family_disposition",
        "sequence": 5, "status": analysis["status"],
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": first_boundary,
        "analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
    })
    append_report(report_path, "## Family disposition", "- LAST_PROVEN_GOOD: exact v68 and exact packaged 4/2 lineage reached the package-runtime-preflight interval.\n- FIRST_DIVERGENCE: `PACKAGE_RUNTIME_PREFLIGHT_BEFORE_PACKAGE_MANIFEST_COPY`.\n- Current attempt root mechanism: open because preflight stdout/stderr/exit and runner-stage receipt are absent.\n- RULE_GAP_AUDIT: not triggered; target did not execute.\n- PACKAGE_BUILD_FAILURE_RULE_AUDIT: recurring third-attempt implementation escape; current public gate semantics are confirmed, but the package failed to implement them.\n- Successor: a fresh runner/return-only repair is warranted; config/numeric/workload/golden/functional RTL/causal target remain frozen.\n- Natural terminal/Formal-D/E3/E4/E5: not proven.")

    chunk_rows = []
    for path in sorted(CHUNKS.glob("*.json")):
        chunk_rows.append({"path": path.relative_to(STREAM).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)})
    atomic_json(STREAM / "review_index.json", {
        "schema": "qadd-v68-stream-review-index-v1",
        "return_sha256": EXPECTED_RETURN_SHA,
        "revision": 5,
        "next_sequence": 6,
        "chunks": chunk_rows,
        "terminal_status": "INCONCLUSIVE_STOP_PRETARGET_RETURN_CAPTURE_GAP",
        "final_pointer": "../formal_return_analysis.json",
    })
    final_state = dict(initial)
    final_state.update({
        "status": "EOF_REACHED_FAMILY_ANALYSIS_COMPLETE",
        "resume": {"next_sequence": 6, "return_member_offset": archive_safety["member_count"]},
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": first_boundary,
        "formal_analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
        "package_build_failure_rule_audit_sha256": sha_file(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"),
        "shared_rule_audit_escalation_sha256": sha_file(OUT / "SHARED_RULE_AUDIT_ESCALATION.json"),
    })
    atomic_json(state_path, final_state)
    atomic_json(OUT / "formal_return_consumption_receipt.json", {
        "schema": "qadd-v68-formal-return-consumption-receipt-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "return_zip": {"path": str(return_zip), "bytes": EXPECTED_RETURN_BYTES, "sha256": EXPECTED_RETURN_SHA},
        "source_package_zip": {"path": package_zip.relative_to(ROOT).as_posix(), "bytes": EXPECTED_PACKAGE_BYTES, "sha256": EXPECTED_PACKAGE_SHA},
        "analysis": identity(OUT / "formal_return_analysis.json"),
        "package_build_failure_rule_audit": identity(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"),
        "shared_rule_audit_escalation": identity(OUT / "SHARED_RULE_AUDIT_ESCALATION.json"),
        "return_preserved": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "conflicts": [],
        "pass": analysis["pass"],
        "errors": analysis["errors"],
        "claim_boundary": analysis["claim_boundary"],
    })
    print(json.dumps({"analysis": str(OUT / "formal_return_analysis.json"), "pass": analysis["pass"]}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
