#!/usr/bin/env python3
"""Validate and adjudicate the exact serialized-Conv v88b formal return.

This analyzer never modifies the supplied return or source-package ZIP.  It
validates both archives in place, emits a machine report, and copies only a
small selected evidence set into a fresh analysis directory for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE = "r5_n4_hw_v88b_portvcd"
RETURN_ROOT = f"{PACKAGE}_return"
EXPECTED_RETURN_BASENAME = (
    "r5_n4_hw_v88b_portvcd_r1786512376161600481_1423296_return.zip"
)
EXPECTED_EXECUTION = "r1786512376161600481_1423296"
TARGET_INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new."
    "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group."
    "slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
)

GENERATED_CORE = {
    "RETURN_CORE_MANIFEST.json",
    "return_core/RETURN_CORE_STATUS.json",
    "return_core/RETURN_PLUGIN_STATUS.json",
    "return_core/SIM_EXIT_RECEIPT.json",
    "return_core/plugins/node0004_source_bound_collect.status.json",
    "return_core/plugins/node0004_source_bound_collect.stderr.log",
    "return_core/plugins/node0004_source_bound_collect.stdout.log",
}

SELECTED_RETURN_EVIDENCE = {
    "evidence/compiled_source/actual_target_source.sv": "actual_target_source.sv",
    "evidence/compiled_source/preprocessed_target.sv": "preprocessed_target.sv",
    "evidence/compiled_source/preprocessed_target_receipt.json": "preprocessed_target_receipt.json",
    "evidence/compiled_source/elaborated_ack_driver_set.json": "elaborated_ack_driver_set.json",
    "evidence/compile_rootcause/compile_source_identity.json": "compile_source_identity.json",
    "evidence/compile_rootcause/compile_argv.json": "compile_argv.json",
    "evidence/SERVER_RESULT_GATE.json": "server_result_gate.json",
    "evidence/buffer_ack_phase_raw_preservation.json": "phase_raw_preservation.json",
    "return_core/SIM_EXIT_RECEIPT.json": "sim_exit_receipt.json",
    "return_core/RETURN_CORE_STATUS.json": "return_core_status.json",
    "return_core/plugins/node0004_source_bound_collect.stderr.log": "post_sim_plugin.stderr.log",
    "runs/c0/buffer_ack_phase_decision.json": "phase_decision.json",
    "runs/c0/source_bound_causal_decision.json": "source_bound_causal_decision.json",
    "waveforms/WAVEFORM_RUNTIME_RECEIPT.json": "waveform_runtime_receipt.json",
    "waveforms/portable/PORTABLE_RUNTIME_RECEIPT.json": "portable_runtime_receipt.json",
    "waveforms/portable/PORTABLE_RUNTIME_VALIDATION.json": "portable_runtime_validation.json",
    "waveforms/portable/SIGNAL_QUERY_RECEIPT.json": "signal_query_receipt.json",
    "waveforms/portable/codex_wave_dump.tcl": "codex_wave_dump.tcl",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def as_object(payloads: dict[str, bytes], name: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(payloads[name])
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as error:
        errors.append(f"invalid_json:{name}:{type(error).__name__}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"json_not_object:{name}")
        return {}
    return value


def read_archive(
    path: Path, expected_root: str, errors: list[str]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    payloads: dict[str, bytes] = {}
    names: list[str] = []
    roots: set[str] = set()
    expanded = 0
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc_failure:{bad}")
        for info in archive.infolist():
            name = info.filename
            names.append(name)
            member = PurePosixPath(name)
            if member.parts:
                roots.add(member.parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in name
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe_member:{name}")
                continue
            if info.is_dir():
                continue
            if len(member.parts) < 2 or member.parts[0] != expected_root:
                errors.append(f"root_mismatch:{name}")
                continue
            relative = PurePosixPath(*member.parts[1:]).as_posix()
            if relative in payloads:
                errors.append(f"duplicate_relative_member:{relative}")
                continue
            payloads[relative] = archive.read(info)
            expanded += info.file_size
    if len(names) != len(set(names)):
        errors.append("duplicate_archive_member")
    if roots != {expected_root}:
        errors.append(f"single_root_mismatch:{sorted(roots)}")
    return payloads, {
        "member_count": len(names),
        "file_count": len(payloads),
        "root": expected_root,
        "roots_observed": sorted(roots),
        "expanded_bytes": expanded,
        "crc_valid": not any(item.startswith("crc_failure:") for item in errors),
        "path_safe": not any(
            item.startswith(("unsafe_member:", "root_mismatch:", "duplicate_"))
            for item in errors
        ),
    }


def core_exact_set(
    payloads: dict[str, bytes], manifest: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    rows = manifest.get("core_entry_receipts")
    if not isinstance(rows, list):
        errors.append("core_entry_receipts_not_list")
        rows = []
    declared: set[str] = set()
    receipt_errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            receipt_errors.append("invalid_core_entry_receipt")
            continue
        name = row["path"]
        declared.add(name)
        payload = payloads.get(name)
        if payload is None:
            receipt_errors.append(f"missing:{name}")
        elif row.get("bytes") != len(payload) or row.get("sha256") != sha256_bytes(payload):
            receipt_errors.append(f"identity_mismatch:{name}")
    expected = declared | GENERATED_CORE
    missing = sorted(expected - set(payloads))
    unexpected = sorted(set(payloads) - expected)
    if receipt_errors:
        errors.extend(f"core_receipt:{item}" for item in receipt_errors)
    if missing or unexpected:
        errors.append("return_exact_set_mismatch")
    return {
        "declared_core_count": len(declared),
        "generated_core_count": len(GENERATED_CORE),
        "actual_count": len(payloads),
        "missing": missing,
        "unexpected": unexpected,
        "receipt_errors": receipt_errors,
        "pass": not receipt_errors and not missing and not unexpected,
    }


def assignment(source: str, net: str) -> list[str]:
    no_comments = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*", "", source), flags=re.S)
    return [
        " ".join(match.group(1).split())
        for match in re.finditer(rf"assign\s+{re.escape(net)}\s*=\s*(.*?);", no_comments, re.S)
    ]


def indexed_assignment(source: str, net: str) -> list[str]:
    no_comments = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*", "", source), flags=re.S)
    return [
        " ".join(match.group(2).split())
        for match in re.finditer(
            rf"assign\s+{re.escape(net)}\s*\[\s*([^]]+)\s*\]\s*=\s*(.*?);",
            no_comments,
            re.S,
        )
    ]


def declaration_assignment(source: str, net: str) -> list[str]:
    no_comments = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*", "", source), flags=re.S)
    return [
        " ".join(match.group(1).split())
        for match in re.finditer(
            rf"\b(?:wire|logic)\b[^;=]*\b{re.escape(net)}\s*=\s*(.*?);",
            no_comments,
            re.S,
        )
    ]


def extract_selected(
    output_dir: Path,
    returned: dict[str, bytes],
    source: dict[str, bytes],
    errors: list[str],
) -> dict[str, Any]:
    evidence_dir = output_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=False)
    receipts: dict[str, Any] = {}
    for member, leaf in SELECTED_RETURN_EVIDENCE.items():
        payload = returned.get(member)
        if payload is None:
            errors.append(f"selected_evidence_missing:{member}")
            continue
        target = evidence_dir / leaf
        target.write_bytes(payload)
        receipts[member] = {
            "path": str(target.resolve()),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
    observer_member = "tb_probe/buffer_ack_portable_query_observer.svh"
    observer = source.get(observer_member)
    if observer is None:
        errors.append(f"source_observer_missing:{observer_member}")
    else:
        target = evidence_dir / "source_buffer_ack_portable_query_observer.svh"
        target.write_bytes(observer)
        receipts[f"source:{observer_member}"] = {
            "path": str(target.resolve()),
            "bytes": len(observer),
            "sha256": sha256_bytes(observer),
        }
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--local-rtl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    if args.return_zip.name != EXPECTED_RETURN_BASENAME:
        errors.append("return_basename_mismatch")
    if args.output_dir.exists():
        raise FileExistsError(f"analysis output already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)

    returned, return_archive = read_archive(args.return_zip, RETURN_ROOT, errors)
    source, source_archive = read_archive(args.source_zip, PACKAGE, errors)
    manifest = as_object(returned, "RETURN_CORE_MANIFEST.json", errors)
    exact_set = core_exact_set(returned, manifest, errors)

    source_manifest = source.get("package_manifest.json", b"")
    returned_manifest = returned.get("evidence/returned_package_manifest.json", b"")
    manifest_binding = bool(source_manifest) and returned_manifest == source_manifest
    if not manifest_binding:
        errors.append("returned_package_manifest_not_byte_equal_to_source")

    core = as_object(returned, "return_core/RETURN_CORE_STATUS.json", errors)
    sim = as_object(returned, "return_core/SIM_EXIT_RECEIPT.json", errors)
    result = as_object(returned, "evidence/SERVER_RESULT_GATE.json", errors)
    waveform = as_object(returned, "waveforms/WAVEFORM_RUNTIME_RECEIPT.json", errors)
    portable = as_object(returned, "waveforms/portable/PORTABLE_RUNTIME_RECEIPT.json", errors)
    portable_validation = as_object(
        returned, "waveforms/portable/PORTABLE_RUNTIME_VALIDATION.json", errors
    )
    query = as_object(returned, "waveforms/portable/SIGNAL_QUERY_RECEIPT.json", errors)
    phase = as_object(returned, "evidence/buffer_ack_phase_raw_preservation.json", errors)
    phase_decision = as_object(returned, "runs/c0/buffer_ack_phase_decision.json", errors)
    compile_source = as_object(
        returned, "evidence/compile_rootcause/compile_source_identity.json", errors
    )
    preprocessed = as_object(
        returned, "evidence/compiled_source/preprocessed_target_receipt.json", errors
    )
    drivers = as_object(
        returned, "evidence/compiled_source/elaborated_ack_driver_set.json", errors
    )

    actual_source_bytes = returned.get("evidence/compiled_source/actual_target_source.sv", b"")
    actual_source = actual_source_bytes.decode("utf-8", errors="replace")
    local_source_bytes = args.local_rtl.read_bytes()
    local_source = local_source_bytes.decode("utf-8", errors="replace")
    observer_bytes = source.get("tb_probe/buffer_ack_portable_query_observer.svh", b"")
    observer_source = observer_bytes.decode("utf-8", errors="replace")

    actual_public_equations = assignment(actual_source, "mse_buf_queue_bp_pre")
    local_public_equations = indexed_assignment(local_source, "mse_buf_queue_bp_pre")
    observer_inline = declaration_assignment(observer_source, "codex_inline_rhs")
    expected_actual = "{!row_fifo_full, !col_fifo_full}"
    expected_observer = "{2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask"
    expected_local = "(!buf_ag_idx_queue_full && buf_idx_bp_pre_mask[INPORT_IDX])"
    semantic_misbinding = (
        actual_public_equations == [expected_actual]
        and observer_inline == [expected_observer]
        and local_public_equations == [expected_local]
    )
    if not semantic_misbinding:
        errors.append("actual_source_to_observer_semantic_misbinding_not_reproduced")

    wave_rows = waveform.get("waveforms") if isinstance(waveform.get("waveforms"), list) else []
    vpd = next(
        (row for row in wave_rows if isinstance(row, dict) and row.get("format") == "VPD"),
        {},
    )
    vpd_member = returned.get("waveforms/run/sim_results/wave.vpd")
    vpd_identity_valid = bool(vpd_member) and vpd.get("bytes") == len(vpd_member) and vpd.get(
        "sha256"
    ) == sha256_bytes(vpd_member)
    if not vpd_identity_valid:
        errors.append("vpd_identity_binding_invalid")

    coverage = query.get("candidate_coverage") if isinstance(query.get("candidate_coverage"), dict) else {}
    expected_candidates = coverage.get("expected") if isinstance(coverage.get("expected"), list) else []
    covered_candidates = coverage.get("covered") if isinstance(coverage.get("covered"), list) else []
    missing_candidates = coverage.get("missing") if isinstance(coverage.get("missing"), list) else []
    capture = query.get("capture") if isinstance(query.get("capture"), dict) else {}

    tcl = returned.get("waveforms/portable/codex_wave_dump.tcl", b"").decode(
        "utf-8", errors="replace"
    )
    tcl_lines = tcl.splitlines()
    failed_vcd_command = next(
        (line for line in tcl_lines if "wave.vcd" in line and "-type VCD" in line), None
    )
    run_command_index = next(
        (index for index, line in enumerate(tcl_lines) if line.startswith("run ")), None
    )
    vcd_command_index = (
        tcl_lines.index(failed_vcd_command) if failed_vcd_command in tcl_lines else None
    )
    time_advance_unproven = all(
        (
            sim.get("sim_started") is True,
            sim.get("sim_exit_code") == 0,
            sim.get("natural_terminal_observed") is False,
            len(returned.get("runs/c0/sim.log", b"")) == 0,
            phase.get("event_count") == 0,
            phase_decision.get("live_event_count") == 0,
            not covered_candidates,
            portable.get("portable_vcd", {}).get("status") == "FAILED",
        )
    )

    evidence_receipts = extract_selected(args.output_dir, returned, source, errors)

    report = {
        "schema": "conv-node0004-v88b-formal-return-analysis-v1",
        "analysis_valid": not errors,
        "errors": errors,
        "role_id": "family.conv.serialized",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "previous_version_progress": (
            "v87b passed production compile and its execution-bound observer recorded an ACK public-output "
            "versus locally derived inline-RHS xor, while actual compiled-source identity, reset context, "
            "portable semantic decoding and the raw 65 phase rows remained unbound."
        ),
        "current_version_purpose": (
            "v88b was intended to bind the actual production source/preprocess/ACK drivers and return the "
            "same-attempt raw VPD, direct VCD, complete query/control evidence and all 65 phase rows."
        ),
        "identity": {
            "return_zip": {
                "path": str(args.return_zip.resolve()),
                "bytes": args.return_zip.stat().st_size,
                "sha256": sha256_file(args.return_zip),
                "basename_match": args.return_zip.name == EXPECTED_RETURN_BASENAME,
            },
            "source_package": {
                "path": str(args.source_zip.resolve()),
                "bytes": args.source_zip.stat().st_size,
                "sha256": sha256_file(args.source_zip),
            },
            "execution_id": sim.get("execution_id"),
            "execution_id_match": sim.get("execution_id") == EXPECTED_EXECUTION,
            "returned_package_manifest_byte_equal": manifest_binding,
            "return_archive": return_archive,
            "source_archive": source_archive,
            "return_exact_set": exact_set,
        },
        "compile_and_source": {
            "compile_exit": compile_source.get("compile_exit"),
            "production_elaboration_succeeded": drivers.get(
                "production_elaboration_succeeded"
            ),
            "production_elaboration_markers": drivers.get(
                "production_elaboration_markers"
            ),
            "target_in_filelist_closure": compile_source.get("target_in_filelist_closure"),
            "recursive_source_count": compile_source.get("recursive_source_count"),
            "actual_compile_defines": compile_source.get("compile_defines"),
            "actual_compile_includes": compile_source.get("compile_includes"),
            "actual_parameter_overrides": compile_source.get(
                "compile_parameter_overrides"
            ),
            "preprocess_complete_for_target_object_macros": preprocessed.get(
                "complete_for_target_object_macros"
            ),
            "actual_target": {
                "member": "evidence/compiled_source/actual_target_source.sv",
                "bytes": len(actual_source_bytes),
                "sha256": sha256_bytes(actual_source_bytes),
                "public_ack_equations": actual_public_equations,
            },
            "local_expected_target": {
                "path": str(args.local_rtl.resolve()),
                "bytes": len(local_source_bytes),
                "sha256": sha256_bytes(local_source_bytes),
                "public_ack_indexed_equations": local_public_equations,
            },
            "source_identity_match": actual_source_bytes == local_source_bytes,
            "collector_status": compile_source.get("status"),
            "collector_errors": compile_source.get("errors"),
            "collector_false_negative_reason": (
                "The collector required exactly one per-lane generate assignment, while the actual source "
                "has one vector assignment. The copied source and successful-elaboration binding remain "
                "usable; the collector's exact_set_complete=false is a package-tool assumption defect."
            ),
            "driver_receipt": drivers,
        },
        "simulation_and_termination": {
            "sim_process_invoked": sim.get("sim_started"),
            "sim_exit_code": sim.get("sim_exit_code"),
            "signal": sim.get("signal"),
            "natural_terminal": sim.get("natural_terminal_observed"),
            "effective_time_advance_proven": False,
            "time_advance_evidence_boundary": {
                "sim_log_bytes": len(returned.get("runs/c0/sim.log", b"")),
                "source_bound_log_bytes": len(
                    returned.get("runs/c0/source_bound_causal.log", b"")
                ),
                "phase_event_rows": phase.get("event_count"),
                "query_event_rows": len(query.get("events", []))
                if isinstance(query.get("events"), list)
                else None,
                "query_covered_candidates": len(covered_candidates),
                "all_end_states_unknown": all(
                    isinstance(row, dict)
                    and isinstance(row.get("value"), str)
                    and "x" in row["value"].lower()
                    for row in query.get("candidate_end_states", [])
                )
                if isinstance(query.get("candidate_end_states"), list)
                else False,
                "time_advance_unproven": time_advance_unproven,
            },
            "formal_d": "ABSENT_OR_NOT_CLAIMED",
            "E3": "NOT_REACHED_NO_NATURAL_TERMINAL",
            "E4": "NOT_REACHED_NO_FORMAL_D_AND_NO_NATURAL_TERMINAL",
            "E5": "NOT_REACHED",
        },
        "waveform_and_query": {
            "raw_vpd": {
                "present": vpd_member is not None,
                "identity_valid": vpd_identity_valid,
                "completeness": vpd.get("completeness"),
                "receipt_pass": waveform.get("pass"),
                "no_size_limit": waveform.get("no_size_limit"),
                "semantic_decoded": False,
            },
            "direct_vcd": {
                "present": "waveforms/portable/wave.vcd" in returned,
                "runtime_status": portable.get("portable_vcd", {}).get("status"),
                "validation_findings": portable_validation.get("diagnostic_findings"),
            },
            "registered_query": {
                "completeness": query.get("completeness"),
                "flush_complete": capture.get("flush_complete"),
                "expected_candidate_count": len(expected_candidates),
                "covered_candidate_count": len(covered_candidates),
                "missing_candidate_count": len(missing_candidates),
                "event_count": len(query.get("events", []))
                if isinstance(query.get("events"), list)
                else None,
            },
            "phase_rows": {
                "expected": phase.get("expected_event_count"),
                "actual": phase.get("event_count"),
                "complete_five_phase_sequences": phase.get(
                    "complete_five_phase_sequences"
                ),
                "pass": phase.get("pass"),
            },
            "positive_and_negative_controls": "NOT_OBSERVED_ZERO_QUERY_EVENTS",
            "same_attempt_binding": {
                "package_id": portable.get("package_id"),
                "execution_id": portable.get("execution_id"),
                "attempt_id": portable.get("attempt_id"),
                "raw_vpd_bound": vpd_identity_valid,
                "portable_derivatives_complete": False,
            },
        },
        "runtime_root_cause": {
            "classification": "PACKAGE_LOCAL_PORTABLE_UCLI_CONTROL_FAILURE_BEFORE_TIME_ADVANCE",
            "tcl_lines": tcl_lines,
            "first_suspect_command": failed_vcd_command,
            "first_suspect_command_index": vcd_command_index,
            "run_command_index": run_command_index,
            "causal_chain": [
                "production compile and elaboration succeeded",
                "simv/UCLI opened an authoritative VPD and emitted a partial raw file",
                "the next Tcl command requested direct VCD through `dump -file ... -type VCD`",
                "no direct VCD, time-0 marker, DUT log, query transition or phase row was produced",
                "the later `run` command is therefore not proven to have executed",
                "post-sim plugins correctly returned EVIDENCE_INCOMPLETE without suppressing raw/core evidence",
            ],
            "claim_strength": (
                "High-confidence package/runtime localization from exact command order and zero-event return. "
                "The exact UCLI diagnostic line is unavailable because the returned sim.log is empty."
            ),
        },
        "false_positive_adjudication": {
            "OBSERVER_OR_TB_FALSE_POSITIVE": "PROVEN_FOR_V88B_COMPARATOR_SEMANTICS",
            "SOURCE_IDENTITY_MISMATCH": "PROVEN_V88B_ACTUAL_VS_LOCAL_EXPECTED",
            "CONFIG_INDUCED_VALID_BEHAVIOR": (
                "STRUCTURALLY_ALLOWED_BY_ACTUAL_SOURCE_BUT_NOT_DYN_OBSERVED_IN_V88B"
            ),
            "FUNCTIONAL_RTL_DEFECT": "NOT_PROVEN",
            "actual_public_ack_equation": actual_public_equations,
            "observer_inline_equation": observer_inline,
            "semantic_misbinding_proven": semantic_misbinding,
            "reason": (
                "The observer compared two different predicates in the actual compiled design. A nonzero XOR "
                "can therefore be legal and cannot prove a public output violates its own driver equation."
            ),
            "v87_retroactive_boundary": (
                "v87b did not bind its actual compiled target bytes. v88b proves the comparator is invalid for "
                "the v88b production source; it does not prove the server source was byte-identical during v87b."
            ),
        },
        "configuration_workaround": {
            "CONFIG_WORKAROUND": "NONE",
            "reason": (
                "No existing config field makes the actual FIFO-full public ACK equation universally equal to "
                "the distinct buffer-index-queue predicate. Disabling or avoiding the path would change target "
                "transactions/coverage and would be diagnostic evasion, not a semantics-preserving workaround."
            ),
            "cost": "NOT_APPLICABLE_NO_PROVEN_FUNCTIONAL_RTL_DEFECT",
        },
        "causal_result": {
            "LAST_PROVEN_GOOD": (
                "production VCS compile/elaboration, source/filelist/include/define/preprocess capture, and "
                "raw partial-VPD publication"
            ),
            "FIRST_DIVERGENCE": (
                "portable UCLI control between opening the raw VPD and the first proven simulation-time advance"
            ),
            "HANG_ROOT_CAUSE": "NOT_A_PROVEN_DUT_HANG_PACKAGE_RUNTIME_STOP_BEFORE_TIME_ADVANCE",
            "natural_terminal": False,
            "formal_D": "NOT_OBSERVED",
        },
        "disposition": {
            "return_analysis": "EVIDENCE_INCOMPLETE_WITH_SOURCE_FALSE_POSITIVE_CLOSED",
            "family_rtl_state": "RTL_DEFECT_WITHDRAWN_NOT_PROVEN",
            "successor_justified": True,
            "successor_scope": [
                "fresh identity",
                "production-supported direct VCD control with explicit UCLI progress evidence",
                "actual-source ACK driver collector accepting vector or per-lane assigns",
                "ACK observer re-bound to the actual public driver equation",
                "same-attempt complete query/65 rows/reset/controls",
            ],
            "frozen": [
                "config",
                "numeric",
                "workload",
                "golden",
                "functional RTL",
            ],
            "local_terminal_state": "WAIT_SHARED_PORTABLE_VCD_METHOD_FIX",
            "blocker": (
                "The activated shared renderer/dispatch/validator hardcode the same `dump -file ... -type VCD` "
                "control that the real V88b production return failed. Family ownership does not include shared-"
                "method maintenance; rebuilding before shared activation would repeat or bypass the escaped gate."
            ),
        },
        "claim_boundary": (
            "No VPD semantic decode and no VCD/query transitions are claimed. Dynamic source-value, reset, "
            "natural-terminal and formal-D conclusions are limited to absence/incompleteness. The source mismatch "
            "and observer semantic misbinding are established from exact v88b compiled source and source-package "
            "observer bytes bound to successful production elaboration."
        ),
        "conflicts": [],
        "selected_evidence_receipts": evidence_receipts,
    }
    write_json(args.output, report)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
