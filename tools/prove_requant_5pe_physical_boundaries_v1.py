#!/usr/bin/env python3
"""Read-only proof driver for the remaining Requant 5PE physical boundaries."""

from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import json
import math
import pathlib
import re
import shutil
import struct
import subprocess
import tempfile
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
RTL_ROOT = ROOT / "Trassic2.0_RTL"
NDP_SIM = ROOT / "ndp-sim"
INCLUDES = RTL_ROOT / "code/NDP_rtl/includes"
BST = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Binary_Search_Tree.sv"
COMPARATOR = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Comparator.sv"
INTERCONNECT = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group_Interconnect.sv"
CONNECT = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Connect.sv"
OUTPORT = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_Outport/GA_Outport_Connect.sv"
PARAMS = INCLUDES / "NDP_Parameters.svh"
INBUFFER = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv"
OUTBUFFER = RTL_ROOT / "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv"
CONTROL = NDP_SIM / "model_execplan/src/execution_plan_generator/control_registers.py"
REGISTRY = NDP_SIM / "address_remapping/src/address_remapping/registry.py"
EVIDENCE = ROOT / "contracts/operator_config/requant_quant_tail_evidence_input_v1.json"
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
BST_TB = ROOT / "tests/rtl/requant_sfu_duplicate_breakpoint_bst_tb.sv"
SELECTOR_TB = ROOT / "tests/rtl/requant_5pe_selector_backpressure_tb.sv"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def run(cmd: list[str], cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def git_identity(repo: pathlib.Path, paths: list[pathlib.Path]) -> dict[str, Any]:
    head = run(["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), "rev-parse", "HEAD"])
    if head.returncode:
        raise RuntimeError(head.stderr)
    result: dict[str, Any] = {"head": head.stdout.strip(), "files": {}}
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        current_blob = run(["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), "hash-object", rel])
        committed_blob = run(
            ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), "rev-parse", f"HEAD:{rel}"]
        )
        status = run(
            ["git", "-c", f"safe.directory={repo.as_posix()}", "-C", str(repo), "status", "--short", "--", rel]
        )
        result["files"][rel] = {
            "sha256": sha256(path),
            "current_byte_blob": current_blob.stdout.strip(),
            "head_blob": committed_blob.stdout.strip() if committed_blob.returncode == 0 else None,
            "byte_blob_equals_head_blob": (
                current_blob.returncode == 0
                and committed_blob.returncode == 0
                and current_blob.stdout.strip() == committed_blob.stdout.strip()
            ),
            "working_tree_status": status.stdout.strip(),
        }
    return result


def f32_from_bits(bits: int) -> float:
    return struct.unpack(">f", bits.to_bytes(4, "big"))[0]


def prove_bst_model() -> dict[str, Any]:
    sorted_breakpoints = [-256.0] * 32 + [256.0] * 33
    heap_rank_by_level = [
        [32],
        [16, 48],
        [8, 24, 40, 56],
        list(range(4, 64, 8)),
        list(range(2, 64, 4)),
        list(range(1, 64, 2)),
        [0, 64],
    ]
    samples = [
        0xFF7FFFFF,
        0xC3808000,
        0xC3800000,
        0xC37F0000,
        0x80000000,
        0x00000000,
        0x437F0000,
        0x43800000,
        0x43808000,
        0x7F7FFFFF,
    ]
    checks = []
    for bits in samples:
        value = f32_from_bits(bits)
        address = bisect.bisect_right(sorted_breakpoints, value)
        expected = 0 if value < -256.0 else 32 if value < 256.0 else 65
        checks.append(
            {
                "input_bits": f"0x{bits:08x}",
                "input_float32": value,
                "upper_bound_address": address,
                "expected_region_address": expected,
                "match": address == expected,
            }
        )
    return {
        "semantic": "upper_bound_rank_over_65_sorted_breakpoints_equality_goes_right",
        "sorted_breakpoints": {
            "rank_0_through_31": {"bits": "0xc3800000", "value": -256.0, "duplicate_count": 32},
            "rank_32_through_64": {"bits": "0x43800000", "value": 256.0, "duplicate_count": 33},
        },
        "heap_rank_by_pipeline_level": heap_rank_by_level,
        "reachable_addresses": [0, 32, 65],
        "coefficient_regions": {
            "0": {"slope": 0, "intercept": -256},
            "32": {"slope": 1, "intercept": 0},
            "65": {"slope": 0, "intercept": 256},
        },
        "representative_checks": checks,
        "all_representative_checks_match": all(item["match"] for item in checks),
        "domain": "finite_binary32_only_from_already_accepted_stage0_multiplier_output",
        "excluded": "NaN_or_infinity_comparator_semantics_not_claimed_and_not_reachable",
    }


def compile_and_run_tb(name: str, sources: list[pathlib.Path]) -> dict[str, Any]:
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        return {"name": name, "pass": False, "error": "iverilog_or_vvp_not_found"}
    with tempfile.TemporaryDirectory(prefix=f"{name}_") as td:
        binary = pathlib.Path(td) / f"{name}.vvp"
        compile_cmd = [iverilog, "-g2012", "-I", str(INCLUDES), "-s", name, "-o", str(binary)]
        compile_cmd.extend(str(path) for path in sources)
        compile_result = run(compile_cmd, ROOT)
        if compile_result.returncode:
            return {
                "name": name,
                "compile_exit_code": compile_result.returncode,
                "compile_stdout": compile_result.stdout,
                "compile_stderr": compile_result.stderr,
                "run_exit_code": None,
                "pass": False,
            }
        run_result = run([vvp, str(binary)], ROOT)
        return {
            "name": name,
            "compile_exit_code": compile_result.returncode,
            "compile_stdout": compile_result.stdout,
            "compile_stderr": compile_result.stderr,
            "run_exit_code": run_result.returncode,
            "run_stdout": run_result.stdout,
            "run_stderr": run_result.stderr,
            "pass": run_result.returncode == 0 and "PASS" in run_result.stdout,
        }


def require_fragments(path: pathlib.Path, fragments: list[str]) -> list[str]:
    text = read_text(path)
    return [fragment for fragment in fragments if fragment not in text]


def prove_selector_and_backpressure() -> dict[str, Any]:
    edges = [
        {
            "producer": "PE00",
            "consumer": "PE01",
            "consumer_inport": 0,
            "consumer_source_id": 4,
            "producer_destination_id": 4,
            "source_offset": [0, -1],
        },
        {
            "producer": "PE01",
            "consumer": "PE10",
            "consumer_inport": 0,
            "consumer_source_id": 3,
            "producer_destination_id": 7,
            "source_offset": [-1, 1],
        },
        {
            "producer": "PE10",
            "consumer": "PE11",
            "consumer_inport": 0,
            "consumer_source_id": 4,
            "producer_destination_id": 4,
            "source_offset": [0, -1],
        },
        {
            "producer": "PE11",
            "consumer": "PE12",
            "consumer_inport": 0,
            "consumer_source_id": 4,
            "producer_destination_id": 4,
            "source_offset": [0, -1],
        },
    ]
    missing = []
    missing.extend(
        require_fragments(
            INTERCONNECT,
            [
                "localparam int SRC_PE_ROW_OFFSET[`GA_PE_SRC_GA_PE_NUM] = '{-1, -1, -1,  0,  0};",
                "localparam int SRC_PE_COL_OFFSET[`GA_PE_SRC_GA_PE_NUM] = '{-1,  0,  1, -1,  1};",
                "ga_pe_bp_pre[DST_PE_ROW_IDX][DST_PE_COL_IDX][DST_PE_INPORT_IDX][DST_PE_BP_PRE_IDX]",
            ],
        )
    )
    missing.extend(
        require_fragments(
            CONNECT,
            [
                "ga_pe_inport[GA_PE_INPORT_IDX][ga_pe_src_id[GA_PE_INPORT_IDX]]",
                "assign ga_pe_connect_bp_pre = &ga_pe_bp_post;",
                "? ga_pe_ib2connect_bp_post[GA_PE_INPORT_IDX] : 1'b1;",
            ],
        )
    )
    missing.extend(
        require_fragments(
            OUTPORT,
            [
                "localparam GA_OUTPORT_ID  = GA_PE_ROW_ID + 4*(GA_COL_PE_NUM/2);",
                "localparam GA_OUTPORT_SRC = GA_COL_PE_NUM % 2;",
                "? ga_outport_bp_pre[GA_OUTPORT_ID] : 1'b1;",
            ],
        )
    )
    missing.extend(
        require_fragments(
            INBUFFER,
            [
                "ga_pe_inbuffer_tag[GA_PORT_IDX] <= {ga_pe_inport_valid_bit_masked[GA_PORT_IDX], ga_pe_inport_last_bit[GA_PORT_IDX], ga_pe_inport_last_index[GA_PORT_IDX]};",
                "assign ga_pe_alu_result_tag",
            ],
        )
    )
    missing.extend(
        require_fragments(
            OUTBUFFER,
            [
                "assign normal_mode_wr_tag        = {normal_mode_valid_bit, normal_mode_last_bit, normal_mode_last_index};",
                "assign ga_pe_outbuffer_port = { alu_op_is_transout ? ga_pe_transout_result_valid : ga_pe_outbuffer_valid_bit,",
            ],
        )
    )
    return {
        "pe_grid": [4, 4],
        "chain": ["PE00", "PE01", "PE10", "PE11", "PE12"],
        "edges": edges,
        "terminal_route": {
            "producer": "PE12",
            "coordinate": [1, 2],
            "outport_id": 5,
            "outport_source_id": 0,
        },
        "tag_scope": "full selected source tag reaches consumer; valid/last/last_index are retained by inbuffer and normal outbuffer",
        "backpressure_scope": (
            "selected source receives consumer backpressure; unselected sources return ready=1; "
            "terminal PE12 receives outport5 backpressure"
        ),
        "source_anchor_missing_fragments": missing,
        "static_equations_pass": not missing,
    }


def multiplier_supply() -> dict[str, Any]:
    evidence_doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    lowering_doc = json.loads(LOWERING.read_text(encoding="utf-8"))
    evidence = evidence_doc["stage_evidence"]
    lowering = [
        request
        for request in lowering_doc["requests"]
        if request["identity"]["hw_op_type"] == "RequantizeUint8"
    ]
    evidence_ids = [item["hw_op_id"] for item in evidence]
    lowering_ids = [request["identity"]["hw_op_id"] for request in lowering]
    counts = [math.prod(item["qparams"]["multiplier_shape"]) for item in evidence]
    shape_counts = collections.Counter(tuple(item["qparams"]["multiplier_shape"]) for item in evidence)
    invalid = []
    for item in evidence:
        qparams = item["qparams"]
        if not qparams["all_multiplier_finite_positive"]:
            invalid.append({"hw_op_id": item["hw_op_id"], "reason": "not_all_finite_positive"})
        if not re.fullmatch(r"[0-9a-f]{64}", qparams["multiplier_sha256"]):
            invalid.append({"hw_op_id": item["hw_op_id"], "reason": "invalid_multiplier_sha256"})
        if qparams["multiplier_minimum"] <= 0 or not math.isfinite(qparams["multiplier_maximum"]):
            invalid.append({"hw_op_id": item["hw_op_id"], "reason": "invalid_minmax"})
    control_text = read_text(CONTROL)
    registry_text = read_text(REGISTRY)
    mul_placeholder = (
        '"""Placeholder for prefill_mul_fp32MN_fp32M_fp32MN control register logic."""' in control_text
    )
    quant_placeholder = (
        '"""Placeholder for quant_from_buffer_int32MN_uint8MN control register logic."""' in control_text
    )
    mul_registered = '"prefill_mul_fp32MN_fp32M_fp32MN"' in registry_text
    quant_registered = '"quant_from_buffer_int32MN_uint8MN"' in registry_text
    node0001 = next(item for item in evidence if item["hw_op_id"] == "hwop-0001-01")
    identity_pass = (
        len(evidence) == 54
        and len(lowering) == 54
        and evidence_ids == lowering_ids
        and not invalid
    )
    supply_proven = (
        identity_pass
        and mul_registered
        and not mul_placeholder
        and quant_registered
        and not quant_placeholder
    )
    return {
        "typed_payload_identity": {
            "stage_count": len(evidence),
            "lowering_stage_count": len(lowering),
            "ordered_stage_ids_match": evidence_ids == lowering_ids,
            "all_hash_shape_minmax_finite_positive_valid": not invalid,
            "invalid_entries": invalid,
            "total_multiplier_elements": sum(counts),
            "multiplier_shape_histogram": {
                "x".join(str(x) for x in shape): count for shape, count in sorted(shape_counts.items())
            },
            "stages_with_at_least_two_distinct_values_from_minmax": sum(
                item["qparams"]["multiplier_minimum"] < item["qparams"]["multiplier_maximum"]
                for item in evidence
            ),
            "identity_pass": identity_pass,
        },
        "candidate_existing_primitive": {
            "name": "prefill_mul_fp32MN_fp32M_fp32MN",
            "address_remapping_registered": mul_registered,
            "control_handler_placeholder": mul_placeholder,
            "classification": "POTENTIAL_EXISTING_PRIMITIVE_BUT_UNBOUND",
        },
        "terminal_quant_primitive": {
            "name": "quant_from_buffer_int32MN_uint8MN",
            "address_remapping_registered": quant_registered,
            "control_handler_placeholder": quant_placeholder,
        },
        "minimal_fail_closed_counterexample": {
            "stage": "hwop-0001-01",
            "multiplier_shape": node0001["qparams"]["multiplier_shape"],
            "multiplier_minimum": node0001["qparams"]["multiplier_minimum"],
            "multiplier_maximum": node0001["qparams"]["multiplier_maximum"],
            "proof": (
                "minimum != maximum guarantees at least two required channel values; one fixed PE constant "
                "cannot supply both. A streamed operand could do so only after exact channel-axis, address, "
                "occurrence, broadcast/serialization, and lifetime binding is proven."
            ),
        },
        "physical_supply_proven": supply_proven,
        "first_unproven_capability": (
            "exact multiplier payload bits and channel axis are not bound to PE00 input1 for every "
            "spatial/sample occurrence; the current control handler is a placeholder"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/operator_config_validation/requant_5pe_physical_boundaries_v1/report.json",
    )
    args = parser.parse_args()

    bst_model = prove_bst_model()
    selector_model = prove_selector_and_backpressure()
    bst_rtl = compile_and_run_tb(
        "requant_sfu_duplicate_breakpoint_bst_tb",
        [BST_TB, BST, COMPARATOR],
    )
    selector_rtl = compile_and_run_tb(
        "requant_5pe_selector_backpressure_tb",
        [SELECTOR_TB],
    )
    multiplier = multiplier_supply()

    bst_anchors = require_fragments(
        BST,
        [
            "bst_search_addr_o <= 7'h00;",
            "bst_search_addr_o <= 7'h41;",
            "bst_search_addr_o <= (bst_search_addr_5<<1)+2;",
            "bst_search_addr_o <= (bst_search_addr_5<<1)+1;",
        ],
    ) + require_fragments(COMPARATOR, ["// GTET: data_a is greater than or equal to data_b"])
    bst_proven = (
        not bst_anchors
        and bst_model["all_representative_checks_match"]
        and bst_rtl["pass"]
    )
    selector_proven = selector_model["static_equations_pass"] and selector_rtl["pass"]
    structural_errors = []
    if not bst_proven:
        structural_errors.append("BST_PROOF_OR_RTL_TEST_FAILED")
    if not selector_proven:
        structural_errors.append("SELECTOR_TAG_BACKPRESSURE_PROOF_OR_RTL_TEST_FAILED")
    if not multiplier["typed_payload_identity"]["identity_pass"]:
        structural_errors.append("54_STAGE_MULTIPLIER_IDENTITY_MISMATCH")
    completion_blockers = []
    if not multiplier["physical_supply_proven"]:
        completion_blockers.append(
            {
                "id": "MULTIPLIER_SUPPLY_TYPED_ADDRESS_LIFETIME_UNPROVEN",
                "category": "PHYSICAL_MATERIALIZATION_CAPABILITY",
                "detail": multiplier["first_unproven_capability"],
            }
        )

    report: dict[str, Any] = {
        "schema": "requant-5pe-physical-boundaries-proof-v1",
        "status": (
            "BST_AND_SINGLE_OPERATOR_ROUTE_PROVEN__54_STAGE_MULTIPLIER_PHYSICAL_SUPPLY_BLOCKED"
            if not structural_errors and completion_blockers
            else "PROOF_INVALID"
        ),
        "mainline_thread_id": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "scope": {
            "accepted_numeric_dependency": (
                "full-INT32 5PE numeric graph: mul -> 3-region clamp[-256,256] -> "
                "magic -> intsub -> integer zp -> uint8"
            ),
            "numeric_dependency_recomputed": False,
            "strict_or_physical_claim": False,
            "server_or_package_action": False,
        },
        "source_identity": {
            "trassic": git_identity(
                RTL_ROOT,
                [PARAMS, BST, COMPARATOR, INTERCONNECT, CONNECT, OUTPORT, INBUFFER, OUTBUFFER],
            ),
            "ndp_sim": git_identity(NDP_SIM, [CONTROL, REGISTRY]),
            "contracts": {
                EVIDENCE.relative_to(ROOT).as_posix(): sha256(EVIDENCE),
                LOWERING.relative_to(ROOT).as_posix(): sha256(LOWERING),
            },
            "testbenches": {
                BST_TB.relative_to(ROOT).as_posix(): sha256(BST_TB),
                SELECTOR_TB.relative_to(ROOT).as_posix(): sha256(SELECTOR_TB),
            },
        },
        "duplicate_breakpoint_bst": {
            "proven": bst_proven,
            "source_anchor_missing_fragments": bst_anchors,
            "model": bst_model,
            "rtl_test": bst_rtl,
        },
        "single_operator_selector_tag_backpressure": {
            "proven": selector_proven,
            "model": selector_model,
            "source_bound_equation_test": selector_rtl,
            "test_kind": (
                "current RTL source anchors plus equivalent equation simulation; "
                "not a production-module elaboration claim"
            ),
        },
        "multiplier_supply_54_stage": multiplier,
        "structural_errors": structural_errors,
        "completion_blockers": completion_blockers,
        "blocked_valid": not structural_errors and bool(completion_blockers),
        "pass": not structural_errors and not completion_blockers,
        "blocker_delta": {
            "close_subleaves": [
                "B_REQUANT_5PE_DUPLICATE_BREAKPOINT_BST_ADDRESS",
                "B_REQUANT_5PE_SINGLE_OPERATOR_SELECTOR_TAG_BACKPRESSURE",
            ]
            if bst_proven and selector_proven
            else [],
            "keep_open": ["B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY"],
            "aggregate": "B_REQUANT_5PE_PHYSICAL_BST_SELECTOR_TAG_BACKPRESSURE_MULTIPLIER_SUPPLY",
            "aggregate_state": "OPEN_REFINED_TO_MULTIPLIER_SUPPLY_ONLY",
        },
        "claim_boundary": (
            "Read-only equation and focused RTL proof only. No strict JSON, mapping, bitstream, execplan, "
            "SCA, local physical E2, package, server run, E3, E4, or E5 claim. The accepted numeric 5PE "
            "graph is not recomputed or promoted."
        ),
        "rule_delta_proposal": {
            "status": "PROPOSAL",
            "proposed_id": "CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001",
            "text": (
                "Per-channel multiplier availability requires exact payload-bit/channel-axis binding to "
                "every materialized consumer occurrence, including address, broadcast or serialization, "
                "and lifetime. Hash/min/max/count evidence, registry presence, or a placeholder handler "
                "alone must not be promoted to physical supply."
            ),
        },
        "package_release": "NONE",
    }
    output = ROOT / args.output
    if pathlib.Path(args.output).is_absolute():
        output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        output_display = output.relative_to(ROOT).as_posix()
    except ValueError:
        output_display = str(output)
    print(json.dumps(
        {
            "report": output_display,
            "report_sha256": sha256(output),
            "status": report["status"],
            "structural_error_count": len(structural_errors),
            "completion_blocker_count": len(completion_blockers),
            "bst_proven": bst_proven,
            "selector_proven": selector_proven,
            "multiplier_identity_54_54": multiplier["typed_payload_identity"]["identity_pass"],
            "multiplier_physical_supply_proven": multiplier["physical_supply_proven"],
        },
        indent=2,
        sort_keys=True,
    ))
    return 0 if not structural_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
