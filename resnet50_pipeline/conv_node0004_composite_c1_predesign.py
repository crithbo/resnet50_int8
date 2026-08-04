"""Fresh proposal-only predesign for node0004's composite Conv C1 route.

The module deliberately emits no operator JSON, mapping, bitstream, execplan,
SCA, simulator payload, or package.  It consumes the typed request, formal
model/W3 tensors, active rules, and C1 authorization only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx


SCHEMA = "conv-node0004-composite-c1-predesign-v1"
REPORT_SCHEMA = "conv-node0004-composite-c1-predesign-report-v1"
REQUEST_ID = "r5:hwop-0004-00"
CONTRACT_PATH = "contracts/operator_config/conv_node0004_composite_c1_predesign_v1.json"
REPORT_PATH = (
    "artifacts/operator_config_validation/"
    "conv-node0004-composite-c1-predesign-v1/report.json"
)

PLAN_PATH = ".agents/plan.md"
INDEX_PATH = ".agents/rules/生成前必读索引.md"
COMMON_PATH = ".agents/rules/算子配置规则.md"
NDP_PATH = ".agents/rules/NDP硬件字段语义.md"
SA_PATH = ".agents/rules/INT8_SA点积专项规则.md"
GAP_PATH = ".agents/rules/GAP_int32_mac_bypass_rules.md"
TAIL_PATH = ".agents/rules/精确UINT8量化尾专项规则.md"
REQUANT_PATH = ".agents/rules/RequantizeUint8算子配置规则.md"
AUTH_PATH = (
    ".agents/task_records/"
    "20260728_conv_c0_mainline_adjudication_and_composite_c1_authorization.md"
)
MAINLINE_ADJUDICATION_PATH = (
    ".agents/task_records/"
    "20260728_conv_node0004_composite_c1_mainline_adjudication.md"
)
TAIL_DEP_PATH = (
    "contracts/operator_config/"
    "node0004_exact_uint8_tail_fresh_c1_dependency_v1.json"
)
TAIL_BINDING_PATH = (
    "contracts/operator_config/requant_conv53_exact_tail_binding_v1.json"
)
LOWERING_PATH = "contracts/resnet50_r5_lowering_bundle.json"
MODEL_PATH = "artifacts/reference_model/resnet50-v1-12-int8.onnx"
INPUT_PATH = (
    "artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy"
)
ACCUMULATOR_PATH = (
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0004-accumulate.npy"
)
NATIVE_MODELS_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/models.py"
)
NATIVE_CONTROL_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py"
)
NATIVE_TEMPLATE_MANAGER_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/template_manager.py"
)
NATIVE_MAPPER_PATH = "ndp-sim/bitstream/config/mapper.py"
NATIVE_ENCODER_PATH = "ndp-sim/bitstream/config/general.py"

EXPECTED_CURRENT_SHA = {
    INDEX_PATH: "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    COMMON_PATH: "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    NDP_PATH: "a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59",
    SA_PATH: "af4eb4c3795c8a8dfaba7dca47839906eb02dbb46bb17ec040f893638005502b",
    GAP_PATH: "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
    TAIL_PATH: "32c47b83e98d9dd9cbf1f8be7f25dd99d86ddecb583d5972b61b1e72d3b931be",
    REQUANT_PATH: "d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f",
    AUTH_PATH: "6415f8adfdd163a6c360a46e9392371c386b900b85722b9eee8a8d3760a89e2a",
    MAINLINE_ADJUDICATION_PATH: (
        "1f343efe8383b65ffb836427ba4994dcd78f7e0869b98882a831920ff34e9760"
    ),
}

FROZEN_NUMERIC_ORACLE_SHA256 = (
    "a2ba3cafbbac11e1ebd537bb91d7d88fe9770c61e202b78801ba042268ef6a41"
)

INITIALIZERS = {
    "x_zero_point": "resnetv17_relu0_fwd_zero_point",
    "w": "ConvBnFusion_W_resnetv17_stage1_conv0_weight_quantized",
    "w_zero_point": "ConvBnFusion_W_resnetv17_stage1_conv0_weight_zero_point",
    "bias": "ConvBnFusion_BN_B_resnetv17_stage1_batchnorm0_beta_quantized",
}


class PredesignError(ValueError):
    """Raised when the proposal-only contract no longer follows its sources."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(payload)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PredesignError(f"JSON root is not an object: {path}")
    return value


