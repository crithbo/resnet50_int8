from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

from .w5_conv_preflight import _initializer_values, _load_npy


LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
REQUANT_REL = Path(
    "contracts/operator_config/requant_conv53_tail_signature_binding_v1.json"
)
RUNTIME_REL = Path("artifacts/w3/golden_batch16")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
EXCLUDED_HW_OP_ID = "hwop-0004-00"
SIGNED17_MIN = -(1 << 16)
SIGNED17_MAX = (1 << 16) - 1


class ConvRemaining52Error(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConvRemaining52Error(f"JSON root must be object: {path}")
    return value


def _port(request: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [
        item
        for item in request["ports"]["inputs"]
        if item.get("role") == role
    ]
    if len(matches) != 1:
        raise ConvRemaining52Error(
            f"{request['request_id']} has {len(matches)} {role} ports"
        )
    return matches[0]


def _typed_parameter(request: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item for item in request["typed_parameters"] if item.get("name") == name
    ]
    if len(matches) != 1:
        raise ConvRemaining52Error(
            f"{request['request_id']} has {len(matches)} {name} parameters"
        )
    return matches[0]


def _exact_dot4_domain(
    activation: np.ndarray,
    weight: np.ndarray,
    *,
    x_zero_point: int,
    w_zero_point: np.ndarray,
    strides: tuple[int, int],
    pads: tuple[int, int, int, int],
    dilations: tuple[int, int],
    output_shape: tuple[int, int, int, int],
    output_value_budget: int = 8_000_000,
) -> dict[str, Any]:
    if dilations != (1, 1):
        raise ConvRemaining52Error("current exact scanner supports dilation=1 only")
    if activation.dtype != np.uint8 or weight.dtype != np.int8:
        raise ConvRemaining52Error("dot4 scanner requires uint8 activation/int8 weight")
    n, channels, _, _ = activation.shape
    outputs, weight_channels, kh, kw = weight.shape
    if channels != weight_channels:
        raise ConvRemaining52Error("grouped Conv is not supported by this scanner")
    if w_zero_point.shape != (outputs,):
        raise ConvRemaining52Error("weight zero-point shape differs")
    if np.any(w_zero_point != 0):
        raise ConvRemaining52Error(
            "nonzero per-channel w_zp needs an explicit centered-weight packer"
        )
    pt, pl, pb, pr = pads
    padded = np.pad(
        activation,
        ((0, 0), (0, 0), (pt, pb), (pl, pr)),
        mode="constant",
        constant_values=x_zero_point,
    )
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (kh, kw), axis=(2, 3)
    )
    windows = windows[:, :, :: strides[0], :: strides[1], :, :]
    on, _, oh, ow, _, _ = windows.shape
    if (on, outputs, oh, ow) != output_shape:
        raise ConvRemaining52Error(
            f"patch/output geometry differs: {(on, outputs, oh, ow)} "
            f"!= {output_shape}"
        )
    patches = np.ascontiguousarray(
        windows.transpose(0, 2, 3, 1, 4, 5)
    ).reshape(n * oh * ow, channels * kh * kw)
    packed_weight = np.ascontiguousarray(weight.reshape(outputs, -1))
    logical_k = patches.shape[1]
    groups = math.ceil(logical_k / 4)
    padded_k = groups * 4
    if padded_k != logical_k:
        patch_tail = np.full(
            (patches.shape[0], padded_k - logical_k),
            x_zero_point,
            dtype=np.uint8,
        )
        weight_tail = np.zeros(
            (outputs, padded_k - logical_k), dtype=np.int8
        )
        patches = np.concatenate((patches, patch_tail), axis=1)
        packed_weight = np.concatenate((packed_weight, weight_tail), axis=1)

    x = torch.from_numpy(patches.reshape(-1, groups, 4).astype(np.int32))
    w = torch.from_numpy(
        packed_weight.reshape(outputs, groups, 4).astype(np.int32)
    )
    p_chunk = min(512, max(1, x.shape[0]))
    g_chunk = max(1, output_value_budget // max(1, p_chunk * outputs))
    minimum = 1 << 62
    maximum = -(1 << 62)
    violation_count = 0
    witness: dict[str, Any] | None = None
    counted = 0
    for p_start in range(0, x.shape[0], p_chunk):
        xp = x[p_start : p_start + p_chunk]
        for g_start in range(0, groups, g_chunk):
            xg = xp[:, g_start : g_start + g_chunk, :]
            wg = w[:, g_start : g_start + g_chunk, :]
            dot = torch.einsum("pgk,ogk->pgo", xg, wg)
            lo, hi = torch.aminmax(dot)
            minimum = min(minimum, int(lo))
            maximum = max(maximum, int(hi))
            bad = (dot < SIGNED17_MIN) | (dot > SIGNED17_MAX)
            current_bad = int(torch.count_nonzero(bad))
            violation_count += current_bad
            counted += dot.numel()
            if current_bad and witness is None:
                local = torch.nonzero(bad, as_tuple=False)[0]
                lp, lg, oc = (int(item) for item in local)
                p_index = p_start + lp
                group_index = g_start + lg
                lanes_x = x[p_index, group_index].tolist()
                lanes_w = w[oc, group_index].tolist()
                witness = {
                    "output_flat_nhw_index": p_index,
                    "output_channel": oc,
                    "k_group": group_index,
                    "activation_u8_lanes": lanes_x,
                    "weight_s8_lanes": lanes_w,
                    "lane_products": [
                        int(left) * int(right)
                        for left, right in zip(lanes_x, lanes_w, strict=True)
                    ],
                    "dot4": int(dot[lp, lg, oc]),
                }
    expected = math.prod(output_shape) * groups
    if counted != expected:
        raise ConvRemaining52Error(
            f"dot4 count differs: {counted} != {expected}"
        )
    return {
        "operand_domain": "final packed DataA=s8 weight, DataB=u8 activation",
        "reduction_order": "OIHW flatten: input_channel -> kernel_h -> kernel_w",
        "padding_activation_value": x_zero_point,
        "padding_weight_value": 0,
        "logical_k": logical_k,
        "dot4_group_count_per_output": groups,
        "tail_lane_count": logical_k % 4,
        "padded_zero_product_lane_count_per_output": padded_k - logical_k,
        "actual_w3_dot4_count": counted,
        "actual_w3_dot4_range": [minimum, maximum],
        "signed17_legal_range": [SIGNED17_MIN, SIGNED17_MAX],
        "signed17_violation_count": violation_count,
        "first_signed17_violation": witness,
        "exact_full_enumeration": True,
    }


def _small_oracle() -> dict[str, Any]:
    activation = np.array(
        [[[[0, 255]], [[3, 4]], [[7, 8]]]], dtype=np.uint8
    )
    weight = np.array(
        [
            [[[127]], [[-128]], [[3]]],
            [[[-5]], [[11]], [[-9]]],
        ],
        dtype=np.int8,
    )
    report = _exact_dot4_domain(
        activation,
        weight,
        x_zero_point=17,
        w_zero_point=np.zeros(2, dtype=np.int8),
        strides=(1, 1),
        pads=(0, 0, 0, 0),
        dilations=(1, 1),
        output_shape=(1, 2, 1, 2),
    )
    scalar = []
    for position in range(2):
        lanes = [int(activation[0, c, 0, position]) for c in range(3)] + [17]
        for oc in range(2):
            weights = [int(weight[oc, c, 0, 0]) for c in range(3)] + [0]
            scalar.append(sum(a * b for a, b in zip(lanes, weights, strict=True)))
    if report["actual_w3_dot4_range"] != [min(scalar), max(scalar)]:
        raise ConvRemaining52Error("small dot4 oracle differs")
    return {
        "case_count": len(scalar),
        "range": [min(scalar), max(scalar)],
        "k_tail": 3,
        "nonzero_x_zp_padding_product_is_zero": True,
        "status": "PASS",
    }


def build_remaining52_expansion(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_path = root / LOWERING_REL
    requant_path = root / REQUANT_REL
    runtime_manifest_path = root / RUNTIME_REL / "manifest.json"
    lowering = _load(lowering_path)
    requant = _load(requant_path)
    runtime = _load(runtime_manifest_path)
    initializers = _initializer_values(root / MODEL_REL)

    conv_requests = [
        item
        for item in lowering["requests"]
        if item["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    ]
    remaining = [
        item
        for item in conv_requests
        if item["identity"]["hw_op_id"] != EXCLUDED_HW_OP_ID
    ]
    if len(conv_requests) != 53 or len(remaining) != 52:
        raise ConvRemaining52Error("Conv census differs from 53/52")
    tail_by_node = {
        item["typed_request"]["node_id"]: item
        for item in requant["stage_bindings"]
    }
    if len(tail_by_node) != 53:
        raise ConvRemaining52Error("Requant dependency does not cover 53 Conv")

    records: list[dict[str, Any]] = []
    for index, request in enumerate(remaining, start=1):
        identity = request["identity"]
        geometry = request["logical_geometry"]
        attrs = geometry["attributes"]
        x_port = _port(request, "x")
        w_port = _port(request, "w")
        wzp_port = _port(request, "w_zero_point")
        bias_port = _port(request, "bias")
        x_record = runtime["tensors"][x_port["tensor_id"]]
        activation = _load_npy(root / RUNTIME_REL, runtime, x_record)
        weight = initializers[w_port["onnx_name"]]
        w_zero_point = initializers[wzp_port["onnx_name"]]
        x_zp = int(
            _typed_parameter(request, "x_zero_point")["value"]["scalar"]
        )
        output_shape = tuple(geometry["output_shapes"][0])
        domain = _exact_dot4_domain(
            activation,
            weight,
            x_zero_point=x_zp,
            w_zero_point=w_zero_point,
            strides=tuple(attrs["strides"]),
            pads=tuple(attrs["pads"]),
            dilations=tuple(attrs["dilations"]),
            output_shape=output_shape,
        )
        tail = tail_by_node[identity["node_id"]]
        physical_tail = tail["physical_tail_schedule_dependencies"]
        rounding = tail["rounding_saturation_binding"]
        logical_k = domain["logical_k"]
        groups = domain["dot4_group_count_per_output"]
        output_elements = math.prod(output_shape)
        fallback_padded = output_elements * groups * 4
        route = (
            "NORMAL_FOUR_LANE_DOMAIN_COMPATIBLE_UNDER_ASSUMED_FIXED_HARDWARE"
            if domain["signed17_violation_count"] == 0
            else "ONE_PRODUCT_LANE_DATAC_FALLBACK_REQUIRED"
        )
        signature_fields = {
            "kernel": list(weight.shape[2:]),
            "stride": attrs["strides"],
            "padding": attrs["pads"],
            "dilation": attrs["dilations"],
            "group": attrs["group"],
            "input_shape_nchw": geometry["input_shapes"][0],
            "weight_shape_oihw": geometry["input_shapes"][2],
            "output_shape_nchw": geometry["output_shapes"][0],
            "k": logical_k,
            "k_group_count": groups,
            "k_tail_lane_count": logical_k % 4,
            "sample_wave_forecast": physical_tail["sample_waves_forecast"],
            "bias_present": True,
            "input_zero_point": x_zp,
            "output_requant_profile": rounding["profile_id"],
            "tail_physical_schedule_profile": physical_tail["profile_id"],
        }
        records.append(
            {
                "ordinal_within_remaining52": index,
                "identity": {
                    **identity,
                    "request_id": request["request_id"],
                    "request_sha256": request["request_sha256"],
                },
                "source_ownership": {
                    "activation": {
                        "tensor_id": x_port["tensor_id"],
                        "identity_sha256": x_port["identity_sha256"],
                        "source": x_port["identity_source"],
                    },
                    "weight": {
                        "onnx_name": w_port["onnx_name"],
                        "tensor_id": w_port["tensor_id"],
                        "identity_sha256": w_port["identity_sha256"],
                    },
                    "weight_zero_point": {
                        "onnx_name": wzp_port["onnx_name"],
                        "identity_sha256": wzp_port["identity_sha256"],
                    },
                    "bias": {
                        "onnx_name": bias_port["onnx_name"],
                        "identity_sha256": bias_port["identity_sha256"],
                    },
                    "requant_dependency_signature_sha256": tail[
                        "signature_sha256"
                    ],
                },
                "schedule_signature": {
                    "signature_id": canonical_sha256(signature_fields),
                    "fields": signature_fields,
                    "physical_binding_status": "LIST_ONLY_DYNAMIC_GATE_PENDING",
                },
                "final_lane_packing_domain": domain,
                "route_adjudication": {
                    "route": route,
                    "hardware_semantics_assumed_available": True,
                    "final_trassic20_rtl_commit_bound": False,
                    "counts_as_e4_or_e5": False,
                },
                "resource_and_occurrence_forecast": {
                    "output_element_count": output_elements,
                    "normal_dot4_occurrence_count": domain[
                        "actual_w3_dot4_count"
                    ],
                    "normal_lane_utilization": logical_k / (groups * 4),
                    "serialized_padded_occurrence_count": fallback_padded,
                    "serialized_occurrence_ratio_vs_dot4": 4.0,
                    "serialized_effective_lane_utilization_upper_bound": (
                        logical_k / (groups * 16)
                    ),
                    "activation_bytes": int(activation.nbytes),
                    "weight_bytes": int(weight.nbytes),
                    "bias_bytes": int(np.prod(weight.shape[:1]) * 4),
                    "int32_output_bytes": output_elements * 4,
                    "physical_address_lifetime_binding_pending": True,
                },
                "requant_read_only_dependency": {
                    "profile_id": physical_tail["profile_id"],
                    "rounding_profile_id": rounding["profile_id"],
                    "multiplier_bits_sha256": tail[
                        "multiplier_bits_binding"
                    ]["bits_sha256"],
                    "fresh_multiplier_binding_required": True,
                    "fresh_address_lifetime_binding_required": True,
                    "node0004_constant_reuse_allowed": False,
                    "w3_classification_repeated": False,
                },
            }
        )

    signature_groups: dict[str, list[str]] = {}
    route_counts: dict[str, int] = {}
    for record in records:
        signature_id = record["schedule_signature"]["signature_id"]
        signature_groups.setdefault(signature_id, []).append(
            record["identity"]["hw_op_id"]
        )
        route = record["route_adjudication"]["route"]
        route_counts[route] = route_counts.get(route, 0) + 1
    return {
        "schema": "resnet50-conv-sa-remaining52-expansion-v1",
        "status": "LOCAL_EXPANSION_LIST_COMPLETE_DYNAMIC_GATE_PENDING",
        "owner_family": "Conv/SA",
        "scope": {
            "typed_conv_count": 53,
            "excluded_frozen_anchor": EXCLUDED_HW_OP_ID,
            "remaining_conv_count": len(records),
            "new_target_json_generated": False,
            "new_mapping_bitstream_execplan_sca_generated": False,
            "new_server_package_generated_for_remaining52": False,
        },
        "source_receipts": {
            LOWERING_REL.as_posix(): sha256_file(lowering_path),
            REQUANT_REL.as_posix(): sha256_file(requant_path),
            (RUNTIME_REL / "manifest.json").as_posix(): sha256_file(
                runtime_manifest_path
            ),
            MODEL_REL.as_posix(): sha256_file(root / MODEL_REL),
        },
        "analysis": {
            "numeric_analysis_repeated_for_node0004": False,
            "new_numeric_analysis_performed_for_remaining52": True,
            "requant_w3_classification_repeated": False,
            "reuse_assets_consumed": True,
            "reused_assets": [
                "trusted typed lowering requests",
                "formal ONNX/W3 activation and initializer tensors",
                "requant_conv53_tail_signature_binding_v1 read-only profiles",
            ],
            "small_oracle": _small_oracle(),
            "actual_w3_dot4_count_total": sum(
                item["final_lane_packing_domain"]["actual_w3_dot4_count"]
                for item in records
            ),
            "route_counts": route_counts,
        },
        "schedule_group_summary": {
            "exact_schedule_signature_count": len(signature_groups),
            "groups": [
                {
                    "signature_id": signature_id,
                    "member_count": len(members),
                    "member_hw_op_ids": members,
                }
                for signature_id, members in sorted(signature_groups.items())
            ],
        },
        "claim_boundary": {
            "hardware_semantics_assumed_available": True,
            "final_trassic20_rtl_commit_bound": False,
            "list_only": True,
            "counts_as_e2_for_remaining52": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
            "bulk_materialization_allowed_before_valid_node0004_dynamic": False,
        },
        "records": records,
    }


def validate_remaining52_expansion(
    project_root: Path, report: dict[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    errors: list[str] = []
    if report.get("schema") != "resnet50-conv-sa-remaining52-expansion-v1":
        errors.append("schema differs")
    records = report.get("records")
    if not isinstance(records, list) or len(records) != 52:
        errors.append("record count differs")
        records = []
    receipts = report.get("source_receipts", {})
    for relative in (LOWERING_REL, REQUANT_REL, RUNTIME_REL / "manifest.json", MODEL_REL):
        path = root / relative
        if receipts.get(relative.as_posix()) != sha256_file(path):
            errors.append(f"source receipt differs: {relative.as_posix()}")
    ids = [item.get("identity", {}).get("hw_op_id") for item in records]
    if len(ids) != len(set(ids)) or EXCLUDED_HW_OP_ID in ids:
        errors.append("remaining52 identity set differs")
    total = 0
    lowering = _load(root / LOWERING_REL)
    typed_by_id = {
        item["identity"]["hw_op_id"]: item
        for item in lowering["requests"]
        if item["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    }
    requant = _load(root / REQUANT_REL)
    tail_by_node = {
        item["typed_request"]["node_id"]: item
        for item in requant["stage_bindings"]
    }
    for item in records:
        domain = item["final_lane_packing_domain"]
        fields = item["schedule_signature"]["fields"]
        hw_op_id = item["identity"]["hw_op_id"]
        typed = typed_by_id.get(hw_op_id)
        if typed is None:
            errors.append(f"typed request missing: {hw_op_id}")
            continue
        geometry = typed["logical_geometry"]
        attributes = geometry["attributes"]
        expected_fields = {
            "kernel": geometry["input_shapes"][2][2:],
            "stride": attributes["strides"],
            "padding": attributes["pads"],
            "dilation": attributes["dilations"],
            "group": attributes["group"],
            "input_shape_nchw": geometry["input_shapes"][0],
            "weight_shape_oihw": geometry["input_shapes"][2],
            "output_shape_nchw": geometry["output_shapes"][0],
        }
        for name, expected_value in expected_fields.items():
            if fields.get(name) != expected_value:
                errors.append(f"typed field differs: {hw_op_id}:{name}")
        if item["identity"]["request_sha256"] != typed["request_sha256"]:
            errors.append(f"request receipt differs: {hw_op_id}")
        tail = tail_by_node.get(item["identity"]["node_id"])
        if tail is None:
            errors.append(f"Requant dependency missing: {hw_op_id}")
        else:
            dependency = item["requant_read_only_dependency"]
            if (
                dependency["profile_id"]
                != tail["physical_tail_schedule_dependencies"]["profile_id"]
                or dependency["rounding_profile_id"]
                != tail["rounding_saturation_binding"]["profile_id"]
                or dependency["multiplier_bits_sha256"]
                != tail["multiplier_bits_binding"]["bits_sha256"]
            ):
                errors.append(f"Requant dependency differs: {hw_op_id}")
        expected = math.prod(fields["output_shape_nchw"]) * fields["k_group_count"]
        if domain["actual_w3_dot4_count"] != expected:
            errors.append(f"dot4 count differs: {item['identity']['hw_op_id']}")
        total += expected
        violations = domain["signed17_violation_count"]
        route = item["route_adjudication"]["route"]
        if (violations == 0) != route.startswith("NORMAL_FOUR_LANE"):
            errors.append(f"route/domain differs: {item['identity']['hw_op_id']}")
        if item["requant_read_only_dependency"]["w3_classification_repeated"]:
            errors.append("Requant classification was repeated")
    if total != report.get("analysis", {}).get("actual_w3_dot4_count_total"):
        errors.append("aggregate dot4 count differs")
    if report.get("scope", {}).get("new_server_package_generated_for_remaining52"):
        errors.append("remaining52 package generation is forbidden")
    return {
        "schema": "resnet50-conv-sa-remaining52-expansion-validation-v1",
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
        "record_count": len(records),
        "numeric_analysis_repeated_by_validator": False,
        "small_oracle_status": _small_oracle()["status"],
    }


__all__ = [
    "ConvRemaining52Error",
    "build_remaining52_expansion",
    "validate_remaining52_expansion",
]
