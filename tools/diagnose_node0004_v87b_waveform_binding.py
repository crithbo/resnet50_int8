#!/usr/bin/env python3
"""Bind v87b's formal return to its VPD and emit the decoder evidence boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


PACKAGE = "r5_n4_hw_v87b_mandatory_vpd"
EXECUTION = "r1786458170706574446_1205339"
RETURN_ROOT = f"{PACKAGE}_return"
SOURCE_ROOT = PACKAGE
PLAN = "contracts/server_waveform_mandatory_plan.json"
RUNTIME_RECEIPT = "waveforms/WAVEFORM_RUNTIME_RECEIPT.json"
VPD = "waveforms/compile/sim_results/wave.vpd"
ACK_DECISION = "runs/c0/buffer_ack_phase_decision.json"
TEMPORAL_DECISION = "runs/c0/target_temporal_decision.json"
RESULT_GATE = "evidence/SERVER_RESULT_GATE.json"
EXPECTED_RETURN_SHA = "793163afeea31675192429f0f4c39021299b594d487ed4fa4b4e0ca62b718148"
EXPECTED_SOURCE_SHA = "6fb39c67759f42fd0d3ffe8485cdcbb645c20618eacbc049e309feeba9b0a0da"
EXPECTED_VPD_SHA = "bd75bcb588345bc1819049e247b512a67e9b5b3885e2cb0e6e52065c8c90b3b7"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def as_json(value: bytes) -> dict[str, Any]:
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ValueError("expected JSON object")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    return_sha = sha_file(args.return_zip)
    source_sha = sha_file(args.source_zip)
    if return_sha != EXPECTED_RETURN_SHA:
        errors.append("return_sha256_mismatch")
    if source_sha != EXPECTED_SOURCE_SHA:
        errors.append("source_sha256_mismatch")

    with zipfile.ZipFile(args.source_zip) as source_zip:
        plan_bytes = source_zip.read(f"{SOURCE_ROOT}/{PLAN}")
    with zipfile.ZipFile(args.return_zip) as return_zip:
        def member(relative: str) -> bytes:
            return return_zip.read(f"{RETURN_ROOT}/{relative}")

        runtime_bytes = member(RUNTIME_RECEIPT)
        vpd_bytes = member(VPD)
        core = as_json(member("RETURN_CORE_MANIFEST.json"))
        ack = as_json(member(ACK_DECISION))
        temporal = as_json(member(TEMPORAL_DECISION))
        result_gate = as_json(member(RESULT_GATE))

    plan = as_json(plan_bytes)
    runtime = as_json(runtime_bytes)
    plan_sha = sha_bytes(plan_bytes)
    vpd_sha = sha_bytes(vpd_bytes)
    runtime_wave = runtime.get("waveforms", [{}])[0]
    core_rows = {
        row.get("path"): row
        for row in core.get("core_entry_receipts", [])
        if isinstance(row, dict)
    }
    vpd_core = core_rows.get(VPD, {})
    receipt_core = core_rows.get(RUNTIME_RECEIPT, {})

    plan_valid = all((
        plan.get("package_id") == PACKAGE,
        plan.get("dump", {}).get("format") == "VPD",
        plan.get("dump", {}).get("hierarchy_depth") == 0,
        plan.get("dump", {}).get("included_scopes") == ["tb_NDP_Top_new_phy"],
        plan.get("dump", {}).get("excluded_scopes") == [],
        plan.get("dump", {}).get("make_arguments")
        == {"DUMP_FSDB": "0", "DUMP_VCD": "1", "TB_DUMP_FSDB": "0"},
        plan.get("return_policy", {}).get("hard_limit_bytes") is None,
        plan.get("return_policy", {}).get("collect_all_matching") is True,
        plan.get("return_policy", {}).get("truncation_allowed") is False,
    ))
    runtime_valid = all((
        runtime.get("package_id") == PACKAGE,
        runtime.get("execution_id") == EXECUTION,
        runtime.get("plan_sha256") == plan_sha,
        runtime.get("simulation_started") is True,
        runtime.get("no_size_limit") is True,
        runtime.get("all_matching_collected") is True,
        runtime.get("pass") is True,
        runtime_wave.get("archive_path") == VPD,
        runtime_wave.get("format") == "VPD",
        runtime_wave.get("completeness") == "PARTIAL",
        runtime_wave.get("sha256") == vpd_sha,
        runtime_wave.get("bytes") == len(vpd_bytes),
    ))
    core_valid = all((
        vpd_core.get("sha256") == vpd_sha,
        vpd_core.get("bytes") == len(vpd_bytes),
        vpd_core.get("required") is True,
        receipt_core.get("sha256") == sha_bytes(runtime_bytes),
        receipt_core.get("bytes") == len(runtime_bytes),
        receipt_core.get("required") is True,
    ))
    if not plan_valid:
        errors.append("source_waveform_plan_invalid")
    if not runtime_valid:
        errors.append("runtime_waveform_receipt_invalid")
    if not core_valid:
        errors.append("return_core_waveform_binding_invalid")
    if vpd_sha != EXPECTED_VPD_SHA:
        errors.append("vpd_identity_mismatch")

    witnesses = ack.get("witnesses", [])
    first_witness = min(
        (
            {
                "sequence": row.get("seq"),
                "phase": ack.get("phases", [])[index],
                "realtime_ns": row.get("realtimes", [])[index],
                "xor": row.get("xor", [])[index],
            }
            for row in witnesses
            for index in range(len(row.get("realtimes", [])))
            if int(row.get("xor", [])[index], 16) != 0
        ),
        key=lambda row: float(row["realtime_ns"]),
    )
    stable_late = [row["xor"][-1] for row in witnesses]
    observer_valid = all((
        ack.get("decision") == "PERSISTENT_INLINE_RHS_MISMATCH_AT_STABLE_LATE_SAMPLE",
        ack.get("complete_sequence_count") == 13,
        ack.get("live_event_count") == 65,
        ack.get("unknown_or_invalid_count") == 0,
        ack.get("foreign_event_count") == 0,
        len(stable_late) == 13,
        all(int(value, 16) & 0x2 for value in stable_late),
    ))
    if not observer_valid:
        errors.append("observer_dynamic_decision_invalid")

    tools = {name: shutil.which(name) for name in ("vpd2vcd", "verdi", "dve")}
    decoder_available = any(tools.values())
    observations = temporal.get("observations", {})
    canonical = result_gate.get("canonical_decision", {}).get("fields", {})

    output = {
        "schema": "conv-node0004-v87b-waveform-level-diagnosis-v1",
        "valid": not errors,
        "errors": errors,
        "identity_binding": {
            "return_zip": {
                "path": str(args.return_zip.resolve()),
                "bytes": args.return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "source_package": {
                "path": str(args.source_zip.resolve()),
                "bytes": args.source_zip.stat().st_size,
                "sha256": source_sha,
            },
            "plan": {
                "member": PLAN,
                "bytes": len(plan_bytes),
                "sha256": plan_sha,
                "valid": plan_valid,
            },
            "runtime_receipt": {
                "member": RUNTIME_RECEIPT,
                "bytes": len(runtime_bytes),
                "sha256": sha_bytes(runtime_bytes),
                "valid": runtime_valid,
            },
            "vpd": {
                "member": VPD,
                "bytes": len(vpd_bytes),
                "sha256": vpd_sha,
                "format": "VPD",
                "completeness": "PARTIAL",
                "core_receipt_valid": core_valid,
            },
            "chain": "source plan SHA == runtime plan_sha256; runtime VPD bytes/SHA == return-core receipt == ZIP member",
        },
        "waveform_capture_contract": {
            "scope": "tb_NDP_Top_new_phy",
            "depth": 0,
            "excluded_scopes": [],
            "make_arguments": plan["dump"]["make_arguments"],
            "unbounded": True,
            "all_shards_collected": True,
        },
        "decoder": {
            "available": decoder_available,
            "discovery": tools,
            "blocker_id": None if decoder_available else "VPD_SEMANTIC_DECODER_EXECUTABLE_NOT_AVAILABLE",
            "exact_missing_capability": None if decoder_available else (
                "A local read-only Synopsys VPD decoder/converter (vpd2vcd, verdi batch export, "
                "or an identity-bound shared equivalent) that can enumerate hierarchy and "
                "export selected signal transitions with exact simulation timestamps."
            ),
            "input_identity": {"sha256": vpd_sha, "bytes": len(vpd_bytes)},
        },
        "signal_level_result": {
            "source": "execution-bound exact observer decisions",
            "not_source": "VPD semantic decode",
            "first_observer_proven_divergence": {
                **first_witness,
                "boundary": "SLICE13_GROUP1_MSE4_BUFFER_ACK_OUTPUT_DIFFERS_FROM_SAME_INSTANCE_INLINE_RHS",
            },
            "stable_late_samples": {
                "count": len(stable_late),
                "xor_values": stable_late,
                "bit1_mismatch_count": sum(bool(int(value, 16) & 0x2) for value in stable_late),
            },
            "earliest_vpd_transition": (
                "UNRESOLVED_UNTIL_SHARED_CONVERTER_AVAILABLE"
                if not decoder_available else "DECODER_AVAILABLE_ANALYSIS_REQUIRED"
            ),
        },
        "causal_chain": {
            "exact_ack_target": ack.get("target_instance"),
            "ack_result": ack.get("decision"),
            "memory_terminal_result": temporal.get("decision"),
            "memory_queue_residual": observations.get("mem_queue_residual"),
            "buffer_queue_residual": observations.get("buf_queue_residual"),
            "buffer_enqueue_after_memory_terminal": len(
                observations.get("buf_enqueue_after_mem_terminal", [])
            ),
            "buffer_dequeue_after_memory_terminal": len(
                observations.get("buf_dequeue_after_mem_terminal", [])
            ),
            "canonical_hang_boundary": canonical.get("boundary"),
            "qualified_delta": canonical.get("qualified_delta"),
            "slice_finish": canonical.get("slice_finish"),
            "natural_terminal": False,
            "formal_d_present_expected": "0/320",
        },
        "classification": {
            "config": "RULED_OUT_FOR_THE_BOOLEAN_OUTPUT_VS_SAME_INPUT_RHS_CONTRADICTION",
            "package": (
                "INDEPENDENT_LEGACY_PARSER_TARGET_DEFECT_EXISTS; exact phase observer/decision "
                "remains receipt-bound and does not explain the stable public-net contradiction"
            ),
            "rtl": "FUNCTIONAL_RTL_OR_ACTUAL_COMPILED_SOURCE_PUBLIC_ACK_DRIVER_PATH",
            "terminal": "WAIT_RTL_FIX",
            "claim_boundary": (
                "The observer proves the runtime output/RHS contradiction and downstream stall. "
                "Without a semantic VPD decoder, it does not prove the globally earliest transition, "
                "enumerate the VPD driver cone, or independently confirm signal presence/value from "
                "the binary VPD. The compile-core also does not hash the actual server DUT RTL file."
            ),
        },
        "shared_converter_request": {
            "required": not decoder_available,
            "mode": "READ_ONLY_LOCAL_NO_SERVER",
            "required_outputs": [
                "converter executable identity and version",
                "input VPD bytes/SHA binding",
                "hierarchy/signal existence receipt",
                "time/value transitions in VCD/FST/CSV with timescale",
                "conversion log and exit status",
            ],
            "priority_signals": [
                f"{ack.get('target_instance')}.mse_buf_queue_bp_pre[1:0]",
                f"{ack.get('target_instance')}.buf_ag_idx_queue_full",
                f"{ack.get('target_instance')}.buf_idx_bp_pre_mask[1:0]",
                f"{ack.get('target_instance')}.buf_ag_idx_queue_wr_en",
            ],
            "priority_windows_ns": [
                "first output/RHS divergence before and through 2446109.000",
                "2446109.000 through 2446110.125 (first complete observer sequence)",
                "memory-terminal through final buffer activity around 2446448-2446473",
                "final canonical stall decision at 4084491.000",
            ],
        },
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "valid": output["valid"],
        "decoder_available": decoder_available,
        "blocker": output["decoder"]["blocker_id"],
        "first_observer_proven_divergence": first_witness,
        "terminal": output["classification"]["terminal"],
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