def _request(root: Path) -> dict[str, Any]:
    bundle = _load_json(root / LOWERING_PATH)
    matches = [
        item
        for item in bundle.get("requests", [])
        if isinstance(item, dict) and item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise PredesignError(f"expected one {REQUEST_ID}, got {len(matches)}")
    return matches[0]


def _initializers(root: Path) -> dict[str, np.ndarray]:
    model = onnx.load(str(root / MODEL_PATH), load_external_data=True)
    wanted = set(INITIALIZERS.values())
    values = {
        tensor.name: onnx.numpy_helper.to_array(tensor)
        for tensor in model.graph.initializer
        if tensor.name in wanted
    }
    if set(values) != wanted:
        raise PredesignError(f"missing initializers: {sorted(wanted - set(values))}")
    return {role: np.asarray(values[name]) for role, name in INITIALIZERS.items()}


def _align16(value: int) -> int:
    return (value + 15) & ~15


def _region(name: str, offset: int, size: int) -> dict[str, Any]:
    if offset % 16 or size % 16:
        raise PredesignError(f"region {name} is not 16-byte aligned")
    return {
        "name": name,
        "offset": offset,
        "size_bytes": size,
        "end_exclusive": offset + size,
        "alignment": 16,
    }


def _schedule() -> dict[str, Any]:
    n_count, oc_count, height, width, k_count = 16, 64, 56, 56, 64
    oc_tile = 8
    output_elements = n_count * oc_count * height * width
    product_elements = output_elements * k_count
    tile_output_elements = height * width * oc_tile
    tile_count = n_count * (oc_count // oc_tile)
    widths = [64, 32, 16, 8, 4, 2, 1]

    input_bytes = k_count * height * width
    weight_bytes = oc_tile * k_count
    correction_unique_bytes = oc_tile * 4
    offset = 0
    regions = []
    for name, size in [
        ("input_nchw_u8", input_bytes),
        ("weight_oc8_k64_s8", weight_bytes),
        ("correction_oc8_i32", correction_unique_bytes),
        ("product_q_k_i32", tile_output_elements * 64 * 4),
    ]:
        offset = _align16(offset)
        regions.append(_region(name, offset, size))
        offset += size
    for stage, stage_width in enumerate(widths[1:], 1):
        size = tile_output_elements * stage_width * 4
        offset = _align16(offset)
        regions.append(_region(f"tree_l{stage}_q_j_i32", offset, size))
        offset += size
    offset = _align16(offset)
    regions.append(
        _region("corrected_accumulator_hwc8_i32", offset, tile_output_elements * 4)
    )
    offset += tile_output_elements * 4

    tree_stages = []
    previous = "product_q_k_i32"
    for stage, (input_width, output_width) in enumerate(
        zip(widths[:-1], widths[1:]), 1
    ):
        output = f"tree_l{stage}_q_j_i32"
        tree_stages.append(
            {
                "stage": stage,
                "opcode": "int32_mac",
                "opcode_value": 14,
                "equation": "D=low32(A*1+C)",
                "input_width": input_width,
                "output_width": output_width,
                "input_region": previous,
                "output_region": output,
                "accepted_pair_occurrences_per_tile": tile_output_elements
                * output_width,
                "a_address": (
                    f"{previous}.base + 4*(q*{input_width} + 2*j)"
                ),
                "c_address": (
                    f"{previous}.base + 4*(q*{input_width} + 2*j + 1)"
                ),
                "d_address": f"{output}.base + 4*(q*{output_width} + j)",
                "a_terminal_owner": True,
                "c_mode": "buffer",
                "b_mode": "constant_int32_one",
                "normal_fifo_required": True,
                "transout_last_index": None,
                "barrier_after": "D write drain before next stage reconfigure",
            }
        )
        previous = output

    per_slice_capacity = 4 * 6144 * 64 * 16
    aggregate_capacity = 28 * per_slice_capacity
    waves = [28, 28, 28, 28, 16]
    tree_read = output_elements * sum(widths[:-1]) * 4
    tree_write = output_elements * sum(widths[1:]) * 4
    sa_operand_read = product_elements * 2
    product_write = product_elements * 4
    correction_read_keep = output_elements * 4 + tile_count * oc_tile * 4
    correction_write = output_elements * 4

    return {
        "logical": {
            "shape": [n_count, oc_count, height, width],
            "k": k_count,
            "output_elements": output_elements,
            "product_elements": product_elements,
            "equation": (
                "acc[n,oc,oh,ow]=bias[oc]+sum_k("
                "(u8(x[n,k,oh,ow])-x_zp)*(s8(w[oc,k])-w_zp[oc]))"
            ),
            "node0004_specialization": "x_zp=0 and all w_zp=0",
        },
        "tile": {
            "axes": ["n", "oc_group8"],
            "tile_id": "n*8+oc_group8",
            "tile_count": tile_count,
            "output_elements": tile_output_elements,
            "product_elements": tile_output_elements * k_count,
            "q": "((oh*56+ow)*8+lane)",
            "inverse": {
                "lane": "q%8",
                "spatial": "q//8",
                "oh": "(q//8)//56",
                "ow": "(q//8)%56",
                "n": "tile_id//8",
                "oc": "8*(tile_id%8)+lane",
            },
            "source_x_byte": "(((n*64+k)*56+oh)*56+ow)",
            "source_w_byte": "oc*64+k",
            "formal_nchw_accumulator_byte": (
                "4*(((n*64+oc)*56+oh)*56+ow)"
            ),
            "product_scratch_byte": (
                "product_q_k_i32.base+4*(q*64+k)"
            ),
            "waves_over_28_slices": waves,
        },
        "coverage": {
            "product_per_tile": {
                "element_count": tile_output_elements * k_count,
                "byte_count": tile_output_elements * k_count * 4,
                "relative_byte_interval": [
                    0,
                    tile_output_elements * k_count * 4,
                ],
                "multiplicity": 1,
                "proof": (
                    "(q,k)->q*64+k is an affine bijection over "
                    "q in [0,25088), k in [0,64)"
                ),
            },
            "product_all_tiles": {
                "element_count": product_elements,
                "byte_count": product_elements * 4,
                "tile_count": tile_count,
                "multiplicity": 1,
                "logical_inverse": (
                    "tile_id,q,k -> n,oc,oh,ow,k using tile.inverse"
                ),
            },
            "tree_stage_output_elements_all_tiles": [
                output_elements * width for width in widths[1:]
            ],
            "corrected_accumulator": {
                "element_count": output_elements,
                "byte_count": output_elements * 4,
                "formal_nchw_inverse_required": True,
            },
            "final_materialized_address_hash": None,
            "status": (
                "SYMBOLIC_BIJECTION_CLOSED__FINAL_OCCURRENCE_ADDRESS_ENUMERATION_"
                "BLOCKED"
            ),
        },
        "sa_single_product": {
            "equation": "i32(s8(weight))*i32(u8(input))",
            "data_c": 0,
            "nonzero_dot4_product_lanes_per_logical_occurrence": 1,
            "zero_dot4_product_lanes_per_logical_occurrence": 3,
            "dot4_lane_utilization": 0.25,
            "logical_occurrences": product_elements,
            "physical_parallel_grouping": None,
            "status": "SOURCE_PRIMITIVE_PROVEN__MATERIALIZER_PENDING",
        },
        "tree": {
            "widths": widths,
            "stage_count": 6,
            "stages": tree_stages,
            "pair_operations": output_elements * sum(widths[1:]),
            "odd_tail_count": 0,
            "buffer_word_columns": [0, 4, 8, 12, 16, 20, 24, 28],
            "buffer_banks": list(range(8)),
            "buffer_byte": 0,
            "tag_contract": "A is terminal carrier; C matches A occurrence/tag",
            "normal_fifo_contract": "0<=occupancy<=2 on accepted read/write only",
            "status": "SOURCE_EXPRESSIBLE_PROPOSAL_ONLY",
        },
        "correction_leaf": {
            "formula_general_wzp_zero": "bias[oc]-x_zp*sum_k(w[oc,k])",
            "node0004_formula": "bias[oc]",
            "opcode": "int32_mac",
            "opcode_value": 14,
            "equation": "D=low32(root*1+correction[oc])",
            "a_mode": "buffer_terminal",
            "b_mode": "constant_int32_one",
            "c_mode": "keep_replay_oc8",
            "unique_constant_bytes_per_tile": correction_unique_bytes,
            "accepted_occurrences_per_tile": tile_output_elements,
            "barrier_after": "corrected accumulator D write drain",
            "status": "SOURCE_EXPRESSIBLE_PROPOSAL_ONLY",
        },
        "terminal_and_ownership": {
            "logical_loop_order": ["tile_id", "q", "k"],
            "logical_product_terminal": (
                "k=63 terminates one output's product group; q=25087 "
                "terminates one tile"
            ),
            "ga_stage_terminal": (
                "j=output_width-1 terminates one q group; q=25087 "
                "terminates one tile stage"
            ),
            "physical_last_index": None,
            "physical_lc_src_id": None,
            "physical_sa_transout": None,
            "physical_buffer_lifetime": None,
            "owners": [
                {
                    "field": "logical geometry and typed constants",
                    "owner": "typed request/formal ONNX",
                    "status": "CLOSED",
                },
                {
                    "field": "tile axes, region sizes, symbolic byte equations",
                    "owner": "composite C1 predesign planner",
                    "status": "CLOSED_PROPOSAL_ONLY",
                },
                {
                    "field": "SA lane packing, LC/MSE, Buffer bank/column, terminal",
                    "owner": None,
                    "status": (
                        "B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL"
                    ),
                },
                {
                    "field": "GA A/C roots, tag/FIFO, barrier and writeback",
                    "owner": "future composite manual materializer",
                    "status": "PROPOSAL_ONLY",
                },
                {
                    "field": "all base_addr and final physical occurrences",
                    "owner": None,
                    "status": "UNBOUND_NO_TARGET_JSON",
                },
                {
                    "field": "exact UINT8 tail",
                    "owner": "parallel shared-tail/max0 audit",
                    "status": "BLOCKED_NOT_CONSUMABLE",
                },
            ],
            "claim_boundary": (
                "Logical terminals are equations, not encoded last_index/tag "
                "proof. Every null physical leaf is a generation stop."
            ),
        },
        "memory": {
            "regions": regions,
            "tile_residency_bytes": offset,
            "per_slice_capacity_bytes": per_slice_capacity,
            "per_slice_headroom_bytes": per_slice_capacity - offset,
            "full_product_scratch_bytes": product_elements * 4,
            "aggregate_28_slice_capacity_bytes": aggregate_capacity,
            "full_product_scratch_exceeds_aggregate_by_bytes": (
                product_elements * 4 - aggregate_capacity
            ),
            "capacity_verdict": (
                "FULL_LAYER_RESIDENCY_IMPOSSIBLE__OC8_TILE_RESIDENCY_FITS"
            ),
            "region_overlap_count": 0,
            "visibility": (
                "Each producer region is disjoint; every stage requires complete "
                "write drain and same-active-mask barrier before consumer reload."
            ),
        },
        "traffic_lower_bound": {
            "sa_operand_read_bytes": sa_operand_read,
            "product_write_bytes": product_write,
            "ga_tree_read_bytes": tree_read,
            "ga_tree_write_bytes": tree_write,
            "correction_root_plus_keep_seed_read_bytes": correction_read_keep,
            "correction_write_bytes": correction_write,
            "total_accumulate_bytes": (
                sa_operand_read
                + product_write
                + tree_read
                + tree_write
                + correction_read_keep
                + correction_write
            ),
            "excludes": [
                "config traffic",
                "read-modify-write amplification",
                "cache-line padding",
                "tail stages",
            ],
        },
    }


def _numeric_oracle(root: Path) -> dict[str, Any]:
    values = _initializers(root)
    x = np.load(root / INPUT_PATH).astype(np.int32, copy=False)
    w = values["w"].astype(np.int32).reshape(64, 64)
    wzp = values["w_zero_point"].astype(np.int32).reshape(64)
    bias = values["bias"].astype(np.int32).reshape(64)
    xzp = int(values["x_zero_point"].reshape(-1)[0])
    correction64 = bias.astype(np.int64) - xzp * (
        w.astype(np.int64) - wzp[:, None].astype(np.int64)
    ).sum(axis=1)
    if np.any(correction64 < -(1 << 31)) or np.any(correction64 >= (1 << 31)):
        raise PredesignError("correction leaf exceeds signed int32")
    correction = correction64.astype(np.int32)
    matrix = x.transpose(0, 2, 3, 1).reshape(-1, 64)
    result = (
        (matrix - xzp) @ (w - wzp[:, None]).T + bias.astype(np.int32)
    ).reshape(16, 56, 56, 64).transpose(0, 3, 1, 2)
    formal = np.load(root / ACCUMULATOR_PATH)
    mismatch = int(np.count_nonzero(result != formal))
    return {
        "x_zero_point": xzp,
        "w_zero_point_minimum": int(wzp.min()),
        "w_zero_point_maximum": int(wzp.max()),
        "weight_payload_sha256": sha256_bytes(values["w"].tobytes()),
        "bias_payload_sha256": sha256_bytes(bias.tobytes()),
        "correction_payload_sha256": sha256_bytes(correction.tobytes()),
        "correction_minimum": int(correction.min()),
        "correction_maximum": int(correction.max()),
        "correction_equals_bias": bool(np.array_equal(correction, bias)),
        "full_w3_mismatch_count": mismatch,
        "computed_accumulator_payload_sha256": sha256_bytes(
            np.ascontiguousarray(result).tobytes()
        ),
        "formal_accumulator_payload_sha256": sha256_bytes(
            np.ascontiguousarray(formal).tobytes()
        ),
        "formal_element_count": int(formal.size),
        "claim_boundary": (
            "Independent golden validation only; no product, partial-sum, "
            "accumulator, scaled, rounded, saturated, or final tensor is emitted."
        ),
    }


def build_contract(root: Path) -> dict[str, Any]:
    root = root.resolve()
    request = _request(root)
    geometry = request["logical_geometry"]
    if geometry["input_shapes"][:5] != [
        [16, 64, 56, 56],
        [1],
        [64, 64, 1, 1],
        [64],
        [64],
    ]:
        raise PredesignError("typed node0004 geometry changed")
    if request.get("request_sha256") != (
        "e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b"
    ):
        raise PredesignError("typed node0004 request identity changed")

    semantic_receipts = []
    for path, expected in EXPECTED_CURRENT_SHA.items():
        actual = sha256_file(root / path)
        if actual != expected:
            raise PredesignError(f"current-match receipt drifted: {path}")
        semantic_receipts.append(
            {"path": path, "sha256": actual, "gate": "current_match_fail_closed"}
        )
    source_paths = [
        LOWERING_PATH,
        MODEL_PATH,
        INPUT_PATH,
        ACCUMULATOR_PATH,
        TAIL_DEP_PATH,
        TAIL_BINDING_PATH,
        NATIVE_MODELS_PATH,
        NATIVE_CONTROL_PATH,
        NATIVE_TEMPLATE_MANAGER_PATH,
        NATIVE_MAPPER_PATH,
        NATIVE_ENCODER_PATH,
    ]
    source_receipts = [
        {"path": path, "sha256": sha256_file(root / path)}
        for path in source_paths
    ]
    tail_dep = _load_json(root / TAIL_DEP_PATH)
    first_tail_blocker = tail_dep["pure_configuration_decision"][
        "first_unavoidable_capability"
    ]
    return {
        "schema": SCHEMA,
        "test_id": "r5_conv_node0004_composite_c1_predesign_v1",
        "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
        "status": "PROPOSAL_ONLY_FEASIBILITY__TARGET_GENERATION_STOPPED",
        "identity": request["identity"],
        "typed_request_sha256": request["request_sha256"],
        "receipts": {
            "plan_mutable_provenance": {
                "path": PLAN_PATH,
                "sha256_at_generation": sha256_file(root / PLAN_PATH),
                "current_match_required": False,
            },
            "semantic": semantic_receipts,
            "sources": source_receipts,
        },
        "schedule": _schedule(),
        "numeric_oracle": _numeric_oracle(root),
        "feasibility": {
            "logical_schedule": "CLOSED_SYMBOLIC_AND_W3_BIT_EXACT",
            "capacity": "CLOSED_WITH_OC8_TILING_FIVE_WAVES",
            "sa_physical_materialization": "BLOCKED",
            "ga_tree_physical_materialization": "PROPOSAL_ONLY",
            "tail_materialization": "BLOCKED",
            "complete_target": False,
            "first_physical_blocker": (
                "B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL"
            ),
            "first_physical_blocker_detail": (
                "No authorized typed/manual materializer currently binds the "
                "single-nonzero-dot4 SA product occurrence to final LC/MSE/"
                "Buffer bank columns, tag/last terminal, direct INT32 scratch "
                "write, and 205,520,896-occurrence coverage. Symbolic addresses "
                "cannot substitute for final JSON/bitstream occurrence inversion."
            ),
            "next_blockers": [
                "B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY",
                "B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP",
                first_tail_blocker,
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_EXECPLAN_TYPED_TRANSPORT",
            ],
        },
        "bypass_annotation": {
            "bypass_reason": (
                "stock four-lane INT8 SA has duplicate carry shift, signed17 "
                "reduction range loss, and INT8 DataC/psum gating"
            ),
            "contradicted_or_missing_native_path": (
                "normal four-lane dot, SA internal psum, and a registered "
                "composite Conv typed/materializer entry"
            ),
            "exact_equivalence_scope": (
                "node0004 1x1 Cin64 accumulate only; modulo-2^32 product/tree/"
                "correction arithmetic over all 3,211,264 outputs"
            ),
            "materialized_configuration_mechanism": None,
            "performance_and_resource_cost": (
                "205,520,896 scalar SA product occurrences at 25% dot4-lane "
                "utilization; six GA tree levels plus one correction level; "
                "128 OC8 tiles in five waves; 13,046,304 bytes/tile"
            ),
            "unresolved_production_blocker": (
                "SA scalar-product physical materializer/terminal first; exact "
                "UINT8 tail remains independently blocked"
            ),
            "claim_boundary": (
                "proposal-only machine predesign; not a "
                "CONFIG_ONLY_CORRECTNESS_BASELINE"
            ),
        },
        "emission": {
            "target_json_generated": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_or_sca_generated": False,
            "config_bound_simulator_generated": False,
            "server_package_generated": False,
            "candidate_release": False,
            "package_release": "NONE",
        },
    }


def validate_contract(contract_path: Path, root: Path) -> dict[str, Any]:
    root = root.resolve()
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise PredesignError("contract schema mismatch")
    for receipt in contract["receipts"]["semantic"]:
        actual = sha256_file(root / receipt["path"])
        if actual != receipt["sha256"]:
            raise PredesignError(f"semantic receipt drift: {receipt['path']}")
    schedule = contract["schedule"]
    memory = schedule["memory"]
    regions = memory["regions"]
    for left, right in zip(regions, regions[1:]):
        if left["end_exclusive"] > right["offset"]:
            raise PredesignError("scratch regions overlap")
    if regions[-1]["end_exclusive"] != memory["tile_residency_bytes"]:
        raise PredesignError("tile residency end mismatch")
    if memory["tile_residency_bytes"] > memory["per_slice_capacity_bytes"]:
        raise PredesignError("OC8 tile does not fit one slice")
    if sum(schedule["tile"]["waves_over_28_slices"]) != 128:
        raise PredesignError("wave coverage mismatch")
    if schedule["tree"]["widths"] != [64, 32, 16, 8, 4, 2, 1]:
        raise PredesignError("tree width mismatch")
    if schedule["tree"]["odd_tail_count"] != 0:
        raise PredesignError("node0004 K64 must not have an odd tree tail")
    numeric = contract["numeric_oracle"]
    numeric_sha = canonical_json_sha256(numeric)
    if numeric_sha != FROZEN_NUMERIC_ORACLE_SHA256:
        raise PredesignError("frozen numeric oracle digest drift")
    if numeric["full_w3_mismatch_count"] != 0:
        raise PredesignError("frozen full-W3 accumulate conclusion changed")
    refresh = contract.get("receipt_only_integration_refresh")
    if not isinstance(refresh, dict):
        raise PredesignError("receipt-only integration refresh is missing")
    if refresh.get("numeric_analysis_repeated") is not False:
        raise PredesignError("receipt refresh repeated numeric analysis")
    if refresh.get("frozen_numeric_oracle_sha256") != numeric_sha:
        raise PredesignError("receipt refresh numeric digest mismatch")
    if refresh.get("target_or_package_generated") is not False:
        raise PredesignError("receipt refresh generated a target or package")
    if refresh.get("conclusion_changed") is not False:
        raise PredesignError("receipt refresh changed the conclusion")
    if contract["feasibility"]["complete_target"] is not False:
        raise PredesignError("proposal-only contract claimed a complete target")
    if any(
        value is not False
        for key, value in contract["emission"].items()
        if key.endswith("_generated")
    ):
        raise PredesignError("proposal-only contract emitted a target asset")
    return {
        "schema": REPORT_SCHEMA,
        "test_id": contract["test_id"],
        "status": (
            "PASS_RECEIPT_ONLY_INTEGRATION_REFRESH__"
            "PROPOSAL_ONLY_TARGET_FAIL_CLOSED"
        ),
        "semantic_receipt_count": len(contract["receipts"]["semantic"]),
        "source_receipt_count": len(contract["receipts"]["sources"]),
        "full_w3_mismatch_count": numeric["full_w3_mismatch_count"],
        "numeric_analysis_repeated": False,
        "frozen_numeric_oracle_sha256": numeric_sha,
        "conclusion_changed": False,
        "formal_element_count": numeric["formal_element_count"],
        "tile_count": schedule["tile"]["tile_count"],
        "waves": schedule["tile"]["waves_over_28_slices"],
        "tile_residency_bytes": memory["tile_residency_bytes"],
        "per_slice_capacity_bytes": memory["per_slice_capacity_bytes"],
        "full_product_scratch_bytes": memory["full_product_scratch_bytes"],
        "aggregate_28_slice_capacity_bytes": memory[
            "aggregate_28_slice_capacity_bytes"
        ],
        "logical_product_occurrences": schedule["sa_single_product"][
            "logical_occurrences"
        ],
        "first_physical_blocker": contract["feasibility"][
            "first_physical_blocker"
        ],
        "complete_target": False,
        "package_release": "NONE",
    }


def refresh_contract_receipts(contract_path: Path, root: Path) -> dict[str, Any]:
    """Refresh only active identities while preserving the frozen numeric oracle."""
    root = root.resolve()
    value = _load_json(contract_path)
    if value.get("schema") != SCHEMA:
        raise PredesignError("contract schema mismatch")
    numeric_sha = canonical_json_sha256(value.get("numeric_oracle"))
    if numeric_sha != FROZEN_NUMERIC_ORACLE_SHA256:
        raise PredesignError("refusing receipt refresh after numeric oracle drift")
    semantic_receipts = []
    for path, expected in EXPECTED_CURRENT_SHA.items():
        actual = sha256_file(root / path)
        if actual != expected:
            raise PredesignError(f"current-match receipt drifted: {path}")
        semantic_receipts.append(
            {"path": path, "sha256": actual, "gate": "current_match_fail_closed"}
        )
    value["receipts"]["plan_mutable_provenance"] = {
        "path": PLAN_PATH,
        "sha256_at_receipt_refresh": sha256_file(root / PLAN_PATH),
        "current_match_required": False,
    }
    value["receipts"]["semantic"] = semantic_receipts
    value["receipt_only_integration_refresh"] = {
        "classification": "ACTIVE_RULE_RECEIPT_ONLY",
        "numeric_analysis_repeated": False,
        "frozen_numeric_oracle_sha256": numeric_sha,
        "frozen_full_w3_mismatch_count": 0,
        "frozen_formal_element_count": 3_211_264,
        "conclusion_changed": False,
        "target_or_package_generated": False,
        "new_rule_bindings": [
            "CDA-COMPOSITE-SCRATCH-GLOBAL-VS-TILED-CAPACITY-001",
            "CDA-PREDESIGN-SYMBOLIC-ADDRESS-NOT-PHYSICAL-COVERAGE-001",
        ],
        "tail_adjudication": (
            "B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED"
        ),
        "claim_boundary": (
            "No W3/model numeric replay, target materialization, simulator, "
            "package, server inspection, upload, run, or lease."
        ),
    }
    value["status"] = (
        "PROPOSAL_ONLY_FEASIBILITY__RECEIPTS_REFRESHED__"
        "TARGET_GENERATION_STOPPED"
    )
    return value


def write_contract(root: Path, output: Path) -> dict[str, Any]:
    value = build_contract(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return value


def write_receipt_refresh(
    contract_path: Path, root: Path, output: Path
) -> dict[str, Any]:
    value = refresh_contract_receipts(contract_path, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return value


def write_report(contract: Path, root: Path, output: Path) -> dict[str, Any]:
    value = validate_contract(contract, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return value
