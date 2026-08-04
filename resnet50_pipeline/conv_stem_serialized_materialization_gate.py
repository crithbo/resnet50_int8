from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
EXPANSION_REL = Path(
    "contracts/operator_config/conv_sa_remaining52_expansion_v1.json"
)
REQUANT_REL = Path(
    "contracts/operator_config/requant_conv53_tail_signature_binding_v1.json"
)
GENERATOR_REL = Path("tools/generate_conv_instance.py")
LAYOUT_REL = Path("resnet50_pipeline/conv28_layout.py")
PATCHER_REL = Path("resnet50_pipeline/ndp_patch_toolchain.py")
PLAN_REL = Path(".agents/plan.md")
INDEX_REL = Path(".agents/rules/生成前必读索引.md")
COMMON_RULE_REL = Path(".agents/rules/算子配置规则.md")
SA_RULE_REL = Path(".agents/rules/INT8_SA点积专项规则.md")
NDP_RULE_REL = Path(".agents/rules/NDP硬件字段语义.md")
TAIL_RULE_REL = Path(".agents/rules/精确UINT8量化尾专项规则.md")
REQUEST_ID = "r5:hwop-0001-00"
TAIL_REQUEST_ID = "r5:hwop-0001-01"
EXPECTED_ABSENT_PATHS = (
    Path("configs/native_ndp_sim/r5_conv_stem_serialized_local_e2_v1"),
    Path(
        "artifacts/operator_config_validation/"
        "r5_conv_stem_serialized_local_e2_v1"
    ),
    Path(
        "artifacts/operator_config_validation/r5-server-test-packages/"
        "r5_conv_stem_serialized_local_e2_v1.zip"
    ),
)


class StemMaterializationGateError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StemMaterializationGateError(f"JSON root must be object: {path}")
    return value


def _line(path: Path, snippet: str) -> int:
    matches = [
        index
        for index, text in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if snippet in text
    ]
    if len(matches) != 1:
        raise StemMaterializationGateError(
            f"source witness is not unique: {path}:{snippet}"
        )
    return matches[0]


