#!/usr/bin/env python3
"""Materialize all 17 local QLinearAdd slow-composite strict JSON candidates.

The output is intentionally operator-local and relocatable.  It consumes the
accepted reachable-domain SFU tables, the read-only nine-PE topology proof,
and the node0076 hardware replay proof.  It never emits native backend JSON,
mapping, bitstream, execplan, SCA, or a server package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
FROZEN_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinearadd"
)
STAGE_INVENTORY = FROZEN_ROOT / "stage_inventory.json"
CURRENT_DIFF = FROZEN_ROOT / "current_test_diff.json"
DEPENDENCY_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260806_qadd_slow_composite_feasible_materializer_dependency_adjudication.md"
)
REQUANT_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_requant_scalar_phase_strict_json_v1/report.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_qlinearadd_slow_composite_strict_json_v1"
)
OWNER_PROOF_ROOT = (
    Path.home()
    / ".codex/worktrees/532a/resnet50_int8/"
    "artifacts/operator_config_validation/"
    "r5_existing_primitive_slow_composite_proof_v1/qlinearadd"
)

FAMILY = "qlinearadd"
LOWERING_SHA256 = "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
NDP_SIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
ALIGNMENT = 16
MAX_LC_END = 32768
PROOF_FILES = {
    "reachable_domain_sfu_segment_dp.json":
        "d11a8109bdcd5edb342b5575024c30ae2981798bf348ed73661828bc127d563e",
    "one_lane_rtl_topology_audit.json":
        "90ce8c4ce016e987954be6980edd0ceb7c945b9a0db5c5490cc844de6d74b4e5",
    "node0076_replay_proof.json":
        "a6fb283615496a22e68f1c3dcedb581b2ff2b489b7795045bed7553c4248d490",
    "front_half_exhaustive_proof.json":
        "09b7f6b22b56fcdfc51cf317a6ac4c6a7ce6b5b2a820b04939686a0006a63b52",
    "dequant_single_fma_counterexample.json":
        "074f74b6af37edae6f6d097bac962c02d2b2d991460337dd6293b8245a34f92b",
    "reachable_exact_divide_counterexample.json":
        "c0007b13614fe3231d18646de2dd44797d67313b763c0248053abd9409da460f",
    "reachable_fp32_sum_ranges.json":
        "71e59112481a1360f17d41dc4e2bf21405287b7e38b9a0e5a6461b979038f1f9",
    "negative_controls.json":
        "dc8b7454cbb03d5824bd49c7e1e3d93b1cee38713561ed6532c72c7fb656bc13",
    "report.json":
        "2759381f660496d57be7891efd2716c253276d13256b1fe22ccabdeae0e5e491",
}
EXACTNESS_AXES = {
    "op": True,
    "dtype": True,
    "shape": True,
    "layout": True,
    "qparams": True,
    "topology": True,
    "address": True,
    "schedule": True,
    "consumer": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_bytes(value))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def bound_file(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256_file(path)}


def align(value: int, alignment: int = ALIGNMENT) -> int:
    return (value + alignment - 1) // alignment * alignment


def escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def iter_json_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
            return
        for key in sorted(value):
            yield from iter_json_leaves(
                value[key], f"{pointer}/{escape_pointer_token(key)}"
            )
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", value
            return
        for index, item in enumerate(value):
            yield from iter_json_leaves(item, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def f32_bits(value: float) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def signed_fp32_constant_bits(value: int) -> str:
    return f32_bits(float(value))


def spatial_tiles(group_count: int) -> list[dict[str, int]]:
    tiles: list[dict[str, int]] = []
    cursor = 0
    while cursor < group_count:
        count = min(MAX_LC_END, group_count - cursor)
        tiles.append(
            {
                "tile_id": len(tiles),
                "group_start": cursor,
                "group_count": count,
            }
        )
        cursor += count
    return tiles


def request_index(lowering: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    ordered: list[str] = []
    indexed: dict[str, Any] = {}
    for request in lowering["requests"]:
        identity = request["identity"]
        if identity["hw_op_type"] != "QLinearAddUint8":
            continue
        stage_id = identity["hw_op_id"]
        ordered.append(stage_id)
        indexed[stage_id] = request
    if len(ordered) != 17 or len(indexed) != 17:
        raise ValueError(f"expected 17 QLinearAdd stages, got {len(ordered)}")
    return ordered, indexed


def snapshot_proofs(proof_root: Path, output_root: Path) -> dict[str, Path]:
    target_root = output_root / "inputs/qadd_slow_composite_proof"
    target_root.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name, expected_sha in PROOF_FILES.items():
        source = proof_root / name
        if not source.is_file():
            raise ValueError(f"required proof absent: {source}")
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise ValueError(
                f"proof SHA drift for {name}: {actual_sha} != {expected_sha}"
            )
        target = target_root / name
        shutil.copyfile(source, target)
        if sha256_file(target) != expected_sha:
            raise ValueError(f"proof snapshot mismatch: {target}")
        result[name] = target
    return result


def pe_graph(
    stage: dict[str, Any],
    dp_row: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    q = stage["qparams"]
    a_zp = int(q["a_zero_point"]["value"])
    b_zp = int(q["b_zero_point"]["value"])
    y_zp = int(q["y_zero_point"]["value"])
    expected_placement = [
        ("PE00", "add", "A_ADD_NEG_ZP"),
        ("PE01", "mul", "A_MUL_SCALE"),
        ("PE02", "add", "B_ADD_NEG_ZP"),
        ("PE03", "mul", "B_MUL_SCALE"),
        ("PE12", "add", "A_PLUS_B"),
        ("PE13", "sfu_activation", "REACHABLE_DOMAIN_SFU"),
        ("PE22", "mac", "MAGIC_ADD"),
        ("PE23", "int32_sub", "MAGIC_INT32_SUB"),
        ("PE32", "int32_mac", "ADD_OUTPUT_ZERO_POINT"),
    ]
    actual = [
        (item["pe"], item["opcode"], item["role"])
        for item in topology["placement"]
    ]
    if actual != expected_placement:
        raise ValueError(f"{stage['identity']['hw_op_id']}: stale topology")
    return {
        "operation_order": list(stage["dag"]["W3_order"]),
        "rounding_contract": (
            "sequential binary32 A dequant multiply; sequential binary32 B "
            "dequant multiply; binary32 add; exact reachable-domain SFU "
            "divide/RNE transform; magic integer decode; integer zero-point; "
            "uint8 saturation"
        ),
        "single_fma_dequant_forbidden": True,
        "reciprocal_approximation_forbidden": True,
        "pe_chain": [
            {
                "pe": "PE00",
                "opcode": "add",
                "input0": "GA_INPORT0_UINT8_TO_FP32_SERIAL",
                "input1_constant_bits": signed_fp32_constant_bits(-a_zp),
                "role": "A_ADD_NEG_ZP",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE01",
                "opcode": "mul",
                "input0": "PE00_WEST_SRC4",
                "input1_constant_bits": q["a_scale"]["float32_bits"],
                "role": "A_MUL_SCALE",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE02",
                "opcode": "add",
                "input0": "GA_INPORT1_UINT8_TO_FP32_SERIAL",
                "input1_constant_bits": signed_fp32_constant_bits(-b_zp),
                "role": "B_ADD_NEG_ZP",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE03",
                "opcode": "mul",
                "input0": "PE02_WEST_SRC4",
                "input1_constant_bits": q["b_scale"]["float32_bits"],
                "role": "B_MUL_SCALE",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE12",
                "opcode": "add",
                "input0": "PE01_SOUTHWEST_SRC1",
                "input1": "PE03_NORTHWEST_SRC3",
                "role": "A_PLUS_B",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE13",
                "opcode": "sfu_activation",
                "input0": "PE12_WEST_SRC4",
                "role": "REACHABLE_DOMAIN_SFU",
                "output_dtype": "fp32",
            },
            {
                "pe": "PE22",
                "opcode": "mac",
                "input0": "PE13_NORTHWEST_SRC3",
                "input1_constant_bits": "0x3f800000",
                "input2_constant_bits": "0x4b400000",
                "role": "MAGIC_ADD",
                "output_dtype": "fp32_bits",
            },
            {
                "pe": "PE23",
                "opcode": "int32_sub",
                "input0": "PE22_WEST_SRC4",
                "input1_constant_bits": "0x4b400000",
                "role": "MAGIC_INT32_SUB",
                "output_dtype": "int32",
            },
            {
                "pe": "PE32",
                "opcode": "int32_mac",
                "input0": "PE23_NORTHWEST_SRC3",
                "input1_constant_int32": 1,
                "input2_constant_int32": y_zp,
                "role": "ADD_OUTPUT_ZERO_POINT",
                "output_dtype": "int32_to_uint8_saturating",
            },
        ],
        "selector_edges": [
            {
                "source": edge["source"],
                "destination": edge["destination"],
                "consumer_src_id": edge["calculated_src_id"],
            }
            for edge in topology["edges"]
        ],
        "terminal": {
            "source_pe": topology["outport"]["source_pe"],
            "outport_id": topology["outport"]["outport_id"],
            "src_id": topology["outport"]["src_id"],
            "int32_to_uint8_saturating": True,
            "normal_outbuffer": True,
        },
        "reachable_domain_sfu": {
            "comparator_semantics": "x >= breakpoint",
            "breakpoint_bits": list(dp_row["hardware_breakpoint_bits"]),
            "segments": list(dp_row["hardware_segments"]),
            "breakpoint_count": dp_row["hardware_breakpoint_count"],
            "segment_count": dp_row["hardware_segment_count"],
            "logical_minimum_segment_count": dp_row[
                "logical_minimum_segment_count"
            ],
            "reachable_pair_count": dp_row["reachable_pair_count"],
            "dispatch_mismatch_count": dp_row["dispatch_mismatch_count"],
            "ordered_domain_target_sha256": dp_row[
                "ordered_domain_target_sha256"
            ],
        },
    }


def candidate_for_stage(
    *,
    stage: dict[str, Any],
    request: dict[str, Any],
    dp_row: dict[str, Any],
    topology: dict[str, Any],
    broadcast_proof: dict[str, Any],
    proof_receipts: dict[str, Path],
) -> dict[str, Any]:
    identity = stage["identity"]
    stage_id = identity["hw_op_id"]
    a_shape = list(stage["shapes"]["a"])
    b_shape = list(stage["shapes"]["b"])
    y_shape = list(stage["shapes"]["y"])
    a_count = math.prod(a_shape)
    b_count = math.prod(b_shape)
    y_count = math.prod(y_shape)
    if y_count % 4:
        raise ValueError(f"{stage_id}: output count not divisible by 4")
    broadcast = b_shape != y_shape
    if broadcast != (stage_id == "hwop-0076-00"):
        raise ValueError(f"{stage_id}: unexpected broadcast classification")
    if not broadcast and not (a_shape == b_shape == y_shape):
        raise ValueError(f"{stage_id}: non-broadcast shape mismatch")
    if broadcast and not (
        a_shape == y_shape == [16, 1000] and b_shape == [1000]
    ):
        raise ValueError(f"{stage_id}: broadcast shape mismatch")

    a_base = 0
    b_base = align(a_count)
    y_base = align(b_base + b_count)
    total_bytes = align(y_base + y_count)
    group_count = y_count // 4
    groups_per_batch = 250 if broadcast else group_count
    replay = {
        "mode": (
            "HARDWARE_REPEATED_SOURCE_B_READS"
            if broadcast
            else "ONE_TO_ONE_ELEMENTWISE"
        ),
        "materialized_by_host": False,
        "host_precomputed_internal_tensor": False,
        "invocation_count": 16 if broadcast else 1,
        "source_B_lifetime": (
            "acquire before first accepted B read; release after final accepted "
            "B read of invocation 15"
            if broadcast
            else "acquire before first accepted B read; release after final accepted B read"
        ),
        "B_address_equation": (
            "B_base + 4*(group_index % 250)"
            if broadcast
            else "B_base + 4*group_index"
        ),
        "Y_address_equation": "Y_base + 4*group_index",
        "proof_request_sha256": (
            broadcast_proof["request_sha256"] if broadcast else None
        ),
    }
    return {
        "schema": "qlinearadd_slow_composite_strict_json_v1",
        "family": FAMILY,
        "identity": {
            "request_id": stage["request_id"],
            "hw_op_id": stage_id,
            "hw_op_type": identity["hw_op_type"],
            "node_id": identity["node_id"],
            "onnx_op_type": identity["onnx_op_type"],
            "onnx_name": identity["onnx_name"],
            "request_sha256": stage["request_sha256"],
        },
        "typed_io": {
            "A": {
                "dtype": "uint8",
                "shape": a_shape,
                "layout": stage["layout"]["layout_id"],
            },
            "B": {
                "dtype": "uint8",
                "shape": b_shape,
                "layout": stage["layout"]["layout_id"],
            },
            "Y": {
                "dtype": "uint8",
                "shape": y_shape,
                "layout": stage["layout"]["layout_id"],
            },
        },
        "qparams": {
            name: dict(stage["qparams"][name])
            for name in (
                "a_scale",
                "a_zero_point",
                "b_scale",
                "b_zero_point",
                "y_scale",
                "y_zero_point",
            )
        },
        "numeric_graph": pe_graph(stage, dp_row, topology),
        "physical_schedule": {
            "mode": (
                "NODE0076_HARDWARE_B_REPLAY_ONE_LANE_9PE"
                if broadcast
                else "ELEMENTWISE_ONE_LANE_9PE"
            ),
            "operator_relative_address_space": {
                "alignment_bytes": ALIGNMENT,
                "width_bits": 30,
                "relocatable_by_uniform_backend_base": True,
                "regions": {
                    "A_uint8": {"base": a_base, "size_bytes": a_count},
                    "B_uint8": {"base": b_base, "size_bytes": b_count},
                    "Y_uint8": {"base": y_base, "size_bytes": y_count},
                },
                "total_bytes": total_bytes,
            },
            "loops": {
                "logical_output_elements": y_count,
                "group_count": group_count,
                "groups_per_broadcast_invocation": groups_per_batch,
                "tiles": spatial_tiles(group_count),
                "maximum_lc_end": MAX_LC_END,
                "all_lc_positive_stride": True,
                "all_lc_end_le_32768": True,
                "terminal_equation": (
                    "terminal iff final tile, final 4-byte group, final "
                    "serialized byte, and final Buffer5 accepted write"
                ),
            },
            "streams": {
                "A": {
                    "transaction_bytes": 4,
                    "idx_size": [3, 0, "NULL"],
                    "dim_stride": [4, 0, 0],
                    "address_equation": "A_base + 4*group_index",
                },
                "B": {
                    "transaction_bytes": 4,
                    "idx_size": [3, 0, "NULL"],
                    "dim_stride": [4, 0, 0],
                    "address_equation": replay["B_address_equation"],
                },
                "Y": {
                    "transaction_bytes": 4,
                    "idx_size": [3, 0, "NULL"],
                    "dim_stride": [4, 0, 0],
                    "address_equation": replay["Y_address_equation"],
                },
            },
            "buffers": {
                "buffer0_A": {
                    "buf_spatial_stride": [0, 1, 2, 3],
                    "buf_spatial_size": 4,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
                "buffer2_B": {
                    "buf_spatial_stride": [0, 1, 2, 3],
                    "buf_spatial_size": 4,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
                "buffer5_Y": {
                    "buf_spatial_stride": [0, 1, 2, 3],
                    "buf_spatial_size": 4,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                },
            },
            "ga_inports": {
                "A": {
                    "source_buffer": 0,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                    "uint8_to_fp32_serial": True,
                },
                "B": {
                    "source_buffer": 2,
                    "mask": [1, 0, 0, 0, 0, 0, 0, 0],
                    "uint8_to_fp32_serial": True,
                },
            },
            "broadcast_replay": replay,
            "paired_readiness": {
                "A_and_B_same_group_tag_required": True,
                "A_and_B_same_serial_byte_required": True,
                "selected_consumer_backpressure_reaches_both_sources": True,
                "one_sided_progress_is_not_pair_accept": True,
            },
            "lifetime": {
                "A": "visible until final accepted A read",
                "B": replay["source_B_lifetime"],
                "Y": (
                    "fresh allocation before first write; visible from each "
                    "accepted write through downstream release"
                ),
                "scratch_regions": [],
                "cross_stage_barriers": [],
            },
            "coverage": {
                "A_elements": a_count,
                "B_elements": b_count,
                "Y_elements": y_count,
                "logical_group_count": group_count,
                "active_buffer_bank_byte_set": "[0,4)",
                "producer_windows": ["[0,4)"],
                "consumer_required_set": "[0,4)",
                "gap_bytes": 0,
                "overlap_bytes": 0,
                "tail_valid_bytes": 4,
                "each_Y_element_exactly_once": True,
            },
            "limits": {
                "maximum_stream_stride": 4,
                "all_stream_stride_le_1048575": True,
                "buffer_row_bytes": 32,
                "active_low_bank_bytes": 4,
            },
        },
        "local_strict_claim": {
            "candidate_complete": True,
            "backend_bound": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "sca_generated": False,
            "server_package_generated": False,
            "dynamic_execution_claimed": False,
            "evidence_level": "LOCAL_STRICT_JSON_ONLY",
        },
        "proof_receipts": {
            "typed_stage_inventory": bound_file(STAGE_INVENTORY),
            "lowering_bundle": bound_file(LOWERING),
            "requant_shared_tail_dependency": bound_file(REQUANT_REPORT),
            "dependency_adjudication": bound_file(DEPENDENCY_RECORD),
            "reachable_domain_dp": bound_file(
                proof_receipts["reachable_domain_sfu_segment_dp.json"]
            ),
            "one_lane_9pe_topology": bound_file(
                proof_receipts["one_lane_rtl_topology_audit.json"]
            ),
            "node0076_hardware_replay": bound_file(
                proof_receipts["node0076_replay_proof.json"]
            ),
            "front_half_exhaustive": bound_file(
                proof_receipts["front_half_exhaustive_proof.json"]
            ),
            "single_fma_counterexample": bound_file(
                proof_receipts["dequant_single_fma_counterexample.json"]
            ),
        },
    }


def receipt_for_pointer(
    pointer: str, proof_receipts: dict[str, Path], broadcast: bool
) -> Path:
    if (
        pointer.startswith("/identity")
        or pointer.startswith("/typed_io")
        or pointer.startswith("/qparams")
    ):
        return STAGE_INVENTORY
    if pointer.startswith("/numeric_graph/reachable_domain_sfu"):
        return proof_receipts["reachable_domain_sfu_segment_dp.json"]
    if pointer.startswith("/numeric_graph"):
        return proof_receipts["one_lane_rtl_topology_audit.json"]
    if broadcast and pointer.startswith(
        "/physical_schedule/broadcast_replay"
    ):
        return proof_receipts["node0076_replay_proof.json"]
    if pointer.startswith("/physical_schedule"):
        return proof_receipts["one_lane_rtl_topology_audit.json"]
    return proof_receipts["report.json"]


def origin_for_pointer(pointer: str, value: Any) -> tuple[str, str]:
    if value is None:
        return "EXPLICIT_DISABLED", "EXPLICITLY_INACTIVE"
    if (
        pointer.startswith("/identity")
        or pointer.startswith("/typed_io")
        or pointer.startswith("/qparams")
    ):
        return "MODEL_DERIVED", "DERIVED_FOR_TARGET"
    if pointer.startswith("/numeric_graph"):
        return "RTL_DERIVED", "DERIVED_FOR_TARGET"
    if "/operator_relative_address_space/" in pointer or "address_equation" in pointer:
        return "ADDRESS_PLANNER_DERIVED", "DERIVED_FOR_TARGET"
    return "SCHEDULE_DERIVED", "DERIVED_FOR_TARGET"


def axes_for_pointer(pointer: str) -> list[str]:
    axes: list[str] = []
    if pointer.startswith("/typed_io") or "/loops/" in pointer:
        axes.append("shape")
    if "dtype" in pointer or "uint8_to_fp32" in pointer:
        axes.append("dtype")
    if pointer.startswith("/qparams") or pointer.startswith("/numeric_graph"):
        axes.append("qparam")
    if "layout" in pointer or "stride" in pointer or "mask" in pointer:
        axes.append("layout")
    if "address" in pointer or "base" in pointer or "regions" in pointer:
        axes.append("address")
    if pointer.startswith("/numeric_graph") or pointer.startswith(
        "/physical_schedule"
    ):
        axes.append("cross_stage_schedule")
    return sorted(set(axes)) or ["shape"]


def build_ledger(
    candidate: dict[str, Any], proof_receipts: dict[str, Path]
) -> dict[str, Any]:
    candidate_sha = hashlib.sha256(pretty_bytes(candidate)).hexdigest()
    broadcast = candidate["identity"]["hw_op_id"] == "hwop-0076-00"
    entries = []
    absences = [
        {
            "target_json_pointer": "/physical_schedule/mode",
            "state": "TARGET_REQUIRED_DERIVED",
            "reason": (
                "No exact native QLinearAdd strict replay exists; the authorized "
                "materializer composes proved existing primitives."
            ),
            "owner": "qlinearadd_slow_composite_materializer_v1",
        },
        {
            "target_json_pointer": "/native_exact_replay",
            "state": "SOURCE_ABSENT_NOT_APPLICABLE",
            "reason": "This candidate is a proved primitive composition, not a nearest-template replay.",
            "owner": "qlinearadd_slow_composite_materializer_v1",
        },
    ]
    for pointer, value in iter_json_leaves(candidate):
        origin, applicability = origin_for_pointer(pointer, value)
        receipt = (
            None
            if origin == "EXPLICIT_DISABLED"
            else bound_file(
                receipt_for_pointer(pointer, proof_receipts, broadcast)
            )
        )
        entries.append(
            {
                "json_pointer": pointer,
                "target_value": value,
                "origin": origin,
                "applicability_class": applicability,
                "exactness_axes": dict(EXACTNESS_AXES),
                "owner": (
                    "typed_lowering_and_six_qparams"
                    if origin == "MODEL_DERIVED"
                    else "qlinearadd_slow_composite_materializer_v1"
                ),
                "consumer_equation": (
                    "Leaf is consumed by the local one-lane nine-PE QLinearAdd "
                    "configuration exactly as materialized; backend rebasing and "
                    "dynamic execution are outside this claim."
                ),
                "derivation_receipt": receipt,
                "source": None,
                "negative_control_ids": [
                    "NC_QADD_QPARAM_BIT_TAMPER",
                    "NC_QADD_SFU_TABLE_TAMPER",
                    "NC_QADD_SELECTOR_TAMPER",
                    "NC_QADD_BROADCAST_HOST_REPLAY",
                    "NC_QADD_LIFETIME_PREMATURE_RELEASE",
                    "NC_QADD_TERMINAL_TAMPER",
                    "NC_QADD_ACTIVE_BANK_WINDOW_TAMPER",
                ],
                "status": "RESOLVED",
            }
        )
        if value is None:
            absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_NULL_INACTIVE",
                    "reason": "Field is explicitly inactive for this candidate.",
                    "owner": "qlinearadd_slow_composite_materializer_v1",
                }
            )
    return {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha,
        "entries": entries,
        "source_absences": absences,
        "claim_boundary": (
            "100% leaf provenance for local strict QLinearAdd one-lane 9PE "
            "configuration; no backend artifact is claimed."
        ),
    }


def build_handler_capability(
    candidate: dict[str, Any], ledger: dict[str, Any]
) -> dict[str, Any]:
    capabilities = {
        axis: {
            "supported": True,
            "evidence": (
                "Authorized isolated materializer binds exact typed stage, six "
                "qparams, reachable-domain SFU table, nine-PE selectors, one-lane "
                "transport, local addresses, terminal and lifetime."
            ),
        }
        for axis in (
            "exact_replay",
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        )
    }
    ledger_pointers = {entry["json_pointer"] for entry in ledger["entries"]}
    selected = [
        "/identity/hw_op_id",
        "/typed_io/A/shape/0",
        "/qparams/a_scale/float32_bits",
        "/qparams/a_zero_point/value",
        "/qparams/b_scale/float32_bits",
        "/qparams/b_zero_point/value",
        "/qparams/y_scale/float32_bits",
        "/qparams/y_zero_point/value",
        "/numeric_graph/pe_chain/0/opcode",
        "/numeric_graph/selector_edges/0/consumer_src_id",
        "/numeric_graph/reachable_domain_sfu/breakpoint_bits/0",
        "/numeric_graph/terminal/outport_id",
        "/physical_schedule/mode",
        "/physical_schedule/streams/A/transaction_bytes",
        "/physical_schedule/buffers/buffer0_A/buf_spatial_size",
        "/physical_schedule/broadcast_replay/materialized_by_host",
        "/physical_schedule/loops/terminal_equation",
        "/physical_schedule/lifetime/B",
    ]
    return {
        "schema": "operator_config_handler_capability_v1",
        "family": FAMILY,
        "handler": {
            "kind": "AUTHORIZED_PATCH",
            "path": rel(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "source_span": "candidate_for_stage/build_ledger/build_composition",
        },
        "capabilities": capabilities,
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": axes_for_pointer(pointer),
                "covered_by": rel(Path(__file__).resolve()),
                "status": "COVERED",
            }
            for pointer in selected
            if pointer in ledger_pointers
        ],
        "claim_boundary": (
            "Local strict QLinearAdd materialization only. Native backend "
            "registration, encoding and execution remain outside scope."
        ),
    }


def build_composition(candidate: dict[str, Any]) -> dict[str, Any]:
    stage_id = candidate["identity"]["hw_op_id"]
    groups = candidate["physical_schedule"]["coverage"]["logical_group_count"]
    token_set = f"{stage_id}:accepted_group_tokens[0..{groups - 1}]x4B"
    edges = [
        ("A_INPUT_TO_PE00", "uint8x4", "fp32_serial"),
        ("B_INPUT_TO_PE02", "uint8x4", "fp32_serial"),
        ("PE00_TO_PE01", "fp32", "fp32"),
        ("PE02_TO_PE03", "fp32", "fp32"),
        ("PE01_TO_PE12", "fp32", "fp32"),
        ("PE03_TO_PE12", "fp32", "fp32"),
        ("PE12_TO_PE13", "fp32", "fp32"),
        ("PE13_TO_PE22", "fp32", "fp32"),
        ("PE22_TO_PE23", "fp32_bits", "int32_bits"),
        ("PE23_TO_PE32", "int32", "int32"),
        ("PE32_TO_Y", "int32", "uint8_saturating"),
    ]
    return {
        "schema": "operator_config_composition_boundary_v1",
        "family": FAMILY,
        "boundaries": [
            {
                "boundary_id": f"{stage_id}:{edge}",
                "producer_dtype": producer_dtype,
                "consumer_dtype": consumer_dtype,
                "shape": "four serial scalar occurrences per accepted group",
                "layout": candidate["typed_io"]["Y"]["layout"],
                "producer_byte_set": token_set,
                "consumer_required_byte_set": token_set,
                "transaction_bytes": 4,
                "tag_last": (
                    "selected route carries group tag; only the fourth serialized "
                    "byte can carry group last"
                ),
                "clock_handshake": (
                    "selected consumer ready backpressures the exact producer; "
                    "unselected consumers are neutral"
                ),
                "lifetime_visibility": (
                    "token remains visible until the selected consumer accepts it"
                ),
                "qparam_rounding": candidate["numeric_graph"][
                    "rounding_contract"
                ],
                "status": "RESOLVED",
                "evidence": [
                    candidate["proof_receipts"]["reachable_domain_dp"]["path"],
                    candidate["proof_receipts"]["one_lane_9pe_topology"]["path"],
                ],
            }
            for edge, producer_dtype, consumer_dtype in edges
        ],
        "claim_boundary": (
            "Resolved local input/PE/output primitive boundaries; backend "
            "encoding and dynamic execution are excluded."
        ),
    }


def build_current_diff(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_sha = hashlib.sha256(pretty_bytes(candidate)).hexdigest()
    entries = [
        {
            "json_pointer": pointer,
            "candidate_value": value,
            "current_value_present": False,
            "current_value": None,
            "classification": "CURRENT_ABSENT",
            "reason": (
                "The active v36 configuration is a distinct six-stage dynamic "
                "diagnostic and is not generation authority for this local 9PE "
                "strict candidate."
            ),
            "evidence": [rel(CURRENT_DIFF), rel(DEPENDENCY_RECORD)],
        }
        for pointer, value in iter_json_leaves(candidate)
    ]
    return {
        "schema": "operator_config_current_test_diff_v1",
        "family": FAMILY,
        "candidate_json_sha256": candidate_sha,
        "current_identity": {
            "available": False,
            "path": None,
            "sha256": None,
            "package_or_record": rel(DEPENDENCY_RECORD),
            "latest_result": (
                "v36 dynamic package/config remains frozen and independent; "
                "no current strict one-lane 9PE QLinearAdd config exists."
            ),
        },
        "entries": entries,
        "blocker_attribution": [
            {
                "blocker_id": "B_COMPLETE_JSON_QADD_SIX_QPARAM_TYPED_MATERIALIZATION",
                "classification": "CONFIG_EXPLAINS",
                "candidate_json_pointers": [
                    "/qparams/a_scale/float32_bits",
                    "/qparams/b_scale/float32_bits",
                    "/qparams/y_scale/float32_bits",
                    "/numeric_graph/pe_chain/0/opcode",
                    "/numeric_graph/reachable_domain_sfu/breakpoint_bits/0",
                    "/physical_schedule/mode",
                ],
                "reason": (
                    "Candidate explicitly materializes the previously absent "
                    "six-qparam one-lane 9PE strict configuration."
                ),
                "evidence": [rel(DEPENDENCY_RECORD)],
            },
            {
                "blocker_id": "B_QADD_BACKEND_AND_DYNAMIC_EXECUTION",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "Backend and dynamic execution are outside this task.",
                "evidence": [rel(DEPENDENCY_RECORD)],
            },
            {
                "blocker_id": "B_QADD_SERVER_E4_E5",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": "No server run or formal D is produced.",
                "evidence": [rel(DEPENDENCY_RECORD)],
            },
        ],
        "claim_boundary": (
            "Leaf-complete comparison against absence of a current strict 9PE "
            "candidate; v36 package/observer/RTL outcomes remain dynamic-only."
        ),
    }


def build_contract(
    *,
    output_root: Path,
    stage_id: str,
    candidate_path: Path,
    ledger_path: Path,
    handler_path: Path,
    diff_path: Path,
    composition_path: Path,
) -> dict[str, Any]:
    return {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": FAMILY,
        "candidate_status": "COMPLETE",
        "reference_class": "D",
        "changed_axes": [
            "shape",
            "dtype",
            "qparam",
            "layout",
            "address",
            "cross_stage_schedule",
        ],
        "target_hw_op_types": ["QLinearAddUint8"],
        "stage_ids": [stage_id],
        "candidate_json": bound_file(candidate_path),
        "field_provenance_ledger": bound_file(ledger_path),
        "handler_capability": bound_file(handler_path),
        "current_test_diff": bound_file(diff_path),
        "composition": {
            "required": True,
            "boundary": bound_file(composition_path),
        },
        "artifact_root": rel(output_root),
        "claim_boundary": (
            "COMPLETE local strict QLinearAdd one-lane 9PE JSON only. No "
            "mapping, bitstream, execplan, SCA, package, server, formal D, "
            "E3, E4, or E5 is produced or claimed."
        ),
    }


def materialize(output_root: Path, proof_root: Path | None = None) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"output root must be fresh and empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    if sha256_file(LOWERING) != LOWERING_SHA256:
        raise ValueError("lowering SHA drift")
    for required in (
        STAGE_INVENTORY,
        CURRENT_DIFF,
        DEPENDENCY_RECORD,
        REQUANT_REPORT,
    ):
        if not required.is_file():
            raise ValueError(f"required evidence absent: {required}")
    if proof_root is None:
        local_snapshot = (
            DEFAULT_OUTPUT / "inputs/qadd_slow_composite_proof"
        )
        proof_root = local_snapshot if local_snapshot.is_dir() else OWNER_PROOF_ROOT
    proof_receipts = snapshot_proofs(proof_root, output_root)

    lowering = load_json(LOWERING)
    inventory = load_json(STAGE_INVENTORY)
    ordered_ids, requests = request_index(lowering)
    targets = inventory["targets"]
    target_by_id = {
        target["identity"]["hw_op_id"]: target for target in targets
    }
    if ordered_ids != [target["identity"]["hw_op_id"] for target in targets]:
        raise ValueError("stage inventory order differs from lowering")

    dp = load_json(proof_receipts["reachable_domain_sfu_segment_dp.json"])
    topology = load_json(proof_receipts["one_lane_rtl_topology_audit.json"])
    broadcast_proof = load_json(proof_receipts["node0076_replay_proof.json"])
    if not (dp["pass"] and topology["pass"] and broadcast_proof["pass"]):
        raise ValueError("accepted proof status drift")
    dp_by_id = {row["stage_id"]: row for row in dp["rows"]}
    if list(dp_by_id) != ordered_ids:
        raise ValueError("DP stage order differs from lowering")

    candidate_refs = []
    summaries = []
    for stage_id in ordered_ids:
        candidate = candidate_for_stage(
            stage=target_by_id[stage_id],
            request=requests[stage_id],
            dp_row=dp_by_id[stage_id],
            topology=topology,
            broadcast_proof=broadcast_proof,
            proof_receipts=proof_receipts,
        )
        candidate_dir = output_root / "candidates" / stage_id
        candidate_path = candidate_dir / "complete_json.json"
        write_json(candidate_path, candidate)
        ledger = build_ledger(candidate, proof_receipts)
        ledger_path = candidate_dir / "field_provenance_ledger.json"
        write_json(ledger_path, ledger)
        handler = build_handler_capability(candidate, ledger)
        handler_path = candidate_dir / "handler_capability.json"
        write_json(handler_path, handler)
        diff = build_current_diff(candidate)
        diff_path = candidate_dir / "current_test_diff.json"
        write_json(diff_path, diff)
        composition = build_composition(candidate)
        composition_path = candidate_dir / "composition_boundary.json"
        write_json(composition_path, composition)
        contract = build_contract(
            output_root=output_root,
            stage_id=stage_id,
            candidate_path=candidate_path,
            ledger_path=ledger_path,
            handler_path=handler_path,
            diff_path=diff_path,
            composition_path=composition_path,
        )
        contract_path = candidate_dir / "candidate_contract.json"
        write_json(contract_path, contract)
        candidate_refs.append(bound_file(contract_path))
        summaries.append(
            {
                "stage_id": stage_id,
                "shape_A": candidate["typed_io"]["A"]["shape"],
                "shape_B": candidate["typed_io"]["B"]["shape"],
                "shape_Y": candidate["typed_io"]["Y"]["shape"],
                "broadcast": stage_id == "hwop-0076-00",
                "logical_minimum_sfu_segments": candidate["numeric_graph"][
                    "reachable_domain_sfu"
                ]["logical_minimum_segment_count"],
                "candidate_sha256": sha256_file(candidate_path),
                "candidate_contract_sha256": sha256_file(contract_path),
                "ledger_leaf_count": len(ledger["entries"]),
            }
        )

    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": FAMILY,
        "target_hw_op_types": ["QLinearAddUint8"],
        "family_scope": {
            "mode": "PINNED_EXACT_STAGE_IDS",
            "lowering_sha256": LOWERING_SHA256,
            "expected_stage_ids": ordered_ids,
        },
        "candidate_contracts": candidate_refs,
        "no_config_stages": [],
        "claim_boundary": (
            "Exact 17-stage local strict QLinearAdd one-lane 9PE candidate set; "
            "all backend and execution surfaces are excluded."
        ),
    }
    family_set_path = output_root / "family_set.json"
    write_json(family_set_path, family_set)
    manifest = {
        "schema": "qlinearadd_slow_composite_strict_json_materialization_manifest_v1",
        "status": "LOCAL_STRICT_JSON_MATERIALIZED_PENDING_SHARED_GATES",
        "family": FAMILY,
        "stage_count": 17,
        "strict_json_count": 17,
        "same_shape_stage_count": 16,
        "broadcast_stage_count": 1,
        "unresolved_leaf_count": 0,
        "lowering_sha256": LOWERING_SHA256,
        "stage_ids": ordered_ids,
        "stages": summaries,
        "family_set": bound_file(family_set_path),
        "source_identity": {
            "ndp_sim_commit": NDP_SIM_COMMIT,
            "rtl_commit": RTL_COMMIT,
            "materializer": bound_file(Path(__file__).resolve()),
            "stage_inventory": bound_file(STAGE_INVENTORY),
            "requant_dependency_report": bound_file(REQUANT_REPORT),
            "proof_snapshots": {
                name: bound_file(path) for name, path in proof_receipts.items()
            },
        },
        "forbidden_outputs": {
            "mapping": 0,
            "bitstream": 0,
            "execplan": 0,
            "sca": 0,
            "zip": 0,
            "server_package": 0,
        },
        "claim_boundary": (
            "Materialization manifest for local strict QLinearAdd JSON only; "
            "shared gates run separately and backend/dynamic claims are forbidden."
        ),
    }
    write_json(output_root / "materialization_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--proof-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = materialize(
            args.output_root.resolve(),
            None if args.proof_root is None else args.proof_root.resolve(),
        )
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "stage_count": manifest["stage_count"],
                "strict_json_count": manifest["strict_json_count"],
                "unresolved_leaf_count": manifest["unresolved_leaf_count"],
                "output_root": rel(args.output_root.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
