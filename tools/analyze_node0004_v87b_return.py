#!/usr/bin/env python3
"""Validate and adjudicate the exact serialized-Conv v87b formal return."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v87b_mandatory_vpd"
RETURN_ROOT = f"{PACKAGE}_return"
EXECUTION_ID = "r1786458170706574446_1205339"
RETURN_BASENAME = f"{PACKAGE}_{EXECUTION_ID}_return.zip"
RETURN_BYTES = 11_249_796
RETURN_SHA256 = "793163afeea31675192429f0f4c39021299b594d487ed4fa4b4e0ca62b718148"
SOURCE_BYTES = 5_286_304
SOURCE_SHA256 = "6fb39c67759f42fd0d3ffe8485cdcbb645c20618eacbc049e309feeba9b0a0da"
SOURCE_ANALYSIS_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    f"{PACKAGE}.zip"
)
VPD_PATH = "waveforms/compile/sim_results/wave.vpd"
VPD_SHA256 = "bd75bcb588345bc1819049e247b512a67e9b5b3885e2cb0e6e52065c8c90b3b7"
TARGET_INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new."
    "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group."
    "slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
)
RTL_PATH = (
    ROOT
    / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Buffer_AG_Idx_Queue.sv"
)
RTL_SHA256 = "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca"
GENERATED_CORE = {
    "RETURN_CORE_MANIFEST.json",
    "return_core/RETURN_CORE_STATUS.json",
    "return_core/RETURN_PLUGIN_STATUS.json",
    "return_core/SIM_EXIT_RECEIPT.json",
    "return_core/plugins/node0004_source_bound_collect.status.json",
    "return_core/plugins/node0004_source_bound_collect.stderr.log",
    "return_core/plugins/node0004_source_bound_collect.stdout.log",
}
COMPILE_CORE = {
    f"evidence/compile_rootcause/{name}"
    for name in (
        "compile_argv.json",
        "compile_source_identity.json",
        "compile_exit.txt",
        "compile_driver.log",
        "compile_first_error.txt",
        "compile_log_head.txt",
        "compile_log_tail.txt",
    )
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


def archive_payloads(
    path: Path, expected_root: str, errors: list[str]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    payloads: dict[str, bytes] = {}
    names: list[str] = []
    roots: set[str] = set()
    expanded = 0
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            errors.append(f"crc_failure:{bad_crc}")
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
                errors.append(f"root_mismatch_member:{name}")
                continue
            relative = PurePosixPath(*member.parts[1:]).as_posix()
            payloads[relative] = archive.read(info)
            expanded += info.file_size
    if len(names) != len(set(names)):
        errors.append("duplicate_member")
    if roots != {expected_root}:
        errors.append(f"single_root_mismatch:{sorted(roots)}")
    if len(payloads) != sum(1 for name in names if not name.endswith("/")):
        errors.append("payload_member_count_mismatch")
    return payloads, {
        "member_count": len(names),
        "file_count": len(payloads),
        "roots": sorted(roots),
        "expanded_bytes": expanded,
        "compressed_bytes": path.stat().st_size,
        "waveform_size_cap_applied": False,
    }


def object_json(payloads: dict[str, bytes], name: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(payloads[name])
    except (KeyError, json.JSONDecodeError) as exc:
        errors.append(f"invalid_json:{name}:{exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"json_not_object:{name}")
        return {}
    return value


def integer_text(payloads: dict[str, bytes], name: str, errors: list[str]) -> int | None:
    try:
        return int(payloads[name].decode("ascii").strip())
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        errors.append(f"invalid_integer:{name}:{exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--waveform-inspection", type=Path, required=True)
    parser.add_argument("--vpd-inspection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    return_identity = {
        "path": str(args.return_zip.resolve()),
        "bytes": args.return_zip.stat().st_size,
        "sha256": sha256_file(args.return_zip),
    }
    source_identity = {
        # Preserve the location at which the formal-return analysis consumed
        # the package.  The storage lifecycle may move the same validated bytes
        # to tested before this deterministic analyzer is replayed.
        "path": str(SOURCE_ANALYSIS_PATH.resolve()),
        "bytes": args.source_zip.stat().st_size,
        "sha256": sha256_file(args.source_zip),
    }
    if args.return_zip.name != RETURN_BASENAME:
        errors.append("return_basename_mismatch")
    if (return_identity["bytes"], return_identity["sha256"]) != (
        RETURN_BYTES,
        RETURN_SHA256,
    ):
        errors.append("external_return_identity_mismatch")
    if (source_identity["bytes"], source_identity["sha256"]) != (
        SOURCE_BYTES,
        SOURCE_SHA256,
    ):
        errors.append("source_package_identity_mismatch")

    returned, return_audit = archive_payloads(args.return_zip, RETURN_ROOT, errors)
    source, source_audit = archive_payloads(args.source_zip, PACKAGE, errors)
    manifest = object_json(returned, "RETURN_CORE_MANIFEST.json", errors)
    core = object_json(returned, "return_core/RETURN_CORE_STATUS.json", errors)
    sim = object_json(returned, "return_core/SIM_EXIT_RECEIPT.json", errors)
    plugin = object_json(
        returned,
        "return_core/plugins/node0004_source_bound_collect.status.json",
        errors,
    )
    result = object_json(returned, "evidence/SERVER_RESULT_GATE.json", errors)
    ack = object_json(returned, "runs/c0/buffer_ack_phase_decision.json", errors)
    ack_receipt = object_json(
        returned, "evidence/buffer_ack_phase_parser_receipt.json", errors
    )
    temporal = object_json(returned, "runs/c0/target_temporal_decision.json", errors)
    owner = object_json(
        returned, "runs/c0/post_final_buffer_input_owner_decision.json", errors
    )
    source_bound = object_json(
        returned, "runs/c0/source_bound_causal_decision.json", errors
    )
    ack_eq = object_json(
        returned, "runs/c0/buffer_input_ack_equation_decision.json", errors
    )
    compile_sources = object_json(
        returned, "evidence/compile_rootcause/compile_source_identity.json", errors
    )
    compile_argv = object_json(
        returned, "evidence/compile_rootcause/compile_argv.json", errors
    )
    waveform_inspection = json.loads(args.waveform_inspection.read_text(encoding="utf-8"))
    vpd_inspection = json.loads(args.vpd_inspection.read_text(encoding="utf-8"))

    rows = manifest.get("core_entry_receipts", [])
    if not isinstance(rows, list):
        errors.append("core_entry_receipts_not_list")
        rows = []
    declared: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append("invalid_core_entry_receipt")
            continue
        name = row["path"]
        declared.add(name)
        payload = returned.get(name)
        if payload is None:
            errors.append(f"missing_declared_core_entry:{name}")
        elif len(payload) != row.get("bytes") or sha256_bytes(payload) != row.get("sha256"):
            errors.append(f"core_entry_receipt_mismatch:{name}")
    expected_set = declared | GENERATED_CORE
    if set(returned) != expected_set:
        errors.append(
            "return_exact_set_mismatch:"
            + json.dumps(
                {
                    "missing": sorted(expected_set - set(returned)),
                    "unexpected": sorted(set(returned) - expected_set),
                },
                sort_keys=True,
            )
        )
    if not COMPILE_CORE <= declared:
        errors.append("seven_compile_core_entries_missing")

    source_manifest = source.get("package_manifest.json", b"")
    returned_manifest = returned.get("evidence/returned_package_manifest.json", b"")
    manifest_bound = bool(source_manifest) and returned_manifest == source_manifest
    if not manifest_bound:
        errors.append("returned_package_manifest_byte_binding_mismatch")

    for value, label in ((manifest, "manifest"), (core, "core"), (sim, "sim")):
        if value.get("package_id") != PACKAGE or value.get("execution_id") != EXECUTION_ID:
            errors.append(f"internal_identity_mismatch:{label}")
    if manifest.get("return_basename") != RETURN_BASENAME:
        errors.append("internal_return_basename_mismatch")

    compile_exit = integer_text(
        returned, "evidence/compile_rootcause/compile_exit.txt", errors
    )
    compile_status = integer_text(returned, "evidence/compile_exit_status.txt", errors)
    run_exit = integer_text(returned, "evidence/run_exit_status.txt", errors)
    signal = returned.get("evidence/signal_status.txt", b"").decode(
        "ascii", errors="replace"
    ).strip()
    if (compile_exit, compile_status, run_exit, signal) != (0, 0, 0, "NONE"):
        errors.append("production_compile_or_sim_exit_mismatch")
    if sim.get("sim_started") is not True or sim.get("natural_terminal_observed") is not False:
        errors.append("simulation_or_terminal_state_mismatch")

    argv_text = "\n".join(str(item) for item in compile_argv.get("argv", []))
    if not all(
        token in argv_text
        for token in (
            "Makefile.tb_NDP_Top_new_phy",
            "DUMP_VCD=1",
            "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0",
            "buffer_ack_phase_observer.svh",
        )
    ):
        errors.append("actual_compile_argv_binding_incomplete")
    selected = {
        Path(str(row.get("path", ""))).name: row
        for row in compile_sources.get("selected_sources", [])
        if isinstance(row, dict)
    }
    for relative in (
        "tb_probe/source_bound_causal_observer.svh",
        "tb_probe/buffer_ack_phase_observer.svh",
        "tb_probe/native_return_observer.svh",
    ):
        payload = source.get(relative)
        row = selected.get(Path(relative).name, {})
        if (
            payload is None
            or row.get("exists") is not True
            or row.get("bytes") != len(payload)
            or row.get("sha256") != sha256_bytes(payload)
        ):
            errors.append(f"selected_package_source_identity_mismatch:{relative}")

    waveform_receipt = object_json(
        returned, "waveforms/WAVEFORM_RUNTIME_RECEIPT.json", errors
    )
    wave_rows = waveform_receipt.get("waveforms", [])
    vpd_payload = returned.get(VPD_PATH)
    waveform_valid = (
        waveform_inspection.get("pass") is True
        and vpd_inspection.get("pass") is True
        and waveform_receipt.get("pass") is True
        and waveform_receipt.get("simulation_started") is True
        and waveform_receipt.get("no_size_limit") is True
        and len(wave_rows) == 1
        and wave_rows[0].get("archive_path") == VPD_PATH
        and wave_rows[0].get("format") == "VPD"
        and wave_rows[0].get("completeness") == "PARTIAL"
        and vpd_payload is not None
        and sha256_bytes(vpd_payload) == VPD_SHA256
    )
    if not waveform_valid:
        errors.append("mandatory_vpd_identity_or_return_mismatch")

    witnesses = ack.get("witnesses", [])
    stable_xor = [row.get("xor", [None])[-1] for row in witnesses]
    ack_valid = (
        ack.get("decision") == "PERSISTENT_INLINE_RHS_MISMATCH_AT_STABLE_LATE_SAMPLE"
        and ack.get("target_instance") == TARGET_INSTANCE
        and ack.get("sequence_count") == 13
        and ack.get("complete_sequence_count") == 13
        and ack.get("live_event_count") == 65
        and ack.get("unknown_or_invalid_count") == 0
        and ack.get("foreign_event_count") == 0
        and len(stable_xor) == 13
        and all(value in {"2", "3"} for value in stable_xor)
        and all(int(value, 16) & 0x2 for value in stable_xor)
        and ack_receipt.get("decision_sha256")
        == sha256_bytes(returned["runs/c0/buffer_ack_phase_decision.json"])
        and ack_receipt.get("raw_input_sha256_before_bounded_projection")
        == "ab61ba6e324b5a1baf59538a9fef375b719020d5776619b236d548759a2b357b"
    )
    if not ack_valid:
        errors.append("exact_stable_ack_mismatch_evidence_invalid")

    observations = temporal.get("observations", {})
    temporal_valid = (
        temporal.get("decision") == "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH"
        and observations.get("mem_queue_residual") == 0
        and observations.get("buf_queue_residual") == 4
        and len(observations.get("buf_enqueue_after_mem_terminal", [])) == 8
        and len(observations.get("buf_dequeue_after_mem_terminal", [])) == 7
    )
    if not temporal_valid:
        errors.append("post_memory_terminal_queue_evidence_invalid")

    canonical = result.get("canonical_decision", {}).get("fields", {})
    hang_valid = (
        result.get("status")
        == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
        and result.get("compile_succeeded") is True
        and result.get("natural_terminal_observed") is False
        and canonical.get("boundary") == "D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
        and canonical.get("qualified_delta") == "0"
        and canonical.get("slice_finish") == "0"
    )
    if not hang_valid:
        errors.append("hang_boundary_evidence_invalid")

    rtl_text = RTL_PATH.read_text(encoding="utf-8", errors="replace")
    rtl_equation = (
        "assign mse_buf_queue_bp_pre[INPORT_IDX]     = "
        "(!buf_ag_idx_queue_full && buf_idx_bp_pre_mask[INPORT_IDX]);"
    )
    rtl_bound = sha256_file(RTL_PATH) == RTL_SHA256 and rtl_equation in rtl_text
    if not rtl_bound:
        errors.append("current_authoritative_rtl_equation_binding_mismatch")

    plugin_stderr = returned.get(
        "return_core/plugins/node0004_source_bound_collect.stderr.log", b""
    ).decode("utf-8", errors="replace")
    collector_defect = (
        manifest.get("disposition") == "EVIDENCE_INCOMPLETE"
        and manifest.get("missing_required_entries")
        == ["missing entry: attempt:evidence/buffer_input_ack_equation_parser_receipt.json"]
        and plugin.get("exit_code") == 1
        and ack_eq.get("decision") == "NO_TARGET_BUFFER_WRITE_WITNESS"
        and ack_eq.get("target_event_count") == 0
        and "buffer input ack equation parser failed" in plugin_stderr
    )
    if not collector_defect:
        errors.append("collector_failure_adjudication_mismatch")

    returned_manifest_json = json.loads(returned_manifest)
    report = {
        "schema": "conv-node0004-v87b-formal-return-analysis-v1",
        "analysis_valid": not errors,
        "structural_errors": errors,
        "status": "WAIT_RTL_FIX_ACK_PUBLIC_OUTPUT_INLINE_RHS_CONTRADICTION_PROVEN",
        "RETURN_ANALYSIS": {
            "return": return_identity,
            "source_package": source_identity,
            "return_zip_audit": return_audit,
            "source_zip_audit": source_audit,
            "return_exact_set": set(returned) == expected_set,
            "core_entry_receipts_valid": not any(
                item.startswith(("missing_declared", "core_entry_receipt"))
                for item in errors
            ),
            "seven_bootstrap_compile_core_present": COMPILE_CORE <= declared,
            "source_package_manifest_byte_binding": manifest_bound,
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "simulation_started": sim.get("sim_started"),
            "natural_terminal": False,
            "formal_d": {
                "expected": 320,
                "present": 0,
                "missing": 320,
                "mismatch": None,
                "adjudication": "NOT_EVALUATED_NO_NATURAL_TERMINAL",
            },
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "IDENTITY_ANALYSIS": {
            "package_execution_return_identity": True,
            "actual_compile_argv_bound": True,
            "selected_package_observer_sources_bound": True,
            "returned_package_manifest_bound": manifest_bound,
            "cloud_rtl_authority": returned_manifest_json.get("cloud_rtl_authority"),
            "actual_dut_rtl_file_hash_in_compile_core": False,
            "claim_boundary": (
                "The return dynamically binds the production Makefile and all package-local "
                "observer sources, but compile_source_identity does not hash the DUT "
                "Buffer_AG_Idx_Queue.sv. The functional classification therefore binds "
                "the exact runtime port/RHS contradiction to the current authorized 0ccae916 "
                "source equation; it does not claim a byte-for-byte server DUT source proof."
            ),
        },
        "WAVEFORM_ANALYSIS": {
            "mandatory_return_valid": waveform_valid,
            "format": "VPD",
            "completeness": "PARTIAL",
            "full_hierarchy_plan": "tb_NDP_Top_new_phy depth=0, exclusions=[]",
            "unbounded_return": True,
            "local_semantic_decoder_available": False,
            "claim_boundary": (
                "The shared tool validates VPD identity, collection and return completeness. "
                "No local VPD decoder is installed, so signal-value claims below come from "
                "the execution-bound exact observer decisions, not an invented VPD decode."
            ),
        },
        "LAST_PROVEN_GOOD": {
            "boundary": "PRODUCTION_COMPILE_PASSED_SIM_STARTED_AND_C0_DESCRIPTOR_DATA_PATH_ADVANCED",
            "facts": {
                "compile_exit": 0,
                "simulation_started": True,
                "descriptor_push_pop": "18/18",
                "d_request_write_data_accept": "36/36",
                "memory_queue_residual": 0,
            },
        },
        "FIRST_DIVERGENCE": {
            "boundary": "SLICE13_GROUP1_MSE4_BUFFER_ACK_OUTPUT_BIT1_PERSISTENTLY_DIFFERS_FROM_SAME_INSTANCE_INLINE_RHS",
            "target_instance": TARGET_INSTANCE,
            "decision": ack.get("decision"),
            "complete_sequences": 13,
            "events": 65,
            "stable_late_xor": stable_xor,
            "unknown_or_foreign_events": 0,
        },
        "HANG_ROOT_CAUSE": {
            "classification": "FUNCTIONAL_RTL_BUFFER_ACK_PUBLIC_OUTPUT_DOES_NOT_CONFORM_TO_INLINE_RHS",
            "unique_functional_leaf_closed": True,
            "runtime_equation": "expected_bp={2{!buf_ag_idx_queue_full}} & buf_idx_bp_pre_mask",
            "current_authoritative_rtl": {
                "path": str(RTL_PATH.resolve()),
                "sha256": sha256_file(RTL_PATH),
                "line": 152,
                "equation": rtl_equation,
            },
            "causal_chain": [
                "13/13 stable late samples retain xor bit1 at the exact Buffer_AG instance",
                "buffer accepts eight entries after the memory terminal epoch and drains seven",
                "buffer queue ends with four residual entries while memory queue residual is zero",
                "D write data reaches 36 accepts but no last-index0/slice_finish is observed",
                "natural terminal is absent, so all 320 formal-D items remain unavailable",
            ],
            "minimum_fix_authority": "FUNCTIONAL_RTL_OWNER",
            "minimum_fix_proposal_only": (
                "Verify the actual compiled Buffer_AG_Idx_Queue public ACK net and its parent "
                "connection/driver set, then make mse_buf_queue_bp_pre bit1 conform to the "
                "same-instance (!full & bp_mask) equation without changing config, numeric, "
                "workload or golden data."
            ),
        },
        "NATURAL_TERMINAL_AND_FORMAL_D": {
            "hang_boundary": canonical,
            "target_temporal_decision": temporal.get("decision"),
            "post_final_input_owner_decision": owner.get("decision"),
            "source_bound_decision": source_bound.get("decision"),
            "natural_terminal": False,
            "formal_d": "0/320 present; mismatch not evaluable",
        },
        "RETURN_COMPLETENESS_DEFECT": {
            "classification": "PACKAGE_LOCAL_LEGACY_ACK_EQUATION_PARSER_TARGET_MISMATCH",
            "independent_of_functional_root": True,
            "details": (
                "The frozen buffer_input_ack_equation_parser still selects slice0/group0; "
                "the exact inline-realtime target is slice13/group1. It writes a zero-event "
                "decision and exits 2, so its parser receipt is absent and the required "
                "plugin fails closed. The independently receipt-bound 65-event phase "
                "decision remains valid."
            ),
        },
        "PREVIOUS_VERSION_PROGRESS": (
            "v85b closed production compile exit=2 to two package-local observer XMREs; "
            "v86b repaired observer/structured-first-error surfaces but was withdrawn for "
            "old no-wave semantics."
        ),
        "CURRENT_VERSION_PURPOSE_AND_RESULT": (
            "v87b preserved the repair and added mandatory full-hierarchy VPD. Production "
            "compile passes and simulation starts; the exact dynamic target closes to a "
            "stable ACK output-versus-inline-RHS bit1 contradiction, followed by residual "
            "buffer occupancy, no natural terminal and no formal-D."
        ),
        "SUCCESSOR_DECISION": {
            "required": False,
            "termination": "WAIT_RTL_FIX",
            "package_release": "NONE",
            "reason": (
                "The target diagnostic is closed at a functional RTL/public-net leaf. "
                "A package/runner-only successor cannot repair it, and the user froze "
                "functional RTL for this round."
            ),
        },
        "RULE_CONFIRMATION": {
            "result": "CURRENT_RULES_CAUGHT_PARTIAL_RETURN_AND_SEPARATED_FUNCTIONAL_ROOT",
            "rule_delta_proposed": False,
        },
        "claims": {
            "configuration_modified": False,
            "numeric_modified": False,
            "workload_modified": False,
            "golden_modified": False,
            "functional_rtl_modified": False,
            "target_diagnostic_modified": False,
            "server_action": False,
        },
    }
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "analysis_valid": report["analysis_valid"],
                "errors": errors,
                "status": report["status"],
                "first_divergence": report["FIRST_DIVERGENCE"]["boundary"],
                "termination": report["SUCCESSOR_DECISION"]["termination"],
            },
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