def build_stem_materialization_gate(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    lowering = _load(root / LOWERING_REL)
    expansion = _load(root / EXPANSION_REL)
    requant = _load(root / REQUANT_REL)
    requests = [
        item for item in lowering["requests"] if item["request_id"] == REQUEST_ID
    ]
    if len(requests) != 1:
        raise StemMaterializationGateError("stem typed request is not unique")
    request = requests[0]
    stem_rows = [
        item
        for item in expansion["records"]
        if item["identity"]["request_id"] == REQUEST_ID
    ]
    if len(stem_rows) != 1:
        raise StemMaterializationGateError("stem expansion row is not unique")
    stem = stem_rows[0]
    tail_rows = [
        item
        for item in requant["stage_bindings"]
        if item["typed_request"]["request_id"] == TAIL_REQUEST_ID
    ]
    if len(tail_rows) != 1:
        raise StemMaterializationGateError("stem Requant row is not unique")
    tail = tail_rows[0]

    geometry = request["logical_geometry"]
    attrs = geometry["attributes"]
    if (
        geometry["input_shapes"][0] != [16, 3, 224, 224]
        or geometry["input_shapes"][2] != [64, 3, 7, 7]
        or geometry["output_shapes"][0] != [16, 64, 112, 112]
        or attrs["strides"] != [2, 2]
        or attrs["pads"] != [3, 3, 3, 3]
    ):
        raise StemMaterializationGateError("stem typed geometry differs")

    logical_k = 147
    serialized_k = 148
    spatial = 112 * 112
    local_outputs = 16
    lanes = 4
    weight_bytes = serialized_k * local_outputs * lanes
    activation_bytes = spatial * serialized_k * lanes
    correction_bytes = local_outputs * 4
    output_bytes = spatial * local_outputs * 4
    allocation = weight_bytes + activation_bytes + correction_bytes + output_bytes
    slice_capacity = 4 * 6144 * 64 * 16
    output_elements = math.prod(geometry["output_shapes"][0])
    serialized_occurrences = output_elements * serialized_k
    if serialized_occurrences != 1_901_068_288:
        raise AssertionError("serialized occurrence equation differs")
    offsets = {
        row * 7168 + (block * 8 + q) * 64 + half * 32 + byte
        for row in range(112)
        for block in range(14)
        for q in range(8)
        for half in range(2)
        for byte in range(32)
    }
    if (
        len(offsets) != output_bytes
        or min(offsets) != 0
        or max(offsets) != output_bytes - 1
    ):
        raise AssertionError("symbolic D coverage is not contiguous")

    generator = root / GENERATOR_REL
    layout = root / LAYOUT_REL
    patcher = root / PATCHER_REL
    evidence = {
        "typed_generator_7x7_rejection": {
            "path": GENERATOR_REL.as_posix(),
            "sha256": sha256_file(generator),
            "line": _line(
                generator,
                "typed Conv generator supports only reviewed 1x1/pad0 or 3x3/pad1",
            ),
            "effect": "no authorized typed JSON emitter for 7x7/stride2/pad3",
        },
        "signed_a_layout_7x7_rejection": {
            "path": LAYOUT_REL.as_posix(),
            "sha256": sha256_file(layout),
            "line": _line(
                layout,
                "the signed-A local-replication ABI currently supports only 1x1/stride1/pad0",
            ),
            "effect": "no accepted final physical activation/weight packer for stem",
        },
        "serialized_handler_node0004_shape_lock": {
            "path": PATCHER_REL.as_posix(),
            "sha256": sha256_file(patcher),
            "handler_line": _line(
                patcher,
                "def _compute_resnet50_node0004_serialized_conv_control_register_updates(",
            ),
            "a_shape_line": _line(
                patcher, '\\"A\\": ((1, 1, 4096), \\"int8\\"),'
            ),
            "b_shape_line": _line(
                patcher, '\\"B\\": ((1, 1, 802816), \\"uint8\\"),'
            ),
            "d_shape_line": _line(
                patcher, "serialized node-0004 Conv D must be int32 [1,1,50176]"
            ),
            "effect": (
                "active execplan registry accepts only node0004 identity and "
                "4096/802816/50176 shapes; stem needs 9472/7426048/200704"
            ),
        },
        "patchset_registry_has_no_stem_id": {
            "path": PATCHER_REL.as_posix(),
            "registry_line": _line(patcher, "def _patched_files_for("),
            "effect": (
                "a fresh stem operator type cannot be lowered without adding "
                "a shared patchset/handler semantic owner"
            ),
        },
    }
    return {
        "schema": "resnet50-stem-serialized-materialization-gate-v1",
        "status": "BLOCKED_BEFORE_TARGET_JSON",
        "active_rule_receipts": {
            INDEX_REL.as_posix(): sha256_file(root / INDEX_REL),
            COMMON_RULE_REL.as_posix(): sha256_file(root / COMMON_RULE_REL),
            SA_RULE_REL.as_posix(): sha256_file(root / SA_RULE_REL),
            NDP_RULE_REL.as_posix(): sha256_file(root / NDP_RULE_REL),
            TAIL_RULE_REL.as_posix(): sha256_file(root / TAIL_RULE_REL),
        },
        "mutable_plan_provenance": {
            "path": PLAN_REL.as_posix(),
            "sha256_at_build": sha256_file(root / PLAN_REL),
            "semantic_gate": False,
        },
        "scope": {
            "request_id": REQUEST_ID,
            "request_sha256": request["request_sha256"],
            "node_id": "node-0001",
            "new_target_json_generated": False,
            "mapping_bitstream_execplan_sca_generated": False,
            "server_package_generated": False,
            "expected_materialized_paths_checked_absent": [
                path.as_posix() for path in EXPECTED_ABSENT_PATHS
            ],
        },
        "source_receipts": {
            LOWERING_REL.as_posix(): sha256_file(root / LOWERING_REL),
            EXPANSION_REL.as_posix(): sha256_file(root / EXPANSION_REL),
            REQUANT_REL.as_posix(): sha256_file(root / REQUANT_REL),
        },
        "numeric_domain_reused_without_repeat": {
            "source_record_sha256": hashlib.sha256(
                json.dumps(
                    stem,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "normal_dot4_count": 475_267_072,
            "actual_dot4_range": [-101_231, 95_485],
            "signed17_violation_count": 2_499_984,
            "numeric_analysis_repeated": False,
        },
        "proposal_only_schedule": {
            "logical_k": logical_k,
            "serialized_padded_k": serialized_k,
            "active_lane": "k % 4 for k<147; padded k=147 has zero weight",
            "raw_product_equation": "s8_weight[k] * u8_activation[n,c,ih,iw]",
            "datac_initial_value": (
                "bias[oc] - x_zp(114) * sum(weight[oc,0:147]), modulo 2^32"
            ),
            "psum_recurrence": "psum[k+1] = psum[k] + product[k] modulo 2^32",
            "wave_samples": [[0, 3, 6, 8, 10, 12, 14], [1, 4, 7, 9, 11, 13, 15], [2, 5]],
            "slice_region_count": 64,
            "serialized_occurrence_count": serialized_occurrences,
            "normal_dot4_count": 475_267_072,
            "occurrence_ratio": 4.0,
            "lane_utilization": logical_k / (serialized_k * 4),
        },
        "proposal_only_physical_regions": {
            "per_slice_capacity_bytes": slice_capacity,
            "per_region": {
                "A_serialized_weight_bytes": weight_bytes,
                "B_serialized_im2col_replay_bytes": activation_bytes,
                "C_correction_bytes": correction_bytes,
                "D_int32_bytes": output_bytes,
                "total_bytes": allocation,
                "fits_one_slice": allocation <= slice_capacity,
            },
            "base_offsets": {
                "A": 0,
                "B": weight_bytes,
                "C": weight_bytes + activation_bytes,
                "D": weight_bytes + activation_bytes + correction_bytes,
            },
            "derived_loop_fields": {
                "LC1_LC11_LC14_end": 112,
                "LC2_LC12_LC15_end": 14,
                "LC4_LC6_end": 37,
                "LC5_LC7_end": 4,
                "B_dim_stride": [32, 4736, 66304],
                "D_dim_stride": [32, 64, 7168],
            },
            "claim_boundary": (
                "capacity and affine equations only; not final JSON, address "
                "coverage, mapping, bitstream, terminal or lifetime evidence"
            ),
        },
        "symbolic_output_coverage": {
            "equation": (
                "offset=row*7168 + (wblock*8+q)*64 + half*32 + byte"
            ),
            "recomputed_byte_count": len(offsets),
            "first_offset": min(offsets),
            "last_offset": max(offsets),
            "contiguous": True,
            "physical_coverage_claimed": False,
        },
        "first_blocker": {
            "id": "B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER",
            "classification": "SOURCE_TOOLCHAIN_SEMANTIC_OWNER_MISSING",
            "evidence": evidence,
            "required_authorization_or_input": (
                "authorize a fresh stem-specific typed generator, signed "
                "serialized im2col packer, and execplan patchset handler in "
                "the shared ndp patch registry; borrowing node0004 type is forbidden"
            ),
        },
        "requant_binding": {
            "request_id": TAIL_REQUEST_ID,
            "classification": tail["existing_w3_classification"][
                "classification"
            ],
            "profile_id": tail["physical_tail_schedule_dependencies"][
                "profile_id"
            ],
            "multiplier_bits_sha256": tail["multiplier_bits_binding"][
                "bits_sha256"
            ],
            "numeric_classification_repeated": False,
            "binding_status": "BLOCKED_ON_ACCUMULATE_PHYSICAL_IDENTITY",
            "first_break": (
                "accumulate final D layout/base/address/lifetime do not exist, "
                "so tail identity/address/lifetime compatibility cannot be proven"
            ),
        },
        "blocker_delta": {
            "add": ["B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER"],
            "keep": [
                "B_CONV_STEM_PHYSICAL_COVERAGE",
                "B_CONV_STEM_CONFIG_BOUND_W3",
                "B_CONV_STEM_REQUANT_BINDING",
                "B_NODE0004_DYNAMIC_RESULT_PENDING",
            ],
            "close": [
                "B_CONV_STEM_SYMBOLIC_SCHEDULE",
                "B_CONV_STEM_SLICE_CAPACITY_LOWER_BOUND",
            ],
        },
        "package_release": "NONE",
    }


def validate_stem_materialization_gate(
    project_root: Path, report: dict[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    expected = build_stem_materialization_gate(root)
    errors = [] if report == expected else ["published gate differs from current inputs"]
    if report.get("scope", {}).get("new_target_json_generated"):
        errors.append("target JSON must remain absent")
    if report.get("symbolic_output_coverage", {}).get("physical_coverage_claimed"):
        errors.append("symbolic coverage was promoted to physical")
    unexpected = [
        path.as_posix()
        for path in EXPECTED_ABSENT_PATHS
        if (root / path).exists()
    ]
    if unexpected:
        errors.append(f"unexpected target/package path exists: {unexpected}")
    return {
        "schema": "resnet50-stem-serialized-materialization-gate-validation-v1",
        "valid": not errors,
        "errors": errors,
        "numeric_analysis_repeated": False,
        "target_and_package_absent": not unexpected,
        "checked_absent_paths": [
            path.as_posix() for path in EXPECTED_ABSENT_PATHS
        ],
    }


__all__ = [
    "build_stem_materialization_gate",
    "validate_stem_materialization_gate",
]
